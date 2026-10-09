// Chapter 1 testbench: both adders (radd uses "+", radd_lut a hand-built carry) against the golden vectors, in any simulator.
// The vector file holds one word per line: {expected sum, b, a}. Inputs change at the falling clock edge and the sum of vector k is checked two falling edges later (two register stages).
`timescale 1ns/1ps
`ifndef WIDTH
`define WIDTH 16
`endif
`ifndef NVEC
`define NVEC 100
`endif
module radd_tb;
    localparam W = `WIDTH, N = `NVEC;
    reg clk = 0; reg [W-1:0] a = 0, b = 0; wire [W:0] s1, s2; reg [3*W:0] mem [0:N-1]; integer k, errs = 0;
    radd #(W) d1 (.clk(clk), .a(a), .b(b), .s(s1)); radd_lut #(W) d2 (.clk(clk), .a(a), .b(b), .s(s2));
    always #5 clk = ~clk;
    initial begin
        $readmemh("out/radd_vec.hex", mem);
        for (k = 0; k < N + 2; k = k + 1) begin
            @(negedge clk);
            if (k >= 2) begin
                if (s1 !== mem[k-2][3*W:2*W]) begin errs = errs + 1; if (errs < 5) $display("MISMATCH radd vector %0d: got %h want %h", k-2, s1, mem[k-2][3*W:2*W]); end
                if (s2 !== mem[k-2][3*W:2*W]) begin errs = errs + 1; if (errs < 5) $display("MISMATCH radd_lut vector %0d: got %h want %h", k-2, s2, mem[k-2][3*W:2*W]); end
            end
            if (k < N) begin a = mem[k][W-1:0]; b = mem[k][2*W-1:W]; end
        end
        if (errs == 0) $display("PASS: %0d vectors, W = %0d, both adders match the golden sums", N, W); else $display("FAIL: %0d mismatches", errs);
        $finish;
    end
endmodule
