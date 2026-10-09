// Chapter 8 testbench for mac_rx_path: two unrelated clocks (RXP and COREP, in ps), a stream from out/mac_stream.hex on the PHY clock, a consumer on the core clock that takes a byte with probability RDY percent per cycle. Prints `FRAME <hex> 0` for every frame delivered and `STATS ok bad ovf lost` at the end. Defines: NC, RXP, COREP, AW, CAW, RDY.
`timescale 1ps/1ps
`ifndef NC
`define NC 1000
`endif
`ifndef RXP
`define RXP 8000
`endif
`ifndef COREP
`define COREP 6400
`endif
`ifndef AW
`define AW 11
`endif
`ifndef CAW
`define CAW 4
`endif
`ifndef RDY
`define RDY 100
`endif
module mac_path_tb;
    localparam int NC = `NC;
    logic rx_clk = 0, core_clk = 0, rx_rst_n = 0, core_rst_n = 0, rx_dv = 0, rx_er = 0; logic [7:0] rxd = '0; logic o_valid, o_last, o_ready = 0; logic [7:0] o_data;
    logic [15:0] n_ok, n_bad, n_ovf, n_lost; logic [15:0] vec [0:NC-1]; int k, n = 0, nframes = 0; logic [7:0] buffer [0:2047]; logic [31:0] rng = 32'h2468ace1;
    mac_rx_path #(.AW(`AW), .CAW(`CAW)) dut (.rx_clk(rx_clk), .rx_rst_n(rx_rst_n), .rx_dv(rx_dv), .rx_er(rx_er), .rxd(rxd), .core_clk(core_clk), .core_rst_n(core_rst_n),
        .o_valid(o_valid), .o_data(o_data), .o_last(o_last), .o_ready(o_ready), .n_ok(n_ok), .n_bad(n_bad), .n_ovf(n_ovf), .n_lost(n_lost));
    always #(`RXP / 2) rx_clk = ~rx_clk;
    initial begin #777; forever #(`COREP / 2) core_clk = ~core_clk; end
    always @(posedge core_clk) begin
        if (o_valid && o_ready) begin
            buffer[n] = o_data; n++;
            if (o_last) begin $write("FRAME "); for (int i = 0; i < n; i++) $write("%02x", buffer[i]); $display(" 0"); n = 0; nframes++; end
        end
        rng = rng ^ (rng << 13); rng = rng ^ (rng >> 17); rng = rng ^ (rng << 5); #100 o_ready = ((rng % 100) < `RDY);
    end
    initial begin
        $readmemh("out/mac_stream.hex", vec);
        repeat (4) @(negedge rx_clk); rx_rst_n = 1; repeat (4) @(negedge core_clk); core_rst_n = 1;
        for (k = 0; k < NC; k++) begin @(negedge rx_clk); rx_dv = vec[k][12]; rx_er = vec[k][8]; rxd = vec[k][7:0]; end
        repeat (4000) @(negedge core_clk);
        $display("STATS %0d %0d %0d %0d", n_ok, n_bad, n_ovf, n_lost); $display("DONE %0d frames", nframes); $finish;
    end
endmodule
