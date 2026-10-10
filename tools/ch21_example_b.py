#!/usr/bin/env python3
"""Chapter 21, example B (model level): the symbol table and the rules on a workload. (1) PLACEMENT, for the engine's XOR-fold hash and for a multiplicative one (Exercise 1; model only): a table of 1,024 entries as NB x K (1,024 x 1, 512 x 2, 256 x 4, 128 x 8), keys inserted in random order by place() until the first refusal and, past it, the share of insertions refused at load 50%, 75% and 90%; for two kinds of keys: random 32-bit keys, and tickers (1 to 4 random capital letters, space padded, as 4 ASCII bytes: a stand-in for what a feed gives; the real ones are 8 bytes and not random). 20 shuffles each. (2) RULES: a set of eight rules on a synthetic message stream (200 symbols with a skewed popularity, 60 of them in the table's 'watch list' of the rules, a price that walks, sizes from a long-tailed distribution): the share of messages each rule matches and the share that fires at all."""
import os, random, statistics as st, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import trig_gold as G
def ticker(rng):
    n = rng.randint(1, 4); s = "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(n)).ljust(4); return int.from_bytes(s.encode(), "big")
def keys(kind, n, rng):
    out = set()
    while len(out) < n: out.add(rng.getrandbits(32) if kind == "random" else ticker(rng))
    return sorted(out)
def hmul(key, nb): return ((key * 0x9E3779B1) & G.M) >> (32 - (nb.bit_length() - 1))        # the multiplicative hash of Exercise 1: the top bits of key x 2^32/phi (NOT in the engine; here only to be measured)
def place_all(kind, nb, k, loads, seed, hf=G.h):
    rng = random.Random(seed); ks = keys(kind, int(1024 * max(loads) + 1), rng); rng.shuffle(ks); count = [0] * nb; first = None; refused = 0; res = {}
    for n, key in enumerate(ks):
        b = hf(key, nb)
        if count[b] >= k: refused += 1; first = first if first is not None else n
        else: count[b] += 1
        for L in loads:
            if n + 1 == int(1024 * L): res[L] = refused
    return first, res
def workload(n, seed):
    rng = random.Random(seed); syms = keys("random", 200, rng); watch = set(syms[:60]); pop = [1 / (i + 1) ** 0.9 for i in range(200)]; T = G.Table(128, 4); idx = {}
    for s in syms[:100]:
        a = T.place(s)
        if a is not None: T.write(a, 1, s, len(idx) % 32); idx[s] = len(idx) % 32
    rules = [G.new_rule() for _ in range(8)]
    def mk(i, **kw): rules[i].update(dict(en=1, tmask=31, symany=1, sideany=1), **kw)
    wl = sum(1 << idx[s] for s in watch if s in idx)
    mk(0, tmask=0b00001, pxop=G.GT, pxval=1020)                                                                    # 0: an ADD above 1020
    mk(1, tmask=0b00001, side=0, sideany=0, pxop=G.LT, pxval=980)                                                  # 1: a bid ADD below 980
    rules[2].update(en=1, tmask=0b00110, symany=0, symmask=wl, sideany=1, shop=G.GE, shval=500)                    # 2: an EXEC or CANCEL of 500 or more in the watch list
    rules[3].update(en=1, tmask=31, symany=0, symmask=wl, sideany=1)                                               # 3: anything in the watch list
    rules[4].update(en=1, neg=1, tmask=31, symany=0, symmask=(1 << 32) - 1, sideany=1)                             # 4: every symbol that is NOT in the table (neg of 'any index'; found = 0)
    mk(5, tmask=0b01000, shop=G.GT, shval=0)                                                                       # 5: every DELETE
    mk(6, shop=G.GE, shval=2000)                                                                                   # 6: any message of 2000 shares or more
    rules[7].update(en=1, neg=1, tmask=0b00001, symany=1, sideany=1)                                               # 7: everything that is not an ADD
    cnt = [0] * 8; fired = 0; px = 1000
    for _ in range(n):
        s = rng.choices(syms, pop)[0]; px += rng.choice([-1, 0, 0, 1]); sh = int(rng.paretovariate(1.2) * 20)
        f, i = T.lookup(s); mask, fire, first = G.evaluate(rules, dict(t=rng.choice([0, 0, 0, 1, 2, 3, 4]), side=rng.randrange(2), key=s, px=px + rng.randint(-30, 30), sh=sh), f, i)
        fired += fire
        for r in range(8): cnt[r] += (mask >> r) & 1
    return cnt, fired
if __name__ == "__main__":
    print("== 1. placement: a table of 1,024 entries as NB x K; inserted keys until the first refusal (mean of 20 shuffles, as a % of 1,024), and the share of the insertions up to each load that were refused")
    print(f"  {'keys':8s} {'hash':>7s} {'NB x K':>9s} | {'first refusal at':>16s} | {'refused by 50%':>14s} {'by 75%':>8s} {'by 90%':>8s}")
    for kind in ("random", "ticker"):
        for hn, hf in (("xor", G.h), ("mult", hmul)):
            for nb, k in ((1024, 1), (512, 2), (256, 4), (128, 8)):
                fs = []; r5 = []; r75 = []; r9 = []
                for sd in range(20):
                    f, r = place_all(kind, nb, k, (.5, .75, .9), sd, hf); fs.append(f / 1024 * 100); r5.append(r[.5] / 512 * 100); r75.append(r[.75] / 768 * 100); r9.append(r[.9] / 922 * 100)
                print(f"  {kind:8s} {hn:>7s} {nb:5d} x {k:<2d} | {st.mean(fs):15.1f}% | {st.mean(r5):13.2f}% {st.mean(r75):7.2f}% {st.mean(r9):7.2f}%")
    cnt, fired = workload(200000, 1)
    print("\n== 2. eight rules on 200,000 synthetic messages (200 symbols with skewed popularity, 100 in the table, 60 watched)")
    names = ["ADD above 1020", "bid ADD below 980", "EXEC/CANCEL >= 500 in the watch list", "anything in the watch list", "key not in the table", "every DELETE", "2000 shares or more", "everything but an ADD"]
    for r in range(8): print(f"  rule {r}: {names[r]:40s} {cnt[r] / 2000:6.2f}% of messages")
    print(f"  at least one rule fires: {fired / 2000:.2f}% of messages")
