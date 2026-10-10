// Chapter 23: formal properties of the risk gate, for Yosys's SAT engine. The wrapper drives the gate with FREE inputs (any event, any configuration, any control, any kill, every cycle) and keeps its own, independent account of what the specification says, written in a different form: instead of open quantities and a position it keeps CUMULATIVE sums (accepted, filled, cancelled, per side; notional accepted and released), from which open quantity = accepted - filled - cancelled, position = bought - sold, and the worst-case long exposure = accepted buys - cancelled buys - filled sells. From them it computes what the answer must be and asserts, for every event:
//   S1 (the safety property): if the gate says OK to an order, then after that order every limit holds: worst-case long and short exposure within the limits, notional within the limit, quantity, price band and order notional within theirs, and the gate was armed, not faulted and not killed;
//   S2 the answer equals the one computed from the sums;  S3 the touched state shown (position, open quantities, notional, tokens) equals the sums;  S4 the token bucket never exceeds its size.
// The contract, assumed: no event while the reset is applied; max_long and max_short below 2^(QW-1) and max_not below 2^(PW+QW+1) (so that the registers cannot overflow); event type 3 does not occur.
module risk_props #(parameter int NA = 2, parameter int NS = 2, parameter int QW = 4, parameter int PW = 4, parameter int R = 3, parameter int TW = 3) (
    input logic clk,
    input logic ev_valid, input logic [1:0] ev_type, input logic [3:0] ev_acct, input logic [3:0] ev_sym, input logic ev_side, input logic [PW-1:0] ev_px, input logic [QW-1:0] ev_qty,
    input logic cfg_a_valid, input logic [3:0] cfg_a_idx, input logic [QW-1:0] cfg_maxlong, input logic [QW-1:0] cfg_maxshort, input logic [QW-1:0] cfg_maxqty, input logic [PW+QW-1:0] cfg_maxonot, input logic [PW+QW+1:0] cfg_maxnot, input logic [TW-1:0] cfg_cap,
    input logic cfg_b_valid, input logic [3:0] cfg_b_idx, input logic [PW-1:0] cfg_lo, input logic [PW-1:0] cfg_hi,
    input logic ctl_arm, input logic ctl_disarm, input logic kill);
    localparam int NW = PW + QW + 2, CW = 12;
    logic rst; initial rst = 1'b1; logic started = 1'b0;
    logic o_valid; logic [1:0] o_kind; logic [3:0] o_res; logic signed [QW+1:0] o_pos; logic [QW-1:0] o_ob, o_os; logic [NW-1:0] o_not; logic [TW-1:0] o_tok;
    risk #(.NA(NA), .NS(NS), .QW(QW), .PW(PW), .R(R), .TW(TW)) dut (.clk(clk), .rst(rst), .ev_valid(ev_valid), .ev_type(ev_type), .ev_acct(ev_acct), .ev_sym(ev_sym), .ev_side(ev_side), .ev_px(ev_px), .ev_qty(ev_qty),
        .cfg_a_valid(cfg_a_valid), .cfg_a_idx(cfg_a_idx), .cfg_maxlong(cfg_maxlong), .cfg_maxshort(cfg_maxshort), .cfg_maxqty(cfg_maxqty), .cfg_maxonot(cfg_maxonot), .cfg_maxnot(cfg_maxnot), .cfg_cap(cfg_cap),
        .cfg_b_valid(cfg_b_valid), .cfg_b_idx(cfg_b_idx), .cfg_lo(cfg_lo), .cfg_hi(cfg_hi), .ctl_arm(ctl_arm), .ctl_disarm(ctl_disarm), .kill(kill),
        .o_valid(o_valid), .o_kind(o_kind), .o_res(o_res), .o_pos(o_pos), .o_ob(o_ob), .o_os(o_os), .o_not(o_not), .o_tok(o_tok));
    // the contract
    always @(*) begin
        assume (!rst || !ev_valid);                                                    // no event while the reset is applied
        assume (ev_type != 2'd3);
        assume (cfg_maxlong < (1 << (QW - 1)) && cfg_maxshort < (1 << (QW - 1)));
        assume (cfg_maxnot < (1 << (PW + QW + 1)));
    end
    // ---- the wrapper's account: cumulative sums, per account and symbol, and its copy of the configuration
    logic [CW-1:0] acc_b [0:NA-1][0:NS-1]; logic [CW-1:0] fil_b [0:NA-1][0:NS-1]; logic [CW-1:0] can_b [0:NA-1][0:NS-1];
    logic [CW-1:0] acc_s [0:NA-1][0:NS-1]; logic [CW-1:0] fil_s [0:NA-1][0:NS-1]; logic [CW-1:0] can_s [0:NA-1][0:NS-1];
    logic [CW+8-1:0] acc_n [0:NA-1]; logic [CW+8-1:0] rel_n [0:NA-1]; logic [TW-1:0] g_tok [0:NA-1];
    logic [QW-1:0] g_long [0:NA-1]; logic [QW-1:0] g_short [0:NA-1]; logic [QW-1:0] g_qty [0:NA-1]; logic [PW+QW-1:0] g_onot [0:NA-1]; logic [NW-1:0] g_not [0:NA-1]; logic [TW-1:0] g_cap [0:NA-1];
    logic [PW-1:0] g_lo [0:NS-1]; logic [PW-1:0] g_hi [0:NS-1]; logic g_armed, g_fault; integer g_phase;
    // the event as the gate sees it one cycle later, with the kill input of the cycle it was offered
    logic e_v, e_kill, e_side; logic [1:0] e_t; logic [3:0] e_a, e_s; logic [PW-1:0] e_px; logic [QW-1:0] e_qty;
    // what must be shown the cycle after
    logic x_v, x_ord, x_ok_gate; logic [3:0] x_res; logic signed [QW+1:0] x_pos; logic [QW-1:0] x_ob, x_os; logic [NW-1:0] x_not; logic [TW-1:0] x_tok; logic [1:0] x_kind;
    logic x_arm_ok, x_kill, x_fault, x_buy, x_bad; logic [PW+QW-1:0] x_prod; logic [QW-1:0] x_qty_e, x_qty_max; logic [PW-1:0] x_px, x_lo, x_hi; logic [PW+QW-1:0] x_onot_max; logic signed [CW+1:0] x_long_post, x_short_post, x_long_max, x_short_max; logic [NW-1:0] x_not_post, x_not_max, x_toks_before;
    integer i, j;
    wire e_bad = (e_a >= NA) || (e_s >= NS);
    wire [PW+QW-1:0] e_prod = e_px * e_qty;
    wire [3:0] ai = e_bad ? 4'd0 : e_a, si = e_bad ? 4'd0 : e_s;
    wire signed [CW+1:0] pot_long = $signed({2'b00, acc_b[ai][si]}) - $signed({2'b00, can_b[ai][si]}) - $signed({2'b00, fil_s[ai][si]});      // worst-case long: accepted buys - cancelled buys - filled sells
    wire signed [CW+1:0] pot_short = $signed({2'b00, acc_s[ai][si]}) - $signed({2'b00, can_s[ai][si]}) - $signed({2'b00, fil_b[ai][si]});    // worst-case short exposure
    wire [CW+1:0] open_b = acc_b[ai][si] - fil_b[ai][si] - can_b[ai][si], open_s = acc_s[ai][si] - fil_s[ai][si] - can_s[ai][si];
    wire [NW-1:0] not_open = acc_n[ai] - rel_n[ai];
    wire buy = !e_side;
    wire signed [CW+1:0] pos_now = $signed({2'b00, fil_b[ai][si]}) - $signed({2'b00, fil_s[ai][si]});                                       // position = bought - sold (filled)
    logic [3:0] exp_res;
    always_comb begin
        exp_res = 4'd0;
        if (e_t == 2'd0) begin
            if (e_kill) exp_res = 4'd1;
            else if (!g_armed || g_fault) exp_res = 4'd2;
            else if (e_bad) exp_res = 4'd3;
            else if (e_qty == 0 || e_qty > g_qty[ai]) exp_res = 4'd4;
            else if (e_px < g_lo[si] || e_px > g_hi[si]) exp_res = 4'd5;
            else if (e_prod > g_onot[ai]) exp_res = 4'd6;
            else if (buy ? (pot_long + $signed({2'b00, e_qty}) > $signed({2'b00, g_long[ai]})) : (pot_short + $signed({2'b00, e_qty}) > $signed({2'b00, g_short[ai]}))) exp_res = 4'd7;
            else if (not_open + e_prod > g_not[ai]) exp_res = 4'd8;
            else if (g_tok[ai] == 0) exp_res = 4'd9;
        end else if (e_bad || (buy ? (e_qty > open_b) : (e_qty > open_s)) || e_prod > not_open) exp_res = 4'd10;
    end
    wire acc = e_v && e_t == 2'd0 && exp_res == 4'd0, rel = e_v && e_t != 2'd0 && exp_res == 4'd0, flt = e_v && e_t != 2'd0 && exp_res == 4'd10;
    wire tick = (g_phase == R - 1);
    always @(posedge clk) begin
        rst <= 1'b0; started <= 1'b1;
        e_v <= ev_valid && !rst; e_kill <= kill; e_t <= ev_type; e_a <= ev_acct; e_s <= ev_sym; e_side <= ev_side; e_px <= ev_px; e_qty <= ev_qty;
        if (rst) begin
            g_armed <= 1'b0; g_fault <= 1'b0; g_phase <= 0;
            for (i = 0; i < NA; i++) begin acc_n[i] <= 0; rel_n[i] <= 0; g_tok[i] <= 0; g_long[i] <= 0; g_short[i] <= 0; g_qty[i] <= 0; g_onot[i] <= 0; g_not[i] <= 0; g_cap[i] <= 0; for (j = 0; j < NS; j++) begin acc_b[i][j] <= 0; fil_b[i][j] <= 0; can_b[i][j] <= 0; acc_s[i][j] <= 0; fil_s[i][j] <= 0; can_s[i][j] <= 0; end end
            for (j = 0; j < NS; j++) begin g_lo[j] <= '1; g_hi[j] <= 0; end
        end else begin
            g_phase <= tick ? 0 : g_phase + 1;
            if (acc) begin
                if (buy) acc_b[ai][si] <= acc_b[ai][si] + e_qty; else acc_s[ai][si] <= acc_s[ai][si] + e_qty;
                acc_n[ai] <= acc_n[ai] + e_prod;
            end
            if (rel) begin
                if (buy) begin if (e_t == 2'd1) fil_b[ai][si] <= fil_b[ai][si] + e_qty; else can_b[ai][si] <= can_b[ai][si] + e_qty; end
                else begin if (e_t == 2'd1) fil_s[ai][si] <= fil_s[ai][si] + e_qty; else can_s[ai][si] <= can_s[ai][si] + e_qty; end
                rel_n[ai] <= rel_n[ai] + e_prod;
            end
            if (flt) g_fault <= 1'b1;
            for (i = 0; i < NA; i++) g_tok[i] <= (tick && (g_tok[i] - ((acc && ai == i) ? 1 : 0)) < g_cap[i]) ? (g_tok[i] - ((acc && ai == i) ? 1 : 0) + 1) : (g_tok[i] - ((acc && ai == i) ? 1 : 0));
            if (cfg_a_valid && cfg_a_idx < NA) for (i = 0; i < NA; i++) if (cfg_a_idx == i) begin g_long[i] <= cfg_maxlong; g_short[i] <= cfg_maxshort; g_qty[i] <= cfg_maxqty; g_onot[i] <= cfg_maxonot; g_not[i] <= cfg_maxnot; g_cap[i] <= cfg_cap; g_tok[i] <= cfg_cap; end
            if (cfg_b_valid && cfg_b_idx < NS) for (j = 0; j < NS; j++) if (cfg_b_idx == j) begin g_lo[j] <= cfg_lo; g_hi[j] <= cfg_hi; end
            if (ctl_disarm) g_armed <= 1'b0; else if (ctl_arm && !kill) g_armed <= 1'b1;
        end
        // what the gate must show next cycle, and what the world looks like if it says OK
        x_v <= e_v; x_ord <= e_t == 2'd0; x_res <= exp_res; x_kind <= e_t;
        x_pos <= e_bad ? 0 : (pos_now + ((rel && e_t == 2'd1) ? (buy ? $signed({2'b00, e_qty}) : -$signed({2'b00, e_qty})) : 0));
        x_ob <= e_bad ? 0 : (acc_b[ai][si] - fil_b[ai][si] - can_b[ai][si] + (acc && buy ? e_qty : 0) - ((rel && buy) ? e_qty : 0));
        x_os <= e_bad ? 0 : (acc_s[ai][si] - fil_s[ai][si] - can_s[ai][si] + (acc && !buy ? e_qty : 0) - ((rel && !buy) ? e_qty : 0));
        x_not <= e_bad ? 0 : (acc_n[ai] - rel_n[ai] + (acc ? e_prod : 0) - (rel ? e_prod : 0));
        x_tok <= e_bad ? 0 : (g_tok[ai] - (acc ? 1 : 0));
        x_buy <= buy; x_bad <= e_bad; x_arm_ok <= g_armed; x_fault <= g_fault; x_kill <= e_kill; x_prod <= e_prod; x_qty_e <= e_qty; x_qty_max <= g_qty[ai]; x_px <= e_px; x_lo <= g_lo[si]; x_hi <= g_hi[si]; x_onot_max <= g_onot[ai];
        x_long_post <= pot_long + $signed({2'b00, e_qty}); x_short_post <= pot_short + $signed({2'b00, e_qty}); x_long_max <= $signed({2'b00, g_long[ai]}); x_short_max <= $signed({2'b00, g_short[ai]});
        x_not_post <= not_open + e_prod; x_not_max <= g_not[ai]; x_toks_before <= g_tok[ai];
    end
    always @(*) if (started && !rst) begin
        // S2, S3: what the gate shows is what the sums say
        assert (o_valid == x_v);
        if (x_v) begin
            assert (o_kind == x_kind);
            assert (o_res == x_res);
            assert (o_pos == x_pos);
            assert (o_ob == x_ob);
            assert (o_os == x_os);
            assert (o_not == x_not);
            assert (o_tok == x_tok);
        end
        // S1: the safety property, on what the gate said (not on what the wrapper computed): an OK to an order means every limit holds after it
        if (o_valid && o_kind == 2'd0 && o_res == 4'd0) begin
            assert (x_arm_ok && !x_fault && !x_kill);                                   // fail closed: never OK while disarmed, faulted or killed
            assert (!x_bad);                                                            // the account and symbol exist
            assert (x_qty_e != 0 && x_qty_e <= x_qty_max);                              // quantity within the limit
            assert (x_px >= x_lo && x_px <= x_hi);                                      // price within the band
            assert (x_prod <= x_onot_max);                                              // the order's own notional within its limit
            if (x_buy) assert (x_long_post <= x_long_max); else assert (x_short_post <= x_short_max);   // worst-case long (short) exposure after the order within its limit
            assert (x_not_post <= x_not_max);                                           // total open notional after the order within its limit
            assert (x_toks_before != 0);                                                // a token was available
        end
        // S4: the bucket never holds more than its size
        for (i = 0; i < NA; i++) assert (g_tok[i] <= g_cap[i]);
    end
endmodule
