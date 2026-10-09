#!/usr/bin/env python3
"""Chapter 14: the designs of Chapters 12 and 13 against an independent reference over an impaired network. (1) the reference alone; (2) the three pairings under six impairment profiles: bytes, order, invariants; (3) the missing control-segment timer; (4) the traces of those runs replayed on the RTL (tx_conn for the send side, tcp_conn and the table for the receive side), in two simulators."""
import os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, interop as I, tx_gold as TX, tcp_gold as TC, ref_stack as RS, ch12_run as c12, ch13_run as c13
R = flow.ROOT; TOTAL = 5137; SEEDS = 20
PROF = {k: v for k, v in I.PROFILES.items() if "win" not in v}                       # the small-window profile belongs to Example B
def pairings(total=TOTAL, seeds=SEEDS):
    out = {}
    for nm, pr in PROF.items():
        out[nm] = [[fn(sd, total, pr) for sd in range(seeds)] for fn in (I.run_a, I.run_b, I.run_c)]
    return out
def sender_trace(r): return [(t, 0, e, a, w) for t, e, a, w in r["events"]]
if __name__ == "__main__":
    print("== 1. the reference alone (hand-checked by python3 model/ref_stack.py): out-of-order segments held and delivered when the hole fills, a duplicate adds nothing, the channel loses the probability it is given")
    import subprocess
    print("  " + subprocess.run([sys.executable, "model/ref_stack.py"], cwd=R, capture_output=True, text=True).stdout.strip())
    print(f"\n== 2. three pairings, seven impairment profiles, {SEEDS} seeds each, {TOTAL} bytes (MSS 100, one-way delay 20 ticks, receive window 4,096 for the DUT receiver). 'ok' = every byte arrived once, in order, and the invariants held at every event")
    print("  A: DUT sender -> reference receiver   B: reference client -> DUT receiver (handshake and close included)   C: DUT sender -> DUT receiver")
    print(f"  {'profile':36s} | {'pairing':>7s} {'ok':>6s} {'mean ticks':>11s} {'max':>7s} {'mean retx segs':>15s} {'segments':>9s} {'invariant checks':>17s} {'lost':>6s} {'duplicated':>11s} {'delayed':>8s} {'forged':>7s}")
    res = pairings()
    for nm, trio in res.items():
        for lab, rs in zip("ABC", trio):
            print(f"  {nm:36s} | {lab:>7s} {sum(r['ok'] for r in rs):3d}/{len(rs):<2d} {st.mean(r['ticks'] for r in rs):11.0f} {max(r['ticks'] for r in rs):7d} {st.mean(r['retx'] for r in rs):15.1f} {sum(r['segs'] for r in rs):9d} {sum(r['checks'] for r in rs):17d} {sum(r['lost'] for r in rs):6d} {sum(r['duped'] for r in rs):11d} {sum(r['late'] for r in rs):8d} {sum(r.get('forged', 0) for r in rs):7d}")
    print("  (retx segs = segments the sender flagged as retransmissions, per transfer of 52 segments)")
    print("  (delayed = segments that arrived after one sent later, counted at the receiving end; forged = off-path segments injected and answered without changing state)")
    print("\n== 2b. the same with the sequence numbers about to wrap: the first data byte is 1,500 below 2^32, so the transfer crosses the wrap (profile: loss 5, reorder 10, dup 5; 20 seeds)")
    pr = I.PROFILES["loss 5, reorder 10, dup 5"]; WR = (1 << 32) - 1500
    for lab, fn, kw in (("A", I.run_a, dict(isn=WR)), ("B", I.run_b, dict(iss=WR - 1)), ("C", I.run_c, dict(isn=WR))):
        rs = [fn(sd, TOTAL, pr, **kw) for sd in range(SEEDS)]; print(f"  pairing {lab}: {sum(r['ok'] for r in rs)}/{len(rs)} ok, mean {st.mean(r['ticks'] for r in rs):.0f} ticks")
    print("\n== 3. the DUT has no timer for CONTROL segments (SYN-ACK, FIN). Pairing B, 60 seeds per profile: runs that finish with and without a harness shim that re-sends the DUT's last control segment after 300 silent ticks")
    print(f"  {'profile':36s} | {'no shim: finished':>18s} {'stalled in':>26s} | {'shim 300: finished':>19s} {'shim re-sends':>14s}")
    for nm, pr in PROF.items():
        a = [I.run_b(sd, 2137, pr, ctl_rto=0) for sd in range(60)]; b = [I.run_b(sd, 2137, pr, ctl_rto=300) for sd in range(60)]; stalls = {}
        for r in a:
            if not r["ok"]: stalls[r["state"]] = stalls.get(r["state"], 0) + 1
        print(f"  {nm:36s} | {sum(r['ok'] for r in a):15d}/60 {', '.join(f'{k} {v}' for k, v in sorted(stalls.items())) or '-':>26s} | {sum(r['ok'] for r in b):16d}/60 {sum(r['shim'] for r in b):14d}")
    print("\n== 4. the recorded traces on the RTL. Send side: the events the sender saw in A and C (acknowledgements duplicated, late, lost; every tick is an event) into tx_conn, compared after every event with the model. Receive side: the segments the TCB saw in B and C into tcp_conn and into a 4-connection table (tcp_tab2, 4 stages) with the four runs interleaved")
    print(f"  {'trace':36s} | {'runs':>5s} {'events':>7s} | {'Icarus':>10s} {'Verilator':>10s}")
    for lab, fn in (("A", I.run_a), ("C", I.run_c)):
        for nm in ("loss 5%", "reorder 20%", "harsh: loss 15, reorder 30, dup 15", "off-path noise 10%"):
            ok = 0; ne = 0; v = "-"
            for sd in range(3):
                r = fn(sd + 40, 2137, I.PROFILES[nm]); ev = sender_trace(r); n = TX.write_stim(os.path.join(R, "out", "tx_stim.hex"), ev); got, _ = c13.sim(n, 0); exp = c13.conn_expected(ev, mss=100); ok += got == exp; ne += len(ev)
                if sd == 0: gv, _ = c13.sim(n, 0, simu="verilator"); v = "PASS" if gv == exp else "FAIL"
            print(f"  tx_conn, {lab}, {nm:26s} | {3:5d} {ne:7d} | {ok:7d} of 3 {v:>10s}")
    for lab, fn in (("B", I.run_b), ("C", I.run_c)):
        for nm in ("loss 5%", "reorder 20%", "harsh: loss 15, reorder 30, dup 15", "off-path noise 10%"):
            ok = 0; ne = 0; v = "-"
            for sd in range(3):
                r = fn(sd + 40, 2137, I.PROFILES[nm]); ev = r["evlog"]; exp = TC.expected_results(ev); got, _ = c12.run(ev, 0, seed=sd); ok += got == exp; ne += len(ev)
                if sd == 0: gv, _ = c12.run(ev, 0, sim="verilator"); v = "PASS" if gv == exp else "FAIL"
            print(f"  tcp_conn, {lab}, {nm:25s} | {3:5d} {ne:7d} | {ok:7d} of 3 {v:>10s}")
    ok = 0; ne = 0; v = "-"
    for sd in range(3):
        logs = [I.run_b(sd * 4 + k + 60, 2137, I.PROFILES["loss 5, reorder 10, dup 5"])["evlog"] for k in range(2)] + [I.run_c(sd * 4 + k + 70, 2137, I.PROFILES["loss 5, reorder 10, dup 5"])["evlog"] for k in range(2)]
        evs = []; pos = [0] * 4
        while any(pos[k] < len(logs[k]) for k in range(4)):
            for k in range(4):
                if pos[k] < len(logs[k]): evs.append(dict(logs[k][pos[k]], cid=k)); pos[k] += 1
        exp = TC.expected_results(evs); got, _ = c12.run(evs, 2, 2, 1, seed=sd); ok += got == exp; ne += len(evs)
        if sd == 0: gv, _ = c12.run(evs, 2, 2, 1, sim="verilator"); v = "PASS" if gv == exp else "FAIL"
    print(f"  tcp_tab2 4 stages, B,B,C,C interleaved | {3:5d} {ne:7d} | {ok:7d} of 3 {v:>10s}")
    print("\n== 5. how much of the Chapter 12 receiver do the pairings reach? The distinct (state, event class, next state) triples seen in all B and C runs of section 2 and 2b, against those seen by Chapter 12's directed lives and 8 seeds of 3,000 random events over 8 connections")
    inter = set()
    for nm, trio in res.items():
        for rs in trio[1:]:
            for r in rs: inter |= {(a, c, d) for a, c, d, e, f in TC.transitions(r["evlog"])}
    ch12 = set()
    for seed in range(8): ch12 |= {(a, c, d) for a, c, d, e, f in TC.transitions(TC.directed_events(0) + TC.gen_events(seed, 3000, cids=8))}
    print(f"  pairings: {len(inter)} triples; Chapter 12 stimulus: {len(ch12)}; common: {len(inter & ch12)}; reached by the pairings and not by Chapter 12's stimulus: {len(inter - ch12)}")
    st_i = sorted({a for a, c, d in inter}); st_c = sorted({a for a, c, d in ch12})
    print("  states in which the pairings delivered an event: " + ", ".join(TC.SNAME[x] for x in st_i) + f"  ({len(st_i)} of 11)")
    print("  states Chapter 12's stimulus reached: " + f"{len(st_c)} of 11")
