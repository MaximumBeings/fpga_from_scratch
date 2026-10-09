// Chapter 5: a registered signed multiplier, for measuring what a multiplier costs. Operands registered, product registered: latency 2.
module mulreg #(parameter int W = 16) (input logic clk, input logic signed [W-1:0] a, input logic signed [W-1:0] b, output logic signed [2*W-1:0] p);
    logic signed [W-1:0] ra, rb;
    always_ff @(posedge clk) begin ra <= a; rb <= b; p <= ra * rb; end
endmodule
