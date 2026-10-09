#!/usr/bin/env python3
"""Chapter 9: test the tests. Mutants of rtl/hdr.sv (the header filter and its path) and of rtl/csum.sv (the three checksum accumulators). The battery for hdr.sv: hdr_filter against the specification on four configurations (frames back to back; and with gaps and idle cycles), and hdr_path from the PHY wires with the per-cause counters; for csum.sv: all three accumulators against the model. Usage: mut_ch09.py"""
import concurrent.futures as cf, os, random, re, shutil, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, hw, ip_gold as g, mac_gold as m
CFGS = [g.DEFAULT_CFG | {"ip_en": 0, "plo": 0, "phi": 65535}, g.DEFAULT_CFG, {"ip_en": 1, "ip": g.ip4(10, 1, 255, 255), "vid_en": 1, "vid": 0xABC, "plo": 1234, "phi": 1234}, g.DEFAULT_CFG | {"ip_en": 0, "plo": 0, "phi": 65535, "vid_en": 1, "vid": 0}]
W = {k: (6 if k.startswith("good") or k in ("no_csum", "odd_len") else 2) for k in g.KINDS}; W.update({"trailer": 4, "truncated": 6, "bits": 3, "carry_heavy": 4, "csum_zero": 4})
H = "rtl/hdr.sv"; C = "rtl/csum.sv"
HM = [
 ("type: 0x0800 is recognised by its high byte only", "assign d_ip = h08 && lo00;", "assign d_ip = h08;"),
 ("type: 0x88A8 is recognised with a low byte of 0x00", "(h88 && loA8)", "(h88 && lo00)"),
 ("type: 0x8100 is recognised with a low byte of 0xA8", "(h81 && lo00)", "(h81 && loA8)"),
 ("vlan: three tags are accepted", "if (d_vl && ntags < 2'd2)", "if (d_vl && ntags < 2'd3)"),
 ("vlan: only one tag is accepted", "if (d_vl && ntags < 2'd2)", "if (d_vl && ntags < 2'd1)"),
 ("vlan: the id is taken from the inner tag", "if (st == S_VLAN && ntags == 2'd1 && pos == 4'd0) vid_n[11:8]", "if (st == S_VLAN && ntags == 2'd2 && pos == 4'd0) vid_n[11:8]"),
 ("vlan: the id keeps the priority bits' neighbour (bits 7:4 of the high byte)", "vid_n[11:8] = s_data[3:0];", "vid_n[11:8] = s_data[7:4];"),
 ("type: the first type's flags are taken one byte early", "if ((st == S_ETH && pos == 4'd12) || (st == S_VLAN && pos == 4'd2)) begin h08_n", "if ((st == S_ETH && pos == 4'd11) || (st == S_VLAN && pos == 4'd2)) begin h08_n"),
 ("type: the second type's flags are taken one byte late", "if ((st == S_ETH && pos == 4'd12) || (st == S_VLAN && pos == 4'd2)) begin h08_n", "if ((st == S_ETH && pos == 4'd12) || (st == S_VLAN && pos == 4'd3)) begin h08_n"),
 ("type: the first type's low byte is looked for one byte early", "tpos_n = (st == S_ETH && pos == 4'd12) || (st == S_VLAN && pos == 4'd2);", "tpos_n = (st == S_ETH && pos == 4'd11) || (st == S_VLAN && pos == 4'd2);"),
 ("type: the second type's low byte is looked for one byte late", "tpos_n = (st == S_ETH && pos == 4'd12) || (st == S_VLAN && pos == 4'd2);", "tpos_n = (st == S_ETH && pos == 4'd12) || (st == S_VLAN && pos == 4'd3);"),
 ("vlan: the tag count is not incremented", "ntags_n = ntags + 2'd1; end", "ntags_n = ntags; end"),
 ("ip: version 4 or 5 is accepted", "(vi[7:4] == 4'd4)", "(vi[7:5] == 3'd2)"),
 ("ip: IHL 4 is accepted", "(vi[3:0] >= 4'd5)", "(vi[3:0] >= 4'd4)"),
 ("ip: the header length ignores the options (IHL - 1 off by one)", "ihm_n = (s_data[3:0] < 4'd5) ? 4'd4 : s_data[3:0] - 4'd1;", "ihm_n = (s_data[3:0] < 4'd5) ? 4'd4 : s_data[3:0];"),
 ("ip: the end of the header is one byte late", "(ipc[5:0] == {ihm, 2'b10})", "(ipc[5:0] == {ihm, 2'b11})"),
 ("ip: the total length may equal the header length minus one", "tge_n = ({tot[15:8], s_data} >= {10'd0, hl});", "tge_n = ({tot[15:8], s_data} + 16'd1 >= {10'd0, hl});"),
 ("ip: the total length must exceed the header length", "tge_n = ({tot[15:8], s_data} >= {10'd0, hl});", "tge_n = ({tot[15:8], s_data} > {10'd0, hl});"),
 ("ip: the payload length ignores the options", "trem_n = {tot[15:8], s_data} - {10'd0, hl};", "trem_n = {tot[15:8], s_data} - 16'd20;"),
 ("ip: the total length may exceed the frame by one", "f_tle <= (tot <= {4'd0, ipc});", "f_tle <= (tot <= {4'd0, ipc} + 16'd1);"),
 ("ip: the total length must be shorter than the frame", "f_tle <= (tot <= {4'd0, ipc});", "f_tle <= (tot < {4'd0, ipc});"),
 ("ip: a pending carry is not accepted", "(ipacc[15:0] == 16'hFFFE) : (ipacc[15:0] == 16'hFFFF)", "(ipacc[15:0] == 16'hFFFF) : (ipacc[15:0] == 16'hFFFF)"),
 ("ip: the header checksum is not checked", "&& ip_sum_ok;", ";"),
 ("ip: only the low bytes of the header words are summed", "else ipacc_n = addw(ipacc, {ih, s_data});", "else ipacc_n = addw(ipacc, {8'h00, s_data});"),
 ("ip: a fragment with the more-fragments flag is forwarded", "(frag[13:0] != 14'd0)", "(frag[12:0] != 13'd0)"),
 ("ip: the don't-fragment flag counts as a fragment", "(frag[13:0] != 14'd0)", "(frag[14:0] != 15'd0)"),
 ("ip: protocols other than 6 are taken for UDP", "if (proto == 8'd17) begin st_n = S_UDP;", "if (proto != 8'd6) begin st_n = S_UDP;"),
 ("udp: the length may be 7", "f_ul8 <= (ulen < 16'd8);", "f_ul8 <= (ulen < 16'd7);"),
 ("udp: the length must exceed 8", "f_ul8 <= (ulen < 16'd8);", "f_ul8 <= (ulen < 16'd9);"),
 ("udp: the length may exceed the IP payload by one", "f_ulgt <= (ulen > trem);", "f_ulgt <= (ulen > trem + 16'd1);"),
 ("udp: the length may not equal the IP payload", "f_ulgt <= (ulen > trem);", "f_ulgt <= (ulen >= trem);"),
 ("udp: a zero checksum is verified like any other", "f_ucsbad <= (ucs != 16'd0) && !u_sum_ok;", "f_ucsbad <= !u_sum_ok;"),
 ("udp: the checksum is not checked", "f_ucsbad <= (ucs != 16'd0) && !u_sum_ok;", "f_ucsbad <= 1'b0;"),
 ("udp: a pending carry is not accepted", "(uacc[15:0] == 16'hFFFE) : (uacc[15:0] == 16'hFFFF)", "(uacc[15:0] == 16'hFFFF) : (uacc[15:0] == 16'hFFFF)"),
 ("udp: the pseudo-header protocol is 16", "uacc <= 17'h00011;", "uacc <= 17'h00010;"),
 ("udp: the pseudo-header length is not added", "a_ul = su;", "a_ul = 1'b0;"),
 ("udp: the last address word of the pseudo-header is not added", "ipw_n = ipo[12] || ipo[14] || ipo[16] || ipo[18];", "ipw_n = ipo[12] || ipo[14] || ipo[16];"),
 ("udp: an odd last byte is not added", "a_lone = sl;", "a_lone = 1'b0;"),
 ("udp: the segment counter is loaded 5 short", "left_n = {ulen[15:8], s_data} - 16'd6;", "left_n = {ulen[15:8], s_data} - 16'd5;"),
 ("udp: the segment end is looked for one byte late", "uend_n = (left == 16'd2);", "uend_n = (left == 16'd3);"),
 ("udp: bytes after the segment are still summed", "if (uend) uin_n = 1'b0;", ""),
 ("udp: pairs of segment bytes take no high byte", "({16{a_pair}} & {uh, s_data})", "({16{a_pair}} & {8'h00, s_data})"),
 ("udp: the carry is lost", "addw = {1'b0, a[15:0]} + {16'd0, a[16]} + {1'b0, w};", "addw = {1'b0, a[15:0]} + {1'b0, w};"),
 ("filter: the destination address is always compared", "f_ipbad <= cfg_ip_en && (dip != cfg_ip);", "f_ipbad <= (dip != cfg_ip);"),
 ("filter: the destination address is never compared", "f_ipbad <= cfg_ip_en && (dip != cfg_ip);", "f_ipbad <= 1'b0;"),
 ("filter: the lowest port is excluded", "(dport < cfg_plo) || (dport > cfg_phi)", "(dport <= cfg_plo) || (dport > cfg_phi)"),
 ("filter: the highest port is excluded", "(dport < cfg_plo) || (dport > cfg_phi)", "(dport < cfg_plo) || (dport >= cfg_phi)"),
 ("filter: an untagged frame passes the VLAN rule", "(ntags_v == 2'd0 || vid != cfg_vid)", "(vid != cfg_vid)"),
 ("filter: the VLAN rule is never applied", "f_vidbad <= cfg_vid_en && (ntags_v == 2'd0 || vid != cfg_vid);", "f_vidbad <= 1'b0;"),
 ("verdict: the MAC's bad flag is ignored", "if (f_macbad) cause_n = 3'd1;\n        else if (f_trunc)", "if (1'b0) cause_n = 3'd1;\n        else if (f_trunc)"),
 ("verdict: a frame ending inside the IP header is not truncated", "f_trunc <= (st_v == S_ETH || st_v == S_VLAN || st_v == S_IP);", "f_trunc <= (st_v == S_ETH || st_v == S_VLAN);"),
 ("verdict: a frame ending inside a VLAN tag is not truncated", "f_trunc <= (st_v == S_ETH || st_v == S_VLAN || st_v == S_IP);", "f_trunc <= (st_v == S_ETH || st_v == S_IP);"),
 ("meta: the source address field carries the destination", "m_sip <= v_sip;", "m_sip <= v_dip;"),
 ("meta: the tag count is taken before the last byte", "ntags_v <= ntags_n;", "ntags_v <= ntags;"),
 ("state: the fields are not cleared at the start of a frame", "if (rst || (s_valid && fresh)) begin vid <= '0;", "if (rst) begin vid <= '0;"),
 ("state: the control state is not restarted at the end of a frame", "if (rst || (s_valid && s_last)) begin st <= S_ETH;", "if (rst) begin st <= S_ETH;"),
 ("counters: every byte of a frame is counted, not every frame", "inc[i] <= !rst && o2_v && o2_l && (cause_n == 3'(i));", "inc[i] <= !rst && o2_v && (cause_n == 3'(i));"),
]
CM = [
 ("e2e: the carry is not folded back", "assign t = {1'b0, s[15:0]} + {16'd0, s[16]};", "assign t = {1'b0, s[15:0]};"),
 ("e2e: a lone last byte is the low half of a word", "assign f = {1'b0, acc} + {1'b0, odd ? {hold, 8'h00} : 16'd0};", "assign f = {1'b0, acc} + {1'b0, odd ? {8'h00, hold} : 16'd0};"),
 ("e2e: the sum is not cleared at the start of a message", "if (start) begin acc <= 16'd0; hold <= d; odd <= 1'b1; end\n            else if (odd) begin acc <= t[15:0];", "if (start) begin hold <= d; odd <= 1'b1; end\n            else if (odd) begin acc <= t[15:0];"),
 ("def: the deferred carry is dropped", "acc <= {1'b0, acc[15:0]} + {16'd0, acc[16]} + {1'b0, hold, d};", "acc <= {1'b0, acc[15:0]} + {1'b0, hold, d};"),
 ("def: the final fold is skipped", "assign sum = f1[15:0];", "assign sum = a1[15:0];"),
 ("lane: the odd bytes go into the even lane", "else if (odd) begin al <= al + {12'd0, d}; odd <= 1'b0; end", "else if (odd) begin ah <= ah + {12'd0, d}; odd <= 1'b0; end"),
 ("lane: the high part of the combined sum is not folded in", "assign x = {2'b0, tt[15:0]} + {5'd0, tt[28:16]};", "assign x = {2'b0, tt[15:0]};"),
 ("lane: the lanes are combined the wrong way round", "assign tt = {1'b0, ah, 8'd0} + {9'd0, al};", "assign tt = {1'b0, al, 8'd0} + {9'd0, ah};"),
]
def sim(root, files, top, defines): return hw.sim_icarus(files, top, root=root, defines=defines)[1]
def defs(cfg, n): return (f"NC={n}", f"CFG_IP_EN={cfg['ip_en']}", f"CFG_IP=32'h{cfg['ip']:08x}", f"CFG_VID_EN={cfg['vid_en']}", f"CFG_VID=12'd{cfg['vid']}", f"CFG_PLO=16'd{cfg['plo']}", f"CFG_PHI=16'd{cfg['phi']}")
def battery_hdr(root):
    for ci, cfg in enumerate(CFGS):
        for seed in range(2):
            fr = g.frames(40 * ci + seed, 130, cfg, W)
            for style, (gap, bub) in (("b2b", ((0, 0), 0)), ("gap", ((0, 6), 12))):
                n = g.write_stimulus(os.path.join(root, "out", "hdr_stim.hex"), fr, seed, gap, bub); o = sim(root, ["rtl/hdr.sv", "tb/hdr_tb.sv"], "hdr_tb", defs(cfg, n))
                gf, gr = g.parse_results(o); ef, er = g.expected(fr, cfg)
                if gf != ef or gr != er: return f"hdr_filter, config {ci}, seed {seed}, {style}"
    for ci in (1, 2, 3):
        cfg = CFGS[ci]; fr = g.frames(500 + ci, 120, cfg, W); rng = random.Random(ci); it = [{"kind": rng.choices(["good", "badfcs", "er"], [88, 8, 4])[0], "body": b, "gap": rng.choice([12, 12, 13, 20])} for _, b, _ in fr]
        st = m.phy_stream(it, ci); m.write_stream(os.path.join(root, "out", "mac_stream.hex"), st); sp = m.spec_rx(st); exp = [p for p, bd in sp if not g.spec(p, bd, cfg)["cause"]]; cn = [0] * 8
        for p, bd in sp: cn[g.spec(p, bd, cfg)["cause"]] += 1
        o = sim(root, ["rtl/crc32_stream.sv", "rtl/mac.sv", "rtl/hdr.sv", "tb/hdr_path_tb.sv"], "hdr_path_tb", defs(cfg, len(st))); mm = re.search(r"CNT (.*)", o)
        if [p for p, _ in m.parse_frames(o)] != exp: return f"hdr_path, config {ci}: frames delivered"
        if not mm or [int(x) for x in mm.group(1).split()] != cn: return f"hdr_path, config {ci}: counters"
    return None
def battery_csum(root):
    msgs = g.csum_messages(2); n = g.write_csum_stimulus(os.path.join(root, "out", "csum_stim.hex"), msgs, 2); exp = [g.csum(x) for x in msgs]
    for var in ("csum_e2e", "csum_def", "csum_lane"):
        got = [int(x, 16) for x in re.findall(r"SUM ([0-9a-f]+)", sim(root, ["rtl/csum.sv", "tb/csum_tb.sv"], "csum_tb", (f"NC={n}", f"CSUM={var}")))]
        if got != exp: return var
    return None
def one(job):
    path, battery, (label, old, new) = job; d = tempfile.mkdtemp(prefix="mut9_")
    for sub in ("rtl", "tb", "out", "model"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub), ignore=shutil.ignore_patterns("*.json", "*_synth.log", "*.hex"))
    p = os.path.join(d, path); s = open(p).read()
    if s.count(old) != 1: shutil.rmtree(d, ignore_errors=True); return label, f"BAD ANCHOR ({s.count(old)} occurrences)"
    open(p, "w").write(s.replace(old, new)); r = battery(d); shutil.rmtree(d, ignore_errors=True); return label, ("NOT CAUGHT" if r is None else "caught by: " + r)
if __name__ == "__main__":
    print("NOTE: this script deliberately breaks copies of the RTL. 'caught' lines are EXPECTED: they show the battery notices the mistake.")
    b1 = battery_hdr(flow.ROOT); b2 = battery_csum(flow.ROOT); print("unmutated designs pass the whole battery:", b1 is None and b2 is None, "" if b1 is None and b2 is None else f"{b1} {b2}")
    jobs = [(H, battery_hdr, x) for x in HM] + [(C, battery_csum, x) for x in CM]
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(one, jobs))
    caught = 0
    for label, st in res: print(f"  {label}: {st}"); caught += st.startswith("caught")
    print(f"mutants caught: {caught} of {len(jobs)}")
    sys.exit(0 if b1 is None and b2 is None and caught == len(jobs) else 1)
