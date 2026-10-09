// Chapter 7: a formal proof that the generated K-byte update equals K applications of the generated 1-byte update, for EVERY register value and EVERY data word (32 + 8K free input bits). Yosys treats the inputs as free; the assertion is combinational. K is a parameter (1 to 8).
module crc_equiv #(parameter int K = 2) (input logic [31:0] c, input logic [63:0] d);
    logic [31:0] wide, s [9];
    crc32_comb u_wide (.c(c), .d(d), .k(4'(K)), .n(wide));
    assign s[0] = c;
    for (genvar b = 0; b < K; b++) begin : bytes
        crc32_comb u (.c(s[b]), .d({56'd0, d[8*b +: 8]}), .k(4'd1), .n(s[b + 1]));
    end
    always_comb assert (wide == s[K]);
endmodule
