#!/usr/bin/env python3
"""Chapter 20: the specification of the RAM-based order book. The FUNCTION is Chapter 19's (same events, same results, same top of book), with ONE change that the hardware forces and the model must state: the order table is a HASH TABLE of NB buckets of K ways, so an ADD is rejected with FULL when ITS BUCKET holds K orders, whatever the occupancy of the rest of the table. The hash is part of the contract: h(ref) = (ref ^ ref>>8 ^ ref>>16 ^ ref>>24) mod NB (NB a power of two).
The TIME is no longer one event per cycle: the order table and the price levels are RAMs read one entry per cycle, so an event takes a number of cycles that depends on the book's state. n(event) = cycles from the cycle it is accepted to the cycle the engine accepts the next one (the result is visible in that same cycle):
  ADD with 0 shares ........................ 1
  lookup (every other event) ............... K + 3   (accept 1, K + 1 reads of the bucket, 1 decision); the events that end at the decision (UNK, ZERO, OVER, DUPREF, FULL) cost exactly this
  then the price level is searched from the best price down: p + 2 cycles, where p is the number of strictly better levels (the level's index, or the index at which a new one goes); an ADD that needs a new level when all D are in use ends here (LVL)
  then ADD to an existing level or a reduction that leaves shares at the level: 1 (write the level) + 1 (write the order)
  ADD of a new level at index p with c levels on the side: (c - p + 1 if c > p else 0) (shift the worse levels down) + 1 (write the level) + 1 (write the order)
  reduction that empties the level at index p of c levels: (c - p if c - p > 1 else 0) (shift the worse levels up) + 1 (write the order)
  REPLACE: the deletion (lookup + level search + level update + order write) and then the ADD of the new order WITHOUT the accept cycle (or, if the new shares are 0, ZERO at once).
After reset the order RAM is cleared, one entry per cycle: the engine is not ready for NB * K cycles.
Results, order of checks, symbol reported and the top of book are Chapter 19's; see model/book_gold.py."""
import os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from book_gold import M, ADD, EXEC, CANCEL, DELETE, REPLACE, TN, OK, UNK, FULL, LVL, OVER, DUPREF, ZERO, RN, write_stim, expected_rows
def h(ref, nb): return (ref ^ (ref >> 8) ^ (ref >> 16) ^ (ref >> 24)) & (nb - 1)
def better(side, a, b): return a > b if side == 0 else a < b          # a is a better price than b on this side (bid: higher)
class Book2:
    def __init__(self, ns=2, d=4, nb=4, k=2):
        assert nb & (nb - 1) == 0
        self.ns, self.d, self.nb, self.k = ns, d, nb, k; self.orders = {}; self.lv = [[{}, {}] for _ in range(ns)]
    def top(self, sym):
        b, a = self.lv[sym]; bp = max(b) if b else 0; ap = min(a) if a else 0
        return (bp, b.get(bp, 0), ap, a.get(ap, 0), len(b), len(a), len(self.orders))
    def pos(self, sym, side, px): return sum(1 for q in self.lv[sym][side] if better(side, q, px))
    def _bucket_full(self, ref): return sum(1 for r in self.orders if h(r, self.nb) == h(ref, self.nb)) >= self.k
    def _add(self, ref, sym, side, px, sh):
        """-> (result, cycles after the accept cycle, 0 when sh = 0 and the event ends here)"""
        if sh == 0: return ZERO, 0
        c = self.k + 2
        if ref in self.orders: return DUPREF, c
        if self._bucket_full(ref): return FULL, c
        L = self.lv[sym][side]; p = self.pos(sym, side, px); c += p + 2
        if px in L: c += 2
        else:
            if len(L) >= self.d: return LVL, c
            n = len(L); c += (n - p + 1 if n > p else 0) + 2
        self.orders[ref] = [sym, side, px, sh]; L[px] = (L.get(px, 0) + sh) & M; return OK, c
    def _take(self, ref, sh):
        """reduce the order; -> cycles of the level and order updates (after the lookup)"""
        sym, side, px, osh = self.orders[ref]; L = self.lv[sym][side]; p = self.pos(sym, side, px); n = len(L); c = p + 2
        L[px] = (L[px] - sh) & M
        if L[px] == 0: del L[px]; c += (n - 1 - p + 1 if n - 1 - p > 0 else 0) + 1
        else: c += 2
        if sh == osh: del self.orders[ref]
        else: self.orders[ref][3] = osh - sh
        return c
    def event(self, e):
        """-> (cycles, result, sym). e: dict(t, ref, ref2, sym, side, px, sh)."""
        t = e["t"]; ref = e["ref"] & M; lk = self.k + 2
        if t == ADD:
            r, c = self._add(ref, e["sym"], e["side"], e["px"] & M, e["sh"] & M); return (1 if c == 0 else 1 + c), r, e["sym"]
        if ref not in self.orders: return 1 + lk, UNK, 0
        sym, side, px, osh = self.orders[ref]
        if t in (EXEC, CANCEL):
            sh = e["sh"] & M
            if sh == 0: return 1 + lk, ZERO, sym
            if sh > osh: return 1 + lk, OVER, sym
            return 1 + lk + self._take(ref, sh), OK, sym
        c = lk + self._take(ref, osh)
        if t == DELETE: return 1 + c, OK, sym
        r, c2 = self._add(e["ref2"] & M, sym, side, e["px"] & M, e["sh"] & M); return 1 + c + c2, r, sym                    # REPLACE
def run(events, ns=2, d=4, nb=4, k=2, gaps=None):
    """Closed loop: the i-th event is offered no earlier than cycle sum(gaps[:i + 1]), held on the pins until accepted; the engine is busy for NB * K cycles after reset (clearing the order RAM) and for n cycles after each event. -> dict(rows, lines, book, cycles, busy) with rows[c] = (ready, result visible this cycle or None), busy = the cycles each event took."""
    b = Book2(ns, d, nb, k); n = len(events); arr = []; t = 0
    for i in range(n): t += (gaps[i] if gaps else 0); arr.append(t)
    qi = 0; t = 0; busy_until = nb * k; pend = None; rows = []; lines = []; took = []
    while qi < n or pend or t < busy_until + 2:
        offered = events[qi] if qi < n and arr[qi] <= t else None
        ready = t >= busy_until; res_now = pend[0] if pend and pend[1] == t else None
        if res_now is not None: res_now = (res_now[1], res_now[2]) + pend[2]
        rows.append((1 if ready else 0, res_now)); lines.append(offered)
        if pend and pend[1] == t: pend = None
        if offered is not None and ready:
            cy, r, s = b.event(offered); busy_until = t + cy; pend = ((None, r, s), t + cy, b.top(s)); qi += 1; took.append((offered["t"], r, cy))
        t += 1
        if t > 100 * (n + 4) * (nb * k + 40) + sum(gaps or [0]) + 100: break
    return dict(rows=rows, lines=lines, book=b, cycles=t, took=took)
def worst_case(d, k):
    """The longest event the rules allow (a REPLACE), by enumeration of the structural cases rather than by search: the old order sits at index p1 of a side with n1 levels and its level empties (shifting n1 - 1 - p1 levels up) or does not; the new order then goes to the same side, now n2 levels, hitting an existing level, inserting a new level at index p2 (shifting n2 - p2 levels down) or, with the side full, being refused at the end of the search."""
    lk = k + 2; best = 0
    for n1 in range(1, d + 1):
        for p1 in range(n1):
            for emptied in (True, False):
                a = 1 + lk + (p1 + 2) + (((n1 - 1 - p1 + 1) if n1 - 1 - p1 > 0 else 0) + 1 if emptied else 2); n2 = n1 - 1 if emptied else n1
                for p2 in range(n2 + 1):
                    if p2 < n2: best = max(best, a + lk + p2 + 2 + 2)                                           # hits the level at p2
                    if n2 < d: best = max(best, a + lk + p2 + 2 + ((n2 - p2 + 1) if n2 > p2 else 0) + 2)        # inserts a level at p2
                    elif p2 == n2: best = max(best, a + lk + p2 + 2)                                              # all D in use and a worse price: LVL
    return best
def gen_events(rng, n, ns=2, d=4, nb=4, k=2, mid=1000, spread=6, faults=0.08, sh_max=300, p_add=0.40, p_red=0.20, p_del=0.18, collide=0.4):
    """Flow with faults, as in Chapter 19 (the oracle book runs alongside so that most events name live orders), with references chosen so that buckets fill: with probability `collide` a new reference is a multiple of NB (all in one bucket for small numbers)."""
    book = Book2(ns, d, nb, k); out = []; nxt = 1
    def newref():
        nonlocal nxt
        nxt += 1; return nxt * nb if rng.random() < collide else nxt
    for _ in range(n):
        live = list(book.orders); r = rng.random(); mid += rng.choice([0, 0, 0, 1, -1])
        def px(side): return mid + (rng.randint(0, spread) if side else -rng.randint(0, spread))
        if not live or r < p_add:
            side = rng.randrange(2); e = dict(t=ADD, ref=newref(), sym=rng.randrange(ns), side=side, px=px(side), sh=rng.randint(1, sh_max))
            if rng.random() < faults / 2: e["ref"] = rng.choice(live) if live else 99999
            if rng.random() < faults / 2: e["sh"] = 0
        else:
            ref = rng.choice(live); o = book.orders[ref]
            if r < p_add + p_red: e = dict(t=rng.choice([EXEC, CANCEL]), ref=ref, sh=rng.randint(1, o[3]) if rng.random() < .6 else rng.randint(1, max(1, o[3] - 1)))
            elif r < p_add + p_red + p_del: e = dict(t=DELETE, ref=ref)
            else: e = dict(t=REPLACE, ref=ref, ref2=newref(), px=px(o[1]), sh=rng.randint(1, sh_max))
            if rng.random() < faults / 2: e["ref"] = 777777 + rng.randrange(5)
            elif rng.random() < faults and e["t"] in (EXEC, CANCEL): e["sh"] = o[3] + rng.randint(1, 5)
            elif rng.random() < faults / 2 and e["t"] in (EXEC, CANCEL): e["sh"] = 0
            elif rng.random() < faults / 2 and e["t"] == REPLACE and len(live) > 1: e["ref2"] = rng.choice(live)
        out.append(e); book.event(e)
    return out
if __name__ == "__main__":
    b = Book2(2, 3, 4, 2)                                                    # buckets: h(ref) = ref & 3 for small refs
    assert b.event(dict(t=ADD, ref=4, sym=0, side=0, px=100, sh=50)) == (5 + 2 + 2, OK, 0)       # K + 3 = 5 (accept and lookup), level search at p = 0: 2, new level with nothing to shift: write level, write order: 2
    assert b.top(0) == (100, 50, 0, 0, 1, 0, 1)
    assert b.event(dict(t=ADD, ref=8, sym=0, side=0, px=100, sh=25)) == (5 + 2 + 2, OK, 0)       # the same price: an existing level, write level, write order
    n, r, s = b.event(dict(t=ADD, ref=12, sym=0, side=0, px=100, sh=1)); assert r == FULL and n == 5 and b.top(0)[:2] == (100, 75), (n, r)     # refs 4, 8, 12 share bucket 0 (K = 2): FULL with the table nearly empty
    assert b.event(dict(t=ADD, ref=5, sym=0, side=0, px=101, sh=10)) == (5 + 2 + (1 - 0 + 1) + 2, OK, 0)  # a better bid: search ends at index 0 (2 cycles), one level to shift down (2), write, write
    assert b.top(0)[:2] == (101, 10) and b.top(0)[4] == 2
    assert b.event(dict(t=ADD, ref=6, sym=0, side=0, px=90, sh=1)) == (5 + (2 + 2) + 0 + 2, OK, 0)          # the worst bid: index 2 = the end of 2 levels: search 4 cycles, nothing to shift
    assert b.event(dict(t=ADD, ref=7, sym=0, side=0, px=80, sh=1)) == (5 + (3 + 2), LVL, 0)                 # 3 levels in use, D = 3: the search ends at index 3 and the add is refused
    assert b.event(dict(t=EXEC, ref=5, sh=10)) == (5 + (0 + 2) + (3 - 1 - 0 + 1) + 1, OK, 0)                # the level at index 0 empties: 2 levels move up (3), write order
    assert b.top(0)[:2] == (100, 75) and b.top(0)[4] == 2
    assert b.event(dict(t=CANCEL, ref=4, sh=20)) == (5 + (0 + 2) + 2, OK, 0) and b.top(0)[:2] == (100, 55)   # partial: level write, order write
    assert b.event(dict(t=ADD, ref=9, sym=1, side=1, px=7, sh=0)) == (1, ZERO, 1)                            # zero shares: no lookup at all
    assert b.event(dict(t=DELETE, ref=77)) == (5, UNK, 0) and b.event(dict(t=EXEC, ref=4, sh=0)) == (5, ZERO, 0) and b.event(dict(t=EXEC, ref=4, sh=999)) == (5, OVER, 0)
    assert b.event(dict(t=ADD, ref=4, sym=0, side=1, px=105, sh=5)) == (5, DUPREF, 0)                         # a duplicate costs the lookup only
    c = Book2(1, 2, 2, 1); c.event(dict(t=ADD, ref=1, sym=0, side=0, px=10, sh=5))
    assert c.event(dict(t=REPLACE, ref=1, ref2=3, px=11, sh=7)) == ((1 + 3) + (0 + 2) + 1 + (3 + 2 + 2), OK, 0)    # K = 1: delete = accept + lookup 3 + search 2 + (level empties, nothing to shift) 0 + write order 1; add = lookup 3 + search 2 + 2
    c = Book2(1, 2, 2, 1); c.event(dict(t=ADD, ref=1, sym=0, side=0, px=10, sh=5)); c.event(dict(t=ADD, ref=2, sym=0, side=0, px=11, sh=5))
    assert c.event(dict(t=REPLACE, ref=1, ref2=3, px=12, sh=7)) == ((1 + 3) + (1 + 2) + 0 + 1 + (3 + 2 + 2 + 2), OK, 0)   # the old order is at index 1 (search 3); the new price is the best of one level (search 2, shift 2, write, write)
    assert c.event(dict(t=REPLACE, ref=2, ref2=5, px=1, sh=0)) == (1 + 3 + (1 + 2) + 1 + 0, ZERO, 0) and c.top(0)[6] == 1 and 2 not in c.orders   # zero new shares: the old order is gone, no lookup of the new one
    assert h(4, 4) == 0 and h(0x104, 4) == 1 and h(0x10004, 4) == 1 and h(0x1000004, 4) == 1 and h(0x101, 4) == 0                   # (ref ^ ref>>8 ^ ref>>16 ^ ref>>24) & 3, worked by hand: 0x104 ^ 0x1 = 0x105; 0x101 ^ 0x1 = 0x100
    for r in (0x104, 0x10004, 0x1000004):                                                                                          # with NB = 4, K = 1: 4 and r are in different buckets only because a higher byte is in the hash
        h4 = Book2(1, 2, 4, 1); h4.event(dict(t=ADD, ref=4, sym=0, side=0, px=50, sh=1)); assert h4.event(dict(t=ADD, ref=r, sym=0, side=0, px=50, sh=1))[1] == OK, r
    assert h4.event(dict(t=ADD, ref=0x101, sym=0, side=0, px=50, sh=1))[1] == FULL                                                  # bucket 0 holds ref 4
    s2 = Book2(2, 2, 2, 1); s2.event(dict(t=ADD, ref=2, sym=1, side=0, px=5, sh=1)); assert h(2, 2) == 0 and s2.event(dict(t=ADD, ref=4, sym=0, side=0, px=5, sh=1))[1] == FULL   # a bucket is full whatever the symbols
    assert worst_case(2, 2) == 20 and worst_case(1, 1) == 15               # D = 2, K = 2: REPLACE of the order at the best of 2 levels (accept 1 + lookup 4 + search 2 + shift 1 level up 2 + write 1 = 10) by a new best price on the 1 remaining level (lookup 4 + search 2 + shift 2 + write level and order 2 = 10)
    r = run([dict(t=ADD, ref=1, sym=0, side=0, px=5, sh=1), dict(t=ADD, ref=2, sym=0, side=0, px=5, sh=0)], 1, 2, 2, 2)                                  # after reset the order RAM is cleared for NB * K = 4 cycles
    assert [x[0] for x in r["rows"][:5]] == [0, 0, 0, 0, 1] and r["took"] == [(ADD, OK, 9), (ADD, ZERO, 1)]                                        # the first event is accepted in cycle 4 and takes 9: ready again in cycle 13 with its result; the second takes 1
    assert [x[0] for x in r["rows"][4:15]] == [1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1] and r["rows"][13][1][:2] == (OK, 0) and r["rows"][14][1][:2] == (ZERO, 0)
    print("book2_gold hand-checked scenarios passed")
