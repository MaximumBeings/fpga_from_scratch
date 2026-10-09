// Chapter 9 testbench for the three checksum accumulators (module name given by the define CSUM): replays out/csum_stim.hex (one line per cycle: valid last start data, 4 hex digits) and prints `SUM <hex>` after each message's last byte. Idle cycles carry random junk. Defines: NC, CSUM.
`timescale 1ns/1ps
`ifndef NC
`define NC 1000
`endif
module csum_tb;
    localparam int NC = `NC;
    logic clk = 0, rst = 1, v = 0, start = 0; logic [7:0] d = '0; logic [15:0] sum; logic [19:0] vec [0:NC-1]; int k; logic prev_last = 0;
    `CSUM dut (.clk(clk), .rst(rst), .v(v), .start(start), .d(d), .sum(sum));
    always #4 clk = ~clk;
    initial begin
        $readmemh("out/csum_stim.hex", vec);
        repeat (2) @(negedge clk); rst = 0;
        for (k = 0; k < NC; k++) begin
            @(negedge clk); if (prev_last) $display("SUM %04x", sum);
            prev_last = vec[k][12] && vec[k][16]; v = vec[k][16]; start = vec[k][8]; d = vec[k][7:0];
        end
        @(negedge clk); if (prev_last) $display("SUM %04x", sum);
        $display("DONE"); $finish;
    end
endmodule
