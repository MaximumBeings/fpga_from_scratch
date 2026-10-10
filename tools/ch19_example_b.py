#!/usr/bin/env python3
"""Chapter 19, example B (model level): how big must the book be? A STATIONARY flow, generated against the book itself (so that a rejected add simply is not live): at each event an ADD with a probability that pulls the number of live orders towards a TARGET (0.5 + 0.45 (TARGET - N) / TARGET, clamped to 0.05 .. 0.95), else an event on a uniformly chosen live order (50% DELETE, 25% EXEC or CANCEL of a random part of it, 25% REPLACE at a new price). Prices: within `spread` ticks of a mid that moves one tick in 40% of the events, on the side's own side of the mid. 30,000 events, 5 seeds, 2 symbols, no faults. (1) LEVELS: the share of ADDs rejected for lack of a price level against D, for three spreads, with the order table unlimited. (2) ORDERS: the share of ADDs rejected for FULL against NO for a target of 64 live orders, with D unlimited; and the occupancy that results. (3) both together."""
import os, random, statistics as st, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import book_gold as G
BIG = 10 ** 6
def flow(seed, n, spread, target, d, no, ns=2):
    rng = random.Random(seed); b = G.Book(ns, d, no); mid = 1000; nxt = 1; stats = dict(adds=0, lvl=0, full=0); occ = []; lev = []
    for _ in range(n):
        mid += rng.choice([0, 0, 0, 1, -1]) if rng.random() < .4 else 0; N = len(b.orders); live = list(b.orders)
        p_add = max(0.05, min(0.95, 0.5 + 0.45 * (target - N) / target))
        def px(side): return mid + (rng.randint(1, spread) if side else -rng.randint(1, spread))
        if not live or rng.random() < p_add:
            side = rng.randrange(2); e = dict(t=G.ADD, ref=nxt, sym=rng.randrange(ns), side=side, px=px(side), sh=rng.randint(1, 300)); nxt += 1
        else:
            ref = rng.choice(live); o = b.orders[ref]; r = rng.random()
            if r < 0.5: e = dict(t=G.DELETE, ref=ref)
            elif r < 0.75: e = dict(t=rng.choice([G.EXEC, G.CANCEL]), ref=ref, sh=rng.randint(1, o[3]))
            else: e = dict(t=G.REPLACE, ref=ref, ref2=nxt, px=px(o[1]), sh=rng.randint(1, 300)); nxt += 1
        ph, res, s = b.event(e)
        if e["t"] == G.ADD: stats["adds"] += 1; stats["lvl"] += res == G.LVL; stats["full"] += res == G.FULL
        occ.append(len(b.orders)); lev.append(max(len(b.lv[s_][k]) for s_ in range(ns) for k in range(2)))
    return stats, occ, lev
def pct(xs, q): xs = sorted(xs); return xs[min(len(xs) - 1, int(q * len(xs)))]
if __name__ == "__main__":
    N = 30000; S = range(5)
    print(f"== 1. price levels: ADDs rejected for lack of a level (LVL) against D; unlimited order table; target 64 live orders; {len(S)} seeds x {N:,} events")
    print(f"  {'D':>3s} | " + " ".join(f"{'spread ' + str(sp):>12s}" for sp in (4, 8, 16)))
    prof = {}
    for sp in (4, 8, 16):
        lv = []
        for sd in S: lv += flow(sd, N, sp, 64, BIG, BIG)[2]
        prof[sp] = (st.mean(lv), pct(lv, .99), max(lv))
    for d in (2, 4, 6, 8, 12, 16, 24):
        row = []
        for sp in (4, 8, 16):
            a = l = 0
            for sd in S: s_ = flow(sd, N, sp, 64, d, BIG)[0]; a += s_["adds"]; l += s_["lvl"]
            row.append(f"{l / a * 100:11.2f}%")
        print(f"  {d:3d} | " + " ".join(row))
    print("  levels in use on the fullest side (unlimited D): " + "; ".join(f"spread {sp}: mean {prof[sp][0]:.1f}, p99 {prof[sp][1]}, max {prof[sp][2]}" for sp in (4, 8, 16)))
    print("  (derived: each side can rest at `spread` distinct prices below or above the mid, so `spread` levels if the mid never moved; the mid drifts and orders left behind keep their levels, so the fullest side needs more)")
    print(f"\n== 2. the order table: ADDs rejected for FULL against NO; D unlimited; spread 8; target 64 live orders (the occupancy this flow reaches with an unlimited table is printed first: the control target is not the mean)")
    occ = []
    for sd in S: occ += flow(sd, N, 8, 64, BIG, BIG)[1]
    print(f"  occupancy with an unlimited table: mean {st.mean(occ):.1f}, p99 {pct(occ, .99)}, p99.9 {pct(occ, .999)}, max {max(occ)}")
    print(f"  {'NO':>4s} | {'ADDs rejected (FULL)':>21s}")
    for no in (32, 48, 64, 80, 96, 128, 192):
        a = f = 0
        for sd in S: s_ = flow(sd, N, 8, 64, BIG, no)[0]; a += s_["adds"]; f += s_["full"]
        print(f"  {no:4d} | {f / a * 100:20.2f}%")
    print("\n== 3. both finite: D = 8, NO = 64 and the targets of live orders 32, 64, 96 (spread 8)")
    print(f"  {'target':>6s} | {'ADDs':>7s} {'LVL':>6s} {'FULL':>6s} {'rejected':>9s}")
    for tg in (32, 64, 96):
        a = l = f = 0
        for sd in S: s_ = flow(sd, N, 8, tg, 8, 64)[0]; a += s_["adds"]; l += s_["lvl"]; f += s_["full"]
        print(f"  {tg:6d} | {a:7d} {l:6d} {f:6d} {(l + f) / a * 100:8.2f}%")
