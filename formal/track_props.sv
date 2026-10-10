// Chapter 25: formal properties of the order tracker, for Yosys's SAT engine. The wrapper drives the tracker with FREE inputs (any local event, any report, every cycle) and keeps its own account, written in a different form: indexed by TOKEN instead of by table entry (the contract: tokens are 0..3, so the shadow has four slots, and the table has NT = 2 entries, so it can be full). For each token it keeps whether the order is open, its original quantity, the quantity RELEASED so far (fills and cancels), its state and fields. From that it computes what the answer, the release, the count of open orders and the fault must be, and asserts, one cycle after every event:
//   T1 (no over-release, the safety property): released + remaining = original for every open order, and a release never exceeds what is left;  T2 an order that leaves the table has been released EXACTLY its original quantity;  T3 a release is for an open order, with that order's own account, symbol, side and price;  T4 the answer, the count of open orders and the fault equal the specification's;  T5 an anomalous report changes nothing and releases nothing.
// The contract, assumed: no event while the reset is applied; tokens 0..3; quantities below 8 (3 bits).
module track_props (
    input logic clk,
    input logic l_valid, input logic l_kind, input logic [1:0] l_tok, input logic [3:0] l_acct, input logic [3:0] l_sym, input logic l_side, input logic [3:0] l_px, input logic [2:0] l_qty,
    input logic r_valid, input logic [1:0] r_kind, input logic [1:0] r_tok, input logic [2:0] r_qty);
    localparam int NT = 2;
    logic rst; initial rst = 1'b1; logic started = 1'b0;
    logic ready, o_valid, o_src, o_rv, o_rside, o_fault; logic [2:0] o_res; logic [1:0] o_rtype; logic [3:0] o_racct, o_rsym; logic [3:0] o_rpx; logic [2:0] o_rqty; logic [1:0] o_live;
    track #(.NT(NT), .PW(4), .QW(3)) dut (.clk(clk), .rst(rst), .l_valid(l_valid), .l_kind(l_kind), .l_tok({30'd0, l_tok}), .l_acct(l_acct), .l_sym(l_sym), .l_side(l_side), .l_px(l_px), .l_qty(l_qty), .ready(ready),
        .r_valid(r_valid), .r_kind(r_kind), .r_tok({30'd0, r_tok}), .r_qty(r_qty), .o_valid(o_valid), .o_src(o_src), .o_res(o_res), .o_rv(o_rv), .o_rtype(o_rtype), .o_racct(o_racct), .o_rsym(o_rsym), .o_rside(o_rside), .o_rpx(o_rpx), .o_rqty(o_rqty), .o_live(o_live), .o_fault(o_fault));
    always @(*) assume (!rst || (!l_valid && !r_valid));
    // ---- the shadow, by token
    logic open_ [0:3]; logic [2:0] orig [0:3]; logic [3:0] relsum [0:3]; logic [1:0] st_ [0:3]; logic [3:0] a_ [0:3]; logic [3:0] s_ [0:3]; logic sd_ [0:3]; logic [3:0] p_ [0:3]; logic g_fault;
    // ---- the specification, from the shadow and the pins of this cycle
    wire [1:0] tk = r_valid ? r_tok : l_tok; wire any = r_valid || l_valid;
    wire o = open_[tk]; wire [3:0] left = {1'b0, orig[tk]} - relsum[tk]; wire [3:0] nopen = {3'd0, open_[0]} + {3'd0, open_[1]} + {3'd0, open_[2]} + {3'd0, open_[3]};
    logic [2:0] x_res; logic x_rel; logic [1:0] x_type; logic [2:0] x_q; logic x_free, x_new, x_live, x_pcan, x_fill;
    always_comb begin
        x_res = 3'd0; x_rel = 1'b0; x_type = 2'd0; x_q = 3'd0; x_free = 1'b0; x_new = 1'b0; x_live = 1'b0; x_pcan = 1'b0; x_fill = 1'b0;
        if (r_valid) begin
            if (!o) x_res = 3'd1;
            else case (r_kind)
                2'd0: if (st_[tk] != 2'd0) x_res = 3'd2; else x_live = 1'b1;
                2'd1: if (r_qty == 0) x_res = 3'd4; else if ({1'b0, r_qty} > left) x_res = 3'd3; else begin x_rel = 1'b1; x_type = 2'd1; x_q = r_qty; x_fill = 1'b1; x_live = (st_[tk] == 2'd0); x_free = ({1'b0, r_qty} == left); end
                2'd2: begin x_rel = 1'b1; x_type = 2'd2; x_q = left[2:0]; x_free = 1'b1; end
                default: if (st_[tk] != 2'd0) x_res = 3'd2; else begin x_rel = 1'b1; x_type = 2'd2; x_q = left[2:0]; x_free = 1'b1; end
            endcase
        end else if (l_valid) begin
            if (!l_kind) begin if (l_qty == 0) x_res = 3'd4; else if (o) x_res = 3'd6; else if (nopen >= NT) x_res = 3'd5; else x_new = 1'b1; end
            else begin if (!o) x_res = 3'd1; else if (st_[tk] != 2'd1) x_res = 3'd2; else x_pcan = 1'b1; end
        end
    end
    // what must be shown the cycle after
    logic e_any, e_rv, e_src, e_flt_set; logic [2:0] e_res; logic [1:0] e_type; logic [2:0] e_q; logic [3:0] e_a, e_s, e_p; logic e_sd; logic [1:0] e_live; logic e_fault_exp; logic [3:0] e_total; logic e_freed; logic [3:0] e_rel_after, e_orig;
    integer i;
    always @(posedge clk) begin
        rst <= 1'b0; started <= 1'b1;
        e_any <= any && !rst; e_src <= r_valid; e_res <= x_res; e_rv <= x_rel; e_type <= x_type; e_q <= x_q; e_a <= a_[tk]; e_s <= s_[tk]; e_sd <= sd_[tk]; e_p <= p_[tk];
        e_freed <= x_free; e_rel_after <= relsum[tk] + {1'b0, x_q}; e_orig <= {1'b0, orig[tk]};
        if (rst) begin
            g_fault <= 1'b0; for (i = 0; i < 4; i++) begin open_[i] <= 1'b0; orig[i] <= 0; relsum[i] <= 0; st_[i] <= 0; a_[i] <= 0; s_[i] <= 0; sd_[i] <= 0; p_[i] <= 0; end
        end else begin
            if (r_valid && x_res != 0) g_fault <= 1'b1;
            if (x_new) begin open_[tk] <= 1'b1; orig[tk] <= l_qty; relsum[tk] <= 0; st_[tk] <= 0; a_[tk] <= l_acct; s_[tk] <= l_sym; sd_[tk] <= l_side; p_[tk] <= l_px; end
            if (x_pcan) st_[tk] <= 2'd2;
            if (x_live) st_[tk] <= 2'd1;
            if (x_rel) relsum[tk] <= relsum[tk] + {1'b0, x_q};
            if (x_free) open_[tk] <= 1'b0;
        end
    end
    wire [3:0] sh_open = {3'd0, open_[0]} + {3'd0, open_[1]} + {3'd0, open_[2]} + {3'd0, open_[3]};
    always @(posedge clk) if (started && !rst) begin
        // T4: answer, count, fault
        assert (o_valid == e_any);
        if (e_any) assert (o_res == e_res && o_src == e_src);
        assert ({2'd0, o_live} == sh_open);
        assert (o_fault == g_fault);
        // T3, T5: the release
        assert (o_rv == e_rv);
        if (e_rv) assert (o_rtype == e_type && o_rqty == e_q && o_racct == e_a && o_rsym == e_s && o_rside == e_sd && o_rpx == e_p);
        // T1: released + remaining = original for every open order; nothing over-released
        for (i = 0; i < 4; i++) if (open_[i]) assert (relsum[i] < {1'b0, orig[i]});
        // T2: an order that left the table was released exactly its original quantity (a cancel releases the remainder)
        if (e_rv && e_freed) assert (e_rel_after == e_orig);
        if (e_rv) assert (e_rel_after <= e_orig);
    end
endmodule
