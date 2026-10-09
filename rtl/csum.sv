// verilator lint_off DECLFILENAME
// verilator lint_off UNUSEDSIGNAL
// Chapter 9: three ways to accumulate the Internet checksum (RFC 1071) one byte per clock. All have the same interface: when `v` is high a byte `d` is added; `start` marks the first byte of a message (it clears the sum); `sum` is the folded 16-bit ones' complement sum (NOT inverted) of the bytes added so far, available combinationally from the registers (a lone last byte counts as the high half of a word). The sender's checksum field is ~sum; a received message is correct when sum == 16'hFFFF.
//   csum_e2e : a 16-bit register; every word is added with its carry folded back IN THE SAME CYCLE (two adders in a row).
//   csum_def : a 17-bit register; the carry is kept in bit 16 and added in the NEXT addition (one adder with a carry-in); folded once at the end. This is the form hdr_filter uses.
//   csum_lane: two lane accumulators (the bytes at even and at odd positions) of 20 bits each; no 16-bit word is ever formed during the stream; the lanes are combined and folded once, at the end.
module csum_e2e (input logic clk, input logic rst, input logic v, input logic start, input logic [7:0] d, output logic [15:0] sum);
    logic [15:0] acc; logic [7:0] hold; logic odd; logic [16:0] s; logic [16:0] t;
    assign s = {1'b0, acc} + {1'b0, hold, d};
    assign t = {1'b0, s[15:0]} + {16'd0, s[16]};
    always_ff @(posedge clk) begin
        if (rst) begin acc <= 16'd0; odd <= 1'b0; hold <= 8'd0; end
        else if (v) begin
            if (start) begin acc <= 16'd0; hold <= d; odd <= 1'b1; end
            else if (odd) begin acc <= t[15:0]; odd <= 1'b0; end
            else begin hold <= d; odd <= 1'b1; end
        end
    end
    logic [16:0] f; assign f = {1'b0, acc} + {1'b0, odd ? {hold, 8'h00} : 16'd0};
    assign sum = f[15:0] + {15'd0, f[16]};
endmodule
module csum_def (input logic clk, input logic rst, input logic v, input logic start, input logic [7:0] d, output logic [15:0] sum);
    logic [16:0] acc; logic [7:0] hold; logic odd;
    always_ff @(posedge clk) begin
        if (rst) begin acc <= 17'd0; odd <= 1'b0; hold <= 8'd0; end
        else if (v) begin
            if (start) begin acc <= 17'd0; hold <= d; odd <= 1'b1; end
            else if (odd) begin acc <= {1'b0, acc[15:0]} + {16'd0, acc[16]} + {1'b0, hold, d}; odd <= 1'b0; end
            else begin hold <= d; odd <= 1'b1; end
        end
    end
    logic [16:0] a1, f1; logic [15:0] w;
    assign w = odd ? {hold, 8'h00} : 16'd0;
    assign a1 = {1'b0, acc[15:0]} + {16'd0, acc[16]} + {1'b0, w};
    assign f1 = {1'b0, a1[15:0]} + {16'd0, a1[16]};
    assign sum = f1[15:0];                                          // one fold is enough: a1 <= 0x1FF00, so folding it cannot carry again
endmodule
module csum_lane (input logic clk, input logic rst, input logic v, input logic start, input logic [7:0] d, output logic [15:0] sum);
    logic [19:0] ah, al; logic odd;
    always_ff @(posedge clk) begin
        if (rst) begin ah <= 20'd0; al <= 20'd0; odd <= 1'b0; end
        else if (v) begin
            if (start) begin ah <= {12'd0, d}; al <= 20'd0; odd <= 1'b1; end
            else if (odd) begin al <= al + {12'd0, d}; odd <= 1'b0; end
            else begin ah <= ah + {12'd0, d}; odd <= 1'b1; end
        end
    end
    logic [28:0] tt; logic [17:0] x; logic [16:0] y;
    assign tt = {1'b0, ah, 8'd0} + {9'd0, al};
    assign x = {2'b0, tt[15:0]} + {5'd0, tt[28:16]};
    assign y = {1'b0, x[15:0]} + {15'd0, x[17:16]};
    assign sum = y[15:0];                                           // y cannot carry: x <= 0x11FFE
endmodule
