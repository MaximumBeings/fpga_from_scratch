#!/usr/bin/env python3
"""Chapter 19: the specification of the order book, written with dictionaries and nothing else (no sorted array, no table of slots): it is what a book IS, so that the hardware's structures are tested against it. Cycle accounting at the end.
Events (ITCH-like, with 32-bit order references): ADD(ref, sym, side, px, sh), EXEC(ref, sh) and CANCEL(ref, sh) (reduce the order by sh), DELETE(ref), REPLACE(ref, ref2, px, sh) (the old order is deleted, a new order with reference ref2 and the same symbol and side is added; if the add fails the old order is gone all the same). side 0 = bid, 1 = ask.
Capacity (the only structural facts): the order table holds NO orders; each side of each symbol holds D price levels. Results: 0 OK; 1 UNK (reference not found); 2 FULL (order table full); 3 LVL (a new price level is needed and all D are in use); 4 OVER (reduce by more than the order has); 5 DUPREF (ADD or REPLACE with a reference that exists); 6 ZERO (zero shares). Checks are made in this order: ADD: ZERO, DUPREF, FULL, LVL; REDUCE: UNK, ZERO, OVER. A reduction that leaves 0 shares removes the order; a level whose shares reach 0 disappears. A failed event changes nothing (except the old order of a REPLACE, above).
After every event the result is reported with the symbol (the order's, or the input's for ADD, or 0 if the reference was not found) and the TOP OF BOOK of that symbol: best bid (price, shares), best ask (price, shares), the number of levels on each side and the number of orders in the table. Prices and shares are 32-bit; overflow of a level's shares (2^32) is outside the contract.
Cycles: one event per cycle, except that REPLACE takes two (delete the old order, then add the new): while the second runs, the input is not accepted. The result of an event is visible the cycle after its last phase."""
import random
M = 0xFFFFFFFF
ADD, EXEC, CANCEL, DELETE, REPLACE = range(5)
TN = ["ADD", "EXEC", "CANCEL", "DELETE", "REPLACE"]
OK, UNK, FULL, LVL, OVER, DUPREF, ZERO = range(7)
RN = ["OK", "UNK", "FULL", "LVL", "OVER", "DUPREF", "ZERO"]
class Book:
    def __init__(self, ns=2, d=4, no=8):
        self.ns, self.d, self.no = ns, d, no; self.orders = {}; self.lv = [[{}, {}] for _ in range(ns)]
    def top(self, sym):
        b, a = self.lv[sym]; bp = max(b) if b else 0; ap = min(a) if a else 0
        return (bp, b.get(bp, 0), ap, a.get(ap, 0), len(b), len(a), len(self.orders))
    def _add(self, ref, sym, side, px, sh):
        if sh == 0: return ZERO
        if ref in self.orders: return DUPREF
        if len(self.orders) >= self.no: return FULL
        L = self.lv[sym][side]
        if px not in L and len(L) >= self.d: return LVL
        self.orders[ref] = [sym, side, px, sh]; L[px] = (L.get(px, 0) + sh) & M; return OK
    def _reduce(self, ref, sh):
        if ref not in self.orders: return UNK, 0
        sym, side, px, osh = self.orders[ref]
        if sh == 0: return ZERO, sym
        if sh > osh: return OVER, sym
        self._take(ref, sh); return OK, sym
    def _take(self, ref, sh):
        sym, side, px, osh = self.orders[ref]; L = self.lv[sym][side]; L[px] = (L[px] - sh) & M
        if L[px] == 0: del L[px]
        if sh == osh: del self.orders[ref]
        else: self.orders[ref][3] = osh - sh
    def event(self, e):
        """-> (phases, result, sym). e: dict(t, ref, ref2, sym, side, px, sh)."""
        t = e["t"]; ref = e["ref"] & M
        if t == ADD: r = self._add(ref, e["sym"], e["side"], e["px"] & M, e["sh"] & M); return 1, r, e["sym"]
        if t in (EXEC, CANCEL): r, s = self._reduce(ref, e["sh"] & M); return 1, r, s
        if t == DELETE:
            if ref not in self.orders: return 1, UNK, 0
            s = self.orders[ref][0]; self._take(ref, self.orders[ref][3]); return 1, OK, s
        if ref not in self.orders: return 1, UNK, 0                                                                  # REPLACE
        sym, side, _, osh = self.orders[ref]; self._take(ref, osh); r = self._add(e["ref2"] & M, sym, side, e["px"] & M, e["sh"] & M); return 2, r, sym
def run(events, ns=2, d=4, no=8, gaps=None, split=False):
    """Closed loop: the events arrive in order, the i-th no earlier than cycle sum(gaps[:i + 1]); one is offered per cycle (the oldest not yet accepted) and accepted when the engine is idle. -> dict(rows, lines). rows[c] = (ready, result visible this cycle or None) with result = (res, sym, top...)."""
    b = Book(ns, d, no); n = len(events); arr = []; t = 0
    for i in range(n): t += (gaps[i] if gaps else 0); arr.append(t)
    qi = 0; t = 0; busy_until = 0; pend = None; rows = []; lines = []; per = 2 if split else 1
    while qi < n or pend or t < busy_until + 2:
        offered = events[qi] if qi < n and arr[qi] <= t else None
        ready = t >= busy_until; res_now = pend[0] if pend and pend[1] == t else None
        if res_now is not None: res_now = (res_now[1], res_now[2]) + b_top(pend[2], res_now[2])
        rows.append((1 if ready else 0, res_now)); lines.append(offered)
        if pend and pend[1] == t: pend = None
        if offered is not None and ready:
            ph, r, s = b.event(offered); ph *= per; busy_until = t + ph; pend = ((None, r, s), t + ph, b.top(s)); qi += 1
        t += 1
        if t > 10 * (n + 4) * (2 + 2 * per) + sum(gaps or [0]) + 100: break
    return dict(rows=rows, lines=lines, book=b, cycles=t)
def b_top(top, sym): return top
def write_stim(path, lines, seed=1):
    rng = random.Random(seed)
    with open(path, "w") as f:
        for e in lines:
            if e: f.write("%x%x%x%x%08x%08x%08x%08x\n" % (1, e["t"], e.get("sym", 0), e.get("side", 0), e.get("ref", 0) & M, e.get("ref2", 0) & M, e.get("px", 0) & M, e.get("sh", 0) & M))
            else: f.write("%x%x%x%x%08x%08x%08x%08x\n" % (0, rng.randrange(8), rng.randrange(2), rng.randrange(2), rng.getrandbits(32), rng.getrandbits(32), rng.getrandbits(32), rng.getrandbits(32)))
    return len(lines)
def expected_rows(res):
    """(cycle, ready, rv, result, sym, bpx, bsh, apx, ash, bn, an, nord) as the testbench prints them."""
    out = []
    for c, (ready, r) in enumerate(res["rows"]):
        if r is None: out.append((c, ready, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
        else: out.append((c, ready, 1, r[0], r[1]) + tuple(r[2:]))
    return out
def gen_events(rng, n, ns=2, d=4, no=8, mid=1000, spread=6, faults=0.08, sh_max=300, p_add=0.40, p_red=0.20, p_del=0.18):
    """Realistic flow with faults: the oracle book runs alongside so that EXEC/CANCEL/DELETE/REPLACE mostly name live orders, with partial and full reductions; faults (unknown and duplicate references, over-reductions, zero shares) at probability `faults`; prices within `spread` ticks of a drifting mid so that levels fill and empty."""
    book = Book(ns, d, no); out = []; nxt = 1
    for _ in range(n):
        live = list(book.orders); r = rng.random(); mid += rng.choice([0, 0, 0, 1, -1])
        def px(side): return mid + (rng.randint(0, spread) if side else -rng.randint(0, spread))
        if not live or r < p_add:
            side = rng.randrange(2); e = dict(t=ADD, ref=nxt, sym=rng.randrange(ns), side=side, px=px(side), sh=rng.randint(1, sh_max)); nxt += 1
            if rng.random() < faults / 2: e["ref"] = rng.choice(live) if live else 99999
            if rng.random() < faults / 2: e["sh"] = 0
        else:
            ref = rng.choice(live); o = book.orders[ref]
            if r < p_add + p_red: e = dict(t=rng.choice([EXEC, CANCEL]), ref=ref, sh=rng.randint(1, o[3]) if rng.random() < .6 else rng.randint(1, max(1, o[3] - 1)))
            elif r < p_add + p_red + p_del: e = dict(t=DELETE, ref=ref)
            else: e = dict(t=REPLACE, ref=ref, ref2=nxt, px=px(o[1]), sh=rng.randint(1, sh_max)); nxt += 1
            if rng.random() < faults / 2: e["ref"] = 777777 + rng.randrange(5)
            elif rng.random() < faults and e["t"] in (EXEC, CANCEL): e["sh"] = o[3] + rng.randint(1, 5)
            elif rng.random() < faults / 2 and e["t"] in (EXEC, CANCEL): e["sh"] = 0
            elif rng.random() < faults / 2 and e["t"] == REPLACE and len(live) > 1: e["ref2"] = rng.choice(live)
        out.append(e); book.event(e)
    return out
if __name__ == "__main__":
    b = Book(2, 2, 3)
    assert b.event(dict(t=ADD, ref=1, sym=0, side=0, px=100, sh=50)) == (1, OK, 0) and b.top(0) == (100, 50, 0, 0, 1, 0, 1)
    assert b.event(dict(t=ADD, ref=2, sym=0, side=0, px=100, sh=25))[1] == OK and b.top(0)[:2] == (100, 75)                       # a second order at the same price: one level
    assert b.event(dict(t=ADD, ref=3, sym=0, side=0, px=101, sh=10))[1] == OK and b.top(0)[:2] == (101, 10) and b.top(0)[4] == 2 # a better bid becomes the top
    assert b.event(dict(t=ADD, ref=4, sym=0, side=0, px=99, sh=10))[1] == FULL                                                    # the table holds 3 orders
    assert b.event(dict(t=EXEC, ref=3, sh=10)) == (1, OK, 0) and b.top(0)[:2] == (100, 75)                                         # the level empties and goes
    assert b.event(dict(t=CANCEL, ref=1, sh=51))[1] == OVER and b.event(dict(t=CANCEL, ref=1, sh=0))[1] == ZERO and b.event(dict(t=CANCEL, ref=9, sh=1))[1] == UNK
    assert b.event(dict(t=ADD, ref=2, sym=0, side=1, px=105, sh=5))[1] == DUPREF
    assert b.event(dict(t=REPLACE, ref=1, ref2=5, px=98, sh=40)) == (2, OK, 0) and b.top(0)[:2] == (100, 25) and b.top(0)[4] == 2   # replace: new price, new reference
    assert b.event(dict(t=ADD, ref=6, sym=1, side=1, px=7, sh=1))[1] == OK and b.top(1) == (0, 0, 7, 1, 0, 1, 3) and b.event(dict(t=ADD, ref=7, sym=1, side=1, px=8, sh=1))[1] == FULL      # a second symbol; the table is shared
    c = Book(1, 1, 8); c.event(dict(t=ADD, ref=1, sym=0, side=0, px=10, sh=5)); assert c.event(dict(t=ADD, ref=2, sym=0, side=0, px=11, sh=5))[1] == LVL and c.event(dict(t=ADD, ref=2, sym=0, side=1, px=11, sh=5))[1] == OK   # a full side does not stop the other
    f = Book(2, 2, 2); f.event(dict(t=ADD, ref=1, sym=1, side=0, px=5, sh=1)); f.event(dict(t=ADD, ref=2, sym=1, side=0, px=6, sh=1))
    assert f.event(dict(t=ADD, ref=2, sym=1, side=1, px=7, sh=1))[1] == DUPREF and f.event(dict(t=ADD, ref=3, sym=1, side=1, px=7, sh=1))[1] == FULL      # a duplicate is found before the table is found full
    assert f.event(dict(t=REPLACE, ref=99, ref2=5, px=1, sh=1)) == (1, UNK, 0) and f.event(dict(t=DELETE, ref=99)) == (1, UNK, 0) and f.event(dict(t=DELETE, ref=2)) == (1, OK, 1)   # unknown references report symbol 0
    r = run([dict(t=ADD, ref=1, sym=0, side=0, px=5, sh=1), dict(t=REPLACE, ref=1, ref2=2, px=6, sh=1), dict(t=ADD, ref=3, sym=0, side=1, px=9, sh=1)], 1, 4, 8)
    assert [x[0] for x in r["rows"][:5]] == [1, 1, 0, 1, 1] and r["rows"][1][1] is not None and r["rows"][3][1] is not None      # the replace keeps the engine busy for the next cycle; results one cycle after the last phase
    print("book_gold hand-checked scenarios passed")
