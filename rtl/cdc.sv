// verilator lint_off DECLFILENAME
// Chapter 3: the clock-domain-crossing circuits. All use cdc_sync (rtl/cdc_sync.sv) for the crossing itself.
// cdc_naive_pulse: a one-cycle pulse sent through a plain two-flop synchronizer. A pulse shorter than the destination clock period can be missed entirely.
module cdc_naive_pulse (input logic aclk, input logic bclk, input logic a_pulse, output logic b_pulse);
    logic a_q = 1'b0, b_sync, b_prev = 1'b0;                        // initial values: the FPGA loads them at configuration
    always_ff @(posedge aclk) a_q <= a_pulse;                      // the source flip-flop
    cdc_sync #(1) s (.clk(bclk), .d(a_q), .q(b_sync));
    always_ff @(posedge bclk) b_prev <= b_sync;
    assign b_pulse = b_sync && !b_prev;                            // rising edge of the synchronized level
endmodule
// cdc_toggle_pulse: the pulse becomes a TOGGLE (every pulse flips a flip-flop); the level is synchronized; an edge detector in the destination turns each change back into one pulse. Pulses must be at least three destination clocks apart (the toggle must settle before the next).
module cdc_toggle_pulse (input logic aclk, input logic bclk, input logic a_pulse, output logic b_pulse);
    logic tog = 1'b0, b_sync, b_prev = 1'b0;
    always_ff @(posedge aclk) tog <= tog ^ a_pulse;
    cdc_sync #(1) s (.clk(bclk), .d(tog), .q(b_sync));
    always_ff @(posedge bclk) b_prev <= b_sync;
    assign b_pulse = b_sync ^ b_prev;
endmodule
// cdc_rst_sync: reset ASSERTS at once (asynchronously) and RELEASES synchronously: the release is delayed to a clock edge, two edges after the asynchronous input is released, so that every flip-flop in the domain leaves reset in the same cycle and none sees the release too close to an edge.
module cdc_rst_sync (input logic clk, input logic arst_n, output logic rst_n);
    logic q1;
    always_ff @(posedge clk or negedge arst_n) begin
        if (!arst_n) begin q1 <= 1'b0; rst_n <= 1'b0; end
        else begin q1 <= 1'b1; rst_n <= q1; end
    end
endmodule
// gray2bin: Gray code to binary (each binary bit is the XOR of all the Gray bits above it and itself).
module gray2bin #(parameter int W = 4) (input logic [W-1:0] g, output logic [W-1:0] b);
    always_comb begin
        b[W-1] = g[W-1];
        for (int i = W - 2; i >= 0; i--) b[i] = b[i + 1] ^ g[i];
    end
endmodule
// cdc_afifo: an asynchronous FIFO: data written in the wclk domain, read in the rclk domain. DEPTH = 2^AW. The write and read pointers are AW+1 bits (the extra bit tells full from empty). The pointers cross to the other domain through cdc_sync; with GRAY = 1 they are crossed in Gray code (only one bit changes per step, so a bit caught mid-change gives the old or the new pointer, never a wrong one); with GRAY = 0 they cross as plain binary, which is WRONG for a bus (kept to show the failure).
// The pointer that crosses is a flip-flop (wptr, rptr), loaded with the Gray code of the NEXT binary pointer: if the Gray code were computed from the binary pointer by gates in front of the synchronizer, the gates could glitch several bits at once and the single-bit-change property would be lost (the first version of this file did that, and Section 3.7 shows the failure).
// full is computed in the write domain from the write pointer and the synchronized read pointer; empty in the read domain. Both are conservative: they may assert a little late in the opposite sense (full a little too long, empty a little too long) but never allow an overflow or an underflow. Read data is available whenever empty is 0 (first-word fall-through).
module cdc_afifo #(parameter int W = 8, parameter int AW = 3, parameter bit GRAY = 1'b1, parameter bit REG = 1'b1) (
    input logic wclk, input logic wrst_n, input logic wr_en, input logic [W-1:0] wr_data, output logic full,
    input logic rclk, input logic rrst_n, input logic rd_en, output logic [W-1:0] rd_data, output logic empty,
    output logic [AW:0] wlevel, output logic [AW:0] rlevel);   // wlevel: the words the WRITE side believes are inside; rlevel: the words the READ side believes are inside (both come from the synchronized far pointer)
    localparam int DEPTH = 1 << AW;
    logic [W-1:0] mem [DEPTH];
    logic [AW:0] wbin, rbin, wptr, rptr, wptr_s, rptr_s, wptr_r, rptr_r;           // binary pointers, the form sent across, and the received forms
    logic [AW:0] wbin_n, rbin_n;                                   // the pointers after this edge
    logic do_wr, do_rd;
    // REG = 0 keeps the unregistered version (encoder gates between the binary counter and the synchronizer) to show why it fails; never use it.
    assign wptr = REG ? wptr_r : (GRAY ? (wbin ^ (wbin >> 1)) : wbin);
    assign rptr = REG ? rptr_r : (GRAY ? (rbin ^ (rbin >> 1)) : rbin);
    assign do_wr = wr_en && !full;
    assign do_rd = rd_en && !empty;
    assign wbin_n = wbin + {{AW{1'b0}}, do_wr};
    assign rbin_n = rbin + {{AW{1'b0}}, do_rd};
    cdc_sync #(AW + 1) w2r (.clk(rclk), .d(wptr), .q(wptr_s));
    cdc_sync #(AW + 1) r2w (.clk(wclk), .d(rptr), .q(rptr_s));
    logic [AW:0] wptr_b, rptr_b;                                   // the far pointers converted back to binary
    gray2bin #(AW + 1) g2b_w (.g(wptr_s), .b(wptr_b));
    gray2bin #(AW + 1) g2b_r (.g(rptr_s), .b(rptr_b));
    assign rlevel = (GRAY ? wptr_b : wptr_s) - rbin;           // what the reader may count on: it must never exceed the true occupancy
    assign wlevel = wbin - (GRAY ? rptr_b : rptr_s);           // what the writer assumes is used: it must never be below the true occupancy
    assign empty = (rptr == wptr_s);
    assign full = GRAY ? (wptr == {~rptr_s[AW:AW-1], rptr_s[AW-2:0]}) : ((wptr[AW] != rptr_s[AW]) && (wptr[AW-1:0] == rptr_s[AW-1:0]));
    always_ff @(posedge wclk) begin
        if (!wrst_n) begin wbin <= '0; wptr_r <= '0; end
        else begin
            if (do_wr) mem[wbin[AW-1:0]] <= wr_data;
            wbin <= wbin_n;
            wptr_r <= GRAY ? (wbin_n ^ (wbin_n >> 1)) : wbin_n;      // the form that crosses is REGISTERED: a flip-flop output, never the output of an encoder that can glitch
        end
    end
    always_ff @(posedge rclk) begin
        if (!rrst_n) begin rbin <= '0; rptr_r <= '0; end
        else begin
            rbin <= rbin_n;
            rptr_r <= GRAY ? (rbin_n ^ (rbin_n >> 1)) : rbin_n;
        end
    end
    assign rd_data = mem[rbin[AW-1:0]];
endmodule
