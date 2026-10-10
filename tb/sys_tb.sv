// Chapter 25 testbench for life (the gate and the tracker joined): line k of out/sys_stim.hex (82 hex digits, layout in model/sys_gold.py write_stim) is everything on the pins in cycle k, cycle 0 being the first cycle after reset. Before every clock edge it prints
//   C <cycle> <ord_ready> <cr_ready> <d_valid> <d_res> <d_tok> <c_valid> <c_res> <rk_valid> <kind> <res> <pos> <ob> <os> <not> <tok> <live> <fault> <state>     (zeros where the qualifying valid is low; pos signed)
`timescale 1ns/1ps
`ifndef NC
`define NC 1000
`endif
`ifndef NT
`define NT 4
`endif
`ifndef R
`define R 4
`endif
module sys_tb;
    localparam int NC = `NC, NT = `NT;
    logic clk = 0, rst = 1; logic [327:0] vec [0:NC-1]; int k, cyc = 0; logic run = 0;
    logic ord_valid = 0, ord_side = 0, cr_valid = 0, r_valid = 0, cfg_a_valid = 0, cfg_b_valid = 0, ctl_arm = 0, ctl_disarm = 0, ext_kill = 0;
    logic [31:0] ord_tok = '0, cr_tok = '0, r_tok = '0; logic [3:0] ord_acct = '0, ord_sym = '0, cfg_a_idx = '0, cfg_b_idx = '0; logic [15:0] ord_px = '0, ord_qty = '0, r_qty = '0, cfg_maxlong = '0, cfg_maxshort = '0, cfg_maxqty = '0, cfg_lo = '0, cfg_hi = '0;
    logic [1:0] r_kind = '0; logic [31:0] cfg_maxonot = '0; logic [33:0] cfg_maxnot = '0; logic [7:0] cfg_cap = '0;
    logic ord_ready, cr_ready, d_valid, c_valid, rk_valid, t_fault; logic [4:0] d_res; logic [31:0] d_tok; logic [2:0] c_res, st_o; logic [1:0] rk_kind; logic [3:0] rk_res; logic signed [17:0] rk_pos; logic [15:0] rk_ob, rk_os; logic [33:0] rk_not; logic [7:0] rk_tok; logic [$clog2(NT+1)-1:0] t_live;
    life #(.NT(NT), .NA(4), .NS(4), .QW(16), .PW(16), .R(`R), .TW(8)) dut (.clk(clk), .rst(rst), .ord_valid(ord_valid), .ord_tok(ord_tok), .ord_acct(ord_acct), .ord_sym(ord_sym), .ord_side(ord_side), .ord_px(ord_px), .ord_qty(ord_qty), .ord_ready(ord_ready),
        .cr_valid(cr_valid), .cr_tok(cr_tok), .cr_ready(cr_ready), .r_valid(r_valid), .r_kind(r_kind), .r_tok(r_tok), .r_qty(r_qty),
        .cfg_a_valid(cfg_a_valid), .cfg_a_idx(cfg_a_idx), .cfg_maxlong(cfg_maxlong), .cfg_maxshort(cfg_maxshort), .cfg_maxqty(cfg_maxqty), .cfg_maxonot(cfg_maxonot), .cfg_maxnot(cfg_maxnot), .cfg_cap(cfg_cap),
        .cfg_b_valid(cfg_b_valid), .cfg_b_idx(cfg_b_idx), .cfg_lo(cfg_lo), .cfg_hi(cfg_hi), .ctl_arm(ctl_arm), .ctl_disarm(ctl_disarm), .ext_kill(ext_kill),
        .d_valid(d_valid), .d_res(d_res), .d_tok(d_tok), .c_valid(c_valid), .c_res(c_res), .rk_valid(rk_valid), .rk_kind(rk_kind), .rk_res(rk_res), .rk_pos(rk_pos), .rk_ob(rk_ob), .rk_os(rk_os), .rk_not(rk_not), .rk_tok(rk_tok), .t_live(t_live), .t_fault(t_fault), .st_o(st_o));
    always #4 clk = ~clk;
`ifdef GARBAGE
    initial begin   // Icarus only: the registers that reset must clear power up with garbage
        dut.st = 3'd4; dut.d_valid = 1'b1; dut.d_res = 5'd9; dut.d_tok = 32'hABCD; dut.h_tok = 32'h1234; dut.h_acct = 4'd3; dut.h_sym = 4'd3; dut.h_side = 1'b1; dut.h_px = 16'h4321; dut.h_qty = 16'h1111; dut.h_res = 5'd7;
        for (int i = 0; i < NT; i++) begin dut.trk.used[i] = 1'b1; dut.trk.tok[i] = 32'hDEADBEEF; dut.trk.rem[i] = 16'h7777; dut.trk.st[i] = 2'd2; end
        dut.trk.fault = 1'b1; dut.trk.o_valid = 1'b1; dut.trk.o_rv = 1'b1; dut.trk.o_res = 3'd5;
        dut.gate.armed = 1'b1; dut.gate.fault = 1'b1; dut.gate.s1_v = 1'b1; dut.gate.o_valid = 1'b1; dut.gate.phase = 2'd3;
        for (int i = 0; i < 4; i++) begin dut.gate.notl[i] = 34'h12345; dut.gate.tok[i] = 8'd9; for (int j = 0; j < 4; j++) begin dut.gate.pos[i][j] = 18'd77; dut.gate.ob[i][j] = 16'd88; dut.gate.os[i][j] = 16'd99; end end
    end
`endif
    always @(posedge clk) if (run) begin
        $display("C %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d", cyc, ord_ready, cr_ready, d_valid, d_valid ? d_res : 5'd0, d_valid ? d_tok : 32'd0, c_valid, c_valid ? c_res : 3'd0, rk_valid, rk_valid ? rk_kind : 2'd0, rk_valid ? rk_res : 4'd0,
            rk_valid ? rk_pos : 18'sd0, rk_valid ? rk_ob : 16'd0, rk_valid ? rk_os : 16'd0, rk_valid ? rk_not : 34'd0, rk_valid ? rk_tok : 8'd0, t_live, t_fault, st_o);
        cyc++;
    end
    initial begin
        $readmemh("out/sys_stim.hex", vec);
        repeat (3) @(negedge clk); rst = 0;
        for (k = 0; k < NC; k++) begin
            ord_valid = vec[k][0]; ord_tok = vec[k][32:1]; ord_acct = vec[k][36:33]; ord_sym = vec[k][40:37]; ord_side = vec[k][41]; ord_px = vec[k][57:42]; ord_qty = vec[k][73:58];
            cr_valid = vec[k][74]; cr_tok = vec[k][106:75]; r_valid = vec[k][107]; r_kind = vec[k][109:108]; r_tok = vec[k][141:110]; r_qty = vec[k][157:142];
            cfg_a_valid = vec[k][158]; cfg_a_idx = vec[k][162:159]; cfg_maxlong = vec[k][178:163]; cfg_maxshort = vec[k][194:179]; cfg_maxqty = vec[k][210:195]; cfg_maxonot = vec[k][242:211]; cfg_maxnot = vec[k][276:243]; cfg_cap = vec[k][284:277];
            cfg_b_valid = vec[k][285]; cfg_b_idx = vec[k][289:286]; cfg_lo = vec[k][305:290]; cfg_hi = vec[k][321:306]; ctl_arm = vec[k][322]; ctl_disarm = vec[k][323]; ext_kill = vec[k][324];
            run = 1; @(negedge clk);
        end
        ord_valid = 0; cr_valid = 0; r_valid = 0; cfg_a_valid = 0; cfg_b_valid = 0; ctl_arm = 0; ctl_disarm = 0; ext_kill = 0; repeat (4) @(negedge clk); $finish;
    end
endmodule
