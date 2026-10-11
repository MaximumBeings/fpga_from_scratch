// Chapter 26: wire to wire. The units of Chapters 16 to 25 chained into one design: bytes of a MoldUDP64 + ITCH feed in; bytes of an order entry stream out. The path of a message: the PARSER (Chapter 16; one byte per cycle) -> the ADAPTER (a message becomes a book event; a small FIFO absorbs bursts and counts what it must drop) -> the ORDER BOOK (Chapter 20; variable time) -> in parallel the SIGNAL unit (Chapter 22) and the TRIGGER engine (Chapter 21) -> the STRATEGY (one comparison: a rule fired and the book is lopsided: buy at the ask or sell at the bid, a fixed quantity) -> the LIFECYCLE (Chapter 25: risk gate + tracker) -> the TRANSMITTER (Chapter 24). One message is in the book-signal-strategy stage at a time (`slot`), so nothing has to be matched up after the fact; the FIFO in front of it is what the parser's one-byte-per-cycle pace and the book's variable time are reconciled by. A transmitter that refuses an order the gate has charged is reported to the tracker as a REJECT, which gives the charge back. The specification is in model/wire_gold.py.
module w2w #(parameter int NS = 4, parameter int NA = 4, parameter int NT = 4, parameter int QD = 8, parameter int F = 12, parameter int TPIPE = 1, parameter int THR = 512, parameter int OQ = 10, parameter int W = 8, parameter int HB = 20, parameter int TL = 60) (
    input  logic clk, input logic rst,
    // the wire
    input  logic s_valid, input logic s_sop, input logic s_eop, input logic [7:0] s_data,
    // the exchange's reports (Chapter 25) and the control plane
    input  logic r_valid, input logic [1:0] r_kind, input logic [31:0] r_tok, input logic [15:0] r_qty,
    input  logic tc_valid, input logic [3:0] tc_rule, input logic tc_en, input logic tc_neg, input logic [4:0] tc_tmask, input logic tc_symany, input logic tc_sideany, input logic tc_side, input logic [2:0] tc_pxop, input logic [2:0] tc_shop, input logic [31:0] tc_symmask, input logic [31:0] tc_pxval, input logic [31:0] tc_shval,
    input  logic tl_valid, input logic [11:0] tl_addr, input logic [31:0] tl_key, input logic [4:0] tl_idx, input logic tl_val,
    input  logic cfg_a_valid, input logic [3:0] cfg_a_idx, input logic [15:0] cfg_maxlong, input logic [15:0] cfg_maxshort, input logic [15:0] cfg_maxqty, input logic [39:0] cfg_maxonot, input logic [41:0] cfg_maxnot, input logic [7:0] cfg_cap,
    input  logic cfg_b_valid, input logic [3:0] cfg_b_idx, input logic [15:0] cfg_lo, input logic [15:0] cfg_hi, input logic ctl_arm, input logic ctl_disarm, input logic ext_kill,
    input  logic sc_valid, input logic [2:0] sc_what, input logic [3:0] sc_sym, input logic [31:0] sc_data, input logic rx_valid, input logic [7:0] rx_type, input logic [31:0] rx_seq,
    input  logic cq_valid, input logic [2:0] cq_kind,
    // the order entry stream
    output logic o_valid, output logic [8*W-1:0] o_data, output logic o_last, output logic [3:0] o_nb,
    // what a supervisor needs to see (Chapter 27)
    output logic tap_slot, output logic tap_fault, output logic [2:0] tap_sess, output logic tap_txready, output logic tap_quiet);
    localparam int SW = (NS > 1) ? $clog2(NS) : 1;
    // ---- the parser
    logic m_valid; logic [7:0] m_type; logic [1:0] m_err; logic [15:0] m_idx; logic [63:0] h_seq; logic p_valid, p_trunc, p_cntbad; logic [79:0] h_session; logic [15:0] h_count;
    logic [15:0] f_locate, f_tracking; logic [47:0] f_ts; logic [7:0] f_event; logic [63:0] f_ref; logic [7:0] f_side; logic [31:0] f_shares; logic [63:0] f_stock; logic [31:0] f_price, f_mpid; logic [63:0] f_match, f_newref;
    mold_itch parser (.clk(clk), .rst(rst), .valid(s_valid), .sop(s_sop), .eop(s_eop), .data(s_data), .m_valid(m_valid), .m_type(m_type), .m_err(m_err), .m_idx(m_idx), .h_seq(h_seq), .p_valid(p_valid), .p_trunc(p_trunc), .p_cntbad(p_cntbad), .h_session(h_session), .h_count(h_count),
        .f_locate(f_locate), .f_tracking(f_tracking), .f_ts(f_ts), .f_event(f_event), .f_ref(f_ref), .f_side(f_side), .f_shares(f_shares), .f_stock(f_stock), .f_price(f_price), .f_mpid(f_mpid), .f_match(f_match), .f_newref(f_newref));
    // ---- the adapter: a message becomes a book event (A, F: add; E: execute; X: cancel; D: delete; U: replace); anything else, any message with an error and any symbol index of NS or more is filtered out
    logic ad_ok; logic [2:0] ad_t; logic ad_side; logic [31:0] ad_px, ad_sh;
    always_comb begin
        ad_t = 3'd0; ad_ok = 1'b0; ad_side = 1'b0; ad_px = 32'd0; ad_sh = 32'd0;
        if (m_valid && m_err == 2'd0 && f_locate < 16'(NS)) case (m_type)
            8'h41, 8'h46: begin ad_ok = 1'b1; ad_t = 3'd0; ad_side = (f_side == 8'h53); ad_px = f_price; ad_sh = f_shares; end
            8'h45: begin ad_ok = 1'b1; ad_t = 3'd1; ad_sh = f_shares; end
            8'h58: begin ad_ok = 1'b1; ad_t = 3'd2; ad_sh = f_shares; end
            8'h44: begin ad_ok = 1'b1; ad_t = 3'd3; end
            8'h55: begin ad_ok = 1'b1; ad_t = 3'd4; ad_px = f_price; ad_sh = f_shares; end
            default: ;
        endcase
    end
    // ---- the FIFO (registers): {type, ref, ref2, symbol, side, price, shares}
    localparam int EW = 3 + 32 + 32 + SW + 1 + 32 + 32;
    logic [EW-1:0] fq [0:QD-1]; logic [$clog2(QD+1)-1:0] fcnt; logic [$clog2(QD)-1:0] fhd, ftl; logic [15:0] drops;
    wire fq_full = (fcnt == ($clog2(QD+1))'(QD));
    wire fq_push = ad_ok && !fq_full;
    logic slot; logic bk_ready; wire [EW-1:0] fh = fq[fhd];
    wire bk_in_valid = (fcnt != '0) && !slot; wire bk_acc = bk_in_valid && bk_ready;
    // ---- the order book
    logic bk_o_valid; logic [2:0] bk_o_res; logic [SW-1:0] bk_o_sym; logic [31:0] bk_bpx, bk_bsh, bk_apx, bk_ash; logic [7:0] bk_bn, bk_an; logic [15:0] bk_nord;
    book2 #(.NS(NS), .D(8), .NB(8), .K(4)) book (.clk(clk), .rst(rst), .in_valid(bk_in_valid), .in_type(fh[129+SW +: 3]), .in_ref(fh[97+SW +: 32]), .in_ref2(fh[65+SW +: 32]), .in_sym(fh[65 +: SW]), .in_side(fh[64]), .in_px(fh[63:32]), .in_sh(fh[31:0]), .in_ready(bk_ready),
        .o_valid(bk_o_valid), .o_res(bk_o_res), .o_sym(bk_o_sym), .o_bpx(bk_bpx), .o_bsh(bk_bsh), .o_apx(bk_apx), .o_ash(bk_ash), .o_bn(bk_bn), .o_an(bk_an), .o_nord(bk_nord));
    // the event as accepted, held for the trigger (the book's own result carries only the symbol)
    logic [2:0] h_t; logic [SW-1:0] h_sym; logic h_side; logic [31:0] h_px, h_sh;
    always_ff @(posedge clk) if (rst) begin h_t <= '0; h_sym <= '0; h_side <= 1'b0; h_px <= '0; h_sh <= '0; end else if (bk_acc) begin h_t <= fh[129+SW +: 3]; h_sym <= fh[65 +: SW]; h_side <= fh[64]; h_px <= fh[63:32]; h_sh <= fh[31:0]; end
    // ---- the signal unit and the trigger engine, both fed with the book's result
    logic sg_ready, sg_v, sg_ok, sg_cross, sg_lock; logic [24:0] sg_mid2; logic signed [24:0] sg_spread; logic [F:0] sg_w; logic signed [F+1:0] sg_imb; logic [24+F-1:0] sg_micro;
    sig #(.PW(24), .QW(20), .F(F), .DIV(1)) sgu (.clk(clk), .rst(rst), .in_valid(bk_o_valid), .in_bpx(bk_bpx[23:0]), .in_bsh(bk_bsh[19:0]), .in_apx(bk_apx[23:0]), .in_ash(bk_ash[19:0]), .in_ready(sg_ready),
        .o_valid(sg_v), .o_ok(sg_ok), .o_mid2(sg_mid2), .o_spread(sg_spread), .o_cross(sg_cross), .o_lock(sg_lock), .o_w(sg_w), .o_imb(sg_imb), .o_micro(sg_micro));
    logic tg_ready, tg_v, tg_found, tg_fire; logic [4:0] tg_idx; logic [3:0] tg_mask, tg_first;
    trig #(.NB(8), .K(2), .R(4), .PIPE(TPIPE)) tgu (.clk(clk), .rst(rst), .in_valid(bk_o_valid), .in_type(h_t), .in_key({{(32-SW){1'b0}}, h_sym}), .in_side(h_side), .in_px(h_px), .in_sh(h_sh),
        .cfg_valid(tc_valid), .cfg_rule(tc_rule), .cfg_en(tc_en), .cfg_neg(tc_neg), .cfg_tmask(tc_tmask), .cfg_symany(tc_symany), .cfg_sideany(tc_sideany), .cfg_side(tc_side), .cfg_pxop(tc_pxop), .cfg_shop(tc_shop), .cfg_symmask(tc_symmask), .cfg_pxval(tc_pxval), .cfg_shval(tc_shval),
        .ld_valid(tl_valid), .ld_addr(tl_addr), .ld_key(tl_key), .ld_idx(tl_idx), .ld_val(tl_val), .o_ready(tg_ready), .o_valid(tg_v), .o_found(tg_found), .o_idx(tg_idx), .o_mask(tg_mask), .o_fire(tg_fire), .o_first(tg_first));
    logic t_fire; logic r_okres; logic [SW-1:0] r_sym;
    always_ff @(posedge clk) if (rst) begin t_fire <= 1'b0; r_okres <= 1'b0; r_sym <= '0; end else begin
        if (tg_v) t_fire <= tg_fire;
        if (bk_o_valid) begin r_okres <= (bk_o_res == 3'd0); r_sym <= bk_o_sym; end
    end
    // ---- the strategy: in the cycle the signal unit answers (one message in the stage), buy at the ask or sell at the bid if the rule fired, the event was applied and the book is lopsided enough
    wire dec_buy = sg_v && sg_ok && !sg_cross && !sg_lock && t_fire && r_okres && (sg_imb >= $signed((F+2)'(THR)));
    wire dec_sell = sg_v && sg_ok && !sg_cross && !sg_lock && t_fire && r_okres && (sg_imb <= -$signed((F+2)'(THR)));
    wire ord_valid = dec_buy || dec_sell;
    wire [24:0] ask_px = 25'((sg_mid2 + 25'(sg_spread)) >> 1), bid_px = 25'((sg_mid2 - 25'(sg_spread)) >> 1);
    // ---- the lifecycle
    logic ord_ready; logic [31:0] tokc; logic o_acc_v; logic [31:0] o_tok; logic [3:0] o_sym; logic o_side; logic [15:0] o_px;
    wire ord_acc = ord_valid && ord_ready;
    logic rej_pend; wire rep_v = r_valid || rej_pend;
    logic d_valid; logic [4:0] d_res; logic [31:0] d_tok; logic c_valid; logic [2:0] c_res; logic rk_valid; logic [1:0] rk_kind; logic [3:0] rk_res; logic signed [17:0] rk_pos; logic [15:0] rk_ob, rk_os; logic [33:0] rk_not; logic [7:0] rk_tok; logic [$clog2(NT+1)-1:0] t_live; logic t_fault; logic [2:0] st_o; logic cr_ready;
    life #(.NT(NT), .NA(NA), .NS(NS), .QW(16), .PW(16), .R(4), .TW(8)) lc (.clk(clk), .rst(rst), .ord_valid(ord_valid), .ord_tok(tokc), .ord_acct(4'd0), .ord_sym({{(4-SW){1'b0}}, r_sym}), .ord_side(dec_sell), .ord_px(dec_sell ? bid_px[15:0] : ask_px[15:0]), .ord_qty(16'(OQ)), .ord_ready(ord_ready),
        .cr_valid(1'b0), .cr_tok(32'd0), .cr_ready(cr_ready), .r_valid(rep_v), .r_kind(r_valid ? r_kind : 2'd3), .r_tok(r_valid ? r_tok : o_tok), .r_qty(r_valid ? r_qty : 16'd0),
        .cfg_a_valid(cfg_a_valid), .cfg_a_idx(cfg_a_idx), .cfg_maxlong(cfg_maxlong), .cfg_maxshort(cfg_maxshort), .cfg_maxqty(cfg_maxqty), .cfg_maxonot(cfg_maxonot[31:0]), .cfg_maxnot(cfg_maxnot[33:0]), .cfg_cap(cfg_cap),
        .cfg_b_valid(cfg_b_valid), .cfg_b_idx(cfg_b_idx), .cfg_lo(cfg_lo), .cfg_hi(cfg_hi), .ctl_arm(ctl_arm), .ctl_disarm(ctl_disarm), .ext_kill(ext_kill),
        .d_valid(d_valid), .d_res(d_res), .d_tok(d_tok), .c_valid(c_valid), .c_res(c_res), .rk_valid(rk_valid), .rk_kind(rk_kind), .rk_res(rk_res), .rk_pos(rk_pos), .rk_ob(rk_ob), .rk_os(rk_os), .rk_not(rk_not), .rk_tok(rk_tok), .t_live(t_live), .t_fault(t_fault), .st_o(st_o));
    // ---- the transmitter: an order the gate and the tracker accepted (answer 0) is sent; held if the transmitter is not ready
    logic snd_hold; logic ord_q; logic [15:0] miss, refused;
    wire snd_now = (d_valid && d_res == 5'd0) || snd_hold;
    logic tx_ready, rv_, ov_; logic [8*W-1:0] od_; logic ol_; logic [3:0] on_; logic [2:0] ostate; logic [31:0] oexp; logic [1:0] ores;
    wire tx_in_valid = cq_valid || snd_now;
    sess #(.W(W), .NS(NS), .HB(HB), .TL(TL)) xmit (.clk(clk), .rst(rst), .in_valid(tx_in_valid), .in_kind(cq_valid ? cq_kind : 3'd0), .in_tok(o_tok), .in_tok2(32'd0), .in_sym(o_sym), .in_side(o_side), .in_shares(32'(OQ)), .in_px(32'(o_px)), .in_tif(32'd0), .in_ready(tx_ready),
        .rx_valid(rx_valid), .rx_type(rx_type), .rx_seq(rx_seq), .cfg_valid(sc_valid), .cfg_what(sc_what), .cfg_sym(sc_sym), .cfg_data(sc_data),
        .o_valid(o_valid), .o_data(o_data), .o_last(o_last), .o_nb(o_nb), .o_state(ostate), .o_exp(oexp), .o_rv(rv_), .o_res(ores));
    assign tap_slot = slot; assign tap_fault = t_fault; assign tap_sess = ostate; assign tap_txready = tx_ready; assign tap_quiet = (st_o == 3'd0) && !snd_hold && !d_valid;
    // ---- state
    always_ff @(posedge clk) begin
        if (rst) begin fcnt <= '0; fhd <= '0; ftl <= '0; drops <= '0; slot <= 1'b0; tokc <= 32'd1; o_tok <= '0; o_sym <= '0; o_side <= 1'b0; o_px <= '0; miss <= '0; rej_pend <= 1'b0; snd_hold <= 1'b0; ord_q <= 1'b0; refused <= '0; end
        else begin
            if (fq_push) begin fq[ftl] <= {ad_t, f_ref[31:0], f_newref[31:0], f_locate[SW-1:0], ad_side, ad_px, ad_sh}; ftl <= (ftl == ($clog2(QD))'(QD - 1)) ? '0 : ftl + 1'b1; end
            if (ad_ok && fq_full) drops <= drops + 1'b1;
            if (bk_acc) fhd <= (fhd == ($clog2(QD))'(QD - 1)) ? '0 : fhd + 1'b1;
            fcnt <= fcnt + ($bits(fcnt))'(fq_push) - ($bits(fcnt))'(bk_acc);
            if (bk_acc) slot <= 1'b1; else if (sg_v) slot <= 1'b0;
            if (ord_acc) begin tokc <= tokc + 1'b1; o_tok <= tokc; o_sym <= {{(4-SW){1'b0}}, r_sym}; o_side <= dec_sell; o_px <= dec_sell ? bid_px[15:0] : ask_px[15:0]; end
            if (ord_valid && !ord_ready) miss <= miss + 1'b1;
            // the transmitter's answer to an order: a refusal is a reject of that order
            ord_q <= snd_now && tx_ready && !cq_valid;
            if (rv_ && ord_q && ores != 2'd0) begin rej_pend <= 1'b1; refused <= refused + 1'b1; end
            else if (rej_pend && !r_valid) rej_pend <= 1'b0;
            // one held order is enough: the next answer comes at least 24 cycles after this one (the strategy slot lasts n + F + 4 cycles) and the transmitter is busy for at most 31 (W = 1)
            if (snd_now && !tx_ready && !cq_valid) snd_hold <= 1'b1;
            else if (snd_hold && tx_ready) snd_hold <= 1'b0;
        end
    end
endmodule
// w2w_syn: the whole design behind a handful of pins, ONLY so that it can be placed: the 498 input bits (the layout of tb/w2w_tb.sv) are shifted in serially, the 76 output bits registered and folded into one 16-bit word.
module w2w_syn #(parameter int QD = 8, parameter int F = 12) (input logic clk, input logic rst, input logic si, input logic sh, output logic [15:0] info);
    logic [497:0] iv; logic o_valid, o_last; logic [63:0] o_data; logic [3:0] o_nb;
    always_ff @(posedge clk) if (sh) iv <= {iv[496:0], si};
    w2w #(.QD(QD), .F(F)) u (.clk(clk), .rst(rst), .s_valid(iv[0]), .s_sop(iv[1]), .s_eop(iv[2]), .s_data(iv[10:3]),
        .r_valid(iv[11]), .r_kind(iv[13:12]), .r_tok(iv[45:14]), .r_qty(iv[61:46]),
        .tc_valid(iv[62]), .tc_rule(iv[66:63]), .tc_en(iv[67]), .tc_neg(iv[68]), .tc_tmask(iv[73:69]), .tc_symany(iv[74]), .tc_sideany(iv[75]), .tc_side(iv[76]), .tc_pxop(iv[79:77]), .tc_shop(iv[82:80]), .tc_symmask(iv[114:83]), .tc_pxval(iv[146:115]), .tc_shval(iv[178:147]),
        .tl_valid(iv[179]), .tl_addr(iv[191:180]), .tl_key(iv[223:192]), .tl_idx(iv[228:224]), .tl_val(iv[229]),
        .cfg_a_valid(iv[230]), .cfg_a_idx(iv[234:231]), .cfg_maxlong(iv[250:235]), .cfg_maxshort(iv[266:251]), .cfg_maxqty(iv[282:267]), .cfg_maxonot(iv[322:283]), .cfg_maxnot(iv[364:323]), .cfg_cap(iv[372:365]),
        .cfg_b_valid(iv[373]), .cfg_b_idx(iv[377:374]), .cfg_lo(iv[393:378]), .cfg_hi(iv[409:394]), .ctl_arm(iv[410]), .ctl_disarm(iv[411]), .ext_kill(iv[412]),
        .sc_valid(iv[413]), .sc_what(iv[416:414]), .sc_sym(iv[420:417]), .sc_data(iv[452:421]), .rx_valid(iv[453]), .rx_type(iv[461:454]), .rx_seq(iv[493:462]), .cq_valid(iv[494]), .cq_kind(iv[497:495]),
        .o_valid(o_valid), .o_data(o_data), .o_last(o_last), .o_nb(o_nb), .tap_slot(), .tap_fault(), .tap_sess(), .tap_txready(), .tap_quiet());
    logic [15:0] x, r1; always_comb x = o_data[15:0] ^ o_data[31:16] ^ o_data[47:32] ^ o_data[63:48] ^ {o_nb, o_last, o_valid, 10'd0};
    always_ff @(posedge clk) begin r1 <= x; info <= r1; end
endmodule
