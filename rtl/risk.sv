// Chapter 23: the pre-trade risk gate. An order passes only if every limit holds after it, counting everything still open as if it were executed; fills and cancels release what an order took; the gate fails closed (disarmed after reset, limits that reject everything after reset, a fault latch, a kill input). One event per cycle, answered two cycles after it is offered: stage 1 registers the event and forms price x quantity (the multiplication), stage 2 checks and updates the state in one cycle, so there is no hazard between events. The specification is in model/risk_gold.py.
module risk #(parameter int NA = 4, parameter int NS = 4, parameter int QW = 16, parameter int PW = 16, parameter int R = 4, parameter int TW = 8) (
    input  logic clk, input logic rst,
    input  logic ev_valid, input logic [1:0] ev_type, input logic [3:0] ev_acct, input logic [3:0] ev_sym, input logic ev_side, input logic [PW-1:0] ev_px, input logic [QW-1:0] ev_qty,
    input  logic cfg_a_valid, input logic [3:0] cfg_a_idx, input logic [QW-1:0] cfg_maxlong, input logic [QW-1:0] cfg_maxshort, input logic [QW-1:0] cfg_maxqty, input logic [PW+QW-1:0] cfg_maxonot, input logic [PW+QW+1:0] cfg_maxnot, input logic [TW-1:0] cfg_cap,
    input  logic cfg_b_valid, input logic [3:0] cfg_b_idx, input logic [PW-1:0] cfg_lo, input logic [PW-1:0] cfg_hi,
    input  logic ctl_arm, input logic ctl_disarm, input logic kill,
    output logic o_valid, output logic [1:0] o_kind, output logic [3:0] o_res, output logic signed [QW+1:0] o_pos, output logic [QW-1:0] o_ob, output logic [QW-1:0] o_os, output logic [PW+QW+1:0] o_not, output logic [TW-1:0] o_tok);
    localparam int AW = (NA > 1) ? $clog2(NA) : 1, SW = (NS > 1) ? $clog2(NS) : 1, NW = PW + QW + 2, PB = QW + 2, PHW = (R > 1) ? $clog2(R) : 1;
    localparam logic [3:0] OK = 4'd0, KILL = 4'd1, DISARMED = 4'd2, BADIDX = 4'd3, QTY = 4'd4, BAND = 4'd5, ONOT = 4'd6, POS = 4'd7, NOT = 4'd8, RATE = 4'd9, FAULT = 4'd10;
    // ---- configuration and state
    logic [QW-1:0] c_long [0:NA-1]; logic [QW-1:0] c_short [0:NA-1]; logic [QW-1:0] c_qty [0:NA-1]; logic [PW+QW-1:0] c_onot [0:NA-1]; logic [NW-1:0] c_not [0:NA-1]; logic [TW-1:0] c_cap [0:NA-1];
    logic [PW-1:0] b_lo [0:NS-1]; logic [PW-1:0] b_hi [0:NS-1];
    logic signed [PB-1:0] pos [0:NA-1][0:NS-1]; logic [QW-1:0] ob [0:NA-1][0:NS-1]; logic [QW-1:0] os [0:NA-1][0:NS-1]; logic [NW-1:0] notl [0:NA-1]; logic [TW-1:0] tok [0:NA-1];
    logic armed, fault; logic [PHW-1:0] phase;
    // ---- stage 1: the event and its notional
    logic s1_v, s1_side, s1_kill; logic [1:0] s1_t; logic [3:0] s1_a, s1_s; logic [PW-1:0] s1_px; logic [QW-1:0] s1_qty; logic [PW+QW-1:0] s1_prod;
    always_ff @(posedge clk) begin
        s1_v <= ev_valid; s1_t <= ev_type; s1_a <= ev_acct; s1_s <= ev_sym; s1_side <= ev_side; s1_px <= ev_px; s1_qty <= ev_qty; s1_kill <= kill; s1_prod <= ev_px * ev_qty;
    end
    // ---- stage 2: the checks, in the order of the specification, and the update
    wire bad = (s1_a >= 4'(NA)) || (s1_s >= 4'(NS));
    wire [AW-1:0] a = s1_a[AW-1:0]; wire [SW-1:0] s = s1_s[SW-1:0];
    wire buy = !s1_side; wire isord = (s1_t == 2'd0), isfill = (s1_t == 2'd1);
    wire signed [PB+1:0] pl = $signed({{2{pos[a][s][PB-1]}}, pos[a][s]}) + $signed({{(PB+2-QW){1'b0}}, ob[a][s]}) + $signed({{(PB+2-QW){1'b0}}, s1_qty});      // pos + ob + qty (a buy)
    wire signed [PB+1:0] ps = $signed({{2{pos[a][s][PB-1]}}, pos[a][s]}) - $signed({{(PB+2-QW){1'b0}}, os[a][s]}) - $signed({{(PB+2-QW){1'b0}}, s1_qty});      // pos - os - qty (a sell)
    wire signed [PB+1:0] mlong = $signed({{(PB+2-QW){1'b0}}, c_long[a]}), mshort = -$signed({{(PB+2-QW){1'b0}}, c_short[a]});
    wire [NW-1:0] prod = {{2{1'b0}}, s1_prod};
    logic [3:0] res; logic took; logic fault_set;
    always_comb begin
        res = OK; took = 1'b0; fault_set = 1'b0;
        if (isord) begin
            if (s1_kill) res = KILL;
            else if (!armed || fault) res = DISARMED;
            else if (bad) res = BADIDX;
            else if (s1_qty == '0 || s1_qty > c_qty[a]) res = QTY;
            else if (s1_px < b_lo[s] || s1_px > b_hi[s]) res = BAND;
            else if (s1_prod > c_onot[a]) res = ONOT;
            else if (buy ? (pl > mlong) : (ps < mshort)) res = POS;
            else if (notl[a] + prod > c_not[a]) res = NOT;
            else if (tok[a] == '0) res = RATE;
            else begin res = OK; took = 1'b1; end
        end else begin
            if (bad || (buy ? (s1_qty > ob[a][s]) : (s1_qty > os[a][s])) || prod > notl[a]) begin res = FAULT; fault_set = 1'b1; end
        end
    end
    wire apply = s1_v && !isord && !fault_set;                                                       // a valid release
    wire [TW-1:0] tok_after [0:NA-1];
    for (genvar g = 0; g < NA; g++) begin : tk
        assign tok_after[g] = (s1_v && isord && took && a == AW'(g) && !bad) ? tok[g] - 1'b1 : tok[g];
    end
    wire tick = (phase == PHW'(R - 1));
    always_ff @(posedge clk) begin
        if (rst) begin
            armed <= 1'b0; fault <= 1'b0; phase <= '0;
            for (int i = 0; i < NA; i++) begin c_qty[i] <= '0; c_cap[i] <= '0;     // max_qty 0 refuses every order, so the other limits need no reset; the bucket size does (the tokens tick up to it)
                notl[i] <= '0; tok[i] <= '0; for (int j = 0; j < NS; j++) begin pos[i][j] <= '0; ob[i][j] <= '0; os[i][j] <= '0; end end
            for (int j = 0; j < NS; j++) begin b_lo[j] <= '1; b_hi[j] <= '0; end
        end else begin
            phase <= tick ? '0 : phase + 1'b1;
            // the order or the release of stage 2
            if (s1_v && isord && took) begin
                if (buy) ob[a][s] <= ob[a][s] + s1_qty; else os[a][s] <= os[a][s] + s1_qty;
                notl[a] <= notl[a] + prod;
            end
            if (apply) begin
                if (buy) ob[a][s] <= ob[a][s] - s1_qty; else os[a][s] <= os[a][s] - s1_qty;
                notl[a] <= notl[a] - prod;
                if (isfill) pos[a][s] <= buy ? pos[a][s] + $signed({{2{1'b0}}, s1_qty}) : pos[a][s] - $signed({{2{1'b0}}, s1_qty});
            end
            if (s1_v && fault_set) fault <= 1'b1;
            // tokens: take, then tick (up to the cap); a configuration write refills
            for (int i = 0; i < NA; i++) tok[i] <= (tick && tok_after[i] < c_cap[i]) ? tok_after[i] + 1'b1 : tok_after[i];
            if (cfg_a_valid && cfg_a_idx < 4'(NA)) for (int i = 0; i < NA; i++) if (cfg_a_idx == 4'(i)) begin
                c_long[i] <= cfg_maxlong; c_short[i] <= cfg_maxshort; c_qty[i] <= cfg_maxqty; c_onot[i] <= cfg_maxonot; c_not[i] <= cfg_maxnot; c_cap[i] <= cfg_cap; tok[i] <= cfg_cap;
            end
            if (cfg_b_valid && cfg_b_idx < 4'(NS)) for (int j = 0; j < NS; j++) if (cfg_b_idx == 4'(j)) begin b_lo[j] <= cfg_lo; b_hi[j] <= cfg_hi; end
            if (ctl_disarm) armed <= 1'b0; else if (ctl_arm && !kill) armed <= 1'b1;               // (a fault refuses every order whether or not the gate is armed)
        end
    end
    // ---- the answer: the touched (account, symbol) after the update (before the token tick), zeros for a bad index
    wire [QW-1:0] ob_n = (apply ? (buy ? ob[a][s] - s1_qty : ob[a][s]) : ((isord && took && buy) ? ob[a][s] + s1_qty : ob[a][s]));
    wire [QW-1:0] os_n = (apply ? (!buy ? os[a][s] - s1_qty : os[a][s]) : ((isord && took && !buy) ? os[a][s] + s1_qty : os[a][s]));
    wire signed [PB-1:0] pos_n = (apply && isfill) ? (buy ? pos[a][s] + $signed({{2{1'b0}}, s1_qty}) : pos[a][s] - $signed({{2{1'b0}}, s1_qty})) : pos[a][s];
    wire [NW-1:0] not_n = apply ? notl[a] - prod : ((isord && took) ? notl[a] + prod : notl[a]);
    always_ff @(posedge clk) begin
        o_valid <= s1_v; o_kind <= s1_t; o_res <= res;
        o_pos <= (bad) ? '0 : pos_n; o_ob <= bad ? '0 : ob_n; o_os <= bad ? '0 : os_n; o_not <= bad ? '0 : not_n; o_tok <= bad ? '0 : tok_after[a];
    end
endmodule
// risk_syn: the same design behind a handful of pins, ONLY so that it fits a chip for the place-and-route runs: the inputs are shifted in serially, the outputs registered and folded into one 16-bit word.
module risk_syn #(parameter int NA = 4, parameter int NS = 4, parameter int QW = 16, parameter int PW = 16, parameter int R = 4, parameter int TW = 8) (input logic clk, input logic rst, input logic si, input logic sh, output logic [15:0] info);
    logic [216:0] iv; logic ov_; logic [1:0] kind; logic [3:0] res; logic signed [QW+1:0] pos; logic [QW-1:0] ob, os; logic [PW+QW+1:0] nt; logic [TW-1:0] tk;
    always_ff @(posedge clk) if (sh) iv <= {iv[215:0], si};
    risk #(.NA(NA), .NS(NS), .QW(QW), .PW(PW), .R(R), .TW(TW)) u (.clk(clk), .rst(rst), .ev_valid(iv[0]), .ev_type(iv[2:1]), .ev_acct(iv[6:3]), .ev_sym(iv[10:7]), .ev_side(iv[11]), .ev_px(iv[12 +: PW]), .ev_qty(iv[28 +: QW]),
        .cfg_a_valid(iv[44]), .cfg_a_idx(iv[48:45]), .cfg_maxlong(iv[49 +: QW]), .cfg_maxshort(iv[65 +: QW]), .cfg_maxqty(iv[81 +: QW]), .cfg_maxonot(iv[97 +: PW+QW]), .cfg_maxnot(iv[129 +: PW+QW+2]), .cfg_cap(iv[169 +: TW]),
        .cfg_b_valid(iv[177]), .cfg_b_idx(iv[181:178]), .cfg_lo(iv[182 +: PW]), .cfg_hi(iv[198 +: PW]), .ctl_arm(iv[214]), .ctl_disarm(iv[215]), .kill(iv[216]),
        .o_valid(ov_), .o_kind(kind), .o_res(res), .o_pos(pos), .o_ob(ob), .o_os(os), .o_not(nt), .o_tok(tk));
    logic [15:0] x, r1; always_comb x = 16'(pos) ^ 16'(ob) ^ 16'(os) ^ 16'(nt) ^ 16'(nt >> 16) ^ {8'(tk), res, kind, ov_, 1'b0};
    always_ff @(posedge clk) begin r1 <= x; info <= r1; end
endmodule
