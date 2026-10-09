// Chapter 2 testbench: the three frame recognizers against the golden model, cycle by cycle, and against each other.
// The vector word is {err, done, pay_v, busy, rst, in_valid, in_byte}; the expected outputs are those visible BEFORE the clock edge of that cycle.
`timescale 1ns/1ps
`ifndef NCYC
`define NCYC 3000
`endif
module frame_tb;
    localparam int NC = `NCYC;
    logic clk = 0, rst = 1, in_valid = 0; logic [7:0] in_byte = 8'd0; logic [13:0] vec [0:NC-1]; int errs = 0, k;
    logic [3:0] oa, ob, oc;     // {busy, pay_v, done, err}
    frame_a a (.clk(clk), .rst(rst), .in_valid(in_valid), .in_byte(in_byte), .busy(oa[3]), .pay_v(oa[2]), .done(oa[1]), .err(oa[0]));
    frame_b b (.clk(clk), .rst(rst), .in_valid(in_valid), .in_byte(in_byte), .busy(ob[3]), .pay_v(ob[2]), .done(ob[1]), .err(ob[0]));
    frame_c c (.clk(clk), .rst(rst), .in_valid(in_valid), .in_byte(in_byte), .busy(oc[3]), .pay_v(oc[2]), .done(oc[1]), .err(oc[0]));
    always #5 clk = ~clk;
    int frames = 0, aborts = 0, payload = 0;
    initial begin
        $readmemh("out/frame_vec.hex", vec);
        repeat (2) @(negedge clk); rst = 0;
        for (k = 0; k < NC; k = k + 1) begin
            @(negedge clk); in_byte = vec[k][7:0]; in_valid = vec[k][8]; rst = vec[k][9]; #1;
            if (oa !== {vec[k][10], vec[k][11], vec[k][12], vec[k][13]}) begin errs = errs + 1; if (errs < 6) $display("MISMATCH frame_a cycle %0d: got %b want %b", k, oa, {vec[k][10], vec[k][11], vec[k][12], vec[k][13]}); end
            if (ob !== {vec[k][10], vec[k][11], vec[k][12], vec[k][13]}) begin errs = errs + 1; if (errs < 6) $display("MISMATCH frame_b cycle %0d: got %b want %b", k, ob, {vec[k][10], vec[k][11], vec[k][12], vec[k][13]}); end
            if (oc !== {vec[k][10], vec[k][11], vec[k][12], vec[k][13]}) begin errs = errs + 1; if (errs < 6) $display("MISMATCH frame_c cycle %0d: got %b want %b", k, oc, {vec[k][10], vec[k][11], vec[k][12], vec[k][13]}); end
            frames = frames + oa[1]; aborts = aborts + oa[0]; payload = payload + oa[2];
        end
        if (errs == 0) $display("PASS: %0d cycles, three styles agree with the golden model (%0d frames, %0d aborts, %0d payload bytes)", NC, frames, aborts, payload); else $display("FAIL: %0d problems", errs);
        $finish;
    end
endmodule
