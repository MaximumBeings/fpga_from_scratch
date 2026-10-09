// Chapter 11 testbench for udp_tx_path: descriptors from out/udp_desc.hex (dport, dip, len) and payload bytes from out/udp_bytes.hex; two independent drivers (descriptors, payload) so that a cut-through builder can take the next descriptor while it streams a payload; the payload source offers a byte with probability SRC percent per cycle and holds it until accepted. Prints, for each frame on the wire, `WIRE <hex> 0`, `START <cycle>` and `END <cycle>` (first and last tx_en cycle), then `FIRSTIN <cycle>` (the first payload byte accepted), `FIRSTD <cycle>` (the first descriptor accepted), `STATS n_pkt n_drop underrun cycles`. Defines: MAXCYC (watchdog, default 3,000,000 cycles), NP (packets), TOT (payload bytes), CT, PACE, RATE (0..256), BL (the bucket is 2^BL bytes), SRC, MAXP, GAP (idle cycles before each descriptor, default 0).
`timescale 1ns/1ps
`ifndef NP
`define NP 10
`endif
`ifndef TOT
`define TOT 1000
`endif
`ifndef CT
`define CT 0
`endif
`ifndef PACE
`define PACE 0
`endif
`ifndef RATE
`define RATE 256
`endif
`ifndef BL
`define BL 12
`endif
`ifndef SRC
`define SRC 100
`endif
`ifndef MAXP
`define MAXP 1472
`endif
`ifndef MAXCYC
`define MAXCYC 3000000
`endif
`ifndef GAP
`define GAP 0
`endif
module udp_tb;
    localparam int NP = `NP, TOT = `TOT;
    logic clk = 0, rst = 1, d_valid = 0, s_valid = 0, s_last = 0, d_ready, s_ready, tx_en, underrun; logic [10:0] d_len = '0; logic [15:0] d_dport = '0, n_pkt, n_drop; logic [31:0] d_dip = '0; logic [7:0] s_data = '0, txd;
    logic [63:0] desc [0:NP-1]; logic [7:0] bytes [0:TOT]; int dn = 0, bn = 0, pi = 0, bi = 0, gapc = 0, wn = 0, nframes = 0, cyc = 0, first_in = -1, first_d = -1, fstart = 0; logic [7:0] wbuf [0:2047]; logic [31:0] rng = 32'h2468ace1;
    udp_tx_path #(.CT(`CT), .PACE(`PACE), .MAXP(`MAXP), .BL(`BL)) dut (.clk(clk), .rst(rst), .cfg_dmac(48'hAABBCCDDEEFF), .cfg_smac(48'h021122334455), .cfg_sip(32'h0A000001), .cfg_sport(16'h1234), .rate(9'(`RATE)),
        .d_valid(d_valid), .d_len(d_len), .d_dport(d_dport), .d_dip(d_dip), .d_ready(d_ready), .s_valid(s_valid), .s_data(s_data), .s_last(s_last), .s_ready(s_ready), .tx_en(tx_en), .txd(txd), .underrun(underrun), .n_pkt(n_pkt), .n_drop(n_drop));
    always #4 clk = ~clk;
    always @(posedge clk) begin
        cyc <= cyc + 1; if (cyc > `MAXCYC) begin $display("TIMEOUT"); $finish; end             // a design that deadlocks must not hang the test
        if (s_valid && s_ready && first_in < 0) first_in <= cyc;
        if (d_valid && d_ready && first_d < 0) first_d <= cyc;
        if (tx_en) begin if (wn == 0) fstart = cyc; wbuf[wn] = txd; wn++; end
        else if (wn > 0) begin $write("WIRE "); for (int i = 0; i < wn; i++) $write("%02x", wbuf[i]); $display(" 0"); $display("START %0d", fstart); $display("END %0d", cyc - 1); wn = 0; nframes++; end
    end
    always @(posedge clk) if (!rst) begin                                          // descriptor driver
        if (!d_valid || d_ready) begin
            if (dn < NP && gapc >= `GAP) begin d_valid <= 1'b1; d_dport <= desc[dn][63:48]; d_dip <= desc[dn][47:16]; d_len <= desc[dn][10:0]; dn <= dn + 1; gapc <= 0; end
            else begin d_valid <= 1'b0; gapc <= gapc + 1; end
        end
    end
    always @(posedge clk) if (!rst) begin                                          // payload driver
        rng = rng ^ (rng << 13); rng = rng ^ (rng >> 17); rng = rng ^ (rng << 5);
        if (s_valid && s_ready) begin if (bi == int'(desc[pi][15:0]) - 1) begin pi <= pi + 1; bi <= 0; end else bi <= bi + 1; bn <= bn + 1; end
        if (!s_valid || s_ready) begin
            if ((bn + ((s_valid && s_ready) ? 1 : 0)) < TOT && ((rng % 100) < `SRC)) begin
                s_valid <= 1'b1; s_data <= bytes[bn + ((s_valid && s_ready) ? 1 : 0)];
                s_last <= ((s_valid && s_ready) ? (bi == int'(desc[pi][15:0]) - 1) ? (1 == int'(desc[pi + 1][15:0])) : (bi + 1 == int'(desc[pi][15:0]) - 1) : (bi == int'(desc[pi][15:0]) - 1));
            end else s_valid <= 1'b0;
        end
    end
    initial begin
        $readmemh("out/udp_desc.hex", desc); $readmemh("out/udp_bytes.hex", bytes);
        repeat (4) @(negedge clk); rst = 0;
        wait (dn == NP && bn == TOT);
        for (int t = 0; t < 4000000 && !(int'(n_pkt) + int'(n_drop) == NP && wn == 0 && !tx_en); t++) @(negedge clk);
        repeat (40) @(negedge clk);
        $display("FIRSTIN %0d", first_in); $display("FIRSTD %0d", first_d); $display("STATS %0d %0d %0d %0d", n_pkt, n_drop, underrun, cyc); $display("DONE %0d wire frames", nframes); $finish;
    end
endmodule
