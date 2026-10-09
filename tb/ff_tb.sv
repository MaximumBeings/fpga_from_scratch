// Chapter 8 unit testbench for frame_fifo alone: byte stream from out/ff_stim.hex (one line per cycle: valid last bad data), AW (buffer size is 2^AW bytes, so only 2^AW - 1 can be held), a reader that takes a byte with probability RDY percent per cycle. Prints `FRAME <hex> 0` for each frame delivered and `STATS ok bad ovf`. Defines: NC, AW, RDY.
`timescale 1ns/1ps
`ifndef NC
`define NC 1000
`endif
`ifndef AW
`define AW 4
`endif
`ifndef RDY
`define RDY 100
`endif
module ff_tb;
    localparam int NC = `NC;
    logic clk = 0, rst = 1, in_valid = 0, in_last = 0, in_bad = 0, in_ready, out_valid, out_last, out_ready = 0; logic [7:0] in_data = '0, out_data; logic [15:0] n_ok, n_bad, n_ovf;
    logic [19:0] vec [0:NC-1]; int k, n = 0, nframes = 0; logic [7:0] buffer [0:4095]; logic [31:0] rng = 32'h5eed1234;
    frame_fifo #(.AW(`AW)) dut (.clk(clk), .rst(rst), .in_valid(in_valid), .in_data(in_data), .in_last(in_last), .in_bad(in_bad), .in_ready(in_ready),
        .out_valid(out_valid), .out_data(out_data), .out_last(out_last), .out_ready(out_ready), .n_ok(n_ok), .n_bad(n_bad), .n_ovf(n_ovf));
    always #5 clk = ~clk;
    always @(posedge clk) begin
        if (out_valid && out_ready) begin buffer[n] = out_data; n++; if (out_last) begin $write("FRAME "); for (int i = 0; i < n; i++) $write("%02x", buffer[i]); $display(" 0"); n = 0; nframes++; end end
        rng = rng ^ (rng << 13); rng = rng ^ (rng >> 17); rng = rng ^ (rng << 5); #1 out_ready = ((rng % 100) < `RDY);
    end
    initial begin
        $readmemh("out/ff_stim.hex", vec);
        in_valid = 1; in_last = 1; in_data = 8'hEE; repeat (2) @(negedge clk); rst = 0; in_valid = 0; in_last = 0;         // valid input during reset: reset must discard it
        for (k = 0; k < NC; k++) begin @(negedge clk); in_valid = vec[k][16+0]; in_last = vec[k][12+0]; in_bad = vec[k][8+0]; in_data = vec[k][7:0]; end
        repeat (200) @(negedge clk); $display("STATS %0d %0d %0d", n_ok, n_bad, n_ovf); $display("DONE %0d frames", nframes); $finish;
    end
endmodule
