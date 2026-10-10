// Chapter 25: the order lifecycle: the risk gate (Chapter 23) and the order tracker joined. An order request is offered to the gate; if the gate says OK it is recorded in the tracker (and may be sent: the answer says so); if the tracker cannot record it (table full, token already open, zero quantity) the gate's charge is given back at once with a CANCEL release. Fills, cancels and rejects reported by the exchange make the tracker release to the gate what is no longer open, with the price the gate was charged. A report the tracker cannot explain sets its fault, which holds the gate's kill input high for good (fail closed). The gate's event port has one user per cycle: a release from the tracker first, then a give-back, then a new order. One order is in flight at a time (a small state machine); reports and cancel requests are never held up by it. The specification is in model/life_gold.py (class Sys).
module life #(parameter int NT = 4, parameter int NA = 4, parameter int NS = 4, parameter int QW = 16, parameter int PW = 16, parameter int R = 4, parameter int TW = 8) (
    input  logic clk, input logic rst,
    input  logic ord_valid, input logic [31:0] ord_tok, input logic [3:0] ord_acct, input logic [3:0] ord_sym, input logic ord_side, input logic [PW-1:0] ord_px, input logic [QW-1:0] ord_qty,
    output logic ord_ready,
    input  logic cr_valid, input logic [31:0] cr_tok, output logic cr_ready,
    input  logic r_valid, input logic [1:0] r_kind, input logic [31:0] r_tok, input logic [QW-1:0] r_qty,
    input  logic cfg_a_valid, input logic [3:0] cfg_a_idx, input logic [QW-1:0] cfg_maxlong, input logic [QW-1:0] cfg_maxshort, input logic [QW-1:0] cfg_maxqty, input logic [PW+QW-1:0] cfg_maxonot, input logic [PW+QW+1:0] cfg_maxnot, input logic [TW-1:0] cfg_cap,
    input  logic cfg_b_valid, input logic [3:0] cfg_b_idx, input logic [PW-1:0] cfg_lo, input logic [PW-1:0] cfg_hi,
    input  logic ctl_arm, input logic ctl_disarm, input logic ext_kill,
    output logic d_valid, output logic [4:0] d_res, output logic [31:0] d_tok,
    output logic c_valid, output logic [2:0] c_res,
    output logic rk_valid, output logic [1:0] rk_kind, output logic [3:0] rk_res, output logic signed [QW+1:0] rk_pos, output logic [QW-1:0] rk_ob, output logic [QW-1:0] rk_os, output logic [PW+QW+1:0] rk_not, output logic [TW-1:0] rk_tok,
    output logic [$clog2(NT+1)-1:0] t_live, output logic t_fault, output logic [2:0] st_o);
    localparam logic [2:0] IDLE = 3'd0, RISK1 = 3'd1, RISK2 = 3'd2, TNEW = 3'd3, TANS = 3'd4, RB = 3'd5;
    logic [2:0] st;
    // the order in flight
    logic [31:0] h_tok; logic [3:0] h_acct, h_sym; logic h_side; logic [PW-1:0] h_px; logic [QW-1:0] h_qty; logic [4:0] h_res;
    // ---- the tracker
    logic t_ready, t_ov, t_src, t_rv, t_rside, t_ofault; logic [2:0] t_res; logic [1:0] t_rtype; logic [3:0] t_racct, t_rsym; logic [PW-1:0] t_rpx; logic [QW-1:0] t_rqty;
    wire tl_valid = (st == TNEW) ? 1'b1 : cr_valid;
    track #(.NT(NT), .PW(PW), .QW(QW)) trk (.clk(clk), .rst(rst), .l_valid(tl_valid), .l_kind(st != TNEW), .l_tok(st == TNEW ? h_tok : cr_tok), .l_acct(h_acct), .l_sym(h_sym), .l_side(h_side), .l_px(h_px), .l_qty(h_qty), .ready(t_ready),
        .r_valid(r_valid), .r_kind(r_kind), .r_tok(r_tok), .r_qty(r_qty), .o_valid(t_ov), .o_src(t_src), .o_res(t_res), .o_rv(t_rv), .o_rtype(t_rtype), .o_racct(t_racct), .o_rsym(t_rsym), .o_rside(t_rside), .o_rpx(t_rpx), .o_rqty(t_rqty), .o_live(t_live), .o_fault(t_ofault));
    assign t_fault = t_ofault; assign st_o = st;
    assign cr_ready = (st != TNEW) && t_ready;
    wire cr_acc = cr_valid && cr_ready;
    assign c_valid = t_ov && !t_src && (st != TANS); assign c_res = t_res;
    // ---- the gate's event port
    wire give_back = (st == RB) && !t_rv;
    wire take_order = (st == IDLE) && ord_valid && !t_rv;
    assign ord_ready = (st == IDLE) && !t_rv;
    logic ev_valid; logic [1:0] ev_type; logic [3:0] ev_acct, ev_sym; logic ev_side; logic [PW-1:0] ev_px; logic [QW-1:0] ev_qty;
    always_comb begin
        ev_valid = 1'b1; ev_type = 2'd0; ev_acct = ord_acct; ev_sym = ord_sym; ev_side = ord_side; ev_px = ord_px; ev_qty = ord_qty;
        if (t_rv) begin ev_type = t_rtype; ev_acct = t_racct; ev_sym = t_rsym; ev_side = t_rside; ev_px = t_rpx; ev_qty = t_rqty; end
        else if (give_back) begin ev_type = 2'd2; ev_acct = h_acct; ev_sym = h_sym; ev_side = h_side; ev_px = h_px; ev_qty = h_qty; end
        else ev_valid = take_order;
    end
    risk #(.NA(NA), .NS(NS), .QW(QW), .PW(PW), .R(R), .TW(TW)) gate (.clk(clk), .rst(rst), .ev_valid(ev_valid), .ev_type(ev_type), .ev_acct(ev_acct), .ev_sym(ev_sym), .ev_side(ev_side), .ev_px(ev_px), .ev_qty(ev_qty),
        .cfg_a_valid(cfg_a_valid), .cfg_a_idx(cfg_a_idx), .cfg_maxlong(cfg_maxlong), .cfg_maxshort(cfg_maxshort), .cfg_maxqty(cfg_maxqty), .cfg_maxonot(cfg_maxonot), .cfg_maxnot(cfg_maxnot), .cfg_cap(cfg_cap),
        .cfg_b_valid(cfg_b_valid), .cfg_b_idx(cfg_b_idx), .cfg_lo(cfg_lo), .cfg_hi(cfg_hi), .ctl_arm(ctl_arm), .ctl_disarm(ctl_disarm), .kill(ext_kill || t_ofault),
        .o_valid(rk_valid), .o_kind(rk_kind), .o_res(rk_res), .o_pos(rk_pos), .o_ob(rk_ob), .o_os(rk_os), .o_not(rk_not), .o_tok(rk_tok));
    // ---- the state machine of the order in flight
    always_ff @(posedge clk) begin
        if (rst) begin st <= IDLE; d_valid <= 1'b0; d_res <= '0; d_tok <= '0; h_tok <= '0; h_acct <= '0; h_sym <= '0; h_side <= 1'b0; h_px <= '0; h_qty <= '0; h_res <= '0; end
        else begin
            d_valid <= 1'b0;
            case (st)
                IDLE: if (take_order) begin st <= RISK1; h_tok <= ord_tok; h_acct <= ord_acct; h_sym <= ord_sym; h_side <= ord_side; h_px <= ord_px; h_qty <= ord_qty; end
                RISK1: st <= RISK2;
                RISK2: begin                                                                 // the gate's answer to the order
                    if (rk_res != 4'd0) begin d_valid <= 1'b1; d_res <= {1'b0, rk_res}; d_tok <= h_tok; st <= IDLE; end
                    else st <= TNEW;
                end
                TNEW: if (t_ready) st <= TANS;                                               // the tracker takes the order unless a report wins the cycle
                TANS: begin
                    if (t_res == 3'd0) begin d_valid <= 1'b1; d_res <= 5'd0; d_tok <= h_tok; st <= IDLE; end
                    else begin h_res <= {2'b10, t_res}; st <= RB; end
                end
                RB: if (!t_rv) begin d_valid <= 1'b1; d_res <= h_res; d_tok <= h_tok; st <= IDLE; end
                default: st <= IDLE;
            endcase
        end
    end
    wire unused = &{1'b0, cr_acc, t_ov, rk_valid};
endmodule
// life_syn: the same design behind a handful of pins, ONLY for the place-and-route runs.
module life_syn #(parameter int NT = 4, parameter int NA = 4, parameter int NS = 4) (input logic clk, input logic rst, input logic si, input logic sh, output logic [15:0] info);
    logic [324:0] iv; logic ordr, crr, dv, cv, rkv, tf; logic [4:0] dr; logic [31:0] dt; logic [2:0] cr_; logic [1:0] rkk; logic [3:0] rkr; logic signed [17:0] pos; logic [15:0] ob, os; logic [33:0] nt_; logic [7:0] tk; logic [$clog2(NT+1)-1:0] live; logic [2:0] so;
    always_ff @(posedge clk) if (sh) iv <= {iv[323:0], si};
    life #(.NT(NT), .NA(NA), .NS(NS)) u (.clk(clk), .rst(rst), .ord_valid(iv[0]), .ord_tok(iv[32:1]), .ord_acct(iv[36:33]), .ord_sym(iv[40:37]), .ord_side(iv[41]), .ord_px(iv[57:42]), .ord_qty(iv[73:58]), .ord_ready(ordr),
        .cr_valid(iv[74]), .cr_tok(iv[106:75]), .cr_ready(crr), .r_valid(iv[107]), .r_kind(iv[109:108]), .r_tok(iv[141:110]), .r_qty(iv[157:142]),
        .cfg_a_valid(iv[158]), .cfg_a_idx(iv[162:159]), .cfg_maxlong(iv[178:163]), .cfg_maxshort(iv[194:179]), .cfg_maxqty(iv[210:195]), .cfg_maxonot(iv[242:211]), .cfg_maxnot(iv[276:243]), .cfg_cap(iv[284:277]),
        .cfg_b_valid(iv[285]), .cfg_b_idx(iv[289:286]), .cfg_lo(iv[305:290]), .cfg_hi(iv[321:306]), .ctl_arm(iv[322]), .ctl_disarm(iv[323]), .ext_kill(iv[324]),
        .d_valid(dv), .d_res(dr), .d_tok(dt), .c_valid(cv), .c_res(cr_), .rk_valid(rkv), .rk_kind(rkk), .rk_res(rkr), .rk_pos(pos), .rk_ob(ob), .rk_os(os), .rk_not(nt_), .rk_tok(tk), .t_live(live), .t_fault(tf), .st_o(so));
    logic [15:0] x, r1; always_comb x = 16'(dt) ^ 16'(dt >> 16) ^ {dr, cr_, rkk, rkr, ordr, crr} ^ pos[15:0] ^ {14'd0, pos[17:16]} ^ ob ^ os ^ 16'(nt_) ^ 16'(nt_ >> 16) ^ {8'd0, tk} ^ 16'(live) ^ {so, cv, rkv, tf, dv, 9'd0};
    always_ff @(posedge clk) begin r1 <= x; info <= r1; end
endmodule
