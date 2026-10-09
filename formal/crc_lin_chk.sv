// Chapter 7: wrapper that fixes k, so that the case on k folds away and what remains is the XOR network of one stepK function (used by ch07_run.py to count gate types).
module crc_lin_chk #(parameter int K = 8) (input logic [31:0] c, input logic [63:0] d, output logic [31:0] n);
    crc32_comb u (.c(c), .d(d), .k(4'(K)), .n(n));
endmodule
