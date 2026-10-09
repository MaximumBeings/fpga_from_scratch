// Chapter 4 testbench for pipe: a random valid/data stream against the golden model, cycle by cycle (valid is held high during reset, which must discard it). Every output must appear exactly S + 1 cycles after its input, carry the function of that input, and the valid bit must be low in every other cycle. Defines: S (stages), NC (cycles).
`timescale 1ns/1ps
`ifndef S
`define S 3
`endif
`ifndef NC
`define NC 2000
`endif
module pipe_tb;
    localparam int NC = `NC;
    logic clk = 0, rst = 1, in_valid = 0; logic [15:0] in_data = '0; logic out_valid; logic [15:0] out_data; logic [39:0] vec [0:NC-1]; int errs = 0, k, got = 0;
    pipe #(.W(16), .R(12), .S(`S)) dut (.clk(clk), .rst(rst), .in_valid(in_valid), .in_data(in_data), .out_valid(out_valid), .out_data(out_data));
    always #5 clk = ~clk;
    initial begin
        $readmemh("out/pipe_vec.hex", vec);
        in_valid = 1; in_data = 16'hBEEF;                           // the input is VALID during reset: reset must discard it
        repeat (3) @(negedge clk); rst = 0; in_valid = 0;
        for (k = 0; k < NC; k = k + 1) begin
            @(negedge clk); in_valid = vec[k][36]; in_data = vec[k][35:20]; #1;
            if (out_valid !== vec[k][16] || (vec[k][16] && out_data !== vec[k][15:0])) begin errs++; if (errs < 6) $display("MISMATCH cycle %0d: valid %b/%b data %h/%h", k, out_valid, vec[k][16], out_data, vec[k][15:0]); end
            if (out_valid === 1'b1) got++;
        end
        if (errs == 0) $display("PASS: S = %0d, %0d cycles, %0d outputs, each exactly S + 1 cycles after its input", `S, NC, got); else $display("FAIL: %0d problems", errs);
        $finish;
    end
endmodule
