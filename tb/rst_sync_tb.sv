// Chapter 3 testbench for cdc_rst_sync. 40 trials; trial k releases the asynchronous reset OFFSET_k ps after a clock edge (offsets sweep the whole 10 ns period) and counts the clock edges until rst_n is high; it also asserts the reset in the MIDDLE of a clock period and checks that rst_n falls at once, with no clock edge. Prints one line per trial: REL <offset ps> <edges>. tools/cdc_model.py predicts every line.
`timescale 1ps/1ps
module rst_sync_tb;
    localparam int P = 10000;
    logic clk = 0, arst_n = 0, rst_n; int edges, k, bad_assert = 0, bad_hold = 0;
    cdc_rst_sync dut (.clk(clk), .arst_n(arst_n), .rst_n(rst_n));
    always #(P / 2) clk = ~clk;
    initial begin
        repeat (3) @(posedge clk);
        for (k = 0; k < 40; k++) begin
            // assert mid-period: rst_n must go low within 1 ps, with no clock edge in between
            @(posedge clk); #(P / 3); arst_n = 0; #1; if (rst_n !== 1'b0) bad_assert++;
            repeat (3) @(posedge clk); if (rst_n !== 1'b0) bad_hold++;      // held low through clock edges while the reset is asserted
            @(posedge clk); #(k * (P / 40) + 7);                              // offset after an edge: 7, 257, 507, ... ps
            arst_n = 1; edges = 0;
            while (rst_n !== 1'b1) begin @(posedge clk); #1; edges++; end
            $display("REL %0d %0d", k * (P / 40) + 7, edges);
        end
        $display("ASSERT_CHECKS bad_assert %0d bad_hold %0d", bad_assert, bad_hold); $finish;
    end
endmodule
