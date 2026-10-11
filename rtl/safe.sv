// Chapter 27: the supervised design. The reset generator, the supervisor and the wire-to-wire design of Chapter 26 joined: the units see the stretched reset; the gate's kill input is the control plane's OR the supervisor's (high in every state but RUN); the supervisor's logout request goes to the transmitter ahead of the control plane's. The specification is in model/safe_gold.py (the composition of Chapter 26's model with model/sup_gold.py).
module safe #(parameter int FT = 400, parameter int ST = 100, parameter int WARM = 48, parameter int RSTN = 8, parameter int QD = 8, parameter int F = 12, parameter int W = 8) (
    input  logic clk, input logic rst_in,
    input  logic go, input logic trip,
    input  logic s_valid, input logic s_sop, input logic s_eop, input logic [7:0] s_data,
    input  logic r_valid, input logic [1:0] r_kind, input logic [31:0] r_tok, input logic [15:0] r_qty,
    input  logic tc_valid, input logic [3:0] tc_rule, input logic tc_en, input logic tc_neg, input logic [4:0] tc_tmask, input logic tc_symany, input logic tc_sideany, input logic tc_side, input logic [2:0] tc_pxop, input logic [2:0] tc_shop, input logic [31:0] tc_symmask, input logic [31:0] tc_pxval, input logic [31:0] tc_shval,
    input  logic tl_valid, input logic [11:0] tl_addr, input logic [31:0] tl_key, input logic [4:0] tl_idx, input logic tl_val,
    input  logic cfg_a_valid, input logic [3:0] cfg_a_idx, input logic [15:0] cfg_maxlong, input logic [15:0] cfg_maxshort, input logic [15:0] cfg_maxqty, input logic [39:0] cfg_maxonot, input logic [41:0] cfg_maxnot, input logic [7:0] cfg_cap,
    input  logic cfg_b_valid, input logic [3:0] cfg_b_idx, input logic [15:0] cfg_lo, input logic [15:0] cfg_hi, input logic ctl_arm, input logic ctl_disarm, input logic ext_kill,
    input  logic sc_valid, input logic [2:0] sc_what, input logic [3:0] sc_sym, input logic [31:0] sc_data, input logic rx_valid, input logic [7:0] rx_type, input logic [31:0] rx_seq,
    input  logic cq_valid, input logic [2:0] cq_kind,
    output logic o_valid, output logic [8*W-1:0] o_data, output logic o_last, output logic [3:0] o_nb,
    output logic rst_u, output logic [1:0] sup_state, output logic sup_kill, output logic sup_cq, output logic [4:0] sup_cause);
    logic tap_slot, tap_fault, tap_txready, tap_quiet; logic [2:0] tap_sess;
    rst_gen #(.RSTN(RSTN)) rg (.clk(clk), .rst_in(rst_in), .rst_u(rst_u));
    sup #(.FT(FT), .ST(ST), .WARM(WARM)) sv (.clk(clk), .rst(rst_u), .go(go), .trip(trip), .feed(s_valid), .slot(tap_slot), .fault(tap_fault), .sess(tap_sess), .tx_ready(tap_txready), .quiet(tap_quiet), .state(sup_state), .kill(sup_kill), .cq_valid(sup_cq), .cause(sup_cause));
    w2w #(.NS(4), .NA(4), .NT(4), .QD(QD), .F(F), .TPIPE(1), .THR(512), .OQ(10), .W(W), .HB(20), .TL(60)) core (.clk(clk), .rst(rst_u), .s_valid(s_valid), .s_sop(s_sop), .s_eop(s_eop), .s_data(s_data),
        .r_valid(r_valid), .r_kind(r_kind), .r_tok(r_tok), .r_qty(r_qty),
        .tc_valid(tc_valid), .tc_rule(tc_rule), .tc_en(tc_en), .tc_neg(tc_neg), .tc_tmask(tc_tmask), .tc_symany(tc_symany), .tc_sideany(tc_sideany), .tc_side(tc_side), .tc_pxop(tc_pxop), .tc_shop(tc_shop), .tc_symmask(tc_symmask), .tc_pxval(tc_pxval), .tc_shval(tc_shval),
        .tl_valid(tl_valid), .tl_addr(tl_addr), .tl_key(tl_key), .tl_idx(tl_idx), .tl_val(tl_val),
        .cfg_a_valid(cfg_a_valid), .cfg_a_idx(cfg_a_idx), .cfg_maxlong(cfg_maxlong), .cfg_maxshort(cfg_maxshort), .cfg_maxqty(cfg_maxqty), .cfg_maxonot(cfg_maxonot), .cfg_maxnot(cfg_maxnot), .cfg_cap(cfg_cap),
        .cfg_b_valid(cfg_b_valid), .cfg_b_idx(cfg_b_idx), .cfg_lo(cfg_lo), .cfg_hi(cfg_hi), .ctl_arm(ctl_arm), .ctl_disarm(ctl_disarm), .ext_kill(ext_kill || sup_kill),
        .sc_valid(sc_valid), .sc_what(sc_what), .sc_sym(sc_sym), .sc_data(sc_data), .rx_valid(rx_valid), .rx_type(rx_type), .rx_seq(rx_seq), .cq_valid(cq_valid || sup_cq), .cq_kind(sup_cq ? 3'd4 : cq_kind),
        .o_valid(o_valid), .o_data(o_data), .o_last(o_last), .o_nb(o_nb), .tap_slot(tap_slot), .tap_fault(tap_fault), .tap_sess(tap_sess), .tap_txready(tap_txready), .tap_quiet(tap_quiet));
endmodule
