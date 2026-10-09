#!/usr/bin/env python3
"""Chapter 12: the running designs. (1) lint; (2) the model's hand-checked lives; (3) what the stimulus covers; (4) the single-connection engine against the model; (5) the connection tables (first and second design, 3 and 4 stages) against the model, with events for the same connection back to back; (6) the window test: for every window, segment length and sequence-number base the exact set of acceptable sequence numbers, against the derivation; (7) latency and the price of the missing bypass; (8) the hot path alone, against the model and on realistic traffic. Usage: ch12_run.py"""
import os, re, subprocess, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, tcp_gold as g
R = flow.ROOT; F = ["rtl/tcp.sv", "tb/tcp_tb.sv"]
DES = [("tcp_conn (one connection)", 0, 0), ("tcp_tab (RAM, bypass)", 1, 0), ("tcp_tab2, 3 stages", 2, 0), ("tcp_tab2, 4 stages", 2, 1)]
def run(evs, tab, cidw=4, split=0, idle=15, sim="icarus", seed=1):
    n = g.write_events(os.path.join(R, "out", "tcp_stim.hex"), evs, seed, idle)
    o = (flow.sim_icarus if sim == "icarus" else flow.sim_verilator)(F, "tcp_tb", defines=(f"NC={n}", f"TAB={tab}", f"CIDW={cidw}", f"SPLIT={split}"))[1]
    return [tuple(int(x) for x in l.split()[1:]) for l in o.splitlines() if l.startswith("R ")], o
def stat(o, k): m = re.search(k + r" (\d+)", o); return int(m.group(1)) if m else -1
if __name__ == "__main__":
    print("== 1. lint gate (Verilator -Wall --lint-only, Yosys 'check')")
    for top in ("tcp_next", "tcp_conn", "tcp_tab", "tcp_tab2", "tcp_fast"):
        p = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", top, "rtl/tcp.sv"], cwd=R, capture_output=True, text=True); w = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning")]
        y = subprocess.run(["yosys", "-p", f"read_verilog -sv rtl/tcp.sv; hierarchy -top {top}; proc; opt_clean; check"], cwd=R, capture_output=True, text=True).stdout
        print(f"  {top:10s} Verilator warnings: {len(w)}   Yosys check problems: {len([l for l in y.splitlines() if 'Found and reported' in l and ' 0 problems' not in l])}")
    print("\n== 2. the model's hand-checked lives (asserted by python3 model/tcp_gold.py)")
    print("  " + subprocess.run([sys.executable, "model/tcp_gold.py"], cwd=R, capture_output=True, text=True).stdout.strip() + ": active open with sequence numbers across the wrap, a duplicate, our close, FIN_WAIT_2, TIME_WAIT, the 2MSL timeout; passive open, a blind RST in the window (challenge ACK), the exact RST")
    print("\n== 3. what the stimulus covers (8 seeds of 3,000 random events over 8 connections, plus the directed lives): the state each event arrived in, and the distinct reactions")
    cnt = Counter(); tr = set(); tot = 0
    for seed in range(8):
        evs = g.directed_events(0) + g.gen_events(seed, 3000, cids=8); tot += len(evs); tr |= g.transitions(evs); tcb = {}
        for v in evs: t = tcb.setdefault(v.get("cid", 0), g.TCB()); cnt[t.state] += 1; t.event(v["e"], v.get("f", 0), v.get("seq", 0), v.get("ack", 0), v.get("ln", 0), v.get("wnd", 0), v.get("iss", 0))
    print(f"  {tot} events;  " + ", ".join(f"{g.SNAME[s]} {cnt[s]}" for s in range(11)))
    print(f"  {len(tr)} distinct (state, event class, next state, segment sent, data delivered) combinations; {len({(a, c, d) for a, c, d, e, f in tr})} distinct (state, event class, next state)")
    print("\n== 4. tcp_conn against the model: every state variable, the segment sent and the bytes delivered after every event")
    print(f"  {'seeds':>5s} {'events':>7s} | {'Icarus':>9s} {'Verilator':>10s}")
    ok = 0; n = 0; v = "-"
    for seed in range(8):
        evs = g.directed_events(0) + g.gen_events(seed, 2500, cids=1); got, o = run(evs, 0, seed=seed); exp = g.expected_results(evs); ok += got == exp; n += len(evs)
        if seed == 0: gv, _ = run(evs, 0, sim="verilator"); v = "PASS" if gv == exp else "FAIL"
    print(f"  {8:5d} {n:7d} | {ok:6d} of 8 {v:>10s}")
    print("\n== 5. the tables against the model: many connections, events for the same connection back to back (4 connections: one event in four is for the same connection as the one before) and with idle cycles; 4 seeds each")
    print(f"  {'design':26s} {'connections':>11s} {'events':>7s} | {'no idle':>8s} {'15% idle':>9s} {'Verilator':>10s}")
    for nm, tab, split in DES[1:]:
        for cidw in (2, 4, 6):
            ok0 = ok1 = 0; n = 0; v = "-"
            for seed in range(4):
                evs = g.directed_events(0) + g.gen_events(seed, 2500, cids=1 << cidw); exp = g.expected_results(evs); n += len(evs)
                got, _ = run(evs, tab, cidw, split, idle=0, seed=seed); ok0 += got == exp
                got, _ = run(evs, tab, cidw, split, idle=15, seed=seed); ok1 += got == exp
                if seed == 0 and cidw == 2: gv, _ = run(evs, tab, cidw, split, sim="verilator"); v = "PASS" if gv == exp else "FAIL"
            print(f"  {nm:26s} {1 << cidw:11d} {n:7d} | {ok0:5d} of 4 {ok1:6d} of 4 {v:>10s}")
    print("\n== 6. the window test: ESTABLISHED sequence space near the wrap, a FIN outstanding, a probing ACK segment of length ln at offset `off` from RCV.NXT; the probe is accepted exactly when it moves the connection to FIN_WAIT_2")
    print(f"  {'window':>6s} {'len':>4s} | {'derived accepted offsets':>25s} | {'measured (tcp_conn)':>20s} {'measured (tcp_tab2, 4 stages)':>30s}")
    def probes(base, wnd, ln, offs):
        ev = []
        for off in offs:
            ev += [dict(e=g.E_OPEN_A, iss=1000), dict(e=g.E_SEG, f=g.SYN | g.ACK, seq=(base - 1) & g.M, ack=1001, wnd=wnd), dict(e=g.E_CLOSE), dict(e=g.E_SEG, f=g.ACK, seq=(base + off) & g.M, ack=1002, ln=ln, wnd=wnd), dict(e=g.E_ABORT)]
        return ev
    allok = True
    def rng_str(xs):
        xs = sorted(xs); out = []
        for x in xs:
            if out and out[-1][1] == x - 1: out[-1][1] = x
            else: out.append([x, x])
        return " + ".join(f"[{a}, {b}]" for a, b in out) or "none"
    for wnd in (0, 1, 5, 100):
        for ln in (0, 1, 5):
            if ln == 0: der = {0} if wnd == 0 else set(range(0, wnd))
            else: der = set() if wnd == 0 else set(range(0, wnd)) | set(range(1 - ln, wnd - ln + 1))
            res = []
            for tab, split in ((0, 0), (2, 1)):
                acc = []
                for base in (0, 0xFFFFFFF0, 0x7FFFFFF0):
                    offs = list(range(-8, wnd + 9)); evs = probes(base, wnd, ln, offs)
                    got, _ = run(evs, tab, 2, split, idle=0); acc.append({o for o, r in zip(offs, got[3::5]) if r[1] == g.FW2} if len(got) == len(evs) else None)
                res.append(acc)
            ms = []
            for acc in res:
                good = all(a == der for a in acc); allok &= good; ms.append(rng_str(acc[0]) + ("" if good else " MISMATCH"))
            print(f"  {wnd:6d} {ln:4d} | {rng_str(der):>25s} | {ms[0]:>20s} {ms[1]:>30s}")
    print(f"  derived: a segment is acceptable when its first byte or its last byte lies in the window [RCV.NXT, RCV.NXT + wnd): for length 0, the offsets 0 .. wnd-1 (just 0 when the window is 0); for length ln > 0, the offsets 0 .. wnd-1 and, for the last byte, 1-ln .. wnd-ln (never when the window is 0); note the GAP when ln > wnd + 1: a segment that straddles the whole window is NOT acceptable by this rule. Three bases of the sequence space (0, 0xFFFFFFF0, 0x7FFFFFF0), two designs, equal to the derivation: {'YES' if allok else 'NO'}")
    print("\n== 7. latency and the price of the missing bypass: 1,000 events for ONE connection back to back, and 1,000 spread over 64 connections, no idle cycles")
    print(f"  {'design':26s} {'latency':>8s} | {'one connection: cycles/event':>29s} | {'64 connections: cycles/event':>29s}")
    for nm, tab, split in DES:
        row = []
        for cids, cidw in ((1, 6), (64, 6)):
            evs = g.gen_events(3, 1000, cids=cids); _, o = run(evs, tab, cidw, split, idle=0); row.append((stat(o, "CYCLES") - 6 - (1 << cidw if tab else 0)) / len(evs)); lat = stat(o, "LAT")
        print(f"  {nm:26s} {lat:8d} | {row[0]:29.2f} | {row[1]:29.2f}")
    print("  (cycles per event after the reset and the RAM clearing; the bypass of tcp_tab lets back-to-back events for one connection through; tcp_tab2 has none and waits for the write)")
    print("\n== 8. the hot path alone (tcp_fast): against the model on states and segments of the realistic traffic and on uniformly random ones")
    print(f"  {'cases':>8s} {'hit by model':>13s} {'hit by RTL':>11s} {'hit decisions equal':>20s} {'results equal on hits':>22s}")
    cases = []
    for seed in range(4):
        tcb = {}
        for v in g.realistic_events(seed, 8, 150) + g.gen_events(seed, 3000, cids=4):
            t = tcb.setdefault(v.get("cid", 0), g.TCB())
            if v["e"] == g.E_SEG: cases.append((t.snapshot(), v))
            t.event(v["e"], v.get("f", 0), v.get("seq", 0), v.get("ack", 0), v.get("ln", 0), v.get("wnd", 0), v.get("iss", 0))
    cases += g.fast_random_cases(5, 4000)
    with open(os.path.join(R, "out", "tcp_fast_stim.hex"), "w") as fh:
        for (st, pas, una, nxt, rcv), v in cases: fh.write("%x%08x%08x%08x%08x%08x%x%04x%04x\n" % (st, una, nxt, rcv, v.get("seq", 0) & g.M, v.get("ack", 0) & g.M, v.get("f", 0), v.get("ln", 0), v.get("wnd", 0)))
    o = flow.sim_icarus(["rtl/tcp.sv", "tb/tcp_fast_tb.sv"], "tcp_fast_tb", defines=(f"NC={len(cases)}",))[1]; hs = [tuple(int(x) for x in l.split()[1:]) for l in o.splitlines() if l.startswith("H ")]
    mh = rh = eq = same = 0
    for (snap, v), h in zip(cases, hs):
        t = g.TCB(); t.state, t.passive, t.una, t.nxt, t.rcv = snap; mdl = g.fast_path(t, v.get("f", 0), v.get("seq", 0), v.get("ack", 0), v.get("ln", 0), v.get("wnd", 0)); mh += mdl; rh += h[0]; eq += (h[0] == 1) == mdl
        if h[0]: tx, d = t.event(v["e"], v.get("f", 0), v.get("seq", 0), v.get("ack", 0), v.get("ln", 0), v.get("wnd", 0), 0); same += (h[1], h[2], h[3], h[4]) == (t.una, t.rcv, 1 if tx else 0, d) and t.state == g.ESTAB
    print(f"  {len(cases):8d} {mh:13d} {rh:11d} {eq:14d} of {len(cases)} {same:17d} of {rh}")
