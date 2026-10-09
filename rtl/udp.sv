// verilator lint_off DECLFILENAME
// verilator lint_off UNUSEDSIGNAL
// Chapter 11: egress. Builds Ethernet/IPv4/UDP frames from a payload and hands them to Chapter 8's mac_tx (which pads to 60 bytes, appends the FCS and keeps the gap). Needs rtl/crc32_stream.sv and rtl/mac.sv.
//   udp_hdr   : the 42 header bytes (14 Ethernet + 20 IPv4 + 8 UDP) as a function of the byte index and the fields.
//   pacer     : a token bucket that grants a frame the right to start.
//   udp_sf    : STORE-AND-FORWARD builder: the payload goes into a memory while its length and checksum are summed; when the last byte has arrived the IPv4 and UDP checksums are completed and the frame is sent. UDP checksum is full. One frame at a time.
//   udp_ct    : CUT-THROUGH builder: the length is given up front (a descriptor), so the headers can be sent before the payload arrives and the payload passes through without a buffer. The UDP checksum is 0 ("none", legal for IPv4). The source must not stall inside a payload (mac_tx cannot pause the wire): a gap is an underrun.
//   udp_tx_path : builder (CT = 0 or 1) + optional pacer (PACE = 0 none, 1 pipelined, 2 the first, combinational one) + mac_tx.
// Per packet: a descriptor (d_len, d_dport, d_dip) then d_len payload bytes with s_last on the last. The store-and-forward builder ignores d_len. The other fields (addresses, source port) are static configuration.
module udp_hdr (
    input logic [5:0] k, input logic [47:0] dmac, input logic [47:0] smac, input logic [15:0] totlen, input logic [15:0] id, input logic [15:0] ipcs,
    input logic [31:0] sip, input logic [31:0] dip, input logic [15:0] sport, input logic [15:0] dport, input logic [15:0] ulen, input logic [15:0] ucs, output logic [7:0] b);
    always_comb begin
        case (k)
            6'd0: b = dmac[47:40]; 6'd1: b = dmac[39:32]; 6'd2: b = dmac[31:24]; 6'd3: b = dmac[23:16]; 6'd4: b = dmac[15:8]; 6'd5: b = dmac[7:0];
            6'd6: b = smac[47:40]; 6'd7: b = smac[39:32]; 6'd8: b = smac[31:24]; 6'd9: b = smac[23:16]; 6'd10: b = smac[15:8]; 6'd11: b = smac[7:0];
            6'd12: b = 8'h08; 6'd13: b = 8'h00;
            6'd14: b = 8'h45; 6'd15: b = 8'h00; 6'd16: b = totlen[15:8]; 6'd17: b = totlen[7:0]; 6'd18: b = id[15:8]; 6'd19: b = id[7:0];
            6'd20: b = 8'h40; 6'd21: b = 8'h00; 6'd22: b = 8'h40; 6'd23: b = 8'h11; 6'd24: b = ipcs[15:8]; 6'd25: b = ipcs[7:0];
            6'd26: b = sip[31:24]; 6'd27: b = sip[23:16]; 6'd28: b = sip[15:8]; 6'd29: b = sip[7:0];
            6'd30: b = dip[31:24]; 6'd31: b = dip[23:16]; 6'd32: b = dip[15:8]; 6'd33: b = dip[7:0];
            6'd34: b = sport[15:8]; 6'd35: b = sport[7:0]; 6'd36: b = dport[15:8]; 6'd37: b = dport[7:0];
            6'd38: b = ulen[15:8]; 6'd39: b = ulen[7:0]; 6'd40: b = ucs[15:8]; 6'd41: b = ucs[7:0];
            default: b = 8'h00;
        endcase
    end
endmodule
// pacer_comb (the FIRST version): credit is in 1/256 byte. Every cycle it gains `rate` (0 to 256 = 1 byte per cycle), up to BURST bytes. A request of `len` wire bytes (preamble, frame, FCS and gap) is granted, combinationally, when the credit covers it; the grant takes the cost from the credit. A grant is only meaningful if the requester takes it in that cycle.
module pacer_comb #(parameter int BURST = 3072) (
    input logic clk, input logic rst, input logic [8:0] rate, input logic req, input logic [10:0] len, output logic go);
    localparam int CW = 24; localparam logic [CW-1:0] CAP = CW'(BURST) << 8;
    logic [CW-1:0] credit, cost, after, sum;
    assign cost = {5'd0, len, 8'd0};
    assign go = req && (credit >= cost);
    assign after = go ? credit - cost : credit;
    assign sum = after + {15'd0, rate};
    always_ff @(posedge clk) begin
        if (rst) credit <= CAP; else credit <= (sum > CAP) ? CAP : sum;
    end
endmodule
// pacer (the final version): the same token bucket, pipelined. The bucket holds 2^BL bytes (a power of two, so that saturation is a test of one bit). The requester must hold `req` and `len` steady for 3 cycles (both builders do). Registered: the cost, the credit change a grant makes (rate - cost), the comparison "credit covers the cost", and the request delayed twice; a grant is req AND the twice-delayed req AND the comparison. The credit's next value is chosen between two sums computed in parallel from registers, with and without the grant. A grant clears the comparison for one cycle, so two grants are at least two cycles apart (the comparison would otherwise be stale).
module pacer #(parameter int BL = 12) (
    input logic clk, input logic rst, input logic [8:0] rate, input logic req, input logic [10:0] len, output logic go);
    localparam int W = BL + 9;
    localparam logic [W-1:0] CAPU = W'(1) << (BL + 8);
    logic [W-1:0] credit, cost_r, na, nb; logic signed [W:0] d_r, sa; logic [W:0] sb; logic ok_r, r1, r2;
    assign go = req && r2 && ok_r;
    assign sa = $signed({1'b0, credit}) + d_r; assign sb = {1'b0, credit} + {{(W - 8){1'b0}}, rate};
    assign na = sa[W-1:0];                                                   // no saturation here: a grant takes at least 256 units (one byte) and the rate adds at most 256, so the credit cannot rise
    assign nb = sb[BL + 8] ? CAPU : sb[W-1:0];
    always_ff @(posedge clk) begin
        cost_r <= W'({len, 8'd0}); d_r <= $signed({1'b0, {(W - 9){1'b0}}, rate}) - $signed({1'b0, cost_r});
        ok_r <= (credit >= cost_r) && !go; r1 <= req; r2 <= r1;
        credit <= go ? na : nb;
        if (rst) begin credit <= CAPU; ok_r <= 1'b0; r1 <= 1'b0; r2 <= 1'b0; end
    end
endmodule
module udp_sf #(parameter int AW = 11, parameter int MAXP = 1472) (
    input logic clk, input logic rst,
    input logic [47:0] cfg_dmac, input logic [47:0] cfg_smac, input logic [31:0] cfg_sip, input logic [15:0] cfg_sport,
    input logic d_valid, input logic [15:0] d_dport, input logic [31:0] d_dip, output logic d_ready,
    input logic s_valid, input logic [7:0] s_data, input logic s_last, output logic s_ready,
    output logic p_req, output logic [10:0] p_len, input logic p_go,
    output logic o_valid, output logic [7:0] o_data, output logic o_last, input logic o_ready,
    output logic [15:0] n_pkt, output logic [15:0] n_drop);
    typedef enum logic [1:0] {IN, CALC, REQ, OUT} st_t;
    st_t st; logic have, shown; logic [11:0] cnt, len, k; logic [7:0] hold; logic [16:0] acc, ia, ua; logic [15:0] dport, id, ipcs, ucs; logic [31:0] dip; logic [3:0] step;
    logic [7:0] mem [0:(1 << AW) - 1]; logic [7:0] mem_q; logic [7:0] hb;
    function automatic logic [16:0] addw(input logic [16:0] a, input logic [15:0] w);
        addw = {1'b0, a[15:0]} + {16'd0, a[16]} + {1'b0, w};
    endfunction
    logic [15:0] totlen, ulen, ipw, uw; logic [16:0] f1i, f1u;
    assign totlen = {4'd0, len} + 16'd28; assign ulen = {4'd0, len} + 16'd8;
    always_comb begin
        case (step)
            4'd0: begin ipw = 16'h4500; uw = cfg_sip[31:16]; end
            4'd1: begin ipw = totlen; uw = cfg_sip[15:0]; end
            4'd2: begin ipw = id; uw = dip[31:16]; end
            4'd3: begin ipw = 16'h4000; uw = dip[15:0]; end
            4'd4: begin ipw = 16'h4011; uw = 16'h0011; end
            4'd5: begin ipw = cfg_sip[31:16]; uw = ulen; end
            4'd6: begin ipw = cfg_sip[15:0]; uw = cfg_sport; end
            4'd7: begin ipw = dip[31:16]; uw = dport; end
            default: begin ipw = dip[15:0]; uw = ulen; end
        endcase
    end
    assign f1i = {1'b0, ia[15:0]} + {16'd0, ia[16]}; assign f1u = {1'b0, ua[15:0]} + {16'd0, ua[16]};
    udp_hdr uh (.k(k[5:0]), .dmac(cfg_dmac), .smac(cfg_smac), .totlen(totlen), .id(id), .ipcs(ipcs), .sip(cfg_sip), .dip(dip), .sport(cfg_sport), .dport(dport), .ulen(ulen), .ucs(ucs), .b(hb));
    assign d_ready = (st == IN) && !have;
    assign s_ready = (st == IN) && have;
    assign p_req = (st == REQ);
    assign p_len = ((len + 12'd42 < 12'd60) ? 11'd60 : 11'(len + 12'd42)) + 11'd24;
    logic [11:0] total, kn; logic adv, lastb; logic [AW-1:0] ra;
    assign total = len + 12'd42; assign adv = !shown || o_ready; assign kn = shown ? k + 12'd1 : k;
    assign lastb = shown && (k == total - 12'd1);
    assign o_valid = (st == OUT) && shown; assign o_last = o_valid && lastb; assign o_data = (k < 12'd42) ? hb : mem_q;
    assign ra = AW'((adv ? kn : k) - 12'd42);
    always_ff @(posedge clk) begin
        mem_q <= mem[ra];
        if (st == IN && s_valid && s_ready && cnt < 12'(MAXP)) mem[AW'(cnt)] <= s_data;
        if (rst) begin st <= IN; have <= 1'b0; cnt <= '0; acc <= '0; id <= '0; n_pkt <= '0; n_drop <= '0; shown <= 1'b0; k <= '0; step <= '0; hold <= '0; len <= '0; dport <= '0; dip <= '0; ipcs <= '0; ucs <= '0; ia <= '0; ua <= '0; end
        else case (st)
            IN: begin
                if (d_valid && d_ready) begin have <= 1'b1; dport <= d_dport; dip <= d_dip; end
                if (s_valid && s_ready) begin
                    if (cnt < 12'(MAXP)) begin
                        cnt <= cnt + 12'd1;
                        if (!cnt[0]) begin hold <= s_data; if (s_last) acc <= addw(acc, {s_data, 8'h00}); end
                        else acc <= addw(acc, {hold, s_data});
                    end
                    if (s_last) begin
                        if (cnt >= 12'(MAXP)) begin n_drop <= n_drop + 16'd1; cnt <= '0; acc <= '0; have <= 1'b0; end                 // cnt stops at MAXP: a payload of MAXP + 1 bytes or more arrives at its last byte with cnt = MAXP
                        else begin len <= cnt + 12'd1; st <= CALC; step <= '0; end
                    end
                end
            end
            CALC: begin
                step <= step + 4'd1;
                if (step <= 4'd8) begin ia <= addw(step == 4'd0 ? 17'd0 : ia, ipw); ua <= addw(step == 4'd0 ? acc : ua, uw); end
                else if (step == 4'd9) begin ia <= {1'b0, f1i[15:0]} + {16'd0, f1i[16]}; ua <= {1'b0, f1u[15:0]} + {16'd0, f1u[16]}; end        // one fold is enough: after any addition the sum is at most 0x1FFFE, so low + carry never carries again (as in Chapter 9)
                else begin ipcs <= ~ia[15:0]; ucs <= (ua[15:0] == 16'hFFFF) ? 16'hFFFF : ~ua[15:0]; st <= REQ; end
            end
            REQ: if (p_go) begin st <= OUT; k <= '0; shown <= 1'b0; end
            OUT: begin
                if (adv) begin
                    if (lastb) begin st <= IN; shown <= 1'b0; have <= 1'b0; cnt <= '0; acc <= '0; id <= id + 16'd1; n_pkt <= n_pkt + 16'd1; end
                    else begin k <= kn; shown <= 1'b1; end
                end
            end
            default: st <= IN;
        endcase
    end
endmodule
module udp_ct (
    input logic clk, input logic rst,
    input logic [47:0] cfg_dmac, input logic [47:0] cfg_smac, input logic [31:0] cfg_sip, input logic [15:0] cfg_sport,
    input logic d_valid, input logic [10:0] d_len, input logic [15:0] d_dport, input logic [31:0] d_dip, output logic d_ready,
    input logic s_valid, input logic [7:0] s_data, input logic s_last, output logic s_ready,
    output logic p_req, output logic [10:0] p_len, input logic p_go,
    output logic o_valid, output logic [7:0] o_data, output logic o_last, input logic o_ready,
    output logic [15:0] n_pkt, output logic [15:0] n_drop);
    typedef enum logic [1:0] {A_IDLE, A_CALC, A_WAIT} a_t; typedef enum logic [1:0] {E_IDLE, E_REQ, E_RUN} e_t;
    a_t as; e_t es; logic [3:0] step; logic [10:0] alen; logic [15:0] adport, aid, aipcs; logic [31:0] adip; logic [16:0] ia;
    logic [10:0] elen; logic [15:0] edport, eid, eipcs; logic [31:0] edip; logic [11:0] k; logic [10:0] eplen; logic [7:0] hb;
    function automatic logic [16:0] addw(input logic [16:0] a, input logic [15:0] w);
        addw = {1'b0, a[15:0]} + {16'd0, a[16]} + {1'b0, w};
    endfunction
    logic [15:0] atot, ipw; logic [16:0] f1i; logic [15:0] etot, eulen; logic [11:0] total;
    assign atot = {5'd0, alen} + 16'd28; assign etot = {5'd0, elen} + 16'd28; assign eulen = {5'd0, elen} + 16'd8;
    always_comb begin
        case (step)
            4'd0: ipw = 16'h4500; 4'd1: ipw = atot; 4'd2: ipw = aid; 4'd3: ipw = 16'h4000; 4'd4: ipw = 16'h4011;
            4'd5: ipw = cfg_sip[31:16]; 4'd6: ipw = cfg_sip[15:0]; 4'd7: ipw = adip[31:16]; default: ipw = adip[15:0];
        endcase
    end
    assign f1i = {1'b0, ia[15:0]} + {16'd0, ia[16]};
    udp_hdr uh (.k(k[5:0]), .dmac(cfg_dmac), .smac(cfg_smac), .totlen(etot), .id(eid), .ipcs(eipcs), .sip(cfg_sip), .dip(edip), .sport(cfg_sport), .dport(edport), .ulen(eulen), .ucs(16'h0000), .b(hb));
    assign d_ready = (as == A_IDLE);
    assign p_req = (es == E_REQ); assign p_len = eplen;
    assign total = {1'b0, elen} + 12'd42;
    logic run, hdr_ph; assign run = (es == E_RUN); assign hdr_ph = (k < 12'd42);
    assign o_valid = run && (hdr_ph || s_valid); assign o_data = hdr_ph ? hb : s_data; assign o_last = o_valid && (k == total - 12'd1);
    assign s_ready = run && !hdr_ph && o_ready;
    always_ff @(posedge clk) begin
        if (rst) begin as <= A_IDLE; es <= E_IDLE; step <= '0; k <= '0; n_pkt <= '0; n_drop <= '0; aid <= '0; ia <= '0; alen <= '0; adport <= '0; adip <= '0; aipcs <= '0; elen <= '0; edport <= '0; eid <= '0; eipcs <= '0; edip <= '0; eplen <= '0; end
        else begin
            case (as)
                A_IDLE: if (d_valid) begin alen <= d_len; adport <= d_dport; adip <= d_dip; as <= A_CALC; step <= '0; end
                A_CALC: begin
                    step <= step + 4'd1;
                    if (step <= 4'd8) ia <= addw(step == 4'd0 ? 17'd0 : ia, ipw);
                    else if (step == 4'd9) ia <= {1'b0, f1i[15:0]} + {16'd0, f1i[16]};
                    else begin aipcs <= ~ia[15:0]; as <= A_WAIT; end
                end
                A_WAIT: if (es == E_IDLE) begin
                    elen <= alen; edport <= adport; edip <= adip; eipcs <= aipcs; eid <= aid; aid <= aid + 16'd1; es <= E_REQ;
                    eplen <= ((alen + 11'd42 < 11'd60) ? 11'd60 : (alen + 11'd42)) + 11'd24; as <= A_IDLE;
                end
                default: as <= A_IDLE;
            endcase
            case (es)
                E_REQ: if (p_go) begin es <= E_RUN; k <= '0; end
                E_RUN: if (o_valid && o_ready) begin
                    if (o_last) begin es <= E_IDLE; n_pkt <= n_pkt + 16'd1; end else k <= k + 12'd1;
                end
                default: ;
            endcase
        end
    end
endmodule
module udp_tx_path #(parameter int CT = 0, parameter int PACE = 0, parameter int AW = 11, parameter int MAXP = 1472, parameter int BL = 12) (
    input logic clk, input logic rst,
    input logic [47:0] cfg_dmac, input logic [47:0] cfg_smac, input logic [31:0] cfg_sip, input logic [15:0] cfg_sport, input logic [8:0] rate,
    input logic d_valid, input logic [10:0] d_len, input logic [15:0] d_dport, input logic [31:0] d_dip, output logic d_ready,
    input logic s_valid, input logic [7:0] s_data, input logic s_last, output logic s_ready,
    output logic tx_en, output logic [7:0] txd, output logic underrun, output logic [15:0] n_pkt, output logic [15:0] n_drop);
    logic p_req, p_go, o_valid, o_last, o_ready; logic [10:0] p_len; logic [7:0] o_data;
    if (CT != 0) begin : g_ct
        udp_ct b (.clk(clk), .rst(rst), .cfg_dmac(cfg_dmac), .cfg_smac(cfg_smac), .cfg_sip(cfg_sip), .cfg_sport(cfg_sport), .d_valid(d_valid), .d_len(d_len), .d_dport(d_dport), .d_dip(d_dip), .d_ready(d_ready),
            .s_valid(s_valid), .s_data(s_data), .s_last(s_last), .s_ready(s_ready), .p_req(p_req), .p_len(p_len), .p_go(p_go), .o_valid(o_valid), .o_data(o_data), .o_last(o_last), .o_ready(o_ready), .n_pkt(n_pkt), .n_drop(n_drop));
    end else begin : g_sf
        udp_sf #(.AW(AW), .MAXP(MAXP)) b (.clk(clk), .rst(rst), .cfg_dmac(cfg_dmac), .cfg_smac(cfg_smac), .cfg_sip(cfg_sip), .cfg_sport(cfg_sport), .d_valid(d_valid), .d_dport(d_dport), .d_dip(d_dip), .d_ready(d_ready),
            .s_valid(s_valid), .s_data(s_data), .s_last(s_last), .s_ready(s_ready), .p_req(p_req), .p_len(p_len), .p_go(p_go), .o_valid(o_valid), .o_data(o_data), .o_last(o_last), .o_ready(o_ready), .n_pkt(n_pkt), .n_drop(n_drop));
    end
    if (PACE == 1) begin : g_p
        pacer #(.BL(BL)) p (.clk(clk), .rst(rst), .rate(rate), .req(p_req), .len(p_len), .go(p_go));
    end else if (PACE == 2) begin : g_pc
        pacer_comb #(.BURST(1 << BL)) p (.clk(clk), .rst(rst), .rate(rate), .req(p_req), .len(p_len), .go(p_go));
    end else begin : g_np
        assign p_go = p_req;
    end
    mac_tx mt (.clk(clk), .rst(rst), .f_valid(o_valid), .f_data(o_data), .f_last(o_last), .f_ready(o_ready), .tx_en(tx_en), .txd(txd), .underrun(underrun));
endmodule
// udp_tx_syn: udp_tx_path behind a handful of pins, ONLY so that it fits a chip for the place-and-route runs. The 212 bits of configuration and descriptor fields are shifted in serially; the counters leave through one registered 16-bit port. Its own cost (212 flip-flops and a register) is part of the numbers measured with it.
module udp_tx_syn #(parameter int CT = 0, parameter int PACE = 0) (
    input logic clk, input logic rst, input logic cfg_si, input logic cfg_sh, input logic d_valid, output logic d_ready,
    input logic s_valid, input logic [7:0] s_data, input logic s_last, output logic s_ready, output logic tx_en, output logic [7:0] txd, output logic underrun, output logic [15:0] info);
    logic [211:0] cfg; logic [15:0] n_pkt, n_drop;
    always_ff @(posedge clk) begin if (cfg_sh) cfg <= {cfg[210:0], cfg_si}; info <= n_pkt ^ n_drop; end
    udp_tx_path #(.CT(CT), .PACE(PACE)) u (.clk(clk), .rst(rst), .cfg_dmac(cfg[47:0]), .cfg_smac(cfg[95:48]), .cfg_sip(cfg[127:96]), .cfg_sport(cfg[143:128]), .rate(cfg[152:144]),
        .d_valid(d_valid), .d_len(cfg[163:153]), .d_dport(cfg[179:164]), .d_dip({cfg[211:180]}), .d_ready(d_ready), .s_valid(s_valid), .s_data(s_data), .s_last(s_last), .s_ready(s_ready), .tx_en(tx_en), .txd(txd), .underrun(underrun), .n_pkt(n_pkt), .n_drop(n_drop));
endmodule
