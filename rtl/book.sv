// verilator lint_off DECLFILENAME
// Chapter 19: the order book. Behaviour, results and every simplification are those of model/book_gold.py, cycle for cycle.
// NS symbols, each with a bid side and an ask side of D price levels kept SORTED (best price first, the valid levels contiguous from index 0, in registers: a new level is inserted by shifting the worse ones down, an emptied level removed by shifting them up: one cycle each). An order table of NO orders (reference, symbol, side, price, shares) searched ASSOCIATIVELY (every entry compared with the reference in one cycle). One event per cycle; REPLACE takes two (delete, then add) and in_ready is 0 during the second. The result (res, sym) is registered; the top of book of that symbol is read from the level registers in the cycle the result is visible.
// event types: 0 ADD (ref, sym, side, px, sh), 1 EXEC (ref, sh), 2 CANCEL (ref, sh), 3 DELETE (ref), 4 REPLACE (ref = old, ref2 = new, px, sh). Results: 0 OK, 1 UNK, 2 FULL, 3 LVL, 4 OVER, 5 DUPREF, 6 ZERO.
module book #(parameter int NS = 2, parameter int D = 4, parameter int NO = 8) (
    input logic clk, input logic rst,
    input logic in_valid, input logic [2:0] in_type, input logic [31:0] in_ref, input logic [31:0] in_ref2, input logic [SW-1:0] in_sym, input logic in_side, input logic [31:0] in_px, input logic [31:0] in_sh, output logic in_ready,
    output logic o_valid, output logic [2:0] o_res, output logic [SW-1:0] o_sym,
    output logic [31:0] o_bpx, output logic [31:0] o_bsh, output logic [31:0] o_apx, output logic [31:0] o_ash, output logic [7:0] o_bn, output logic [7:0] o_an, output logic [7:0] o_nord);
    localparam int SW = (NS > 1) ? $clog2(NS) : 1;
    localparam int OW = (NO > 1) ? $clog2(NO) : 1;
    localparam int DW = (D > 1) ? $clog2(D + 1) : 1;
    // state
    logic ov [NO]; logic [31:0] oref [NO]; logic [SW-1:0] osym [NO]; logic osd [NO]; logic [31:0] opx [NO]; logic [31:0] osh [NO];
    logic lv [NS * 2][D]; logic [31:0] lpx [NS * 2][D]; logic [31:0] lsh [NS * 2][D];
    logic busy; logic [31:0] b_ref, b_px, b_sh; logic [SW-1:0] b_sym; logic b_side;
    // the operation of this cycle
    logic is_add, is_red, is_del, is_rep, accept; logic [31:0] a_ref, a_px, a_sh; logic [SW-1:0] a_sym; logic a_side;
    logic dup, free_any, found; logic [OW-1:0] free_idx, f_idx; logic [31:0] f_px, f_sh; logic [SW-1:0] f_sym; logic f_side;
    logic [31:0] tk; logic [2:0] res; logic [SW-1:0] rsym; logic res_v;
    logic lop, lop_add; logic [SW:0] lop_li; logic [31:0] lop_px, lop_sh; logic [DW-1:0] p, cnt; logic hit, lfull; logic [31:0] hit_sh; logic remove_lv; logic ord_free, ord_set, ord_red; logic rep_go;
    always_comb begin
        accept = in_valid && !busy; in_ready = !busy;
        is_add = busy || (accept && in_type == 3'd0); is_red = accept && (in_type == 3'd1 || in_type == 3'd2); is_del = accept && in_type == 3'd3; is_rep = accept && in_type == 3'd4;
        a_ref = busy ? b_ref : in_ref; a_px = busy ? b_px : in_px; a_sh = busy ? b_sh : in_sh; a_sym = busy ? b_sym : in_sym; a_side = busy ? b_side : in_side;
        // the order table: look up the reference of the event (for ADD: the new one, for a duplicate)
        dup = 1'b0; free_any = 1'b0; free_idx = '0; found = 1'b0; f_idx = '0; f_px = 32'd0; f_sh = 32'd0; f_sym = '0; f_side = 1'b0;
        for (int i = NO - 1; i >= 0; i--) begin
            if (ov[i] && oref[i] == a_ref) dup = 1'b1;
            if (!ov[i]) begin free_any = 1'b1; free_idx = OW'(i); end
            if (ov[i] && oref[i] == in_ref) begin found = 1'b1; f_idx = OW'(i); f_px = opx[i]; f_sh = osh[i]; f_sym = osym[i]; f_side = osd[i]; end
        end
        tk = (is_del || is_rep) ? f_sh : in_sh;
        // which level operation (if any), and the checks
        lop = 1'b0; lop_add = 1'b0; lop_li = '0; lop_px = 32'd0; lop_sh = 32'd0; res = 3'd0; rsym = '0; res_v = 1'b0; ord_free = 1'b0; ord_set = 1'b0; ord_red = 1'b0; rep_go = 1'b0;
        // the level search for the symbol and side the operation names (add: the new order's; reduce: the found order's)
        if (is_add) begin lop_li = {a_sym, a_side}; lop_px = a_px; lop_sh = a_sh; end
        else begin lop_li = {f_sym, f_side}; lop_px = f_px; lop_sh = tk; end
        p = '0; cnt = '0; hit = 1'b0; hit_sh = 32'd0;
        for (int i = 0; i < D; i++) begin
            if (lv[lop_li][i]) begin
                cnt = cnt + 1'b1;
                if (lop_li[0] ? (lpx[lop_li][i] < lop_px) : (lpx[lop_li][i] > lop_px)) p = p + 1'b1;            // better than the price: the level sits ahead of it
            end
        end
        for (int i = 0; i < D; i++) if (lv[lop_li][i] && DW'(i) == p && lpx[lop_li][i] == lop_px) begin hit = 1'b1; hit_sh = lsh[lop_li][i]; end
        lfull = !hit && (cnt == DW'(D));
        remove_lv = 1'b0;
        if (is_add) begin
            res_v = 1'b1; rsym = a_sym;
            if (a_sh == 32'd0) res = 3'd6; else if (dup) res = 3'd5; else if (!free_any) res = 3'd2; else if (lfull) res = 3'd3; else begin res = 3'd0; lop = 1'b1; lop_add = 1'b1; ord_set = 1'b1; end
        end else if (is_red || is_del) begin
            res_v = 1'b1; rsym = found ? f_sym : '0;
            if (!found) res = 3'd1;
            else if (is_red && in_sh == 32'd0) res = 3'd6;
            else if (is_red && in_sh > f_sh) res = 3'd4;
            else begin res = 3'd0; lop = 1'b1; remove_lv = ((hit_sh - tk) == 32'd0); if (tk == f_sh) ord_free = 1'b1; else ord_red = 1'b1; end
        end else if (is_rep) begin
            if (!found) begin res_v = 1'b1; res = 3'd1; rsym = '0; end
            else begin rep_go = 1'b1; lop = 1'b1; remove_lv = ((hit_sh - tk) == 32'd0); ord_free = 1'b1; end
        end
    end
    // the result, the engine and the order table
    always_ff @(posedge clk) begin
        o_valid <= 1'b0;
        if (rst) begin
            busy <= 1'b0; for (int i = 0; i < NO; i++) ov[i] <= 1'b0; for (int s = 0; s < NS * 2; s++) for (int i = 0; i < D; i++) lv[s][i] <= 1'b0;
        end else begin
            if (res_v) begin o_valid <= 1'b1; o_res <= res; o_sym <= rsym; end
            if (busy) busy <= 1'b0;
            if (rep_go) begin busy <= 1'b1; b_ref <= in_ref2; b_px <= in_px; b_sh <= in_sh; b_sym <= f_sym; b_side <= f_side; end
            if (ord_set) begin ov[free_idx] <= 1'b1; oref[free_idx] <= a_ref; osym[free_idx] <= a_sym; osd[free_idx] <= a_side; opx[free_idx] <= a_px; osh[free_idx] <= a_sh; end
            if (ord_free) ov[f_idx] <= 1'b0;
            if (ord_red) osh[f_idx] <= f_sh - tk;
            // the levels
            if (lop) for (int s = 0; s < NS * 2; s++) if ((SW + 1)'(s) == lop_li) begin
                if (lop_add && hit) begin for (int i = 0; i < D; i++) if (DW'(i) == p) lsh[s][i] <= lsh[s][i] + lop_sh; end
                else if (lop_add) begin
                    for (int i = D - 1; i >= 0; i--) begin
                        if (DW'(i) == p) begin lv[s][i] <= 1'b1; lpx[s][i] <= lop_px; lsh[s][i] <= lop_sh; end
                        else if (DW'(i) > p && i > 0) begin lv[s][i] <= lv[s][i - 1]; lpx[s][i] <= lpx[s][i - 1]; lsh[s][i] <= lsh[s][i - 1]; end
                    end
                end else if (remove_lv) begin
                    for (int i = 0; i < D; i++) begin
                        if (DW'(i) >= p) begin
                            if (i + 1 < D) begin lv[s][i] <= lv[s][i + 1]; lpx[s][i] <= lpx[s][i + 1]; lsh[s][i] <= lsh[s][i + 1]; end else lv[s][i] <= 1'b0;
                        end
                    end
                end else begin for (int i = 0; i < D; i++) if (DW'(i) == p) lsh[s][i] <= lsh[s][i] - lop_sh; end
            end
        end
    end
    // the top of book of the symbol of the result (read in the cycle the result is visible)
    logic [7:0] nb, na, no_;
    always_comb begin
        o_bpx = lv[{o_sym, 1'b0}][0] ? lpx[{o_sym, 1'b0}][0] : 32'd0; o_bsh = lv[{o_sym, 1'b0}][0] ? lsh[{o_sym, 1'b0}][0] : 32'd0;
        o_apx = lv[{o_sym, 1'b1}][0] ? lpx[{o_sym, 1'b1}][0] : 32'd0; o_ash = lv[{o_sym, 1'b1}][0] ? lsh[{o_sym, 1'b1}][0] : 32'd0;
        nb = 8'd0; na = 8'd0; no_ = 8'd0;
        for (int i = 0; i < D; i++) begin if (lv[{o_sym, 1'b0}][i]) nb = nb + 8'd1; if (lv[{o_sym, 1'b1}][i]) na = na + 8'd1; end
        for (int i = 0; i < NO; i++) if (ov[i]) no_ = no_ + 8'd1;
        o_bn = nb; o_an = na; o_nord = no_;
    end
endmodule
// book_syn: the same design behind a handful of pins, ONLY so that it fits a chip for the place-and-route runs: the event (140 bits) is shifted in serially, the outputs are registered and folded into one 16-bit word.
module book_syn #(parameter int NS = 2, parameter int D = 4, parameter int NO = 8) (input logic clk, input logic rst, input logic si, input logic sh, output logic [15:0] info);
    localparam int SW = (NS > 1) ? $clog2(NS) : 1;
    logic [139:0] iv; logic ready, ov_; logic [2:0] res; logic [SW-1:0] sy; logic [31:0] bpx, bsh, apx, ash; logic [7:0] bn, an, nord;
    always_ff @(posedge clk) if (sh) iv <= {iv[138:0], si};
    book #(.NS(NS), .D(D), .NO(NO)) u (.clk(clk), .rst(rst), .in_valid(iv[139]), .in_type(iv[138:136]), .in_ref(iv[135:104]), .in_ref2(iv[103:72]), .in_sym(iv[71:71-SW+1]), .in_side(iv[0]), .in_px(iv[71:40]), .in_sh(iv[39:8]), .in_ready(ready),
        .o_valid(ov_), .o_res(res), .o_sym(sy), .o_bpx(bpx), .o_bsh(bsh), .o_apx(apx), .o_ash(ash), .o_bn(bn), .o_an(an), .o_nord(nord));
    logic [15:0] x, r1; always_comb x = bpx[15:0] ^ bpx[31:16] ^ bsh[15:0] ^ bsh[31:16] ^ apx[15:0] ^ apx[31:16] ^ ash[15:0] ^ ash[31:16] ^ {bn, an} ^ {nord, ov_, ready, res, 3'(sy)};
    always_ff @(posedge clk) begin r1 <= x; info <= r1; end
endmodule
