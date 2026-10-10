// Chapter 20: the order book with RAMs. The order table is a hash table (NB buckets of K ways, a RAM read one way per cycle); the price levels of each (symbol, side) are a sorted array of D entries in a RAM, searched, shifted and rewritten one entry per cycle; the best level and the number of levels of each side stay in registers. One event at a time; the timing is specified in model/book2_gold.py.
module book2 #(parameter int NS = 2, parameter int D = 8, parameter int NB = 8, parameter int K = 4) (
    input  logic clk, input logic rst,
    input  logic in_valid, input logic [2:0] in_type, input logic [31:0] in_ref, input logic [31:0] in_ref2, input logic [((NS > 1) ? $clog2(NS) : 1) - 1:0] in_sym, input logic in_side, input logic [31:0] in_px, input logic [31:0] in_sh,
    output logic in_ready,
    output logic o_valid, output logic [2:0] o_res, output logic [((NS > 1) ? $clog2(NS) : 1) - 1:0] o_sym, output logic [31:0] o_bpx, output logic [31:0] o_bsh, output logic [31:0] o_apx, output logic [31:0] o_ash,
    output logic [7:0] o_bn, output logic [7:0] o_an, output logic [15:0] o_nord);
    localparam int SW = (NS > 1) ? $clog2(NS) : 1, NL = NS * 2, NOW = NB * K, OA = (NOW > 1) ? $clog2(NOW) : 1, LA = ((NL * D) > 1) ? $clog2(NL * D) : 1, DW = $clog2(D + 2) + 1, KW = $clog2(K + 2) + 1, BW = (NB > 1) ? $clog2(NB) : 1, OW = 1 + 32 + SW + 1 + 32 + 32;
    typedef enum logic [3:0] {S_INIT, S_IDLE, S_LK, S_DEC, S_FIND, S_WLV, S_SHD, S_SHU, S_WINS, S_WOM} st_t;
    st_t st;
    // ---- the two RAMs (one write port, one read port each; the read data is registered)
    logic [OW-1:0] om [0:NOW-1]; logic [OW-1:0] om_rd; logic [OA-1:0] om_ra, om_wa; logic om_we; logic [OW-1:0] om_wd;
    logic [63:0] lm [0:NL * D - 1]; logic [63:0] lm_rd; logic [LA-1:0] lm_ra, lm_wa; logic lm_we; logic [63:0] lm_wd;
    always_ff @(posedge clk) begin if (om_we) om[om_wa] <= om_wd; om_rd <= om[om_ra]; end
    always_ff @(posedge clk) begin if (lm_we) lm[lm_wa] <= lm_wd; lm_rd <= lm[lm_ra]; end
    // ---- registers: per (symbol, side) the number of levels and the best level; the number of orders
    logic [DW-1:0] cnt [0:NL-1]; logic [31:0] tpx [0:NL-1]; logic [31:0] tsh [0:NL-1]; logic [15:0] nord;
    // ---- the event being processed
    logic [2:0] r_t; logic [31:0] r_ref, r_ref2, r_px, r_sh; logic [SW-1:0] r_sym; logic r_side;
    logic [OA-1:0] bkt; logic [KW-1:0] lk_i, fw, ff; logic fv, fvv; logic [SW-1:0] f_sym; logic f_side; logic [31:0] f_px, f_sh, tk;
    logic [OA-1:0] ini;
    logic [DW-1:0] fi, p, srem, sj, sdst; logic fst, sw; logic [31:0] wsh;
    // result register
    logic res_v; logic [2:0] res; logic [SW-1:0] res_sym;
    // the hash: the low bits of the 4 bytes of the reference XORed together; the bucket's first way is h * K
    wire [BW-1:0] hx_in = BW'(in_ref ^ (in_ref >> 8) ^ (in_ref >> 16) ^ (in_ref >> 24)), hx_2 = BW'(r_ref2 ^ (r_ref2 >> 8) ^ (r_ref2 >> 16) ^ (r_ref2 >> 24));
    wire [OA-1:0] hb_in = OA'(hx_in) * OA'(K), hb_2 = OA'(hx_2) * OA'(K);
    logic [SW:0] lidx; logic [LA-1:0] lbase;
    always_comb begin
        if (r_t == 3'(0)) lidx = {r_sym, r_side}; else lidx = {f_sym, f_side};
        lbase = LA'(lidx) * LA'(D);
    end
    logic [DW-1:0] cnt_l; assign cnt_l = cnt[lidx];
    // fields of the word the order RAM returns
    wire        w_v = om_rd[OW-1]; wire [31:0] w_ref = om_rd[OW-2 -: 32]; wire [SW-1:0] w_sym = om_rd[OW-2-32 -: SW]; wire w_side = om_rd[OW-2-32-SW]; wire [31:0] w_px = om_rd[63:32]; wire [31:0] w_sh = om_rd[31:0];
    wire [31:0] l_px = lm_rd[63:32]; wire [31:0] l_sh = lm_rd[31:0];
    wire is_red = (r_t == 3'(1)) || (r_t == 3'(2));
    wire l_better = r_side ? (r_px < l_px) : (r_px > l_px);                         // the new price is better than the level's (ADD only)
    wire [31:0] tgt = (r_t == 3'(0)) ? r_px : f_px;                              // the price of the level the event works on
    assign in_ready = (st == S_IDLE);
    // RAM control: addresses and write data are functions of the state (the read data arrives, registered, one cycle after its address)
    always_comb begin
        om_ra = bkt + OA'(lk_i); om_we = 1'b0; om_wa = '0; om_wd = '0;
        lm_ra = lbase + LA'(sj); lm_we = 1'b0; lm_wa = '0; lm_wd = '0;
        if (st == S_FIND) lm_ra = lbase + (fst ? '0 : LA'(fi) + 1'b1);
        if (st == S_INIT) begin om_we = 1'b1; om_wa = ini; end
        if (st == S_WOM) begin
            om_we = 1'b1;
            if (r_t == 3'(0)) begin om_wa = bkt + OA'(ff); om_wd = {1'b1, r_ref, r_sym, r_side, r_px, r_sh}; end
            else begin om_wa = bkt + OA'(fw); if (tk == f_sh) om_wd = '0; else om_wd = {1'b1, r_ref, f_sym, f_side, f_px, f_sh - tk}; end
        end
        if (st == S_WLV) begin lm_we = 1'b1; lm_wa = lbase + LA'(p); lm_wd = {tgt, wsh}; end
        if (st == S_WINS) begin lm_we = 1'b1; lm_wa = lbase + LA'(p); lm_wd = {r_px, r_sh}; end
        if ((st == S_SHD || st == S_SHU) && sw) begin lm_we = 1'b1; lm_wa = lbase + LA'(sdst); lm_wd = lm_rd; end
    end
    integer i;
    always_ff @(posedge clk) begin
        res_v <= 1'b0;
        if (rst) begin
            st <= S_INIT; ini <= '0; nord <= '0;
            for (i = 0; i < NL; i++) cnt[i] <= '0;                                     // tpx and tsh need no reset: they are shown only when cnt is not 0, and written before it becomes so
        end else case (st)
            S_INIT: begin ini <= ini + 1'b1; if (ini == OA'(NOW - 1)) st <= S_IDLE; end
            S_IDLE: if (in_valid) begin
                r_t <= in_type; r_ref <= in_ref; r_ref2 <= in_ref2; r_sym <= in_sym; r_side <= in_side; r_px <= in_px; r_sh <= in_sh;
                if (in_type == 3'(0) && in_sh == 32'd0) begin res_v <= 1'b1; res <= 3'd6; res_sym <= in_sym; end
                else begin st <= S_LK; lk_i <= '0; fv <= 1'b0; fvv <= 1'b0; bkt <= hb_in; end
            end
            S_LK: begin
                if (lk_i != 0) begin
                    // refs are unique in the table (a duplicate ADD is refused), so at most one way matches
                    if (w_v && w_ref == r_ref) begin fv <= 1'b1; fw <= lk_i - 1'b1; f_sym <= w_sym; f_side <= w_side; f_px <= w_px; f_sh <= w_sh; end
                    // any free way will do (the model does not say which): the last one seen
                    if (!w_v) begin fvv <= 1'b1; ff <= lk_i - 1'b1; end
                end
                lk_i <= lk_i + 1'b1; if (lk_i == KW'(K)) st <= S_DEC;
            end
            S_DEC: begin
                fst <= 1'b1; fi <= '0;
                if (r_t == 3'(0)) begin
                    if (fv) begin res_v <= 1'b1; res <= 3'd5; res_sym <= r_sym; st <= S_IDLE; end
                    else if (!fvv) begin res_v <= 1'b1; res <= 3'd2; res_sym <= r_sym; st <= S_IDLE; end
                    else st <= S_FIND;
                end else begin
                    if (!fv) begin res_v <= 1'b1; res <= 3'd1; res_sym <= '0; st <= S_IDLE; end
                    else if (is_red && r_sh == 32'd0) begin res_v <= 1'b1; res <= 3'd6; res_sym <= f_sym; st <= S_IDLE; end
                    else if (is_red && r_sh > f_sh) begin res_v <= 1'b1; res <= 3'd4; res_sym <= f_sym; st <= S_IDLE; end
                    else begin tk <= is_red ? r_sh : f_sh; st <= S_FIND; end
                end
            end
            S_FIND: begin
                if (fst) fst <= 1'b0;
                else if (fi == cnt_l && r_t == 3'(0)) begin                                // all the levels are better: insert at the end
                    p <= fi;
                    if (cnt_l == DW'(D)) begin res_v <= 1'b1; res <= 3'd3; res_sym <= r_sym; st <= S_IDLE; end
                    else begin srem <= '0; st <= S_WINS; end
                end else if (l_px == tgt) begin
                    p <= fi;
                    if (r_t == 3'(0)) begin wsh <= l_sh + r_sh; st <= S_WLV; end
                    else if (l_sh != tk) begin wsh <= l_sh - tk; st <= S_WLV; end
                    else begin
                        cnt[lidx] <= cnt_l - 1'b1; srem <= cnt_l - 1'b1 - fi; sj <= fi + 1'b1; sw <= 1'b0;
                        st <= (cnt_l - 1'b1 - fi > 0) ? S_SHU : S_WOM;
                    end
                end else if (r_t == 3'(0) && l_better) begin
                    p <= fi;
                    if (cnt_l == DW'(D)) begin res_v <= 1'b1; res <= 3'd3; res_sym <= r_sym; st <= S_IDLE; end
                    else begin srem <= cnt_l - fi; sj <= cnt_l - 1'b1; sw <= 1'b0; st <= (cnt_l > fi) ? S_SHD : S_WINS; end
                end else fi <= fi + 1'b1;
            end
            S_WLV: begin if (p == 0) tsh[lidx] <= wsh; st <= S_WOM; end
            S_SHD: begin
                if (srem != 0) begin sw <= 1'b1; sdst <= sj + 1'b1; sj <= sj - 1'b1; srem <= srem - 1'b1; end
                else begin sw <= 1'b0; st <= S_WINS; end
            end
            S_SHU: begin
                if (sw && sdst == 0) begin tpx[lidx] <= l_px; tsh[lidx] <= l_sh; end
                if (srem != 0) begin sw <= 1'b1; sdst <= sj - 1'b1; sj <= sj + 1'b1; srem <= srem - 1'b1; end
                else begin sw <= 1'b0; st <= S_WOM; end
            end
            S_WINS: begin
                cnt[lidx] <= cnt_l + 1'b1; if (p == 0) begin tpx[lidx] <= r_px; tsh[lidx] <= r_sh; end st <= S_WOM;
            end
            S_WOM: begin
                if (r_t == 3'(0)) begin nord <= nord + 1'b1; res_v <= 1'b1; res <= 3'd0; res_sym <= r_sym; st <= S_IDLE; end
                else begin
                    if (tk == f_sh) nord <= nord - 1'b1;
                    if (r_t == 3'(4)) begin                                                  // REPLACE: now add the new order, with the old order's symbol and side
                        r_t <= 3'(0); r_ref <= r_ref2; r_sym <= f_sym; r_side <= f_side;
                        if (r_sh == 32'd0) begin res_v <= 1'b1; res <= 3'd6; res_sym <= f_sym; st <= S_IDLE; end
                        else begin st <= S_LK; lk_i <= '0; fv <= 1'b0; fvv <= 1'b0; bkt <= hb_2; end
                    end else begin res_v <= 1'b1; res <= 3'd0; res_sym <= f_sym; st <= S_IDLE; end
                end
            end
            default: st <= S_IDLE;
        endcase
    end
    // the top of book of the symbol of the result, read in the cycle the result is visible
    assign o_valid = res_v; assign o_res = res; assign o_sym = res_sym;
    always_comb begin
        o_bpx = (cnt[{o_sym, 1'b0}] != 0) ? tpx[{o_sym, 1'b0}] : 32'd0; o_bsh = (cnt[{o_sym, 1'b0}] != 0) ? tsh[{o_sym, 1'b0}] : 32'd0;
        o_apx = (cnt[{o_sym, 1'b1}] != 0) ? tpx[{o_sym, 1'b1}] : 32'd0; o_ash = (cnt[{o_sym, 1'b1}] != 0) ? tsh[{o_sym, 1'b1}] : 32'd0;
        o_bn = 8'(cnt[{o_sym, 1'b0}]); o_an = 8'(cnt[{o_sym, 1'b1}]); o_nord = nord;
    end
endmodule
// book2_syn: the same design behind a handful of pins, ONLY so that it fits a chip for the place-and-route runs: the event (140 bits) is shifted in serially, the outputs are registered and folded into one 16-bit word.
module book2_syn #(parameter int NS = 2, parameter int D = 8, parameter int NB = 8, parameter int K = 4) (input logic clk, input logic rst, input logic si, input logic sh, output logic [15:0] info);
    localparam int SW = (NS > 1) ? $clog2(NS) : 1;
    logic [139:0] iv; logic ready, ov_; logic [2:0] res; logic [SW-1:0] sy; logic [31:0] bpx, bsh, apx, ash; logic [7:0] bn, an; logic [15:0] nord;
    always_ff @(posedge clk) if (sh) iv <= {iv[138:0], si};
    book2 #(.NS(NS), .D(D), .NB(NB), .K(K)) u (.clk(clk), .rst(rst), .in_valid(iv[139]), .in_type(iv[138:136]), .in_ref(iv[135:104]), .in_ref2(iv[103:72]), .in_sym(iv[71:71-SW+1]), .in_side(iv[0]), .in_px(iv[71:40]), .in_sh(iv[39:8]), .in_ready(ready),
        .o_valid(ov_), .o_res(res), .o_sym(sy), .o_bpx(bpx), .o_bsh(bsh), .o_apx(apx), .o_ash(ash), .o_bn(bn), .o_an(an), .o_nord(nord));
    logic [15:0] x, r1; always_comb x = bpx[15:0] ^ bpx[31:16] ^ bsh[15:0] ^ bsh[31:16] ^ apx[15:0] ^ apx[31:16] ^ ash[15:0] ^ ash[31:16] ^ {bn, an} ^ nord ^ {8'(0), ov_, ready, res, 3'(sy)};
    always_ff @(posedge clk) begin r1 <= x; info <= r1; end
endmodule
