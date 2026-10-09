// Chapter 13 testbench for tx_conn (TAB = 0) and tx_tab (TAB = 1): line k of out/tx_stim.hex is presented in cycle k (that cycle number is `now`): valid(1) type(1) cid(2) a(8) w(4) hex digits; a line with valid = 0 carries random junk. The first line is presented when the design is ready (after the RAM initialisation). Prints for each result `R <cid> <type> <now> <una> <nxt> <max> <wnd> <end> <srtt8> <rv4> <rto> <deadline> <timer_on> <timing_on> <have> <txv> <txseq> <txlen> <txretx>`. Defines: NC, TAB, CIDW, SCAN, MSS, RTO_INIT, RTO_MIN, RTO_MAX.
`timescale 1ns/1ps
`ifndef NC
`define NC 1000
`endif
`ifndef TAB
`define TAB 0
`endif
`ifndef CIDW
`define CIDW 2
`endif
`ifndef SCAN
`define SCAN 1
`endif
`ifndef MSS
`define MSS 100
`endif
`ifndef RTO_INIT
`define RTO_INIT 300
`endif
`ifndef RTO_MIN
`define RTO_MIN 100
`endif
`ifndef RTO_MAX
`define RTO_MAX 6000
`endif
module tx_tb;
    localparam int NC = `NC, CW = `CIDW;
    logic clk = 0, rst = 1, ev_valid = 0, ev_ready; logic [CW-1:0] ev_cid = '0; logic [1:0] ev_type = '0; logic [31:0] ev_a = '0, now = '0; logic [15:0] ev_w = '0;
    logic r_valid, r_timer_on, r_timing_on, r_have, r_txv, r_txretx; logic [CW-1:0] r_cid; logic [1:0] r_type; logic [31:0] r_now, r_una, r_nxt, r_mx, r_en, r_srtt8, r_rv4, r_rto, r_deadline, r_txseq; logic [15:0] r_wnd, r_txlen;
    logic [63:0] vec [0:NC-1]; int k; int nres = 0;
    if (`TAB) begin : gt
        tx_tab #(.CIDW(CW), .MSS(`MSS), .RTO_INIT(`RTO_INIT), .RTO_MIN(`RTO_MIN), .RTO_MAX(`RTO_MAX), .SCAN(`SCAN)) dut (.clk(clk), .rst(rst), .ev_ready(ev_ready), .now(now), .ev_valid(ev_valid), .ev_cid(ev_cid), .ev_type(ev_type), .ev_a(ev_a), .ev_w(ev_w),
            .r_valid(r_valid), .r_cid(r_cid), .r_type(r_type), .r_now(r_now), .r_una(r_una), .r_nxt(r_nxt), .r_mx(r_mx), .r_en(r_en), .r_wnd(r_wnd), .r_srtt8(r_srtt8), .r_rv4(r_rv4), .r_rto(r_rto), .r_deadline(r_deadline), .r_timer_on(r_timer_on), .r_timing_on(r_timing_on), .r_have(r_have), .r_txv(r_txv), .r_txseq(r_txseq), .r_txlen(r_txlen), .r_txretx(r_txretx));
    end else begin : gc
        assign ev_ready = 1'b1; assign r_cid = '0; assign r_type = '0; assign r_now = '0;
        tx_conn #(.MSS(`MSS), .RTO_INIT(`RTO_INIT), .RTO_MIN(`RTO_MIN), .RTO_MAX(`RTO_MAX)) dut (.clk(clk), .rst(rst), .ev_valid(ev_valid), .ev_type(ev_type), .ev_now(now), .ev_a(ev_a), .ev_w(ev_w),
            .r_valid(r_valid), .r_una(r_una), .r_nxt(r_nxt), .r_mx(r_mx), .r_en(r_en), .r_wnd(r_wnd), .r_srtt8(r_srtt8), .r_rv4(r_rv4), .r_rto(r_rto), .r_deadline(r_deadline), .r_timer_on(r_timer_on), .r_timing_on(r_timing_on), .r_have(r_have), .r_txv(r_txv), .r_txseq(r_txseq), .r_txlen(r_txlen), .r_txretx(r_txretx));
    end
    always #4 clk = ~clk;
    always @(posedge clk) if (r_valid) begin
        $display("R %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d", r_cid, `TAB ? r_type : 2'd0, `TAB ? r_now : 32'd0, r_una, r_nxt, r_mx, r_wnd, r_en, r_srtt8, r_rv4, r_rto, r_deadline, r_timer_on, r_timing_on, r_have, r_txv, r_txv ? r_txseq : 32'd0, r_txv ? r_txlen : 16'd0, r_txv ? r_txretx : 1'b0); nres++;
    end
    initial begin
        $readmemh("out/tx_stim.hex", vec);
        ev_valid = 1; ev_type = 2'd1; repeat (3) @(negedge clk); rst = 0; ev_valid = 0;               // a valid event during reset must be discarded
        wait (ev_ready); @(negedge clk);
        for (k = 0; k < NC; k++) begin
            now = k; ev_valid = vec[k][60]; ev_type = vec[k][57:56]; ev_cid = vec[k][48 +: CW]; ev_a = vec[k][47:16]; ev_w = vec[k][15:0];
            @(negedge clk);
        end
        ev_valid = 0; repeat (20 + (1 << CW)) @(negedge clk); $display("DONE %0d results", nres); $finish;
    end
endmodule
