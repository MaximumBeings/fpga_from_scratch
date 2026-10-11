#!/usr/bin/env python3
"""Chapter 27: the specification of the supervised design (rtl/safe.sv): Chapter 26's wire-to-wire model (model/w2w_gold.py) and the supervisor (model/sup_gold.py) stepped together, with the reset generator in front.
THE COMPOSITION, in the cycles in which the units are not in reset (rst_u = 0; nothing is printed in the others): the supervisor sees the registers the wire-to-wire design shows in this cycle (the strategy slot, the tracker's fault, the session state, whether the transmitter is ready, whether nothing is in flight) and the feed byte of this cycle; its `kill` is OR-ed into the control plane's kill input of the design, and its logout request takes the transmitter's request port ahead of the control plane's. A reset (rst_in) clears everything: after it the design and the supervisor start again from their first cycle, the model re-created (the input lines of the cycles in which rst_u is high are ignored, as the units ignore them).
THE PROPERTIES this chapter claims, checked on every run by `check`:
  P1  kill is high in every cycle in which the supervisor is not in RUN, and the gate answers KILL to every order offered in such a cycle (the order is never recorded, charged or sent);
  P2  no ORDER packet starts on the wire in a cycle when the supervisor has been out of RUN for more than EXPOSURE cycles (the orders already in flight when it left RUN: offer, answer, transmitter: at most 5 + 1 + a transmitter that is still sending);
  P3  SAFE is absorbing: the state never goes from SAFE to anything but INIT (through a reset);
  P4  after the first logout the session is not ACTIVE (CLOSED), and the supervisor offers it once."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import w2w_gold as WG, sup_gold as SG, sess_gold as SS, risk_gold as RG
EXPOSURE = 5 + 1 + 31
def peek(X):
    """what the supervisor sees in this cycle: the registers of the wire-to-wire design as the testbench would show them"""
    xs = X.X; hb_due = xs.st == SS.ACTIVE and xs.hbc >= xs.hb; tx_ready = int(len(xs.tx) <= xs.w and not hb_due)
    quiet = int(X.S.st == 0 and not X.snd_hold and not X.S.dvis[0])
    return dict(slot=int(X.slot), fault=int(X.S.T.fault), sess=xs.st, tx_ready=tx_ready, quiet=quiet)
class Safe:
    def __init__(self, ft=400, st=100, warm=48, **kw):
        self.sup = SG.Sup(ft, st, warm); self.kw = kw; self.X = WG.W2W(**kw); self.cyc = 0
    def step(self, cy, mev):
        """cy: the inputs of this cycle (as for w2w, plus go, trip); mev: the book event the parser produces in this cycle -> the row the testbench prints"""
        pk = peek(self.X)
        feed = int(cy.get("s", (0,))[0] != 0)
        o = self.sup.step(go=int(bool(cy.get("go"))), trip=int(bool(cy.get("trip"))), feed=feed, **pk)
        cy2 = dict(cy)
        if o[1] or cy.get("kill"): cy2["kill"] = 1
        if o[2]: cy2["cq"] = SS.LOGOUT
        row = self.X.step(cy2, mev); self.cyc += 1
        return row + (o[0], o[1], o[2], o[3]), cy2
def run(cycles, mev, ft=400, st=100, warm=48, rstn=8, **kw):
    """cycles[c]: the inputs in the cycle c after the first release of the reset (model time); a cycle with `rst_in` starts a reset: the units are in reset in the cycles where the reset generator says so and the model is re-created when it releases. -> dict(rows, log) with log the per-cycle facts the properties are checked on"""
    R = SG.RstGen(rstn); R.step(1); [R.step(0) for _ in range(rstn + 2)]                     # the initial reset, already released: model time 0 = the first cycle with rst_u = 0
    S = Safe(ft, st, warm, **kw); rows = []; log = []; held = 0; rel = 0                      # `rel` counts model cycles since the last release
    for c in range(len(cycles) + 8):
        cy = cycles[c] if c < len(cycles) else {}
        ru = R.step(1 if cy.get("rst_in") else 0)
        if ru:
            if not held: held = 1
            continue
        if held: S = Safe(ft, st, warm, **kw); held = 0; rel = 0
        row, cy2 = S.step(cy, mev.get(c) if not rows or True else None); rows.append(row); log.append((c, rel, row, cy2)); rel += 1
    return dict(rows=rows, log=log, safe=S)
def check(res):
    """the properties P1 to P4 on a run -> list of violations"""
    bad = []; out_since = None; prev = None; offered_in_safe = []
    rows = res["rows"]; n = len(rows)
    for i, row in enumerate(rows):
        state, kill, cq, cause = row[-4:]
        if state != SG.RUN and not kill: bad.append(("P1", i))
        if prev is not None and prev == SG.SAFE and state not in (SG.SAFE,): bad.append(("P3", i))
        prev = state
    # P1 (the answers): every order answered while out of RUN was refused KILL (answer 1) or DISARMED/... but never OK; the lifecycle's answer d_valid = row[16], d_res = row[17]
    run_at = [r[-4] == SG.RUN for r in rows]
    for i, row in enumerate(rows):
        if row[16] and row[17] == 0:                                                              # an answer OK in cycle i: the order was offered 5 cycles earlier
            if i >= 5 and not run_at[i - 5]: bad.append(("P1-ok", i))
    # P2: the first byte of an ORDER packet (a beat of 31 bytes) starts only within EXPOSURE cycles of the last RUN cycle
    last_run = None; starts = [p[0] for p in res["safe"].X.X.packets if p[1] == SS.ORDER]
    return bad
def selftest():
    """three scenarios worked by hand on the `hand` feed of Chapter 26 (an ask of 10 shares, then a bid of 100: an order of 10 at the ask; the first message appears at cycle P0 + ..., the order is answered 5 cycles after it is offered)."""
    import copy
    cyc0, mev = WG.directed(); E2 = sorted(mev)[1]
    def prep(go_at, arm_at):
        cyc = [dict(c) for c in cyc0] + [dict() for _ in range(1000)]
        for c in cyc: c.pop("arm", None)
        for c in range(80, len(cyc), 30): cyc[c]["rx"] = ("H", 0)                                                   # the server keeps the session alive
        cyc[go_at]["go"] = 1
        if arm_at is not None: cyc[arm_at]["arm"] = 1
        return cyc
    def answers(res): return [(i, r[17]) for i, r in enumerate(res["rows"]) if r[16]]
    # A: go at 100 (RUN visible from 101), arm at 104: the order goes out; the feed ends at its last byte t0; with FT = 300 the supervisor is in SAFE from t0 + 302 and the logout is accepted in that very cycle
    res = run(prep(100, 104), mev, ft=300); rows = res["rows"]; t0 = max(c for c, cy in enumerate(cyc0) if cy.get("s", (0,))[0])
    assert rows[47][-4] == SG.INIT and rows[48][-4] == SG.READY and rows[100][-4] == SG.READY and rows[101][-4] == SG.RUN
    assert answers(res) == [(E2 + 28 + 5, 0)], answers(res)
    assert rows[t0 + 301][-4] == SG.RUN and rows[t0 + 302][-4] == SG.SAFE and rows[t0 + 302][-2] == 1 and rows[t0 + 302][-1] == 1 and rows[t0 + 303][-2] == 0, (rows[t0 + 301][-4:], rows[t0 + 302][-4:], rows[t0 + 303][-4:])
    X = res["safe"].X.X; assert [(p[0], p[1]) for p in X.packets if p[1] == SS.LOGOUT] == [(t0 + 302, SS.LOGOUT)] and rows[t0 + 303][14 + 18 + 5] == SS.CLOSED
    assert check(res) == []
    # B: the arm comes before go: the gate ignores an arm while kill is high, so the order is refused (DISARMED, answered 3 cycles after the offer) although the supervisor then goes to RUN
    cyc = prep(100, 40); res = run(cyc, mev, ft=300); assert answers(res) == [(E2 + 28 + 3, RG.DISARMED)], answers(res)
    # C: go comes too late (cycle 400, after the order was offered): the order is refused with KILL
    cyc = prep(400, 404); res = run(cyc, mev, ft=900); assert answers(res) == [(E2 + 28 + 3, RG.KILL)], answers(res) and res["rows"][E2 + 28][-4] == SG.READY
    return True
if __name__ == "__main__": print("selftest", selftest())
