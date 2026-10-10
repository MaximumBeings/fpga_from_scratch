// Chapter 23 testbench for risk: line k of out/risk_stim.hex (56 hex digits) is everything offered in cycle k, cycle 0 being the first cycle after reset: event bits 0..43 (valid, type, account, symbol, side, price, quantity), account configuration 44..176 (valid, index, max long, max short, max quantity, max order notional, max notional, bucket size), symbol band 177..213 (valid, index, low, high), control 214..216 (arm, disarm, kill); fields not offered are junk. Before every clock edge it prints
//   C <cycle> <o_valid> <kind> <result> <pos> <open buy> <open sell> <notional> <tokens>     (zeros when o_valid = 0; pos signed)
`timescale 1ns/1ps
`ifndef NC
`define NC 1000
`endif
`ifndef NA
`define NA 4
`endif
`ifndef NS
`define NS 4
`endif
`ifndef QW
`define QW 16
`endif
`ifndef PW
`define PW 16
`endif
`ifndef R
`define R 4
`endif
module risk_tb;
    localparam int NC = `NC, QW = `QW, PW = `PW, TW = 8;
    logic clk = 0, rst = 1; logic [223:0] vec [0:NC-1]; int k, cyc = 0; logic run = 0;
    logic ev_valid = 0, ev_side = 0, cfg_a_valid = 0, cfg_b_valid = 0, ctl_arm = 0, ctl_disarm = 0, kill = 0; logic [1:0] ev_type = '0; logic [3:0] ev_acct = '0, ev_sym = '0, cfg_a_idx = '0, cfg_b_idx = '0;
    logic [PW-1:0] ev_px = '0, cfg_lo = '0, cfg_hi = '0; logic [QW-1:0] ev_qty = '0, cfg_maxlong = '0, cfg_maxshort = '0, cfg_maxqty = '0; logic [PW+QW-1:0] cfg_maxonot = '0; logic [PW+QW+1:0] cfg_maxnot = '0; logic [TW-1:0] cfg_cap = '0;
    logic o_valid; logic [1:0] o_kind; logic [3:0] o_res; logic signed [QW+1:0] o_pos; logic [QW-1:0] o_ob, o_os; logic [PW+QW+1:0] o_not; logic [TW-1:0] o_tok;
    risk #(.NA(`NA), .NS(`NS), .QW(QW), .PW(PW), .R(`R), .TW(TW)) dut (.clk(clk), .rst(rst), .ev_valid(ev_valid), .ev_type(ev_type), .ev_acct(ev_acct), .ev_sym(ev_sym), .ev_side(ev_side), .ev_px(ev_px), .ev_qty(ev_qty),
        .cfg_a_valid(cfg_a_valid), .cfg_a_idx(cfg_a_idx), .cfg_maxlong(cfg_maxlong), .cfg_maxshort(cfg_maxshort), .cfg_maxqty(cfg_maxqty), .cfg_maxonot(cfg_maxonot), .cfg_maxnot(cfg_maxnot), .cfg_cap(cfg_cap),
        .cfg_b_valid(cfg_b_valid), .cfg_b_idx(cfg_b_idx), .cfg_lo(cfg_lo), .cfg_hi(cfg_hi), .ctl_arm(ctl_arm), .ctl_disarm(ctl_disarm), .kill(kill),
        .o_valid(o_valid), .o_kind(o_kind), .o_res(o_res), .o_pos(o_pos), .o_ob(o_ob), .o_os(o_os), .o_not(o_not), .o_tok(o_tok));
    always #4 clk = ~clk;
`ifdef GARBAGE
    initial begin   // Icarus only: every register of the gate powers up with garbage, so that a reset that forgets one is seen
        dut.armed = 1'b1; dut.fault = 1'b1; dut.phase = `R - 1;
        for (int i = 0; i < `NA; i++) begin dut.c_long[i] = 7; dut.c_short[i] = 7; dut.c_qty[i] = 7; dut.c_onot[i] = 7; dut.c_not[i] = 7; dut.c_cap[i] = 3; dut.notl[i] = 5; dut.tok[i] = 3; for (int j = 0; j < `NS; j++) begin dut.pos[i][j] = 2; dut.ob[i][j] = 1; dut.os[i][j] = 1; end end
        for (int j = 0; j < `NS; j++) begin dut.b_lo[j] = 0; dut.b_hi[j] = '1; end
    end
`endif
    longint pos_p;
    always @(posedge clk) if (run) begin
        pos_p = o_valid ? longint'(o_pos) : 0;
        $display("C %0d %0d %0d %0d %0d %0d %0d %0d %0d", cyc, o_valid, o_valid ? o_kind : 2'd0, o_valid ? o_res : 4'd0, pos_p, o_valid ? o_ob : '0, o_valid ? o_os : '0, o_valid ? o_not : '0, o_valid ? o_tok : '0);
        cyc++;
    end
    initial begin
        $readmemh("out/risk_stim.hex", vec);
        repeat (3) @(negedge clk); rst = 0;
        for (k = 0; k < NC; k++) begin
            ev_valid = vec[k][0]; ev_type = vec[k][2:1]; ev_acct = vec[k][6:3]; ev_sym = vec[k][10:7]; ev_side = vec[k][11]; ev_px = vec[k][12 +: PW]; ev_qty = vec[k][28 +: QW];
            cfg_a_valid = vec[k][44]; cfg_a_idx = vec[k][48:45]; cfg_maxlong = vec[k][49 +: QW]; cfg_maxshort = vec[k][65 +: QW]; cfg_maxqty = vec[k][81 +: QW]; cfg_maxonot = vec[k][97 +: PW+QW]; cfg_maxnot = vec[k][129 +: PW+QW+2]; cfg_cap = vec[k][169 +: TW];
            cfg_b_valid = vec[k][177]; cfg_b_idx = vec[k][181:178]; cfg_lo = vec[k][182 +: PW]; cfg_hi = vec[k][198 +: PW]; ctl_arm = vec[k][214]; ctl_disarm = vec[k][215]; kill = vec[k][216];
            run = 1; @(negedge clk);
        end
        ev_valid = 0; cfg_a_valid = 0; cfg_b_valid = 0; ctl_arm = 0; ctl_disarm = 0; kill = 0; repeat (6) @(negedge clk); $finish;
    end
endmodule
