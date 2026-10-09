// Chapter 1: a registered adder in two styles. radd uses "+": the synthesis tool may use the FPGA's dedicated carry chain.
// radd_lut builds the carry by hand from gates, so the tool can only use ordinary lookup tables. Same function, same ports.
module radd #(parameter W = 16) (input clk, input [W-1:0] a, input [W-1:0] b, output reg [W:0] s);
    reg [W-1:0] ra, rb;
    always @(posedge clk) begin ra <= a; rb <= b; s <= ra + rb; end
endmodule
module radd_lut #(parameter W = 16) (input clk, input [W-1:0] a, input [W-1:0] b, output reg [W:0] s);
    reg [W-1:0] ra, rb; wire [W:0] c; wire [W:0] sum; assign c[0] = 1'b0;
    genvar i;
    generate for (i = 0; i < W; i = i + 1) begin : fa
        assign sum[i] = ra[i] ^ rb[i] ^ c[i];
        assign c[i+1] = (ra[i] & rb[i]) | (c[i] & (ra[i] ^ rb[i]));
    end endgenerate
    assign sum[W] = c[W];
    always @(posedge clk) begin ra <= a; rb <= b; s <= sum; end
endmodule
