// verilator lint_off DECLFILENAME
// verilator lint_off UNUSEDSIGNAL
// Chapter 9, FIRST VERSION of the header filter (kept so that the book can show what its measurement found: Fmax 61 MHz on iCE40 and 77 MHz on ECP5). The final design is rtl/hdr.sv.
//
// hdr_filter: a stream of frame bytes (valid, data, last, bad: the output of mac_rx, FCS already removed; no ready, bytes may arrive on any cycle) -> the same bytes two cycles later with the frame's verdict:
//   m_bad = 1 on the last byte unless the frame is a valid IPv4/UDP frame for this node (so frame_fifo drops everything else), and the CAUSE with the fields that were seen.
// One byte per clock, whatever the header length: a small state machine follows the headers, each field is captured by position, and two 17-bit accumulators add the 16-bit words of the IPv4 header and of the UDP pseudo-header + segment. The accumulator keeps a DEFERRED carry in bit 16 (the end-around carry of the ones' complement sum is added in the NEXT addition, so the adder never chains two carries). The verdict is a function of registers, taken in the cycle after the last byte and registered.
// cause: 0 forward  1 mac_bad  2 trunc (the frame ends inside the headers)  3 not_ip (type is not 0x0800 after at most two VLAN tags)  4 ip_bad (version, IHL, header checksum, total length)  5 not_udp (protocol is not 17, or a fragment)  6 udp_bad (length, checksum)  7 not_ours (VLAN id, destination address or destination port)
module hdr_filter_v1 (
    input logic clk, input logic rst,
    input logic s_valid, input logic [7:0] s_data, input logic s_last, input logic s_bad,
    input logic cfg_ip_en, input logic [31:0] cfg_ip, input logic cfg_vid_en, input logic [11:0] cfg_vid, input logic [15:0] cfg_plo, input logic [15:0] cfg_phi,
    output logic m_valid, output logic [7:0] m_data, output logic m_last, output logic m_bad,
    output logic [2:0] m_cause, output logic [1:0] m_ntags, output logic [11:0] m_vid, output logic [31:0] m_sip, output logic [31:0] m_dip,
    output logic [15:0] m_sport, output logic [15:0] m_dport, output logic [15:0] m_ulen, output logic [127:0] cnt);
    localparam logic [2:0] S_ETH = 3'd0, S_VLAN = 3'd1, S_IP = 3'd2, S_UDP = 3'd3, S_XIP = 3'd4, S_NIP = 3'd5;
    // --- state of the frame being absorbed. `fresh` = the previous frame ended: every field reads as its initial value (the *_c copies), so frames may follow each other with no idle cycle.
    logic fresh; logic [2:0] st; logic [3:0] pos; logic [1:0] ntags; logic [11:0] vid; logic [7:0] th, vi, proto, ih, uh; logic [15:0] tot, frag, sport, dport, ulen, ucs;
    logic [31:0] sip, dip; logic [11:0] ipc, uc; logic [16:0] ipacc, uacc; logic uin;
    logic [2:0] st_c; logic [3:0] pos_c; logic [1:0] ntags_c; logic [11:0] vid_c; logic [7:0] th_c, vi_c, proto_c, ih_c, uh_c; logic [15:0] tot_c, frag_c, sport_c, dport_c, ulen_c, ucs_c;
    logic [31:0] sip_c, dip_c; logic [11:0] ipc_c, uc_c; logic [16:0] ipacc_c, uacc_c; logic uin_c;
    assign st_c = fresh ? S_ETH : st; assign pos_c = fresh ? 4'd0 : pos; assign ntags_c = fresh ? 2'd0 : ntags; assign vid_c = fresh ? 12'd0 : vid; assign th_c = fresh ? 8'd0 : th;
    assign vi_c = fresh ? 8'd0 : vi; assign proto_c = fresh ? 8'd0 : proto; assign ih_c = fresh ? 8'd0 : ih; assign uh_c = fresh ? 8'd0 : uh; assign tot_c = fresh ? 16'd0 : tot;
    assign frag_c = fresh ? 16'd0 : frag; assign sport_c = fresh ? 16'd0 : sport; assign dport_c = fresh ? 16'd0 : dport; assign ulen_c = fresh ? 16'd0 : ulen; assign ucs_c = fresh ? 16'd0 : ucs;
    assign sip_c = fresh ? 32'd0 : sip; assign dip_c = fresh ? 32'd0 : dip; assign ipc_c = fresh ? 12'd0 : ipc; assign uc_c = fresh ? 12'd0 : uc;
    assign ipacc_c = fresh ? 17'd0 : ipacc; assign uacc_c = fresh ? 17'd0 : uacc; assign uin_c = fresh ? 1'b1 : uin;
    // --- next state
    logic [2:0] st_n; logic [3:0] pos_n; logic [1:0] ntags_n; logic [11:0] vid_n; logic [7:0] th_n, vi_n, proto_n, ih_n, uh_n; logic [15:0] tot_n, frag_n, sport_n, dport_n, ulen_n, ucs_n;
    logic [31:0] sip_n, dip_n; logic [11:0] ipc_n, uc_n; logic [16:0] ipacc_n, uacc_n; logic uin_n;
    logic [15:0] typ; logic is_vlan; logic [3:0] ihl_c; logic [5:0] hdr_last; logic uend; logic [15:0] addend; logic do_add;
    assign typ = {th_c, s_data};
    assign is_vlan = (typ == 16'h8100) || (typ == 16'h88A8);
    assign ihl_c = (vi_c[3:0] < 4'd5) ? 4'd5 : vi_c[3:0];
    assign hdr_last = {ihl_c - 4'd1, 2'b11};                               // index of the last byte of the IP header: 4 * IHL - 1
    assign uend = (uc_c > 12'd5) && (uc_c + 12'd1 == ulen_c[11:0]) && (ulen_c[15:12] == 4'd0);
    function automatic logic [16:0] addw(input logic [16:0] a, input logic [15:0] w);        // ones' complement add with the end-around carry DEFERRED into bit 16
        addw = {1'b0, a[15:0]} + {16'd0, a[16]} + {1'b0, w};
    endfunction
    always_comb begin
        st_n = st_c; pos_n = pos_c; ntags_n = ntags_c; vid_n = vid_c; th_n = th_c; vi_n = vi_c; proto_n = proto_c; ih_n = ih_c; uh_n = uh_c; tot_n = tot_c; frag_n = frag_c;
        sport_n = sport_c; dport_n = dport_c; ulen_n = ulen_c; ucs_n = ucs_c; sip_n = sip_c; dip_n = dip_c; ipc_n = ipc_c; uc_n = uc_c; ipacc_n = ipacc_c; uacc_n = uacc_c; uin_n = uin_c;
        addend = 16'd0; do_add = 1'b0;
        case (st_c)
            S_ETH, S_VLAN: begin
                pos_n = pos_c + 4'd1;
                if (st_c == S_ETH) begin
                    if (pos_c == 4'd12) th_n = s_data;
                end else begin
                    if (pos_c == 4'd0 && ntags_c == 2'd1) vid_n[11:8] = s_data[3:0];
                    if (pos_c == 4'd1 && ntags_c == 2'd1) vid_n[7:0] = s_data;
                    if (pos_c == 4'd2) th_n = s_data;
                end
                if ((st_c == S_ETH && pos_c == 4'd13) || (st_c == S_VLAN && pos_c == 4'd3)) begin
                    pos_n = 4'd0;
                    if (is_vlan && ntags_c < 2'd2) begin st_n = S_VLAN; ntags_n = ntags_c + 2'd1; end
                    else if (typ == 16'h0800) st_n = S_IP;
                    else st_n = S_NIP;
                end
            end
            S_IP: begin
                if (ipc_c != 12'hFFF) ipc_n = ipc_c + 12'd1;
                case (ipc_c)
                    12'd0: vi_n = s_data;
                    12'd2: tot_n[15:8] = s_data;   12'd3: tot_n[7:0] = s_data;
                    12'd6: frag_n[15:8] = s_data;  12'd7: frag_n[7:0] = s_data;
                    12'd9: proto_n = s_data;
                    12'd12: sip_n[31:24] = s_data; 12'd13: sip_n[23:16] = s_data; 12'd14: sip_n[15:8] = s_data; 12'd15: sip_n[7:0] = s_data;
                    12'd16: dip_n[31:24] = s_data; 12'd17: dip_n[23:16] = s_data; 12'd18: dip_n[15:8] = s_data; 12'd19: dip_n[7:0] = s_data;
                    default: ;
                endcase
                if (!ipc_c[0]) ih_n = s_data;
                else begin
                    ipacc_n = addw(ipacc_c, {ih_c, s_data});
                    if (ipc_c >= 12'd13 && ipc_c <= 12'd19) begin do_add = 1'b1; addend = {ih_c, s_data}; end      // the address words also belong to the UDP pseudo-header
                end
                if (ipc_c[5:0] == hdr_last) begin st_n = (proto_c == 8'd17) ? S_UDP : S_XIP; uc_n = 12'd0; end
            end
            S_UDP: begin
                if (ipc_c != 12'hFFF) ipc_n = ipc_c + 12'd1;
                if (uc_c != 12'hFFF) uc_n = uc_c + 12'd1;
                case (uc_c)
                    12'd0: sport_n[15:8] = s_data; 12'd1: sport_n[7:0] = s_data; 12'd2: dport_n[15:8] = s_data; 12'd3: dport_n[7:0] = s_data;
                    12'd4: ulen_n[15:8] = s_data;  12'd5: ulen_n[7:0] = s_data;  12'd6: ucs_n[15:8] = s_data;   12'd7: ucs_n[7:0] = s_data;
                    default: ;
                endcase
                if (uin_c) begin
                    if (uc_c[0]) begin do_add = 1'b1; addend = {uh_c, s_data}; end
                    else if (uend) begin do_add = 1'b1; addend = {s_data, 8'h00}; end            // an odd length: the last byte is the high half of a word
                    else begin
                        uh_n = s_data;
                        if (uc_c == 12'd0) begin do_add = 1'b1; addend = 16'h0011; end              // the pseudo-header's zero byte and protocol
                        if (uc_c == 12'd6) begin do_add = 1'b1; addend = ulen_c; end                // the pseudo-header's UDP length (the segment's own copy is added with the segment)
                    end
                    if (uend) uin_n = 1'b0;
                end
            end
            S_XIP: if (ipc_c != 12'hFFF) ipc_n = ipc_c + 12'd1;
            default: ;
        endcase
        if (do_add) uacc_n = addw(uacc_c, addend);
    end
    always_ff @(posedge clk) begin
        if (rst) fresh <= 1'b1;
        else if (s_valid) begin
            fresh <= s_last;
            st <= st_n; pos <= pos_n; ntags <= ntags_n; vid <= vid_n; th <= th_n; vi <= vi_n; proto <= proto_n; ih <= ih_n; uh <= uh_n; tot <= tot_n; frag <= frag_n;
            sport <= sport_n; dport <= dport_n; ulen <= ulen_n; ucs <= ucs_n; sip <= sip_n; dip <= dip_n; ipc <= ipc_n; uc <= uc_n; ipacc <= ipacc_n; uacc <= uacc_n; uin <= uin_n;
        end
    end
    // --- the verdict, from the registers, in the cycle after the last byte
    logic [16:0] f1, g1; logic [15:0] f2, g2; logic ip_sum_ok, u_sum_ok, ip_ok, not_udp, udp_bad, not_ours; logic [5:0] hl; logic [2:0] cause_n;
    assign f1 = {1'b0, ipacc[15:0]} + {16'd0, ipacc[16]}; assign f2 = f1[15:0] + {15'd0, f1[16]}; assign ip_sum_ok = (f2 == 16'hFFFF);
    assign g1 = {1'b0, uacc[15:0]} + {16'd0, uacc[16]}; assign g2 = g1[15:0] + {15'd0, g1[16]}; assign u_sum_ok = (g2 == 16'hFFFF);
    assign hl = {(vi[3:0] < 4'd5) ? 4'd5 : vi[3:0], 2'b00};
    assign ip_ok = (vi[7:4] == 4'd4) && (vi[3:0] >= 4'd5) && ip_sum_ok && (tot >= {10'd0, hl}) && (tot <= {4'd0, ipc});
    assign not_udp = (st != S_UDP) || (frag[13:0] != 14'd0);
    assign udp_bad = (ulen < 16'd8) || (ulen > tot - {10'd0, hl}) || ((ucs != 16'd0) && !u_sum_ok);
    assign not_ours = (cfg_vid_en && (ntags == 2'd0 || vid != cfg_vid)) || (cfg_ip_en && dip != cfg_ip) || (dport < cfg_plo) || (dport > cfg_phi);
    logic o1_v, o1_l, o1_b; logic [7:0] o1_d;
    always_comb begin
        if (o1_b) cause_n = 3'd1;
        else if (st == S_ETH || st == S_VLAN || st == S_IP) cause_n = 3'd2;
        else if (st == S_NIP) cause_n = 3'd3;
        else if (!ip_ok) cause_n = 3'd4;
        else if (not_udp) cause_n = 3'd5;
        else if (udp_bad) cause_n = 3'd6;
        else if (not_ours) cause_n = 3'd7;
        else cause_n = 3'd0;
    end
    logic [15:0] cn [0:7];
    always_ff @(posedge clk) begin
        o1_v <= s_valid && !rst; o1_d <= s_data; o1_l <= s_last; o1_b <= s_bad;
        m_valid <= o1_v && !rst; m_data <= o1_d; m_last <= o1_v && o1_l;
        if (o1_v && o1_l) begin m_cause <= cause_n; m_ntags <= ntags; m_vid <= vid; m_sip <= sip; m_dip <= dip; m_sport <= sport; m_dport <= dport; m_ulen <= ulen; end
        if (rst) for (int i = 0; i < 8; i++) cn[i] <= 16'd0;
        else if (m_valid && m_last) cn[m_cause] <= cn[m_cause] + 16'd1;
    end
    assign m_bad = m_last && (m_cause != 3'd0);
    assign cnt = {cn[7], cn[6], cn[5], cn[4], cn[3], cn[2], cn[1], cn[0]};
endmodule
// hdr_filter_v1_syn: the same designs behind a handful of pins, ONLY so that they fit a chip's pins for the place-and-route measurements (the iCE40 HX8K has 256, the ECP5-25F 197; hdr_filter alone has 359). The 78 configuration bits are shifted in serially (cfg_sh, cfg_si) and the metadata and counters leave 16 bits at a time, chosen by `sel`. The wrappers' own cost (78 flip-flops and a 16-bit multiplexer) is part of the numbers measured with them.
module hdr_filter_v1_syn (
    input logic clk, input logic rst, input logic s_valid, input logic [7:0] s_data, input logic s_last, input logic s_bad, input logic cfg_si, input logic cfg_sh, input logic [3:0] sel,
    output logic m_valid, output logic [7:0] m_data, output logic m_last, output logic m_bad, output logic [2:0] m_cause, output logic [15:0] info);
    logic [77:0] cfg; logic [1:0] nt; logic [11:0] vd; logic [31:0] si, di; logic [15:0] sp, dp, ul; logic [127:0] cnt; logic [255:0] all_bits;
    always_ff @(posedge clk) if (cfg_sh) cfg <= {cfg[76:0], cfg_si};
    hdr_filter_v1 hf (.clk(clk), .rst(rst), .s_valid(s_valid), .s_data(s_data), .s_last(s_last), .s_bad(s_bad), .cfg_ip_en(cfg[0]), .cfg_ip(cfg[32:1]), .cfg_vid_en(cfg[33]), .cfg_vid(cfg[45:34]), .cfg_plo(cfg[61:46]), .cfg_phi(cfg[77:62]),
        .m_valid(m_valid), .m_data(m_data), .m_last(m_last), .m_bad(m_bad), .m_cause(m_cause), .m_ntags(nt), .m_vid(vd), .m_sip(si), .m_dip(di), .m_sport(sp), .m_dport(dp), .m_ulen(ul), .cnt(cnt));
    assign all_bits = {cnt, nt, vd, si, di, sp, dp, ul, 2'b00};
    always_ff @(posedge clk) info <= all_bits[{sel, 4'b0000} +: 16];            // registered, so that the pin path of the multiplexer is not what the clock measurement finds
endmodule
