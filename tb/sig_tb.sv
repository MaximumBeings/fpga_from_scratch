// Chapter 22 testbench for sig: line k of out/sig_stim.hex (34 hex digits) is the message OFFERED in cycle k: valid(1), bid price, bid shares, ask price, ask shares (32 bits each, junk where valid = 0); the offer is held on the pins whether or not the unit is ready: model/sig_gold.py run() decides which cycle's offer is accepted. Before every clock edge it prints
//   C <cycle> <in_ready> <o_valid> <ok> <mid2> <spread> <cross> <lock> <w> <imbalance> <microprice>     (zeros when o_valid = 0; spread and imbalance signed)
`timescale 1ns/1ps
`ifndef NC
`define NC 1000
`endif
`ifndef PW
`define PW 24
`endif
`ifndef QW
`define QW 20
`endif
`ifndef F
`define F 12
`endif
`ifndef DIV
`define DIV 1
`endif
module sig_tb;
    localparam int NC = `NC, PW = `PW, QW = `QW, F = `F;
    logic clk = 0, rst = 1, in_valid = 0; logic [PW-1:0] in_bpx = '0, in_apx = '0; logic [QW-1:0] in_bsh = '0, in_ash = '0; logic [128:0] vec [0:NC-1]; int k, cyc = 0; logic run = 0;
    logic in_ready, o_valid, o_ok, o_cross, o_lock; logic [PW:0] o_mid2; logic signed [PW:0] o_spread; logic [F:0] o_w; logic signed [F+1:0] o_imb; logic [PW+F-1:0] o_micro;
    sig #(.PW(PW), .QW(QW), .F(F), .DIV(`DIV)) dut (.clk(clk), .rst(rst), .in_valid(in_valid), .in_bpx(in_bpx), .in_bsh(in_bsh), .in_apx(in_apx), .in_ash(in_ash), .in_ready(in_ready),
        .o_valid(o_valid), .o_ok(o_ok), .o_mid2(o_mid2), .o_spread(o_spread), .o_cross(o_cross), .o_lock(o_lock), .o_w(o_w), .o_imb(o_imb), .o_micro(o_micro));
    always #4 clk = ~clk;
    longint sp_p, im_p;
    always @(posedge clk) if (run) begin
        sp_p = o_valid ? longint'(o_spread) : 0; im_p = o_valid ? longint'(o_imb) : 0;
        $display("C %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d", cyc, in_ready, o_valid, o_valid ? o_ok : 1'b0, o_valid ? o_mid2 : '0, sp_p, o_valid ? o_cross : 1'b0, o_valid ? o_lock : 1'b0, o_valid ? o_w : '0, im_p, o_valid ? o_micro : '0);
        cyc++;
    end
    initial begin
        $readmemh("out/sig_stim.hex", vec);
        repeat (3) @(negedge clk); rst = 0;
        for (k = 0; k < NC; k++) begin
            in_valid = vec[k][128]; in_bpx = vec[k][96 +: PW]; in_bsh = vec[k][64 +: QW]; in_apx = vec[k][32 +: PW]; in_ash = vec[k][0 +: QW]; run = 1; @(negedge clk);
        end
        in_valid = 0; repeat (F + 8) @(negedge clk); $finish;
    end
endmodule
