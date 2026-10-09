// Chapter 3: the one property that makes Gray code safe to cross, as a combinational assertion for Yosys to prove for ALL counter values: stepping the counter by one changes exactly one bit of the code that crosses. MODE = 1 checks the Gray code, MODE = 0 checks plain binary (which fails: the proof returns a counterexample).
module gray_prop #(parameter int W = 4, parameter int MODE = 1) (input logic [W-1:0] b);
    logic [W-1:0] c0, c1, d; logic [W-1:0] b1;
    assign b1 = b + 1'b1;
    assign c0 = MODE == 1 ? (b ^ (b >> 1)) : b;
    assign c1 = MODE == 1 ? (b1 ^ (b1 >> 1)) : b1;
    assign d = c0 ^ c1;
    always_comb assert (d != '0 && (d & (d - 1'b1)) == '0);     // exactly one bit differs: d is nonzero and a power of two
endmodule
