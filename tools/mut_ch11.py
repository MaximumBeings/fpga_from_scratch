#!/usr/bin/env python3
"""Chapter 11: test the tests. Mutants of rtl/udp.sv (header bytes, both builders, the pacer). The battery: both builders against the specification on several seeds (the store-and-forward one also with a slow source and oversize payloads), the pacer alone against the cycle-exact model, and the pacer in the system (frames exact, token-bucket bound on the start times). Usage: mut_ch11.py"""
import concurrent.futures as cf, os, re, shutil, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, hw, mac_gold as mg, udp_gold as g
M = "rtl/udp.sv"; F = ["rtl/crc32_stream.sv", "rtl/mac.sv", "rtl/udp.sv", "tb/udp_tb.sv"]
MUTANTS = [
 ("hdr: EtherType 0x0801", "6'd12: b = 8'h08; 6'd13: b = 8'h00;", "6'd12: b = 8'h08; 6'd13: b = 8'h01;"),
 ("hdr: IP version/IHL 0x46", "6'd14: b = 8'h45;", "6'd14: b = 8'h46;"),
 ("hdr: total length low byte swapped with high", "6'd16: b = totlen[15:8]; 6'd17: b = totlen[7:0];", "6'd16: b = totlen[7:0]; 6'd17: b = totlen[15:8];"),
 ("hdr: flags are not don't-fragment", "6'd20: b = 8'h40; 6'd21: b = 8'h00;", "6'd20: b = 8'h00; 6'd21: b = 8'h00;"),
 ("hdr: TTL 63", "6'd22: b = 8'h40;", "6'd22: b = 8'h3F;"),
 ("hdr: protocol 6", "6'd23: b = 8'h11;", "6'd23: b = 8'h06;"),
 ("hdr: source and destination addresses swapped", "6'd26: b = sip[31:24]; 6'd27: b = sip[23:16]; 6'd28: b = sip[15:8]; 6'd29: b = sip[7:0];", "6'd26: b = dip[31:24]; 6'd27: b = dip[23:16]; 6'd28: b = dip[15:8]; 6'd29: b = dip[7:0];"),
 ("hdr: destination MAC byte 5 is the source's", "6'd5: b = dmac[7:0];", "6'd5: b = smac[7:0];"),
 ("hdr: UDP length bytes swapped", "6'd38: b = ulen[15:8]; 6'd39: b = ulen[7:0];", "6'd38: b = ulen[7:0]; 6'd39: b = ulen[15:8];"),
 ("hdr: ports swapped", "6'd34: b = sport[15:8]; 6'd35: b = sport[7:0]; 6'd36: b = dport[15:8]; 6'd37: b = dport[7:0];", "6'd34: b = dport[15:8]; 6'd35: b = dport[7:0]; 6'd36: b = sport[15:8]; 6'd37: b = sport[7:0];"),
 ("sf: the IP total length is len + 27", "assign totlen = {4'd0, len} + 16'd28; assign ulen = {4'd0, len} + 16'd8;", "assign totlen = {4'd0, len} + 16'd27; assign ulen = {4'd0, len} + 16'd8;"),
 ("sf: the UDP length is len + 9", "assign totlen = {4'd0, len} + 16'd28; assign ulen = {4'd0, len} + 16'd8;", "assign totlen = {4'd0, len} + 16'd28; assign ulen = {4'd0, len} + 16'd9;"),
 ("sf: the IP checksum omits the id", "4'd2: begin ipw = id; uw = dip[31:16]; end", "4'd2: begin ipw = 16'h0000; uw = dip[31:16]; end"),
 ("sf: the IP checksum omits the flags word", "4'd3: begin ipw = 16'h4000; uw = dip[15:0]; end", "4'd3: begin ipw = 16'h0000; uw = dip[15:0]; end"),
 ("sf: the pseudo-header protocol is missing", "4'd4: begin ipw = 16'h4011; uw = 16'h0011; end", "4'd4: begin ipw = 16'h4011; uw = 16'h0000; end"),
 ("sf: the pseudo-header length is missing", "4'd5: begin ipw = cfg_sip[31:16]; uw = ulen; end", "4'd5: begin ipw = cfg_sip[31:16]; uw = 16'h0000; end"),
 ("sf: the UDP checksum omits the destination port", "4'd7: begin ipw = dip[31:16]; uw = dport; end", "4'd7: begin ipw = dip[31:16]; uw = 16'h0000; end"),
 ("sf: the UDP checksum omits the UDP header's length", "default: begin ipw = dip[15:0]; uw = ulen; end", "default: begin ipw = dip[15:0]; uw = 16'h0000; end"),
 ("sf: the payload sum starts from the IP sum", "ua <= addw(step == 4'd0 ? acc : ua, uw);", "ua <= addw(step == 4'd0 ? ia : ua, uw);"),
 ("sf: the carry of the payload sum is dropped", "else acc <= addw(acc, {hold, s_data});", "else acc <= {1'b0, acc[15:0]} + {1'b0, hold, s_data};"),
 ("sf: an odd last byte is the low half of a word", "if (s_last) acc <= addw(acc, {s_data, 8'h00});", "if (s_last) acc <= addw(acc, {8'h00, s_data});"),
 ("sf: an odd last byte is not added", "if (s_last) acc <= addw(acc, {s_data, 8'h00});", ""),
 ("sf: no fold at the end", "else if (step == 4'd9) begin ia <= {1'b0, f1i[15:0]} + {16'd0, f1i[16]}; ua <= {1'b0, f1u[15:0]} + {16'd0, f1u[16]}; end", "else if (step == 4'd9) begin ia <= ia; ua <= ua; end"),
 ("sf: a checksum of zero is sent as zero", "ucs <= (ua[15:0] == 16'hFFFF) ? 16'hFFFF : ~ua[15:0];", "ucs <= ~ua[15:0];"),
 ("sf: the IP checksum is not complemented", "begin ipcs <= ~ia[15:0]; ucs", "begin ipcs <= ia[15:0]; ucs"),
 ("ct: the IP checksum is not complemented", "aipcs <= ~ia[15:0];", "aipcs <= ia[15:0];"),
 ("ct: no fold at the end", "else if (step == 4'd9) ia <= {1'b0, f1i[15:0]} + {16'd0, f1i[16]};", "else if (step == 4'd9) ia <= ia;"),
 ("sf: the maximum payload is 1473", "if (cnt >= 12'(MAXP)) begin n_drop", "if (cnt > 12'(MAXP)) begin n_drop"),
 ("sf: the maximum payload is 1471", "if (cnt >= 12'(MAXP)) begin n_drop", "if (cnt >= 12'(MAXP - 1)) begin n_drop"),
 ("sf: an oversize packet is not dropped", "if (cnt >= 12'(MAXP)) begin n_drop", "if (1'b0) begin n_drop"),
 ("sf: the accumulator is not cleared after a drop", "begin n_drop <= n_drop + 16'd1; cnt <= '0; acc <= '0;", "begin n_drop <= n_drop + 16'd1; cnt <= '0;"),
 ("sf: the accumulator is not cleared after a frame", "have <= 1'b0; cnt <= '0; acc <= '0; id <= id + 16'd1;", "have <= 1'b0; cnt <= '0; id <= id + 16'd1;"),
 ("sf: the id does not advance", "id <= id + 16'd1; n_pkt <= n_pkt + 16'd1;", "n_pkt <= n_pkt + 16'd1;"),
 ("sf: the destination port is the previous packet's", "have <= 1'b1; dport <= d_dport; dip <= d_dip; end", "have <= 1'b1; dip <= d_dip; end"),
 ("sf: the wire cost is not padded to 60", "p_len = ((len + 12'd42 < 12'd60) ? 11'd60 : 11'(len + 12'd42)) + 11'd24;", "p_len = 11'(len + 12'd42) + 11'd24;"),
 ("sf: the wire cost omits the gap", "11'(len + 12'd42)) + 11'd24;", "11'(len + 12'd42)) + 11'd12;"),
 ("sf: the payload read is one byte late", "assign ra = AW'((adv ? kn : k) - 12'd42);", "assign ra = AW'((adv ? k : k) - 12'd42);"),
 ("sf: the last byte is marked one early", "assign lastb = shown && (k == total - 12'd1);", "assign lastb = shown && (k == total - 12'd2);"),
 ("sf: the output does not hold while the MAC is not ready", "assign adv = !shown || o_ready;", "assign adv = 1'b1;"),
 ("ct: the IP total length is len + 27", "assign etot = {5'd0, elen} + 16'd28;", "assign etot = {5'd0, elen} + 16'd27;"),
 ("ct: the IP checksum uses the previous id", "4'd2: ipw = aid;", "4'd2: ipw = aid + 16'd1;"),
 ("ct: the UDP checksum is not zero", ".ulen(eulen), .ucs(16'h0000), .b(hb));", ".ulen(eulen), .ucs(16'h0001), .b(hb));"),
 ("ct: payload is accepted during the headers", "assign s_ready = run && !hdr_ph && o_ready;", "assign s_ready = run && o_ready;"),
 ("ct: the next descriptor overwrites the waiting one", "A_WAIT: if (es == E_IDLE) begin", "A_WAIT: if (1'b1) begin"),
 ("ct: the descriptor's address is not captured", "alen <= d_len; adport <= d_dport; adip <= d_dip;", "alen <= d_len; adport <= d_dport;"),
 ("pacer: the bucket does not saturate", "assign nb = sb[BL + 8] ? CAPU : sb[W-1:0];", "assign nb = sb[W-1:0];"),
 ("pacer: the bucket starts empty", "if (rst) begin credit <= CAPU;", "if (rst) begin credit <= '0;"),
 ("pacer: a grant needs one unit more", "ok_r <= (credit >= cost_r) && !go;", "ok_r <= (credit > cost_r) && !go;"),
 ("pacer: the comparison is not cleared by a grant", "ok_r <= (credit >= cost_r) && !go;", "ok_r <= (credit >= cost_r);"),
 ("pacer: the request is delayed once, not twice", "assign go = req && r2 && ok_r;", "assign go = req && r1 && ok_r;"),
 ("pacer: the delayed request is ignored", "assign go = req && r2 && ok_r;", "assign go = req && ok_r;"),
 ("pacer: the current request is ignored", "assign go = req && r2 && ok_r;", "assign go = r2 && ok_r;"),
 ("pacer: a grant takes no credit", "credit <= go ? na : nb;", "credit <= nb;"),
 ("pacer: the rate is not added on a grant cycle", "assign sa = $signed({1'b0, credit}) + d_r;", "assign sa = $signed({1'b0, credit}) + d_r - $signed({1'b0, {(W - 9){1'b0}}, rate});"),
 ("pacer: the rate is halved when idle", "assign sb = {1'b0, credit} + {{(W - 8){1'b0}}, rate};", "assign sb = {1'b0, credit} + {{(W - 8){1'b0}}, 1'b0, rate[8:1]};"),
 ("pacer: the cost is that of the length minus one", "cost_r <= W'({len, 8'd0});", "cost_r <= W'({len - 11'd1, 8'd0});"),
 ("pacer: the cost of the first (combinational) version is not taken", "assign after = go ? credit - cost : credit;", "assign after = credit;"),
 ("pacer_comb: a grant without a request", "assign go = req && (credit >= cost);", "assign go = (credit >= cost);"),
]
def battery(root):
    def run(pk, ct, pace=0, rate=256, src=100):
        g.write_pkts(pk, os.path.join(root, "out", "udp_desc.hex"), os.path.join(root, "out", "udp_bytes.hex"))
        d = (f"NP={len(pk)}", f"TOT={sum(len(q['payload']) for q in pk)}", f"CT={ct}", f"PACE={pace}", f"RATE={rate}", f"SRC={src}"); return hw.sim_icarus(F, "udp_tb", root=root, defines=d + ("MAXCYC=900000",))[1]
    wires = lambda o: [w for w, _ in mg.parse_frames(o, "WIRE")]
    for ct in (0, 1):
        for seed in range(4):
            pk = g.make_packets(seed, 24, oversize=(ct == 0)); e, drop = g.expected_frames(pk, ct=bool(ct)); o = run(pk, ct)
            if wires(o) != e: return f"{'cut-through' if ct else 'store-and-forward'} builder, seed {seed}"
            if ct == 0 and re.search(r"STATS \d+ (\d+)", o) and int(re.search(r"STATS \d+ (\d+)", o).group(1)) != drop: return f"drop count, seed {seed}"
    pk = g.make_packets(9, 14); e, _ = g.expected_frames(pk)
    if wires(run(pk, 0, src=55)) != e: return "store-and-forward builder, slow source"
    for comb in (0, 1):
        for rate in (16, 64, 256):
            st = g.pacer_stim(rate, 12000); g.write_pacer(os.path.join(root, "out", "pacer_stim.hex"), st)
            o = hw.sim_icarus(["rtl/udp.sv", "tb/pacer_tb.sv"], "pacer_tb", root=root, defines=(f"NC={len(st)}", f"RATE={rate}", f"COMB={comb}"))[1]
            got = [(int(a), int(b)) for a, b in re.findall(r"G (\d+) (\d+)", o)]; m = g.PacerModelComb() if comb else g.PacerModel(rate=rate); exp = [(k, ln) for k, (r, ln) in enumerate(st) if m.step(r, ln, rate)]
            if got != exp: return f"pacer alone, {'combinational' if comb else 'pipelined'}, rate {rate}"
    for ct, pace in ((0, 1), (1, 1), (1, 2)):
        for rate in (32, 160):
            pk = [q for q in g.make_packets(7, 20, sizes=[18, 100, 400, 1000]) if len(q["payload"]) <= g.MAXP]; o = run(pk, ct, pace=pace, rate=rate); e, _ = g.expected_frames(pk, ct=bool(ct))
            if wires(o) != e: return f"pacer in the system, frames, ct {ct}, pacer {pace}, rate {rate}"
            stt = [int(x) for x in re.findall(r"START (\d+)", o)]; cost = [g.wire_cost(len(q["payload"])) for q in pk]
            for i in range(len(stt)):
                tot = 0
                for j in range(i, len(stt)):
                    tot += cost[j]
                    if tot > 4096 + rate * (stt[j] - stt[i]) / 256 + 1e-9: return f"pacer in the system, token-bucket bound, ct {ct}, pacer {pace}, rate {rate}"
            if rate == 32:
                achieved = sum(cost[1:]) / (stt[-1] - stt[0])
                if achieved < 0.8 * rate / 256: return f"pacer in the system, rate too low (ct {ct}, pacer {pace})"
    return None
def one(m):
    label, old, new = m; d = tempfile.mkdtemp(prefix="mut11_")
    for sub in ("rtl", "tb", "out", "model"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub), ignore=shutil.ignore_patterns("*.json", "*_synth.log", "*.hex"))
    p = os.path.join(d, M); s = open(p).read()
    if s.count(old) != 1: shutil.rmtree(d, ignore_errors=True); return label, f"BAD ANCHOR ({s.count(old)} occurrences)"
    open(p, "w").write(s.replace(old, new)); r = battery(d); shutil.rmtree(d, ignore_errors=True); return label, ("NOT CAUGHT" if r is None else "caught by: " + r)
if __name__ == "__main__":
    print("NOTE: this script deliberately breaks copies of the RTL. 'caught' lines are EXPECTED: they show the battery notices the mistake.")
    base = battery(flow.ROOT); print("unmutated design passes the whole battery:", base is None, "" if base is None else base)
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(one, MUTANTS))
    caught = 0
    for label, st in res: print(f"  {label}: {st}"); caught += st.startswith("caught")
    print(f"mutants caught: {caught} of {len(MUTANTS)}")
    sys.exit(0 if base is None and caught == len(MUTANTS) else 1)
