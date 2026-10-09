// Chapter 6 testbench for sfifo: vector replay. Each line of out/fifo_vec.hex has the inputs for one cycle (wr, rd, data) and the golden model's outputs (rd_data, full, empty, count) as they must be BEFORE the clock edge. rd_data is compared only when the FIFO is not empty. Defines: BUG, NC, VEC (the vector file, default out/fifo_vec.hex). Prints PASS or the first mismatches.
`timescale 1ns/1ps
`ifndef BUG
`define BUG 0
`endif
`ifndef VEC
`define VEC "out/fifo_vec.hex"
`endif
`ifndef NC
`define NC 2000
`endif
module sfifo_tb;
    localparam int NC = `NC;
    logic clk = 0, rst = 1, wr_en = 0, rd_en = 0; logic [7:0] wr_data = '0, rd_data; logic full, empty; logic [2:0] count; logic [39:0] vec [0:NC-1]; int errs = 0, k;
    sfifo #(.W(8), .DEPTH(6), .BUG(`BUG)) dut (.clk(clk), .rst(rst), .wr_en(wr_en), .wr_data(wr_data), .rd_en(rd_en), .rd_data(rd_data), .full(full), .empty(empty), .count(count));
    always #5 clk = ~clk;
    initial begin
        $readmemh(`VEC, vec);
        repeat (2) @(negedge clk); rst = 0;
        for (k = 0; k < NC; k++) begin
            @(negedge clk); wr_en = vec[k][32]; rd_en = vec[k][28]; wr_data = vec[k][27:20]; #1;
            // bit positions: wr 32, rd 28, data 27:20, rd_data 19:12, full 8, empty 4, count 2:0
            if (full !== vec[k][8] || empty !== vec[k][4] || count !== vec[k][2:0] || (!vec[k][4] && rd_data !== vec[k][19:12])) begin
                errs++; if (errs < 4) $display("MISMATCH cycle %0d: full %b/%b empty %b/%b count %0d/%0d rd_data %h/%h", k, full, vec[k][8], empty, vec[k][4], count, vec[k][2:0], rd_data, vec[k][19:12]);
            end
        end
        if (errs == 0) $display("PASS: BUG=%0d, %0d cycles", `BUG, NC); else $display("FAIL: BUG=%0d, %0d mismatches", `BUG, errs);
        $finish;
    end
endmodule
