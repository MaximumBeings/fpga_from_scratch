// Chapter 8 testbench for mac_rx alone: replays out/mac_stream.hex (one line per PHY cycle: dv er byte) and prints each frame the MAC reports as `FRAME <hex bytes> <bad>`; tools/ch08_run.py compares the list with the specification model. Defines: NC (cycles).
`timescale 1ns/1ps
`ifndef NC
`define NC 1000
`endif
module mac_rx_tb;
    localparam int NC = `NC;
    logic clk = 0, rst = 1, rx_dv = 0, rx_er = 0; logic [7:0] rxd = '0; logic m_valid, m_last, m_bad; logic [7:0] m_data; logic [15:0] vec [0:NC-1]; int k, n = 0, nframes = 0; logic [7:0] buffer [0:2047];
    mac_rx dut (.clk(clk), .rst(rst), .rx_dv(rx_dv), .rx_er(rx_er), .rxd(rxd), .m_valid(m_valid), .m_data(m_data), .m_last(m_last), .m_bad(m_bad));
    always #4 clk = ~clk;
    always @(posedge clk) if (m_valid) begin
        buffer[n] = m_data; n++;
        if (m_last) begin
            $write("FRAME "); for (int i = 0; i < n; i++) $write("%02x", buffer[i]); $display(" %0d", m_bad); n = 0; nframes++;
        end
    end
    initial begin
        $readmemh("out/mac_stream.hex", vec);
        repeat (3) @(negedge clk); rst = 0;
        for (k = 0; k < NC; k++) begin @(negedge clk); rx_dv = vec[k][8+4]; rx_er = vec[k][8]; rxd = vec[k][7:0]; end
        repeat (10) @(negedge clk); $display("DONE %0d frames", nframes); $finish;
    end
endmodule
