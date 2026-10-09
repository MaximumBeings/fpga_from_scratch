#!/usr/bin/env python3
"""Chapter 13: the running designs. (1) lint; (2) the model: hand-checked RFC 6298 scenarios and the closed loop (sender, lossy FIFO channel, in-order receiver); (3) tx_conn against the model on closed-loop traces; (4) tx_tab with the timer scanner against the model, with connections interleaved and the scanner's own ticks; (5) how late the scanner is; (6) delivered bytes and retransmissions under loss. Usage: ch13_run.py"""
import os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, tx_gold as g
R = flow.ROOT; F = ["rtl/tx.sv", "tb/tx_tb.sv"]
def sim(n, tab, cidw=2, scan=1, simu="icarus", **extra):
    d = (f"NC={n}", f"TAB={tab}", f"CIDW={cidw}", f"SCAN={scan}") + tuple(f"{k}={v}" for k, v in extra.items())
    o = (flow.sim_icarus if simu == "icarus" else flow.sim_verilator)(F, "tx_tb", defines=d)[1]
    return [tuple(int(x) for x in l.split()[1:]) for l in o.splitlines() if l.startswith("R ")], o
def row(cid, typ, now, s, tx):
    una, nxt, mx, wnd, end, sr, rv, rto, dl, ton, tim, have = s.snapshot(); return (cid, typ, now, una, nxt, mx, wnd, end, sr, rv, rto, dl, ton, tim, have, 1 if tx else 0, tx[0] if tx else 0, tx[1] if tx else 0, tx[2] if tx else 0)
def conn_expected(ev, **p):
    s = g.Sender(**p); out = []
    for c, cid, e, a, w in ev: tx = s.event(e, c, a, w); out.append(row(0, 0, 0, s, tx))
    return out
def tab_events(K, seed, loss, total=3000):
    evs = []
    for c in range(K):
        r = g.transfer(seed * 10 + c, total, loss=loss, k=K, c=c); evs += [(cy, c, e, a, w) for cy, e, a, w in r["events"] if e != g.TICK]
    evs.sort(); return evs
def replay(evs, got, **p):
    snd = {}; ext = iter(evs); exp = []; lateness = []
    for r in got:
        cid, typ, now = r[0], r[1], r[2]
        if typ == g.TICK: a = w = 0
        else:
            c, cc, e, a, w = next(ext)
            if (cc, e, c) != (cid, typ, now): return None, None
        s = snd.setdefault(cid, g.Sender(**p)); dl = s.deadline; on = s.timer_on; tx = s.event(typ, now, a, w); exp.append(row(cid, typ, now, s, tx))
        if typ == g.TICK and tx and on: lateness.append((now - dl) & g.M)
    return exp, lateness
if __name__ == "__main__":
    print("== 1. lint gate (Verilator -Wall --lint-only, Yosys 'check')")
    for top in ("tx_next", "tx_conn", "tx_tab"):
        p = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", top, "rtl/tx.sv"], cwd=R, capture_output=True, text=True); w = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning")]
        y = subprocess.run(["yosys", "-p", f"read_verilog -sv rtl/tx.sv; hierarchy -top {top}; proc; opt_clean; check"], cwd=R, capture_output=True, text=True).stdout
        print(f"  {top:8s} Verilator warnings: {len(w)}   Yosys check problems: {len([l for l in y.splitlines() if 'Found and reported' in l and ' 0 problems' not in l])}")
    print("\n== 2. the model: RFC 6298 by hand, and the closed loop (sender, lossy FIFO channel with random delay, in-order receiver); every byte must arrive in order")
    print("  " + subprocess.run([sys.executable, "model/tx_gold.py"], cwd=R, capture_output=True, text=True).stdout.strip().replace("\n", "\n  "))
    print(f"  {'one-way loss':>12s} {'bytes':>7s} {'delivered':>10s} {'ticks':>7s} {'retransmitted segments':>23s} {'segments':>9s}")
    for loss in (0.0, 0.01, 0.05, 0.2):
        r = g.transfer(7, 20000, loss=loss, mss=100); print(f"  {loss * 100:11.0f}% {r['total']:7d} {r['delivered']:10d} {r['done_tick']:7d} {r['retx']:23d} {len(r['tx']):9d}")
    print("\n== 3. tx_conn against the model: the events of a closed-loop transfer, every state variable and the segment after every event")
    print(f"  {'loss':>5s} {'seeds':>5s} {'events':>7s} {'segments':>9s} | {'Icarus':>9s} {'Verilator':>10s}")
    for loss in (0.0, 0.01, 0.05, 0.2):
        ok = 0; ne = ns = 0; v = "-"
        for seed in range(4):
            r = g.transfer(seed, 6000, loss=loss, mss=100); ev = [(c, 0, e, a, w) for c, e, a, w in r["events"]]; n = g.write_stim(os.path.join(R, "out", "tx_stim.hex"), ev); got, _ = sim(n, 0); exp = conn_expected(ev, mss=100); ok += got == exp; ne += len(ev); ns += sum(1 for x in exp if x[15])
            if seed == 0: gv, _ = sim(n, 0, simu="verilator"); v = "PASS" if gv == exp else "FAIL"
        print(f"  {loss * 100:4.0f}% {4:5d} {ne:7d} {ns:9d} | {ok:6d} of 4 {v:>10s}")
    print("\n== 3b. tx_conn on traces the closed loop cannot make: a small window that changes with every ACK (400 bytes, halved or quartered at random), and open-loop FUZZ (ACKs at SND.UNA, at the edges of the data in flight, beyond it, before it, with windows of 0, 50, 100, 300, 65535 and random; WRITEs; POLLs; TICKs at random times, some far apart)")
    print(f"  {'trace':34s} {'runs':>5s} {'events':>7s} {'segments':>9s} | {'Icarus':>9s} {'Verilator':>10s}")
    for nm, mk in (("window 400, updated by every ACK, 5%", lambda sd: [(c, 0, e, a, w) for c, e, a, w in g.transfer(sd, 6000, loss=0.05, mss=100, wnd=400, wnd_var=True)["events"]]), ("open-loop fuzz, 3,000 events", lambda sd: [(c, 0, e, a, w) for c, cid, e, a, w in g.fuzz_events(sd, 3000)])):
        ok = 0; ne = ns = 0; v = "-"
        for seed in range(6):
            ev = mk(seed); n = g.write_stim(os.path.join(R, "out", "tx_stim.hex"), ev); got, _ = sim(n, 0); exp = conn_expected(ev, mss=100); ok += got == exp; ne += len(ev); ns += sum(1 for x in exp if x[15])
            if seed == 0: gv, _ = sim(n, 0, simu="verilator"); v = "PASS" if gv == exp else "FAIL"
        print(f"  {nm:34s} {6:5d} {ne:7d} {ns:9d} | {ok:6d} of 6 {v:>10s}")
    print("\n== 4. tx_tab with the timer scanner: K connections whose events are interleaved (cycle t x K + c), the timers checked by the scanner's own ticks (in every cycle with no outside event); the model replays the events in the order the RTL processed them")
    print(f"  {'connections':>11s} {'RAM words':>9s} {'outside events':>14s} {'scanner ticks':>13s} {'timeouts':>9s} | {'Icarus':>8s} {'Verilator':>10s}")
    for K, cidw in ((2, 1), (4, 2), (13, 4), (50, 6)):
        evs = tab_events(K, 1, 0.05, 2000); n = g.write_stim(os.path.join(R, "out", "tx_stim.hex"), evs); got, _ = sim(n, 1, cidw); exp, late = replay(evs, got, mss=100)
        ok = exp == got and exp is not None; v = "-"
        if K == 4: gv, _ = sim(n, 1, cidw, simu="verilator"); v = "PASS" if gv == got else "FAIL"
        print(f"  {K:11d} {1 << cidw:9d} {len(evs):14d} {sum(1 for x in got if x[1] == g.TICK):13d} {len(late or []):9d} | {'YES' if ok else 'NO':>8s} {v:>10s}")
    evs = []
    for c in range(4): evs += [(cy, c, e, a, w) for cy, cid, e, a, w in g.fuzz_events(40 + c, 1500, k=4, c=c) if e != g.TICK]
    evs.sort(); n = g.write_stim(os.path.join(R, "out", "tx_stim.hex"), evs); got, _ = sim(n, 1, 2); exp, late = replay(evs, got, mss=100)
    print(f"  4 open-loop fuzz streams, interleaved: {len(evs)} outside events, {sum(1 for x in got if x[1] == g.TICK)} scanner ticks, {len(late or [])} timeouts: equal to the model: {'YES' if exp == got and exp is not None else 'NO'}")
    print("\n== 5. how late is the scanner? N connections, each sends one window of data at start and then nothing; its retransmission timer (300 ticks, then backed off) fires when the scanner reaches it: lateness = the cycle of the TICK that fired it minus the deadline")
    print(f"  {'connections':>11s} {'timeouts seen':>13s} {'min late':>9s} {'mean late':>10s} {'max late':>9s} {'derived bound N':>16s}")
    for cidw in (1, 2, 4, 6):
        N = 1 << cidw; evs = []
        for c in range(N): evs += [(2 * c, c, g.WRITE, 500, 0), (2 * c + 1, c, g.POLL, 0, 0)]
        evs.sort(); n = g.write_stim(os.path.join(R, "out", "tx_stim.hex"), evs, 2 * N + 12 * 300 + 2000); got, _ = sim(n, 1, cidw); exp, late = replay(evs, got, mss=100)
        print(f"  {N:11d} {len(late):13d} {min(late):9d} {sum(late) / len(late):10.1f} {max(late):9d} {N:16d}")
    print("  (a timer is checked once every N cycles when the scanner has the cycles to itself: the lateness lies between 0 and N - 1; outside events take cycles from it and raise the bound by their number; a timer wheel (Exercise 2) bounds it by the wheel's resolution instead)")
