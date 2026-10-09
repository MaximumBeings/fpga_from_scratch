// Chapter 4: a deep function cut into S pipeline stages. The function is R rounds of one LUT level each (the same mixing as Chapter 3's tchain): x' = x ^ (x[+1] & x[+3]) ^ x[+7], bit positions mod W.
// The input is registered first (so that every logic path starts and ends at a flip-flop, which is what a timing tool measures), and a register is placed after every R/S rounds: the logic between registers is R/S LUT levels and the latency is exactly S + 1 clock cycles. R must be a multiple of S. A valid bit travels beside the data.
module pipe #(parameter int W = 16, parameter int R = 12, parameter int S = 3) (
    input logic clk, input logic rst, input logic in_valid, input logic [W-1:0] in_data, output logic out_valid, output logic [W-1:0] out_data);
    localparam int G = R / S;                                        // rounds per stage
    function logic [W-1:0] rnd(input logic [W-1:0] x);              // (assignment to the function name, not `return`: Yosys 0.33 does not accept `return`)
        logic [W-1:0] y;
        begin
            for (int j = 0; j < W; j++) y[j] = x[j] ^ (x[(j + 1) % W] & x[(j + 3) % W]) ^ x[(j + 7) % W];
            rnd = y;
        end
    endfunction
    logic [W-1:0] qi; logic vi;                                      // the input register
    always_ff @(posedge clk) begin qi <= in_data; vi <= rst ? 1'b0 : in_valid; end
    logic [W-1:0] q [S];                                             // q[s] is the register after stage s
    logic         v [S];
    for (genvar s = 0; s < S; s++) begin : stg
        logic [W-1:0] a, t; logic av;
        assign a  = (s == 0) ? qi : q[(s == 0) ? 0 : s - 1];
        assign av = (s == 0) ? vi : v[(s == 0) ? 0 : s - 1];
        always_comb begin
            t = a;
            for (int r = 0; r < G; r++) t = rnd(t);
        end
        always_ff @(posedge clk) begin
            q[s] <= t;
            v[s] <= rst ? 1'b0 : av;
        end
    end
    assign out_data = q[S - 1]; assign out_valid = v[S - 1];
endmodule
