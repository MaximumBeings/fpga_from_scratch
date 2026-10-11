// Chapter 26 testbench for w2w: line k of out/w2w_stim.hex (125 hex digits; layout in model/w2w_gold.py `write_stim`) is everything on the pins in cycle k, cycle 0 being the first cycle after reset: a byte of the feed (valid, sop, eop, data), an exchange report, the trigger's rule and table writes, the gate's configuration, control and kill, the transmitter's configuration, the server's events and a control request (login, logout). Before every clock edge it prints
//   C <cycle> <queue length> <drops> <pushed> <book accepted> <book answered> <result> <signal answered> <order offered> <order taken> <missed> <refused> <held> <reject pending> <token counter>
//     <lifecycle: ready, cancel ready, answer valid, answer, token, cancel answer valid, cancel answer, gate answer valid, kind, result, position, open buys, open sells, notional, tokens, live orders, fault, state>
//     <transmitter: ready, beat valid, data, last, bytes, state, expected sequence number, answer valid, answer>      (zeros where the qualifying valid is low)
`timescale 1ns/1ps
`ifndef NC
`define NC 1000
`endif
`ifndef QD
`define QD 8
`endif
`ifndef F
`define F 12
`endif
`ifndef W
`define W 8
`endif
module w2w_tb;
    localparam int NC = `NC;
    logic clk = 0, rst = 1; logic [511:0] vec [0:NC-1]; int k, cyc = 0; logic run = 0;
    logic s_valid = 0, s_sop = 0, s_eop = 0; logic [7:0] s_data = '0;
    logic r_valid = 0; logic [1:0] r_kind = '0; logic [31:0] r_tok = '0; logic [15:0] r_qty = '0;
    logic tc_valid = 0, tc_en = 0, tc_neg = 0, tc_symany = 0, tc_sideany = 0, tc_side = 0; logic [3:0] tc_rule = '0; logic [4:0] tc_tmask = '0; logic [2:0] tc_pxop = '0, tc_shop = '0; logic [31:0] tc_symmask = '0, tc_pxval = '0, tc_shval = '0;
    logic tl_valid = 0, tl_val = 0; logic [11:0] tl_addr = '0; logic [31:0] tl_key = '0; logic [4:0] tl_idx = '0;
    logic cfg_a_valid = 0, cfg_b_valid = 0, ctl_arm = 0, ctl_disarm = 0, ext_kill = 0; logic [3:0] cfg_a_idx = '0, cfg_b_idx = '0; logic [15:0] cfg_maxlong = '0, cfg_maxshort = '0, cfg_maxqty = '0, cfg_lo = '0, cfg_hi = '0; logic [39:0] cfg_maxonot = '0; logic [41:0] cfg_maxnot = '0; logic [7:0] cfg_cap = '0;
    logic sc_valid = 0, rx_valid = 0, cq_valid = 0; logic [2:0] sc_what = '0, cq_kind = '0; logic [3:0] sc_sym = '0; logic [31:0] sc_data = '0, rx_seq = '0; logic [7:0] rx_type = '0;
    logic o_valid, o_last; logic [8*`W-1:0] o_data; logic [3:0] o_nb;
    w2w #(.NS(4), .NA(4), .NT(4), .QD(`QD), .F(`F), .TPIPE(1), .THR(512), .OQ(10), .W(`W), .HB(20), .TL(60)) dut (.clk(clk), .rst(rst), .s_valid(s_valid), .s_sop(s_sop), .s_eop(s_eop), .s_data(s_data),
        .r_valid(r_valid), .r_kind(r_kind), .r_tok(r_tok), .r_qty(r_qty),
        .tc_valid(tc_valid), .tc_rule(tc_rule), .tc_en(tc_en), .tc_neg(tc_neg), .tc_tmask(tc_tmask), .tc_symany(tc_symany), .tc_sideany(tc_sideany), .tc_side(tc_side), .tc_pxop(tc_pxop), .tc_shop(tc_shop), .tc_symmask(tc_symmask), .tc_pxval(tc_pxval), .tc_shval(tc_shval),
        .tl_valid(tl_valid), .tl_addr(tl_addr), .tl_key(tl_key), .tl_idx(tl_idx), .tl_val(tl_val),
        .cfg_a_valid(cfg_a_valid), .cfg_a_idx(cfg_a_idx), .cfg_maxlong(cfg_maxlong), .cfg_maxshort(cfg_maxshort), .cfg_maxqty(cfg_maxqty), .cfg_maxonot(cfg_maxonot), .cfg_maxnot(cfg_maxnot), .cfg_cap(cfg_cap),
        .cfg_b_valid(cfg_b_valid), .cfg_b_idx(cfg_b_idx), .cfg_lo(cfg_lo), .cfg_hi(cfg_hi), .ctl_arm(ctl_arm), .ctl_disarm(ctl_disarm), .ext_kill(ext_kill),
        .sc_valid(sc_valid), .sc_what(sc_what), .sc_sym(sc_sym), .sc_data(sc_data), .rx_valid(rx_valid), .rx_type(rx_type), .rx_seq(rx_seq), .cq_valid(cq_valid), .cq_kind(cq_kind),
        .o_valid(o_valid), .o_data(o_data), .o_last(o_last), .o_nb(o_nb));
    always #4 clk = ~clk;
    wire signed [17:0] pos_s = dut.rk_pos;
    always @(posedge clk) if (run) begin
        $display("C %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d  %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d  %0d %0d %0d %0d %0d %0d %0d %0d %0d", cyc,
            dut.fcnt, dut.drops, dut.fq_push, dut.bk_acc, dut.bk_o_valid, dut.bk_o_valid ? dut.bk_o_res : 3'd0, dut.sg_v, dut.ord_valid, dut.ord_acc, dut.miss, dut.refused, dut.snd_hold, dut.rej_pend, dut.tokc[15:0],
            dut.ord_ready, dut.cr_ready, dut.d_valid, dut.d_valid ? dut.d_res : 5'd0, dut.d_valid ? dut.d_tok : 32'd0, dut.c_valid, dut.c_valid ? dut.c_res : 3'd0, dut.rk_valid, dut.rk_valid ? dut.rk_kind : 2'd0, dut.rk_valid ? dut.rk_res : 4'd0,
            dut.rk_valid ? pos_s : 18'sd0, dut.rk_valid ? dut.rk_ob : 16'd0, dut.rk_valid ? dut.rk_os : 16'd0, dut.rk_valid ? dut.rk_not : 34'd0, dut.rk_valid ? dut.rk_tok : 8'd0, dut.t_live, dut.t_fault, dut.st_o,
            dut.tx_ready, o_valid, o_valid ? 64'(o_data) : 64'd0, o_valid ? o_last : 1'b0, o_valid ? o_nb : 4'd0, dut.ostate, dut.oexp, dut.rv_, dut.rv_ ? dut.ores : 2'd0);
        cyc++;
    end
    initial begin
        $readmemh("out/w2w_stim.hex", vec);
        repeat (3) @(negedge clk); rst = 0;
        for (k = 0; k < NC; k++) begin
            s_valid = vec[k][0]; s_sop = vec[k][1]; s_eop = vec[k][2]; s_data = vec[k][10:3];
            r_valid = vec[k][11]; r_kind = vec[k][13:12]; r_tok = vec[k][45:14]; r_qty = vec[k][61:46];
            tc_valid = vec[k][62]; tc_rule = vec[k][66:63]; tc_en = vec[k][67]; tc_neg = vec[k][68]; tc_tmask = vec[k][73:69]; tc_symany = vec[k][74]; tc_sideany = vec[k][75]; tc_side = vec[k][76]; tc_pxop = vec[k][79:77]; tc_shop = vec[k][82:80]; tc_symmask = vec[k][114:83]; tc_pxval = vec[k][146:115]; tc_shval = vec[k][178:147];
            tl_valid = vec[k][179]; tl_addr = vec[k][191:180]; tl_key = vec[k][223:192]; tl_idx = vec[k][228:224]; tl_val = vec[k][229];
            cfg_a_valid = vec[k][230]; cfg_a_idx = vec[k][234:231]; cfg_maxlong = vec[k][250:235]; cfg_maxshort = vec[k][266:251]; cfg_maxqty = vec[k][282:267]; cfg_maxonot = vec[k][322:283]; cfg_maxnot = vec[k][364:323]; cfg_cap = vec[k][372:365];
            cfg_b_valid = vec[k][373]; cfg_b_idx = vec[k][377:374]; cfg_lo = vec[k][393:378]; cfg_hi = vec[k][409:394]; ctl_arm = vec[k][410]; ctl_disarm = vec[k][411]; ext_kill = vec[k][412];
            sc_valid = vec[k][413]; sc_what = vec[k][416:414]; sc_sym = vec[k][420:417]; sc_data = vec[k][452:421]; rx_valid = vec[k][453]; rx_type = vec[k][461:454]; rx_seq = vec[k][493:462]; cq_valid = vec[k][494]; cq_kind = vec[k][497:495];
            run = 1; @(negedge clk);
        end
        s_valid = 0; r_valid = 0; tc_valid = 0; tl_valid = 0; cfg_a_valid = 0; cfg_b_valid = 0; ctl_arm = 0; ctl_disarm = 0; ext_kill = 0; sc_valid = 0; rx_valid = 0; cq_valid = 0; repeat (4) @(negedge clk); $finish;
    end
endmodule
