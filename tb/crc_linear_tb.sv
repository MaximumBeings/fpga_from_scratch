// Chapter 7: equivalence of the 64-bit-per-beat update and eight 1-byte updates on a BASIS. Both circuits are built only from XOR and NOT gates (checked in tools/ch07_run.py by counting the gate types Yosys maps them to), hence affine over GF(2); this testbench also checks that the all-zero input gives zero for both, so the constant term is zero and they are linear, and a function equal on the 96 unit inputs and on zero is equal on all 2^96 inputs: f(x ^ y) = f(x) ^ f(y).
`timescale 1ns/1ps
module crc_linear_tb;
    logic [31:0] c, wide, s [9]; logic [63:0] d; int errs = 0, i, j;
    crc32_comb u_wide (.c(c), .d(d), .k(4'd8), .n(wide));
    assign s[0] = c;
    for (genvar b = 0; b < 8; b++) begin : bytes
        crc32_comb u (.c(s[b]), .d({56'd0, d[8*b +: 8]}), .k(4'd1), .n(s[b + 1]));
    end
    initial begin
        c = 0; d = 0; #1; if (wide !== s[8] || wide !== 32'd0) errs++;
        for (i = 0; i < 96; i++) begin
            c = 0; d = 0; if (i < 32) c[i] = 1'b1; else d[i - 32] = 1'b1; #1;
            if (wide !== s[8]) begin errs++; $display("MISMATCH on basis vector %0d: %h %h", i, wide, s[8]); end
        end
        if (errs == 0) $display("PASS: the 8-byte update equals eight 1-byte updates on all 97 basis inputs (hence on all 2^96 inputs, the circuits being linear)"); else $display("FAIL: %0d", errs);
        $finish;
    end
endmodule
