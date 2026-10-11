#!/usr/bin/env python3
"""Chapter 26: the specification of the wire-to-wire design (rtl/w2w.sv), composed from the specifications of the units it chains: model/itch_gold.py (the parser: which cycle each message appears in), model/book2_gold.py (the order book and the cycles an event takes), model/sig_gold.py and model/trig_gold.py (the signal and the trigger), model/sys_gold.py (the gate and the tracker of Chapter 25, stepped one cycle at a time) and model/sess_gold.py (the transmitter, here as a class that is stepped).
THE PATH OF A MESSAGE (cycle numbers are the testbench's; cycle 0 is the first after reset).
 PARSER   a message whose last byte is in cycle e appears (m_valid) in cycle E = e + 1 (Chapter 16: model/itch_gold.py `decode`).
 ADAPTER  in cycle E: A and F become ADD, E EXEC, X CANCEL, D DELETE, U REPLACE (S, P, unknown types, messages with an error, and any symbol (locate) of NS or more are dropped before the queue). The event (reference and new reference: the low 32 bits of the 64-bit references; shares and price as they are, for E and X the shares only, for D nothing) is pushed into a FIFO of QD entries in cycle E: if the FIFO is full in that cycle the message is DROPPED and counted. It is at the head from cycle E + 1.
 BOOK     in the first cycle a >= E + 1 in which the book is ready and the strategy slot is free, the head event is accepted (popped); the book takes n(event) cycles (Chapter 20) and its result and the top of book of the event's symbol are visible in cycle r = a + n.
 SIGNAL, TRIGGER  both are offered the result in cycle r (the trigger with the event as accepted: type, symbol index as the key, side, price, shares). The signal answers in cycle d = r + F + 4, the trigger in r + 4 + TPIPE (its `fire` is kept until d).
 STRATEGY in cycle d, with the slot busy from a to d (one message at a time between the book and here, so the FIFO and the slot are the only queues): if the trigger fired, the book applied the event (result OK), both sides are present, not crossed or locked, and the signal's imbalance is at least +THR (buy at the ask) or at most -THR (sell at the bid), an order of OQ shares at that price is offered to the lifecycle in cycle d ONLY: if the lifecycle is not ready (an order or a release is using it) the order is missed and counted. The order's token is a counter that counts the orders taken.
 LIFECYCLE the gate and tracker of Chapter 25 (model/sys_gold.py): an accepted order is answered (d_valid, d_res = 0 means send) 5 cycles after it is offered if both accept.
 TRANSMITTER an answer of 0 is offered to the transmitter in the cycle it appears and, if the transmitter is not ready, in every following cycle until it accepts (the order sent is the one taken last; one held order is enough: the next answer is at least 24 cycles later and the transmitter is busy for at most 31). A transmitter that refuses (session not ACTIVE) makes the design report a REJECT of that token to the tracker (an exchange report wins the report port; the REJECT waits), which gives the gate's charge back.
 The first byte of an order is on the wire in the cycle after the transmitter accepts it.
Every cycle the testbench prints the queue, the counters, the book's, the strategy's, the lifecycle's and the transmitter's outputs; the model reproduces every one."""
import os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import itch_gold as IG, book2_gold as BG, sig_gold as SGG, trig_gold as TG, sys_gold as SYG, life_gold as LG, risk_gold as RG, sess_gold as SS
M = 0xFFFFFFFF
class SessStep:
    """model/sess_gold.py `run`, one cycle at a time: step(req, rx, cfg) -> (row, accepted); req is the request on the pins in this cycle (or None)."""
    def __init__(self, w=8, ns=4, hb=20, tl=60):
        self.w, self.ns, self.hb, self.tl = w, ns, hb, tl; self.cfg = SS.new_cfg(ns); self.st = SS.IDLE; self.exp = 0; self.tx = b""; self.hbc = 0; self.rxc = 0; self.ltc = 0; self.ans = None; self.packets = []; self.c = 0
    def step(self, req, rx, cfgw):
        w = self.w; hb_due = self.st == SS.ACTIVE and self.hbc >= self.hb; ready = 1 if (len(self.tx) <= w and not hb_due) else 0; tx = self.tx
        data = int.from_bytes(tx[:w] + b"\0" * (w - len(tx[:w])), "big") if tx else 0
        row = (ready, 1 if tx else 0, data, 1 if (tx and len(tx) <= w) else 0, min(len(tx), w), self.st, self.exp, 1 if self.ans is not None else 0, self.ans if self.ans is not None else 0)
        tx = tx[w:]; loaded = False; new_ans = None; acc = None; accepted = False; st = self.st
        if hb_due and len(tx) == 0: tx = SS.packet(SS.HEARTBEAT, None, self.cfg, self.ns); loaded = True; self.packets.append((self.c, SS.HEARTBEAT, tx))
        elif req is not None and ready:
            kind, r = req; accepted = True; allowed = (st == SS.IDLE) if kind == SS.LOGINQ else (st == SS.ACTIVE)
            if not allowed: new_ans = SS.REFUSED
            elif kind == SS.ORDER and r["sym"] >= self.ns: new_ans = SS.BADSYM
            else: new_ans = SS.OK; tx = SS.packet(kind, r, self.cfg, self.ns); loaded = True; acc = kind; self.packets.append((self.c, kind, tx))
        nst = st; heard = False
        if rx is not None:
            t, sq = rx
            if st == SS.LOGIN and t == "A": nst = SS.ACTIVE; self.exp = sq
            elif st == SS.LOGIN and t == "J": nst = SS.REJECTED
            elif t == "Z" and st in (SS.LOGIN, SS.ACTIVE): nst = SS.CLOSED
            elif st == SS.ACTIVE and t == "H": heard = True
            elif st == SS.ACTIVE and t == "S":
                if sq == self.exp: self.exp = (self.exp + 1) & M; heard = True
                else: nst = SS.GAP
        if st == SS.LOGIN and nst == SS.LOGIN:
            self.ltc += 1
            if self.ltc >= self.tl: nst = SS.DEAD
        if st == SS.ACTIVE and nst == SS.ACTIVE:
            self.rxc = 0 if heard else self.rxc + 1
            if self.rxc >= 3 * self.hb: nst = SS.DEAD
        if nst == SS.ACTIVE: self.hbc = 0 if (loaded or st != SS.ACTIVE) else self.hbc + 1
        else: self.hbc = 0
        if acc == SS.LOGINQ: nst = SS.LOGIN; self.ltc = 0
        elif acc == SS.LOGOUT: nst = SS.CLOSED
        if cfgw is not None: SS.apply_cfg(self.cfg, cfgw)
        self.st = nst; self.ans = new_ans; self.tx = tx; self.c += 1
        return row, accepted
def to_event(m):
    """the adapter: a parser message (type, fields) -> a book event, or None"""
    t, f = m
    if t in (ord("A"), ord("F")): return dict(t=BG.ADD, ref=f["ref"] & M, ref2=0, sym=f["locate"], side=int(f["side"] == ord("S")), px=f["price"], sh=f["shares"])
    if t == ord("E"): return dict(t=BG.EXEC, ref=f["ref"] & M, ref2=0, sym=f["locate"], side=0, px=0, sh=f["shares"])
    if t == ord("X"): return dict(t=BG.CANCEL, ref=f["ref"] & M, ref2=0, sym=f["locate"], side=0, px=0, sh=f["shares"])
    if t == ord("D"): return dict(t=BG.DELETE, ref=f["ref"] & M, ref2=0, sym=f["locate"], side=0, px=0, sh=0)
    if t == ord("U"): return dict(t=BG.REPLACE, ref=f["ref"] & M, ref2=f["newref"] & M, sym=f["locate"], side=0, px=f["price"], sh=f["shares"])
    return None
class W2W:
    def __init__(self, ns=4, na=4, nt=4, qd=8, f=12, tpipe=1, thr=512, oq=10, w=8, hb=20, tl=60, nb=8, k=4, d=8, tnb=8, tk=2):
        self.ns, self.qd, self.f, self.tpipe, self.thr, self.oq = ns, qd, f, tpipe, thr, oq
        self.book = BG.Book2(ns, d, nb, k); self.busy_until = nb * k; self.pend = None                       # (result cycle, result, sym, top)
        self.fifo = []; self.slot = 0; self.drops = 0; self.h = None; self.sig_at = {}; self.look = {}; self.tg_out = {}
        self.table = TG.Table(tnb, tk); self.rules = [TG.new_rule() for _ in range(4)]; self.tnb = tnb
        self.t_fire = 0; self.r_okres = 0; self.r_sym = 0
        self.S = SYG.Sys(nt, na, ns, 4); self.X = SessStep(w, ns, hb, tl)
        self.tokc = 1; self.o_tok = 0; self.o = None; self.miss = 0; self.refused = 0; self.rej_pend = 0; self.snd_hold = 0; self.ord_q = 0; self.c = 0; self.ans_prev = (0, 0); self.orders = []
        self.xrow = (0,) * 9; self.cur = None; self.log = {}; self.accs = []; self.waits = []; self.ns_list = []
    def step(self, cy, mev):
        """cy: the control plane and exchange inputs of this cycle; mev: the parser message in this cycle (a book event or None, already filtered by the adapter's rules) -> the tuple the testbench prints"""
        c = self.c; S = self.S; pre = (self.drops, self.miss, self.refused, self.snd_hold, self.rej_pend, self.tokc & 0xFFFF)        # the registers as the testbench sees them in this cycle
        # ---- the adapter and the queue
        full = len(self.fifo) == self.qd; push = 0
        if mev is not None:
            if full: self.drops += 1
            else: push = 1
        bk_in_valid = len(self.fifo) != 0 and not self.slot; bk_ready = c >= self.busy_until; acc = bk_in_valid and bk_ready
        fcnt = len(self.fifo)
        # ---- the book's result in this cycle
        bkv = 0; bkres = 0; sgv = 0; res_now = None
        if self.pend and self.pend[0] == c: res_now = self.pend; self.pend = None; bkv = 1; bkres = res_now[1]
        # ---- the trigger's answer (the rules as of the writes up to cycle a + 1, the table as of cycle a), and the signal's
        if c - 2 in self.look:
            fnd, idx, m = self.look.pop(c - 2); mask, fire, first = TG.evaluate(self.rules, m, fnd, idx); self.tg_out[c - 2 + 4 + self.tpipe] = fire
        tg_v = c in self.tg_out; tg_fire = self.tg_out.pop(c) if tg_v else 0
        sg = self.sig_at.pop(c, None); sgv = 1 if sg is not None else 0
        # ---- the strategy (cycle d)
        ordv = 0; dec = None
        if sg is not None:
            ok, mid2, spread, cross, lock, wv, imb, micro = sg
            if ok and not cross and not lock and self.t_fire and self.r_okres:
                if imb >= self.thr: dec = (0, (mid2 + spread) >> 1)
                elif imb <= -self.thr: dec = (1, (mid2 - spread) >> 1)
        ordv = 1 if dec is not None else 0
        # ---- the lifecycle (Chapter 25's model, one cycle)
        scy = {}
        if dec is not None: scy["ord1"] = dict(tok=self.tokc, acct=0, sym=self.r_sym, side=dec[0], px=dec[1] & 0xFFFF, qty=self.oq)
        if "rep" in cy: scy["rep"] = cy["rep"]
        elif self.rej_pend: scy["rep"] = (LG.REJECT, dict(tok=self.o_tok, qty=0))
        for k in ("cfg", "band", "arm", "disarm", "kill"):
            if k in cy: scy[k] = cy[k]
        srow = S.step(scy); ordacc = int(ordv and S.accepted_once)
        d_valid, d_res = srow[2], srow[3]
        # ---- the transmitter
        snd_now = (d_valid and d_res == 0) or self.snd_hold; cq = cy.get("cq")
        req = None
        if cq is not None: req = (cq, {})
        elif snd_now: req = (SS.ORDER, dict(tok=self.o_tok, tok2=0, sym=self.o[0] if self.o else 0, side=self.o[1] if self.o else 0, shares=self.oq, px=self.o[2] if self.o else 0, tif=0))
        xrow, taken = self.X.step(req, cy.get("rx"), cy.get("sc"))
        if d_valid and d_res == 0 and srow[4] in self.log: self.log[srow[4]]['ca'] = c
        if taken and cq is None and snd_now and self.o_tok in self.log and self.X.ans == SS.OK: self.log[self.o_tok]['cx'] = c      # accepted and packed: it will be on the wire
        tx_ready = xrow[0]
        # ---- the registers at the end of the cycle
        if push: self.fifo.append((mev, c))
        if acc:
            e, pc = self.fifo.pop(0); cyc, r_, s_ = self.book.event(e); self.busy_until = c + cyc; self.pend = (c + cyc, r_, s_, self.book.top(s_)); self.h = e; self.slot = 1; self.accs.append(c); self.waits.append(c - (pc + 1)); self.ns_list.append(cyc); self.cur = dict(E=pc, a=c, n=cyc, r=c + cyc, d=c + cyc + self.f + 4, t=e["t"], res=r_)
        elif sgv: self.slot = 0
        if res_now is not None:
            _, r_, s_, top = res_now; bpx, bsh, apx, ash = top[0], top[1], top[2], top[3]
            self.sig_at[c + self.f + 4] = SGG.compute(bpx & 0xFFFFFF, bsh & 0xFFFFF, apx & 0xFFFFFF, ash & 0xFFFFF, self.f)
            h = self.h; self.look[c] = (*self.table.lookup(h["sym"]), dict(t=h["t"], key=h["sym"], side=h["side"], px=h["px"], sh=h["sh"]))
            self.r_okres = int(r_ == BG.OK); self.r_sym = s_
        if tg_v: self.t_fire = tg_fire
        if "tc" in cy: r, u = cy["tc"]; self.rules[r] = dict(u)
        if "tl" in cy: a, v, key, i = cy["tl"]; self.table.write(a, v, key, i)
        if ordacc:
            self.o = (self.r_sym, dec[0], dec[1] & 0xFFFF); self.o_tok = self.tokc; self.tokc += 1; self.orders.append((c, self.o_tok, dec[0], dec[1] & 0xFFFF)); self.log[self.o_tok] = dict(self.cur)
        if ordv and not S.accepted_once: self.miss += 1
        self.ord_q_new = int(bool(snd_now) and tx_ready and cq is None)
        rv, ores = xrow[7], xrow[8]
        if rv and self.ord_q and ores != 0: self.rej_pend = 1; self.refused += 1
        elif self.rej_pend and "rep" not in cy: self.rej_pend = 0
        if snd_now and not tx_ready and cq is None: self.snd_hold = 1
        elif self.snd_hold and tx_ready: self.snd_hold = 0
        self.ord_q = self.ord_q_new
        self.c += 1
        return (fcnt, pre[0], push, int(acc), bkv, bkres if bkv else 0, sgv, ordv, ordacc) + pre[1:] + tuple(srow) + tuple(xrow)
NS = 4; P0 = 120; SHT = 30          # symbols, the cycle the feed starts, the trigger's share threshold

RULE = lambda: dict(TG.new_rule(), en=1, tmask=0b00001, symany=0, symmask=0b0111, sideany=1, pxop=TG.ANY, shop=TG.GE, shval=SHT)      # the trigger: an ADD of SHT shares or more in a symbol of the table
def preamble(rng):
    cy = [dict() for _ in range(P0)]; c = 10
    for i in range(NS): cy[c + i]["sc"] = (0, i, int.from_bytes(b"SY%dX" % i, "big"))
    cy[c + 4]["sc"] = (1, 0, int.from_bytes(b"USER", "big")); cy[c + 5]["sc"] = (2, 0, int.from_bytes(b"PASS", "big")); cy[c + 6]["sc"] = (3, 0, int.from_bytes(b"FIRM", "big")); cy[c + 7]["sc"] = (4, 0, 0x5943); cy[c + 8]["sc"] = (5, 0, 1000)
    u = dict(maxlong=rng.randint(800, 4000), maxshort=rng.randint(800, 4000), maxqty=200, maxonot=2000 * 1100, maxnot=60000000, cap=8)
    for a in range(4): cy[c + a]["cfg"] = (a, dict(u) if a == 0 else dict(u, maxqty=5))                    # only account 0 may send an order of 10 shares
    for s_ in range(NS): cy[c + 4 + s_]["band"] = (s_, 800, 1200 if s_ < 3 else 900)                       # symbol 3's band excludes the prices traded: the gate refuses (BAND)
    t = TG.Table(8, 2)
    for key in range(NS): addr = t.place(key); t.write(addr, 1, key, key); cy[c + 10 + key]["tl"] = (addr, 1, key, key)
    cy[c + 15]["tc"] = (0, RULE())
    cy[c + 16]["tc"] = (1, dict(TG.new_rule(), en=1, tmask=0b00010, symmask=0b1111, sideany=1, shop=TG.GE, shval=40))                                  # an EXEC of 40 shares or more, any symbol
    cy[c + 17]["tc"] = (2, dict(TG.new_rule(), en=1, tmask=0b10000, symmask=0b1111, sideany=1, pxop=TG.GE, pxval=1000, shop=TG.GE, shval=20))            # a REPLACE at 1000 or more, 20 shares or more
    cy[c + 18]["tc"] = (3, dict(TG.new_rule(), en=1, tmask=0b00001, symmask=0b1111, sideany=0, side=1, shop=TG.GE, shval=150))                         # an ADD on the ask side of 150 shares or more
    cy[c + 30]["arm"] = 1; cy[c + 40]["cq"] = SS.LOGINQ; cy[c + 60]["rx"] = ("A", 1000)
    return cy
def _build(msgs, hb_until=None, between=(60, 60), packets=None, tail=160):
    """a scenario from a list of messages, one per packet (or the packet sizes given), the trading session kept alive by server heartbeats until hb_until"""
    rng = random.Random(5); pk = []; i = 0
    for n in (packets or [1] * len(msgs)): pk.append(dict(data=IG.build_packet(rng, msgs[i:i + n]), eop=True, reset_at=None)); i += n
    lines, info = IG.schedule(rng, pk, gap=0.0, stray=0.0, between=between); mev = parse_events(info, NS, shift=P0)
    cycles = preamble(rng) + [dict() for _ in range(len(lines) + tail)]
    for j, (v, sop, eop, d, _) in enumerate(lines): cycles[P0 + j]["s"] = (v, sop, eop, d)
    for c in range(80, len(cycles), 30):
        if hb_until is None or c < hb_until: cycles[c]["rx"] = ("H", 0)
    return cycles, mev
def _a(rng, loc, ref, side, sh, px): return IG.build_msg(rng, "A", locate=loc, ref=ref, side=ord(side), shares=sh, price=px)
def directed():
    """One scenario worked by hand, and the numbers it must give. The feed: an ADD of an ask (10 shares at 1001) and then an ADD of a bid (100 shares at 999), each in its own packet. The second message fires the trigger (100 >= SHT shares), the book then has both sides, the imbalance is (100 - 10) / 110 = 0.82 >= 0.25, so a BUY of OQ shares at the ask (1001) is offered. Hand-derived times, with E the cycle the second message appears (the cycle after its last byte): accepted at E + 1 (the queue is empty and the book idle); an ADD on an empty side takes 1 (accept) + (K + 2 = 6) (lookup) + 2 (level search at index 0) + 1 (write level) + 1 (write order) = 11 cycles, so the result is at r = E + 12; the signal answers F + 4 = 16 cycles later, d = E + 28, when the order is offered; the gate and tracker answer 5 cycles after that; the transmitter accepts it in that cycle and the first byte is on the wire in the next: E + 28 + 5 + 1 = E + 34; the 31 bytes leave as 8, 8, 8, 7."""
    rng = random.Random(5)
    return _build([_a(rng, 1, 11, "S", 10, 1001), _a(rng, 1, 12, "B", 100, 999)])
def directed_edge():
    """The threshold exactly: symbol 1 gets an ask of 70 and a bid of 90 (w = 90 / 160 = 9 / 16, imbalance +512 = +THR: a BUY at 1001); symbol 2 a bid of 70 and an ask of 90 (imbalance -512 = -THR: a SELL at 999); then the bid of symbol 1 is added AGAIN (the book answers DUPREF, changes nothing, the trigger fires again): no third order."""
    rng = random.Random(5)
    return _build([_a(rng, 1, 21, "S", 70, 1001), _a(rng, 1, 22, "B", 90, 999), _a(rng, 1, 22, "B", 90, 999), _a(rng, 2, 31, "B", 70, 999), _a(rng, 2, 32, "S", 90, 1001)])
def directed_dead():
    """The `hand` scenario with the server falling silent after one heartbeat: the session is DEAD (no heartbeat for 3 HB cycles) before the order, the transmitter refuses it, the design turns the refusal into a REJECT, and the tracker gives the gate's charge back."""
    c, m = directed(); rng = random.Random(5)
    return _build([_a(rng, 1, 11, "S", 10, 1001), _a(rng, 1, 12, "B", 100, 999)], hb_until=100)
def directed_dead2():
    """The session dies between two orders and an exchange report arrives in the very cycle the design's own REJECT is waiting for the report port. Messages: the `hand` pair (the first order is sent while the session is alive), then the same bid again as a new order (ref 13) after the session has died: the transmitter refuses the second order; the design turns it into a REJECT; the exchange's FILL of 2 shares of the first order is made to arrive in the cycle the REJECT is pending: the report wins the port, the REJECT waits one cycle and is applied. Afterwards: the first order has 8 shares left (the gate's open buys: 8), the second order is gone, no fault."""
    rng = random.Random(5)
    msgs = [_a(rng, 1, 11, "S", 10, 1001), _a(rng, 1, 12, "B", 100, 999), _a(rng, 1, 13, "B", 100, 999)]
    c0, m0 = _build(msgs); es = sorted(m0); cycles, mev = _build(msgs, hb_until=es[1] + 30)
    X = W2W(); at = None
    for c in range(len(cycles)):
        X.step(cycles[c], mev.get(c))
        if X.rej_pend and at is None: at = c
    assert at is not None
    cycles[at + 1]["rep"] = (LG.FILL, dict(tok=1, qty=2))                                      # X.rej_pend after the step of cycle `at` is what cycle at + 1 sees
    return cycles, mev
def directed_queue():
    """Five DELETE messages (unknown references) in one packet, 21 cycles apart, with a queue of TWO entries and F = 32. An unknown reference costs the book 1 + K + 2 = 7 cycles, and the strategy slot is held for n + F + 4 = 43 cycles from the accept. The first is accepted at E1 + 1; the second and third are queued (E1 + 21, E1 + 42); the second is accepted when the slot frees, E1 + 1 + 43 + 1 = E1 + 45, and the fourth is queued (E1 + 63); the fifth arrives at E1 + 84 with the queue full (the third and fourth) and is DROPPED. The accepts are E1 + 1, 45, 89 and 133."""
    rng = random.Random(5)
    c, m = _build([IG.build_msg(rng, "D", locate=0, ref=999) for _ in range(5)], packets=[5], tail=300)
    return c, m, dict(qd=2, f=32)
def selftest():
    cycles, mev = directed(); r = run(cycles, mev); X = r["w2w"]; rows = r["rows"]; E = sorted(mev)[1]
    assert len(X.orders) == 1 and X.orders[0][1:] == (1, 0, 1001), X.orders
    lg = X.log[1]; assert (lg["E"], lg["a"], lg["n"], lg["r"], lg["d"], lg["ca"], lg["cx"]) == (E, E + 1, 11, E + 12, E + 28, E + 33, E + 33), lg
    beats = [(c, row[14 + 18 + 4], row[14 + 18 + 1], row[14 + 18 + 3]) for c, row in enumerate(rows) if row[14 + 18 + 1] and c > E + 30]
    beats = beats[:4]; assert [b[0] for b in beats] == [E + 34 + i for i in range(4)] and [b[1] for b in beats] == [8, 8, 8, 7] and [b[3] for b in beats] == [0, 0, 0, 1], beats
    assert X.S.g.ob[0][1] == 10 and X.S.T.nlive() == 1 and X.drops == 0 and X.miss == 0 and rows[E + 40][14 + 18 + 5] == SS.ACTIVE
    cycles, mev = directed_edge(); X = run(cycles, mev)["w2w"]
    assert [o[1:] for o in X.orders] == [(1, 0, 1001), (2, 1, 999)], X.orders
    cycles, mev = directed_dead(); r = run(cycles, mev); X = r["w2w"]
    assert len(X.orders) == 1 and X.refused == 1 and X.S.T.nlive() == 0 and X.S.g.ob[0][1] == 0 and X.S.g.notional[0] == 0 and r["rows"][-1][14 + 18 + 5] == SS.DEAD and not any(p[1] == SS.ORDER for p in X.X.packets)
    cycles, mev = directed_dead2(); r = run(cycles, mev); X = r["w2w"]
    assert [o[1] for o in X.orders] == [1, 2] and X.refused == 1 and X.S.T.nlive() == 1 and X.S.T.e[0] is not None and X.S.T.e[0]["rem"] == 8 and X.S.g.ob[0][1] == 8 and not X.S.T.fault and X.S.g.notional[0] == 8 * 1001
    cycles, mev, kw = directed_queue(); X = run(cycles, mev, **kw)["w2w"]; E1 = sorted(mev)[0]
    assert X.drops == 1 and X.accs == [E1 + 1, E1 + 45, E1 + 89, E1 + 133], (X.drops, X.accs, E1)
    return True
def parse_events(packets, ns, shift=0):
    """cycle -> book event, for the messages the adapter keeps"""
    out = {}
    for e in IG.decode(packets):
        if e[0] == "M" and e[3] == 0:
            ev = to_event((e[2], e[6]))
            if ev is not None and ev["sym"] < ns: out[e[1] + shift] = ev
    return out
def run(cycles, mev, **kw):
    X = W2W(**kw); rows = []
    for c in range(len(cycles) + 8): rows.append(X.step(cycles[c] if c < len(cycles) else {}, mev.get(c)))
    return dict(rows=rows, w2w=X)
def _x(): pass
if __name__ == "__main__":
    # the stepped transmitter equals model/sess_gold.py run() on random traffic
    rng = random.Random(3)
    for trial in range(30):
        cyc = []; kinds = [SS.ORDER, SS.CANCEL, SS.REPLACE, SS.LOGINQ, SS.LOGOUT]
        for c in range(260):
            d = {}
            if rng.random() < .12: d["req"] = (rng.choice(kinds), dict(tok=rng.getrandbits(32), tok2=rng.getrandbits(32), sym=rng.randrange(5), side=rng.randrange(2), shares=rng.randint(1, 999), px=rng.randint(1, 999), tif=0))
            if rng.random() < .1: d["rx"] = (rng.choice("AHSHSJZ"), rng.choice([0, 1, 2, 5]))
            if c < 9: d["cfg"] = (rng.randrange(6), rng.randrange(4), rng.getrandbits(32))
            cyc.append(d)
        ref = SS.run(cyc, 8, 4, 20, 60); X = SessStep(8, 4, 20, 60); rows = []
        for c in range(len(ref["rows"])):
            held, rx, cfgw = ref["lines"][c]; row, _ = X.step(held, rx, cfgw); rows.append(row)
        assert rows == ref["rows"], trial
    print("selftest: the stepped transmitter equals sess_gold.run on 30 random sessions;", "the hand-worked scenario gives the hand-worked times:", selftest())
