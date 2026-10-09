// verilator lint_off DECLFILENAME
// verilator lint_off UNUSEDSIGNAL
// Chapter 12: the TCP connection state machine and its segment checks (RFC 9293 section 3.10 with the RFC 5961 mitigations), as hardware. The behaviour, and every simplification, is that of model/tcp_gold.py.
//   tcp_next : the whole machine as a combinational function: (state variables, event) -> (new state variables, segment to send, bytes delivered).
//   tcp_conn : one connection in registers: one event per cycle, the result in the next cycle.
//   tcp_tab  : N connections in a RAM, one event per cycle for any connection, result two cycles later; a read-modify-write pipeline with forwarding for back-to-back events of the same connection.
// Event types: 0 OPEN_PASSIVE, 1 OPEN_ACTIVE (iss), 2 CLOSE, 3 ABORT, 4 TIMEOUT (2MSL), 5 SEGMENT (flags: bit 0 SYN, 1 ACK, 2 FIN, 3 RST; seq, ack, len, wnd = our receive window). States: 0 CLOSED, 1 LISTEN, 2 SYN_SENT, 3 SYN_RCVD, 4 ESTABLISHED, 5 FIN_WAIT_1, 6 FIN_WAIT_2, 7 CLOSE_WAIT, 8 CLOSING, 9 LAST_ACK, 10 TIME_WAIT.
module tcp_next (
    input logic [3:0] st, input logic pas, input logic [31:0] una, input logic [31:0] nxt, input logic [31:0] rcv,
    input logic [2:0] e, input logic [3:0] f, input logic [31:0] seq, input logic [31:0] ack, input logic [15:0] ln, input logic [15:0] wnd, input logic [31:0] iss,
    output logic [3:0] n_st, output logic n_pas, output logic [31:0] n_una, output logic [31:0] n_nxt, output logic [31:0] n_rcv,
    output logic tx_v, output logic [3:0] tx_f, output logic [31:0] tx_seq, output logic [31:0] tx_ack, output logic [15:0] dlv);
    localparam logic [3:0] CLOSED = 4'd0, LISTEN = 4'd1, SYN_SENT = 4'd2, SYN_RCVD = 4'd3, ESTAB = 4'd4, FW1 = 4'd5, FW2 = 4'd6, CLOSE_WAIT = 4'd7, CLOSING = 4'd8, LAST_ACK = 4'd9, TIME_WAIT = 4'd10;
    localparam logic [3:0] SYN = 4'd1, ACK = 4'd2, FIN = 4'd4, RST = 4'd8;
    logic s_syn, s_ack, s_fin, s_rst; logic [16:0] segl; logic [31:0] d_seq, d_end, du, dn, una2, rcv2; logic ack_in, ack_old, acc_ok, stop, acked, fin_ok; logic [3:0] st2; logic [15:0] nn;
    always_comb begin
        n_st = st; n_pas = pas; n_una = una; n_nxt = nxt; n_rcv = rcv; tx_v = 1'b0; tx_f = 4'd0; tx_seq = 32'd0; tx_ack = 32'd0; dlv = 16'd0;
        s_syn = f[0]; s_ack = f[1]; s_fin = f[2]; s_rst = f[3];
        segl = {1'b0, ln} + {16'd0, s_syn} + {16'd0, s_fin};
        d_seq = seq - rcv; d_end = seq + {15'd0, segl} - 32'd1 - rcv; du = ack - una; dn = nxt - una;
        ack_in = (du != 32'd0) && (du <= dn); ack_old = du[31];
        acc_ok = (segl == 17'd0) ? ((wnd == 16'd0) ? (seq == rcv) : (d_seq < {16'd0, wnd})) : ((wnd == 16'd0) ? 1'b0 : ((d_seq < {16'd0, wnd}) || (d_end < {16'd0, wnd})));
        una2 = una; rcv2 = rcv; st2 = st; stop = 1'b0; acked = 1'b0; fin_ok = 1'b1; nn = 16'd0;
        case (e)
            3'd0: if (st == CLOSED) begin n_st = LISTEN; n_pas = 1'b1; n_una = iss; n_nxt = iss; end
            3'd1: if (st == CLOSED || st == LISTEN) begin n_st = SYN_SENT; n_pas = 1'b0; n_una = iss; n_nxt = iss + 32'd1; tx_v = 1'b1; tx_f = SYN; tx_seq = iss; end
            3'd2: begin
                if (st == LISTEN || st == SYN_SENT) n_st = CLOSED;
                else if (st == SYN_RCVD || st == ESTAB || st == CLOSE_WAIT) begin tx_v = 1'b1; tx_f = FIN | ACK; tx_seq = nxt; tx_ack = rcv; n_nxt = nxt + 32'd1; n_st = (st == CLOSE_WAIT) ? LAST_ACK : FW1; end
            end
            3'd3: begin
                if (st == SYN_RCVD || st == ESTAB || st == FW1 || st == FW2 || st == CLOSE_WAIT) begin tx_v = 1'b1; tx_f = RST; tx_seq = nxt; end
                n_st = CLOSED;
            end
            3'd4: if (st == TIME_WAIT) n_st = CLOSED;
            default: begin
                if (st == CLOSED) begin
                    if (!s_rst) begin
                        tx_v = 1'b1;
                        if (s_ack) begin tx_f = RST; tx_seq = ack; end else begin tx_f = RST | ACK; tx_seq = 32'd0; tx_ack = seq + {15'd0, segl}; end
                    end
                end else if (st == LISTEN) begin
                    if (s_rst) begin end
                    else if (s_ack) begin tx_v = 1'b1; tx_f = RST; tx_seq = ack; end
                    else if (s_syn) begin n_rcv = seq + 32'd1; n_una = nxt; n_nxt = nxt + 32'd1; n_st = SYN_RCVD; n_pas = 1'b1; tx_v = 1'b1; tx_f = SYN | ACK; tx_seq = nxt; tx_ack = seq + 32'd1; end
                end else if (st == SYN_SENT) begin
                    if (s_ack && !ack_in) begin if (!s_rst) begin tx_v = 1'b1; tx_f = RST; tx_seq = ack; end end
                    else if (s_rst) begin if (s_ack) n_st = CLOSED; end
                    else if (s_syn) begin
                        n_rcv = seq + 32'd1;
                        if (s_ack) begin n_una = ack; n_st = ESTAB; tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = seq + 32'd1; end
                        else begin n_st = SYN_RCVD; n_pas = 1'b0; tx_v = 1'b1; tx_f = SYN | ACK; tx_seq = una; tx_ack = seq + 32'd1; end
                    end
                end else begin
                    if (!acc_ok) begin if (!s_rst) begin tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = rcv; end end
                    else if (s_rst) begin
                        if (seq == rcv) n_st = (st == SYN_RCVD && pas) ? LISTEN : CLOSED;
                        else begin tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = rcv; end
                    end
                    else if (s_syn) begin tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = rcv; end
                    else if (s_ack) begin
                        if (st == SYN_RCVD) begin
                            if (ack_in) begin st2 = ESTAB; una2 = ack; end else begin tx_v = 1'b1; tx_f = RST; tx_seq = ack; stop = 1'b1; end
                        end else begin
                            if (!ack_old && du > dn) begin tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = rcv; stop = 1'b1; end
                            else if (!ack_old && du != 32'd0) una2 = ack;
                        end
                        if (!stop) begin
                            acked = (una2 == nxt);
                            if (st2 == FW1 && acked) st2 = FW2; else if (st2 == CLOSING && acked) st2 = TIME_WAIT; else if (st2 == LAST_ACK && acked) begin st2 = CLOSED; stop = 1'b1; end
                            n_una = una2; n_st = st2;
                            if (!stop) begin
                                if (st2 == ESTAB || st2 == FW1 || st2 == FW2) begin
                                    if (ln != 16'd0) begin
                                        if (seq == rcv) begin nn = (ln < wnd) ? ln : wnd; dlv = nn; rcv2 = rcv + {16'd0, nn}; fin_ok = (nn == ln); end else fin_ok = 1'b0;
                                        n_rcv = rcv2; tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = rcv2;
                                    end else fin_ok = (seq == rcv);
                                    if (s_fin) begin
                                        if (fin_ok) begin
                                            rcv2 = rcv2 + 32'd1; n_rcv = rcv2; tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = rcv2;
                                            n_st = (st2 == ESTAB) ? CLOSE_WAIT : ((st2 == FW2) ? TIME_WAIT : CLOSING);
                                        end else if (!tx_v) begin tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = rcv; end
                                    end
                                end else if (s_fin) begin tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = rcv; end
                            end
                        end
                    end
                end
            end
        endcase
    end
endmodule
// tcp_conn: one connection. ev_valid with the event; the result (state, segment to send, bytes delivered, the three sequence variables) is registered and valid in the next cycle (r_valid).
module tcp_conn (
    input logic clk, input logic rst,
    input logic ev_valid, input logic [2:0] ev_type, input logic [3:0] ev_f, input logic [31:0] ev_seq, input logic [31:0] ev_ack, input logic [15:0] ev_len, input logic [15:0] ev_wnd, input logic [31:0] ev_iss,
    output logic r_valid, output logic [3:0] r_st, output logic r_pas, output logic [31:0] r_una, output logic [31:0] r_nxt, output logic [31:0] r_rcv, output logic r_txv, output logic [3:0] r_txf, output logic [31:0] r_txseq, output logic [31:0] r_txack, output logic [15:0] r_dlv);
    logic [3:0] st, n_st; logic pas, n_pas; logic [31:0] una, nxt, rcv, n_una, n_nxt, n_rcv, tx_seq, tx_ack; logic tx_v; logic [3:0] tx_f; logic [15:0] dlv;
    tcp_next nx (.st(st), .pas(pas), .una(una), .nxt(nxt), .rcv(rcv), .e(ev_type), .f(ev_f), .seq(ev_seq), .ack(ev_ack), .ln(ev_len), .wnd(ev_wnd), .iss(ev_iss),
        .n_st(n_st), .n_pas(n_pas), .n_una(n_una), .n_nxt(n_nxt), .n_rcv(n_rcv), .tx_v(tx_v), .tx_f(tx_f), .tx_seq(tx_seq), .tx_ack(tx_ack), .dlv(dlv));
    always_ff @(posedge clk) begin
        r_valid <= ev_valid && !rst;
        if (rst) begin st <= 4'd0; pas <= 1'b0; una <= 32'd0; nxt <= 32'd0; rcv <= 32'd0; end
        else if (ev_valid) begin
            st <= n_st; pas <= n_pas; una <= n_una; nxt <= n_nxt; rcv <= n_rcv;
            r_st <= n_st; r_pas <= n_pas; r_una <= n_una; r_nxt <= n_nxt; r_rcv <= n_rcv; r_txv <= tx_v; r_txf <= tx_f; r_txseq <= tx_seq; r_txack <= tx_ack; r_dlv <= dlv;
        end
    end
endmodule
// tcp_tab: 2^CIDW connections whose state (4 + 1 + 3 x 32 = 101 bits each) lives in a RAM. One event per cycle for ANY connection. Cycle 0: the event arrives and the RAM is read; cycle 1: tcp_next runs on what was read and the result is written back and registered. An event that arrives in the cycle in which the previous event's result is being written to the SAME connection would read the old state, so the new state is also kept in a bypass register and used instead (fwd_r). After reset the RAM is cleared, one word per cycle: ev_ready is low until then.
module tcp_tab #(parameter int CIDW = 4) (
    input logic clk, input logic rst, output logic ev_ready,
    input logic ev_valid, input logic [CIDW-1:0] ev_cid, input logic [2:0] ev_type, input logic [3:0] ev_f, input logic [31:0] ev_seq, input logic [31:0] ev_ack, input logic [15:0] ev_len, input logic [15:0] ev_wnd, input logic [31:0] ev_iss,
    output logic r_valid, output logic [CIDW-1:0] r_cid, output logic [3:0] r_st, output logic r_pas, output logic [31:0] r_una, output logic [31:0] r_nxt, output logic [31:0] r_rcv, output logic r_txv, output logic [3:0] r_txf, output logic [31:0] r_txseq, output logic [31:0] r_txack, output logic [15:0] r_dlv);
    localparam int W = 101;
    logic [W-1:0] mem [0:(1 << CIDW) - 1]; logic [W-1:0] mem_q, fwd_d, sv, nvec; logic fwd_r, v1; logic [CIDW:0] ic; logic initing;
    logic [CIDW-1:0] cid1; logic [2:0] t1; logic [3:0] f1; logic [31:0] seq1, ack1, iss1; logic [15:0] len1, wnd1;
    logic [3:0] n_st; logic n_pas; logic [31:0] n_una, n_nxt, n_rcv, tx_seq, tx_ack; logic tx_v; logic [3:0] tx_f; logic [15:0] dlv;
    assign initing = !ic[CIDW]; assign ev_ready = !initing;
    assign sv = fwd_r ? fwd_d : mem_q;
    tcp_next nx (.st(sv[100:97]), .pas(sv[96]), .una(sv[95:64]), .nxt(sv[63:32]), .rcv(sv[31:0]), .e(t1), .f(f1), .seq(seq1), .ack(ack1), .ln(len1), .wnd(wnd1), .iss(iss1),
        .n_st(n_st), .n_pas(n_pas), .n_una(n_una), .n_nxt(n_nxt), .n_rcv(n_rcv), .tx_v(tx_v), .tx_f(tx_f), .tx_seq(tx_seq), .tx_ack(tx_ack), .dlv(dlv));
    assign nvec = {n_st, n_pas, n_una, n_nxt, n_rcv};
    logic take; assign take = ev_valid && ev_ready;
    always_ff @(posedge clk) begin
        if (rst) ic <= '0; else if (initing) ic <= ic + 1'b1;
        if (initing) mem[ic[CIDW-1:0]] <= '0; else if (v1) mem[cid1] <= nvec;
        mem_q <= mem[ev_cid];
        fwd_r <= take && v1 && (ev_cid == cid1); fwd_d <= nvec;
        v1 <= take && !rst; cid1 <= ev_cid; t1 <= ev_type; f1 <= ev_f; seq1 <= ev_seq; ack1 <= ev_ack; iss1 <= ev_iss; len1 <= ev_len; wnd1 <= ev_wnd;
        r_valid <= v1 && !rst; r_cid <= cid1; r_st <= n_st; r_pas <= n_pas; r_una <= n_una; r_nxt <= n_nxt; r_rcv <= n_rcv; r_txv <= tx_v; r_txf <= tx_f; r_txseq <= tx_seq; r_txack <= tx_ack; r_dlv <= dlv;
    end
endmodule
// ---------------------------------------------------------------------------------------------------------------
// The second design: the same machine cut in two so that it can be pipelined. tcp_pre does ALL the arithmetic (32-bit comparisons and additions, in parallel, from registered values); tcp_sel only chooses (flags and one-bit predicates in, state and segment out). tcp_tab2 puts a register between them.
//   P bits: 0 seq == rcv, 1 acceptable, 2 una < ack <= nxt, 3 ack < una, 4 ack > nxt, 5 ack == nxt, 6 una == nxt, 7 len != 0, 8 len <= wnd
//   S words: 0 seq + 1, 1 seq + segment length, 2 rcv + 1, 3 rcv + len, 4 rcv + len + 1, 5 rcv + wnd, 6 nxt + 1, 7 iss + 1
// tcp_pre_a: the arithmetic (differences and sums, in parallel from registered values) and the equalities. tcp_pre_b: the comparisons of the differences. tcp_pre = both, in one cycle.
module tcp_pre_a (
    input logic [31:0] una, input logic [31:0] nxt, input logic [31:0] rcv, input logic [3:0] f, input logic [31:0] seq, input logic [31:0] ack, input logic [15:0] ln, input logic [15:0] wnd, input logic [31:0] iss,
    output logic [127:0] D, output logic [6:0] E, output logic [255:0] S);
    logic [16:0] segl;
    always_comb begin
        segl = {1'b0, ln} + {16'd0, f[0]} + {16'd0, f[2]};
        D = {ack - una, nxt - una, seq + {15'd0, segl} - 32'd1 - rcv, seq - rcv};
        E = {(wnd == 16'd0), (segl == 17'd0), (ln <= wnd), (ln != 16'd0), (una == nxt), (ack == nxt), (seq == rcv)};
        S = {iss + 32'd1, nxt + 32'd1, rcv + {16'd0, wnd}, rcv + {16'd0, ln} + 32'd1, rcv + {16'd0, ln}, rcv + 32'd1, seq + {15'd0, segl}, seq + 32'd1};
    end
endmodule
module tcp_pre_b (input logic [127:0] D, input logic [6:0] E, input logic [15:0] wnd, output logic [8:0] P);
    logic [31:0] d_seq, d_end, dn, du; logic ack_in, acc_ok;
    always_comb begin
        {du, dn, d_end, d_seq} = D;
        ack_in = (du != 32'd0) && (du <= dn);
        acc_ok = E[5] ? (E[6] ? E[0] : (d_seq < {16'd0, wnd})) : (E[6] ? 1'b0 : ((d_seq < {16'd0, wnd}) || (d_end < {16'd0, wnd})));
        P = {E[4], E[3], E[2], E[1], (!du[31] && du > dn), du[31], ack_in, acc_ok, E[0]};
    end
endmodule
module tcp_sel (
    input logic [3:0] st, input logic pas, input logic [31:0] una, input logic [31:0] nxt, input logic [31:0] rcv,
    input logic [2:0] e, input logic [3:0] f, input logic [31:0] seq, input logic [31:0] ack, input logic [15:0] ln, input logic [15:0] wnd, input logic [31:0] iss, input logic [8:0] P, input logic [255:0] S,
    output logic [3:0] n_st, output logic n_pas, output logic [31:0] n_una, output logic [31:0] n_nxt, output logic [31:0] n_rcv,
    output logic tx_v, output logic [3:0] tx_f, output logic [31:0] tx_seq, output logic [31:0] tx_ack, output logic [15:0] dlv);
    localparam logic [3:0] CLOSED = 4'd0, LISTEN = 4'd1, SYN_SENT = 4'd2, SYN_RCVD = 4'd3, ESTAB = 4'd4, FW1 = 4'd5, FW2 = 4'd6, CLOSE_WAIT = 4'd7, CLOSING = 4'd8, LAST_ACK = 4'd9, TIME_WAIT = 4'd10;
    localparam logic [3:0] SYN = 4'd1, ACK = 4'd2, FIN = 4'd4, RST = 4'd8;
    logic s_syn, s_ack, s_fin, s_rst, seq_eq, acc_ok, ack_in, ack_old, ack_fut, ack_eq, una_eq, ln_nz, ln_le; logic [31:0] seq_p1, seq_pseg, rcv_p1, rcv_pln, rcv_pln1, rcv_pwnd, nxt_p1, iss_p1;
    logic [31:0] rcv2; logic [3:0] st2; logic stop, acked, fin_ok, una_upd;
    always_comb begin
        {ln_le, ln_nz, una_eq, ack_eq, ack_fut, ack_old, ack_in, acc_ok, seq_eq} = P;
        {iss_p1, nxt_p1, rcv_pwnd, rcv_pln1, rcv_pln, rcv_p1, seq_pseg, seq_p1} = S;
        s_syn = f[0]; s_ack = f[1]; s_fin = f[2]; s_rst = f[3];
        n_st = st; n_pas = pas; n_una = una; n_nxt = nxt; n_rcv = rcv; tx_v = 1'b0; tx_f = 4'd0; tx_seq = 32'd0; tx_ack = 32'd0; dlv = 16'd0;
        rcv2 = rcv; st2 = st; stop = 1'b0; acked = 1'b0; fin_ok = 1'b1; una_upd = 1'b0;
        case (e)
            3'd0: if (st == CLOSED) begin n_st = LISTEN; n_pas = 1'b1; n_una = iss; n_nxt = iss; end
            3'd1: if (st == CLOSED || st == LISTEN) begin n_st = SYN_SENT; n_pas = 1'b0; n_una = iss; n_nxt = iss_p1; tx_v = 1'b1; tx_f = SYN; tx_seq = iss; end
            3'd2: begin
                if (st == LISTEN || st == SYN_SENT) n_st = CLOSED;
                else if (st == SYN_RCVD || st == ESTAB || st == CLOSE_WAIT) begin tx_v = 1'b1; tx_f = FIN | ACK; tx_seq = nxt; tx_ack = rcv; n_nxt = nxt_p1; n_st = (st == CLOSE_WAIT) ? LAST_ACK : FW1; end
            end
            3'd3: begin
                if (st == SYN_RCVD || st == ESTAB || st == FW1 || st == FW2 || st == CLOSE_WAIT) begin tx_v = 1'b1; tx_f = RST; tx_seq = nxt; end
                n_st = CLOSED;
            end
            3'd4: if (st == TIME_WAIT) n_st = CLOSED;
            default: begin
                if (st == CLOSED) begin
                    if (!s_rst) begin
                        tx_v = 1'b1;
                        if (s_ack) begin tx_f = RST; tx_seq = ack; end else begin tx_f = RST | ACK; tx_seq = 32'd0; tx_ack = seq_pseg; end
                    end
                end else if (st == LISTEN) begin
                    if (s_rst) begin end
                    else if (s_ack) begin tx_v = 1'b1; tx_f = RST; tx_seq = ack; end
                    else if (s_syn) begin n_rcv = seq_p1; n_una = nxt; n_nxt = nxt_p1; n_st = SYN_RCVD; n_pas = 1'b1; tx_v = 1'b1; tx_f = SYN | ACK; tx_seq = nxt; tx_ack = seq_p1; end
                end else if (st == SYN_SENT) begin
                    if (s_ack && !ack_in) begin if (!s_rst) begin tx_v = 1'b1; tx_f = RST; tx_seq = ack; end end
                    else if (s_rst) begin if (s_ack) n_st = CLOSED; end
                    else if (s_syn) begin
                        n_rcv = seq_p1;
                        if (s_ack) begin n_una = ack; n_st = ESTAB; tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = seq_p1; end
                        else begin n_st = SYN_RCVD; n_pas = 1'b0; tx_v = 1'b1; tx_f = SYN | ACK; tx_seq = una; tx_ack = seq_p1; end
                    end
                end else begin
                    if (!acc_ok) begin if (!s_rst) begin tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = rcv; end end
                    else if (s_rst) begin
                        if (seq_eq) n_st = (st == SYN_RCVD && pas) ? LISTEN : CLOSED;
                        else begin tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = rcv; end
                    end
                    else if (s_syn) begin tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = rcv; end
                    else if (s_ack) begin
                        if (st == SYN_RCVD) begin
                            if (ack_in) begin st2 = ESTAB; una_upd = 1'b1; end else begin tx_v = 1'b1; tx_f = RST; tx_seq = ack; stop = 1'b1; end
                        end else begin
                            if (ack_fut) begin tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = rcv; stop = 1'b1; end
                            else if (ack_in) una_upd = 1'b1;
                        end
                        if (!stop) begin
                            acked = una_upd ? ack_eq : una_eq;
                            if (st2 == FW1 && acked) st2 = FW2; else if (st2 == CLOSING && acked) st2 = TIME_WAIT; else if (st2 == LAST_ACK && acked) begin st2 = CLOSED; stop = 1'b1; end
                            if (una_upd) n_una = ack;
                            n_st = st2;
                            if (!stop) begin
                                if (st2 == ESTAB || st2 == FW1 || st2 == FW2) begin
                                    if (ln_nz) begin
                                        if (seq_eq) begin dlv = ln_le ? ln : wnd; rcv2 = ln_le ? rcv_pln : rcv_pwnd; fin_ok = ln_le; end else fin_ok = 1'b0;
                                        n_rcv = rcv2; tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = rcv2;
                                    end else fin_ok = seq_eq;
                                    if (s_fin) begin
                                        if (fin_ok) begin
                                            rcv2 = ln_nz ? rcv_pln1 : rcv_p1; n_rcv = rcv2; tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = rcv2;
                                            n_st = (st2 == ESTAB) ? CLOSE_WAIT : ((st2 == FW2) ? TIME_WAIT : CLOSING);
                                        end else if (!tx_v) begin tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = rcv; end
                                    end
                                end else if (s_fin) begin tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = rcv; end
                            end
                        end
                    end
                end
            end
        endcase
    end
endmodule
// tcp_tab2 (SPLIT = 0): 2^CIDW connections, three stages: (0) the event arrives and the RAM is read; (1) tcp_pre computes every comparison and sum from the state read and the event, and registers them; (2) tcp_sel chooses the new state and the segment, the new state is written back and the result registered. Result in the third cycle. With SPLIT = 1 the arithmetic and the comparisons are two stages (four in all, result in the fourth cycle). A second event for the SAME connection must wait until the first has been written: ev_ready is low while an event for ev_cid is in any stage (there is no bypass), so events for one connection are accepted at least 3 (SPLIT = 0) or 4 (SPLIT = 1) cycles apart; events for different connections one per cycle. After reset the RAM is cleared.
module tcp_tab2 #(parameter int CIDW = 4, parameter int SPLIT = 0) (
    input logic clk, input logic rst, output logic ev_ready,
    input logic ev_valid, input logic [CIDW-1:0] ev_cid, input logic [2:0] ev_type, input logic [3:0] ev_f, input logic [31:0] ev_seq, input logic [31:0] ev_ack, input logic [15:0] ev_len, input logic [15:0] ev_wnd, input logic [31:0] ev_iss,
    output logic r_valid, output logic [CIDW-1:0] r_cid, output logic [3:0] r_st, output logic r_pas, output logic [31:0] r_una, output logic [31:0] r_nxt, output logic [31:0] r_rcv, output logic r_txv, output logic [3:0] r_txf, output logic [31:0] r_txseq, output logic [31:0] r_txack, output logic [15:0] r_dlv);
    localparam int W = 101;
    logic [W-1:0] mem [0:(1 << CIDW) - 1]; logic [W-1:0] mem_q, sv1, sv2, nvec; logic v1, vb, v2; logic [CIDW:0] ic; logic initing;
    logic [CIDW-1:0] cid1, cidb, cid2; logic [2:0] t1, tb, t2; logic [3:0] f1, fb, f2; logic [31:0] seq1, ack1, iss1, seqb, ackb, issb, seq2, ack2, iss2; logic [15:0] len1, wnd1, lenb, wndb, len2, wnd2;
    logic [127:0] D1, Db; logic [6:0] E1, Eb; logic [255:0] S1, Sb, S2; logic [8:0] P2, Pw; logic [W-1:0] svb;
    logic [3:0] n_st; logic n_pas; logic [31:0] n_una, n_nxt, n_rcv, tx_seq, tx_ack; logic tx_v; logic [3:0] tx_f; logic [15:0] dlv;
    assign initing = !ic[CIDW];
    assign ev_ready = !initing && !(v1 && cid1 == ev_cid) && !(vb && cidb == ev_cid && SPLIT != 0) && !(v2 && cid2 == ev_cid);
    tcp_pre_a pa (.una(mem_q[95:64]), .nxt(mem_q[63:32]), .rcv(mem_q[31:0]), .f(f1), .seq(seq1), .ack(ack1), .ln(len1), .wnd(wnd1), .iss(iss1), .D(D1), .E(E1), .S(S1));
    // the comparisons: in the same stage (SPLIT = 0) or one stage later (SPLIT = 1)
    logic [127:0] Dc; logic [6:0] Ec; logic [15:0] wc; logic [8:0] Pc;
    assign Dc = (SPLIT != 0) ? Db : D1; assign Ec = (SPLIT != 0) ? Eb : E1; assign wc = (SPLIT != 0) ? wndb : wnd1;
    tcp_pre_b pb (.D(Dc), .E(Ec), .wnd(wc), .P(Pc));
    tcp_sel sel (.st(sv2[100:97]), .pas(sv2[96]), .una(sv2[95:64]), .nxt(sv2[63:32]), .rcv(sv2[31:0]), .e(t2), .f(f2), .seq(seq2), .ack(ack2), .ln(len2), .wnd(wnd2), .iss(iss2), .P(P2), .S(S2),
        .n_st(n_st), .n_pas(n_pas), .n_una(n_una), .n_nxt(n_nxt), .n_rcv(n_rcv), .tx_v(tx_v), .tx_f(tx_f), .tx_seq(tx_seq), .tx_ack(tx_ack), .dlv(dlv));
    assign nvec = {n_st, n_pas, n_una, n_nxt, n_rcv};
    logic take; assign take = ev_valid && ev_ready;
    always_ff @(posedge clk) begin
        if (rst) ic <= '0; else if (initing) ic <= ic + 1'b1;
        if (initing) mem[ic[CIDW-1:0]] <= '0; else if (v2) mem[cid2] <= nvec;
        mem_q <= mem[ev_cid];
        v1 <= take && !rst; cid1 <= ev_cid; t1 <= ev_type; f1 <= ev_f; seq1 <= ev_seq; ack1 <= ev_ack; iss1 <= ev_iss; len1 <= ev_len; wnd1 <= ev_wnd;
        // stage b (used when SPLIT = 1): the arithmetic registered
        vb <= v1 && !rst; cidb <= cid1; svb <= mem_q; tb <= t1; fb <= f1; seqb <= seq1; ackb <= ack1; issb <= iss1; lenb <= len1; wndb <= wnd1; Db <= D1; Eb <= E1; Sb <= S1;
        // stage 2: the predicates registered
        if (SPLIT != 0) begin v2 <= vb && !rst; cid2 <= cidb; sv2 <= svb; t2 <= tb; f2 <= fb; seq2 <= seqb; ack2 <= ackb; iss2 <= issb; len2 <= lenb; wnd2 <= wndb; S2 <= Sb; end
        else begin v2 <= v1 && !rst; cid2 <= cid1; sv2 <= mem_q; t2 <= t1; f2 <= f1; seq2 <= seq1; ack2 <= ack1; iss2 <= iss1; len2 <= len1; wnd2 <= wnd1; S2 <= S1; end
        P2 <= Pc;
        r_valid <= v2 && !rst; r_cid <= cid2; r_st <= n_st; r_pas <= n_pas; r_una <= n_una; r_nxt <= n_nxt; r_rcv <= n_rcv; r_txv <= tx_v; r_txf <= tx_f; r_txseq <= tx_seq; r_txack <= tx_ack; r_dlv <= dlv;
    end
endmodule
// tcp_conn_syn and tcp_tab_syn: the same designs behind a handful of pins, ONLY so that they fit a chip for the place-and-route runs. The 148-bit event is shifted in serially; the result leaves through one registered 16-bit port chosen by `sel`.
module tcp_conn_syn (input logic clk, input logic rst, input logic si, input logic sh, input logic ev_valid, input logic [3:0] sel, output logic r_valid, output logic [15:0] info);
    logic [147:0] ev; logic [3:0] r_st, r_txf; logic r_pas, r_txv; logic [31:0] r_una, r_nxt, r_rcv, r_txseq, r_txack; logic [15:0] r_dlv; logic [255:0] allb;
    always_ff @(posedge clk) if (sh) ev <= {ev[146:0], si};
    tcp_conn c (.clk(clk), .rst(rst), .ev_valid(ev_valid), .ev_type(ev[143:141]), .ev_f(ev[131:128]), .ev_seq(ev[95:64]), .ev_ack(ev[63:32]), .ev_len(ev[127:112]), .ev_wnd(ev[111:96]), .ev_iss(ev[31:0]), .r_valid(r_valid), .r_st(r_st), .r_pas(r_pas), .r_una(r_una), .r_nxt(r_nxt), .r_rcv(r_rcv), .r_txv(r_txv), .r_txf(r_txf), .r_txseq(r_txseq), .r_txack(r_txack), .r_dlv(r_dlv));
    assign allb = {70'd0, r_st, r_pas, r_txv, r_txf, r_dlv, r_una, r_nxt, r_rcv, r_txseq, r_txack}; 
    always_ff @(posedge clk) info <= allb[{sel, 4'b0000} +: 16];
endmodule
module tcp_tab_syn #(parameter int CIDW = 4, parameter int V2 = 0) (input logic clk, input logic rst, input logic si, input logic sh, input logic ev_valid, output logic ev_ready, input logic [3:0] sel, output logic r_valid, output logic [15:0] info);
    logic [147:0] ev; logic [3:0] r_st, r_txf; logic r_pas, r_txv; logic [31:0] r_una, r_nxt, r_rcv, r_txseq, r_txack; logic [15:0] r_dlv; logic [CIDW-1:0] r_cid; logic [255:0] allb;
    always_ff @(posedge clk) if (sh) ev <= {ev[146:0], si};
    if (V2 != 0) begin : g2
        tcp_tab2 #(.CIDW(CIDW), .SPLIT(V2 - 1)) t (.clk(clk), .rst(rst), .ev_ready(ev_ready), .ev_valid(ev_valid), .ev_cid(ev[132 +: CIDW]), .ev_type(ev[143:141]), .ev_f(ev[131:128]), .ev_seq(ev[95:64]), .ev_ack(ev[63:32]), .ev_len(ev[127:112]), .ev_wnd(ev[111:96]), .ev_iss(ev[31:0]),
            .r_valid(r_valid), .r_cid(r_cid), .r_st(r_st), .r_pas(r_pas), .r_una(r_una), .r_nxt(r_nxt), .r_rcv(r_rcv), .r_txv(r_txv), .r_txf(r_txf), .r_txseq(r_txseq), .r_txack(r_txack), .r_dlv(r_dlv));
    end else begin : g1
        tcp_tab #(.CIDW(CIDW)) t (.clk(clk), .rst(rst), .ev_ready(ev_ready), .ev_valid(ev_valid), .ev_cid(ev[132 +: CIDW]), .ev_type(ev[143:141]), .ev_f(ev[131:128]), .ev_seq(ev[95:64]), .ev_ack(ev[63:32]), .ev_len(ev[127:112]), .ev_wnd(ev[111:96]), .ev_iss(ev[31:0]),
            .r_valid(r_valid), .r_cid(r_cid), .r_st(r_st), .r_pas(r_pas), .r_una(r_una), .r_nxt(r_nxt), .r_rcv(r_rcv), .r_txv(r_txv), .r_txf(r_txf), .r_txseq(r_txseq), .r_txack(r_txack), .r_dlv(r_dlv));
    end
    assign allb = {{(256 - 186 - CIDW){1'b0}}, r_st, r_pas, r_txv, r_txf, r_dlv, r_una, r_nxt, r_rcv, r_txseq, r_txack, r_cid};
    always_ff @(posedge clk) info <= allb[{sel, 4'b0000} +: 16];
endmodule
// ---------------------------------------------------------------------------------------------------------------
// tcp_fast: the HOT PATH alone. A segment is handled here when the connection is ESTABLISHED, the flags are exactly ACK, the data starts at RCV.NXT and fits the window, and the ACK is not older than SND.UNA nor newer than SND.NXT. Anything else sets `punt`: the full machine (or software) must see it. For a handled segment the result is the one tcp_next would give: the state stays ESTABLISHED, SND.UNA = ack, RCV.NXT advances by the length, an ACK is sent if there was data, the length is delivered.
module tcp_fast (
    input logic [3:0] st, input logic [31:0] una, input logic [31:0] nxt, input logic [31:0] rcv, input logic [3:0] f, input logic [31:0] seq, input logic [31:0] ack, input logic [15:0] ln, input logic [15:0] wnd,
    output logic hit, output logic [31:0] n_una, output logic [31:0] n_rcv, output logic tx_v, output logic [15:0] dlv);
    logic [31:0] du, dn;
    always_comb begin
        du = ack - una; dn = nxt - una;
        hit = (st == 4'd4) && (f == 4'd2) && (seq == rcv) && (ln <= wnd) && (du <= dn);
        n_una = ack; n_rcv = rcv + {16'd0, ln}; tx_v = (ln != 16'd0); dlv = ln;
    end
endmodule
// tcp_fast_syn: tcp_fast with registered inputs and outputs behind a handful of pins (for the place-and-route runs only): the 4 + 32 x 4 + 4 + 32 x 2 + 16 x 2 input bits are shifted in serially.
module tcp_fast_syn (input logic clk, input logic si, input logic sh, output logic hit, output logic [15:0] info);
    logic [259:0] iv; logic h; logic [31:0] nu, nr; logic tv; logic [15:0] d;
    always_ff @(posedge clk) if (sh) iv <= {iv[258:0], si};
    tcp_fast u (.st(iv[259:256]), .una(iv[255:224]), .nxt(iv[223:192]), .rcv(iv[191:160]), .f(iv[159:156]), .seq(iv[155:124]), .ack(iv[123:92]), .ln(iv[91:76]), .wnd(iv[75:60]), .hit(h), .n_una(nu), .n_rcv(nr), .tx_v(tv), .dlv(d));
    always_ff @(posedge clk) begin hit <= h; info <= nu[15:0] ^ nu[31:16] ^ nr[15:0] ^ nr[31:16] ^ d ^ {15'd0, tv}; end
endmodule
