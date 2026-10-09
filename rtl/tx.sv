// verilator lint_off DECLFILENAME
// verilator lint_off UNUSEDSIGNAL
// Chapter 13: the TCP send side of an established connection as hardware: send window, cumulative ACK, retransmission timer with the RFC 6298 estimator, backoff, go-back-N. The behaviour, and every simplification, is that of model/tx_gold.py.
//   tx_next : the whole machine as a combinational function: (state, event) -> (new state, segment to send).
//   tx_conn : one connection in registers: one event per cycle, result in the next cycle.
//   tx_tab  : 2^CIDW connections in a RAM (read-modify-write with a bypass) and a SCANNER that checks the timers: in every cycle without an outside event it injects a TICK for the next connection, round robin, with the current time.
// Events: 0 WRITE (a = bytes), 1 ACK (a = acknowledgement number, w = window), 2 POLL, 3 TICK. `now` is a 32-bit tick counter. Parameters (ticks): MSS, RTO_INIT, RTO_MIN, RTO_MAX; the RTT of a sample must be below 2^28.
module tx_next #(parameter int MSS = 100, parameter int RTO_MIN = 100, parameter int RTO_MAX = 6000) (
    input logic [31:0] una, input logic [31:0] nxt, input logic [31:0] mx, input logic [31:0] en, input logic [15:0] wnd, input logic [31:0] srtt8, input logic [31:0] rv4, input logic [31:0] rto, input logic [31:0] deadline,
    input logic timer_on, input logic timing_on, input logic have, input logic [31:0] rtt_seq, input logic [31:0] rtt_t0,
    input logic [1:0] e, input logic [31:0] now, input logic [31:0] a, input logic [15:0] w,
    output logic [31:0] n_una, output logic [31:0] n_nxt, output logic [31:0] n_mx, output logic [31:0] n_en, output logic [15:0] n_wnd, output logic [31:0] n_srtt8, output logic [31:0] n_rv4, output logic [31:0] n_rto, output logic [31:0] n_deadline,
    output logic n_timer_on, output logic n_timing_on, output logic n_have, output logic [31:0] n_rtt_seq, output logic [31:0] n_rtt_t0,
    output logic tx_v, output logic [31:0] tx_seq, output logic [15:0] tx_len, output logic tx_retx);
    logic [31:0] avail, wl, n32, newmax, r, sr, err, aerr, s8, v4, rto2, nretx;
    logic retx, do_sample;
    function automatic logic ltf(input logic [31:0] x, input logic [31:0] y); logic [31:0] d; d = x - y; ltf = d[31]; endfunction
    function automatic logic [31:0] clampr(input logic [31:0] x); clampr = (x < RTO_MIN) ? 32'(RTO_MIN) : (x > RTO_MAX) ? 32'(RTO_MAX) : x; endfunction
    always_comb begin
        n_una = una; n_nxt = nxt; n_mx = mx; n_en = en; n_wnd = wnd; n_srtt8 = srtt8; n_rv4 = rv4; n_rto = rto; n_deadline = deadline; n_timer_on = timer_on; n_timing_on = timing_on; n_have = have; n_rtt_seq = rtt_seq; n_rtt_t0 = rtt_t0;
        tx_v = 1'b0; tx_seq = 32'd0; tx_len = 16'd0; tx_retx = 1'b0; do_sample = 1'b0;
        avail = en - nxt; wl = una + {16'd0, wnd} - nxt; if (wl[31]) wl = 32'd0;
        n32 = (avail < 32'(MSS)) ? avail : 32'(MSS); if (wl < n32) n32 = wl;
        retx = ltf(nxt, mx); newmax = nxt + n32;
        r = now - rtt_t0; sr = srtt8 >> 3; err = r - sr; aerr = err[31] ? (32'd0 - err) : err;
        s8 = have ? srtt8 + err : (r << 3); v4 = have ? rv4 + aerr - (rv4 >> 2) : (r << 1);
        rto2 = rto << 1; if (rto2 > RTO_MAX) rto2 = 32'(RTO_MAX); nretx = (mx - una < 32'(MSS)) ? (mx - una) : 32'(MSS);
        case (e)
            2'd0: n_en = en + a;
            2'd2: if (n32 != 32'd0) begin
                tx_v = 1'b1; tx_seq = nxt; tx_len = n32[15:0]; tx_retx = retx;
                if (ltf(mx, newmax)) n_mx = newmax;
                n_nxt = newmax;
                if (!timing_on && !retx) begin n_timing_on = 1'b1; n_rtt_seq = newmax; n_rtt_t0 = now; end
                if (!timer_on) begin n_timer_on = 1'b1; n_deadline = now + rto; end
            end
            2'd1: begin
                if (ltf(una, a) && !ltf(mx, a)) begin
                    n_una = a; if (ltf(nxt, a)) n_nxt = a; n_wnd = w;
                    do_sample = timing_on && !ltf(a, rtt_seq);
                    if (do_sample) begin
                        n_srtt8 = s8; n_rv4 = v4; n_have = 1'b1; n_timing_on = 1'b0;
                        n_rto = clampr((s8 >> 3) + v4);
                    end else if (have) n_rto = clampr((srtt8 >> 3) + rv4);
                    if (a == mx) n_timer_on = 1'b0; else n_deadline = now + ((do_sample) ? clampr((s8 >> 3) + v4) : (have ? clampr((srtt8 >> 3) + rv4) : rto));
                end else if (a == una) n_wnd = w;
            end
            default: if (timer_on && !ltf(now, deadline)) begin
                n_rto = rto2; n_timing_on = 1'b0;
                if (nretx != 32'd0) begin tx_v = 1'b1; tx_seq = una; tx_len = nretx[15:0]; tx_retx = 1'b1; n_nxt = una + nretx; end else n_nxt = una;
                n_deadline = now + rto2;
            end
        endcase
    end
endmodule
// tx_conn: one connection, event in, result registered in the next cycle (r_valid). Reset: una = nxt = max = end = ISN, window WND0, RTO = RTO_INIT, timers off.
module tx_conn #(parameter int MSS = 100, parameter int RTO_INIT = 300, parameter int RTO_MIN = 100, parameter int RTO_MAX = 6000, parameter int ISN = 1000, parameter int WND0 = 65535) (
    input logic clk, input logic rst, input logic ev_valid, input logic [1:0] ev_type, input logic [31:0] ev_now, input logic [31:0] ev_a, input logic [15:0] ev_w,
    output logic r_valid, output logic [31:0] r_una, output logic [31:0] r_nxt, output logic [31:0] r_mx, output logic [31:0] r_en, output logic [15:0] r_wnd, output logic [31:0] r_srtt8, output logic [31:0] r_rv4, output logic [31:0] r_rto, output logic [31:0] r_deadline,
    output logic r_timer_on, output logic r_timing_on, output logic r_have, output logic r_txv, output logic [31:0] r_txseq, output logic [15:0] r_txlen, output logic r_txretx);
    logic [31:0] una, nxt, mx, en, srtt8, rv4, rto, deadline, rtt_seq, rtt_t0; logic [15:0] wnd; logic timer_on, timing_on, have;
    logic [31:0] n_una, n_nxt, n_mx, n_en, n_srtt8, n_rv4, n_rto, n_deadline, n_rtt_seq, n_rtt_t0, tx_seq; logic [15:0] n_wnd, tx_len; logic n_timer_on, n_timing_on, n_have, tx_v, tx_retx;
    tx_next #(.MSS(MSS), .RTO_MIN(RTO_MIN), .RTO_MAX(RTO_MAX)) nx (.una(una), .nxt(nxt), .mx(mx), .en(en), .wnd(wnd), .srtt8(srtt8), .rv4(rv4), .rto(rto), .deadline(deadline), .timer_on(timer_on), .timing_on(timing_on), .have(have), .rtt_seq(rtt_seq), .rtt_t0(rtt_t0),
        .e(ev_type), .now(ev_now), .a(ev_a), .w(ev_w), .n_una(n_una), .n_nxt(n_nxt), .n_mx(n_mx), .n_en(n_en), .n_wnd(n_wnd), .n_srtt8(n_srtt8), .n_rv4(n_rv4), .n_rto(n_rto), .n_deadline(n_deadline), .n_timer_on(n_timer_on), .n_timing_on(n_timing_on), .n_have(n_have), .n_rtt_seq(n_rtt_seq), .n_rtt_t0(n_rtt_t0),
        .tx_v(tx_v), .tx_seq(tx_seq), .tx_len(tx_len), .tx_retx(tx_retx));
    always_ff @(posedge clk) begin
        r_valid <= ev_valid && !rst;
        if (rst) begin una <= 32'(ISN); nxt <= 32'(ISN); mx <= 32'(ISN); en <= 32'(ISN); wnd <= 16'(WND0); srtt8 <= '0; rv4 <= '0; rto <= 32'(RTO_INIT); deadline <= '0; timer_on <= 1'b0; timing_on <= 1'b0; have <= 1'b0; rtt_seq <= '0; rtt_t0 <= '0; end
        else if (ev_valid) begin
            una <= n_una; nxt <= n_nxt; mx <= n_mx; en <= n_en; wnd <= n_wnd; srtt8 <= n_srtt8; rv4 <= n_rv4; rto <= n_rto; deadline <= n_deadline; timer_on <= n_timer_on; timing_on <= n_timing_on; have <= n_have; rtt_seq <= n_rtt_seq; rtt_t0 <= n_rtt_t0;
            r_una <= n_una; r_nxt <= n_nxt; r_mx <= n_mx; r_en <= n_en; r_wnd <= n_wnd; r_srtt8 <= n_srtt8; r_rv4 <= n_rv4; r_rto <= n_rto; r_deadline <= n_deadline; r_timer_on <= n_timer_on; r_timing_on <= n_timing_on; r_have <= n_have;
            r_txv <= tx_v; r_txseq <= tx_seq; r_txlen <= tx_len; r_txretx <= tx_retx;
        end
    end
endmodule
// tx_tab: 2^CIDW connections in a RAM, 339 bits each. An outside event takes the cycle; in a cycle without one, the SCANNER injects a TICK (with the current `now`) for connection scan_ptr and moves on: every connection is checked once every 2^CIDW cycles at the latest, so a timer fires at most 2^CIDW cycles (plus the pipeline) after its deadline. Stage 0: the event is chosen and the RAM read; stage 1: tx_next on what was read (or on the bypass), the result written back and registered. After reset the RAM is initialised, one word per cycle (ev_ready low until done).
module tx_tab #(parameter int CIDW = 4, parameter int MSS = 100, parameter int RTO_INIT = 300, parameter int RTO_MIN = 100, parameter int RTO_MAX = 6000, parameter int ISN = 1000, parameter int WND0 = 65535, parameter int SCAN = 1) (
    input logic clk, input logic rst, output logic ev_ready, input logic [31:0] now,
    input logic ev_valid, input logic [CIDW-1:0] ev_cid, input logic [1:0] ev_type, input logic [31:0] ev_a, input logic [15:0] ev_w,
    output logic r_valid, output logic [CIDW-1:0] r_cid, output logic [1:0] r_type, output logic [31:0] r_now, output logic [31:0] r_una, output logic [31:0] r_nxt, output logic [31:0] r_mx, output logic [31:0] r_en, output logic [15:0] r_wnd, output logic [31:0] r_srtt8, output logic [31:0] r_rv4, output logic [31:0] r_rto, output logic [31:0] r_deadline,
    output logic r_timer_on, output logic r_timing_on, output logic r_have, output logic r_txv, output logic [31:0] r_txseq, output logic [15:0] r_txlen, output logic r_txretx);
    localparam int W = 339;
    logic [W-1:0] mem [0:(1 << CIDW) - 1]; logic [W-1:0] mem_q, fwd_d, sv, nvec, initw; logic fwd_r, v1; logic [CIDW:0] ic; logic initing; logic [CIDW-1:0] sp, cid0, cid1; logic [1:0] t0, t1; logic [31:0] a0, a1, now0, now1; logic [15:0] w0, w1; logic go0;
    logic [31:0] una, nxt, mx, en, srtt8, rv4, rto, deadline, rtt_seq, rtt_t0; logic [15:0] wnd; logic timer_on, timing_on, have;
    logic [31:0] n_una, n_nxt, n_mx, n_en, n_srtt8, n_rv4, n_rto, n_deadline, n_rtt_seq, n_rtt_t0, tx_seq; logic [15:0] n_wnd, tx_len; logic n_timer_on, n_timing_on, n_have, tx_v, tx_retx;
    assign initw = {32'(ISN), 32'(ISN), 32'(ISN), 32'(ISN), 32'd0, 32'd0, 32'(RTO_INIT), 32'd0, 32'd0, 32'd0, 16'(WND0), 3'b000};
    assign initing = !ic[CIDW]; assign ev_ready = !initing;
    assign sv = fwd_r ? fwd_d : mem_q;
    assign {una, nxt, mx, en, srtt8, rv4, rto, deadline, rtt_seq, rtt_t0, wnd, timer_on, timing_on, have} = sv;
    tx_next #(.MSS(MSS), .RTO_MIN(RTO_MIN), .RTO_MAX(RTO_MAX)) nx (.una(una), .nxt(nxt), .mx(mx), .en(en), .wnd(wnd), .srtt8(srtt8), .rv4(rv4), .rto(rto), .deadline(deadline), .timer_on(timer_on), .timing_on(timing_on), .have(have), .rtt_seq(rtt_seq), .rtt_t0(rtt_t0),
        .e(t1), .now(now1), .a(a1), .w(w1), .n_una(n_una), .n_nxt(n_nxt), .n_mx(n_mx), .n_en(n_en), .n_wnd(n_wnd), .n_srtt8(n_srtt8), .n_rv4(n_rv4), .n_rto(n_rto), .n_deadline(n_deadline), .n_timer_on(n_timer_on), .n_timing_on(n_timing_on), .n_have(n_have), .n_rtt_seq(n_rtt_seq), .n_rtt_t0(n_rtt_t0),
        .tx_v(tx_v), .tx_seq(tx_seq), .tx_len(tx_len), .tx_retx(tx_retx));
    assign nvec = {n_una, n_nxt, n_mx, n_en, n_srtt8, n_rv4, n_rto, n_deadline, n_rtt_seq, n_rtt_t0, n_wnd, n_timer_on, n_timing_on, n_have};
    logic ext; assign ext = ev_valid && ev_ready;
    assign go0 = !initing && (ext || SCAN != 0);
    assign cid0 = ext ? ev_cid : sp; assign t0 = ext ? ev_type : 2'd3; assign a0 = ev_a; assign w0 = ev_w; assign now0 = now;
    always_ff @(posedge clk) begin
        if (rst) begin ic <= '0; sp <= '0; end
        else begin
            if (initing) ic <= ic + 1'b1;
            if (go0 && !ext) sp <= sp + 1'b1;
        end
        if (initing) mem[ic[CIDW-1:0]] <= initw; else if (v1) mem[cid1] <= nvec;
        mem_q <= mem[cid0];
        fwd_r <= go0 && v1 && (cid0 == cid1); fwd_d <= nvec;
        v1 <= go0 && !rst; cid1 <= cid0; t1 <= t0; a1 <= a0; w1 <= w0; now1 <= now0;
        r_valid <= v1 && !rst; r_cid <= cid1; r_type <= t1; r_now <= now1; r_una <= n_una; r_nxt <= n_nxt; r_mx <= n_mx; r_en <= n_en; r_wnd <= n_wnd; r_srtt8 <= n_srtt8; r_rv4 <= n_rv4; r_rto <= n_rto; r_deadline <= n_deadline;
        r_timer_on <= n_timer_on; r_timing_on <= n_timing_on; r_have <= n_have; r_txv <= tx_v; r_txseq <= tx_seq; r_txlen <= tx_len; r_txretx <= tx_retx;
    end
endmodule
// tx_conn_syn and tx_tab_syn: the same designs behind a handful of pins, ONLY so that they fit a chip for the place-and-route runs. The 64-bit event is shifted in serially, `now` is a free-running counter, the result leaves through one registered 16-bit port chosen by `sel`.
module tx_conn_syn (input logic clk, input logic rst, input logic si, input logic sh, input logic ev_valid, input logic [3:0] sel, output logic r_valid, output logic [15:0] info);
    logic [63:0] ev; logic [31:0] now, r_una, r_nxt, r_mx, r_en, r_srtt8, r_rv4, r_rto, r_deadline, r_txseq; logic [15:0] r_wnd, r_txlen; logic r_timer_on, r_timing_on, r_have, r_txv, r_txretx; logic [511:0] allb;
    always_ff @(posedge clk) begin if (sh) ev <= {ev[62:0], si}; now <= rst ? 32'd0 : now + 32'd1; end
    tx_conn c (.clk(clk), .rst(rst), .ev_valid(ev_valid), .ev_type(ev[57:56]), .ev_now(now), .ev_a(ev[47:16]), .ev_w(ev[15:0]), .r_valid(r_valid), .r_una(r_una), .r_nxt(r_nxt), .r_mx(r_mx), .r_en(r_en), .r_wnd(r_wnd), .r_srtt8(r_srtt8), .r_rv4(r_rv4), .r_rto(r_rto), .r_deadline(r_deadline),
        .r_timer_on(r_timer_on), .r_timing_on(r_timing_on), .r_have(r_have), .r_txv(r_txv), .r_txseq(r_txseq), .r_txlen(r_txlen), .r_txretx(r_txretx));
    assign allb = 512'({r_una, r_nxt, r_mx, r_en, r_srtt8, r_rv4, r_rto, r_deadline, r_txseq, r_wnd, r_txlen, r_timer_on, r_timing_on, r_have, r_txv, r_txretx});
    always_ff @(posedge clk) info <= allb[{5'd0 + sel, 4'b0000} +: 16];
endmodule
module tx_tab_syn #(parameter int CIDW = 4) (input logic clk, input logic rst, input logic si, input logic sh, input logic ev_valid, output logic ev_ready, input logic [3:0] sel, output logic r_valid, output logic [15:0] info);
    logic [63:0] ev; logic [31:0] now, r_now, r_una, r_nxt, r_mx, r_en, r_srtt8, r_rv4, r_rto, r_deadline, r_txseq; logic [15:0] r_wnd, r_txlen; logic r_timer_on, r_timing_on, r_have, r_txv, r_txretx; logic [CIDW-1:0] r_cid; logic [1:0] r_type; logic [511:0] allb;
    always_ff @(posedge clk) begin if (sh) ev <= {ev[62:0], si}; now <= rst ? 32'd0 : now + 32'd1; end
    tx_tab #(.CIDW(CIDW)) t (.clk(clk), .rst(rst), .ev_ready(ev_ready), .now(now), .ev_valid(ev_valid), .ev_cid(ev[48 +: CIDW]), .ev_type(ev[57:56]), .ev_a(ev[47:16]), .ev_w(ev[15:0]), .r_valid(r_valid), .r_cid(r_cid), .r_type(r_type), .r_now(r_now),
        .r_una(r_una), .r_nxt(r_nxt), .r_mx(r_mx), .r_en(r_en), .r_wnd(r_wnd), .r_srtt8(r_srtt8), .r_rv4(r_rv4), .r_rto(r_rto), .r_deadline(r_deadline), .r_timer_on(r_timer_on), .r_timing_on(r_timing_on), .r_have(r_have), .r_txv(r_txv), .r_txseq(r_txseq), .r_txlen(r_txlen), .r_txretx(r_txretx));
    assign allb = 512'({r_una, r_nxt, r_mx, r_en, r_srtt8, r_rv4, r_rto, r_deadline, r_txseq, r_wnd, r_txlen, r_timer_on, r_timing_on, r_have, r_txv, r_txretx, r_type, {(26 - CIDW){1'b0}}, r_cid, r_now});
    always_ff @(posedge clk) info <= allb[{5'd0 + sel, 4'b0000} +: 16];
endmodule
