#!/usr/bin/env python3
"""Chapter 25: the specification of the order tracker: what is live, what is left of it, and what has to be told to the risk gate when the exchange reports.
THE TABLE. NT entries; an order is in it from the moment the requester records it (NEW) until it is finished (filled, cancelled, rejected). Per entry: token (32 bits), account, symbol, side, the order's PRICE (the price the gate was charged), the REMAINING quantity, and a state: PENDING_NEW (sent, not acknowledged), LIVE (acknowledged), PENDING_CANCEL (a cancel was asked for). A finished order leaves the table, so a later report for its token is a report for an UNKNOWN token.
LOCAL EVENTS (from the requester): NEW(token, account, symbol, side, price, qty) records an order: ZERO if qty = 0, DUPTOK if the token is in the table, FULL if there is no free entry (the order must then NOT be sent), else OK (which entry is used is not observable). CANCELREQ(token): UNKNOWN if not in the table; BADSTATE unless LIVE; LIVE becomes PENDING_CANCEL (OK). Local refusals change nothing and are not faults.
REPORTS (from the exchange): ACK(token): PENDING_NEW becomes LIVE (anything else: BADSTATE). FILL(token, qty): qty = 0 is ZERO; qty above the remaining quantity is OVERFILL; else the remaining quantity falls by qty (a PENDING_NEW order becomes LIVE: a fill is an implicit acknowledgement), and a FILL release (account, symbol, side, the ORDER's price, qty) is sent to the gate; at zero the order leaves the table. CANCELED(token): the whole remaining quantity is released to the gate (a CANCEL release) and the order leaves (any state). REJECT(token): only in PENDING_NEW (else BADSTATE): the quantity is released (CANCEL) and the order leaves. A report for a token not in the table is UNKNOWN. Any report that is not OK (UNKNOWN, BADSTATE, ZERO, OVERFILL) changes nothing, sends no release and sets the sticky FAULT: the exchange and the books disagree, and nothing is believed until reset (it fails closed; the system wires FAULT to the gate's kill).
RELEASES (to the gate, Chapter 23's events): FILL(type 1) moves the position and releases open quantity and notional; CANCEL (type 2) releases without moving the position. The release carries the order's own price, so the notional released is exactly the notional charged when the order was accepted.
TIME. One event per cycle; a report wins over a local event offered in the same cycle (the local event is held, `ready` is low). An event in cycle c is applied at the end of c; its answer, release and the new count of live orders are visible in cycle c + 1."""
import random
NEW, CANCELREQ = range(2)
ACK, FILL, CANCELED, REJECT = range(4)
LN = ["NEW", "CANCELREQ"]; RPN = ["ACK", "FILL", "CANCELED", "REJECT"]
OK, UNKNOWN, BADSTATE, OVERFILL, ZERO, FULL, DUPTOK = range(7)
RN = ["OK", "UNKNOWN", "BADSTATE", "OVERFILL", "ZERO", "FULL", "DUPTOK"]
PNEW, LIVE, PCAN = range(3)
SN = ["PENDING_NEW", "LIVE", "PENDING_CANCEL"]
REL_FILL, REL_CANCEL = 1, 2
M32 = 0xFFFFFFFF
class Tracker:
    def __init__(self, nt): self.nt = nt; self.e = [None] * nt; self.fault = 0
    def find(self, tok):
        for i, x in enumerate(self.e):
            if x is not None and x["tok"] == tok: return i
        return None
    def nlive(self): return sum(x is not None for x in self.e)
    def local(self, kind, f):
        """-> (result, release or None)"""
        tok = f["tok"] & M32
        if kind == NEW:
            if f["qty"] == 0: return ZERO, None
            if self.find(tok) is not None: return DUPTOK, None
            free = [i for i, x in enumerate(self.e) if x is None]
            if not free: return FULL, None
            self.e[free[0]] = dict(tok=tok, acct=f["acct"], sym=f["sym"], side=f["side"], px=f["px"], rem=f["qty"], st=PNEW); return OK, None
        i = self.find(tok)
        if i is None: return UNKNOWN, None
        if self.e[i]["st"] != LIVE: return BADSTATE, None
        self.e[i]["st"] = PCAN; return OK, None
    def report(self, kind, f):
        tok = f["tok"] & M32; i = self.find(tok); anomaly = None; rel = None
        if i is None: anomaly = UNKNOWN
        else:
            x = self.e[i]
            if kind == ACK:
                if x["st"] != PNEW: anomaly = BADSTATE
                else: x["st"] = LIVE
            elif kind == FILL:
                q = f["qty"]
                if q == 0: anomaly = ZERO
                elif q > x["rem"]: anomaly = OVERFILL
                else:
                    x["rem"] -= q; x["st"] = LIVE if x["st"] == PNEW else x["st"]; rel = (REL_FILL, x["acct"], x["sym"], x["side"], x["px"], q)
                    if x["rem"] == 0: self.e[i] = None
            elif kind == CANCELED: rel = (REL_CANCEL, x["acct"], x["sym"], x["side"], x["px"], x["rem"]); self.e[i] = None
            else:
                if x["st"] != PNEW: anomaly = BADSTATE
                else: rel = (REL_CANCEL, x["acct"], x["sym"], x["side"], x["px"], x["rem"]); self.e[i] = None
        if anomaly is not None: self.fault = 1; return anomaly, None
        return OK, rel
def run(cycles, nt=4):
    """Closed loop. cycles[c] = dict(loc=(kind, dict), rep=(kind, dict)); a local event is held on the pins until accepted (a report in the same cycle wins and the local event waits); cycle 0 is the first cycle after reset. -> dict(rows, lines, tracker) with rows[c] = (ready, valid, source, result, release valid, type, account, symbol, side, price, qty, live count, fault) as visible in cycle c (the answer and the state come from the event of cycle c - 1); lines[c] = (the local event on the pins, the report on the pins)."""
    T = Tracker(nt); n = len(cycles); rows = []; lines = []; held = None; qi = 0
    locs = [(c, cy["loc"]) for c, cy in enumerate(cycles) if "loc" in cy]; pend = (0, 0, 0, None)
    for c in range(n + 3):
        cy = cycles[c] if c < n else {}
        if held is None and qi < len(locs) and locs[qi][0] <= c: held = locs[qi][1]; qi += 1
        rep = cy.get("rep"); ready = 0 if rep is not None else 1
        lines.append((held, rep))
        v, src, res, rel = pend
        rows.append((ready, v, src, res) + (((1,) + rel) if rel else (0,) * 7) + (T.nlive(), T.fault))
        if rep is not None: r_, rel_ = T.report(*rep); pend = (1, 1, r_, rel_)
        elif held is not None: r_, rel_ = T.local(*held); held = None; pend = (1, 0, r_, rel_)
        else: pend = (0, 0, 0, None)
    return dict(rows=rows, lines=lines, tracker=T)
def selftest():
    N = lambda t, a, s, sd, px, q: (NEW, dict(tok=t, acct=a, sym=s, side=sd, px=px, qty=q))
    cyc = [dict(loc=N(7, 1, 2, 0, 100, 10)),
           dict(rep=(ACK, dict(tok=7))),
           dict(rep=(FILL, dict(tok=7, qty=4))),
           dict(loc=(CANCELREQ, dict(tok=7))),
           dict(rep=(CANCELED, dict(tok=7, qty=0))),
           dict(rep=(FILL, dict(tok=7, qty=1)))]
    r = run(cyc)["rows"]
    assert r[1] == (0, 1, 0, OK, 0, 0, 0, 0, 0, 0, 0, 1, 0)
    assert r[3] == (1, 1, 1, OK, 1, REL_FILL, 1, 2, 0, 100, 4, 1, 0)
    assert r[4][:4] == (0, 1, 0, OK)
    assert r[5] == (0, 1, 1, OK, 1, REL_CANCEL, 1, 2, 0, 100, 6, 0, 0)
    assert r[6][3] == UNKNOWN and r[6][4] == 0 and r[6][12] == 1
    return True
def selftest2():
    """each rule of the specification, worked by hand on the tracker itself"""
    def new(t, q=10): T.local(NEW, dict(tok=t, acct=3, sym=4, side=1, px=50, qty=q))
    T = Tracker(2)
    assert T.local(NEW, dict(tok=1, acct=0, sym=0, side=0, px=5, qty=0)) == (ZERO, None) and T.nlive() == 0
    new(1); assert T.nlive() == 1 and T.e[0]["st"] == PNEW
    assert T.local(NEW, dict(tok=1, acct=0, sym=0, side=0, px=5, qty=1)) == (DUPTOK, None) and T.nlive() == 1
    assert T.local(CANCELREQ, dict(tok=1)) == (BADSTATE, None) and T.e[0]["st"] == PNEW        # not yet live
    assert T.local(CANCELREQ, dict(tok=9)) == (UNKNOWN, None) and not T.fault                   # a local refusal is not a fault
    new(2); assert T.local(NEW, dict(tok=3, acct=0, sym=0, side=0, px=5, qty=1)) == (FULL, None)
    assert T.report(FILL, dict(tok=1, qty=3)) == (OK, (REL_FILL, 3, 4, 1, 50, 3)) and T.e[0]["st"] == LIVE and T.e[0]["rem"] == 7   # a fill is an implicit ack
    assert T.report(FILL, dict(tok=1, qty=8))[0] == OVERFILL and T.fault and T.e[0]["rem"] == 7  # one too many, nothing changes
    T = Tracker(2); new(1); new(2); T.local(CANCELREQ, dict(tok=1))
    assert T.report(ACK, dict(tok=1)) == (OK, None) and T.e[0]["st"] == LIVE
    assert T.local(CANCELREQ, dict(tok=1)) == (OK, None) and T.e[0]["st"] == PCAN
    assert T.local(CANCELREQ, dict(tok=1)) == (BADSTATE, None)
    assert T.report(CANCELED, dict(tok=1)) == (OK, (REL_CANCEL, 3, 4, 1, 50, 10)) and T.find(1) is None and T.nlive() == 1
    assert T.report(REJECT, dict(tok=2)) == (OK, (REL_CANCEL, 3, 4, 1, 50, 10)) and T.nlive() == 0
    T = Tracker(2); new(1); T.report(ACK, dict(tok=1))
    assert T.report(REJECT, dict(tok=1))[0] == BADSTATE and T.fault and T.nlive() == 1           # a reject of a live order is an anomaly
    T = Tracker(2); new(1)
    assert T.report(FILL, dict(tok=1, qty=10)) == (OK, (REL_FILL, 3, 4, 1, 50, 10)) and T.nlive() == 0   # filled to zero while pending: leaves
    assert T.report(ACK, dict(tok=1))[0] == UNKNOWN
    return True
def write_stim(path, res):
    """one line per cycle, 128 bits as 32 hex digits: bit 0 local valid, 1 kind, 2..33 token, 34..37 account, 38..41 symbol, 42 side, 43..58 price, 59..74 quantity, 75 report valid, 76..77 kind, 78..109 token, 110..125 quantity. -> number of lines"""
    with open(path, "w") as f:
        for loc, rep in res["lines"]:
            v = 0
            if loc: k, d = loc; v |= 1 | k << 1 | (d["tok"] & M32) << 2 | d.get("acct", 0) << 34 | d.get("sym", 0) << 38 | d.get("side", 0) << 42 | (d.get("px", 0) & 0xFFFF) << 43 | (d.get("qty", 0) & 0xFFFF) << 59
            if rep: k, d = rep; v |= 1 << 75 | k << 76 | (d["tok"] & M32) << 78 | (d.get("qty", 0) & 0xFFFF) << 110
            f.write("%032x\n" % v)
    return len(res["lines"])
def expected_rows(res): return res["rows"]
if __name__ == "__main__": print("selftest", selftest(), selftest2())
