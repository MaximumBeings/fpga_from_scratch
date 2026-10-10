#!/usr/bin/env python3
"""Chapter 23: the specification of the pre-trade risk gate. An ORDER may leave the building only if every limit holds AFTER it, counting the worst case in which everything still open is executed. FILLS and CANCELS release what an order took. The gate fails CLOSED.
STATE. Per account a and symbol s: pos (signed net shares filled), ob and os (open buy and sell shares: accepted, not yet filled or cancelled). Per account: notional (the sum of price x quantity of the open orders) and tokens (the rate bucket). Global: armed, fault.
CONFIGURATION (written at run time, reset to values that reject everything). Per account: max_long, max_short, max_qty, max_onot (the largest notional of one order), max_not (the largest total open notional), cap (the bucket size). Per symbol: a price band lo..hi (reset: lo > hi, empty). Every R cycles each account earns one token (up to cap); writing an account's configuration refills its bucket to cap.
EVENTS (offered in cycle a, answered in cycle a + 2, one per cycle, never stalled). ORDER(acct, sym, side, px, qty) is checked in this order, the first failure is the answer: 1 KILL (the kill input was high in cycle a), 2 DISARMED (not armed, or a fault has happened), 3 BADIDX (account or symbol out of range), 4 QTY (qty = 0 or above max_qty), 5 BAND (price outside lo..hi), 6 ONOT (px x qty above max_onot), 7 POS (buy: pos + ob + qty above max_long; sell: pos - os - qty below -max_short), 8 NOT (notional + px x qty above max_not), 9 RATE (no token), else 0 OK. An accepted order adds qty to ob (buy) or os (sell), px x qty to the notional and takes a token. A rejected order changes nothing.
FILL(acct, sym, side, px, qty) and CANCEL(...) name an accepted order's side, price and the quantity released: qty from ob (buy) or os (sell), px x qty from the notional; a FILL also moves pos (+qty for a buy, -qty for a sell). They are applied whether or not the gate is armed or killed (a cancel must always get through). If they release more than is open (or name a bad account or symbol), nothing changes and the answer is 10 FAULT, and the FAULT latch is set: from then on every order is refused (2) until reset.
CONTROL. arm (a pulse) sets armed unless kill is high (a fault refuses every order whether or not the gate is armed); disarm clears it and wins over arm. kill is a LEVEL. Reset (in_valid must be 0 while it is applied): armed = 0, fault = 0, all state 0, max_qty and the bucket sizes 0 (max_qty 0 rejects every order even if somebody arms the gate, so the other limits need no reset), bands empty.
ANSWER: (kind, result, pos, ob, os, notional, tokens) of the touched (account, symbol) AFTER the update (zeros if the indexes are bad).
TIME: a write (configuration, band, arm, disarm) in cycle c is seen by the orders offered from cycle c on (they are checked in cycle a + 1 > c); the kill input is sampled in the cycle the order is offered. A token tick comes in the cycles with c mod R = R - 1, and is applied after the order of that cycle took its token."""
import random
ORDER, FILL, CANCEL = range(3)
KN = ["ORDER", "FILL", "CANCEL"]
OK, KILL, DISARMED, BADIDX, QTY, BAND, ONOT, POS, NOT, RATE, FAULT = range(11)
RN = ["OK", "KILL", "DISARMED", "BADIDX", "QTY", "BAND", "ONOT", "POS", "NOT", "RATE", "FAULT"]
BUY, SELL = 0, 1
def new_cfg(): return dict(maxlong=0, maxshort=0, maxqty=0, maxonot=0, maxnot=0, cap=0)
class Gate:
    def __init__(self, na, ns, r):
        self.na, self.ns, self.r = na, ns, r
        self.pos = [[0] * ns for _ in range(na)]; self.ob = [[0] * ns for _ in range(na)]; self.os = [[0] * ns for _ in range(na)]
        self.notional = [0] * na; self.tokens = [0] * na; self.cfg = [new_cfg() for _ in range(na)]; self.band = [(1, 0)] * ns
        self.armed = 0; self.fault = 0
    def touched(self, a, s):
        if a >= self.na or s >= self.ns: return (0, 0, 0, 0, 0)
        return (self.pos[a][s], self.ob[a][s], self.os[a][s], self.notional[a], self.tokens[a])
    def event(self, e, kill):
        """-> (kind, result, state after, consumed a token?)"""
        t, a, s, side, px, qty = e; bad = a >= self.na or s >= self.ns; prod = px * qty
        if t == ORDER:
            if kill: r = KILL
            elif not self.armed or self.fault: r = DISARMED
            elif bad: r = BADIDX
            else:
                c = self.cfg[a]; lo, hi = self.band[s]
                if qty == 0 or qty > c["maxqty"]: r = QTY
                elif not lo <= px <= hi: r = BAND
                elif prod > c["maxonot"]: r = ONOT
                elif (side == BUY and self.pos[a][s] + self.ob[a][s] + qty > c["maxlong"]) or (side == SELL and self.pos[a][s] - self.os[a][s] - qty < -c["maxshort"]): r = POS
                elif self.notional[a] + prod > c["maxnot"]: r = NOT
                elif self.tokens[a] == 0: r = RATE
                else: r = OK
            if r == OK:
                if side == BUY: self.ob[a][s] += qty
                else: self.os[a][s] += qty
                self.notional[a] += prod; self.tokens[a] -= 1
            return t, r, self.touched(a, s), r == OK
        open_ = None if bad else (self.ob[a][s] if side == BUY else self.os[a][s])
        if bad or qty > open_ or prod > self.notional[a]: self.fault = 1; return t, FAULT, self.touched(a, s), False
        if side == BUY: self.ob[a][s] -= qty
        else: self.os[a][s] -= qty
        self.notional[a] -= prod
        if t == FILL: self.pos[a][s] += qty if side == BUY else -qty
        return t, OK, self.touched(a, s), False
def run(cycles, na=4, ns=4, r=4):
    """Closed loop. cycles[c] = dict(ev=(type, acct, sym, side, px, qty), cfg=(acct, dict), band=(sym, lo, hi), arm=1, disarm=1, kill=1), any subset; cycle 0 is the first cycle after reset. -> dict(rows, gate) with rows[c] = (valid, kind, result, pos, ob, os, notional, tokens) of the answer visible in cycle c."""
    g = Gate(na, ns, r); n = len(cycles) + 3; rows = [(0,) * 8] * n; pend = None
    for c in range(n):
        cy = cycles[c] if c < len(cycles) else {}
        if pend is not None:                                                                       # stage C: the event offered in cycle c - 1, with the state as of the start of cycle c
            e, k = pend; kind, res, st, _ = g.event(e, k); rows[c + 1 if c + 1 < n else c] = (1, kind, res) + st
        pend = (cy["ev"], cy.get("kill", 0)) if "ev" in cy else None
        for a in range(na):                                                                        # the token tick, after the order of this cycle took its token
            if c % r == r - 1 and g.tokens[a] < g.cfg[a]["cap"]: g.tokens[a] += 1
        if "cfg" in cy:                                                                            # a configuration write refills the bucket (and wins over the tick)
            a, u = cy["cfg"]
            if a < na: g.cfg[a] = dict(u); g.tokens[a] = u["cap"]
        if "band" in cy:
            s, lo, hi = cy["band"]
            if s < ns: g.band[s] = (lo, hi)
        if cy.get("disarm"): g.armed = 0
        elif cy.get("arm") and not cy.get("kill", 0): g.armed = 1
    return dict(rows=rows[:len(cycles) + 3], gate=g)
def expected_rows(res): return [(c,) + tuple(r) for c, r in enumerate(res["rows"])]
def write_stim(path, cycles, seed=1):
    """One line per cycle, the layout of tb/risk_tb.sv (bit offsets: event 0..43, account configuration 44..176, band 177..213, control 214..216); fields not offered are junk."""
    rng = random.Random(seed)
    with open(path, "w") as f:
        for cy in cycles:
            v = 0; e = cy.get("ev"); u = cy.get("cfg"); b = cy.get("band")
            t, a, s, side, px, qty = e if e else (rng.randrange(3), rng.randrange(16), rng.randrange(16), rng.randrange(2), rng.getrandbits(16), rng.getrandbits(16))
            v |= (1 if e else 0) | (t << 1) | (a << 3) | (s << 7) | (side << 11) | (px << 12) | (qty << 28)
            ca, w = u if u else (rng.randrange(16), dict(maxlong=rng.getrandbits(16), maxshort=rng.getrandbits(16), maxqty=rng.getrandbits(16), maxonot=rng.getrandbits(32), maxnot=rng.getrandbits(40), cap=rng.getrandbits(8)))
            v |= ((1 if u else 0) << 44) | (ca << 45) | (w["maxlong"] << 49) | (w["maxshort"] << 65) | (w["maxqty"] << 81) | (w["maxonot"] << 97) | (w["maxnot"] << 129) | (w["cap"] << 169)
            bs, lo, hi = b if b else (rng.randrange(16), rng.getrandbits(16), rng.getrandbits(16))
            v |= ((1 if b else 0) << 177) | (bs << 178) | (lo << 182) | (hi << 198)
            v |= (cy.get("arm", 0) << 214) | (cy.get("disarm", 0) << 215) | (cy.get("kill", 0) << 216)
            f.write("%056x\n" % v)
    return len(cycles)
def gen_cycles(rng, n, na=4, ns=4, r=4, qmax=60, pmax=100, density=0.7, bad=0.03, malformed=0.0, kill_rate=0.01):
    """Traffic: the control plane configures every account and symbol and arms the gate in the first cycles (but writes again at random later, with arm / disarm / kill pulses), then orders, fills and cancels mostly on accepted orders (an oracle gate runs alongside, so that fills and cancels mostly release what is open), some at limits, some bad indexes, some malformed releases (more than is open)."""
    def rcfg(): return dict(maxlong=rng.randint(0, qmax * 2), maxshort=rng.randint(0, qmax * 2), maxqty=rng.randint(0, qmax), maxonot=rng.randint(0, pmax * qmax), maxnot=rng.randint(0, pmax * qmax * 3), cap=rng.randint(0, 6))
    cyc = []; setup = [dict(cfg=(a, rcfg())) for a in range(na)] + [dict(band=(s, rng.randint(0, pmax // 2), rng.randint(pmax // 2, pmax))) for s in range(ns)]
    for u in setup: cyc.append(u)
    cyc.append(dict(arm=1)); og = Gate(na, ns, r); open_orders = []
    def oracle(cy, c):                                                                                 # the generator's own copy of the gate, to know which orders were accepted (the same writes are seen by the event of their cycle)
        if "cfg" in cy:
            a, u = cy["cfg"]
            if a < na: og.cfg[a] = dict(u); og.tokens[a] = u["cap"]
        if "band" in cy:
            s_, lo, hi = cy["band"]
            if s_ < ns: og.band[s_] = (lo, hi)
        if cy.get("disarm"): og.armed = 0
        elif cy.get("arm") and not cy.get("kill", 0): og.armed = 1
        took = None
        if "ev" in cy: took = og.event(cy["ev"], cy.get("kill", 0))
        for a in range(na):
            if c % r == r - 1 and og.tokens[a] < og.cfg[a]["cap"]: og.tokens[a] += 1
        return took
    for c, u in enumerate(cyc): oracle(u, c)
    for n_ in range(n):
        cy = {}; c = len(cyc)
        if rng.random() < density:
            x = rng.random()
            if x < 0.45 or not open_orders:
                a = rng.randrange(na + (1 if rng.random() < bad else 0)); s = rng.randrange(ns + (1 if rng.random() < bad else 0)); cy["ev"] = (ORDER, a, s, rng.randrange(2), rng.randint(0, pmax + 5), rng.randint(0, qmax + 3))
            else:
                k = rng.randrange(len(open_orders)); o = open_orders[k]; q = rng.randint(1, max(1, o[5])) if rng.random() > malformed else o[5] + rng.randint(1, 3)
                cy["ev"] = (rng.choice([FILL, CANCEL]), o[1], o[2], o[3], o[4] if rng.random() > malformed / 2 else o[4] + 1, q)
        if rng.random() < 0.02: cy["cfg"] = (rng.randrange(na), rcfg())
        if rng.random() < 0.02: cy["band"] = (rng.randrange(ns), rng.randint(0, pmax // 2), rng.randint(pmax // 2, pmax))
        if rng.random() < 0.02: cy["arm"] = 1
        if rng.random() < 0.004: cy["disarm"] = 1
        if rng.random() < kill_rate: cy["kill"] = 1
        took = oracle(cy, c); cyc.append(cy)
        if took is not None and took[0] == ORDER and took[1] == OK: open_orders.append(cy["ev"])
        elif took is not None and took[0] != ORDER and took[1] == OK:                                   # forget the released part
            e = cy["ev"]
            for k, x in enumerate(open_orders):
                if x[1:5] == e[1:5]:
                    if x[5] <= e[5]: open_orders.pop(k)
                    else: open_orders[k] = x[:5] + (x[5] - e[5],)
                    break
    for cy in cyc: cy.pop("_order", None)
    return cyc
def fault_cycles(variant, na=4, ns=4):
    """Directed, one release that is not allowed, each from reset (the latch holds until reset, so one fault per run): 0 a sell release of one more than is open; 1 the exact open quantity (applied), then one more; 2 a quantity that is open but at a price whose notional is exactly one more than is open (21 against 20); 3 a bad account; 4 a bad symbol. After it: an order (refused: DISARMED) and a release that is allowed (applied)."""
    big = dict(maxlong=100, maxshort=100, maxqty=50, maxonot=5000, maxnot=20000, cap=9); O = lambda side, px, q: dict(ev=(ORDER, 0, 0, side, px, q))
    out = [dict(cfg=(0, big)), dict(band=(0, 1, 50)), dict(arm=1), dict()]
    if variant == 0: out += [O(SELL, 20, 5), O(BUY, 20, 5), dict(ev=(CANCEL, 0, 0, SELL, 20, 6))]
    elif variant == 1: out += [O(SELL, 20, 5), O(BUY, 20, 5), dict(ev=(CANCEL, 0, 0, SELL, 20, 5)), dict(ev=(CANCEL, 0, 0, SELL, 20, 1))]
    elif variant == 2: out += [O(BUY, 20, 1), dict(ev=(CANCEL, 0, 0, BUY, 21, 1))]
    elif variant == 3: out += [O(BUY, 20, 5), dict(ev=(FILL, na, 0, BUY, 20, 5))]
    else: out += [O(BUY, 20, 5), dict(ev=(CANCEL, 0, ns, BUY, 20, 5))]
    out += [O(BUY, 20, 1), dict(ev=(FILL, 0, 0, BUY, 20, 1)), dict(), dict(), dict()]
    return out
def reset_cycles(na=4, ns=4, r=5):
    """Directed, the first cycles after reset: an order to an account nobody configured, ten cycles after reset (its answer shows the account's tokens: 0, since the bucket size resets to 0), then an account with a bucket of 4 and a stream of accepted orders, one per cycle, whose answers show the bucket emptying and the ticks refilling it (the phase of the tick counter after reset)."""
    big = dict(maxlong=100, maxshort=100, maxqty=50, maxonot=5000, maxnot=20000, cap=4)
    out = [dict() for _ in range(10)] + [dict(arm=1), dict(), dict(ev=(ORDER, 0, 0, BUY, 5, 1)), dict(cfg=(0, big)), dict(band=(0, 1, 50))]
    out += [dict(ev=(ORDER, 0, 0, BUY if k % 3 else SELL, 5, 1)) for k in range(24)] + [dict()] * 4
    return out
def edge_cycles(na=4, ns=4, r=1000):
    """Directed: every result of an order once and each limit at its boundary (the sequence of the hand-checked scenarios, one event per cycle), with a second account whose bucket holds one token, a fault, and fills after it. R must be large (no token ticks): the bucket sizes are the counts."""
    c0 = dict(maxlong=10, maxshort=8, maxqty=6, maxonot=300, maxnot=500, cap=5); c1 = dict(c0, cap=1)
    O = lambda a, s, side, px, q, **kw: dict(ev=(ORDER, a, s, side, px, q), **kw)
    out = [O(0, 0, BUY, 50, 1), dict(arm=1), O(0, 0, BUY, 50, 1), dict(cfg=(0, c0)), O(0, 0, BUY, 50, 1), dict(cfg=(1, c1)), dict(band=(0, 10, 100)), dict(band=(1, 10, 100)), dict(), dict(disarm=1)]      # armed with nothing configured: QTY (max_qty resets to 0); configured account, no band: BAND (the band resets empty)
    out += [O(0, 0, BUY, 50, 1), dict(arm=1), dict(), O(0, 0, BUY, 50, 1, kill=1), O(na, 0, BUY, 50, 1), O(0, ns, BUY, 50, 1), O(0, 0, BUY, 50, 0), O(0, 0, BUY, 50, 7), O(0, 0, BUY, 9, 1), O(0, 0, BUY, 101, 1), O(0, 0, SELL, 100, 4)]
    out += [O(0, 0, SELL, 10, 1), O(0, 0, SELL, 75, 4), O(0, 0, SELL, 20, 4), O(0, 0, SELL, 20, 3), O(0, 0, BUY, 20, 6), O(0, 0, BUY, 20, 5), O(0, 0, BUY, 20, 4), O(0, 0, BUY, 10, 1)]
    out += [dict(ev=(FILL, 0, 0, BUY, 20, 6)), O(0, 0, BUY, 10, 4), dict(ev=(FILL, 0, 0, SELL, 20, 3)), dict(ev=(CANCEL, 0, 0, BUY, 10, 1)), O(1, 1, BUY, 50, 1), O(1, 1, BUY, 50, 1), O(1, 0, SELL, 20, 1)]
    out += [dict(disarm=1), dict(ev=(CANCEL, 1, 1, BUY, 50, 1), kill=1), dict(arm=1, kill=1), O(0, 0, BUY, 20, 1), dict(arm=1, disarm=1), O(0, 0, BUY, 20, 1), dict(arm=1), O(0, 0, BUY, 20, 1)]       # releases apply while disarmed and killed; arm is refused while kill is high; disarm wins over arm; the gate is armed again
    out += [dict(ev=(CANCEL, 0, 0, BUY, 10, 1)), O(0, 0, BUY, 20, 1), dict(disarm=1), dict(arm=1), O(0, 0, BUY, 20, 1), dict(ev=(FILL, 0, 0, SELL, 75, 4)), dict(ev=(FILL, na, 0, BUY, 1, 1)), dict(), dict(), dict()]
    return out
if __name__ == "__main__":
    g = Gate(2, 2, 4); g.cfg[0] = dict(maxlong=10, maxshort=8, maxqty=6, maxonot=300, maxnot=500, cap=2); g.tokens[0] = 2; g.band[0] = (10, 100); g.band[1] = (10, 100)
    ev = lambda *a, k=0: g.event(a, k)
    assert ev(ORDER, 0, 0, BUY, 50, 1)[:2] == (ORDER, DISARMED)                                                      # not armed: nothing passes
    g.armed = 1
    assert ev(ORDER, 0, 0, BUY, 50, 1, k=1)[1] == KILL and ev(ORDER, 5, 0, BUY, 50, 1, k=1)[1] == KILL                 # kill is checked first, even before the index
    assert ev(ORDER, 5, 0, BUY, 50, 1)[1] == BADIDX and ev(ORDER, 0, 2, BUY, 50, 1)[1] == BADIDX                      # account and symbol out of range
    assert ev(ORDER, 0, 0, BUY, 50, 0)[1] == QTY and ev(ORDER, 0, 0, BUY, 50, 7)[1] == QTY and ev(ORDER, 0, 0, BUY, 50, 6)[1] == OK                  # zero, above max_qty 6, and exactly 6 passes
    assert g.touched(0, 0) == (0, 6, 0, 300, 1)
    g = Gate(2, 2, 4); g.cfg[0] = dict(maxlong=10, maxshort=8, maxqty=6, maxonot=300, maxnot=500, cap=2); g.tokens[0] = 2; g.band[0] = (10, 100); g.band[1] = (10, 100); g.armed = 1
    assert ev(ORDER, 0, 0, BUY, 9, 1)[1] == BAND and ev(ORDER, 0, 0, BUY, 101, 1)[1] == BAND and ev(ORDER, 0, 0, SELL, 10, 1)[:3] == (ORDER, OK, g.touched(0, 0)) and g.touched(0, 0) == (0, 0, 1, 10, 1)   # the band is inclusive
    assert ev(ORDER, 0, 0, SELL, 100, 4)[1] == ONOT and ev(ORDER, 0, 0, SELL, 75, 4)[1] == OK and g.touched(0, 0) == (0, 0, 5, 310, 0)      # 100 x 4 = 400 > 300; 75 x 4 = 300 is allowed: os 1 + 4 = 5, notional 10 + 300, last token
    assert ev(ORDER, 0, 0, BUY, 50, 1)[1] == RATE and g.touched(0, 0) == (0, 0, 5, 310, 0)                              # no token: refused, nothing changed
    g.tokens[0] = 5
    assert ev(ORDER, 0, 0, SELL, 20, 4)[1] == POS and ev(ORDER, 0, 0, SELL, 20, 3)[1] == OK and g.touched(0, 0) == (0, 0, 8, 370, 4)                  # short: 0 - 5 - 4 = -9 < -8; 0 - 5 - 3 = -8 allowed
    assert ev(ORDER, 0, 0, BUY, 20, 6)[1] == OK and g.touched(0, 0) == (0, 6, 8, 490, 3)                                # long: 0 + 0 + 6 = 6
    assert ev(ORDER, 0, 0, BUY, 20, 5)[1] == POS and ev(ORDER, 0, 0, BUY, 20, 4)[1] == NOT and g.touched(0, 0) == (0, 6, 8, 490, 3)                  # 6 + 5 = 11 > 10; 6 + 4 = 10 passes POS but 490 + 80 = 570 > 500
    assert ev(ORDER, 0, 0, BUY, 10, 1)[1] == OK and g.touched(0, 0) == (0, 7, 8, 500, 2)                                # 500 = max_not exactly
    assert ev(FILL, 0, 0, BUY, 20, 6)[1:] == (OK, (6, 1, 8, 380, 2), False) and ev(FILL, 0, 0, SELL, 20, 3)[1:] == (OK, (3, 1, 5, 320, 2), False)       # a fill releases open quantity and notional and moves the position
    assert ev(CANCEL, 0, 0, BUY, 10, 1)[1:] == (OK, (3, 0, 5, 310, 2), False)                                            # a cancel releases but does not move the position
    assert ev(CANCEL, 0, 0, BUY, 10, 1)[1:] == (FAULT, (3, 0, 5, 310, 2), False) and g.fault == 1                         # more than is open: FAULT, nothing changes, the latch is set
    assert ev(ORDER, 0, 0, BUY, 20, 1)[1] == DISARMED                                                                    # armed, but after a fault every order is refused
    assert ev(FILL, 0, 0, SELL, 75, 4)[1:] == (OK, (-1, 0, 1, 10, 2), False)                                             # fills still apply after a fault (and while killed or disarmed)
    h = Gate(1, 1, 4); h.cfg[0] = dict(maxlong=10, maxshort=10, maxqty=5, maxonot=100, maxnot=100, cap=3); h.tokens[0] = 3; h.band[0] = (1, 100); h.armed = 1
    assert h.event((ORDER, 0, 0, BUY, 10, 2), 0)[1] == OK and h.event((CANCEL, 0, 0, BUY, 11, 2), 0)[1] == FAULT and h.touched(0, 0) == (0, 2, 0, 20, 2)  # releasing 11 x 2 = 22 from a notional of 20
    assert h.event((FILL, 5, 0, BUY, 1, 1), 0)[1] == FAULT                                                               # a fill for an account that does not exist
    # timing, hand-simulated: R = 2 (a token tick in the odd cycles), cap 2; a write in cycle c is seen by the orders offered from cycle c on
    B = dict(maxlong=10, maxshort=10, maxqty=5, maxonot=1000, maxnot=1000, cap=2); o = (ORDER, 0, 0, BUY, 10, 1)
    t = run([dict(cfg=(0, B)), dict(band=(0, 1, 100), ev=o), dict(arm=1, ev=o), dict(ev=o), dict(ev=o), dict(ev=o), dict(ev=o), dict(ev=o), dict(), dict()], 1, 1, 2)["rows"]
    assert t[3] == (1, ORDER, DISARMED, 0, 0, 0, 0, 2) and t[4] == (1, ORDER, OK, 0, 1, 0, 10, 1)                          # offered in cycle 1 (checked in 2, before the arm of cycle 2 lands): refused; offered in cycle 2 together with the arm: accepted, tokens 2 -> 1 (the tick of cycle 3 refills the bucket after the answer is formed)
    assert t[5] == (1, ORDER, OK, 0, 2, 0, 20, 1) and t[6] == (1, ORDER, OK, 0, 3, 0, 30, 0) and t[7] == (1, ORDER, OK, 0, 4, 0, 40, 0)   # checked in 4 (tokens 2 -> 1, no tick), in 5 (1 -> 0, the tick of 5 gives 1 back), in 6 (1 -> 0)
    assert t[8] == (1, ORDER, RATE, 0, 4, 0, 40, 0) and t[9] == (1, ORDER, OK, 0, 5, 0, 50, 0)                              # checked in 7: no token, refused (the tick of cycle 7 comes after it); checked in 8: the token from that tick
    u = run([dict(cfg=(0, B)), dict(band=(0, 1, 100)), dict(arm=1, kill=1), dict(ev=o), dict(ev=o, kill=1), dict(arm=1), dict(ev=o), dict(), dict()], 1, 1, 100)["rows"]
    assert u[5] == (1, ORDER, DISARMED, 0, 0, 0, 0, 2) and u[6] == (1, ORDER, KILL, 0, 0, 0, 0, 2) and u[8] == (1, ORDER, OK, 0, 1, 0, 10, 1)      # the arm of cycle 2 was refused (kill was high), so the order of cycle 3 is DISARMED; kill sampled in cycle 4 refuses that order; the arm of cycle 5 lands, the order of cycle 6 passes
    f = run([dict(cfg=(0, B)), dict(band=(0, 1, 100)), dict(arm=1), dict(ev=(CANCEL, 0, 0, BUY, 10, 1)), dict(ev=o), dict(), dict()], 1, 1, 100)
    assert f["rows"][5][:3] == (1, CANCEL, FAULT) and f["rows"][6][:3] == (1, ORDER, DISARMED) and f["gate"].fault == 1 and f["gate"].armed == 1     # a release with nothing open: FAULT, and the next order is refused although the gate is armed
    d = run([dict(cfg=(0, B)), dict(band=(0, 1, 100)), dict(arm=1, disarm=1), dict(ev=o), dict(), dict()], 1, 1, 100)
    assert d["rows"][5][2] == DISARMED and d["gate"].armed == 0                                                         # disarm wins over arm in the same cycle
    print("risk_gold hand-checked scenarios passed")
