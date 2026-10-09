#!/usr/bin/env python3
"""Chapter 10, example B: how a hash table behaves. (1) Keys the control plane could not place, against the load, for one table of 512 slots and two tables of 256, on four key types (20 seeds each); with the derived value for one table and random keys. (2) The false-positive rate of a table that stores only KW bits of each key, against KW, with the derived value occupancy x 2^-KW per table. All numbers come from the control-plane model (model/match_gold.py), whose answers ch10_run.py shows equal to the RTL's. Usage: ch10_example_b.py"""
import os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import match_gold as g
def fail_rate(ch, aw, kind, load, seeds=20):
    n = int(load * ch * (1 << aw)); tot = 0
    for s in range(seeds):
        rng = random.Random(1000 * s + aw); hp = g.HashPlane(aw, ch); ks = g.keys_of(kind, rng, n); f = 0
        for k in ks: f += not hp.insert(k, 1)[1]
        tot += f / n
    return 100 * tot / seeds
def derived_one(m, n): return 100 * (1 - m * (1 - (1 - 1 / m) ** n) / n)
def rank(fn, aw, kw):
    """Rank over GF(2) of the hash restricted to key differences whose low kw bits are zero (the hashes are linear, so P(hash(d) = 0) = 2^-rank)."""
    rows = []
    for b in range(kw, 32):
        v = fn(1 << b, aw)
        for r in rows: v = min(v, v ^ r)
        if v: rows.append(v)
    return len(rows)
def fp_rate(kw, kind, load=0.8, aw=8, ch=2, nq=400000):
    rng = random.Random(7 + kw); hp = g.HashPlane(aw, ch, kw); ks = g.keys_of(kind, rng, int(load * ch * (1 << aw)))
    for k in ks: hp.insert(k, 1)
    occ = [len(t) / (1 << aw) for t in hp.slot]; fp = 0; tested = 0; mem = set(hp.where); der2 = 0.0 if kw == 32 else occ[0] * 2.0 ** -kw + occ[1] * 2.0 ** -kw * 2 ** (aw - rank(g.h2, aw, kw))
    for _ in range(nq):
        q = rng.getrandbits(32)
        if q in mem: continue
        tested += 1; fp += hp.lookup(q)[0]
    return fp, tested, sum(occ), der2
if __name__ == "__main__":
    print("== 1. keys the control plane could not place (% of the keys offered), same 512 slots: one table of 512, or two tables of 256; mean of 20 seeds; each key may use one slot (one table) or one slot in each table (two tables)")
    print(f"  {'load':>5s} | {'1 x 512 random':>15s} {'derived':>8s} {'1 x 512 seq':>12s} {'1 x 512 mcast':>14s} {'1 x 512 stride':>15s} | {'2 x 256 random':>15s} {'2 x 256 seq':>12s} {'2 x 256 mcast':>14s} {'2 x 256 stride':>15s}")
    for load in (0.25, 0.5, 0.7, 0.8, 0.9, 0.95):
        r1 = [fail_rate(1, 9, k, load) for k in ("random", "seq", "mcast", "stride")]; r2 = [fail_rate(2, 8, k, load) for k in ("random", "seq", "mcast", "stride")]
        print(f"  {load * 100:4.0f}% | {r1[0]:14.1f}% {derived_one(512, int(load * 512)):7.1f}% {r1[1]:11.1f}% {r1[2]:13.1f}% {r1[3]:14.1f}% | {r2[0]:14.1f}% {r2[1]:11.1f}% {r2[2]:13.1f}% {r2[3]:14.1f}%")
    print("  derived (one table, random keys): n keys into m slots leave m(1 - (1 - 1/m)^n) slots occupied, so n minus that many keys find theirs taken.")
    print("\n== 2. false positives of a table that stores only the low KW bits of each key (two tables of 256, 80% full; 400,000 random keys that are not members)")
    print(f"  {'KW':>3s} | {'random keys: false hits':>24s} {'rate':>10s} {'derived':>10s} {'derived, hash 2 rank':>20s} | {'stride keys: false hits':>24s} {'rate':>10s}   rank of hash 1, hash 2")
    for kw in (8, 12, 16, 20, 32):
        fp, t, occ, d2 = fp_rate(kw, "random"); occ = 0.0 if kw == 32 else occ; fs, ts, _, _ = fp_rate(kw, "stride")
        print(f"  {kw:3d} | {fp:14d} of {t:7d} {fp / t:10.2e} {occ * 2.0 ** -kw:10.2e} {d2:20.2e} | {fs:14d} of {ts:7d} {fs / ts:10.2e}   {'(exact: no false positives)' if kw == 32 else str(rank(g.h1, 8, kw)) + ', ' + str(rank(g.h2, 8, kw))}")
    print("  derived = (occupancy of table 0 + occupancy of table 1) x 2^-KW: a probe finds an occupied slot with probability = occupancy, and the stored fingerprint then equals the key's with probability 2^-KW, IF the fingerprint bits are independent of the hash.")
    print("  derived, hash 2 rank: the second hash is linear in the key bits, and when the low KW bits of two keys agree the hash difference is a linear function of the remaining bits; if that map has rank r < 8 the two keys also collide in the second table with probability 2^-r, not 2^-8, so the table-1 term is multiplied by 2^(8 - r).")
