// Chapter 25: the order tracker. NT entries, each an order that was sent and is not finished: token, account, symbol, side, the order's price, the remaining quantity and a state (PENDING_NEW, LIVE, PENDING_CANCEL). The token is looked up in all entries at once. One event per cycle: a report from the exchange wins over a local event (ready is low and the requester holds its event). Every report that does not fit the books sets the sticky fault. Outputs are qualified by their valid: the answer fields by o_valid, the release fields by o_rv, and are otherwise don't-care. The specification is in model/life_gold.py.
module track #(parameter int NT = 4, parameter int PW = 16, parameter int QW = 16) (
    input  logic clk, input logic rst,
    input  logic l_valid, input logic l_kind, input logic [31:0] l_tok, input logic [3:0] l_acct, input logic [3:0] l_sym, input logic l_side, input logic [PW-1:0] l_px, input logic [QW-1:0] l_qty,
    output logic ready,
    input  logic r_valid, input logic [1:0] r_kind, input logic [31:0] r_tok, input logic [QW-1:0] r_qty,
    output logic o_valid, output logic o_src, output logic [2:0] o_res,
    output logic o_rv, output logic [1:0] o_rtype, output logic [3:0] o_racct, output logic [3:0] o_rsym, output logic o_rside, output logic [PW-1:0] o_rpx, output logic [QW-1:0] o_rqty,
    output logic [$clog2(NT+1)-1:0] o_live, output logic o_fault);
    localparam logic [2:0] OK = 3'd0, UNKNOWN = 3'd1, BADSTATE = 3'd2, OVERFILL = 3'd3, ZERO = 3'd4, FULL = 3'd5, DUPTOK = 3'd6;
    localparam logic [1:0] PNEW = 2'd0, LIVE = 2'd1, PCAN = 2'd2;
    localparam logic [1:0] ACK = 2'd0, FILL = 2'd1, CANCELED = 2'd2;   // REJECT is the remaining value 3 (the default branch)
    localparam int IW = $clog2(NT) > 0 ? $clog2(NT) : 1;
    logic used [0:NT-1]; logic [31:0] tok [0:NT-1]; logic [3:0] acct [0:NT-1]; logic [3:0] sym [0:NT-1]; logic side [0:NT-1];
    logic [PW-1:0] px [0:NT-1]; logic [QW-1:0] rem [0:NT-1]; logic [1:0] st [0:NT-1];
    logic fault;
    assign ready = !r_valid;
    wire [31:0] etok = r_valid ? r_tok : l_tok;
    // ---- the lookup: every entry compares its token at once
    logic hit; logic [IW-1:0] hi; logic free; logic [IW-1:0] fi;
    always_comb begin
        hit = 1'b0; hi = '0; free = 1'b0; fi = '0;
        for (int i = NT - 1; i >= 0; i--) begin
            if (used[i] && tok[i] == etok) begin hit = 1'b1; hi = IW'(i); end
            if (!used[i]) begin free = 1'b1; fi = IW'(i); end
        end
    end
    wire [QW-1:0] hrem = rem[hi]; wire [1:0] hst = st[hi];
    // ---- the decision of this cycle
    logic [2:0] res; logic anomaly;
    logic do_new, do_fill, do_free, do_pcan, do_live;
    logic rel; logic [1:0] rtype; logic [QW-1:0] rq;
    always_comb begin
        res = OK; anomaly = 1'b0; do_new = 1'b0; do_fill = 1'b0; do_free = 1'b0; do_pcan = 1'b0; do_live = 1'b0; rel = 1'b0; rtype = 2'd0; rq = '0;
        if (r_valid) begin
            if (!hit) res = UNKNOWN;
            else case (r_kind)
                ACK: if (hst != PNEW) res = BADSTATE; else do_live = 1'b1;
                FILL: begin
                    if (r_qty == '0) res = ZERO;
                    else if (r_qty > hrem) res = OVERFILL;
                    else begin do_fill = 1'b1; do_live = (hst == PNEW); rel = 1'b1; rtype = 2'd1; rq = r_qty; do_free = (r_qty == hrem); end
                end
                CANCELED: begin rel = 1'b1; rtype = 2'd2; rq = hrem; do_free = 1'b1; end
                default: if (hst != PNEW) res = BADSTATE; else begin rel = 1'b1; rtype = 2'd2; rq = hrem; do_free = 1'b1; end
            endcase
            anomaly = (res != OK);
        end else if (l_valid) begin
            if (!l_kind) begin
                if (l_qty == '0) res = ZERO; else if (hit) res = DUPTOK; else if (!free) res = FULL; else do_new = 1'b1;
            end else begin
                if (!hit) res = UNKNOWN; else if (hst != LIVE) res = BADSTATE; else do_pcan = 1'b1;
            end
        end
    end
    always_ff @(posedge clk) begin
        if (rst) begin
            for (int i = 0; i < NT; i++) begin used[i] <= 1'b0; tok[i] <= '0; acct[i] <= '0; sym[i] <= '0; side[i] <= 1'b0; px[i] <= '0; rem[i] <= '0; st[i] <= '0; end
            fault <= 1'b0; o_valid <= 1'b0; o_src <= 1'b0; o_res <= '0; o_rv <= 1'b0; o_rtype <= '0; o_racct <= '0; o_rsym <= '0; o_rside <= 1'b0; o_rpx <= '0; o_rqty <= '0;
        end else begin
            o_valid <= r_valid || l_valid; o_src <= r_valid; o_res <= res;
            o_rv <= rel; o_rtype <= rtype; o_racct <= acct[hi]; o_rsym <= sym[hi]; o_rside <= side[hi]; o_rpx <= px[hi]; o_rqty <= rq;
            if (anomaly) fault <= 1'b1;
            if (do_new) begin
                used[fi] <= 1'b1; tok[fi] <= l_tok; acct[fi] <= l_acct; sym[fi] <= l_sym; side[fi] <= l_side; px[fi] <= l_px; rem[fi] <= l_qty; st[fi] <= PNEW;
            end
            if (do_pcan) st[hi] <= PCAN;
            if (do_live) st[hi] <= LIVE;
            if (do_fill) rem[hi] <= hrem - r_qty;
            if (do_free) used[hi] <= 1'b0;
        end
    end
    always_comb begin o_live = '0; for (int i = 0; i < NT; i++) o_live = o_live + (used[i] ? 1 : 0); end
    assign o_fault = fault;
endmodule
// track_syn: the tracker behind a handful of pins, ONLY for the place-and-route runs.
module track_syn #(parameter int NT = 4, parameter int PW = 16, parameter int QW = 16) (input logic clk, input logic rst, input logic si, input logic sh, output logic [15:0] info);
    localparam int LQ = 43 + PW, LR = LQ + QW, LT = LR + 3 + 32 + QW;
    logic [LT-1:0] iv; logic ready, ov_, src, rv, rside, fault; logic [2:0] res; logic [1:0] rtype; logic [3:0] racct, rsym; logic [PW-1:0] rpx; logic [QW-1:0] rqty; logic [$clog2(NT+1)-1:0] live;
    always_ff @(posedge clk) if (sh) iv <= {iv[LT-2:0], si};
    track #(.NT(NT), .PW(PW), .QW(QW)) u (.clk(clk), .rst(rst), .l_valid(iv[0]), .l_kind(iv[1]), .l_tok(iv[33:2]), .l_acct(iv[37:34]), .l_sym(iv[41:38]), .l_side(iv[42]), .l_px(iv[LQ-1:43]), .l_qty(iv[LR-1:LQ]), .ready(ready),
        .r_valid(iv[LR]), .r_kind(iv[LR+2:LR+1]), .r_tok(iv[LR+34:LR+3]), .r_qty(iv[LT-1:LR+35]),
        .o_valid(ov_), .o_src(src), .o_res(res), .o_rv(rv), .o_rtype(rtype), .o_racct(racct), .o_rsym(rsym), .o_rside(rside), .o_rpx(rpx), .o_rqty(rqty), .o_live(live), .o_fault(fault));
    logic [15:0] x, r1; always_comb x = 16'(rpx) ^ 16'(rqty) ^ {1'b0, racct, rsym, rtype, rside, rv, res} ^ 16'(live) ^ {12'd0, src, ov_, ready, fault};
    always_ff @(posedge clk) begin r1 <= x; info <= r1; end
endmodule
