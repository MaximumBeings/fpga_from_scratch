// Chapter 27: the supervisor. A state machine around the wire-to-wire design that decides whether orders may leave: INIT (after reset: wait WARM cycles for the units to finish clearing their RAMs), READY (warm, waiting for the control plane's `go` and an ACTIVE session), RUN (orders may leave), SAFE (an unexplained thing happened: the gate is killed, the session is logged out once, and nothing leaves the state except a reset). In RUN, five things send it to SAFE: the feed is silent for FT cycles, the strategy slot is held for ST cycles (a stalled pipeline), the tracker's fault, the session leaving ACTIVE, and an external trip. `kill` is high in every state but RUN. The cause of the first trip is latched (a bit per cause, all that were true in that cycle). The logout (`cq`) is offered once, when nothing is in flight and the transmitter is ready, because a request offered while an order's answer is being sent would overwrite it. The specification is in model/sup_gold.py.
module sup #(parameter int FT = 100, parameter int ST = 100, parameter int WARM = 48) (
    input  logic clk, input logic rst,
    input  logic go, input logic trip, input logic feed, input logic slot, input logic fault, input logic [2:0] sess, input logic tx_ready, input logic quiet,
    output logic [1:0] state, output logic kill, output logic cq_valid, output logic [4:0] cause);
    localparam logic [1:0] INIT = 2'd0, READY = 2'd1, RUN = 2'd2, SAFE = 2'd3;
    localparam logic [2:0] ACTIVE = 3'd2;
    localparam int CW = $clog2((FT > ST ? FT : ST) + 2) > $clog2(WARM + 2) ? $clog2((FT > ST ? FT : ST) + 2) : $clog2(WARM + 2);
    logic [CW-1:0] cnt, fc, sc; logic sent;
    wire f_t = (fc >= CW'(FT)), s_t = (sc >= CW'(ST)), x_f = fault, x_s = (sess != ACTIVE), x_t = trip;
    wire [4:0] now = {x_s, x_f, x_t, s_t, f_t};
    assign kill = (state != RUN);
    assign cq_valid = (state == SAFE) && !sent && (sess == ACTIVE) && tx_ready && quiet;
    always_ff @(posedge clk) begin
        if (rst) begin state <= INIT; cnt <= '0; fc <= '0; sc <= '0; sent <= 1'b0; cause <= '0; end
        else begin
            case (state)
                INIT: begin cnt <= cnt + 1'b1; if (cnt + 1'b1 >= CW'(WARM)) state <= READY; end
                READY: if (go && sess == ACTIVE) state <= RUN;                                       // fc and sc are 0 here: nothing counts outside RUN, and a reset clears them
                RUN: begin
                    fc <= feed ? '0 : fc + 1'b1; sc <= slot ? sc + 1'b1 : '0;                      // no saturation: a count that reaches its limit leaves RUN in the next cycle
                    if (now != 5'd0) begin state <= SAFE; cause <= now; end
                end
                default: if (cq_valid) sent <= 1'b1;
            endcase
        end
    end
endmodule
// rst_gen: the reset the units see. The external reset asserts at once (asynchronously) and releases synchronously, two clocks after it goes away, and then is stretched by RSTN more clocks, so that every unit sees a reset that is long enough for its RAM-clearing and a release that is aligned to the clock.
module rst_gen #(parameter int RSTN = 8) (input logic clk, input logic rst_in, output logic rst_u);
    logic r1, r2; logic [$clog2(RSTN+1)-1:0] cnt;
    always_ff @(posedge clk or posedge rst_in) if (rst_in) begin r1 <= 1'b1; r2 <= 1'b1; end else begin r1 <= 1'b0; r2 <= r1; end      // asserts at once, releases two clocks after the input goes away
    always_ff @(posedge clk) if (r2) cnt <= ($bits(cnt))'(RSTN); else if (cnt != '0) cnt <= cnt - 1'b1;                                  // the stretch (loaded while r2 is high; it needs no reset of its own: r2 holds rst_u high until it is loaded)
    assign rst_u = r2 || (cnt != '0);
endmodule
// sup_syn: the supervisor and the reset generator behind a handful of pins, ONLY for the place-and-route runs.
module sup_syn #(parameter int FT = 100, parameter int ST = 100, parameter int WARM = 48) (input logic clk, input logic rst_in, input logic si, input logic sh, output logic [15:0] info);
    logic [9:0] iv; logic [1:0] state; logic kill, cq, rst_u; logic [4:0] cause;
    always_ff @(posedge clk) if (sh) iv <= {iv[8:0], si};
    rst_gen #(.RSTN(8)) rg (.clk(clk), .rst_in(rst_in), .rst_u(rst_u));
    sup #(.FT(FT), .ST(ST), .WARM(WARM)) u (.clk(clk), .rst(rst_u), .go(iv[0]), .trip(iv[1]), .feed(iv[2]), .slot(iv[3]), .fault(iv[4]), .sess(iv[7:5]), .tx_ready(iv[8]), .quiet(iv[9]), .state(state), .kill(kill), .cq_valid(cq), .cause(cause));
    always_ff @(posedge clk) info <= {7'd0, state, kill, cq, cause};
endmodule
