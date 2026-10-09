// Chapter 9 testbench for hdr_filter (or the module named by the define DUT): replays out/hdr_stim.hex (one line per cycle: valid last bad data) and prints, for each frame that leaves the filter, `FRAME <hex> <bad>` and `RES cause ntags vid sip dip sport dport ulen`; at the end `STATS` (frames per cause), `LAT` (cycles from the first byte in to the first byte out) and `CYC`. Defines: NC (cycles), and the configuration CFG_IP_EN, CFG_IP, CFG_VID_EN, CFG_VID, CFG_PLO, CFG_PHI.
`timescale 1ns/1ps
`ifndef NC
`define NC 1000
`endif
`ifndef DUT
`define DUT hdr_filter
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
module hdr_tb;
    localparam int NC = `NC;
    logic clk = 0, rst = 1, s_valid = 0, s_last = 0, s_bad = 0; logic [7:0] s_data = '0;
    logic m_valid, m_last, m_bad; logic [7:0] m_data; logic [2:0] m_cause; logic [1:0] m_ntags; logic [11:0] m_vid; logic [31:0] m_sip, m_dip; logic [15:0] m_sport, m_dport, m_ulen; logic [127:0] cnt;
    logic [19:0] vec [0:NC-1]; int k, n = 0, nframes = 0, first_in = -1, first_out = -1, cyc = 0; logic [7:0] buffer [0:4095];
    `DUT dut (.clk(clk), .rst(rst), .s_valid(s_valid), .s_data(s_data), .s_last(s_last), .s_bad(s_bad), .cfg_ip_en(1'(`CFG_IP_EN)), .cfg_ip(`CFG_IP), .cfg_vid_en(1'(`CFG_VID_EN)), .cfg_vid(`CFG_VID), .cfg_plo(`CFG_PLO), .cfg_phi(`CFG_PHI),
        .m_valid(m_valid), .m_data(m_data), .m_last(m_last), .m_bad(m_bad), .m_cause(m_cause), .m_ntags(m_ntags), .m_vid(m_vid), .m_sip(m_sip), .m_dip(m_dip), .m_sport(m_sport), .m_dport(m_dport), .m_ulen(m_ulen), .cnt(cnt));
    always #4 clk = ~clk;
    always @(posedge clk) begin
        cyc <= cyc + 1;
        if (s_valid && first_in < 0 && !rst) first_in <= cyc;
        if (m_valid) begin
            if (first_out < 0) first_out = cyc;
            buffer[n] = m_data; n++;
            if (m_last) begin
                $write("FRAME "); for (int i = 0; i < n; i++) $write("%02x", buffer[i]); $display(" %0d", m_bad);
                $display("RES %0d %0d %0d %0d %0d %0d %0d %0d", m_cause, m_ntags, m_vid, m_sip, m_dip, m_sport, m_dport, m_ulen); n = 0; nframes++;
            end
        end
    end
    initial begin
        $readmemh("out/hdr_stim.hex", vec);
        s_valid = 1; s_last = 1; s_data = 8'hEE; repeat (2) @(negedge clk); rst = 0; s_valid = 0; s_last = 0;        // valid input during reset: reset must discard it
        for (k = 0; k < NC; k++) begin @(negedge clk); s_valid = vec[k][16]; s_last = vec[k][12]; s_bad = vec[k][8]; s_data = vec[k][7:0]; end
        @(negedge clk); s_valid = 0; s_last = 0;
        repeat (10) @(negedge clk); $display("STATS %0d %0d %0d %0d %0d %0d %0d %0d", cnt[15:0], cnt[31:16], cnt[47:32], cnt[63:48], cnt[79:64], cnt[95:80], cnt[111:96], cnt[127:112]);
        $display("LAT %0d", first_out - first_in); $display("CYC %0d", NC); $display("DONE %0d frames", nframes); $finish;
    end
endmodule
