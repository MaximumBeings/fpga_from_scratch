#!/usr/bin/env python3
"""Chapter 23, example B (model level): what the limits do to a stream of orders, and how fast the kill switch bites. A strategy-like stream on one account and one symbol, run through the specification's gate (model/risk_gold.py) cycle by cycle: in each cycle a release that is due goes first, otherwise with probability 0.5 an order of 1 to 10 shares on a random side at a price within 3 ticks of 100; each accepted order is, after 1 to 20 cycles, filled in full (80%) or cancelled in part or in full (20%): positions drift as in a market maker that does not hedge. 200,000 cycles, one seed per row. (1) REJECTIONS against the position limit: max_long = max_short from 10 to 200, no rate limit: the share of orders refused for POS and the largest position and worst-case exposure reached, against the limit. (2) REJECTIONS against the rate limit: a bucket of 1 to 8 tokens and a refill period R of 2 to 16 cycles: the share refused for RATE. (3) THE KILL SWITCH: kill raised for 50 cycles at random times: the orders offered in the cycle kill rose or later that were accepted (the specification says none), and those offered in the cycle before (already in the pipeline: not stopped)."""
import os, random, statistics as st, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import risk_gold as G
def play(seed, n, lim, r, cap, kills=False):
    rng = random.Random(seed); big = 10 ** 9
    g = G.Gate(1, 1, r); g.cfg[0] = dict(maxlong=lim, maxshort=lim, maxqty=10, maxonot=big, maxnot=big, cap=cap); g.tokens[0] = cap; g.band[0] = (90, 110); g.armed = 1
    due = []; res = {k: 0 for k in G.RN}; orders = 0; maxpos = 0; maxexp = 0; kill_until = -1; acc_after = acc_before = 0; kill_starts = set(); pending = None
    for c in range(n):
        kill = 0
        if kills and c > kill_until and rng.random() < 0.002: kill_until = c + 50; kill_starts.add(c)
        if c <= kill_until: kill = 1
        ev = None
        ready = [x for x in due if x[0] <= c]
        if ready:
            due.remove(min(ready, key=lambda x: x[0])); ev = min(ready, key=lambda x: x[0])[1]
        elif rng.random() < 0.5:
            ev = (G.ORDER, 0, 0, rng.randrange(2), 100 + rng.randint(-3, 3), rng.randint(1, 10))
        if pending is not None:                                                                   # the event offered in the previous cycle is checked now, with the kill of its own cycle
            e, k, off = pending; kind, r_, st_, took = g.event(e, k)
            if kind == G.ORDER:
                orders += 1; res[G.RN[r_]] += 1
                if r_ == G.OK:
                    q = e[5]; side = e[3]
                    if rng.random() < 0.8: due.append((c + rng.randint(1, 20), (G.FILL, 0, 0, side, e[4], q)))
                    else:
                        part = rng.randint(1, q); due.append((c + rng.randint(1, 20), (G.CANCEL, 0, 0, side, e[4], part)))
                        if part < q: due.append((c + rng.randint(21, 40), (G.FILL, 0, 0, side, e[4], q - part)))
                    if any(off >= s for s in kill_starts) and any(s <= off < s + 51 for s in kill_starts): acc_after += 1
                    elif any(off == s - 1 for s in kill_starts): acc_before += 1
            pos, ob, os_, _, _ = g.touched(0, 0); maxpos = max(maxpos, abs(pos)); maxexp = max(maxexp, pos + ob, -(pos - os_))
        pending = (ev, kill, c) if ev else None
        if c % r == r - 1 and g.tokens[0] < g.cfg[0]["cap"]: g.tokens[0] += 1
    return res, orders, maxpos, maxexp, acc_after, acc_before, len(kill_starts)
if __name__ == "__main__":
    N = 200000
    print(f"== 1. the position limit (no rate limit: bucket 1000, refill every cycle): {N:,} cycles")
    print(f"  {'limit':>6s} | {'orders':>7s} {'refused: POS':>13s} {'other':>6s} | {'largest |pos|':>13s} {'largest exposure':>17s}")
    for lim in (10, 20, 40, 80, 160, 200):
        res, orders, mp, me, *_ = play(1, N, lim, 2, 1000); other = sum(v for k, v in res.items() if k not in ("OK", "POS"))
        print(f"  {lim:6d} | {orders:7d} {res['POS'] / orders * 100:12.1f}% {other / orders * 100:5.1f}% | {mp:13d} {me:17d}")
    print(f"\n== 2. the rate limit (position limit 1000): share of orders refused for RATE, by bucket size and refill period R (one token per R cycles; orders arrive at about 0.5 per cycle, 0.3 per cycle after the releases)")
    print(f"  {'bucket':>6s} | " + " ".join(f"{'R = ' + str(r):>9s}" for r in (2, 4, 8, 16)))
    for cap in (1, 2, 4, 8):
        row = []
        for r in (2, 4, 8, 16):
            res, orders, *_ = play(2, N, 1000, r, cap); row.append(f"{res['RATE'] / orders * 100:8.1f}%")
        print(f"  {cap:6d} | " + " ".join(row))
    print(f"\n== 3. the kill switch: kill raised for 50 cycles at about 0.2% of the cycles; orders accepted that were offered in the cycle kill rose or later, and in the cycle before")
    res, orders, mp, me, after, before, ks = play(3, N, 1000, 2, 1000, kills=True)
    print(f"  {ks} kills, {orders} orders; accepted offered while kill was up: {after}; accepted offered in the cycle just before a kill rose: {before}; refused for KILL: {res['KILL']}")
