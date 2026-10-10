// verilator lint_off DECLFILENAME
// Chapter 18: the sequencer and A/B arbiter at the packet level. Behaviour, rules and every simplification are those of model/arb_gold.py, cycle for cycle.
// One packet header per cycle (feed 0 = A, 1 = B, 2 = retransmission; 32-bit sequence number; 16-bit count; count 0 is a heartbeat). The arbiter forwards each packet once, in order: a packet that arrives AHEAD of the expected sequence number is kept in one of PEND slots until it is in order (then released, one per cycle, with priority over the input), a copy of one already forwarded or kept is dropped, and a GAP that lasts TO cycles is requested (REQ: sequence number and count of the missing range); a request not answered within TO2 more cycles is given up (SKIP: the range is reported lost and the arbiter moves on). While a release or a SKIP happens in_ready is 0.
// Outputs are registered (seen the cycle after): d_* the decision for the input or the release (kind 0 FWD, 1 STORE, 2 DUP, 3 BAD, 4 OVF, 5 HB, 6 REL), t_* the timer event (1 REQ, 2 SKIP); o_next and o_np (slots in use) are the state.
module seq_arb #(parameter int PEND = 4, parameter int TO = 16, parameter int TO2 = 64, parameter logic [31:0] INIT = 32'd1) (
    input logic clk, input logic rst,
    input logic in_valid, input logic [1:0] in_feed, input logic [31:0] in_seq, input logic [15:0] in_cnt, output logic in_ready,
    output logic d_valid, output logic [2:0] d_kind, output logic [31:0] d_seq, output logic [15:0] d_cnt, output logic [1:0] d_feed,
    output logic t_valid, output logic [1:0] t_kind, output logic [31:0] t_seq, output logic [31:0] t_cnt,
    output logic [31:0] o_next, output logic [3:0] o_np);
    localparam int IW = (PEND > 1) ? $clog2(PEND) : 1;
    logic sv [PEND]; logic [31:0] ss [PEND]; logic [15:0] sc [PEND]; logic [1:0] sf [PEND];
    logic [31:0] nx; logic [15:0] tmr; logic req;
    logic rel_any, has_pend, gap, req_fire, skip_fire, accept, same, free_any, dz, bh, dup_beh, cnt0; logic [IW-1:0] rel_idx, free_idx; logic [31:0] mind, d, e, di; logic [3:0] np;
    always_comb begin
        rel_any = 1'b0; rel_idx = '0; has_pend = 1'b0; mind = 32'hffffffff; same = 1'b0; free_any = 1'b0; free_idx = '0; np = 4'd0;
        for (int i = PEND - 1; i >= 0; i--) begin
            di = ss[i] - nx;
            if (sv[i]) begin has_pend = 1'b1; np = np + 4'd1; if (di < mind) mind = di; if (di == 32'd0) begin rel_any = 1'b1; rel_idx = IW'(i); end if (ss[i] == in_seq) same = 1'b1; end
            else begin free_any = 1'b1; free_idx = IW'(i); end
        end
        gap = has_pend && !rel_any;
        req_fire = gap && !req && (tmr == 16'(TO)); skip_fire = gap && req && (tmr == 16'(TO2));
        in_ready = !rel_any && !skip_fire; accept = in_valid && in_ready;
        d = in_seq - nx; e = d + {16'd0, in_cnt}; cnt0 = (in_cnt == 16'd0); dz = (d == 32'd0); bh = d[31]; dup_beh = e[31] || (e == 32'd0);
        o_next = nx; o_np = np;
    end
    always_ff @(posedge clk) begin
        d_valid <= 1'b0; t_valid <= 1'b0;
        if (rst) begin
            nx <= INIT; tmr <= 16'd0; req <= 1'b0; for (int i = 0; i < PEND; i++) sv[i] <= 1'b0;
        end else begin
            if (!gap) begin tmr <= 16'd0; req <= 1'b0; end
            else if (req_fire) begin tmr <= 16'd0; req <= 1'b1; end
            else if (skip_fire) begin tmr <= 16'd0; req <= 1'b0; end
            else tmr <= tmr + 16'd1;
            if (req_fire) begin t_valid <= 1'b1; t_kind <= 2'd1; t_seq <= nx; t_cnt <= (mind > 32'hffff) ? 32'hffff : mind; end
            if (skip_fire) begin t_valid <= 1'b1; t_kind <= 2'd2; t_seq <= nx; t_cnt <= mind; nx <= nx + mind; end
            if (rel_any) begin
                d_valid <= 1'b1; d_kind <= 3'd6; d_seq <= ss[rel_idx]; d_cnt <= sc[rel_idx]; d_feed <= sf[rel_idx]; sv[rel_idx] <= 1'b0; nx <= nx + {16'd0, sc[rel_idx]};
            end else if (accept) begin
                d_valid <= 1'b1; d_seq <= in_seq; d_cnt <= in_cnt; d_feed <= in_feed;
                if (cnt0) d_kind <= 3'd5;
                else if (dz) begin d_kind <= 3'd0; nx <= nx + {16'd0, in_cnt}; end
                else if (bh) d_kind <= dup_beh ? 3'd2 : 3'd3;
                else if (same) d_kind <= 3'd2;
                else if (free_any) begin d_kind <= 3'd1; sv[free_idx] <= 1'b1; ss[free_idx] <= in_seq; sc[free_idx] <= in_cnt; sf[free_idx] <= in_feed; end
                else d_kind <= 3'd4;
            end
        end
    end
endmodule
// seq_arb_syn: the same design behind a handful of pins, ONLY so that it fits a chip for the place-and-route runs: the 50-bit input is shifted in serially, the outputs are folded into one registered 16-bit word.
module seq_arb_syn #(parameter int PEND = 4, parameter int TO = 16, parameter int TO2 = 64) (input logic clk, input logic rst, input logic si, input logic sh, output logic [15:0] info);
    logic [50:0] iv; logic ready, dv, tv; logic [2:0] dk; logic [31:0] ds, ts, tc, nx; logic [15:0] dc; logic [1:0] df, tk; logic [3:0] np;
    always_ff @(posedge clk) if (sh) iv <= {iv[49:0], si};
    seq_arb #(.PEND(PEND), .TO(TO), .TO2(TO2)) u (.clk(clk), .rst(rst), .in_valid(iv[50]), .in_feed(iv[49:48]), .in_seq(iv[47:16]), .in_cnt(iv[15:0]), .in_ready(ready), .d_valid(dv), .d_kind(dk), .d_seq(ds), .d_cnt(dc), .d_feed(df), .t_valid(tv), .t_kind(tk), .t_seq(ts), .t_cnt(tc), .o_next(nx), .o_np(np));
    logic [15:0] x; always_comb x = ds[15:0] ^ ds[31:16] ^ dc ^ ts[15:0] ^ ts[31:16] ^ tc[15:0] ^ tc[31:16] ^ nx[15:0] ^ nx[31:16] ^ {dv, tv, ready, dk, tk, df, np, 2'd0};
    always_ff @(posedge clk) info <= x;
endmodule
