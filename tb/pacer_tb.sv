// Chapter 11 testbench for the pacer alone: replays out/pacer_stim.hex (per cycle: request, length in wire bytes) and prints `G <cycle> <len>` for every cycle in which the pacer grants. Defines: NC, RATE, BL, COMB (1 = the first, combinational pacer).
`timescale 1ns/1ps
`ifndef NC
`define NC 1000
`endif
`ifndef RATE
`define RATE 64
`endif
`ifndef BL
`define BL 12
`endif
`ifndef COMB
`define COMB 0
`endif
module pacer_tb;
    localparam int NC = `NC;
    logic clk = 0, rst = 1, req = 0, go; logic [10:0] len = '0; logic [15:0] vec [0:NC-1]; int k;
    if (`COMB) begin : gc
        pacer_comb #(.BURST(1 << `BL)) dut (.clk(clk), .rst(rst), .rate(9'(`RATE)), .req(req), .len(len), .go(go));
    end else begin : gp
        pacer #(.BL(`BL)) dut (.clk(clk), .rst(rst), .rate(9'(`RATE)), .req(req), .len(len), .go(go));
    end
    always #4 clk = ~clk;
    initial begin
        $readmemh("out/pacer_stim.hex", vec); req = 1; len = 11'd1538; repeat (3) @(negedge clk); rst = 0;
        for (k = 0; k < NC; k++) begin req = vec[k][12]; len = vec[k][10:0]; #1; if (go) $display("G %0d %0d", k, len); @(negedge clk); end
        $display("DONE"); $finish;
    end
endmodule
