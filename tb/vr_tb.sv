// Chapter 2 testbench for vr_chain. Three phases, in any simulator.
//  1. CYCLE-ACCURATE: the DUT against the golden model's per-cycle vector file (arbitrary valid/ready patterns; the model says what in_ready, out_valid and out_data must be in every cycle).
//  2. PROTOCOL: a compliant source (it holds its item until accepted) and a random sink; every item must come out once, in order, unchanged; a stalled output must hold its data. A xorshift generator keeps the run identical in every simulator.
//  3. THROUGHPUT AND LATENCY: valid = ready = 1 all the time; count the cycles to move 1000 items and the cycles until the first item appears.
`timescale 1ns/1ps
`ifndef WIDTH
`define WIDTH 16
`endif
`ifndef NSTAGES
`define NSTAGES 4
`endif
`ifndef STYLE
`define STYLE 2
`endif
`ifndef NCYC
`define NCYC 200
`endif
module vr_tb;
    localparam int W = `WIDTH, N = `NSTAGES, STYLE = `STYLE, NC = `NCYC;
    logic clk = 0, rst = 1, in_valid = 0, out_ready = 0; logic [W-1:0] in_data = '0; logic in_ready, out_valid; logic [W-1:0] out_data;
    logic [2*W+4:0] vec [0:NC-1]; int errs = 0; int k;
    vr_chain #(.W(W), .N(N), .STYLE(STYLE)) dut (.clk(clk), .rst(rst), .in_valid(in_valid), .in_ready(in_ready), .in_data(in_data), .out_valid(out_valid), .out_ready(out_ready), .out_data(out_data));
    always #5 clk = ~clk;
    logic [31:0] rng = 32'h1234abcd;
    function automatic logic [31:0] next_rng(input logic [31:0] x); logic [31:0] y; y = x; y = y ^ (y << 13); y = y ^ (y >> 17); y = y ^ (y << 5); return y; endfunction
    int sent, got, stall_checks, cyc; logic [W-1:0] exp_item, held_data; logic held, accepted;
    initial begin
        $readmemh("out/vr_vec.hex", vec);
        repeat (2) @(negedge clk); rst = 0;
        // ---- phase 1
        for (k = 0; k < NC; k = k + 1) begin
            @(negedge clk); in_data = vec[k][W-1:0]; in_valid = vec[k][W]; out_ready = vec[k][W+1]; #1;
            if (in_ready !== vec[k][W+2] || out_valid !== vec[k][W+3] || (vec[k][W+3] && out_data !== vec[k][2*W+3:W+4])) begin
                errs = errs + 1; if (errs < 6) $display("MISMATCH cycle %0d: in_ready %b/%b out_valid %b/%b out_data %h/%h", k, in_ready, vec[k][W+2], out_valid, vec[k][W+3], out_data, vec[k][2*W+3:W+4]);
            end
        end
        // ---- phase 2: reset, then a compliant source and a random sink
        @(negedge clk); in_valid = 0; out_ready = 0; rst = 1; repeat (2) @(negedge clk); rst = 0; sent = 0; got = 0; held = 0; stall_checks = 0; accepted = 1;
        for (cyc = 0; cyc < 3000 && got < 400; cyc = cyc + 1) begin
            @(negedge clk); rng = next_rng(rng);
            if (accepted || !in_valid) begin in_valid = (rng[3:0] < 11); in_data = sent[W-1:0] + 1'b1; end   // a source holds an offered item until the cycle in which it was accepted
            rng = next_rng(rng); out_ready = (rng[2:0] < 5); #1;
            accepted = in_valid && in_ready; if (accepted) sent = sent + 1;
            if (out_valid && out_ready) begin
                got = got + 1; if (out_data !== got[W-1:0]) begin errs = errs + 1; if (errs < 6) $display("MISMATCH item %0d: got %h", got, out_data); end
            end
            if (held) begin
                if (!out_valid || out_data !== held_data) begin errs = errs + 1; if (errs < 6) $display("MISMATCH output changed while stalled at cycle %0d", cyc); end
                stall_checks = stall_checks + 1;
            end
            held = out_valid && !out_ready; held_data = out_data;
        end
        if (got < 400) begin errs = errs + 1; $display("MISMATCH only %0d of 400 items delivered", got); end
        // ---- phase 3: throughput and latency with valid = ready = 1
        @(negedge clk); in_valid = 0; out_ready = 0; rst = 1; repeat (2) @(negedge clk); rst = 0; sent = 0; got = 0;
        out_ready = 1; in_valid = 1; cyc = 0; begin : lat int first = -1; for (cyc = 0; got < 1000; cyc = cyc + 1) begin
            @(negedge clk); in_data = sent[W-1:0] + 1'b1; #1; if (in_valid && in_ready) sent = sent + 1; if (out_valid && out_ready) begin got = got + 1; if (first < 0) first = cyc + 1; end
            if (cyc > 6000) got = 1000;
        end $display("TPUT style %0d stages %0d: 1000 items in %0d cycles; first item out after %0d cycles; stall checks %0d", STYLE, N, cyc, first, stall_checks); end
        if (errs == 0) $display("PASS: style %0d, %0d stages, W = %0d: %0d golden cycles, 400 items in order, stalled outputs held", STYLE, N, W, NC); else $display("FAIL: %0d problems", errs);
        $finish;
    end
endmodule
