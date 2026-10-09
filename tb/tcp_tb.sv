// Chapter 12 testbench for tcp_conn (TAB = 0), tcp_tab (TAB = 1) and tcp_tab2 (TAB = 2); an event is held until ev_ready accepts it: replays out/tcp_stim.hex, one operation per cycle: valid(1) type(1) cid(2) flags(1) len(4) wnd(4) seq(8) ack(8) iss(8) hex digits. Idle cycles carry random junk on every field. Prints `R <cid> <state> <passive> <una> <nxt> <rcv> <txv> <txflags> <txseq> <txack> <delivered>` for each result `LAT` (cycles from the first event to its result), `STALLS` (cycles an event waited for ev_ready) and `CYCLES`. Defines: NC, TAB, CIDW, SPLIT.
`timescale 1ns/1ps
`ifndef NC
`define NC 1000
`endif
`ifndef TAB
`define TAB 0
`endif
`ifndef SPLIT
`define SPLIT 0
`endif
`ifndef CIDW
`define CIDW 4
`endif
module tcp_tb;
    localparam int NC = `NC, CW = `CIDW;
    logic clk = 0, rst = 1, ev_valid = 0, ev_ready; logic [CW-1:0] ev_cid = '0; logic [2:0] ev_type = '0; logic [3:0] ev_f = '0; logic [31:0] ev_seq = '0, ev_ack = '0, ev_iss = '0; logic [15:0] ev_len = '0, ev_wnd = '0;
    logic r_valid, r_pas, r_txv; logic [CW-1:0] r_cid; logic [3:0] r_st, r_txf; logic [31:0] r_una, r_nxt, r_rcv, r_txseq, r_txack; logic [15:0] r_dlv;
    logic [147:0] vec [0:NC-1]; int k, nres = 0, cyc = 0, first_ev = -1, first_r = -1, stalls = 0; logic took = 0;
    if (`TAB == 2) begin : gt2
        tcp_tab2 #(.CIDW(CW), .SPLIT(`SPLIT)) dut (.clk(clk), .rst(rst), .ev_ready(ev_ready), .ev_valid(ev_valid), .ev_cid(ev_cid), .ev_type(ev_type), .ev_f(ev_f), .ev_seq(ev_seq), .ev_ack(ev_ack), .ev_len(ev_len), .ev_wnd(ev_wnd), .ev_iss(ev_iss),
            .r_valid(r_valid), .r_cid(r_cid), .r_st(r_st), .r_pas(r_pas), .r_una(r_una), .r_nxt(r_nxt), .r_rcv(r_rcv), .r_txv(r_txv), .r_txf(r_txf), .r_txseq(r_txseq), .r_txack(r_txack), .r_dlv(r_dlv));
    end else if (`TAB == 1) begin : gt
        tcp_tab #(.CIDW(CW)) dut (.clk(clk), .rst(rst), .ev_ready(ev_ready), .ev_valid(ev_valid), .ev_cid(ev_cid), .ev_type(ev_type), .ev_f(ev_f), .ev_seq(ev_seq), .ev_ack(ev_ack), .ev_len(ev_len), .ev_wnd(ev_wnd), .ev_iss(ev_iss),
            .r_valid(r_valid), .r_cid(r_cid), .r_st(r_st), .r_pas(r_pas), .r_una(r_una), .r_nxt(r_nxt), .r_rcv(r_rcv), .r_txv(r_txv), .r_txf(r_txf), .r_txseq(r_txseq), .r_txack(r_txack), .r_dlv(r_dlv));
    end else begin : gc
        assign ev_ready = 1'b1; assign r_cid = '0;
        tcp_conn dut (.clk(clk), .rst(rst), .ev_valid(ev_valid), .ev_type(ev_type), .ev_f(ev_f), .ev_seq(ev_seq), .ev_ack(ev_ack), .ev_len(ev_len), .ev_wnd(ev_wnd), .ev_iss(ev_iss),
            .r_valid(r_valid), .r_st(r_st), .r_pas(r_pas), .r_una(r_una), .r_nxt(r_nxt), .r_rcv(r_rcv), .r_txv(r_txv), .r_txf(r_txf), .r_txseq(r_txseq), .r_txack(r_txack), .r_dlv(r_dlv));
    end
    always #4 clk = ~clk;
    always @(posedge clk) begin
        cyc <= cyc + 1; took <= ev_valid && ev_ready && !rst; if (ev_valid && !ev_ready && !rst) stalls++; if (ev_valid && ev_ready && !rst && first_ev < 0) first_ev <= cyc;
        if (r_valid) begin
            $display("R %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d", r_cid, r_st, r_pas, r_una, r_nxt, r_rcv, r_txv, r_txv ? r_txf : 4'd0, r_txv ? r_txseq : 32'd0, r_txv ? r_txack : 32'd0, r_dlv); nres++; if (first_r < 0) first_r = cyc;
        end
    end
    initial begin
        $readmemh("out/tcp_stim.hex", vec);
        ev_valid = 1; ev_type = 3'd5; repeat (3) @(negedge clk); rst = 0; ev_valid = 0;               // a valid event during reset must be discarded
        wait (ev_ready);
        for (k = 0; k < NC; k++) begin
            @(negedge clk); ev_valid = vec[k][144]; ev_type = vec[k][143:140]; ev_cid = vec[k][132 +: CW]; ev_f = vec[k][131:128]; ev_len = vec[k][127:112]; ev_wnd = vec[k][111:96]; ev_seq = vec[k][95:64]; ev_ack = vec[k][63:32]; ev_iss = vec[k][31:0];
            if (ev_valid) begin do begin @(posedge clk); #1; end while (!took); end
        end
        @(negedge clk); ev_valid = 0; repeat (8) @(negedge clk); $display("LAT %0d", first_r - first_ev); $display("STALLS %0d", stalls); $display("CYCLES %0d", cyc); $display("DONE %0d results", nres); $finish;
    end
endmodule
