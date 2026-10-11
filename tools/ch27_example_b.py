#!/usr/bin/env python3
"""Chapter 27, example B (model level; the model equals the RTL on every scenario of ch27_run.py): (1) DETECTION LATENCY AND EXPOSURE for each cause: the cycle the supervisor leaves RUN, the cycle the logout is accepted, and how many orders still START on the wire after it has left RUN (against the bound EXPOSURE = 37 of model/safe_gold.py). (2) THE MARGINS: the longest gap between feed bytes and the longest strategy-slot hold in the traffic mixes of Chapter 26, which say how small FT and ST can be before a healthy system trips."""
import os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model")); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import safe_gold as SGD, sup_gold as SG, w2w_gold as WG, sess_gold as SS, ch26_run as C26, ch27_run as C27
def first_safe(rows):
    for i in range(1, len(rows)):
        if rows[i][-4] == SG.SAFE and rows[i - 1][-4] != SG.SAFE: return i
if __name__ == "__main__":
    print("== 1. detection latency and exposure, per cause (the scenarios of ch27_run.py; cycle numbers are model time)")
    print(f"  {'scenario':9s} {'cause':>10s} {'event':>6s} {'kill':>6s} {'logout':>7s} | {'orders sent':>11s} {'after kill':>10s} {'last start - kill':>17s}")
    for i, k in enumerate(("feedloss", "stall", "trip", "faults", "refuse", "close")):
        c, m, kw = C27.make(k, C27.KINDS.index(k) + 1); res = SGD.run(c, m, **C27.mkw(kw)); rows = res["rows"]; ks = first_safe(rows)
        if ks is None: print(f"  {k:9s} did not trip"); continue
        cs = rows[ks][-1]; cause = "+".join(n for b, n in enumerate(SG.CAUSES) if cs >> b & 1)
        lg = [j for j, r in enumerate(rows) if r[-2]]; logout = lg[0] if lg else None
        sent = [p[0] for p in res["safe"].X.X.packets if p[1] == SS.ORDER]; after = [p for p in sent if p > ks]
        ev = {"feedloss": 1500, "trip": 2000}.get(k)
        print(f"  {k:9s} {cause:>10s} {str(ev) if ev else '-':>6s} {ks:6d} {str(logout):>7s} | {len(sent):11d} {len(after):10d} {str(max(after) - ks) if after else '-':>17s}")
    print(f"  (the bound on how long after leaving RUN an order may still START on the wire: {SGD.EXPOSURE} cycles)")
    print("\n== 2. the margins: the longest silence of the feed and the longest hold of the strategy slot in the healthy mixes of Chapter 26 (seed 1)")
    print(f"  {'mix':9s} {'longest feed gap':>16s} {'longest slot hold':>17s}  (F = 12 unless noted)")
    for kind in ("normal", "dense", "slow", "burst", "slowsig", "narrow", "openbook"):
        cm = C26.make(kind, 1); cyc = cm[0]; kw = cm[2]; last = None; gap = 0
        for c, cy in enumerate(cyc):
            if cy.get("s", (0,))[0]:
                if last is not None: gap = max(gap, c - last)
                last = c
        X = WG.W2W(**kw); held = 0; mx = 0
        for c, cy in enumerate(cyc):
            X.step(cy, cm[1].get(c)); held = held + 1 if X.slot else 0; mx = max(mx, held)
        print(f"  {kind:9s} {gap:16d} {mx:17d}  {'F = ' + str(kw.get('f', 12))}")
    print("  (a supervisor with FT at or below the longest gap trips a healthy system; the same for ST and the longest hold; the gap includes the idle cycles between packets, which the mixes choose)")
