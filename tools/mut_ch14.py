#!/usr/bin/env python3
"""Chapter 14: test the tests. Three families of mutants, one battery each.
  (1) the ORACLE: mutants of model/ref_stack.py (the reference receiver, the reference client, the channel). A wrong reference must make the interop battery fail, or the comparison proves nothing. Battery: interop.battery().
  (2) the DUT MODELS: mutants of model/tx_gold.py and model/tcp_gold.py. Battery: interop.battery() (bytes, order, completion, invariants, profile coverage, time budget). What it does NOT catch is the interesting part: the bugs the network never provokes.
  (3) the RTL, with only the interop traces: mutants of rtl/tx.sv and rtl/tcp.sv from Chapters 12 and 13, replayed against traces recorded in the pairings (and nothing else: no fuzz, no directed lives). How many of the earlier batteries' mutants does end-to-end evidence alone reach?"""
import concurrent.futures as cf, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, hw
RS = "model/ref_stack.py"; TXG = "model/tx_gold.py"; TCG = "model/tcp_gold.py"
PY = [
 (RS, "ref receiver: acknowledges one byte too many", "out.append((ACK, 0, self.nxt, 0, self.wnd))", "out.append((ACK, 0, (self.nxt + 1) & M, 0, self.wnd))"),
 (RS, "ref receiver: keeps no out-of-order data", "self.ooo[seq] = max(self.ooo.get(seq, 0), ln)", "pass"),
 (RS, "ref receiver: delivers the whole of an overlapping segment", "n = (end - self.nxt) & M; self.buf += stream((self.nxt - self.first) & M, n)", "n = l; self.buf += stream((sq - self.first) & M, n)"),
 (RS, "ref receiver: stores only segments that start at RCV.NXT", "if le(sq, self.nxt):", "if sq == self.nxt:"),
 (RS, "ref client: fast retransmit at the first duplicate ACK", "self.dup == 3", "self.dup == 1"),
 (RS, "ref client: no fast retransmit at all", "if self.fast and self.dup == 3 and self.state == \"EST\":", "if False:"),
 (RS, "ref client: no go-back-N after a timeout", "elif self.state == \"EST\": self.nxt = self.una; self.dup = 0; self._data(t, out)", "elif self.state == \"EST\": self.dup = 0"),
 (RS, "ref client: the SYN is never retransmitted", "if self.state == \"SYN_SENT\": out.append((SYN, self.iss, 0, 0, self.win))", "if self.state == \"SYN_SENT\": pass"),
 (RS, "ref client: the peer's FIN is not acknowledged", "self.rcv = (self.rcv + 1) & M; out.append((ACK, self.nxt, self.rcv, 0, self.win))\n                if self.state == \"FIN_WAIT_2\"", "self.rcv = (self.rcv + 1) & M\n                if self.state == \"FIN_WAIT_2\""),
 (RS, "ref client: the FIN's sequence number is one too high", "out.append((FIN | ACK, self.dend, self.rcv, 0, self.win)); self.nxt = (self.dend + 1) & M; self.state = \"FIN_WAIT_1\"", "out.append((FIN | ACK, (self.dend + 1) & M, self.rcv, 0, self.win)); self.nxt = (self.dend + 1) & M; self.state = \"FIN_WAIT_1\""),
 (RS, "ref client: ignores the window", "min(self.win, self.peer_wnd)", "10**9"),
 (RS, "ref client: the timeout is not reset by an ACK", "self.dup = 0; self.rto = self.rto0; self.timer", "self.dup = 0; self.timer"),
 (RS, "channel: never duplicates", "if self.rng.random() < self.dup: copies = 2", "if False: copies = 2"),
 (RS, "channel: never delays", "d += self.rng.randint(1, self.spread)", "d += 0"),
 (RS, "channel: loses nothing", "if self.rng.random() < self.loss: return", "if False: return"),
 (TXG, "sender: avail counts from SND.UNA", "avail = (self.end - self.nxt) & M; wl", "avail = (self.end - self.una) & M; wl"),
 (TXG, "sender: the window limit ignores SND.NXT", "wl = (self.una + self.wnd - self.nxt) & M; wl = 0", "wl = (self.una + self.wnd) & M; wl = 0"),
 (TXG, "sender: a retransmission is never flagged", "retx = lt(self.nxt, self.max);", "retx = 0;"),
 (TXG, "sender: SND.MAX always follows SND.NXT", "if lt(self.max, new): self.max = new", "self.max = new"),
 (TXG, "sender: timing starts on a retransmission", "if not self.timing_on and not retx:", "if not self.timing_on:"),
 (TXG, "sender: an ACK beyond SND.MAX is accepted", "if lt(self.una, a) and not lt(self.max, a):", "if lt(self.una, a):"),
 (TXG, "sender: an ACK at or below SND.UNA is accepted as new", "if lt(self.una, a) and not lt(self.max, a):", "if not lt(self.max, a):"),
 (TXG, "sender: SND.NXT is not pulled forward by an ACK", "if lt(self.nxt, a): self.nxt = a", "pass"),
 (TXG, "sender: a duplicate ACK does not update the window", "elif a == self.una: self.wnd = w & 0xFFFF", "elif a == self.una: pass"),
 (TXG, "sender: the timer is not stopped when everything is acknowledged", "if self.una == self.max: self.timer_on = 0", "if False: self.timer_on = 0"),
 (TXG, "sender: a new ACK does not restart the timer", "else: self.deadline = (now + self.rto) & M\n            elif a == self.una:", "else: pass\n            elif a == self.una:"),
 (TXG, "sender: a timeout does not back off", "self.rto = min((self.rto << 1) & M, self.rto_max); self.timing_on = 0", "self.timing_on = 0"),
 (TXG, "sender: a timeout does not cancel the sample", "self.timing_on = 0\n                n = min(self.mss", "n = min(self.mss"),
 (TXG, "sender: a timeout does not go back", "if n > 0: tx = (self.una, n, 1); self.nxt = (self.una + n) & M", "if n > 0: tx = (self.una, n, 1)"),
 (TXG, "sender: a sample is taken from any ACK", "if self.timing_on and not lt(a, self.rtt_seq):", "if self.timing_on:"),
 (TXG, "sender: the RTO has no lower clamp", "self.rto = min(max(rto, self.rto_min), self.rto_max)", "self.rto = min(rto, self.rto_max)"),
 (TXG, "sender: the first SRTT is R x 4", "self.srtt8 = (r << 3) & M; self.rv4", "self.srtt8 = (r << 2) & M; self.rv4"),
 (TXG, "sender: the RTO leaves out the variance", "rto = ((self.srtt8 >> 3) + max(1, self.rv4)) & M", "rto = ((self.srtt8 >> 3) + 1) & M"),
 (TXG, "sender: a timeout retransmits what was written, not what was outstanding (the bug this chapter found)", "n = min(self.mss, (self.max - self.una) & M)", "n = min(self.mss, (self.end - self.una) & M)"),
 (TXG, "sender: the timer fires one tick late", "if self.timer_on and not lt(now, self.deadline):", "if self.timer_on and lt(self.deadline, now):"),
 (TCG, "receiver: LISTEN sets RCV.NXT to seq, not seq + 1", "self.rcv = (seq + 1) & M; self.una = self.nxt", "self.rcv = seq & M; self.una = self.nxt"),
 (TCG, "receiver: SYN_RCVD takes any ACK as the third step", "if du != 0 and du <= dn: self.state = ESTAB", "if True: self.state = ESTAB"),
 (TCG, "receiver: out-of-order data is delivered", "if seq == self.rcv: n = min(ln, wnd)", "if True: n = min(ln, wnd)"),
 (TCG, "receiver: data beyond the window is delivered", "n = min(ln, wnd); dlv = n", "n = ln; dlv = n"),
 (TCG, "receiver: no ACK for data", "tx = self._ack_seg()                                                # new data or duplicate ACK", "tx = None"),
 (TCG, "receiver: a FIN does not advance RCV.NXT", "self.rcv = (self.rcv + 1) & M; tx = self._ack_seg()\n                    self.state = CLOSE_WAIT", "tx = self._ack_seg()\n                    self.state = CLOSE_WAIT"),
 (TCG, "receiver: LAST_ACK never closes", "elif st == LAST_ACK and acked: self.state = CLOSED; return None, 0", "elif st == LAST_ACK and acked: return None, 0"),
 (TCG, "receiver: CLOSE in CLOSE_WAIT goes to FIN_WAIT_1", "self.state = LAST_ACK if st == CLOSE_WAIT else FW1", "self.state = FW1"),
 (TCG, "receiver: the acceptability test accepts everything", "ok = False if wnd == 0 else (d < wnd) or (((seq + segl - 1 - self.rcv) & M) < wnd)", "ok = True"),
 (TCG, "receiver: an unacceptable segment is not acknowledged", "if not ok: return (None if s_rst else self._ack_seg()), 0", "if not ok: return None, 0"),
 (TCG, "receiver: an ACK for unsent data is not challenged", "if not old and du > dn: return self._ack_seg(), 0", "if False: return self._ack_seg(), 0"),
 (TCG, "receiver: a retransmitted FIN is not acknowledged again", "elif s_fin: tx = self._ack_seg()", "elif s_fin: tx = None"),
 (TCG, "receiver: the SYN-ACK acknowledges seq", "return (SYN | ACK, iss, self.rcv), 0", "return (SYN | ACK, iss, seq), 0"),
]
def py_one(j):
    f, label, old, new = j
    d = tempfile.mkdtemp(prefix="mut14_"); shutil.copytree(os.path.join(flow.ROOT, "model"), os.path.join(d, "model"), ignore=shutil.ignore_patterns("__pycache__"))
    p = os.path.join(d, f)
    s = open(p).read()
    if old not in s: shutil.rmtree(d, ignore_errors=True); return label, "BAD ANCHOR (0 occurrences)"
    i = s.index(old); open(p, "w").write(s[:i] + new + s[i + len(old):])
    try: r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, 'model'); import interop; print('RESULT', interop.battery())"], cwd=d, capture_output=True, text=True, timeout=300); out = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "RESULT crash: " + r.stderr.strip().splitlines()[-1][:80]
    except subprocess.TimeoutExpired: out = "RESULT hang (timeout)"
    res = out.replace("RESULT ", ""); extra = ""
    if res == "None":                                                    # what the hand-checked scenarios of the earlier chapter say about it: before this chapter's additions, and after
        def selftest(text):
            q = os.path.join(d, "model", "st_tmp.py"); open(q, "w").write(text)
            try: return subprocess.run([sys.executable, q], cwd=d, capture_output=True, text=True, timeout=300).returncode == 0
            except subprocess.TimeoutExpired: return False
        full = open(p).read(); i0 = full.index("    # ---- added in Chapter 14"); i1 = full.index("    # ---- end of the Chapter 14 additions"); before = selftest(full[:i0] + full[i1:]); after = selftest(full)
        extra = f" [hand-checked scenarios: before this chapter {'pass' if before else 'FAIL'}, after {'pass' if after else 'FAIL'}]"
    shutil.rmtree(d, ignore_errors=True)
    return label, ("NOT CAUGHT" + extra if res == "None" else "caught by: " + res)
# ---------------------------------------------------------------- family 3: the RTL, interop traces only
def rtl_battery(root, which):
    import interop as I, tx_gold as TX, tcp_gold as TC, ch12_run as c12, ch13_run as c13
    if which == "tx":
        for lab, fn in (("A", I.run_a), ("C", I.run_c)):
            for nm in ("loss 5%", "reorder 20%", "harsh: loss 15, reorder 30, dup 15", "off-path noise 10%"):
                r = fn(40, 2137, I.PROFILES[nm]); ev = [(t, 0, e, a, w) for t, e, a, w in r["events"]]; n = TX.write_stim(os.path.join(root, "out", "tx_stim.hex"), ev)
                d = (f"NC={n}", "TAB=0", "CIDW=2", "MAXCYC=400000"); o = hw.sim_icarus(["rtl/tx.sv", "tb/tx_tb.sv"], "tx_tb", root=root, defines=d)[1]
                try: got = [tuple(int(x) for x in l.split()[1:]) for l in o.splitlines() if l.startswith("R ")]
                except ValueError: return f"tx_conn, {lab}, {nm}"
                if got != c13.conn_expected(ev, mss=100): return f"tx_conn, {lab}, {nm}"
        return None
    logs = []
    for lab, fn in (("B", I.run_b), ("C", I.run_c)):
        for nm in ("loss 5%", "reorder 20%", "harsh: loss 15, reorder 30, dup 15", "off-path noise 10%"): logs.append((f"{lab}, {nm}", fn(40, 2137, I.PROFILES[nm])["evlog"]))
    def run(evs, tab, cidw, split, idle, seed):
        n = TC.write_events(os.path.join(root, "out", "tcp_stim.hex"), evs, seed, idle)
        o = hw.sim_icarus(["rtl/tcp.sv", "tb/tcp_tb.sv"], "tcp_tb", root=root, defines=(f"NC={n}", f"TAB={tab}", f"CIDW={cidw}", f"SPLIT={split}", "MAXCYC=400000"))[1]
        try: return [tuple(int(x) for x in l.split()[1:]) for l in o.splitlines() if l.startswith("R ")]
        except ValueError: return [("x",)]
    for nm, ev in logs:
        if run(ev, 0, 2, 0, 15, 1) != TC.expected_results(ev): return f"tcp_conn, {nm}"
    evs = []; pos = [0] * 4; four = [logs[1][1], logs[4][1], logs[2][1], logs[5][1]]
    while any(pos[k] < len(four[k]) for k in range(4)):
        for k in range(4):
            if pos[k] < len(four[k]): evs.append(dict(four[k][pos[k]], cid=k)); pos[k] += 1
    if run(evs, 2, 2, 1, 0, 2) != TC.expected_results(evs): return "tcp_tab2, interleaved"
    return None
def rtl_jobs(modname, which):
    m = __import__(modname); return [(m, which, j) for j in m.jobs() if not j[0].startswith("tab:")]            # tx_tab's own mutants (bypass, scanner, RAM initial values) need a table; the pairings use one connection
def rtl_one(job):
    m, which, (label, old, new, k) = job
    if old is None: return label, "BAD ANCHOR (0 occurrences)"
    d = tempfile.mkdtemp(prefix="mut14r_")
    for sub in ("rtl", "tb", "out", "model"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub), ignore=shutil.ignore_patterns("*.json", "*_synth.log", "*.hex", "__pycache__"))
    p = os.path.join(d, m.M); s = open(p).read(); idx = -1
    for _ in range(k + 1): idx = s.index(old, idx + 1)
    open(p, "w").write(s[:idx] + new + s[idx + len(old):]); r = rtl_battery(d, which); shutil.rmtree(d, ignore_errors=True); return label, ("NOT CAUGHT" if r is None else "caught by: " + r)
if __name__ == "__main__":
    print("NOTE: this script deliberately breaks copies of the models and the RTL. 'caught' lines are EXPECTED. NOT CAUGHT lines are the finding: the bug the network never provokes.")
    import interop as I
    base = I.battery(); print("unmutated design passes the interop battery:", base is None, "" if base is None else base)
    print("\n-- family 1 and 2: the reference and the design's models, battery = interop.battery()")
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(py_one, PY))
    cnt = {"model/ref_stack.py": [0, 0], "model/tx_gold.py": [0, 0], "model/tcp_gold.py": [0, 0]}
    for (f, *_), (label, st) in zip(PY, res): print(f"  {label}: {st}"); cnt[f][1] += 1; cnt[f][0] += st.startswith("caught")
    for f, (c, n) in cnt.items(): print(f"  {f}: caught {c} of {n}")
    print("\n-- family 3: the RTL, battery = the traces recorded in the pairings only (no fuzz, no directed lives)")
    import ch12_run, ch13_run
    sys.modules["mut_ch12"] = __import__("mut_ch12"); sys.modules["mut_ch13"] = __import__("mut_ch13")
    for modname, which, title in (("mut_ch13", "tx", "rtl/tx.sv (Chapter 13's mutants)"), ("mut_ch12", "tcp", "rtl/tcp.sv (Chapter 12's mutants)")):
        J = rtl_jobs(modname, which)
        with cf.ThreadPoolExecutor(4) as ex: rr = list(ex.map(rtl_one, J))
        c = 0
        for label, st in rr: print(f"  {label}: {st}"); c += st.startswith("caught")
        print(f"  {title}: caught {c} of {len(J)}")
