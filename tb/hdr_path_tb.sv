// Chapter 9 testbench for hdr_path (mac_rx -> hdr_filter -> frame_fifo, one clock): replays out/mac_stream.hex (one line per PHY cycle: dv er byte), a consumer that takes a byte with probability RDY percent per cycle; prints `FRAME <hex> 0` for every frame delivered, `STATS ok bad ovf` and `CNT` (frames per cause 0..7). Defines: NC, AW, RDY, and the CFG_* of hdr_tb.
`timescale 1ns/1ps
`ifndef NC
`define NC 1000
`endif
`ifndef AW
`define AW 11
`endif
`ifndef RDY
`define RDY 100
`endif
`ifndef CFG_IP_EN
`define CFG_IP_EN 1
`endif
`ifndef CFG_IP
`define CFG_IP 32'hC0A8010A
`endif
`ifndef CFG_VID_EN
`define CFG_VID_EN 0
`endif
`ifndef CFG_VID
`define CFG_VID 12'd100
`endif
`ifndef CFG_PLO
`define CFG_PLO 16'd5000
`endif
`ifndef CFG_PHI
`define CFG_PHI 16'd5999
`endif
module hdr_path_tb;
    localparam int NC = `NC;
    logic clk = 0, rst = 1, rx_dv = 0, rx_er = 0; logic [7:0] rxd = '0; logic o_valid, o_last, o_ready = 0; logic [7:0] o_data; logic [15:0] n_ok, n_bad, n_ovf; logic [127:0] cnt;
    logic [15:0] vec [0:NC-1]; int k, n = 0, nframes = 0; logic [7:0] buffer [0:2047]; logic [31:0] rng = 32'h13572468;
    hdr_path #(.AW(`AW)) dut (.clk(clk), .rst(rst), .rx_dv(rx_dv), .rx_er(rx_er), .rxd(rxd), .cfg_ip_en(1'(`CFG_IP_EN)), .cfg_ip(`CFG_IP), .cfg_vid_en(1'(`CFG_VID_EN)), .cfg_vid(`CFG_VID), .cfg_plo(`CFG_PLO), .cfg_phi(`CFG_PHI),
        .o_valid(o_valid), .o_data(o_data), .o_last(o_last), .o_ready(o_ready), .n_ok(n_ok), .n_bad(n_bad), .n_ovf(n_ovf), .cnt(cnt));
    always #4 clk = ~clk;
    always @(posedge clk) begin
        if (o_valid && o_ready) begin buffer[n] = o_data; n++; if (o_last) begin $write("FRAME "); for (int i = 0; i < n; i++) $write("%02x", buffer[i]); $display(" 0"); n = 0; nframes++; end end
        rng = rng ^ (rng << 13); rng = rng ^ (rng >> 17); rng = rng ^ (rng << 5); #1 o_ready = ((rng % 100) < `RDY);
    end
    initial begin
        $readmemh("out/mac_stream.hex", vec);
        repeat (3) @(negedge clk); rst = 0;
        for (k = 0; k < NC; k++) begin @(negedge clk); rx_dv = vec[k][8+4]; rx_er = vec[k][8]; rxd = vec[k][7:0]; end
        rx_dv = 0; rx_er = 0; repeat (3000) @(negedge clk);
        $display("STATS %0d %0d %0d", n_ok, n_bad, n_ovf);
        $display("CNT %0d %0d %0d %0d %0d %0d %0d %0d", cnt[15:0], cnt[31:16], cnt[47:32], cnt[63:48], cnt[79:64], cnt[95:80], cnt[111:96], cnt[127:112]);
        $display("DONE %0d frames", nframes); $finish;
    end
endmodule
