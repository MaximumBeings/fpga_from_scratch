// Chapter 4 testbench for ct_filter and sf_filter. Reads a per-cycle vector file made by model/lat_gold.py: inputs (valid, last, data) and the expected outputs of the golden model (in_ready, out_valid, out_last, out_bad, out_data), and compares every cycle. Define SF = 1 tests sf_filter, 0 ct_filter. NC = number of cycles.
`timescale 1ns/1ps
`ifndef SF
`define SF 0
`endif
`ifndef NC
`define NC 1000
`endif
module pkt_tb;
    localparam int NC = `NC;
    logic clk = 0, rst = 1, in_valid = 0, in_last = 0; logic [31:0] in_data = '0; logic in_ready, out_valid, out_last, out_bad; logic [31:0] out_data;
    logic [95:0] vec [0:NC-1];                 // each line is 22 hex digits: six flag digits (each 0 or 1), the input beat, the expected output beat
    int errs = 0, k, accepted_while_not_ready = 0;
    if (`SF) begin : g1 sf_filter dut (.clk(clk), .rst(rst), .in_valid(in_valid), .in_data(in_data), .in_last(in_last), .in_ready(in_ready), .out_valid(out_valid), .out_data(out_data), .out_last(out_last), .out_bad(out_bad)); end
    else begin : g0 ct_filter dut (.clk(clk), .rst(rst), .in_valid(in_valid), .in_data(in_data), .in_last(in_last), .out_valid(out_valid), .out_data(out_data), .out_last(out_last), .out_bad(out_bad)); assign in_ready = 1'b1; end
    always #5 clk = ~clk;
    initial begin
        $readmemh("out/pkt_vec.hex", vec);
        repeat (2) @(negedge clk); rst = 0;
        for (k = 0; k < NC; k = k + 1) begin
            @(negedge clk);
            in_valid = vec[k][84]; in_last = vec[k][80]; in_data = vec[k][63:32]; #1;
            // bit positions: valid 84, last 80, ready 76, out_valid 72, out_last 68, out_bad 64, in_data 63:32, out_data 31:0
            if (in_valid && !in_ready) accepted_while_not_ready++;
            if (in_ready !== vec[k][76] || out_valid !== vec[k][72] || out_last !== vec[k][68] || out_bad !== vec[k][64] || (vec[k][72] && out_data !== vec[k][31:0])) begin
                errs++; if (errs < 6) $display("MISMATCH cycle %0d: ready %b/%b valid %b/%b last %b/%b bad %b/%b data %h/%h", k, in_ready, vec[k][76], out_valid, vec[k][72], out_last, vec[k][68], out_bad, vec[k][64], out_data, vec[k][31:0]);
            end
        end
        if (accepted_while_not_ready != 0) begin errs++; $display("MISMATCH: %0d beats offered while not ready", accepted_while_not_ready); end
        if (errs == 0) begin if (`SF) $display("PASS: store-and-forward, %0d cycles against the golden model", NC); else $display("PASS: cut-through, %0d cycles against the golden model", NC); end else $display("FAIL: %0d problems", errs);
        $finish;
    end
endmodule
