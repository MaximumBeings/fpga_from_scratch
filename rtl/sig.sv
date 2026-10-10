// Chapter 22: the signal unit. From the top of book (bid price and shares, ask price and shares) to mid (in half ticks), spread, the bid's share of the quantity at the touch w, the imbalance and the microprice, in fixed point, bit for bit as model/sig_gold.py says. One division (F restoring steps, then a rounding), one multiplication, one addition. DIV = 1: a pipelined divider, one message per cycle; DIV = 0: one shared divider step, busy for F + 3 cycles after it accepts a message. Both answer in cycle a + F + 4 for a message accepted in cycle a.
module sig #(parameter int PW = 24, parameter int QW = 20, parameter int F = 12, parameter int DIV = 1) (
    input  logic clk, input logic rst,
    input  logic in_valid, input logic [PW-1:0] in_bpx, input logic [QW-1:0] in_bsh, input logic [PW-1:0] in_apx, input logic [QW-1:0] in_ash,
    output logic in_ready,
    output logic o_valid, output logic o_ok, output logic [PW:0] o_mid2, output logic signed [PW:0] o_spread, output logic o_cross, output logic o_lock,
    output logic [F:0] o_w, output logic signed [F+1:0] o_imb, output logic [PW+F-1:0] o_micro);
    // ---- stage 0, the message: both sides present, the total quantity, the spread, the mid in half ticks
    wire        x_ok  = (in_bsh != '0) && (in_ash != '0);
    wire [QW:0] x_d   = {1'b0, in_bsh} + {1'b0, in_ash};
    wire signed [PW:0] x_s = $signed({1'b0, in_apx}) - $signed({1'b0, in_bpx});
    wire [PW:0] x_m2  = {1'b0, in_apx} + {1'b0, in_bpx};
    // ---- the divider: r starts as the bid's shares, F steps of "double, subtract the total if it fits" give the F fraction bits t of Qb / D and a remainder
    logic d_v, d_ok; logic [QW:0] d_r, d_d; logic [F-1:0] d_t; logic signed [PW:0] d_s; logic [PW:0] d_m2; logic [PW-1:0] d_pb;
    function automatic logic [QW:0] rem_next(input logic [QW:0] r, input logic [QW:0] d);          // the remainder after one step
        logic [QW+1:0] r2; r2 = {r, 1'b0}; rem_next = (r2 >= {1'b0, d}) ? (QW + 1)'(r2 - {1'b0, d}) : r2[QW:0];
    endfunction
    function automatic logic bit_next(input logic [QW:0] r, input logic [QW:0] d);                 // the quotient bit of that step
        logic [QW+1:0] r2; r2 = {r, 1'b0}; bit_next = (r2 >= {1'b0, d});
    endfunction
    if (DIV == 1) begin : pipe
        logic v [0:F]; logic ok [0:F]; logic [QW:0] r [0:F]; logic [QW:0] dd [0:F]; logic [F-1:0] t [0:F]; logic signed [PW:0] s [0:F]; logic [PW:0] m2 [0:F]; logic [PW-1:0] pb [0:F];
        always_ff @(posedge clk) begin
            v[0] <= in_valid; ok[0] <= x_ok; r[0] <= {1'b0, in_bsh}; dd[0] <= x_d; t[0] <= '0; s[0] <= x_s; m2[0] <= x_m2; pb[0] <= in_bpx;
            for (int i = 0; i < F; i++) begin
                v[i+1] <= v[i] && !rst; ok[i+1] <= ok[i]; dd[i+1] <= dd[i]; s[i+1] <= s[i]; m2[i+1] <= m2[i]; pb[i+1] <= pb[i];
                r[i+1] <= rem_next(r[i], dd[i]); t[i+1] <= {t[i][F-2:0], bit_next(r[i], dd[i])};
            end
        end
        assign d_v = v[F]; assign d_ok = ok[F]; assign d_r = r[F]; assign d_d = dd[F]; assign d_t = t[F]; assign d_s = s[F]; assign d_m2 = m2[F]; assign d_pb = pb[F];
        assign in_ready = 1'b1;
    end else begin : seq
        localparam int CW = $clog2(F + 4); localparam logic [CW-1:0] FC = CW'(F); logic busy; logic [CW-1:0] cnt;
        always_ff @(posedge clk) begin
            d_v <= 1'b0;
            if (rst) busy <= 1'b0;
            else if (!busy) begin
                if (in_valid) begin busy <= 1'b1; cnt <= '0; d_ok <= x_ok; d_r <= {1'b0, in_bsh}; d_d <= x_d; d_t <= '0; d_s <= x_s; d_m2 <= x_m2; d_pb <= in_bpx; end
            end else begin
                d_r <= rem_next(d_r, d_d); d_t <= {d_t[F-2:0], bit_next(d_r, d_d)};       // steps every busy cycle: the F-th result is taken by the next stage in the cycle the extra steps start
                if (cnt == FC - 1'b1) d_v <= 1'b1;
                cnt <= cnt + 1'b1; if (cnt == FC + CW'(2)) busy <= 1'b0;
            end
        end
        assign in_ready = !busy;
    end
    // ---- stage A: the rounding (w = t + (2 r >= D)) and the imbalance 2 w - 2^F
    logic a_v, a_ok; logic [F:0] a_w; logic signed [F+1:0] a_imb; logic signed [PW:0] a_s; logic [PW:0] a_m2; logic [PW-1:0] a_pb;
    wire [F:0] w_n = {1'b0, d_t} + {{F{1'b0}}, ({d_r, 1'b0} >= {1'b0, d_d})};
    wire [F+1:0] imb_n = {w_n, 1'b0} - {1'b0, 1'b1, {F{1'b0}}};                                       // 2 w - 2^F, in F + 2 bits (two's complement)
    always_ff @(posedge clk) begin
        a_v <= d_v && !rst; a_ok <= d_ok; a_w <= w_n; a_imb <= imb_n; a_s <= d_s; a_m2 <= d_m2; a_pb <= d_pb;
    end
    // ---- stage B: the product spread x w (signed x unsigned)
    logic b_v, b_ok; logic [F:0] b_w; logic signed [F+1:0] b_imb; logic signed [PW:0] b_s; logic [PW:0] b_m2; logic [PW-1:0] b_pb; logic [PW+F-1:0] b_prod;
    always_ff @(posedge clk) begin
        b_v <= a_v && !rst; b_ok <= a_ok; b_w <= a_w; b_imb <= a_imb; b_s <= a_s; b_m2 <= a_m2; b_pb <= a_pb;
        b_prod <= (PW + F)'(a_s * $signed({1'b0, a_w}));                                        // modulo 2^(PW+F): the value is in range, so the low bits are the answer
    end
    // ---- stage C: micro = Pb 2^F + spread w, and the outputs (all 0 when a side has no shares)
    wire [PW+F-1:0] micro_n = {b_pb, {F{1'b0}}} + b_prod;
    always_ff @(posedge clk) begin
        o_valid <= b_v; o_ok <= b_ok;
        o_mid2 <= b_ok ? b_m2 : '0; o_spread <= b_ok ? b_s : '0; o_cross <= b_ok && b_s[PW]; o_lock <= b_ok && (b_s == '0);
        o_w <= b_ok ? b_w : '0; o_imb <= b_ok ? b_imb : '0; o_micro <= b_ok ? micro_n : '0;
    end
endmodule
// sig_syn: the same design behind a handful of pins, ONLY so that it fits a chip for the place-and-route runs: the message is shifted in serially, the outputs are registered and folded into one 16-bit word.
module sig_syn #(parameter int PW = 24, parameter int QW = 20, parameter int F = 12, parameter int DIV = 1) (input logic clk, input logic rst, input logic si, input logic sh, output logic [15:0] info);
    logic [PW+QW+PW+QW:0] iv; logic ready, ov_, ok_, cr, lk; logic [PW:0] m2; logic signed [PW:0] sp; logic [F:0] w; logic signed [F+1:0] im; logic [PW+F-1:0] mi;
    always_ff @(posedge clk) if (sh) iv <= {iv[PW+QW+PW+QW-1:0], si};
    sig #(.PW(PW), .QW(QW), .F(F), .DIV(DIV)) u (.clk(clk), .rst(rst), .in_valid(iv[PW+QW+PW+QW]), .in_bpx(iv[PW+QW+PW+QW-1 -: PW]), .in_bsh(iv[QW+PW+QW-1 -: QW]), .in_apx(iv[PW+QW-1 -: PW]), .in_ash(iv[QW-1:0]), .in_ready(ready),
        .o_valid(ov_), .o_ok(ok_), .o_mid2(m2), .o_spread(sp), .o_cross(cr), .o_lock(lk), .o_w(w), .o_imb(im), .o_micro(mi));
    logic [15:0] x, r1; always_comb x = 16'(m2) ^ 16'(sp) ^ 16'(w) ^ 16'(im) ^ mi[15:0] ^ 16'(mi >> 16) ^ {11'd0, ready, ov_, ok_, cr, lk};
    always_ff @(posedge clk) begin r1 <= x; info <= r1; end
endmodule
