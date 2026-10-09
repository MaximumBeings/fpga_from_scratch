// Chapter 7 testbench for crc32_stream: replays out/crc_vec.hex (made by model/crc_gold.py from zlib.crc32, not from the RTL). Each line: valid last nbytes data | out_valid out_good out_crc. Compared every cycle. Defines: W (8, 16, 32, 64), NC (cycles), FAST (0 = crc32_stream, latency 1; 1 = crc32_fast, latency 5: the vector file must have been made with the same latency).
`timescale 1ns/1ps
`ifndef W
`define W 64
`endif
`ifndef FAST
`define FAST 0
`endif
`ifndef NC
`define NC 2000
`endif
module crc_tb;
    localparam int W = `W, NC = `NC, DH = W / 4, LW = 4 * (3 + DH + 2 + 8);
    logic clk = 0, rst = 1, in_valid = 0, in_last = 0; logic [W-1:0] in_data = '0; logic [3:0] in_nbytes = '0; logic out_valid, out_good; logic [31:0] out_crc;
    logic [127:0] vec [0:NC-1]; int errs = 0, k, frames = 0;
    if (`FAST) begin : g1 crc32_fast #(.W(W)) dut (.clk(clk), .rst(rst), .in_valid(in_valid), .in_data(in_data), .in_nbytes(in_nbytes), .in_last(in_last), .out_valid(out_valid), .out_good(out_good), .out_crc(out_crc)); end
    else begin : g0 crc32_stream #(.W(W)) dut (.clk(clk), .rst(rst), .in_valid(in_valid), .in_data(in_data), .in_nbytes(in_nbytes), .in_last(in_last), .out_valid(out_valid), .out_good(out_good), .out_crc(out_crc)); end
    always #5 clk = ~clk;
    initial begin
        $readmemh("out/crc_vec.hex", vec);
        in_valid = 1; in_last = 1; in_nbytes = 4'd1; in_data = '1;                  // valid input during reset: reset must discard it
        repeat (2) @(negedge clk); rst = 0; in_valid = 0; in_last = 0; in_nbytes = '0;
        for (k = 0; k < NC; k++) begin
            @(negedge clk);
            // line layout, from the right: out_crc 8 hex, out_good 1, out_valid 1, data DH hex, nbytes 1, last 1, valid 1
            in_valid = vec[k][4*(DH+8+2+2)]; in_last = vec[k][4*(DH+8+2+1)]; in_nbytes = vec[k][4*(DH+8+2) +: 4]; in_data = vec[k][4*(8+2) +: W]; #1;
            if (out_valid !== vec[k][4*9] || (vec[k][4*9] && (out_good !== vec[k][4*8] || out_crc !== vec[k][31:0]))) begin
                errs++; if (errs < 5) $display("MISMATCH cycle %0d: valid %b/%b good %b/%b crc %h/%h", k, out_valid, vec[k][4*9], out_good, vec[k][4*8], out_crc, vec[k][31:0]);
            end
            if (out_valid === 1'b1) frames++;
        end
        if (errs == 0) $display("PASS: W=%0d FAST=%0d, %0d cycles, %0d frames checked against zlib.crc32", W, `FAST, NC, frames); else $display("FAIL: W=%0d FAST=%0d, %0d mismatches", W, `FAST, errs);
        $finish;
    end
endmodule
