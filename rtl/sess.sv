// Chapter 24: the order-entry transmitter. A request (order, cancel, replace, login, logout) becomes a packet in ONE cycle: the fixed bytes of the template (type, length, stock name of the symbol, firm, display, capacity, user, password) are already in registers and the request's fields are patched into the right positions of a 32-byte buffer; the buffer then leaves W bytes per beat, first byte first, with no gap between packets. The client side of the session (login, heartbeats, liveness, the expected sequence number) is a small state machine around it. The specification is in model/sess_gold.py (a simplified, OUCH- and SoupBinTCP-like protocol of this book).
module sess #(parameter int W = 8, parameter int NS = 4, parameter int HB = 20, parameter int TL = 60) (
    input  logic clk, input logic rst,
    input  logic in_valid, input logic [2:0] in_kind, input logic [31:0] in_tok, input logic [31:0] in_tok2, input logic [3:0] in_sym, input logic in_side, input logic [31:0] in_shares, input logic [31:0] in_px, input logic [31:0] in_tif,
    output logic in_ready,
    input  logic rx_valid, input logic [7:0] rx_type, input logic [31:0] rx_seq,
    input  logic cfg_valid, input logic [2:0] cfg_what, input logic [3:0] cfg_sym, input logic [31:0] cfg_data,
    output logic o_valid, output logic [8*W-1:0] o_data, output logic o_last, output logic [3:0] o_nb, output logic [2:0] o_state, output logic [31:0] o_exp, output logic o_rv, output logic [1:0] o_res);
    localparam logic [2:0] IDLE = 3'd0, LOGIN = 3'd1, ACTIVE = 3'd2, REJECTED = 3'd3, DEAD = 3'd4, CLOSED = 3'd5, GAP = 3'd6;
    localparam logic [2:0] K_ORDER = 3'd0, K_CANCEL = 3'd1, K_REPLACE = 3'd2, K_LOGIN = 3'd3, K_LOGOUT = 3'd4;
    localparam int TW = 16;
    // ---- configuration: the fixed parts of the templates
    logic [31:0] stock [0:NS-1]; logic [31:0] user, pw, firm, reqseq; logic [7:0] display, capacity;
    always_ff @(posedge clk) if (rst) begin
        for (int i = 0; i < NS; i++) stock[i] <= '0;
        user <= '0; pw <= '0; firm <= '0; reqseq <= '0; display <= '0; capacity <= '0;
    end else if (cfg_valid) begin
        case (cfg_what)
            3'd0: for (int i = 0; i < NS; i++) if (cfg_sym == 4'(i)) stock[i] <= cfg_data;
            3'd1: user <= cfg_data;
            3'd2: pw <= cfg_data;
            3'd3: firm <= cfg_data;
            3'd4: begin display <= cfg_data[15:8]; capacity <= cfg_data[7:0]; end
            3'd5: reqseq <= cfg_data;
            default: ;
        endcase
    end
    // ---- state, timers, the transmitter
    logic [2:0] st; logic [31:0] expseq; logic [TW-1:0] hbc, rxc, ltc; logic [255:0] tx; logic [5:0] txlen; logic rv; logic [1:0] res;
    wire hb_due = (st == ACTIVE) && (hbc >= TW'(HB));
    wire tx_free = (txlen <= 6'(W));
    assign in_ready = tx_free && !hb_due;
    assign o_valid = (txlen != 0); assign o_data = tx[255 -: 8*W]; assign o_last = (txlen != 0) && tx_free; assign o_nb = tx_free ? 4'(txlen) : 4'(W);
    assign o_state = st; assign o_exp = expseq; assign o_rv = rv; assign o_res = res;
    // ---- the packets: the template with the request's fields patched in (byte 0 is the high byte)
    wire [31:0] stk = (in_sym < 4'(NS)) ? stock[in_sym[$clog2(NS > 1 ? NS : 2)-1:0]] : 32'd0;
    wire [7:0] side_c = in_side ? 8'h53 : 8'h42;
    wire [255:0] p_order   = {16'h001D, 8'h55, 8'h4F, in_tok, side_c, in_shares, stk, in_px, in_tif, firm, display, capacity, 8'h00};
    wire [255:0] p_cancel  = {16'h000A, 8'h55, 8'h58, in_tok, in_shares, 160'd0};
    wire [255:0] p_replace = {16'h0017, 8'h55, 8'h4E, in_tok, in_tok2, in_shares, in_px, in_tif, display, 56'd0};
    wire [255:0] p_login   = {16'h000D, 8'h4C, user, pw, reqseq, 136'd0};
    wire [255:0] p_hb      = {16'h0001, 8'h52, 232'd0};
    wire [255:0] p_logout  = {16'h0001, 8'h4F, 232'd0};
    // ---- the decisions of this cycle
    wire accept = in_valid && in_ready;
    wire allowed = (in_kind == K_LOGIN) ? (st == IDLE) : (st == ACTIVE);
    wire badsym = (in_kind == K_ORDER) && (in_sym >= 4'(NS));
    wire load_req = accept && allowed && !badsym && (in_kind <= K_LOGOUT);
    wire load_hb = hb_due && tx_free;
    wire loaded = load_req || load_hb;
    logic [255:0] pk; logic [5:0] pklen;
    always_comb begin
        pk = p_hb; pklen = 6'd3;
        if (load_req) case (in_kind)
            K_ORDER: begin pk = p_order; pklen = 6'd31; end
            K_CANCEL: begin pk = p_cancel; pklen = 6'd12; end
            K_REPLACE: begin pk = p_replace; pklen = 6'd25; end
            K_LOGIN: begin pk = p_login; pklen = 6'd15; end
            default: begin pk = p_logout; pklen = 6'd3; end
        endcase
    end
    logic [2:0] nst; logic heard; logic [31:0] nexp;
    always_comb begin
        nst = st; heard = 1'b0; nexp = expseq;
        if (rx_valid) begin
            if (st == LOGIN && rx_type == 8'h41) begin nst = ACTIVE; nexp = rx_seq; end
            else if (st == LOGIN && rx_type == 8'h4A) nst = REJECTED;
            else if (rx_type == 8'h5A && (st == LOGIN || st == ACTIVE)) nst = CLOSED;
            else if (st == ACTIVE && rx_type == 8'h48) heard = 1'b1;
            else if (st == ACTIVE && rx_type == 8'h53) begin if (rx_seq == expseq) begin nexp = expseq + 1'b1; heard = 1'b1; end else nst = GAP; end
        end
        if (st == LOGIN && nst == LOGIN && ltc + 1'b1 >= TW'(TL)) nst = DEAD;
        if (st == ACTIVE && nst == ACTIVE && !heard && rxc + 1'b1 >= TW'(3 * HB)) nst = DEAD;
    end
    always_ff @(posedge clk) begin
        if (rst) begin st <= IDLE; expseq <= '0; rxc <= '0; ltc <= '0; txlen <= '0; rv <= 1'b0; res <= '0; end         // hbc needs no reset: it is cleared in the first cycle outside ACTIVE
        else begin
            rv <= accept; res <= !allowed ? 2'd1 : (badsym ? 2'd2 : 2'd0);
            // the transmitter
            if (loaded) begin tx <= pk; txlen <= pklen; end
            else begin tx <= tx << (8 * W); txlen <= tx_free ? 6'd0 : txlen - 6'(W); end
            // timers and state
            expseq <= nexp;
            if (st == LOGIN && nst == LOGIN) ltc <= ltc + 1'b1;
            if (st == ACTIVE && nst == ACTIVE) rxc <= heard ? '0 : rxc + 1'b1;
            hbc <= (loaded || st != ACTIVE) ? '0 : hbc + 1'b1;           // counts only in ACTIVE (hb_due says so); cleared by any packet
            if (load_req && in_kind == K_LOGIN) st <= LOGIN;          // ltc and rxc are 0 from reset: the session goes through LOGIN and ACTIVE once
            else if (load_req && in_kind == K_LOGOUT) st <= CLOSED;
            else st <= nst;
        end
    end
endmodule
// sess_syn: the same design behind a handful of pins, ONLY so that it fits a chip for the place-and-route runs: the inputs are shifted in serially, the outputs registered and folded into one 16-bit word.
module sess_syn #(parameter int W = 8, parameter int NS = 4, parameter int HB = 20, parameter int TL = 60) (input logic clk, input logic rst, input logic si, input logic sh, output logic [15:0] info);
    logic [319:0] iv; logic ready, ov_, last, rv; logic [8*W-1:0] data; logic [3:0] nb; logic [2:0] state; logic [31:0] exp_; logic [1:0] res;
    always_ff @(posedge clk) if (sh) iv <= {iv[318:0], si};
    sess #(.W(W), .NS(NS), .HB(HB), .TL(TL)) u (.clk(clk), .rst(rst), .in_valid(iv[0]), .in_kind(iv[3:1]), .in_tok(iv[35:4]), .in_tok2(iv[67:36]), .in_sym(iv[71:68]), .in_side(iv[72]), .in_shares(iv[104:73]), .in_px(iv[136:105]), .in_tif(iv[168:137]), .in_ready(ready),
        .rx_valid(iv[169]), .rx_type(iv[177:170]), .rx_seq(iv[209:178]), .cfg_valid(iv[210]), .cfg_what(iv[213:211]), .cfg_sym(iv[217:214]), .cfg_data(iv[249:218]),
        .o_valid(ov_), .o_data(data), .o_last(last), .o_nb(nb), .o_state(state), .o_exp(exp_), .o_rv(rv), .o_res(res));
    logic [15:0] x, r1; always_comb x = 16'(data) ^ 16'(data >> 16) ^ 16'(data >> 32) ^ 16'(data >> 48) ^ 16'(exp_) ^ {state, nb, res, rv, last, ov_, ready, 2'b0};
    always_ff @(posedge clk) begin r1 <= x; info <= r1; end
endmodule
