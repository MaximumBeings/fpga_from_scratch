// Chapter 25 testbench for track: line k of out/life_stim.hex (32 hex digits) is everything on the pins in cycle k, cycle 0 being the first cycle after reset: the local event of the requester (held on the pins until accepted: model/life_gold.py run() decides which cycle) bits 0..74, the exchange's report bits 75..125. Before every clock edge it prints
//   C <cycle> <ready> <answer valid> <source> <result> <release valid> <type> <account> <symbol> <side> <price> <quantity> <live> <fault>     (zeros where nothing is valid)
`timescale 1ns/1ps
`ifndef NC
`define NC 1000
`endif
`ifndef NT
`define NT 4
`endif
module life_tb;
    localparam int NC = `NC, NT = `NT;
    logic clk = 0, rst = 1; logic [127:0] vec [0:NC-1]; int k, cyc = 0; logic run = 0;
    logic l_valid = 0, l_kind = 0, l_side = 0, r_valid = 0; logic [31:0] l_tok = '0, r_tok = '0; logic [3:0] l_acct = '0, l_sym = '0; logic [15:0] l_px = '0, l_qty = '0, r_qty = '0; logic [1:0] r_kind = '0;
    logic ready, o_valid, o_src, o_rv, o_rside, o_fault; logic [2:0] o_res; logic [1:0] o_rtype; logic [3:0] o_racct, o_rsym; logic [15:0] o_rpx, o_rqty; logic [$clog2(NT+1)-1:0] o_live;
    track #(.NT(NT), .PW(16), .QW(16)) dut (.clk(clk), .rst(rst), .l_valid(l_valid), .l_kind(l_kind), .l_tok(l_tok), .l_acct(l_acct), .l_sym(l_sym), .l_side(l_side), .l_px(l_px), .l_qty(l_qty), .ready(ready),
        .r_valid(r_valid), .r_kind(r_kind), .r_tok(r_tok), .r_qty(r_qty), .o_valid(o_valid), .o_src(o_src), .o_res(o_res), .o_rv(o_rv), .o_rtype(o_rtype), .o_racct(o_racct), .o_rsym(o_rsym), .o_rside(o_rside), .o_rpx(o_rpx), .o_rqty(o_rqty), .o_live(o_live), .o_fault(o_fault));
    always #4 clk = ~clk;
`ifdef GARBAGE
    initial begin   // Icarus only: every register powers up with garbage, so that a reset that forgets one is seen
        for (int i = 0; i < NT; i++) begin dut.used[i] = 1'b1; dut.tok[i] = 32'hDEADBEEF; dut.acct[i] = 4'd9; dut.sym[i] = 4'd9; dut.side[i] = 1'b1; dut.px[i] = 16'h5555; dut.rem[i] = 16'h7777; dut.st[i] = 2'd2; end
        dut.fault = 1'b1; dut.o_valid = 1'b1; dut.o_src = 1'b1; dut.o_res = 3'd5; dut.o_rv = 1'b1; dut.o_rtype = 2'd3; dut.o_racct = 4'd7; dut.o_rsym = 4'd7; dut.o_rside = 1'b1; dut.o_rpx = 16'h1234; dut.o_rqty = 16'h4321;
    end
`endif
    always @(posedge clk) if (run) begin
        $display("C %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d", cyc, ready, o_valid, o_valid ? o_src : 1'b0, o_valid ? o_res : 3'd0, o_rv, o_rv ? o_rtype : 2'd0, o_rv ? o_racct : 4'd0, o_rv ? o_rsym : 4'd0, o_rv ? o_rside : 1'b0, o_rv ? o_rpx : 16'd0, o_rv ? o_rqty : 16'd0, o_live, o_fault);
        cyc++;
    end
    initial begin
        $readmemh("out/life_stim.hex", vec);
        repeat (3) @(negedge clk); rst = 0;
        for (k = 0; k < NC; k++) begin
            l_valid = vec[k][0]; l_kind = vec[k][1]; l_tok = vec[k][33:2]; l_acct = vec[k][37:34]; l_sym = vec[k][41:38]; l_side = vec[k][42]; l_px = vec[k][58:43]; l_qty = vec[k][74:59];
            r_valid = vec[k][75]; r_kind = vec[k][77:76]; r_tok = vec[k][109:78]; r_qty = vec[k][125:110];
            run = 1; @(negedge clk);
        end
        l_valid = 0; r_valid = 0; repeat (4) @(negedge clk); $finish;
    end
endmodule
