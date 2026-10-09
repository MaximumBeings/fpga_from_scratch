// Chapter 4: two packet filters with the same specification and opposite latency.
// Packets are streams of 32-bit beats (in_valid, in_data, in_last). A packet is DROPPED unless the low byte of its first beat is 0xA5; a kept packet is BAD if the sum of the low 16 bits of all its beats is not 0 (mod 65536), GOOD otherwise.
// ct_filter (cut-through): forwards each beat one clock later. The drop decision needs only the first beat, so it is made at once; the checksum needs the whole packet, so a kept packet is forwarded speculatively and out_bad is raised on its LAST beat if the sum is wrong. A downstream stage must discard a packet whose last beat has out_bad. Latency: 1 cycle for every beat of every packet.
// sf_filter (store-and-forward): stores the whole packet, decides at the last beat, and streams only GOOD packets out, one beat per cycle. It never emits a bad packet. in_ready is low while a packet drains (one buffer). Latency: grows with packet length.
// verilator lint_off DECLFILENAME
module ct_filter (
    input logic clk, input logic rst, input logic in_valid, input logic [31:0] in_data, input logic in_last,
    output logic out_valid, output logic [31:0] out_data, output logic out_last, output logic out_bad);
    logic inpkt, keep; logic [15:0] acc;
    logic first, keep_n; logic [15:0] acc_n;
    assign first = !inpkt;
    assign keep_n = first ? (in_data[7:0] == 8'hA5) : keep;
    assign acc_n = (first ? 16'd0 : acc) + in_data[15:0];
    always_ff @(posedge clk) begin
        if (rst) begin out_valid <= 1'b0; out_last <= 1'b0; out_bad <= 1'b0; inpkt <= 1'b0; keep <= 1'b0; acc <= 16'd0; out_data <= 32'd0; end
        else if (!in_valid) begin out_valid <= 1'b0; out_last <= 1'b0; out_bad <= 1'b0; end
        else begin
            out_valid <= keep_n; out_data <= in_data; out_last <= in_last; out_bad <= in_last && keep_n && (acc_n != 16'd0);
            inpkt <= !in_last; keep <= keep_n; acc <= acc_n;
        end
    end
endmodule
module sf_filter #(parameter int DEPTH = 32) (
    input logic clk, input logic rst, input logic in_valid, input logic [31:0] in_data, input logic in_last, output logic in_ready,
    output logic out_valid, output logic [31:0] out_data, output logic out_last, output logic out_bad);
    localparam int AW = $clog2(DEPTH);
    logic [31:0] buffer [DEPTH]; logic [AW:0] n, rd, total; logic [15:0] acc; logic drain; logic [7:0] first_lo;
    logic [15:0] acc_n; logic good;
    assign in_ready = !drain;
    assign out_bad = 1'b0;
    assign acc_n = acc + in_data[15:0];
    assign good = (((n == '0) ? in_data[7:0] : first_lo) == 8'hA5) && (acc_n == 16'd0);
    always_ff @(posedge clk) begin
        if (rst) begin n <= '0; rd <= '0; total <= '0; acc <= 16'd0; drain <= 1'b0; out_valid <= 1'b0; out_last <= 1'b0; out_data <= 32'd0; first_lo <= 8'd0; end
        else if (drain) begin
            out_valid <= 1'b1; out_data <= buffer[rd[AW-1:0]]; out_last <= (rd == total - 1'b1); rd <= rd + 1'b1;
            if (rd == total - 1'b1) begin drain <= 1'b0; n <= '0; acc <= 16'd0; end
        end else begin
            out_valid <= 1'b0; out_last <= 1'b0;
            if (in_valid) begin
                buffer[n[AW-1:0]] <= in_data; if (n == '0) first_lo <= in_data[7:0]; acc <= acc_n;
                if (in_last) begin
                    if (good) begin drain <= 1'b1; rd <= '0; total <= n + 1'b1; n <= n + 1'b1; end
                    else begin n <= '0; acc <= 16'd0; end
                end else n <= n + 1'b1;
            end
        end
    end
endmodule
