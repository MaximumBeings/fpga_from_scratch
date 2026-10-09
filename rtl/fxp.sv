// verilator lint_off DECLFILENAME
// Chapter 5: fixed-point building blocks.
// Q1.15 operands: a signed 16-bit value x means x / 2^15. A product of two Q1.15 numbers is Q2.30 (32 bits); a sum of products needs guard bits (the accumulator is 40 bits: eight bits of headroom, 256 products at full scale); the result is brought back to Q1.15 by shifting right 15 places.
// fx_round_sat: a signed IW-bit value, scaled down by 2^SH to an OW-bit signed result. RND = 0 truncates (floor: rounds toward minus infinity), RND = 1 rounds half up (adds half an output step first). SAT = 1 clamps to the largest/smallest OW-bit value; SAT = 0 wraps (keeps the low bits), which is the cheap option and a silent disaster on overflow.
module fx_round_sat #(parameter int IW = 40, parameter int OW = 16, parameter int SH = 15, parameter int RND = 1, parameter int SAT = 1) (
    input logic signed [IW-1:0] x, output logic signed [OW-1:0] y);
    localparam int EW = IW + 1;                                        // one extra bit so that adding the rounding constant cannot overflow
    localparam logic signed [EW-1:0] HALF = (RND != 0 && SH > 0) ? (EW'(1) <<< (SH - 1)) : EW'(0);
    localparam logic signed [EW-1:0] MAXV = (EW'(1) <<< (OW - 1)) - EW'(1);
    localparam logic signed [EW-1:0] MINV = -(EW'(1) <<< (OW - 1));
    logic signed [EW-1:0] r, s;
    always_comb begin
        r = EW'(x) + HALF;
        s = r >>> SH;
        if (SAT != 0) begin
            if (s > MAXV) y = MAXV[OW-1:0];
            else if (s < MINV) y = MINV[OW-1:0];
            else y = s[OW-1:0];
        end else y = s[OW-1:0];
    end
endmodule
// fx_mac: a three-stage multiply-accumulate. Stage 1 registers the operands, stage 2 the product, stage 3 the accumulator. clr starts a new sum (acc := product if en, else 0); en adds the product to the sum. acc is the full 40-bit sum; y is acc rounded and saturated to Q1.15.
module fx_mac #(parameter int RND = 1, parameter int SAT = 1) (
    input logic clk, input logic rst, input logic en, input logic clr, input logic signed [15:0] a, input logic signed [15:0] b,
    output logic signed [39:0] acc, output logic signed [15:0] y);
    logic signed [15:0] ra, rb; logic ren, rclr, pen, pclr; logic signed [31:0] p;
    always_ff @(posedge clk) begin
        if (rst) begin ra <= '0; rb <= '0; ren <= 1'b0; rclr <= 1'b0; p <= '0; pen <= 1'b0; pclr <= 1'b0; acc <= '0; end
        else begin
            ra <= a; rb <= b; ren <= en; rclr <= clr;
            p <= ra * rb; pen <= ren; pclr <= rclr;
            if (pclr) acc <= pen ? 40'(p) : 40'sd0;
            else if (pen) acc <= acc + 40'(p);
        end
    end
    fx_round_sat #(.IW(40), .OW(16), .SH(15), .RND(RND), .SAT(SAT)) rs (.x(acc), .y(y));
endmodule
