// Chapter 27 testbench for sup and rst_gen: line k of out/sup_stim.hex (3 hex digits) is everything on the pins in cycle k: bit 0 go, 1 trip, 2 feed, 3 slot, 4 fault, 5..7 session state, 8 tx_ready, 9 quiet, 10 reset of the supervisor, 11 rst_in of the reset generator (set at the falling edge before the cycle's rising edge). Before every clock edge it prints
//   C <cycle> <state> <kill> <cq> <cause> <rst_u>
`timescale 1ns/1ps
`ifndef NC
`define NC 1000
`endif
`ifndef FT
`define FT 100
`endif
`ifndef ST
`define ST 100
`endif
`ifndef WARM
`define WARM 48
`endif
`ifndef RSTN
`define RSTN 8
`endif
module sup_tb;
    localparam int NC = `NC;
    logic clk = 0; logic [11:0] vec [0:NC-1]; int k, cyc = 0; logic run = 0;
    logic rst = 1, rst_in = 0, go = 0, trip = 0, feed = 0, slot = 0, fault = 0, tx_ready = 0, quiet = 0; logic [2:0] sess = '0;
    logic [1:0] state; logic kill, cq_valid; logic [4:0] cause; logic rst_u;
    sup #(.FT(`FT), .ST(`ST), .WARM(`WARM)) dut (.clk(clk), .rst(rst), .go(go), .trip(trip), .feed(feed), .slot(slot), .fault(fault), .sess(sess), .tx_ready(tx_ready), .quiet(quiet), .state(state), .kill(kill), .cq_valid(cq_valid), .cause(cause));
    rst_gen #(.RSTN(`RSTN)) rg (.clk(clk), .rst_in(rst_in), .rst_u(rst_u));
    always #4 clk = ~clk;
`ifdef GARBAGE
    initial begin dut.state = 2'd2; dut.cnt = '1; dut.fc = '1; dut.sc = '1; dut.sent = 1'b1; dut.cause = 5'd31; end
`endif
    always @(posedge clk) if (run) begin $display("C %0d %0d %0d %0d %0d %0d", cyc, state, kill, cq_valid, cause, rst_u); cyc++; end
    initial begin
        $readmemh("out/sup_stim.hex", vec);
        @(negedge clk);
        for (k = 0; k < NC; k++) begin
            go = vec[k][0]; trip = vec[k][1]; feed = vec[k][2]; slot = vec[k][3]; fault = vec[k][4]; sess = vec[k][7:5]; tx_ready = vec[k][8]; quiet = vec[k][9]; rst = vec[k][10]; rst_in = vec[k][11];
            run = 1; @(negedge clk);
        end
        $finish;
    end
endmodule
