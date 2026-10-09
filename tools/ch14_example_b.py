#!/usr/bin/env python3
"""Chapter 14, Example B: a receive window below one segment. The Chapter 12 receiver accepts the part of a segment that fits the window and acknowledges that part; the Chapter 13 sender sends whole segments after a timeout. Window swept from 40 to 1,000 bytes (MSS 100), no loss, 5,137 bytes; the reference client (B) respects the window per segment in flight, the Chapter 13 sender (C) is the DUT pair. A run is cut at 400,000 ticks."""
import os, statistics as st, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import interop as I
TOTAL = 5137; SEEDS = 5
print(f"{'window':>7s} | {'B: reference client -> Ch12 receiver':^40s} | {'C: Ch13 sender -> Ch12 receiver':^46s}")
print(f"{'bytes':>7s} | {'finished':>9s} {'ticks':>8s} {'retx segs':>10s} {'segments':>9s} | {'finished':>9s} {'ticks':>8s} {'retx segs':>10s} {'segments':>9s} {'timeouts*':>10s}")
for w in (40, 60, 99, 100, 150, 250, 1000):
    b = [I.run_b(sd, TOTAL, dict(win=w)) for sd in range(SEEDS)]; c = [I.run_c(sd, TOTAL, dict(win=w)) for sd in range(SEEDS)]
    def f(rs): return st.mean(r["ticks"] for r in rs)
    print(f"{w:7d} | {sum(r['ok'] for r in b):6d}/{SEEDS} {f(b):8.0f} {st.mean(r['retx'] for r in b):10.1f} {st.mean(r['segs'] for r in b):9.1f} | {sum(r['ok'] for r in c):6d}/{SEEDS} {f(c):8.0f} {st.mean(r['retx'] for r in c):10.1f} {st.mean(r['segs'] for r in c):9.1f} {st.mean(r['retx'] for r in c):10.1f}")
print("\n* each timeout of the Chapter 13 sender is one retransmitted segment, so the two columns agree; a run that does not finish is cut at 400,000 ticks and its tick count is the cut")
