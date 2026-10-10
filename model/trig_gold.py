#!/usr/bin/env python3
"""Chapter 21: the specification of the trigger engine. A MESSAGE (type, key, side, price, shares) goes through a SYMBOL TABLE (key -> symbol index) and a set of RULES (predicates), and the answer is, for each message, which rules matched.
SYMBOL TABLE. NB buckets of K ways; a key lives in bucket h(key) = (key ^ key>>8 ^ key>>16 ^ key>>24) mod NB (NB a power of two), in any way. The table is WRITTEN by address (the control plane decides where: place() below does what software would do: the first free way of the key's bucket, or refuse when the bucket is full). A lookup finds the way whose valid bit is set and whose key equals the message's key and answers (found, symbol index); not found answers (0, 0).
RULES. R rules, each: en, neg, a mask over the 5 message types, symany or a mask over the NS symbol indexes (a message whose key is not in the table matches only a rule with symany), sideany or one side, and one comparison each on the price and on the shares: ANY, LT, LE, EQ, NE, GE, GT or NEVER (unsigned 32 bits) against a constant. inner = type ok and symbol ok and side ok and price ok and shares ok; the rule MATCHES when en and (inner xor neg). The answer for a message: mask (bit r = rule r matched), fire = any bit, first = the lowest matching rule (0 if none).
TIME. Everything is pipelined, one message per cycle, never stalled. A message offered in cycle a (when the engine is ready, that is, after the NB cycles that clear the table after reset) is answered in cycle a + L, L = 4 + PIPE (PIPE = 1: the 32-bit comparisons take two stages). The table as the message sees it: the writes made in cycles BEFORE a (a write in cycle w is seen by the lookups of cycles w + 1 on). The rules as the message sees them: the writes made in cycles up to a + 1 (a rule write in cycle c is seen by the messages offered from cycle c - 1: the comparison happens in cycle a + 2). Both are exact statements of the hardware, and the closed loop below applies them."""
import random
M = 0xFFFFFFFF
ADD, EXEC, CANCEL, DELETE, REPLACE = range(5)
TN = ["ADD", "EXEC", "CANCEL", "DELETE", "REPLACE"]
ANY, LT, LE, EQ, NE, GE, GT, NEVER = range(8)
ON = ["ANY", "LT", "LE", "EQ", "NE", "GE", "GT", "NEVER"]
def h(key, nb): return (key ^ (key >> 8) ^ (key >> 16) ^ (key >> 24)) & (nb - 1)
def cmp(op, x, c):
    return [True, x < c, x <= c, x == c, x != c, x >= c, x > c, False][op]
def new_rule(): return dict(en=0, neg=0, tmask=0, symany=0, symmask=0, sideany=0, side=0, pxop=ANY, pxval=0, shop=ANY, shval=0)
class Table:
    """The symbol table as the hardware holds it: NB x K entries (valid, key, index)."""
    def __init__(self, nb, k): self.nb, self.k = nb, k; self.e = [None] * (nb * k)
    def lookup(self, key):
        b = h(key, self.nb)
        for w in range(self.k):
            x = self.e[b * self.k + w]
            if x is not None and x[0] == key: return 1, x[1]
        return 0, 0
    def place(self, key):
        """What the control plane does to insert a key: the address of the first free way of its bucket, or None if the bucket is full (or the key is there already)."""
        b = h(key, self.nb)
        if any(self.e[b * self.k + w] is not None and self.e[b * self.k + w][0] == key for w in range(self.k)): return None
        for w in range(self.k):
            if self.e[b * self.k + w] is None: return b * self.k + w
        return None
    def write(self, addr, valid, key, idx): self.e[addr] = (key, idx) if valid else None
def evaluate(rules, msg, found, idx):
    """-> (mask, fire, first) for a message that the table gave (found, idx)."""
    mask = 0
    for r, u in enumerate(rules):
        inner = bool((u["tmask"] >> msg["t"]) & 1) and (u["symany"] or (found and (u["symmask"] >> idx) & 1)) and (u["sideany"] or msg["side"] == u["side"]) and cmp(u["pxop"], msg["px"], u["pxval"]) and cmp(u["shop"], msg["sh"], u["shval"])
        if u["en"] and (inner != bool(u["neg"])): mask |= 1 << r
    first = (mask & -mask).bit_length() - 1 if mask else 0
    return mask, 1 if mask else 0, first
def run(cycles, nb=8, k=2, nr=4, ns=16, pipe=0):
    """Closed loop. cycles[c] = dict(msg=..., cfg=(rule index, rule dict), ld=(addr, valid, key, idx)) with any of the three missing; cycle 0 is the first cycle after reset, in which the table is being cleared for NB cycles (nothing may be offered before cycle NB). -> dict(rows, table, rules) with rows[c] = (valid, found, idx, mask, fire, first) of the answer visible in cycle c."""
    assert all(not any(x in cy for x in ("msg", "cfg", "ld")) for cy in cycles[:nb]), "nothing may be offered while the table is being cleared"
    L = 4 + pipe; T = Table(nb, k); rules = [new_rule() for _ in range(nr)]; n = len(cycles) + L + 4; rows = [(0, 0, 0, 0, 0, 0)] * n; look = {}
    for c in range(n):
        cy = cycles[c] if c < len(cycles) else {}
        if c - 2 in look:                                                                        # the rules as of the start of cycle a + 2: the writes of cycles up to a + 1
            f, i, m = look.pop(c - 2); mask, fire, first = evaluate(rules, m, f, i); rows[c - 2 + L] = (1, f, i, mask, fire, first)
        if "msg" in cy: f, i = T.lookup(cy["msg"]["key"]); look[c] = (f, i, cy["msg"])           # the table as of the start of cycle a: the writes of cycles before a
        if "cfg" in cy: r, u = cy["cfg"]; rules[r] = dict(u)
        if "ld" in cy: a, v, key, i = cy["ld"]; T.write(a, v, key, i)
    return dict(rows=rows[:len(cycles) + L], table=T, rules=rules)
def expected_rows(res, nb): return [(c, 1 if c >= nb else 0) + r for c, r in enumerate(res["rows"])]       # (cycle, ready, valid, found, idx, mask, fire, first) as the testbench prints them
def write_stim(path, cycles, seed=1):
    """One line per cycle, the layout of tb/trig_tb.sv (bit offsets: msg 0..100, cfg 101..217, ld 218..268); fields not offered are junk."""
    rng = random.Random(seed)
    with open(path, "w") as f:
        for cy in cycles:
            m = cy.get("msg"); u = cy.get("cfg"); ld = cy.get("ld")
            v = 0
            mm = m or dict(t=rng.randrange(5), side=rng.randrange(2), key=rng.getrandbits(32), px=rng.getrandbits(32), sh=rng.getrandbits(32))
            v |= (1 if m else 0) | (mm["t"] << 1) | (mm["side"] << 4) | (mm["key"] << 5) | (mm["px"] << 37) | (mm["sh"] << 69)
            r, w = u if u else (rng.randrange(16), dict(en=rng.randrange(2), neg=rng.randrange(2), tmask=rng.randrange(32), symany=rng.randrange(2), symmask=rng.getrandbits(32), sideany=rng.randrange(2), side=rng.randrange(2), pxop=rng.randrange(8), pxval=rng.getrandbits(32), shop=rng.randrange(8), shval=rng.getrandbits(32)))
            v |= ((1 if u else 0) << 101) | (r << 102) | (w["en"] << 106) | (w["neg"] << 107) | (w["tmask"] << 108) | (w["symany"] << 113) | (w["sideany"] << 114) | (w["side"] << 115) | (w["pxop"] << 116) | (w["shop"] << 119) | (w["symmask"] << 122) | (w["pxval"] << 154) | (w["shval"] << 186)
            a, lv, lk, li = ld if ld else (rng.getrandbits(12), rng.randrange(2), rng.getrandbits(32), rng.getrandbits(5))
            v |= ((1 if ld else 0) << 218) | (a << 219) | (lk << 231) | (li << 263) | (lv << 268)
            f.write("%068x\n" % v)
    return len(cycles)
def gen_cycles(rng, n, nb=8, k=2, nr=4, ns=16, density=0.7, cfg_rate=0.05, ld_rate=0.06, key_space=40, wide=False, near=False):
    """Random traffic: after the NB empty cycles, messages (probability `density` per cycle) over a small space of keys, of which some are in the table; rule writes and table writes (insertions by place(), deletions, refused insertions are simply not issued) at random cycles, possibly the same cycle as a message, so the visibility rules are exercised. Prices and shares from small ranges so that the comparisons are close to their constants."""
    T = Table(nb, k); out = [dict() for _ in range(nb)]; keys = [(rng.getrandbits(32) if wide else rng.randint(0, 255 * 4)) for _ in range(key_space)]; idx_of = {}
    if near: base = rng.getrandbits(32); keys = [base ^ (1 << b) for b in range(32)] + [base] + [rng.getrandbits(32) for _ in range(7)]       # keys one bit apart: those whose bit only changes a high bit of the hash share a bucket
    def rand_rule():
        return dict(en=int(rng.random() < .85), neg=int(rng.random() < .2), tmask=rng.choice([31, 31, 1, 2, 6, 24, rng.randrange(32)]), symany=int(rng.random() < .3), symmask=rng.getrandbits(ns), sideany=int(rng.random() < .5), side=rng.randrange(2),
                    pxop=rng.randrange(8), pxval=rng.choice([0, 50, 100, 101, 0xFFFFFFFF, rng.getrandbits(7)]), shop=rng.randrange(8), shval=rng.choice([0, 1, 10, 100, 0x10000, 0xFFFF, rng.getrandbits(8)]))
    for _ in range(n):
        cy = {}
        if rng.random() < density:
            key = rng.choice(keys) if rng.random() < .85 else rng.getrandbits(32)
            cy["msg"] = dict(t=rng.randrange(5), side=rng.randrange(2), key=key, px=rng.choice([0, 49, 50, 51, 99, 100, 101, 0xFFFFFFFF, 0x10000, 0xFFFF, rng.getrandbits(7), rng.getrandbits(32)]), sh=rng.choice([0, 1, 9, 10, 11, 100, 0x10000, 0xFFFF, 0xFFFFFFFF, rng.getrandbits(8)]))
        if rng.random() < cfg_rate: cy["cfg"] = (rng.randrange(nr), rand_rule())
        if rng.random() < ld_rate:
            key = rng.choice(keys)
            if rng.random() < .3 and any(e is not None for e in T.e):
                a = rng.choice([i for i, e in enumerate(T.e) if e is not None]); ok, oi = T.e[a]; cy["ld"] = (a, 0, ok, oi); T.write(a, 0, 0, 0)    # a deletion: clears the valid bit, with the key and index of the entry (what software that keeps a copy of the table does)
            else:
                a = T.place(key)
                if a is not None: i = rng.randrange(ns); cy["ld"] = (a, 1, key, i); T.write(a, 1, key, i)
        out.append(cy)
    return out
EDGE = [0, 1, 2, 0x7FFF, 0x8000, 0xFFFF, 0x10000, 0x10001, 0x1FFFF, 0x7FFFFFFF, 0x80000000, 0xFFFF0000, 0xFFFFFFFE, 0xFFFFFFFF]
def edge_cycles(nb=8, ns=16):
    """Directed: for every comparison, every constant in EDGE (the 16-bit and 32-bit boundaries, which the two-stage comparison splits on) against every message value in EDGE, on the price (rule 0) and on the shares (rule 1); one rule write, then the messages one per cycle, a message every cycle."""
    out = [dict() for _ in range(nb)]; base = dict(en=1, neg=0, tmask=31, symany=1, symmask=0, sideany=1, side=0)
    for field in ("px", "sh"):
        for op in range(8):
            for c in EDGE:
                u = dict(new_rule(), **base); u["pxop" if field == "px" else "shop"] = op; u["pxval" if field == "px" else "shval"] = c
                out.append(dict(cfg=(0 if field == "px" else 1, u))); out += [dict(), dict(), dict()]
                for x in EDGE: out.append(dict(msg=dict(t=ADD, side=0, key=1, px=x if field == "px" else 0, sh=x if field == "sh" else 0)))
    return out
if __name__ == "__main__":
    assert [h(k, 4) for k in (0, 1, 4, 0x104, 0x10004, 0x1000004, 0x101)] == [0, 1, 0, 1, 1, 1, 0]                       # (key ^ key>>8 ^ key>>16 ^ key>>24) & 3, worked by hand
    assert [cmp(op, 5, 5) for op in range(8)] == [True, False, True, True, False, True, False, False] and [cmp(op, 4, 5) for op in range(8)] == [True, True, True, False, True, False, False, False] and [cmp(op, 0xFFFFFFFF, 5) for op in (LT, GT)] == [False, True]
    T = Table(2, 2); assert T.place(4) == 0 and (T.write(0, 1, 4, 7), T.place(6))[1] == 1 and (T.write(1, 1, 6, 9), T.place(8))[1] is None and T.place(4) is None   # bucket 0 holds keys 4 and 6 (2 ways): a third key is refused, and a key already there
    assert T.lookup(6) == (1, 9) and T.lookup(8) == (0, 0) and (T.write(0, 0, 0, 0), T.lookup(4))[1] == (0, 0) and T.place(8) == 0
    T2 = Table(2, 2); T2.write(0, 1, 4, 3); assert T2.place(4) is None and T2.place(6) == 1 and T2.place(5) == 2        # key 4 is there and its bucket has a free way: refused as a duplicate; another key of the same bucket takes the free way; a key of the other bucket takes its first way
    msg = dict(t=ADD, side=0, key=4, px=100, sh=10)
    r = new_rule(); r.update(en=1, tmask=0b00001, symany=1, sideany=1)                                                  # rule 0: every ADD
    q = new_rule(); q.update(en=1, tmask=0b11111, symmask=1 << 7, sideany=1, pxop=GT, pxval=99, shop=GE, shval=10)       # rule 1: symbol index 7, price above 99, shares at least 10
    n = new_rule(); n.update(en=1, neg=1, tmask=0b00001, symany=1, sideany=1)                                           # rule 2: everything but an ADD
    d = new_rule(); d.update(en=0, tmask=31, symany=1, sideany=1)                                                       # rule 3: disabled
    assert evaluate([r, q, n, d], msg, 1, 7) == (0b0011, 1, 0) and evaluate([r, q, n, d], msg, 1, 6) == (0b0001, 1, 0) and evaluate([r, q, n, d], msg, 0, 0) == (0b0001, 1, 0)   # an unknown key matches only symany rules
    z0 = new_rule(); z0.update(en=1, tmask=31, symmask=1, sideany=1)                                                   # symbol index 0 only, no symany: a message whose key is NOT in the table answers (found 0, index 0) and must not match
    assert evaluate([z0], msg, 0, 0) == (0, 0, 0) and evaluate([z0], msg, 1, 0) == (1, 1, 0)
    z1 = new_rule(); z1.update(en=0, neg=1, tmask=0, symany=1, sideany=1)                                               # disabled and negated, and the inner predicate false (so the negation is true): still never matches
    assert evaluate([z1], msg, 1, 7) == (0, 0, 0)
    z2 = new_rule(); z2.update(en=1, tmask=31, symany=1, sideany=0, side=1)                                             # only the ask side
    assert evaluate([z2], msg, 1, 7) == (0, 0, 0) and evaluate([z2], dict(msg, side=1), 1, 7) == (1, 1, 0)
    z3 = new_rule(); z3.update(en=1, tmask=0b00110, symany=1, sideany=1)                                                # only EXEC and CANCEL
    assert evaluate([z3], msg, 1, 7) == (0, 0, 0) and evaluate([z3], dict(msg, t=EXEC), 1, 7)[0] == 1 and evaluate([z3], dict(msg, t=CANCEL), 1, 7)[0] == 1 and evaluate([z3], dict(msg, t=DELETE), 1, 7)[0] == 0
    assert evaluate([r, q, n, d], dict(t=DELETE, side=1, key=4, px=100, sh=9), 1, 7) == (0b0100, 1, 2) and evaluate([r, q, n, d], dict(t=EXEC, side=0, key=4, px=99, sh=10), 1, 7) == (0b0100, 1, 2)   # the negated rule; price 99 is not above 99; shares 9 are not at least 10 (in the first)
    assert evaluate([r, q, n, d], dict(t=EXEC, side=0, key=4, px=100, sh=10), 1, 7) == (0b0110, 1, 1) and evaluate([q], dict(t=EXEC, side=0, key=4, px=100, sh=9), 1, 7) == (0, 0, 0)
    # timing: NB = 2, K = 1; a table write in cycle 2, then a message in cycle 2 (does not see it), in cycle 3 (sees it); a rule write in cycle 4, messages in cycle 3 and 4 (see it: a + 2 > 4... a >= 3) and in cycle 2 (does not)
    cyc = [dict(), dict(), dict(msg=dict(t=ADD, side=0, key=4, px=1, sh=1), ld=(0, 1, 4, 5)), dict(msg=dict(t=ADD, side=0, key=4, px=1, sh=1)), dict(cfg=(0, dict(en=1, neg=0, tmask=31, symany=0, symmask=1 << 5, sideany=1, side=0, pxop=ANY, pxval=0, shop=ANY, shval=0))), dict(), dict(), dict(), dict()]
    z = run(cyc, nb=2, k=1, nr=1, ns=16, pipe=0)["rows"]
    assert z[6] == (1, 0, 0, 0, 0, 0) and z[7] == (1, 1, 5, 1, 1, 0) and z[2] == (0, 0, 0, 0, 0, 0)                      # the message of cycle 2 (answered in 6): not found, rule 0 not yet; of cycle 3 (answered in 7): found (the write was in cycle 2), index 5, and it sees the rule written in cycle 4
    cyc2 = [dict(), dict(), dict(msg=dict(t=ADD, side=0, key=4, px=1, sh=1)), dict(msg=dict(t=ADD, side=0, key=4, px=1, sh=1), cfg=(0, dict(en=1, neg=0, tmask=31, symany=1, symmask=0, sideany=1, side=0, pxop=ANY, pxval=0, shop=ANY, shval=0))), dict(), dict(), dict(), dict(), dict()]
    y = run(cyc2, nb=2, k=1, nr=1, ns=16, pipe=0)["rows"]
    assert y[6][3] == 1 and y[7][3] == 1                                                                                  # a rule written in cycle 3 is seen by the message of cycle 2 (compared in cycle 4)
    cyc3 = [dict(), dict(), dict(msg=dict(t=ADD, side=0, key=4, px=1, sh=1)), dict(), dict(cfg=(0, dict(en=1, neg=0, tmask=31, symany=1, symmask=0, sideany=1, side=0, pxop=ANY, pxval=0, shop=ANY, shval=0))), dict(), dict(), dict(), dict()]
    assert run(cyc3, nb=2, k=1, nr=1, ns=16, pipe=0)["rows"][6][3] == 0 and run(cyc3, nb=2, k=1, nr=1, ns=16, pipe=1)["rows"][7] == (1, 0, 0, 0, 0, 0)       # written in cycle 4, the message of cycle 2 compares in cycle 4 and does not see it; PIPE 1 answers a cycle later
    assert [x[1] for x in expected_rows(run([dict()] * 6, nb=2, k=1, nr=1, ns=16, pipe=0), 2)[:4]] == [0, 0, 1, 1]            # not ready while the table is cleared (NB = 2 cycles)
    print("trig_gold hand-checked scenarios passed")
