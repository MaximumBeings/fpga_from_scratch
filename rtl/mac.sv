// verilator lint_off DECLFILENAME
// verilator lint_off UNUSEDSIGNAL
// Chapter 8: the MAC datapath at the byte interface (GMII style: one byte per clock). Needs rtl/crc32_stream.sv (crc32_comb, Chapter 7) and rtl/cdc.sv + rtl/cdc_sync.sv (cdc_afifo, Chapter 3).
// AXI-Stream conventions used: (valid, data, last) with ready where a stage can stall; an RX MAC cannot stall the wire, so its output has NO ready.
//
// mac_rx: PHY bytes -> frame bytes. Finds the start (>= 1 byte 0x55 then 0xD5 within one rx_dv run; anything else in the run is ignored), removes the FCS with a four-byte delay line, checks the FCS by running the CRC over all bytes after the SFD and comparing with the residue, and marks the LAST byte of the frame with m_bad = (rx_er seen) | (length outside 64..1522 including FCS) | (FCS wrong). A frame of four bytes or fewer after the SFD produces no output. Output is one cycle behind the held byte so that the end of the frame (rx_dv falling) can mark it.
module mac_rx (
    input logic clk, input logic rst, input logic rx_dv, input logic rx_er, input logic [7:0] rxd,
    output logic m_valid, output logic [7:0] m_data, output logic m_last, output logic m_bad);
    typedef enum logic [1:0] {IDLE, PRE, DATA, IGN} st_t;
    st_t st;
    logic [7:0] d0, d1, d2, d3, held_d; logic held_v; logic [11:0] cnt; logic [31:0] crc, nx; logic ersn;
    crc32_comb ucrc (.c(crc), .d({56'd0, rxd}), .k(4'd1), .n(nx));
    logic bad_now;
    assign bad_now = ersn || (cnt < 12'd64) || (cnt > 12'd1522) || (crc != 32'hDEBB20E3);   // crc is the un-inverted register: ~0x2144DF1C
    always_ff @(posedge clk) begin
        m_valid <= 1'b0; m_last <= 1'b0; m_bad <= 1'b0;
        if (rst) begin st <= IDLE; held_v <= 1'b0; cnt <= '0; ersn <= 1'b0; crc <= 32'hFFFFFFFF; end
        else case (st)
            IDLE: if (rx_dv) st <= (rxd == 8'h55) ? PRE : IGN;
            PRE: if (!rx_dv) st <= IDLE;
                 else if (rxd == 8'h55) st <= PRE;
                 else if (rxd == 8'hD5) begin st <= DATA; cnt <= '0; ersn <= 1'b0; crc <= 32'hFFFFFFFF; held_v <= 1'b0; end
                 else st <= IGN;
            IGN: if (!rx_dv) st <= IDLE;
            DATA: begin
                if (rx_dv) begin
                    if (cnt != 12'hFFF) cnt <= cnt + 12'd1;
                    ersn <= ersn | rx_er; crc <= nx;
                    d0 <= rxd; d1 <= d0; d2 <= d1; d3 <= d2;
                    if (cnt >= 12'd4) begin
                        if (held_v) begin m_valid <= 1'b1; m_data <= held_d; end
                        held_v <= 1'b1; held_d <= d3;
                    end
                end else begin
                    if (held_v) begin m_valid <= 1'b1; m_data <= held_d; m_last <= 1'b1; m_bad <= bad_now; end
                    held_v <= 1'b0; st <= IDLE;
                end
            end
            default: st <= IDLE;
        endcase
    end
endmodule
// frame_fifo: a store-and-forward FRAME buffer in one clock domain: bytes are written into a memory with a registered (synchronous) read, which an FPGA places in block RAM (the style Chapter 5 measured). A frame becomes visible to the reader only when its last byte has been written and was not marked bad: a bad frame, or a frame that did not fit, is rolled back by moving the write pointer back to the commit pointer. The read side is first-word fall-through built on the synchronous read: the output register is loaded from mem[ra] each clock with ra = rptr (or rptr + 1 when the current byte is being taken); a frame is visible one cycle after its commit (cptr_r) so that the byte loaded in the commit cycle is not stale (a synchronous read of an address being written returns the old data).
// The write side accepts every offered byte (in_ready is information for a source that can wait): a byte offered while the buffer is full starts a drop of the whole frame. Counters: ok (committed), bad (rolled back because in_bad), ovf (rolled back because it did not fit).
module frame_fifo #(parameter int AW = 11) (
    input logic clk, input logic rst, input logic in_valid, input logic [7:0] in_data, input logic in_last, input logic in_bad, output logic in_ready,
    output logic out_valid, output logic [7:0] out_data, output logic out_last, input logic out_ready,
    output logic [15:0] n_ok, output logic [15:0] n_bad, output logic [15:0] n_ovf);
    logic [8:0] mem [1 << AW];
    logic [AW-1:0] wptr, cptr, cptr_r, rptr, ra; logic dropping; logic [8:0] q;
    logic full;
    assign full = (wptr + 1'b1) == rptr;
    assign in_ready = !full && !dropping;
    assign ra = (out_valid && out_ready) ? rptr + 1'b1 : rptr;
    assign out_valid = (rptr != cptr_r);
    assign out_data = q[7:0]; assign out_last = q[8];
    always_ff @(posedge clk) begin
        q <= mem[ra]; rptr <= rst ? '0 : ra; cptr_r <= rst ? '0 : cptr;
        if (rst) begin wptr <= '0; cptr <= '0; dropping <= 1'b0; n_ok <= '0; n_bad <= '0; n_ovf <= '0; end
        else if (in_valid) begin
            if (dropping || full) begin
                if (in_last) begin wptr <= cptr; dropping <= 1'b0; if (in_bad && !dropping && !full) n_bad <= n_bad + 1'b1; else n_ovf <= n_ovf + 1'b1; end
                else dropping <= 1'b1;
            end else begin
                mem[wptr] <= {in_last, in_data};
                if (in_last) begin
                    if (in_bad) begin wptr <= cptr; n_bad <= n_bad + 1'b1; end
                    else begin wptr <= wptr + 1'b1; cptr <= wptr + 1'b1; n_ok <= n_ok + 1'b1; end
                end else wptr <= wptr + 1'b1;
            end
        end
    end
endmodule
// mac_rx_path: the receive path across a clock boundary. mac_rx runs in the PHY clock and cannot be stalled, so its bytes go into an asynchronous FIFO (Chapter 3) of {bad, last, data}; the core side drains it at one byte per core clock into frame_fifo. If the asynchronous FIFO is full when a byte arrives the byte is lost; the frame must then not be delivered: the writer remembers the loss and forces bad on the frame's last byte, or, if the last byte itself was lost, writes a terminating {bad, last} byte as soon as there is room. The loss counter counts lost bytes.
module mac_rx_path #(parameter int AW = 11, parameter int CAW = 4) (
    input logic rx_clk, input logic rx_rst_n, input logic rx_dv, input logic rx_er, input logic [7:0] rxd,
    input logic core_clk, input logic core_rst_n,
    output logic o_valid, output logic [7:0] o_data, output logic o_last, input logic o_ready,
    output logic [15:0] n_ok, output logic [15:0] n_bad, output logic [15:0] n_ovf, output logic [15:0] n_lost);
    logic m_valid, m_last, m_bad; logic [7:0] m_data; logic rst_rx;
    assign rst_rx = !rx_rst_n;
    mac_rx u_rx (.clk(rx_clk), .rst(rst_rx), .rx_dv(rx_dv), .rx_er(rx_er), .rxd(rxd), .m_valid(m_valid), .m_data(m_data), .m_last(m_last), .m_bad(m_bad));
    logic af_full, af_empty, lost, fix, wr; logic [9:0] wd, rd; logic [CAW:0] wl, rl;                // wl, rl: the FIFO's occupancy beliefs, unused here
    always_comb begin
        wr = 1'b0; wd = {m_bad | lost, m_last, m_data};
        if (fix && !af_full) begin wr = 1'b1; wd = {1'b1, 1'b1, 8'd0}; end
        else if (m_valid && !af_full && !fix) wr = 1'b1;
    end
    always_ff @(posedge rx_clk) begin
        if (rst_rx) begin lost <= 1'b0; fix <= 1'b0; n_lost <= '0; end
        else begin
            if (m_valid && (af_full || fix)) begin n_lost <= n_lost + 1'b1; lost <= 1'b1; if (m_last) fix <= 1'b1; end
            if (fix && !af_full) begin fix <= m_valid && m_last; lost <= m_valid; end
            else if (m_valid && !af_full && !fix && m_last) lost <= 1'b0;
        end
    end
    cdc_afifo #(.W(10), .AW(CAW)) u_af (.wclk(rx_clk), .wrst_n(rx_rst_n), .wr_en(wr), .wr_data(wd), .full(af_full),
        .rclk(core_clk), .rrst_n(core_rst_n), .rd_en(!af_empty), .rd_data(rd), .empty(af_empty), .wlevel(wl), .rlevel(rl));
    logic in_ready_unused;
    frame_fifo #(.AW(AW)) u_ff (.clk(core_clk), .rst(!core_rst_n), .in_valid(!af_empty), .in_data(rd[7:0]), .in_last(rd[8]), .in_bad(rd[9]), .in_ready(in_ready_unused),
        .out_valid(o_valid), .out_data(o_data), .out_last(o_last), .out_ready(o_ready), .n_ok(n_ok), .n_bad(n_bad), .n_ovf(n_ovf));
endmodule
// mac_tx: frame bytes -> PHY bytes. Reads a COMMITTED frame from a frame_fifo (so every byte of the frame is available in consecutive cycles: a PHY cannot be paused), sends 7 x 0x55, 0xD5, the frame, zero padding up to 60 bytes, the FCS (CRC-32, inverted, low byte first), then leaves 12 idle cycles. If the source runs dry inside a frame (it cannot happen behind a frame_fifo) the sticky flag underrun is set.
module mac_tx (
    input logic clk, input logic rst, input logic f_valid, input logic [7:0] f_data, input logic f_last, output logic f_ready,
    output logic tx_en, output logic [7:0] txd, output logic underrun);
    typedef enum logic [2:0] {IDLE, PRE, SFD, DATA, PAD, FCS} st_t;
    st_t st; logic [3:0] gap; logic [2:0] k; logic [11:0] len; logic [31:0] crc, nx; logic [7:0] bytein;
    assign f_ready = (st == DATA);
    assign bytein = (st == PAD) ? 8'd0 : f_data;
    crc32_comb ucrc (.c(crc), .d({56'd0, bytein}), .k(4'd1), .n(nx));
    always_ff @(posedge clk) begin
        if (rst) begin st <= IDLE; gap <= 4'd0; tx_en <= 1'b0; txd <= 8'd0; underrun <= 1'b0; k <= 3'd0; len <= '0; crc <= 32'hFFFFFFFF; end
        else case (st)
            IDLE: begin
                tx_en <= 1'b0;
                if (gap != 4'd0) gap <= gap - 4'd1;
                else if (f_valid) begin st <= PRE; k <= 3'd0; end
            end
            PRE: begin tx_en <= 1'b1; txd <= 8'h55; if (k == 3'd6) st <= SFD; k <= k + 3'd1; end
            SFD: begin tx_en <= 1'b1; txd <= 8'hD5; st <= DATA; crc <= 32'hFFFFFFFF; len <= '0; end
            DATA: begin
                tx_en <= 1'b1;
                if (f_valid) begin
                    txd <= f_data; crc <= nx; len <= len + 12'd1;
                    if (f_last) begin st <= (len + 12'd1 < 12'd60) ? PAD : FCS; k <= 3'd0; end
                end else begin underrun <= 1'b1; txd <= 8'd0; crc <= nx; st <= FCS; k <= 3'd0; end
            end
            PAD: begin tx_en <= 1'b1; txd <= 8'd0; crc <= nx; len <= len + 12'd1; if (len + 12'd1 >= 12'd60) begin st <= FCS; k <= 3'd0; end end
            FCS: begin
                tx_en <= 1'b1; txd <= (k == 3'd0) ? ~crc[7:0] : (k == 3'd1) ? ~crc[15:8] : (k == 3'd2) ? ~crc[23:16] : ~crc[31:24];
                k <= k + 3'd1; if (k == 3'd3) begin st <= IDLE; gap <= 4'd11; end
            end
            default: st <= IDLE;
        endcase
    end
endmodule
// mac_tx_path: a frame source (AXI-Stream with ready) -> frame_fifo -> mac_tx. s_ready is the buffer's in_ready: a frame larger than the buffer would deadlock (the source waits for space that only a COMMITTED frame can free), so the buffer must hold the largest frame (AW >= 11 for 1522 bytes).
module mac_tx_path #(parameter int AW = 11) (
    input logic clk, input logic rst, input logic s_valid, input logic [7:0] s_data, input logic s_last, output logic s_ready,
    output logic tx_en, output logic [7:0] txd, output logic underrun, output logic [15:0] n_ok, output logic [15:0] n_ovf);
    logic f_valid, f_last, f_ready; logic [7:0] f_data; logic [15:0] nb;
    frame_fifo #(.AW(AW)) u_ff (.clk(clk), .rst(rst), .in_valid(s_valid && s_ready), .in_data(s_data), .in_last(s_last), .in_bad(1'b0), .in_ready(s_ready),
        .out_valid(f_valid), .out_data(f_data), .out_last(f_last), .out_ready(f_ready), .n_ok(n_ok), .n_bad(nb), .n_ovf(n_ovf));
    mac_tx u_tx (.clk(clk), .rst(rst), .f_valid(f_valid), .f_data(f_data), .f_last(f_last), .f_ready(f_ready), .tx_en(tx_en), .txd(txd), .underrun(underrun));
endmodule
