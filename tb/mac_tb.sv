// Chapter 5 testbench for fx_mac: per-cycle stimulus (en, clr, a, b) and the expected 40-bit accumulator and rounded 16-bit output from the golden model, compared every cycle. Defines: RND SAT NC.
`timescale 1ns/1ps
`ifndef RND
`define RND 1
`endif
`ifndef SAT
`define SAT 1
`endif
`ifndef NC
`define NC 3000
`endif
module mac_tb;
    localparam int NC = `NC;
    logic clk = 0, rst = 1, en = 0, clr = 0; logic signed [15:0] a = '0, b = '0, y; logic signed [39:0] acc; logic [95:0] vec [0:NC-1]; int errs = 0, k;
    fx_mac #(.RND(`RND), .SAT(`SAT)) dut (.clk(clk), .rst(rst), .en(en), .clr(clr), .a(a), .b(b), .acc(acc), .y(y));
    always #5 clk = ~clk;
    initial begin
        $readmemh("out/mac_vec.hex", vec);
        repeat (3) @(negedge clk); rst = 0;
        for (k = 0; k < NC; k++) begin
            @(negedge clk); en = vec[k][92]; clr = vec[k][88]; a = vec[k][87:72]; b = vec[k][71:56]; #1;
            if (acc !== vec[k][55:16] || y !== vec[k][15:0]) begin errs++; if (errs < 6) $display("MISMATCH cycle %0d: acc %0d/%0d y %0d/%0d", k, acc, $signed(vec[k][55:16]), y, $signed(vec[k][15:0])); end
        end
        if (errs == 0) $display("PASS: %0d cycles, RND=%0d SAT=%0d", NC, `RND, `SAT); else $display("FAIL: %0d problems", errs);
        $finish;
    end
endmodule
