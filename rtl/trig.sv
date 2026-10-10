// Chapter 21: the trigger engine. A message goes through a symbol table (a hash table in K RAM banks, all K ways read at once) and R rules (predicates compared in parallel), one message per cycle, never stalled; the answer, in cycle a + 4 + PIPE for a message offered in cycle a, is the set of rules that matched. The table is written by address (the control plane places keys); the rules are written by index. The specification (and the exact rules for when a write is first seen) is in model/trig_gold.py.
module trig #(parameter int NB = 8, parameter int K = 2, parameter int R = 4, parameter int PIPE = 0) (
    input  logic clk, input logic rst,
    input  logic in_valid, input logic [2:0] in_type, input logic [31:0] in_key, input logic in_side, input logic [31:0] in_px, input logic [31:0] in_sh,
    input  logic cfg_valid, input logic [3:0] cfg_rule, input logic cfg_en, input logic cfg_neg, input logic [4:0] cfg_tmask, input logic cfg_symany, input logic cfg_sideany, input logic cfg_side,
    input  logic [2:0] cfg_pxop, input logic [2:0] cfg_shop, input logic [31:0] cfg_symmask, input logic [31:0] cfg_pxval, input logic [31:0] cfg_shval,
    input  logic ld_valid, input logic [11:0] ld_addr, input logic [31:0] ld_key, input logic [4:0] ld_idx, input logic ld_val,
    output logic o_ready,
    output logic o_valid, output logic o_found, output logic [4:0] o_idx, output logic [R-1:0] o_mask, output logic o_fire, output logic [3:0] o_first);
    localparam int BW = (NB > 1) ? $clog2(NB) : 1, KB = 32 - BW, WW = 1 + KB + 5;      // NB from 2 to 256: a stored key omits the low BW bits, which the row (the hash) and the other bits already give
    // ---- the symbol table: K banks of NB words {valid, key without its low BW bits, index}, cleared by a sweep after reset (NB cycles); a lookup reads the same row of every bank
    logic [BW-1:0] ini; logic ini_run;
    wire [BW-1:0] hrow = BW'(in_key ^ (in_key >> 8) ^ (in_key >> 16) ^ (in_key >> 24));
    logic [WW-1:0] rdw [0:K-1];
    for (genvar g = 0; g < K; g++) begin : way
        logic [WW-1:0] mem [0:NB-1]; logic [WW-1:0] rd;
        always_ff @(posedge clk) begin
            if (ini_run) mem[ini] <= '0;
            else if (ld_valid && (ld_addr % 12'(K)) == 12'(g)) mem[BW'(ld_addr / 12'(K))] <= {ld_val, ld_key[31:BW], ld_idx};
            rd <= mem[hrow];
        end
        assign rdw[g] = rd;
    end
    // the low BW bits of a key are not stored or compared (see above): say so to the lint
    /* verilator lint_off UNUSEDSIGNAL */ wire unused_low_key_bits = &{1'b0, ld_key[BW-1:0], s1_key[BW-1:0]}; /* verilator lint_on UNUSEDSIGNAL */
    assign o_ready = !ini_run;
    // ---- stage 1: the message registered while the banks are read
    logic s1_v, s1_side; logic [2:0] s1_t; logic [31:0] s1_key, s1_px, s1_sh;
    always_ff @(posedge clk) begin
        s1_v <= in_valid; s1_t <= in_type; s1_key <= in_key; s1_side <= in_side; s1_px <= in_px; s1_sh <= in_sh;
        if (rst) begin ini_run <= 1'b1; ini <= '0; end
        else if (ini_run) begin ini <= ini + 1'b1; if (ini == BW'(NB - 1)) ini_run <= 1'b0; end
    end
    // ---- stage 2: the K ways are compared with the key; at most one matches (keys are unique in the table)
    logic [K-1:0] hitw; logic [4:0] idx_or;
    always_comb begin
        idx_or = '0;
        for (int g = 0; g < K; g++) begin hitw[g] = rdw[g][WW-1] && (rdw[g][WW-2 -: KB] == s1_key[31:BW]); if (hitw[g]) idx_or = idx_or | rdw[g][4:0]; end
    end
    logic s2_v, s2_found, s2_side; logic [4:0] s2_idx; logic [2:0] s2_t; logic [31:0] s2_px, s2_sh;
    always_ff @(posedge clk) begin
        s2_v <= s1_v; s2_found <= |hitw; s2_idx <= idx_or; s2_t <= s1_t; s2_side <= s1_side; s2_px <= s1_px; s2_sh <= s1_sh;
    end
    // ---- the rules
    logic r_en [0:R-1]; logic r_neg [0:R-1]; logic [4:0] r_tmask [0:R-1]; logic r_symany [0:R-1]; logic r_sideany [0:R-1]; logic r_side [0:R-1]; logic [2:0] r_pxop [0:R-1]; logic [2:0] r_shop [0:R-1]; logic [31:0] r_symmask [0:R-1]; logic [31:0] r_pxval [0:R-1]; logic [31:0] r_shval [0:R-1];
    always_ff @(posedge clk) begin
        if (rst) for (int r = 0; r < R; r++) r_en[r] <= 1'b0;
        else if (cfg_valid) for (int r = 0; r < R; r++) if (cfg_rule == 4'(r)) begin
            r_en[r] <= cfg_en; r_neg[r] <= cfg_neg; r_tmask[r] <= cfg_tmask; r_symany[r] <= cfg_symany; r_sideany[r] <= cfg_sideany; r_side[r] <= cfg_side; r_pxop[r] <= cfg_pxop; r_shop[r] <= cfg_shop;
            r_symmask[r] <= cfg_symmask; r_pxval[r] <= cfg_pxval; r_shval[r] <= cfg_shval;
        end
    end
    function automatic logic cmpf(input logic [2:0] op, input logic lt, input logic eq);          // the comparison of x with c, from x < c and x == c
        case (op)
            3'd0: cmpf = 1'b1;  3'd1: cmpf = lt;  3'd2: cmpf = lt | eq;  3'd3: cmpf = eq;  3'd4: cmpf = !eq;  3'd5: cmpf = !lt;  3'd6: cmpf = !(lt | eq);  default: cmpf = 1'b0;
        endcase
    endfunction
    // the part of a rule that does not depend on the price and the shares
    logic pre [0:R-1];
    always_comb for (int r = 0; r < R; r++) pre[r] = r_tmask[r][s2_t[2:0]] && (r_symany[r] || (s2_found && r_symmask[r][s2_idx])) && (r_sideany[r] || (s2_side == r_side[r]));
    // ---- stage 2 (the comparisons) and, with PIPE = 1, the stage that combines the two halves
    logic [R-1:0] s3_m; logic s3_v, s3_found; logic [4:0] s3_idx;
    if (PIPE == 0) begin : cmp1
        always_ff @(posedge clk) begin
            for (int r = 0; r < R; r++) s3_m[r] <= r_en[r] && ((pre[r] && cmpf(r_pxop[r], s2_px < r_pxval[r], s2_px == r_pxval[r]) && cmpf(r_shop[r], s2_sh < r_shval[r], s2_sh == r_shval[r])) != r_neg[r]);
            s3_v <= s2_v && !rst; s3_found <= s2_found; s3_idx <= s2_idx;
        end
    end else begin : cmp2
        logic [R-1:0] a_pre, a_en, a_neg, p_hlt, p_heq, p_llt, p_leq, q_hlt, q_heq, q_llt, q_leq; logic [2:0] a_pxop [0:R-1]; logic [2:0] a_shop [0:R-1]; logic a_v, a_found; logic [4:0] a_idx;
        always_ff @(posedge clk) begin
            for (int r = 0; r < R; r++) begin
                a_pre[r] <= pre[r]; a_en[r] <= r_en[r]; a_neg[r] <= r_neg[r]; a_pxop[r] <= r_pxop[r]; a_shop[r] <= r_shop[r];
                p_hlt[r] <= s2_px[31:16] < r_pxval[r][31:16]; p_heq[r] <= s2_px[31:16] == r_pxval[r][31:16]; p_llt[r] <= s2_px[15:0] < r_pxval[r][15:0]; p_leq[r] <= s2_px[15:0] == r_pxval[r][15:0];
                q_hlt[r] <= s2_sh[31:16] < r_shval[r][31:16]; q_heq[r] <= s2_sh[31:16] == r_shval[r][31:16]; q_llt[r] <= s2_sh[15:0] < r_shval[r][15:0]; q_leq[r] <= s2_sh[15:0] == r_shval[r][15:0];
            end
            a_v <= s2_v; a_found <= s2_found; a_idx <= s2_idx;
        end
        always_ff @(posedge clk) begin
            for (int r = 0; r < R; r++) s3_m[r] <= a_en[r] && ((a_pre[r] && cmpf(a_pxop[r], p_hlt[r] | (p_heq[r] & p_llt[r]), p_heq[r] & p_leq[r]) && cmpf(a_shop[r], q_hlt[r] | (q_heq[r] & q_llt[r]), q_heq[r] & q_leq[r])) != a_neg[r]);
            s3_v <= a_v && !rst; s3_found <= a_found; s3_idx <= a_idx;
        end
    end
    // ---- the last stage: which rules matched, whether any, and the first
    always_ff @(posedge clk) begin
        o_valid <= s3_v; o_found <= s3_found; o_idx <= s3_idx; o_mask <= s3_m; o_fire <= |s3_m;
        o_first <= '0;
        for (int r = R - 1; r >= 0; r--) if (s3_m[r]) o_first <= 4'(r);
    end
endmodule
// trig_syn: the same design behind a handful of pins, ONLY so that it fits a chip for the place-and-route runs: the inputs (messages, rule writes and table writes, 270 bits) are shifted in serially, the outputs registered and folded into one 16-bit word.
module trig_syn #(parameter int NB = 8, parameter int K = 2, parameter int R = 4, parameter int PIPE = 0) (input logic clk, input logic rst, input logic si, input logic sh, output logic [15:0] info);
    logic [269:0] iv; logic ready, ov_, fnd, fire; logic [4:0] idx; logic [R-1:0] mask; logic [3:0] first;
    always_ff @(posedge clk) if (sh) iv <= {iv[268:0], si};
    trig #(.NB(NB), .K(K), .R(R), .PIPE(PIPE)) u (.clk(clk), .rst(rst),
        .in_valid(iv[0]), .in_type(iv[3:1]), .in_side(iv[4]), .in_key(iv[36:5]), .in_px(iv[68:37]), .in_sh(iv[100:69]),
        .cfg_valid(iv[101]), .cfg_rule(iv[105:102]), .cfg_en(iv[106]), .cfg_neg(iv[107]), .cfg_tmask(iv[112:108]), .cfg_symany(iv[113]), .cfg_sideany(iv[114]), .cfg_side(iv[115]), .cfg_pxop(iv[118:116]), .cfg_shop(iv[121:119]), .cfg_symmask(iv[153:122]), .cfg_pxval(iv[185:154]), .cfg_shval(iv[217:186]),
        .ld_valid(iv[218]), .ld_addr(iv[230:219]), .ld_key(iv[262:231]), .ld_idx(iv[267:263]), .ld_val(iv[268]),
        .o_ready(ready), .o_valid(ov_), .o_found(fnd), .o_idx(idx), .o_mask(mask), .o_fire(fire), .o_first(first));
    logic [15:0] x, r1; always_comb x = 16'(mask) ^ {first, idx, fnd, fire, ov_, ready, iv[269], 1'b0, 1'b0};
    always_ff @(posedge clk) begin r1 <= x; info <= r1; end
endmodule
