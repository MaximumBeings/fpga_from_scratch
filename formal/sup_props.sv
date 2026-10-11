// Chapter 27: formal properties of the supervisor, for Yosys's SAT engine. The wrapper drives sup with FREE inputs (a go, a trip, a feed byte, the slot, the tracker's fault, any session state, the transmitter's readiness, quiet, and a reset, in every cycle) and keeps its own account, written without the supervisor's counters: shadow counters of consecutive silent cycles and consecutive held-slot cycles, a shadow of "was a logout offered". It asserts, in every cycle:
//   S1  (absorbing)  a SAFE cycle is followed by a SAFE cycle unless the reset was applied;
//   S2  (entry)      RUN is entered only from READY, by a `go` with the session ACTIVE;
//   S3  (causes)     a RUN cycle in which the trip, the tracker's fault or a non-ACTIVE session was seen is followed by SAFE;
//   S4  (detection, exact)  in a RUN cycle the shadow counts of silent cycles and of held-slot cycles are at least FT (resp. ST) exactly when the supervisor leaves RUN for that cause in the next cycle: it neither trips early nor late;
//   S5  (kill)       kill is high in every state but RUN, low in RUN;
//   S6  (logout)     the logout request is offered only in SAFE, with the session ACTIVE, the transmitter ready and nothing in flight, and at most once between resets;
//   S7  (warm-up)    the state is INIT for exactly WARM cycles after a reset.
// The contract, assumed: the reset is applied in the first cycle.
module sup_props (input logic clk, input logic rst_x, input logic go, input logic trip, input logic feed, input logic slot, input logic fault, input logic [2:0] sess, input logic tx_ready, input logic quiet);
    localparam int FT = 4, ST = 3, WARM = 2;
    logic first = 1'b1; logic rst; always @(*) rst = first ? 1'b1 : rst_x;
    logic [1:0] state; logic kill, cq_valid; logic [4:0] cause;
    sup #(.FT(FT), .ST(ST), .WARM(WARM)) dut (.clk(clk), .rst(rst), .go(go), .trip(trip), .feed(feed), .slot(slot), .fault(fault), .sess(sess), .tx_ready(tx_ready), .quiet(quiet), .state(state), .kill(kill), .cq_valid(cq_valid), .cause(cause));
    // the wrapper's own account
    logic [1:0] p_state; logic p_rst, p_go, p_trip, p_fault; logic [2:0] p_sess; logic p_v; logic [7:0] sil, held, wup, p_sil, p_held; logic sent_sh;
    always @(posedge clk) begin
        first <= 1'b0; p_v <= 1'b1; p_sil <= sil; p_held <= held; p_state <= state; p_rst <= rst; p_go <= go; p_trip <= trip; p_fault <= fault; p_sess <= sess;
        sil <= (rst || state != 2'd2) ? 8'd0 : (feed ? 8'd0 : sil + 8'd1);
        held <= (rst || state != 2'd2) ? 8'd0 : (slot ? held + 8'd1 : 8'd0);
        wup <= rst ? 8'd1 : (wup + 8'd1);
        sent_sh <= rst ? 1'b0 : (sent_sh || cq_valid);
        if (p_v && !p_rst) begin
            if (p_state == 2'd3) assert (state == 2'd3);                                                                    // S1
            if (state == 2'd2 && p_state != 2'd2) assert (p_state == 2'd1 && p_go && p_sess == 3'd2);                       // S2
            if (p_state == 2'd2 && (p_trip || p_fault || p_sess != 3'd2)) assert (state == 2'd3);                           // S3
            if (p_state == 2'd2 && (p_sil >= 8'(FT) || p_held >= 8'(ST))) assert (state == 2'd3);                           // S4: not late
            if (p_state == 2'd2 && state == 2'd3) begin if (cause[0]) assert (p_sil >= 8'(FT)); if (cause[1]) assert (p_held >= 8'(ST)); end   // S4: not early
        end
        if (p_v) begin
            assert (kill == (state != 2'd2));                                                                               // S5
            if (cq_valid) assert (state == 2'd3 && sess == 3'd2 && tx_ready && quiet && !sent_sh);                           // S6
            if (!p_rst && !rst) begin if (wup <= 8'(WARM)) assert (state == 2'd0); else if (wup == 8'(WARM + 1)) assert (state != 2'd0); end   // S7
        end
    end
endmodule
