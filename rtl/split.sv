// verilator lint_off DECLFILENAME
// Chapter 15: the hot path and the cold path of TCP. tcp_split keeps, for each of 2^CIDW connections, the state variables of Chapter 12 and a count of the events that software still owes it. Each cycle at most one event arrives:
//   * a SEGMENT for a connection with nothing pending that tcp_fast (Chapter 12) accepts is handled HERE, in this cycle: SND.UNA and RCV.NXT are updated, the ACK is produced, the bytes are delivered;
//   * anything else (an application command, a segment the hot path does not take, or ANY event for a connection that already has events pending) is PUNTED to software: it enters a FIFO together with a snapshot of the connection's state and a flag `first` (nothing was pending, so software must load the snapshot);
//   * software pops the FIFO (pq_valid / pq_data / pq_pop), runs the full state machine, and WRITES BACK the new state (wb_*); the write-back is what decrements the count. While the count is not zero every event of the connection goes to software, so the order of events per connection is the order of arrival.
// If the FIFO is full and the event must be punted: POLICY 0 holds it (ev_ready = 0: the events behind it wait, whatever their connection: head-of-line blocking), POLICY 1 drops it (path 2; TCP's retransmission must recover).
// One event per cycle, one write-back per cycle, results registered. The table is registers (CIDW <= 6), read and written in the same cycle. The behaviour is that of model/split_gold.py, cycle for cycle.
module tcp_split #(parameter int CIDW = 3, parameter int DEPTH = 4, parameter int POLICY = 0, localparam int PW = CIDW + 3 + 4 + 32 + 32 + 16 + 16 + 32 + 4 + 1 + 96 + 1) (
    input logic clk, input logic rst,
    input logic ev_valid, input logic [CIDW-1:0] ev_cid, input logic [2:0] ev_type, input logic [3:0] ev_f, input logic [31:0] ev_seq, input logic [31:0] ev_ack, input logic [15:0] ev_ln, input logic [15:0] ev_wnd, input logic [31:0] ev_iss,
    output logic ev_ready,
    output logic r_valid, output logic [CIDW-1:0] r_cid, output logic [1:0] r_path, output logic r_txv, output logic [3:0] r_txf, output logic [31:0] r_txseq, output logic [31:0] r_txack, output logic [15:0] r_dlv,
    output logic pq_valid, output logic [PW-1:0] pq_data, input logic pq_pop,
    input logic wb_valid, input logic [CIDW-1:0] wb_cid, input logic [3:0] wb_st, input logic wb_pas, input logic [31:0] wb_una, input logic [31:0] wb_nxt, input logic [31:0] wb_rcv);
    localparam int N = 1 << CIDW;
    // an entry: cid, type, f, seq, ack, ln, wnd, iss, state, passive, una, nxt, rcv, first
    localparam int PTRW = $clog2(DEPTH), CNTW = $clog2(DEPTH + 1);
    logic [3:0] t_st [N]; logic t_pas [N]; logic [31:0] t_una [N]; logic [31:0] t_nxt [N]; logic [31:0] t_rcv [N]; logic [3:0] t_cnt [N];
    logic [PW-1:0] mem [DEPTH]; logic [CNTW-1:0] count; logic [PTRW-1:0] rd, wr;
    logic [3:0] st, cnt; logic pas; logic [31:0] una, nxt, rcv; logic hit_raw, hot, punt, full, consumed, pushed, drop, tx_v_i; logic [31:0] n_una_f, n_rcv_f; logic [15:0] dlv_f; logic txv_f;
    tcp_fast fast (.st(st), .una(una), .nxt(nxt), .rcv(rcv), .f(ev_f), .seq(ev_seq), .ack(ev_ack), .ln(ev_ln), .wnd(ev_wnd), .hit(hit_raw), .n_una(n_una_f), .n_rcv(n_rcv_f), .tx_v(txv_f), .dlv(dlv_f));
    always_comb begin
        st = t_st[ev_cid]; pas = t_pas[ev_cid]; una = t_una[ev_cid]; nxt = t_nxt[ev_cid]; rcv = t_rcv[ev_cid]; cnt = t_cnt[ev_cid];
        full = (count == CNTW'(DEPTH));
        hot = ev_valid && (ev_type == 3'd5) && (cnt == 4'd0) && hit_raw;
        punt = ev_valid && !hot;
        ev_ready = (POLICY == 0) ? !(punt && full) : 1'b1;
        consumed = ev_valid && ev_ready;
        pushed = consumed && punt && !full;
        drop = consumed && punt && full;
        tx_v_i = txv_f;
        pq_valid = (count != '0); pq_data = mem[rd];
    end
    logic [PW-1:0] entry;
    always_comb entry = {ev_cid, ev_type, ev_f, ev_seq, ev_ack, ev_ln, ev_wnd, ev_iss, st, pas, una, nxt, rcv, (cnt == 4'd0)};
    logic pop_ok; always_comb pop_ok = pq_pop && pq_valid;
    always_ff @(posedge clk) begin
        r_valid <= 1'b0; r_cid <= ev_cid; r_path <= 2'd0; r_txv <= 1'b0; r_txf <= 4'd0; r_txseq <= 32'd0; r_txack <= 32'd0; r_dlv <= 16'd0;
        if (rst) begin
            count <= '0; rd <= '0; wr <= '0;
            for (int i = 0; i < N; i++) begin t_st[i] <= 4'd0; t_pas[i] <= 1'b0; t_una[i] <= 32'd0; t_nxt[i] <= 32'd0; t_rcv[i] <= 32'd0; t_cnt[i] <= 4'd0; end
        end else begin
            r_valid <= consumed;
            if (consumed) begin
                r_path <= hot ? 2'd0 : (drop ? 2'd2 : 2'd1);
                if (hot) begin r_txv <= tx_v_i; r_txf <= tx_v_i ? 4'd2 : 4'd0; r_txseq <= tx_v_i ? nxt : 32'd0; r_txack <= tx_v_i ? n_rcv_f : 32'd0; r_dlv <= dlv_f; end
            end
            if (hot) t_rcv[ev_cid] <= n_rcv_f;                                   // only RCV.NXT moves: in ESTABLISHED the machine of Chapter 12 has SND.UNA = SND.NXT (it sends no data), so the ACK number tcp_fast would store is the one already there
            if (pushed) begin mem[wr] <= entry; wr <= (wr == PTRW'(DEPTH - 1)) ? '0 : wr + PTRW'(1); t_cnt[ev_cid] <= cnt + 4'd1; end
            if (pop_ok) rd <= (rd == PTRW'(DEPTH - 1)) ? '0 : rd + PTRW'(1);
            count <= count + CNTW'(pushed) - CNTW'(pop_ok);
            if (wb_valid) begin
                t_st[wb_cid] <= wb_st; t_pas[wb_cid] <= wb_pas; t_una[wb_cid] <= wb_una; t_nxt[wb_cid] <= wb_nxt; t_rcv[wb_cid] <= wb_rcv;
                t_cnt[wb_cid] <= t_cnt[wb_cid] - 4'd1 + ((pushed && ev_cid == wb_cid) ? 4'd1 : 4'd0);
            end
        end
    end
endmodule
// tcp_split_syn: the same design behind a handful of pins, ONLY so that it fits a chip for the place-and-route runs: the inputs are shifted in serially, the outputs are folded into one registered 16-bit word.
module tcp_split_syn #(parameter int CIDW = 3, parameter int DEPTH = 4, parameter int POLICY = 0) (input logic clk, input logic rst, input logic si, input logic sh, output logic [15:0] info);
    localparam int PW = CIDW + 3 + 4 + 32 + 32 + 16 + 16 + 32 + 4 + 1 + 96 + 1;
    logic [CIDW+3+4+32+32+16+16+32+1+1+CIDW+4+1+96+1-1:0] iv; logic ev_ready, r_valid, r_txv, pq_valid; logic [CIDW-1:0] r_cid; logic [1:0] r_path; logic [3:0] r_txf; logic [31:0] r_txseq, r_txack; logic [15:0] r_dlv; logic [PW-1:0] pq_data;
    always_ff @(posedge clk) if (sh) iv <= {iv[$bits(iv)-2:0], si};
    tcp_split #(.CIDW(CIDW), .DEPTH(DEPTH), .POLICY(POLICY)) u (.clk(clk), .rst(rst), .ev_valid(iv[0]), .ev_cid(iv[CIDW:1]), .ev_type(iv[CIDW+3:CIDW+1]), .ev_f(iv[CIDW+7:CIDW+4]), .ev_seq(iv[CIDW+39:CIDW+8]), .ev_ack(iv[CIDW+71:CIDW+40]), .ev_ln(iv[CIDW+87:CIDW+72]), .ev_wnd(iv[CIDW+103:CIDW+88]), .ev_iss(iv[CIDW+135:CIDW+104]),
        .ev_ready(ev_ready), .r_valid(r_valid), .r_cid(r_cid), .r_path(r_path), .r_txv(r_txv), .r_txf(r_txf), .r_txseq(r_txseq), .r_txack(r_txack), .r_dlv(r_dlv), .pq_valid(pq_valid), .pq_data(pq_data), .pq_pop(iv[CIDW+136]),
        .wb_valid(iv[CIDW+137]), .wb_cid(iv[2*CIDW+137:CIDW+138]), .wb_st(iv[2*CIDW+141:2*CIDW+138]), .wb_pas(iv[2*CIDW+142]), .wb_una(iv[2*CIDW+174:2*CIDW+143]), .wb_nxt(iv[2*CIDW+206:2*CIDW+175]), .wb_rcv(iv[2*CIDW+238:2*CIDW+207]));
    logic [15:0] pf; logic [15:0] mix;
    always_comb begin pf = 16'd0; for (int k = 0; k < PW; k += 16) pf ^= 16'(pq_data >> k); mix = r_dlv ^ r_txseq[15:0] ^ r_txseq[31:16] ^ r_txack[15:0] ^ r_txack[31:16] ^ {r_txf, r_path, r_txv, r_valid, ev_ready, pq_valid, 6'd0} ^ 16'(r_cid); end
    always_ff @(posedge clk) info <= mix ^ pf;
endmodule
