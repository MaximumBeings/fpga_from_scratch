// verilator lint_off DECLFILENAME
// verilator lint_off UNUSEDSIGNAL
// Chapter 10: match engines. Every engine answers the same question, "which entry, if any, matches this key?", through the same pins and with the same latency, so that one testbench and one model serve all of them:
//   query : q_valid, q_key (32 bits). Result: r_valid TWO cycles later, r_hit, r_val (8 bits; 0 on a miss).
//   write : w_en, w_sel (which table, hash engines only), w_addr (the slot), w_key, w_aux, w_val, w_vld (0 deletes the slot). The control plane (software) decides WHERE an entry goes; the hardware only stores it.
//   One operation per cycle. A query sees every write issued in an EARLIER cycle (and none issued later), whatever the pipeline stage it is in.
//   The data inputs are don't-cares when q_valid / w_en is low and are ignored; r_hit and r_val are don't-cares when r_valid is low.
//
// match_cam: N entries in registers, all compared with the key in ONE cycle. MODE 0 = exact match on w_key; MODE 1 = ternary (TCAM): a bit of w_aux set means "this bit of the key must match", clear means don't care; MODE 2 = range: the low 16 bits of the key must lie in [w_aux[15:0], w_aux[31:16]] (an empty range, lo > hi, never matches). Several entries may match: the LOWEST slot number wins (priority). Stage 1 registers the N match bits; stage 2 picks the lowest and reads its value, which is read in the cycle after the compare: a write in that cycle takes effect at its end, so the older query still sees the old value. N must be a power of two.
module match_cam #(parameter int N = 16, parameter int MODE = 0) (
    input logic clk, input logic rst,
    input logic q_valid, input logic [31:0] q_key,
    input logic w_en, input logic w_sel, input logic [11:0] w_addr, input logic [31:0] w_key, input logic [31:0] w_aux, input logic [7:0] w_val, input logic w_vld,
    output logic r_valid, output logic r_hit, output logic [7:0] r_val);
    localparam int IW = $clog2(N);
    logic [31:0] k [0:N-1]; logic [31:0] a [0:N-1]; logic [7:0] v [0:N-1]; logic [N-1:0] vld, hv, hv_r; logic qv_r;
    always_comb begin
        for (int i = 0; i < N; i++) begin
            case (MODE)
                0: hv[i] = vld[i] && (k[i] == q_key);
                1: hv[i] = vld[i] && (((k[i] ^ q_key) & a[i]) == 32'd0);
                default: hv[i] = vld[i] && (q_key[15:0] >= a[i][15:0]) && (q_key[15:0] <= a[i][31:16]);
            endcase
        end
    end
    always_ff @(posedge clk) begin
        if (w_en) begin k[w_addr[IW-1:0]] <= w_key; a[w_addr[IW-1:0]] <= w_aux; v[w_addr[IW-1:0]] <= w_val; end
        if (rst) vld <= '0; else if (w_en) vld[w_addr[IW-1:0]] <= w_vld;
        hv_r <= hv; qv_r <= q_valid && !rst;
    end
    logic found; logic [IW-1:0] idx;
    always_comb begin
        found = 1'b0; idx = '0;
        for (int i = N - 1; i >= 0; i--) if (hv_r[i]) begin found = 1'b1; idx = IW'(i); end          // the last assignment is the lowest index
    end
    always_ff @(posedge clk) begin r_valid <= qv_r; r_hit <= found; r_val <= found ? v[idx] : 8'd0; end
endmodule
// hash_tab: an exact-match table in block RAM. CH = 1: one table of 2^AW slots, indexed by hash 1 of the key. CH = 2: two tables of 2^AW slots, indexed by hash 1 and hash 2, BOTH read in the same cycle (two-choice hashing: an entry may live in either). Each slot holds {valid, the low KW bits of the key, value}: KW = 32 is exact; KW < 32 stores only a FINGERPRINT of the key, which makes the table a filter that can answer "hit" for a key that was never inserted (a false positive) but never "miss" for one that was.
// The hash is the XOR of the key's AW-bit chunks (fold); hash 2 is the same fold of the key rotated left by 13 and XORed with the key shifted right by 5. Cheap in logic, and the chapter measures where it is good and where it is not. Stage 1 reads the RAM(s) (the key is held for one cycle); stage 2 compares and registers the result.
module hash_tab #(parameter int AW = 8, parameter int CH = 2, parameter int KW = 32) (
    input logic clk, input logic rst,
    input logic q_valid, input logic [31:0] q_key,
    input logic w_en, input logic w_sel, input logic [11:0] w_addr, input logic [31:0] w_key, input logic [31:0] w_aux, input logic [7:0] w_val, input logic w_vld,
    output logic r_valid, output logic r_hit, output logic [7:0] r_val);
    localparam int EW = 1 + KW + 8;
    function automatic logic [AW-1:0] fold(input logic [31:0] x);
        logic [AW-1:0] s; s = '0;
        for (int i = 0; i < 32; i += AW) s = s ^ AW'(x >> i);
        fold = s;
    endfunction
    logic [EW-1:0] m0 [0:(1 << AW) - 1]; logic [EW-1:0] m1 [0:(1 << AW) - 1]; logic [EW-1:0] r0, r1; logic [31:0] qk; logic qv; logic [AW-1:0] h1, h2;
    assign h1 = fold(q_key);
    assign h2 = fold({q_key[18:0], q_key[31:19]} ^ {5'd0, q_key[31:5]});
    always_ff @(posedge clk) begin
        if (w_en && !w_sel) m0[w_addr[AW-1:0]] <= {w_vld, w_key[KW-1:0], w_val};
        r0 <= m0[h1];
    end
    if (CH == 2) begin : g2
        always_ff @(posedge clk) begin
            if (w_en && w_sel) m1[w_addr[AW-1:0]] <= {w_vld, w_key[KW-1:0], w_val};
            r1 <= m1[h2];
        end
    end else begin : g1
        assign r1 = '0;
    end
    always_ff @(posedge clk) begin qk <= q_key; qv <= q_valid && !rst; end
    logic hit0, hit1;
    assign hit0 = r0[EW-1] && (r0[EW-2:8] == qk[KW-1:0]);
    assign hit1 = (CH == 2) && r1[EW-1] && (r1[EW-2:8] == qk[KW-1:0]);
    always_ff @(posedge clk) begin r_valid <= qv; r_hit <= hit0 || hit1; r_val <= hit0 ? r0[7:0] : hit1 ? r1[7:0] : 8'd0; end
endmodule
