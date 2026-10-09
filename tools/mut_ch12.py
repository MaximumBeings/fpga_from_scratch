#!/usr/bin/env python3
"""Chapter 12: test the tests. Mutants of rtl/tcp.sv. Most anchors occur twice (the first design, tcp_next, and the second, tcp_sel): each occurrence is a separate mutant. The battery: the single-connection engine and the three tables against the model on directed lives and random events (two seeds), the window probes on the engine and the 4-stage table, and the hot path against the model. Usage: mut_ch12.py"""
import concurrent.futures as cf, os, random, re, shutil, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, hw, tcp_gold as g
M = "rtl/tcp.sv"
MUT = [
 ("CLOSED: a RST is answered", "if (!s_rst) begin\n                        tx_v = 1'b1;\n                        if (s_ack)", "if (1'b1) begin\n                        tx_v = 1'b1;\n                        if (s_ack)"),
 ("CLOSED: the reset for an ACK segment takes seq instead of ack", "if (s_ack) begin tx_f = RST; tx_seq = ack; end else", "if (s_ack) begin tx_f = RST; tx_seq = seq; end else"),
 ("CLOSED: the reset's ACK ignores the segment length", "tx_ack = seq + {15'd0, segl}; end", "tx_ack = seq; end"),
 ("CLOSED: the reset's ACK ignores the segment length (second design)", "tx_ack = seq_pseg; end", "tx_ack = seq_p1; end"),
 ("LISTEN: a SYN with ACK is accepted", "else if (s_ack) begin tx_v = 1'b1; tx_f = RST; tx_seq = ack; end\n                    else if (s_syn)", "else if (1'b0) begin tx_v = 1'b1; tx_f = RST; tx_seq = ack; end\n                    else if (s_syn)"),
 ("LISTEN: the SYN-ACK acknowledges seq, not seq + 1", "tx_f = SYN | ACK; tx_seq = nxt; tx_ack = seq + 32'd1; end", "tx_f = SYN | ACK; tx_seq = nxt; tx_ack = seq; end"),
 ("LISTEN: RCV.NXT is seq, not seq + 1", "n_rcv = seq + 32'd1; n_una = nxt;", "n_rcv = seq; n_una = nxt;"),
 ("LISTEN: SND.NXT does not advance past the SYN", "n_una = nxt; n_nxt = nxt + 32'd1; n_st = SYN_RCVD;", "n_una = nxt; n_nxt = nxt; n_st = SYN_RCVD;"),
 ("LISTEN: a RST is answered", "if (s_rst) begin end\n                    else if (s_ack)", "if (1'b0) begin end\n                    else if (s_ack)"),
 ("SYN_SENT: any ACK is accepted", "if (s_ack && !ack_in) begin if (!s_rst)", "if (1'b0) begin if (!s_rst)"),
 ("SYN_SENT: a bad ACK with RST is answered", "if (s_ack && !ack_in) begin if (!s_rst) begin tx_v", "if (s_ack && !ack_in) begin if (1'b1) begin tx_v"),
 ("SYN_SENT: a RST without ACK closes", "else if (s_rst) begin if (s_ack) n_st = CLOSED; end", "else if (s_rst) begin n_st = CLOSED; end"),
 ("SYN_SENT: SYN + ACK does not reach ESTABLISHED", "n_una = ack; n_st = ESTAB; tx_v", "n_una = ack; n_st = SYN_RCVD; tx_v"),
 ("SYN_SENT: SND.UNA is not updated by the ACK", "if (s_ack) begin n_una = ack; n_st = ESTAB;", "if (s_ack) begin n_st = ESTAB;"),
 ("SYN_SENT: simultaneous open sends no SYN-ACK", "else begin n_st = SYN_RCVD; n_pas = 1'b0; tx_v = 1'b1;", "else begin n_st = SYN_RCVD; n_pas = 1'b0; tx_v = 1'b0;"),
 ("SYN_SENT: simultaneous open is marked passive", "else begin n_st = SYN_RCVD; n_pas = 1'b0;", "else begin n_st = SYN_RCVD; n_pas = 1'b1;"),
 ("sync: the acceptability test ignores the window for empty segments", "((wnd == 16'd0) ? (seq == rcv) : (d_seq < {16'd0, wnd}))", "((wnd == 16'd0) ? (seq == rcv) : 1'b1)"),
 ("sync: the zero-window rule accepts any empty segment", "((wnd == 16'd0) ? (seq == rcv) : (d_seq < {16'd0, wnd}))", "((wnd == 16'd0) ? 1'b1 : (d_seq < {16'd0, wnd}))"),
 ("sync: the acceptability test ignores the segment's last byte", "((d_seq < {16'd0, wnd}) || (d_end < {16'd0, wnd}))", "(d_seq < {16'd0, wnd})"),
 ("sync: the acceptability test ignores the segment's first byte", "((d_seq < {16'd0, wnd}) || (d_end < {16'd0, wnd}))", "(d_end < {16'd0, wnd})"),
 ("sync: a window of one byte beyond", "(d_seq < {16'd0, wnd})", "(d_seq <= {16'd0, wnd})"),
 ("sync: the last byte is one beyond", "seq + {15'd0, segl} - 32'd1 - rcv", "seq + {15'd0, segl} - rcv"),
 ("sync: an unacceptable RST is answered", "if (!acc_ok) begin if (!s_rst) begin", "if (!acc_ok) begin if (1'b1) begin"),
 ("sync: an unacceptable segment is not answered", "if (!acc_ok) begin if (!s_rst) begin tx_v = 1'b1;", "if (!acc_ok) begin if (!s_rst) begin tx_v = 1'b0;"),
 ("sync: a RST in the window anywhere resets", "if (seq == rcv) n_st = (st == SYN_RCVD && pas) ? LISTEN : CLOSED;", "if (1'b1) n_st = (st == SYN_RCVD && pas) ? LISTEN : CLOSED;"),
 ("sync: a RST at RCV.NXT does not reset (second design)", "if (seq_eq) n_st = (st == SYN_RCVD && pas) ? LISTEN : CLOSED;", "if (1'b0) n_st = (st == SYN_RCVD && pas) ? LISTEN : CLOSED;"),
 ("sync: a RST in SYN_RCVD goes to CLOSED even if passive", "n_st = (st == SYN_RCVD && pas) ? LISTEN : CLOSED;", "n_st = CLOSED;"),
 ("sync: a SYN in the window is not challenged", "else if (s_syn) begin tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = rcv; end\n                    else if (s_ack) begin\n                        if (st == SYN_RCVD)", "else if (1'b0) begin tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = rcv; end\n                    else if (s_ack) begin\n                        if (st == SYN_RCVD)"),
 ("sync: SYN_RCVD accepts ACK = SND.UNA", "if (ack_in) begin st2 = ESTAB;", "if (ack_in || ack == una) begin st2 = ESTAB;"),
 ("sync: SYN_RCVD does not answer a bad ACK with a RST", "else begin tx_v = 1'b1; tx_f = RST; tx_seq = ack; stop = 1'b1; end", "else begin tx_v = 1'b0; tx_f = RST; tx_seq = ack; stop = 1'b1; end"),
 ("sync: an ACK for data not yet sent is accepted", "if (!ack_old && du > dn) begin tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = rcv; stop = 1'b1; end", "if (1'b0) begin tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = rcv; stop = 1'b1; end"),
 ("sync: an old ACK moves SND.UNA back", "else if (!ack_old && du != 32'd0) una2 = ack;", "else if (du != 32'd0) una2 = ack;"),
 ("sync: FIN_WAIT_1 does not move on when its FIN is acknowledged", "if (st2 == FW1 && acked) st2 = FW2;", "if (st2 == FW1 && 1'b0) st2 = FW2;"),
 ("sync: CLOSING does not move on", "else if (st2 == CLOSING && acked) st2 = TIME_WAIT;", "else if (st2 == CLOSING && 1'b0) st2 = TIME_WAIT;"),
 ("sync: LAST_ACK does not close", "else if (st2 == LAST_ACK && acked) begin st2 = CLOSED; stop = 1'b1; end", "else if (st2 == LAST_ACK && 1'b0) begin st2 = CLOSED; stop = 1'b1; end"),
 ("sync: SND.UNA is not stored", "n_una = una2;", "n_una = una;"),
 ("data: out-of-order data is delivered", "if (seq == rcv) begin nn = (ln < wnd) ? ln : wnd;", "if (1'b1) begin nn = (ln < wnd) ? ln : wnd;"),
 ("data: the delivered length is not limited by the window", "nn = (ln < wnd) ? ln : wnd;", "nn = ln;"),
 ("data: the delivery is limited to ln < wnd (second design)", "dlv = ln_le ? ln : wnd;", "dlv = ln;"),
 ("data: RCV.NXT does not advance by the data (second design)", "rcv2 = ln_le ? rcv_pln : rcv_pwnd; fin_ok = ln_le;", "rcv2 = rcv; fin_ok = ln_le;"),
 ("data: truncated data still lets the FIN through", "fin_ok = (nn == ln); end else fin_ok = 1'b0;", "fin_ok = 1'b1; end else fin_ok = 1'b0;"),
 ("data: the FIN is accepted out of order", "end else fin_ok = (seq == rcv);", "end else fin_ok = 1'b1;"),
 ("data: a FIN behind a gap is accepted", "fin_ok = (nn == ln); end else fin_ok = 1'b0;", "fin_ok = (nn == ln); end else fin_ok = 1'b1;"),
 ("data: the ACK for data acknowledges the old RCV.NXT", "n_rcv = rcv2; tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = rcv2;\n                                    end else fin_ok", "n_rcv = rcv2; tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = rcv;\n                                    end else fin_ok"),
 ("data: no ACK for data", "n_rcv = rcv2; tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = rcv2;\n                                    end else fin_ok", "n_rcv = rcv2; tx_v = 1'b0; tx_f = ACK; tx_seq = nxt; tx_ack = rcv2;\n                                    end else fin_ok"),
 ("fin: the FIN does not advance RCV.NXT", "rcv2 = rcv2 + 32'd1; n_rcv = rcv2;", "rcv2 = rcv2; n_rcv = rcv2;"),
 ("fin: ESTABLISHED + FIN goes to CLOSING", "n_st = (st2 == ESTAB) ? CLOSE_WAIT : ((st2 == FW2) ? TIME_WAIT : CLOSING);", "n_st = (st2 == ESTAB) ? CLOSING : ((st2 == FW2) ? TIME_WAIT : CLOSING);"),
 ("fin: FIN_WAIT_2 + FIN goes to CLOSING", "n_st = (st2 == ESTAB) ? CLOSE_WAIT : ((st2 == FW2) ? TIME_WAIT : CLOSING);", "n_st = (st2 == ESTAB) ? CLOSE_WAIT : ((st2 == FW2) ? CLOSING : CLOSING);"),
 ("fin: FIN_WAIT_1 + FIN goes to TIME_WAIT", "n_st = (st2 == ESTAB) ? CLOSE_WAIT : ((st2 == FW2) ? TIME_WAIT : CLOSING);", "n_st = (st2 == ESTAB) ? CLOSE_WAIT : TIME_WAIT;"),
 ("fin: a retransmitted FIN is not acknowledged", "end else if (s_fin) begin tx_v = 1'b1; tx_f = ACK; tx_seq = nxt; tx_ack = rcv; end\n                            end", "end else if (s_fin) begin tx_v = 1'b0; tx_f = ACK; tx_seq = nxt; tx_ack = rcv; end\n                            end"),
 ("app: OPEN_PASSIVE works in any state", "3'd0: if (st == CLOSED) begin", "3'd0: if (1'b1) begin"),
 ("app: OPEN_ACTIVE sends no SYN", "n_nxt = iss + 32'd1; tx_v = 1'b1; tx_f = SYN; tx_seq = iss; end", "n_nxt = iss + 32'd1; tx_v = 1'b0; tx_f = SYN; tx_seq = iss; end"),
 ("app: OPEN_ACTIVE does not advance SND.NXT", "n_nxt = iss + 32'd1; tx_v = 1'b1; tx_f = SYN;", "n_nxt = iss; tx_v = 1'b1; tx_f = SYN;"),
 ("app: OPEN_ACTIVE (second design) does not advance SND.NXT", "n_nxt = iss_p1; tx_v = 1'b1; tx_f = SYN;", "n_nxt = iss; tx_v = 1'b1; tx_f = SYN;"),
 ("app: OPEN_ACTIVE is refused in LISTEN", "3'd1: if (st == CLOSED || st == LISTEN) begin", "3'd1: if (st == CLOSED) begin"),
 ("app: CLOSE in CLOSE_WAIT goes to FIN_WAIT_1", "n_st = (st == CLOSE_WAIT) ? LAST_ACK : FW1;", "n_st = FW1;"),
 ("app: CLOSE in ESTABLISHED does not send the FIN", "tx_v = 1'b1; tx_f = FIN | ACK; tx_seq = nxt; tx_ack = rcv;", "tx_v = 1'b0; tx_f = FIN | ACK; tx_seq = nxt; tx_ack = rcv;"),
 ("app: the FIN does not advance SND.NXT", "n_nxt = nxt + 32'd1; n_st = (st == CLOSE_WAIT)", "n_nxt = nxt; n_st = (st == CLOSE_WAIT)"),
 ("app: CLOSE in SYN_SENT does not close", "if (st == LISTEN || st == SYN_SENT) n_st = CLOSED;", "if (st == LISTEN) n_st = CLOSED;"),
 ("app: ABORT sends no RST", "tx_v = 1'b1; tx_f = RST; tx_seq = nxt; end\n                n_st = CLOSED;", "tx_v = 1'b0; tx_f = RST; tx_seq = nxt; end\n                n_st = CLOSED;"),
 ("app: ABORT in LISTEN sends a RST", "if (st == SYN_RCVD || st == ESTAB || st == FW1 || st == FW2 || st == CLOSE_WAIT) begin tx_v = 1'b1; tx_f = RST;", "if (st == LISTEN || st == SYN_RCVD || st == ESTAB || st == FW1 || st == FW2 || st == CLOSE_WAIT) begin tx_v = 1'b1; tx_f = RST;"),
 ("app: the timeout closes any state", "3'd4: if (st == TIME_WAIT) n_st = CLOSED;", "3'd4: n_st = CLOSED;"),
 ("pre: the window compares the segment's last byte with the wrong base", "seq + {15'd0, segl} - 32'd1 - rcv", "seq + {15'd0, segl} - 32'd1 - nxt"),
 ("pre: the acceptability of an empty segment uses the last-byte difference", "E[5] ? (E[6] ? E[0] : (d_seq < {16'd0, wnd}))", "E[5] ? (E[6] ? E[0] : (d_end < {16'd0, wnd}))"),
 ("pre: the zero-window rule is dropped", "(E[6] ? 1'b0 : ((d_seq", "(E[6] ? 1'b1 : ((d_seq"),
 ("pre: ack_in allows ack = una", "ack_in = (du != 32'd0) && (du <= dn);\n        acc_ok = E[5]", "ack_in = (du <= dn);\n        acc_ok = E[5]"),
 ("pre: ack_in allows ack = nxt + 1", "ack_in = (du != 32'd0) && (du <= dn);\n        acc_ok = E[5]", "ack_in = (du != 32'd0) && (du <= dn + 32'd1);\n        acc_ok = E[5]"),
 ("pre: ack_fut is its own negation", "(!du[31] && du > dn), du[31]", "(du > dn), du[31]"),
 ("pre: seq + 1 computed as seq", "seq + 32'd1};\n    end\nendmodule\nmodule tcp_pre_b", "seq};\n    end\nendmodule\nmodule tcp_pre_b"),
 ("pre: rcv + len + 1 computed as rcv + len", "rcv + {16'd0, ln} + 32'd1, rcv + {16'd0, ln}, rcv + 32'd1, seq + {15'd0, segl}", "rcv + {16'd0, ln}, rcv + {16'd0, ln}, rcv + 32'd1, seq + {15'd0, segl}"),
 ("pre: rcv + wnd computed as rcv + len", "rcv + {16'd0, wnd}, rcv + {16'd0, ln} + 32'd1", "rcv + {16'd0, ln}, rcv + {16'd0, ln} + 32'd1"),
 ("pre: the segment length counts no FIN", "segl = {1'b0, ln} + {16'd0, f[0]} + {16'd0, f[2]};\n        D", "segl = {1'b0, ln} + {16'd0, f[0]};\n        D"),
 ("pre: the segment length counts no SYN", "segl = {1'b0, ln} + {16'd0, f[0]} + {16'd0, f[2]};\n        D", "segl = {1'b0, ln} + {16'd0, f[2]};\n        D"),
 ("tab: the bypass is not used", "assign sv = fwd_r ? fwd_d : mem_q;", "assign sv = mem_q;"),
 ("tab: the bypass is used for any connection", "fwd_r <= take && v1 && (ev_cid == cid1);", "fwd_r <= take && v1;"),
 ("tab: the write goes to the wrong connection", "else if (v1) mem[cid1] <= nvec;", "else if (v1) mem[ev_cid] <= nvec;"),
 ("tab: the RAM is not cleared after reset", "if (initing) mem[ic[CIDW-1:0]] <= '0; else if (v1) mem[cid1] <= nvec;", "if (initing) ; else if (v1) mem[cid1] <= nvec;"),
 ("tab2: no wait for an event of the same connection in stage 1", "assign ev_ready = !initing && !(v1 && cid1 == ev_cid) && !(vb", "assign ev_ready = !initing && !(vb"),
 ("tab2: no wait for an event of the same connection in stage 2", "&& !(v2 && cid2 == ev_cid);", ";"),
 ("tab2: no wait for the middle stage (4 stages)", "&& !(vb && cidb == ev_cid && SPLIT != 0)", ""),
 ("tab2: the write goes to stage 1's connection", "else if (v2) mem[cid2] <= nvec;", "else if (v2) mem[cid1] <= nvec;"),
 ("tab2: stage b keeps the old state", "svb <= mem_q;", "svb <= svb;"),
 ("fast: a window of one less", "(ln <= wnd) && (du <= dn);", "(ln < wnd) && (du <= dn);"),
 ("fast: an ACK beyond SND.NXT is taken", "(ln <= wnd) && (du <= dn);", "(ln <= wnd);"),
 ("fast: other flags are taken", "(f == 4'd2) && (seq == rcv)", "(f[1]) && (seq == rcv)"),
 ("fast: other states are taken", "(st == 4'd4) && (f == 4'd2)", "(st != 4'd0) && (f == 4'd2)"),
 ("fast: any sequence number is taken", "(seq == rcv) && (ln <= wnd)", "(ln <= wnd)"),
 ("fast: RCV.NXT advances by one too many", "n_rcv = rcv + {16'd0, ln};", "n_rcv = rcv + {16'd0, ln} + 32'd1;"),
 ("fast: SND.UNA is not advanced", "n_una = ack; n_rcv", "n_una = una; n_rcv"),
 ("fast: an ACK is sent for an empty segment", "tx_v = (ln != 16'd0);", "tx_v = 1'b1;"),
]
def battery(root):
    def run(evs, tab, cidw=2, split=0, idle=15, seed=1):
        n = g.write_events(os.path.join(root, "out", "tcp_stim.hex"), evs, seed, idle)
        o = hw.sim_icarus(["rtl/tcp.sv", "tb/tcp_tb.sv"], "tcp_tb", root=root, defines=(f"NC={n}", f"TAB={tab}", f"CIDW={cidw}", f"SPLIT={split}", "MAXCYC=400000"))[1]
        try: return [tuple(int(x) for x in l.split()[1:]) for l in o.splitlines() if l.startswith("R ")]
        except ValueError: return [("x",)]                                         # an x or z in the output is never equal to a result
    for seed in (1, 2):
        evs = g.directed_events(0) + g.gen_events(seed, 1500, cids=1)
        if run(evs, 0, seed=seed) != g.expected_results(evs): return f"tcp_conn, seed {seed}"
        evs = g.directed_events(0) + g.gen_events(seed, 1500, cids=4); exp = g.expected_results(evs)
        for tab, split in ((1, 0), (2, 0), (2, 1)):
            if run(evs, tab, 2, split, idle=seed - 1, seed=seed) != exp: return f"table {tab}/{split}, seed {seed}"
    for wnd, ln in ((1, 5), (5, 1), (0, 0)):
        offs = list(range(-6, wnd + 7)); evs = []
        for off in offs: evs += [dict(e=g.E_OPEN_A, iss=1000), dict(e=g.E_SEG, f=g.SYN | g.ACK, seq=0xFFFFFFEF, ack=1001, wnd=wnd), dict(e=g.E_CLOSE), dict(e=g.E_SEG, f=g.ACK, seq=(0xFFFFFFF0 + off) & g.M, ack=1002, ln=ln, wnd=wnd), dict(e=g.E_ABORT)]
        exp = g.expected_results(evs)
        for tab, split in ((0, 0), (2, 1)):
            if run(evs, tab, 2, split, idle=0) != exp: return f"window probes {wnd}/{ln}, {'engine' if tab == 0 else 'table'}"
    cases = []
    for seed in range(2):
        tcb = {}
        for v in g.realistic_events(seed, 4, 60) + g.gen_events(seed, 1500, cids=4):
            t = tcb.setdefault(v.get("cid", 0), g.TCB())
            if v["e"] == g.E_SEG: cases.append((t.snapshot(), v))
            t.event(v["e"], v.get("f", 0), v.get("seq", 0), v.get("ack", 0), v.get("ln", 0), v.get("wnd", 0), v.get("iss", 0))
    cases += g.fast_random_cases(6, 1500)
    with open(os.path.join(root, "out", "tcp_fast_stim.hex"), "w") as fh:
        for (st, pas, una, nxt, rcv), v in cases: fh.write("%x%08x%08x%08x%08x%08x%x%04x%04x\n" % (st, una, nxt, rcv, v.get("seq", 0) & g.M, v.get("ack", 0) & g.M, v.get("f", 0), v.get("ln", 0), v.get("wnd", 0)))
    o = hw.sim_icarus(["rtl/tcp.sv", "tb/tcp_fast_tb.sv"], "tcp_fast_tb", root=root, defines=(f"NC={len(cases)}",))[1]; hs = [tuple(int(x) if x.lstrip("-").isdigit() else -1 for x in l.split()[1:]) for l in o.splitlines() if l.startswith("H ")]
    if len(hs) != len(cases): return "hot path: no output"
    for (snap, v), h in zip(cases, hs):
        t = g.TCB(); t.state, t.passive, t.una, t.nxt, t.rcv = snap; mdl = g.fast_path(t, v.get("f", 0), v.get("seq", 0), v.get("ack", 0), v.get("ln", 0), v.get("wnd", 0))
        if (h[0] == 1) != mdl: return "hot path: decision"
        if h[0]:
            tx, d = t.event(v["e"], v.get("f", 0), v.get("seq", 0), v.get("ack", 0), v.get("ln", 0), v.get("wnd", 0), 0)
            if (h[1], h[2], h[3], h[4]) != (t.una, t.rcv, 1 if tx else 0, d): return "hot path: result"
    return None
def jobs():
    base = open(os.path.join(flow.ROOT, M)).read(); out = []
    for label, old, new in MUT:
        c = base.count(old)
        if c == 0: out.append((label, None, None, None)); continue
        for k in range(c): out.append((label + (f" [occurrence {k + 1} of {c}]" if c > 1 else ""), old, new, k))
    return out
def one(j):
    label, old, new, k = j
    if old is None: return label, "BAD ANCHOR (0 occurrences)"
    d = tempfile.mkdtemp(prefix="mut12_")
    for sub in ("rtl", "tb", "out", "model"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub), ignore=shutil.ignore_patterns("*.json", "*_synth.log", "*.hex"))
    p = os.path.join(d, M); s = open(p).read(); idx = -1
    for _ in range(k + 1): idx = s.index(old, idx + 1)
    open(p, "w").write(s[:idx] + new + s[idx + len(old):]); r = battery(d); shutil.rmtree(d, ignore_errors=True); return label, ("NOT CAUGHT" if r is None else "caught by: " + r)
if __name__ == "__main__":
    print("NOTE: this script deliberately breaks copies of the RTL. 'caught' lines are EXPECTED: they show the battery notices the mistake.")
    base = battery(flow.ROOT); print("unmutated design passes the whole battery:", base is None, "" if base is None else base)
    J = jobs()
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(one, J))
    caught = 0
    for label, st in res: print(f"  {label}: {st}"); caught += st.startswith("caught")
    print(f"mutants caught: {caught} of {len(J)}")
    sys.exit(0 if base is None and caught == len(J) else 1)
