// verilator lint_off DECLFILENAME
// Chapter 5: an 8-tap FIR filter in two forms with identical behaviour (latency 2, same outputs, bit for bit), to show what moving registers does to the clock.
// fir_direct: the input goes through a shift register; all eight products and their sum are formed in ONE clock period (a multiplier then an eight-input adder tree), and the sum is registered.
// fir_transposed: the input is multiplied by every coefficient at once and the products are added in a CHAIN OF REGISTERS: each clock period holds one multiplier and one adder. Same function, shorter path. (Retiming: moving registers across logic without changing what the circuit computes.)
// Coefficients are Q1.15 and packed into one parameter so that no unsupported array syntax is needed. y is the 40-bit sum rounded and saturated to Q1.15.
module fir_direct #(parameter logic [127:0] CO = 128'd0, parameter int RND = 1, parameter int SAT = 1) (
    input logic clk, input logic rst, input logic signed [15:0] x, output logic signed [15:0] y);
    logic signed [15:0] tap [8]; logic signed [39:0] sum, acc;           // tap[0] is the registered input, tap[i] the input i cycles older
    always_comb begin
        sum = '0;
        for (int i = 0; i < 8; i++) sum = sum + 40'(tap[i] * $signed(CO[i*16 +: 16]));
    end
    always_ff @(posedge clk) begin
        if (rst) begin acc <= '0; for (int i = 0; i < 8; i++) tap[i] <= '0; end
        else begin
            tap[0] <= x; for (int i = 1; i < 8; i++) tap[i] <= tap[i - 1];
            acc <= sum;
        end
    end
    fx_round_sat #(.IW(40), .OW(16), .SH(15), .RND(RND), .SAT(SAT)) rs (.x(acc), .y(y));
endmodule
module fir_transposed #(parameter logic [127:0] CO = 128'd0, parameter int RND = 1, parameter int SAT = 1) (
    input logic clk, input logic rst, input logic signed [15:0] x, output logic signed [15:0] y);
    logic signed [15:0] xr; logic signed [39:0] t [8];
    always_ff @(posedge clk) begin
        if (rst) begin xr <= '0; for (int i = 0; i < 8; i++) t[i] <= '0; end
        else begin
            xr <= x;
            t[7] <= 40'(xr * $signed(CO[7*16 +: 16]));
            for (int i = 0; i < 7; i++) t[i] <= t[i + 1] + 40'(xr * $signed(CO[i*16 +: 16]));
        end
    end
    fx_round_sat #(.IW(40), .OW(16), .SH(15), .RND(RND), .SAT(SAT)) rs (.x(t[0]), .y(y));
endmodule
