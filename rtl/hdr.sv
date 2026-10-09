// verilator lint_off DECLFILENAME
// verilator lint_off UNUSEDSIGNAL
// Chapter 9: headers at line rate. Needs rtl/crc32_stream.sv and rtl/mac.sv only for hdr_path (mac_rx, frame_fifo).
//
// hdr_filter: a stream of frame bytes (valid, data, last, bad: the output of mac_rx, FCS already removed; no ready, bytes may arrive on any cycle) -> the same bytes three cycles later with the frame's verdict:
//   m_bad = 1 on the last byte unless the frame is a valid IPv4/UDP frame for this node (so frame_fifo drops everything else), and the CAUSE with the fields that were seen.
// One byte per clock, whatever the header length. This is the SECOND version (rtl/hdr_v1.sv is the first; the chapter shows what its measurement found): positions inside the headers are ONE-HOT shift registers (a field is captured by `if (position bit) field <= byte`, one LUT), the end of the IP header and of the UDP segment are registered flags computed a cycle ahead, and the state of the frame is cleared by the flip-flops' synchronous reset (at the last byte for the control state, at the first byte for the data fields) instead of by a multiplexer in front of them.
// The verdict is pipelined in two stages (below). The checksum accumulators keep a DEFERRED carry in bit 16 (the end-around carry of the ones' complement sum is added in the NEXT addition, so the adder never chains two carries); a sum is correct when low = 0xFFFF with no carry or low = 0xFFFE with one (their fold is 0xFFFF).
// cause: 0 forward  1 mac_bad  2 trunc (the frame ends inside the headers)  3 not_ip (type is not 0x0800 after at most two VLAN tags)  4 ip_bad (version, IHL, header checksum, total length)  5 not_udp (protocol is not 17, or a fragment)  6 udp_bad (length, checksum)  7 not_ours (VLAN id, destination address or destination port)
module hdr_filter (
    input logic clk, input logic rst,
    input logic s_valid, input logic [7:0] s_data, input logic s_last, input logic s_bad,
    input logic cfg_ip_en, input logic [31:0] cfg_ip, input logic cfg_vid_en, input logic [11:0] cfg_vid, input logic [15:0] cfg_plo, input logic [15:0] cfg_phi,
    output logic m_valid, output logic [7:0] m_data, output logic m_last, output logic m_bad,
    output logic [2:0] m_cause, output logic [1:0] m_ntags, output logic [11:0] m_vid, output logic [31:0] m_sip, output logic [31:0] m_dip,
    output logic [15:0] m_sport, output logic [15:0] m_dport, output logic [15:0] m_ulen, output logic [127:0] cnt);
    localparam logic [2:0] S_ETH = 3'd0, S_VLAN = 3'd1, S_IP = 3'd2, S_UDP = 3'd3, S_XIP = 3'd4, S_NIP = 3'd5;
    // --- control state: back to its initial value by the reset of the flip-flops at the last byte of a frame; (st_v, ntags_v) keep the final values for the verdict
    logic [2:0] st, st_n, st_v; logic [3:0] pos, pos_n; logic [1:0] ntags, ntags_n, ntags_v; logic [19:0] ipo, ipo_n; logic ipar, ipar_n, hlast, hlast_n; logic [7:0] uo, uo_n; logic upar, upar_n, uact, uact_n, uend, uend_n, uin, uin_n;
    logic [15:0] left, left_n; logic ipw, ipw_n, tpos, tpos_n, sp, sp_n, sl, sl_n, su, su_n; logic h08, h81, h88, h08_n, h81_n, h88_n;
    // --- data fields: cleared by the reset of their flip-flops at the FIRST byte of a frame (which is an Ethernet byte and captures none of them)
    logic fresh; logic [11:0] vid, vid_n; logic [7:0] vi, vi_n, proto, proto_n, ih, ih_n, uh, uh_n; logic [15:0] tot, tot_n, frag, frag_n, sport, sport_n, dport, dport_n, ulen, ulen_n, ucs, ucs_n;
    logic [31:0] sip, sip_n, dip, dip_n; logic [11:0] ipc, ipc_n; logic [16:0] ipacc, ipacc_n, uacc, uacc_n;
    logic [15:0] addend; logic do_add, a_ip, a_ul, a_pair, a_lone; logic [3:0] ihm, ihm_n; logic [5:0] hl, hl_n; logic [15:0] trem, trem_n; logic tge, tge_n;
    function automatic logic [16:0] addw(input logic [16:0] a, input logic [15:0] w);        // ones' complement add with the end-around carry DEFERRED into bit 16
        addw = {1'b0, a[15:0]} + {16'd0, a[16]} + {1'b0, w};
    endfunction
    logic lo00, loA8, d_ip, d_vl, typ_now;
    assign lo00 = (s_data == 8'h00); assign loA8 = (s_data == 8'hA8);
    assign d_ip = h08 && lo00; assign d_vl = (h81 && lo00) || (h88 && loA8);
    assign typ_now = tpos;                                                      // this byte is the low byte of an EtherType (a flag computed a byte ahead)
    always_comb begin
        st_n = st; pos_n = pos; ntags_n = ntags; ipo_n = ipo; ipar_n = ipar; hlast_n = hlast; ipw_n = ipw; tpos_n = tpos; sp_n = sp; sl_n = sl; su_n = su; uo_n = uo; upar_n = upar; uact_n = uact; uend_n = uend; uin_n = uin; left_n = left;
        h08_n = h08; h81_n = h81; h88_n = h88; vid_n = vid; vi_n = vi; proto_n = proto; ih_n = ih; uh_n = uh; tot_n = tot; frag_n = frag; sport_n = sport; dport_n = dport; ulen_n = ulen; ucs_n = ucs;
        sip_n = sip; dip_n = dip; hl_n = hl; ihm_n = ihm; trem_n = trem; tge_n = tge; ipc_n = ipc; ipacc_n = ipacc; uacc_n = uacc; addend = 16'd0; do_add = 1'b0;
        case (st)
            S_ETH, S_VLAN: begin
                pos_n = pos + 4'd1; tpos_n = (st == S_ETH && pos == 4'd12) || (st == S_VLAN && pos == 4'd2);
                if ((st == S_ETH && pos == 4'd12) || (st == S_VLAN && pos == 4'd2)) begin h08_n = (s_data == 8'h08); h81_n = (s_data == 8'h81); h88_n = (s_data == 8'h88); end
                if (st == S_VLAN && ntags == 2'd1 && pos == 4'd0) vid_n[11:8] = s_data[3:0];
                if (st == S_VLAN && ntags == 2'd1 && pos == 4'd1) vid_n[7:0] = s_data;
                if (typ_now) begin
                    pos_n = 4'd0; tpos_n = 1'b0;
                    if (d_vl && ntags < 2'd2) begin st_n = S_VLAN; ntags_n = ntags + 2'd1; end
                    else if (d_ip) begin st_n = S_IP; ipo_n = 20'd1; end
                    else st_n = S_NIP;
                end
            end
            S_IP: begin
                if (!ipc[11]) ipc_n = ipc + 12'd1;
                ipo_n = {ipo[18:0], 1'b0}; ipar_n = ~ipar;
                if (ipo[0]) begin vi_n = s_data; hl_n = {(s_data[3:0] < 4'd5) ? 4'd5 : s_data[3:0], 2'b00}; ihm_n = (s_data[3:0] < 4'd5) ? 4'd4 : s_data[3:0] - 4'd1; end      // header length in bytes, and IHL - 1, worked out once
                if (ipo[2]) tot_n[15:8] = s_data;
                if (ipo[3]) begin tot_n[7:0] = s_data; trem_n = {tot[15:8], s_data} - {10'd0, hl}; tge_n = ({tot[15:8], s_data} >= {10'd0, hl}); end      // total length minus header length, and whether it is non-negative, computed as the byte arrives
                if (ipo[6]) frag_n[15:8] = s_data;  if (ipo[7]) frag_n[7:0] = s_data;
                if (ipo[9]) proto_n = s_data;
                if (ipo[12]) sip_n[31:24] = s_data; if (ipo[13]) sip_n[23:16] = s_data; if (ipo[14]) sip_n[15:8] = s_data; if (ipo[15]) sip_n[7:0] = s_data;
                if (ipo[16]) dip_n[31:24] = s_data; if (ipo[17]) dip_n[23:16] = s_data; if (ipo[18]) dip_n[15:8] = s_data; if (ipo[19]) dip_n[7:0] = s_data;
                ipw_n = ipo[12] || ipo[14] || ipo[16] || ipo[18];                    // the NEXT byte completes an address word
                if (!ipar) ih_n = s_data;
                else ipacc_n = addw(ipacc, {ih, s_data});
                hlast_n = (ipc[5:0] == {ihm, 2'b10});                          // the NEXT byte is the last of the header
                if (hlast) begin
                    if (proto == 8'd17) begin st_n = S_UDP; uo_n = 8'd1; end else st_n = S_XIP;
                end
            end
            S_UDP: begin
                if (!ipc[11]) ipc_n = ipc + 12'd1;
                uo_n = {uo[6:0], 1'b0}; upar_n = ~upar;
                if (uo[0]) sport_n[15:8] = s_data; if (uo[1]) sport_n[7:0] = s_data; if (uo[2]) dport_n[15:8] = s_data; if (uo[3]) dport_n[7:0] = s_data;
                if (uo[4]) ulen_n[15:8] = s_data;  if (uo[5]) ulen_n[7:0] = s_data;  if (uo[6]) ucs_n[15:8] = s_data;   if (uo[7]) ucs_n[7:0] = s_data;
                if (uo[5]) begin left_n = {ulen[15:8], s_data} - 16'd6; uact_n = 1'b1; end      // bytes left in the segment, counted from byte 6 (a length of 7 or less is refused by the verdict, so no segment ends before byte 7)
                else if (uact) begin left_n = left - 16'd1; uend_n = (left == 16'd2); end
                if (uend) uin_n = 1'b0;
            end
            S_XIP: if (!ipc[11]) ipc_n = ipc + 12'd1;
            default: ;
        endcase
        // the UDP accumulator takes one of four words: an address word of the IP header (they belong to the pseudo-header), the UDP length (pseudo-header), a pair of segment bytes, or an odd last byte alone. The selects are flip-flop outputs, so the choice is an AND-OR of two LUT levels in front of the adder.
        sp_n = upar_n && uin_n; sl_n = !upar_n && uend_n && uin_n; su_n = uo_n[6] && uin_n;      // the selects, registered a byte ahead
        a_ip = ipw; a_ul = su; a_pair = sp; a_lone = sl;
        addend = ({16{a_ip}} & {ih, s_data}) | ({16{a_ul}} & ulen) | ({16{a_pair}} & {uh, s_data}) | ({16{a_lone}} & {s_data, 8'h00}); do_add = a_ip || a_ul || a_pair || a_lone;
        if (st == S_UDP && uin && !upar && !uend) uh_n = s_data;
        if (do_add) uacc_n = addw(uacc, addend);
    end
    always_ff @(posedge clk) begin
        if (rst) fresh <= 1'b1;
        else if (s_valid) fresh <= s_last;
        // control state
        if (rst || (s_valid && s_last)) begin st <= S_ETH; pos <= 4'd0; ntags <= 2'd0; ipo <= 20'd0; ipar <= 1'b0; hlast <= 1'b0; ipw <= 1'b0; tpos <= 1'b0; sp <= 1'b0; sl <= 1'b0; su <= 1'b0; uo <= 8'd0; upar <= 1'b0; uact <= 1'b0; uend <= 1'b0; uin <= 1'b1; left <= 16'd0; end
        else if (s_valid) begin st <= st_n; pos <= pos_n; ntags <= ntags_n; ipo <= ipo_n; ipar <= ipar_n; hlast <= hlast_n; ipw <= ipw_n; tpos <= tpos_n; sp <= sp_n; sl <= sl_n; su <= su_n; uo <= uo_n; upar <= upar_n; uact <= uact_n; uend <= uend_n; uin <= uin_n; left <= left_n; end
        if (s_valid) begin h08 <= h08_n; h81 <= h81_n; h88 <= h88_n; end
        if (s_valid && s_last) begin st_v <= st_n; ntags_v <= ntags_n; end
        // data fields
        if (rst || (s_valid && fresh)) begin vid <= '0; vi <= '0; proto <= '0; ih <= '0; uh <= '0; tot <= '0; frag <= '0; sport <= '0; dport <= '0; ulen <= '0; ucs <= '0; sip <= '0; dip <= '0; hl <= '0; ihm <= '0; trem <= '0; tge <= 1'b0; ipc <= '0; ipacc <= '0; uacc <= 17'h00011; end        // the pseudo-header's zero byte and protocol are the initial value of the UDP accumulator
        else if (s_valid) begin vid <= vid_n; vi <= vi_n; proto <= proto_n; ih <= ih_n; uh <= uh_n; tot <= tot_n; frag <= frag_n; sport <= sport_n; dport <= dport_n; ulen <= ulen_n; ucs <= ucs_n; sip <= sip_n; dip <= dip_n; hl <= hl_n; ihm <= ihm_n; trem <= trem_n; tge <= tge_n; ipc <= ipc_n; ipacc <= ipacc_n; uacc <= uacc_n; end
    end
    // --- the verdict in two registered stages. Stage 1 (the cycle after the last byte) turns the registers into single-bit facts, each at most one 16-bit comparison deep; stage 2 combines them into the cause.
    logic ip_sum_ok, u_sum_ok; logic o1_v, o1_l, o1_b; logic [7:0] o1_d; logic o2_v, o2_l; logic [7:0] o2_d;
    logic f_macbad, f_trunc, f_notip, f_ipok_a, f_tge, f_tle, f_notudp, f_ul8, f_ulgt, f_ucsbad, f_vidbad, f_ipbad, f_portbad; logic [1:0] v_ntags; logic [11:0] v_vid; logic [31:0] v_sip, v_dip; logic [15:0] v_sport, v_dport, v_ulen;
    assign ip_sum_ok = ipacc[16] ? (ipacc[15:0] == 16'hFFFE) : (ipacc[15:0] == 16'hFFFF);
    assign u_sum_ok = uacc[16] ? (uacc[15:0] == 16'hFFFE) : (uacc[15:0] == 16'hFFFF);
    logic [2:0] cause_n;
    always_comb begin
        if (f_macbad) cause_n = 3'd1;
        else if (f_trunc) cause_n = 3'd2;
        else if (f_notip) cause_n = 3'd3;
        else if (!f_ipok_a || !f_tge || !f_tle) cause_n = 3'd4;
        else if (f_notudp) cause_n = 3'd5;
        else if (f_ul8 || f_ulgt || f_ucsbad) cause_n = 3'd6;
        else if (f_vidbad || f_ipbad || f_portbad) cause_n = 3'd7;
        else cause_n = 3'd0;
    end
    logic [15:0] cn [0:7]; logic [7:0] inc;
    always_ff @(posedge clk) begin
        o1_v <= s_valid && !rst; o1_d <= s_data; o1_l <= s_last; o1_b <= s_bad;
        o2_v <= o1_v && !rst; o2_d <= o1_d; o2_l <= o1_v && o1_l;
        if (o1_v && o1_l) begin
            f_macbad <= o1_b; f_trunc <= (st_v == S_ETH || st_v == S_VLAN || st_v == S_IP); f_notip <= (st_v == S_NIP);
            f_ipok_a <= (vi[7:4] == 4'd4) && (vi[3:0] >= 4'd5) && ip_sum_ok; f_tge <= tge; f_tle <= (tot <= {4'd0, ipc});
            f_notudp <= (st_v != S_UDP) || (frag[13:0] != 14'd0); f_ul8 <= (ulen < 16'd8); f_ulgt <= (ulen > trem); f_ucsbad <= (ucs != 16'd0) && !u_sum_ok;
            f_vidbad <= cfg_vid_en && (ntags_v == 2'd0 || vid != cfg_vid); f_ipbad <= cfg_ip_en && (dip != cfg_ip); f_portbad <= (dport < cfg_plo) || (dport > cfg_phi);
            v_ntags <= ntags_v; v_vid <= vid; v_sip <= sip; v_dip <= dip; v_sport <= sport; v_dport <= dport; v_ulen <= ulen;
        end
        m_valid <= o2_v && !rst; m_data <= o2_d; m_last <= o2_v && o2_l;
        if (o2_v && o2_l) begin m_cause <= cause_n; m_ntags <= v_ntags; m_vid <= v_vid; m_sip <= v_sip; m_dip <= v_dip; m_sport <= v_sport; m_dport <= v_dport; m_ulen <= v_ulen; end
        for (int i = 0; i < 8; i++) inc[i] <= !rst && o2_v && o2_l && (cause_n == 3'(i));        // one-hot count strobes, registered together with m_cause: the counters see no decoder
        if (rst) for (int i = 0; i < 8; i++) cn[i] <= 16'd0;
        else for (int i = 0; i < 8; i++) if (inc[i]) cn[i] <= cn[i] + 16'd1;
    end
    assign m_bad = m_last && (m_cause != 3'd0);
    assign cnt = {cn[7], cn[6], cn[5], cn[4], cn[3], cn[2], cn[1], cn[0]};
endmodule
// hdr_path: the receive side of a UDP node in one clock domain: PHY bytes -> mac_rx -> hdr_filter -> frame_fifo. Only valid UDP frames for this node are committed; everything else is rolled back by the frame buffer. `cnt` = frames per cause.
module hdr_path #(parameter int AW = 11) (
    input logic clk, input logic rst, input logic rx_dv, input logic rx_er, input logic [7:0] rxd,
    input logic cfg_ip_en, input logic [31:0] cfg_ip, input logic cfg_vid_en, input logic [11:0] cfg_vid, input logic [15:0] cfg_plo, input logic [15:0] cfg_phi,
    output logic o_valid, output logic [7:0] o_data, output logic o_last, input logic o_ready,
    output logic [15:0] n_ok, output logic [15:0] n_bad, output logic [15:0] n_ovf, output logic [127:0] cnt);
    logic a_v, a_l, a_b, b_v, b_l, b_bad, rdy; logic [7:0] a_d, b_d; logic [2:0] cause; logic [1:0] nt; logic [11:0] vd; logic [31:0] si, di; logic [15:0] sp, dp, ul;
    mac_rx mrx (.clk(clk), .rst(rst), .rx_dv(rx_dv), .rx_er(rx_er), .rxd(rxd), .m_valid(a_v), .m_data(a_d), .m_last(a_l), .m_bad(a_b));
    hdr_filter hf (.clk(clk), .rst(rst), .s_valid(a_v), .s_data(a_d), .s_last(a_l), .s_bad(a_b), .cfg_ip_en(cfg_ip_en), .cfg_ip(cfg_ip), .cfg_vid_en(cfg_vid_en), .cfg_vid(cfg_vid), .cfg_plo(cfg_plo), .cfg_phi(cfg_phi),
        .m_valid(b_v), .m_data(b_d), .m_last(b_l), .m_bad(b_bad), .m_cause(cause), .m_ntags(nt), .m_vid(vd), .m_sip(si), .m_dip(di), .m_sport(sp), .m_dport(dp), .m_ulen(ul), .cnt(cnt));
    frame_fifo #(.AW(AW)) ff (.clk(clk), .rst(rst), .in_valid(b_v), .in_data(b_d), .in_last(b_l), .in_bad(b_bad), .in_ready(rdy), .out_valid(o_valid), .out_data(o_data), .out_last(o_last), .out_ready(o_ready), .n_ok(n_ok), .n_bad(n_bad), .n_ovf(n_ovf));
endmodule
// hdr_filter_syn and hdr_path_syn: the same designs behind a handful of pins, ONLY so that they fit a chip's pins for the place-and-route measurements (the iCE40 HX8K has 256, the ECP5-25F 197; hdr_filter alone has 359). The 78 configuration bits are shifted in serially (cfg_sh, cfg_si) and the metadata and counters leave 16 bits at a time, chosen by `sel`. The wrappers' own cost (78 flip-flops and a 16-bit multiplexer) is part of the numbers measured with them.
module hdr_filter_syn (
    input logic clk, input logic rst, input logic s_valid, input logic [7:0] s_data, input logic s_last, input logic s_bad, input logic cfg_si, input logic cfg_sh, input logic [3:0] sel,
    output logic m_valid, output logic [7:0] m_data, output logic m_last, output logic m_bad, output logic [2:0] m_cause, output logic [15:0] info);
    logic [77:0] cfg; logic [1:0] nt; logic [11:0] vd; logic [31:0] si, di; logic [15:0] sp, dp, ul; logic [127:0] cnt; logic [255:0] all_bits;
    always_ff @(posedge clk) if (cfg_sh) cfg <= {cfg[76:0], cfg_si};
    hdr_filter hf (.clk(clk), .rst(rst), .s_valid(s_valid), .s_data(s_data), .s_last(s_last), .s_bad(s_bad), .cfg_ip_en(cfg[0]), .cfg_ip(cfg[32:1]), .cfg_vid_en(cfg[33]), .cfg_vid(cfg[45:34]), .cfg_plo(cfg[61:46]), .cfg_phi(cfg[77:62]),
        .m_valid(m_valid), .m_data(m_data), .m_last(m_last), .m_bad(m_bad), .m_cause(m_cause), .m_ntags(nt), .m_vid(vd), .m_sip(si), .m_dip(di), .m_sport(sp), .m_dport(dp), .m_ulen(ul), .cnt(cnt));
    assign all_bits = {cnt, nt, vd, si, di, sp, dp, ul, 2'b00};
    always_ff @(posedge clk) info <= all_bits[{sel, 4'b0000} +: 16];            // registered, so that the pin path of the multiplexer is not what the clock measurement finds
endmodule
module hdr_path_syn #(parameter int AW = 11) (
    input logic clk, input logic rst, input logic rx_dv, input logic rx_er, input logic [7:0] rxd, input logic cfg_si, input logic cfg_sh, input logic [2:0] sel,
    output logic o_valid, output logic [7:0] o_data, output logic o_last, input logic o_ready, output logic [15:0] info);
    logic [77:0] cfg; logic [127:0] cnt; logic [15:0] n_ok, n_bad, n_ovf;
    always_ff @(posedge clk) if (cfg_sh) cfg <= {cfg[76:0], cfg_si};
    hdr_path #(.AW(AW)) hp (.clk(clk), .rst(rst), .rx_dv(rx_dv), .rx_er(rx_er), .rxd(rxd), .cfg_ip_en(cfg[0]), .cfg_ip(cfg[32:1]), .cfg_vid_en(cfg[33]), .cfg_vid(cfg[45:34]), .cfg_plo(cfg[61:46]), .cfg_phi(cfg[77:62]),
        .o_valid(o_valid), .o_data(o_data), .o_last(o_last), .o_ready(o_ready), .n_ok(n_ok), .n_bad(n_bad), .n_ovf(n_ovf), .cnt(cnt));
    always_ff @(posedge clk) info <= cnt[{sel, 4'b0000} +: 16] ^ n_ok ^ n_bad ^ n_ovf;      // the frame buffer's counters are folded in only so that they are not optimised away
endmodule
