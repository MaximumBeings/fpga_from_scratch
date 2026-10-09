#!/usr/bin/env python3
"""Chapter 14, Example A: what the missing out-of-order buffer costs. The reference receiver keeps segments that arrive early; the Chapter 12 receiver drops them (the design says so in its first lines) and relies on the sender to send them again. Same DUT sender, same network, same 5,137 bytes, 30 seeds; only the receiver differs (A = reference, C = Chapter 12 TCB). The reorder probability is swept from 0 to 40% (a reordered segment is delayed by 1 to 60 ticks)."""
import os, statistics as st, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import interop as I
SEEDS = 30; TOTAL = 5137
print(f"{'reorder':>8s} | {'A: reference receiver':^34s} | {'C: Chapter 12 receiver':^34s} | {'C / A':>6s}")
print(f"{'':>8s} | {'ticks':>8s} {'retx segs':>10s} {'segments':>9s} {'ok':>4s} | {'ticks':>8s} {'retx segs':>10s} {'segments':>9s} {'ok':>4s} | {'ticks':>6s}")
for p in (0.0, 0.025, 0.05, 0.1, 0.2, 0.3, 0.4):
    pr = dict(reorder=p) if p else {}
    a = [I.run_a(sd, TOTAL, pr) for sd in range(SEEDS)]; c = [I.run_c(sd, TOTAL, pr) for sd in range(SEEDS)]
    ma, mc = st.mean(r["ticks"] for r in a), st.mean(r["ticks"] for r in c)
    print(f"{p * 100:7.1f}% | {ma:8.0f} {st.mean(r['retx'] for r in a):10.1f} {st.mean(r['segs'] for r in a):9.1f} {sum(r['ok'] for r in a):4d} | {mc:8.0f} {st.mean(r['retx'] for r in c):10.1f} {st.mean(r['segs'] for r in c):9.1f} {sum(r['ok'] for r in c):4d} | {mc / ma:6.1f}")
print("\n(retx segs = segments the sender flagged as retransmissions; segments = every segment the sender put on the wire; the transfer is 52 segments)")
