// Chapter 5 testbench for the two FIR forms: a random Q1.15 input stream against the golden model's output, every cycle. Defines: FORM (0 direct, 1 transposed), COHEX (the 128-bit coefficient vector), NC, RND, SAT.
`timescale 1ns/1ps
`ifndef FORM
`define FORM 0
`endif
`ifndef NC
`define NC 3000
`endif
`ifndef RND
`define RND 1
`endif
`ifndef SAT
`define SAT 1
`endif
module fir_tb;
    localparam int NC = `NC; localparam logic [127:0] CO = 128'h`COHEX;
    logic clk = 0, rst = 1; logic signed [15:0] x = '0, y; logic [31:0] vec [0:NC-1]; int errs = 0, k;
    if (`FORM == 0) begin : g0 fir_direct #(.CO(CO), .RND(`RND), .SAT(`SAT)) dut (.clk(clk), .rst(rst), .x(x), .y(y)); end
    else begin : g1 fir_transposed #(.CO(CO), .RND(`RND), .SAT(`SAT)) dut (.clk(clk), .rst(rst), .x(x), .y(y)); end
    always #5 clk = ~clk;
    initial begin
        $readmemh("out/fir_vec.hex", vec);
        x = 16'h7fff; repeat (3) @(negedge clk); rst = 0; x = 0;                   // the input is nonzero during reset: reset must discard it
        for (k = 0; k < NC; k++) begin
            @(negedge clk); x = vec[k][31:16]; #1;
            if (y !== vec[k][15:0]) begin errs++; if (errs < 6) $display("MISMATCH cycle %0d: y %0d expected %0d", k, y, $signed(vec[k][15:0])); end
        end
        if (errs == 0) begin if (`FORM) $display("PASS: transposed FIR, %0d cycles, RND=%0d SAT=%0d", NC, `RND, `SAT); else $display("PASS: direct FIR, %0d cycles, RND=%0d SAT=%0d", NC, `RND, `SAT); end else $display("FAIL: %0d problems", errs);
        $finish;
    end
endmodule
