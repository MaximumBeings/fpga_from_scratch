#!/usr/bin/env python3
"""Chapter 20, example B (model level): what the hash table and the RAM levels cost in rejected orders and in time. The stationary flow of Chapter 19 (an ADD with a probability that pulls the number of live orders towards a TARGET, else an event on a uniformly chosen live order: 50% DELETE, 25% EXEC or CANCEL of a random part, 25% REPLACE at a new price; prices within `spread` ticks of a mid that moves one tick in 40% of the events; 2 symbols; no faults), run against the cycle model book2_gold.Book2. 20,000 events, 5 seeds.
(1) FULL: the share of ADDs refused because THEIR BUCKET is full, for a table of 128 orders arranged as NB x K (128 x 1, 64 x 2, 32 x 4, 16 x 8), at a target of 64 live orders (load 0.5) and 96 (load 0.75), for three kinds of reference: sequential (ITCH-like), random, and 'strided' (every reference a multiple of 64: the worst case for a hash that takes the low bits).
(2) TIME: cycles per event against D (spread 8, a table that does not limit, 32 x 4): mean, p99 and maximum, per event type, with the closed-form worst case.
(3) THROUGHPUT: events per cycle (mean cycles per event, in a stream that never waits for the engine) and the rate at the clock of Chapter 20's example A is left to the page."""
import os, random, statistics as st, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import book2_gold as G
def flow(seed, n, spread, target, d, nb, k, refs="seq", ns=2):
    rng = random.Random(seed); b = G.Book2(ns, d, nb, k); mid = 1000; cnt = 0; stats = dict(adds=0, lvl=0, full=0); cyc = {}; occ = []
    def newref():
        nonlocal cnt
        cnt += 1
        return {"seq": cnt, "random": rng.getrandbits(32) | 1, "strided": cnt * 64}[refs]
    for _ in range(n):
        if rng.random() < .4: mid += rng.choice([1, -1, 0])
        N = len(b.orders); live = list(b.orders); p_add = max(0.05, min(0.95, 0.5 + 0.45 * (target - N) / target))
        def px(side): return mid + (rng.randint(1, spread) if side else -rng.randint(1, spread))
        if not live or rng.random() < p_add:
            side = rng.randrange(2); e = dict(t=G.ADD, ref=newref(), sym=rng.randrange(ns), side=side, px=px(side), sh=rng.randint(1, 300))
        else:
            ref = rng.choice(live); o = b.orders[ref]; r = rng.random()
            if r < 0.5: e = dict(t=G.DELETE, ref=ref)
            elif r < 0.75: e = dict(t=rng.choice([G.EXEC, G.CANCEL]), ref=ref, sh=rng.randint(1, o[3]))
            else: e = dict(t=G.REPLACE, ref=ref, ref2=newref(), px=px(o[1]), sh=rng.randint(1, 300))
        c, res, s = b.event(e)
        if e["t"] == G.ADD: stats["adds"] += 1; stats["lvl"] += res == G.LVL; stats["full"] += res == G.FULL
        cyc.setdefault(G.TN[e["t"]], []).append(c); occ.append(len(b.orders))
    return stats, cyc, occ
def pct(xs, q): xs = sorted(xs); return xs[min(len(xs) - 1, int(q * len(xs)))]
if __name__ == "__main__":
    N = 20000; S = range(5)
    print(f"== 1. ADDs refused because the bucket is full (FULL); table of 128 orders as NB x K; D unlimited; spread 8; {len(S)} seeds x {N:,} events")
    print(f"  {'NB x K':>8s} | " + " ".join(f"{r + ' ' + str(t):>14s}" for r in ("seq", "random", "strided") for t in (64, 96)))
    for nb, k in ((128, 1), (64, 2), (32, 4), (16, 8)):
        row = []
        for refs in ("seq", "random", "strided"):
            for t in (64, 96):
                a = f = 0
                for sd in S: s_ = flow(sd, N, 8, t, 10 ** 6, nb, k, refs)[0]; a += s_["adds"]; f += s_["full"]
                row.append(f"{f / a * 100:13.2f}%")
        print(f"  {nb:4d} x {k:<2d} | " + " ".join(row))
    for t in (64, 96):
        oc = []
        for sd in S: oc += flow(sd, N, 8, t, 10 ** 6, 1 << 16, 1)[2]
        print(f"  (for scale: with no limit the number of live orders at a target of {t} has mean {st.mean(oc):.1f}, p99 {pct(oc, .99)}, maximum {max(oc)})")
    print(f"\n== 2. cycles per event against D (spread 8, 32 x 4 table, target 64, sequential references): mean / p99 / maximum over {len(S)} seeds x {N:,} events")
    print(f"  {'D':>3s} | " + " ".join(f"{t:>16s}" for t in ("ADD", "EXEC+CANCEL", "DELETE", "REPLACE")) + f" | {'all events: mean':>16s} {'closed-form worst':>18s}")
    for d in (4, 8, 16, 24, 32):
        cy = {}
        for sd in S:
            for t, v in flow(sd, N, 8, 64, d, 32, 4)[1].items(): cy.setdefault(t, []).extend(v)
        cy["EXEC+CANCEL"] = cy.get("EXEC", []) + cy.get("CANCEL", []); allc = [c for t in ("ADD", "EXEC", "CANCEL", "DELETE", "REPLACE") for c in cy.get(t, [])]
        f = lambda v: f"{st.mean(v):5.1f}/{pct(v, .99):3d}/{max(v):3d}"
        print(f"  {d:3d} | " + " ".join(f"{f(cy[t]):>16s}" for t in ("ADD", "EXEC+CANCEL", "DELETE", "REPLACE")) + f" | {st.mean(allc):16.2f} {G.worst_case(d, 4):18d}")
    print(f"\n== 3. cycles per event against K (D 16, 128 orders as NB x K, same flow): the lookup reads K ways and costs K + 3 cycles whatever is found")
    for nb, k in ((128, 1), (64, 2), (32, 4), (16, 8)):
        cy = []
        for sd in S:
            for v in flow(sd, N, 8, 64, 16, nb, k)[1].values(): cy.extend(v)
        print(f"  {nb:4d} x {k:<2d} | mean {st.mean(cy):6.2f} cycles per event, p99 {pct(cy, .99)}, maximum {max(cy)}")
