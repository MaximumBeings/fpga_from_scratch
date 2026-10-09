// Chapter 3: a register, D levels of logic, a register. Every level is one 4-input function per bit (x ^ (a & b) ^ c), so a level is one LUT4 and the logic depth is D LUTs.
module tchain #(parameter int D = 4, parameter int W = 16) (input logic clk, input logic [W-1:0] din, output logic [W-1:0] dout);
    logic [W-1:0] x [D + 1];
    always_ff @(posedge clk) x[0] <= din;
    for (genvar k = 0; k < D; k++) begin : lvl
        for (genvar j = 0; j < W; j++) begin : bit_
            assign x[k + 1][j] = x[k][j] ^ (x[k][(j + 1) % W] & x[k][(j + 3) % W]) ^ x[k][(j + 7) % W];
        end
    end
    always_ff @(posedge clk) dout <= x[D];
endmodule
