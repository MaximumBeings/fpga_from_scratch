#!/usr/bin/env python3
"""Chapter 13: test the tests. Mutants of rtl/tx.sv. The battery: tx_conn on a closed-loop transfer with loss, on a small window updated by every ACK and on open-loop fuzz; tx_tab with the scanner on interleaved connections (closed loop and fuzz) replayed against the model; and the scanner's lateness bound on idle connections. Usage: mut_ch13.py"""
import concurrent.futures as cf, os, re, shutil, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, hw, tx_gold as g
M = "rtl/tx.sv"
MUT = [
 ("avail counts from SND.UNA", "avail = en - nxt;", "avail = en - una;"),
 ("the window limit ignores SND.NXT", "wl = una + {16'd0, wnd} - nxt;", "wl = una + {16'd0, wnd};"),
 ("a negative window limit is not clamped", "if (wl[31]) wl = 32'd0;", ""),
 ("the segment is MSS - 1 when data is plentiful", "n32 = (avail < 32'(MSS)) ? avail : 32'(MSS);", "n32 = (avail < 32'(MSS)) ? avail : 32'(MSS) - 32'd1;"),
 ("a retransmission is never flagged", "retx = ltf(nxt, mx);", "retx = 1'b0;"),
 ("SND.MAX always follows SND.NXT", "if (ltf(mx, newmax)) n_mx = newmax;", "n_mx = newmax;"),
 ("timing starts on a retransmission", "if (!timing_on && !retx) begin", "if (!timing_on) begin"),
 ("the timed sequence number is SND.NXT before sending", "n_rtt_seq = newmax;", "n_rtt_seq = nxt;"),
 ("the sample's start time is not recorded", "n_rtt_seq = newmax; n_rtt_t0 = now; end", "n_rtt_seq = newmax; end"),
 ("a send restarts a running timer", "if (!timer_on) begin n_timer_on = 1'b1; n_deadline = now + rto; end", "if (1'b1) begin n_timer_on = 1'b1; n_deadline = now + rto; end"),
 ("a send starts the timer at now", "n_timer_on = 1'b1; n_deadline = now + rto; end\n            end\n            2'd1", "n_timer_on = 1'b1; n_deadline = now; end\n            end\n            2'd1"),
 ("an ACK beyond SND.MAX is accepted", "if (ltf(una, a) && !ltf(mx, a)) begin", "if (ltf(una, a)) begin"),
 ("an ACK at SND.UNA or before is accepted as new", "if (ltf(una, a) && !ltf(mx, a)) begin", "if (!ltf(mx, a)) begin"),
 ("SND.NXT is not pulled forward by an ACK", "n_una = a; if (ltf(nxt, a)) n_nxt = a; n_wnd = w;", "n_una = a; n_wnd = w;"),
 ("the window is not updated by a new ACK", "n_wnd = w;\n                    do_sample", "\n                    do_sample"),
 ("a sample is taken from any ACK", "do_sample = timing_on && !ltf(a, rtt_seq);", "do_sample = timing_on;"),
 ("a sample is taken only when the ACK equals the timed number", "do_sample = timing_on && !ltf(a, rtt_seq);", "do_sample = timing_on && (a == rtt_seq);"),
 ("the first sample does not set 'have'", "n_srtt8 = s8; n_rv4 = v4; n_have = 1'b1;", "n_srtt8 = s8; n_rv4 = v4; n_have = 1'b0;"),
 ("the first SRTT is R x 4", "(r << 3);", "(r << 2);"),
 ("the first RTTVAR is R, not R / 2", "(r << 1);", "r;"),
 ("the error has the wrong sign", "err = r - sr;", "err = sr - r;"),
 ("SRTT adds |err|", "s8 = have ? srtt8 + err :", "s8 = have ? srtt8 + aerr :"),
 ("RTTVAR decays by 1/8", "v4 = have ? rv4 + aerr - (rv4 >> 2)", "v4 = have ? rv4 + aerr - (rv4 >> 3)"),
 ("the error's magnitude is the signed error", "aerr = err[31] ? (32'd0 - err) : err;", "aerr = err;"),
 ("the RTO has no lower clamp", "clampr = (x < RTO_MIN) ? 32'(RTO_MIN) : (x > RTO_MAX) ? 32'(RTO_MAX) : x;", "clampr = (x > RTO_MAX) ? 32'(RTO_MAX) : x;"),
 ("the RTO has no upper clamp", "clampr = (x < RTO_MIN) ? 32'(RTO_MIN) : (x > RTO_MAX) ? 32'(RTO_MAX) : x;", "clampr = (x < RTO_MIN) ? 32'(RTO_MIN) : x;"),
 ("the backed-off RTO persists after an ACK without a sample", "end else if (have) n_rto = clampr((srtt8 >> 3) + rv4);", "end"),
 ("the timer is not stopped when everything is acknowledged", "if (a == mx) n_timer_on = 1'b0; else n_deadline", "if (1'b0) n_timer_on = 1'b0; else n_deadline"),
 ("the timer is stopped when SND.NXT is reached", "if (a == mx) n_timer_on = 1'b0;", "if (a == nxt) n_timer_on = 1'b0;"),
 ("an ACK restarts the timer without the RTO", "n_deadline = now + ((do_sample)", "n_deadline = now + 32'd0 * ((do_sample)"),
 ("a duplicate ACK does not update the window", "else if (a == una) n_wnd = w;", "else if (1'b0) n_wnd = w;"),
 ("the timer fires one tick late", "default: if (timer_on && !ltf(now, deadline)) begin", "default: if (timer_on && ltf(deadline, now)) begin"),
 ("the backed-off RTO is not clamped", "if (rto2 > RTO_MAX) rto2 = 32'(RTO_MAX);", ""),
 ("a timeout does not back off", "n_rto = rto2; n_timing_on = 1'b0;", "n_rto = rto; n_timing_on = 1'b0;"),
 ("a timeout does not cancel the sample (Karn)", "n_rto = rto2; n_timing_on = 1'b0;", "n_rto = rto2;"),
 ("a timeout retransmits from SND.NXT", "tx_seq = una; tx_len = nretx[15:0]; tx_retx = 1'b1;", "tx_seq = nxt; tx_len = nretx[15:0]; tx_retx = 1'b1;"),
 ("a timeout does not go back", "tx_retx = 1'b1; n_nxt = una + nretx; end else n_nxt = una;", "tx_retx = 1'b1; end else n_nxt = una;"),
 ("a timeout restarts the timer with the old RTO", "n_deadline = now + rto2;", "n_deadline = now + rto;"),
 ("the retransmission is limited to MSS - 1", "nretx = (en - una < 32'(MSS)) ? (en - una) : 32'(MSS);", "nretx = (en - una < 32'(MSS)) ? (en - una) : 32'(MSS) - 32'd1;"),
 ("WRITE replaces the data instead of adding", "2'd0: n_en = en + a;", "2'd0: n_en = a;"),
 ("tab: no bypass", "assign sv = fwd_r ? fwd_d : mem_q;", "assign sv = mem_q;"),
 ("tab: the bypass is taken for any connection", "fwd_r <= go0 && v1 && (cid0 == cid1);", "fwd_r <= go0 && v1;"),
 ("tab: the scanner does not move on", "if (go0 && !ext) sp <= sp + 1'b1;", ""),
 ("tab: the scanner injects POLL, not TICK", "assign t0 = ext ? ev_type : 2'd3;", "assign t0 = ext ? ev_type : 2'd2;"),
 ("tab: the scanner is not used", "assign cid0 = ext ? ev_cid : sp;", "assign cid0 = ev_cid;"),
 ("tab: the write goes to the next connection", "else if (v1) mem[cid1] <= nvec;", "else if (v1) mem[cid0] <= nvec;"),
 ("tab: the RAM starts with RTO 0", "32'(RTO_INIT), 32'd0, 32'd0, 32'd0, 16'(WND0)", "32'd0, 32'd0, 32'd0, 32'd0, 16'(WND0)"),
 ("tab: the RAM starts with window 0", "32'd0, 32'd0, 32'd0, 16'(WND0), 3'b000}", "32'd0, 32'd0, 32'd0, 16'd0, 3'b000}"),
 ("tab: the scanner skips the connection just served", "if (go0 && !ext) sp <= sp + 1'b1;", "if (go0 && !ext) sp <= sp + 2'd2;"),
 ("conn: the RTO starts at 0", "rto <= 32'(RTO_INIT);", "rto <= 32'd0;"),
 ("conn: the window starts at 0", "wnd <= 16'(WND0);", "wnd <= 16'd0;"),
]
def battery(root):
    def sim(n, tab, cidw=2, **kw):
        d = (f"NC={n}", f"TAB={tab}", f"CIDW={cidw}", "MAXCYC=400000") + tuple(f"{k}={v}" for k, v in kw.items())
        o = hw.sim_icarus(["rtl/tx.sv", "tb/tx_tb.sv"], "tx_tb", root=root, defines=d)[1]
        try: return [tuple(int(x) for x in l.split()[1:]) for l in o.splitlines() if l.startswith("R ")]
        except ValueError: return [("x",)]
    def row(cid, typ, now, s, tx):
        una, nxt, mx, wnd, end, sr, rv, rto, dl, ton, tim, have = s.snapshot(); return (cid, typ, now, una, nxt, mx, wnd, end, sr, rv, rto, dl, ton, tim, have, 1 if tx else 0, tx[0] if tx else 0, tx[1] if tx else 0, tx[2] if tx else 0)
    def conn_exp(ev):
        s = g.Sender(mss=100); out = []
        for c, cid, e, a, w in ev: tx = s.event(e, c, a, w); out.append(row(0, 0, 0, s, tx))
        return out
    def replay(evs, got):
        snd = {}; ext = iter(evs); exp = []; late = []
        for r in got:
            if len(r) < 3: return None, None
            cid, typ, now = r[0], r[1], r[2]
            if typ == g.TICK: a = w = 0
            else:
                try: c, cc, e, a, w = next(ext)
                except StopIteration: return None, None
                if (cc, e, c) != (cid, typ, now): return None, None
            s = snd.setdefault(cid, g.Sender(mss=100)); dl = s.deadline; on = s.timer_on; tx = s.event(typ, now, a, w); exp.append(row(cid, typ, now, s, tx))
            if typ == g.TICK and tx and on: late.append((now - dl) & g.M)
        return exp, late
    traces = [("closed loop 5%", [(c, 0, e, a, w) for c, e, a, w in g.transfer(11, 4000, loss=0.05, mss=100)["events"]]), ("closed loop 20%", [(c, 0, e, a, w) for c, e, a, w in g.transfer(12, 2500, loss=0.2, mss=100)["events"]]),
              ("small window", [(c, 0, e, a, w) for c, e, a, w in g.transfer(13, 4000, loss=0.05, mss=100, wnd=400, wnd_var=True)["events"]]), ("fuzz", [(c, 0, e, a, w) for c, cid, e, a, w in g.fuzz_events(14, 2500)]), ("fuzz 2", [(c, 0, e, a, w) for c, cid, e, a, w in g.fuzz_events(15, 2500)])]
    for nm, ev in traces:
        n = g.write_stim(os.path.join(root, "out", "tx_stim.hex"), ev)
        if sim(n, 0) != conn_exp(ev): return f"tx_conn, {nm}"
    for nm, K, mk in (("closed loop", 4, lambda c: [(cy, c, e, a, w) for cy, e, a, w in g.transfer(20 + c, 2000, loss=0.05, k=4, c=c, mss=100)["events"] if e != g.TICK]), ("fuzz", 3, lambda c: [(cy, c, e, a, w) for cy, cid, e, a, w in g.fuzz_events(30 + c, 1200, k=3, c=c) if e != g.TICK])):
        evs = []
        for c in range(K): evs += mk(c)
        evs.sort(); n = g.write_stim(os.path.join(root, "out", "tx_stim.hex"), evs); got = sim(n, 1, 2); exp, late = replay(evs, got)
        if exp is None or exp != got: return f"tx_tab, {nm}"
    N = 4; evs = []
    for c in range(N): evs += [(2 * c, c, g.WRITE, 500, 0), (2 * c + 1, c, g.POLL, 0, 0)]
    n = g.write_stim(os.path.join(root, "out", "tx_stim.hex"), evs, 2 * N + 8 * 300 + 1500); got = sim(n, 1, 2); exp, late = replay(evs, got)
    if exp is None or exp != got: return "tx_tab, idle connections"
    if len(late) < 12 or max(late) > N - 1: return f"scanner lateness (timeouts {len(late)}, max {max(late) if late else None})"
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
    d = tempfile.mkdtemp(prefix="mut13_")
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
