#!/usr/bin/env python3
"""Chapter 25: the specification of the joined design (rtl/life.sv): the risk gate of Chapter 23 (model/risk_gold.py, unchanged) and the order tracker (model/life_gold.py) with a small state machine for the order in flight.
THE ORDER IN FLIGHT (one at a time). IDLE: an order request is taken when no release from the tracker is using the gate's event port that cycle (`ord_ready`); it is offered to the gate as an ORDER at once. RISK1, RISK2: the gate answers two cycles after the offer. A refusal ends the order: the answer is the gate's code (0..10). TNEW: the tracker is offered NEW (held until accepted; a report from the exchange wins the cycle). TANS: the tracker's answer: OK ends the order with answer 0 (it may be sent); any other answer (ZERO, DUPTOK, FULL) means the gate has been charged for an order that will not exist, so the state RB gives the charge back: a CANCEL release of the same account, symbol, side, price and quantity, in the first cycle in which the event port is free; the answer is 16 + the tracker's code. The answer (`d_valid`, `d_res`, `d_tok`) is a one-cycle pulse in the cycle after the decisive one.
THE GATE'S EVENT PORT has one user per cycle, in this priority: a release from the tracker (it is already waiting in the tracker's output register), a give-back, a new order. The tracker's releases are therefore never delayed. Cancel requests (`cr_*`) go straight to the tracker (refused while it takes the order in flight); their answers are `c_valid`, `c_res`.
FAIL CLOSED. The tracker's fault is wired to the gate's kill input for good: after any report the books cannot explain, every order is refused (code 1, KILL) until reset; releases still get through.
RECONCILIATION (checked in every cycle in which the design is quiet: no order in flight, nothing waiting in the tracker's output register or in the gate's pipeline): for every account and symbol, the gate's open buys (sells) equal the sum of the remaining quantities of the tracker's buy (sell) orders, and the gate's open notional of an account equals the sum of price x remaining quantity of the tracker's orders. This is the property the design exists to keep: the two books describe the same orders."""
import os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import risk_gold as RG, life_gold as LG
from risk_gold import ORDER, FILL, CANCEL, BUY, SELL
IDLE, RISK1, RISK2, TNEW, TANS, RB = range(6)
SN = ["IDLE", "RISK1", "RISK2", "TNEW", "TANS", "RB"]
class Sys:
    def __init__(self, nt=4, na=4, ns=4, r=4):
        self.na, self.ns, self.r = na, ns, r; self.g = RG.Gate(na, ns, r); self.T = LG.Tracker(nt); self.c = 0; self.st = IDLE; self.h = None; self.hres = 0
        self.tpend = (0, 0, 0, None); self.rpend = None; self.rvis = (0,) * 8; self.dvis = (0, 0, 0); self.ordq = []; self.crq = []; self.checks = 0; self.bad = 0; self.collide = 0
    def reconcile(self):
        g, T = self.g, self.T; self.checks += 1
        for a in range(self.na):
            for s in range(self.ns):
                b = sum(x["rem"] for x in T.e if x and x["acct"] == a and x["sym"] == s and x["side"] == BUY); o = sum(x["rem"] for x in T.e if x and x["acct"] == a and x["sym"] == s and x["side"] == SELL)
                if g.ob[a][s] != b or g.os[a][s] != o: self.bad += 1; return
            if g.notional[a] != sum(x["px"] * x["rem"] for x in T.e if x and x["acct"] == a): self.bad += 1; return
    def step(self, cy):
        c, g, T = self.c, self.g, self.T
        if "ord" in cy: self.ordq.append(cy["ord"])
        if "cr" in cy: self.crq.append(cy["cr"])
        ordp = self.ordq[0] if self.ordq else None; crp = self.crq[0] if self.crq else None; rep = cy.get("rep")
        tv, tsrc, tres, trel = self.tpend; t_ready = rep is None; trv = trel is not None; st = self.st
        ord_ready = int(st == IDLE and not trv); cr_ready = int(st != TNEW and t_ready)
        c_valid = int(bool(tv) and not tsrc and st != TANS)
        row = (ord_ready, cr_ready) + self.dvis[:2] + ((self.dvis[2],) if self.dvis[0] else (0,)) + (c_valid, tres if c_valid else 0) + self.rvis + (T.nlive(), T.fault, st)
        if st == IDLE and self.rpend is None and not trv: self.reconcile()
        # stage 2 of the gate for the event offered in the previous cycle
        if self.rpend is not None: kind, res, stt, _ = g.event(*self.rpend); rnext = (1, kind, res) + stt
        else: rnext = (0,) * 8
        # the event offered in this cycle
        kill = cy.get("kill", 0) or T.fault; ev = None; took = False
        if trv and st == RB: self.collide += 1
        if trv: ev = trel
        elif st == RB: ev = (CANCEL, self.h["acct"], self.h["sym"], self.h["side"], self.h["px"], self.h["qty"])
        elif st == IDLE and ordp: ev = (ORDER, ordp["acct"], ordp["sym"], ordp["side"], ordp["px"], ordp["qty"]); took = True
        self.rpend = (ev, kill) if ev else None
        # the tracker
        tnext = (0, 0, 0, None)
        if rep is not None: r_, rel_ = T.report(*rep); tnext = (1, 1, r_, rel_)
        elif st == TNEW: r_, rel_ = T.local(LG.NEW, self.h); tnext = (1, 0, r_, rel_)
        elif crp is not None: r_, rel_ = T.local(LG.CANCELREQ, crp); tnext = (1, 0, r_, rel_); self.crq.pop(0)
        # the state machine
        dnext = (0, 0, 0)
        if st == IDLE:
            if took: self.h = self.ordq.pop(0); self.st = RISK1
        elif st == RISK1: self.st = RISK2
        elif st == RISK2:
            if self.rvis[2] != RG.OK: dnext = (1, self.rvis[2], self.h["tok"] & LG.M32); self.st = IDLE
            else: self.st = TNEW
        elif st == TNEW:
            if t_ready: self.st = TANS
        elif st == TANS:
            if tres == LG.OK: dnext = (1, 0, self.h["tok"] & LG.M32); self.st = IDLE
            else: self.hres = 16 + tres; self.st = RB
        elif st == RB:
            if not trv: dnext = (1, self.hres, self.h["tok"] & LG.M32); self.st = IDLE
        # the gate's clock: tokens, then the writes of this cycle
        for a in range(self.na):
            if c % self.r == self.r - 1 and g.tokens[a] < g.cfg[a]["cap"]: g.tokens[a] += 1
        if "cfg" in cy:
            a, u = cy["cfg"]
            if a < self.na: g.cfg[a] = dict(u); g.tokens[a] = u["cap"]
        if "band" in cy:
            s, lo, hi = cy["band"]
            if s < self.ns: g.band[s] = (lo, hi)
        if cy.get("disarm"): g.armed = 0
        elif cy.get("arm") and not cy.get("kill", 0): g.armed = 1
        self.tpend = tnext; self.rvis = rnext; self.dvis = dnext; self.c += 1
        return row
def run(cycles, nt=4, na=4, ns=4, r=4):
    """-> dict(rows, lines, sys); rows[c] = (ord_ready, cr_ready, d_valid, d_res, d_tok, c_valid, c_res, rk_valid, rk_kind, rk_res, pos, ob, os, notional, tokens, live, fault, state) visible in cycle c; lines[c] = the pins in cycle c"""
    S = Sys(nt, na, ns, r); rows = []; lines = []
    for c in range(len(cycles) + 8):
        cy = cycles[c] if c < len(cycles) else {}
        q = S.ordq + ([cy["ord"]] if "ord" in cy else []); k = S.crq + ([cy["cr"]] if "cr" in cy else [])
        lines.append((q[0] if q else None, k[0] if k else None, cy))
        rows.append(S.step(cy))
    return dict(rows=rows, lines=lines, sys=S)
def expected_rows(res): return res["rows"]
def write_stim(path, res):
    """one line per cycle, 328 bits as 82 hex digits (the layout of life_syn: 0 order valid, 1..32 token, 33..36 account, 37..40 symbol, 41 side, 42..57 price, 58..73 quantity, 74 cancel request valid, 75..106 token, 107 report valid, 108..109 kind, 110..141 token, 142..157 quantity, 158 cfg_a valid, 159..162 index, 163..178 max long, 179..194 max short, 195..210 max qty, 211..242 max order notional, 243..276 max notional, 277..284 bucket size, 285 cfg_b valid, 286..289 index, 290..305 lo, 306..321 hi, 322 arm, 323 disarm, 324 kill)"""
    with open(path, "w") as f:
        for o, k, cy in res["lines"]:
            v = 0
            if o: v |= 1 | (o["tok"] & LG.M32) << 1 | o["acct"] << 33 | o["sym"] << 37 | o["side"] << 41 | (o["px"] & 0xFFFF) << 42 | (o["qty"] & 0xFFFF) << 58
            if k: v |= 1 << 74 | (k["tok"] & LG.M32) << 75
            if "rep" in cy: kd, d = cy["rep"]; v |= 1 << 107 | kd << 108 | (d["tok"] & LG.M32) << 110 | (d.get("qty", 0) & 0xFFFF) << 142
            if "cfg" in cy:
                a, u = cy["cfg"]; v |= 1 << 158 | a << 159 | u["maxlong"] << 163 | u["maxshort"] << 179 | u["maxqty"] << 195 | u["maxonot"] << 211 | u["maxnot"] << 243 | u["cap"] << 277
            if "band" in cy: s, lo, hi = cy["band"]; v |= 1 << 285 | s << 286 | lo << 290 | hi << 306
            v |= cy.get("arm", 0) << 322 | cy.get("disarm", 0) << 323 | cy.get("kill", 0) << 324
            f.write("%082x\n" % v)
    return len(res["lines"])
def selftest():
    """one order through every outcome, worked by hand (NT 2, 2 accounts, 2 symbols, R 4)"""
    u = dict(maxlong=100, maxshort=100, maxqty=50, maxonot=10000, maxnot=100000, cap=5)
    setup = [dict(cfg=(0, u)), dict(cfg=(1, u)), dict(band=(0, 1, 100)), dict(band=(1, 1, 100)), dict(arm=1), {}, {}]
    o = lambda t, q=10, px=20, a=0, s=0, sd=BUY: dict(tok=t, acct=a, sym=s, side=sd, px=px, qty=q)
    cyc = setup + [dict(ord=o(1))] + [{}] * 8                                           # accepted by both
    S = run(cyc, 2, 2, 2)["sys"]; assert S.T.nlive() == 1 and S.g.ob[0][0] == 10 and S.g.notional[0] == 200 and S.bad == 0
    cyc = setup + [dict(ord=o(1)), dict(ord=o(1))] + [{}] * 12                          # the second has the same token: the gate charges, the tracker refuses, the charge is given back
    r = run(cyc, 2, 2, 2); S = r["sys"]; ds = [(row[3]) for row in r["rows"] if row[2]]
    assert ds == [0, 16 + LG.DUPTOK] and S.T.nlive() == 1 and S.g.ob[0][0] == 10 and S.g.notional[0] == 200 and S.bad == 0 and S.checks > 0, ds
    cyc = setup + [dict(ord=o(1, 200))] + [{}] * 6                                      # quantity above the limit: the gate refuses
    r = run(cyc, 2, 2, 2); assert [row[3] for row in r["rows"] if row[2]] == [RG.QTY] and r["sys"].T.nlive() == 0
    cyc = setup + [dict(ord=o(1)), {}, {}, {}, {}, {}, {}, {}, dict(rep=(LG.FILL, dict(tok=1, qty=4))), {}, {}, {}, dict(rep=(LG.CANCELED, dict(tok=1))), {}, {}, {}, {}]
    r = run(cyc, 2, 2, 2); S = r["sys"]; assert S.T.nlive() == 0 and S.g.ob[0][0] == 0 and S.g.os[0][0] == 0 and S.g.pos[0][0] == 4 and S.g.notional[0] == 0 and S.bad == 0   # filled 4 (position 4), the rest cancelled
    cyc = setup + [dict(rep=(LG.FILL, dict(tok=9, qty=1))), {}, {}, dict(ord=o(2))] + [{}] * 8                                # an unknown report: fault, then the gate is killed
    r = run(cyc, 2, 2, 2); assert r["sys"].T.fault and [row[3] for row in r["rows"] if row[2]] == [RG.KILL]
    # a release from the tracker and a give-back want the gate's port in the same cycle: the release goes first
    hit = 0
    for k in range(0, 14):
        cyc = setup + [dict(ord=o(1)), {}, {}, {}, {}, {}, dict(ord=o(1))] + [{}] * k + [dict(rep=(LG.FILL, dict(tok=1, qty=4)))] + [{}] * 12
        r = run(cyc, 2, 2, 2); S = r["sys"]; kinds = [row[8] for row in r["rows"] if row[7]]
        assert S.bad == 0 and S.g.ob[0][0] == 6 and S.g.pos[0][0] == 4, k
        if S.collide: hit += 1; assert kinds[-2:] == [FILL, CANCEL], (k, kinds)
    assert hit >= 1
    # the reconciliation check sees a difference in sells and in notional (the books are corrupted on purpose)
    r = run(setup + [dict(ord=o(1, sd=SELL)), {}, {}, {}, {}, {}, {}, {}], 2, 2, 2); S = r["sys"]; assert S.g.os[0][0] == 10 and S.bad == 0
    S.g.os[0][1] += 1; S.reconcile(); assert S.bad == 1
    r = run(setup + [dict(ord=o(1)), {}, {}, {}, {}, {}, {}, {}], 2, 2, 2); S = r["sys"]; S.g.notional[0] += 1; S.reconcile(); assert S.bad == 1
    r = run(setup + [dict(ord=o(1)), {}, {}, {}, {}, {}, {}, {}], 2, 2, 2); S = r["sys"]; S.g.ob[0][0] += 1; S.reconcile(); assert S.bad == 1
    return True
if __name__ == "__main__": print("selftest", selftest())
