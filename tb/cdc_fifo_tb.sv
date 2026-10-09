// Chapter 3 testbench for cdc_afifo: two unrelated clocks, a random producer and a random consumer, a scoreboard that checks every word and the occupancy.
//  Compile with rtl/cdc_sync.sv (ideal synchronizer: every capture is clean) or with tb/cdc_sync_meta.sv (metastability model). Defines: GRAY (1/0), WP and RP (clock periods in ps), PW and PR (percent chance per cycle of offering a word / asking for one), NWR (words to send).
//  Checks: (0) the occupancy each side believes (from the synchronized far pointer) is never wrong in the dangerous direction: the reader's count never exceeds the true occupancy and the writer's never falls below it; (1) every word read equals the word written, in order (catches reads of empty entries and overwritten entries); (2) a write accepted when the FIFO really holds DEPTH words is an overflow; (3) a read accepted when it holds nothing is an underflow; (4) all NWR words arrive before a time limit; (5) after the words are through, a reset of both sides in the middle of operation leaves the FIFO empty, not full and with both counts at zero, while the reset is held and after it is released.
`timescale 1ps/1ps
`ifndef GRAY
`define GRAY 1
`endif
`ifndef REG
`define REG 1
`endif
`ifndef WP
`define WP 10000
`endif
`ifndef RP
`define RP 7300
`endif
`ifndef PW
`define PW 70
`endif
`ifndef PR
`define PR 60
`endif
`ifndef NWR
`define NWR 3000
`endif
module cdc_fifo_tb;
    localparam int W = 8, AW = 3, DEPTH = 1 << AW, NWR = `NWR;
    int rlevel_over = 0, wlevel_under = 0, reset_bad = 0;
    logic wclk = 0, rclk = 0, wrst_n = 0, rrst_n = 0, wr_en = 0, rd_en = 0; logic [W-1:0] wr_data = '0, rd_data; logic full, empty; logic [AW:0] wlevel, rlevel;
    cdc_afifo #(.W(W), .AW(AW), .GRAY(`GRAY), .REG(`REG)) dut (.wclk(wclk), .wrst_n(wrst_n), .wr_en(wr_en), .wr_data(wr_data), .full(full), .rclk(rclk), .rrst_n(rrst_n), .rd_en(rd_en), .rd_data(rd_data), .empty(empty), .wlevel(wlevel), .rlevel(rlevel));
    always #(`WP / 2) wclk = ~wclk;
    initial begin #1234; forever #(`RP / 2) rclk = ~rclk; end          // the read clock starts at an unrelated phase
    logic [W-1:0] exp [0:NWR+DEPTH]; int nw = 0, nr = 0, bad_data = 0, overflow = 0, underflow = 0, maxocc = 0, full_seen = 0, empty_seen = 0; logic [31:0] rw = 32'h13579bdf, rr = 32'h2468ace1;
    function automatic logic [31:0] nxt(input logic [31:0] x); logic [31:0] y; y = x; y = y ^ (y << 13); y = y ^ (y >> 17); y = y ^ (y << 5); return y; endfunction
    always @(posedge wclk) if (wrst_n) begin                          // reads the values from BEFORE this edge (the DUT updates after it)
        logic took; took = 0;
        if (int'(wlevel) < nw - nr) wlevel_under++;                    // the writer believes there are fewer words inside than there really are
        if (wr_en && !full) begin
            if (nw - nr >= DEPTH) overflow++;
            exp[nw] = wr_data; nw++; took = 1; if (nw - nr > maxocc) maxocc = nw - nr;
        end
        if (full) full_seen++;
        rw = nxt(rw); #200;
        if (!wr_en || took) wr_en = (nw < NWR) && ((rw % 100) < `PW);   // a compliant source holds an offered word until it is accepted
        wr_data = nw[7:0] * 8'd37 + 8'd11;
    end
    always @(posedge rclk) if (rrst_n) begin
        if (int'(rlevel) > nw - nr) rlevel_over++;                     // the reader believes there are more words inside than there really are
        if (rd_en && !empty) begin
            if (nr >= nw) underflow++;
            else if (rd_data !== exp[nr]) bad_data++;
            nr++;
        end
        if (empty) empty_seen++;
        rr = nxt(rr); #200; rd_en = ((rr % 100) < `PR);
    end
    initial begin
        repeat (6) @(posedge wclk); #500 wrst_n = 1; repeat (3) @(posedge rclk); #500 rrst_n = 1;
        begin : waitdone
            repeat (200000) begin @(posedge rclk); if (nr >= NWR) disable waitdone; end
        end
        #20000;
        // a reset in the MIDDLE of operation: both sides in reset, the FIFO must read as empty (and not full, with both counts zero) while reset is held and again after it is released
        wr_en = 0; rd_en = 0; wrst_n = 0; rrst_n = 0; repeat (8) @(posedge wclk); repeat (8) @(posedge rclk); #500;
        if (empty !== 1'b1 || full !== 1'b0 || wlevel !== 0 || rlevel !== 0) reset_bad++;
        wrst_n = 1; rrst_n = 1; repeat (8) @(posedge wclk); repeat (8) @(posedge rclk); #500;
        if (empty !== 1'b1 || full !== 1'b0 || wlevel !== 0 || rlevel !== 0) reset_bad++;
        if (nr == NWR && nw == NWR && bad_data == 0 && rlevel_over == 0 && wlevel_under == 0 && reset_bad == 0 && overflow == 0 && underflow == 0)
            $display("PASS: %0d words in order, max occupancy %0d of %0d, full seen %0d cycles, empty seen %0d cycles", nr, maxocc, DEPTH, full_seen, empty_seen);
        else $display("FAIL: written %0d read %0d, wrong words %0d, overflows %0d, underflows %0d, reader over-counted %0d times, writer under-counted %0d times, mid-run reset not clean %0d times", nw, nr, bad_data, overflow, underflow, rlevel_over, wlevel_under, reset_bad);
        $finish;
    end
endmodule
