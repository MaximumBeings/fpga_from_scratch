#!/usr/bin/env python3
"""Chapter 14: the design under test (DUT: tx_gold.Sender of Chapter 13, tcp_gold.TCB of Chapter 12) against the independent reference (ref_stack.py) over an impaired network. Three pairings, one tick per step, ONE event per tick for the DUT (as the hardware takes one):
  A  DUT sender  -> reference receiver   (both ends established; the DUT's data, retransmissions and timer meet an independent receiver)
  B  reference client -> DUT receiver    (the DUT's TCB does the handshake as passive opener, receives, closes: SYN_RCVD, ESTABLISHED, CLOSE_WAIT, LAST_ACK, CLOSED)
  C  DUT sender  -> DUT receiver         (the two designs of Chapters 12 and 13 against each other; the receiver is in ESTABLISHED, set up by a lossless handshake)
The DUT has no timer for CONTROL segments (SYN-ACK, FIN): `ctl_rto` > 0 switches on a shim in the harness that re-sends the DUT's last control segment after that many silent ticks; with ctl_rto = 0 the handshake can stall, and the harness reports it. Every run checks, after EVERY event, the invariants listed in `Monitor` and, at the end, that the byte stream the user receives is exactly the byte stream sent."""
import os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ref_stack as R, tx_gold as TX, tcp_gold as TC
M = 0xFFFFFFFF
PROFILES = {"clean": dict(), "loss 5%": dict(loss=0.05), "reorder 20%": dict(reorder=0.2), "duplicate 10%": dict(dup=0.1), "loss 5, reorder 10, dup 5": dict(loss=0.05, reorder=0.1, dup=0.05), "harsh: loss 15, reorder 30, dup 15": dict(loss=0.15, reorder=0.3, dup=0.15), "off-path noise 10%": dict(noise=0.1), "receive window 60 B, loss 5%": dict(win=60, loss=0.05)}
W = 4096
class Violation(Exception): pass
class Monitor:
    """Invariants of the sender after every event, and of the receiver. Raises Violation with the event number."""
    def __init__(self): self.n = 0; self.checks = 0; self.una = None; self.rcv = None
    def sender(self, s, e, a, tx, old):
        self.n += 1; una, nxt, mx, wnd, end = s.una, s.nxt, s.max, s.wnd, s.end
        def chk(c, msg):
            self.checks += 1
            if not c: raise Violation(f"event {self.n}: {msg}")
        chk(R.le(una, nxt) and R.le(nxt, mx) and R.le(mx, end), "SND.UNA <= SND.NXT <= SND.MAX <= end")
        if self.una is not None: chk(R.le(self.una, una), "SND.UNA never moves backwards")
        self.una = una
        if tx:
            sq, ln, rx = tx; chk(0 < ln <= s.mss, "segment length in 1..MSS"); chk(sq == old[1] or (e == TX.TICK and sq == old[0]), "a segment starts at SND.NXT (or at SND.UNA after a timeout)")
            chk(R.le((sq + ln) & M, end), "no byte beyond the application's data"); chk(bool(rx) == R.lt(sq, old[2]), "retransmission flag = start below the old SND.MAX")
        if e == TX.POLL and tx: chk(R.le((tx[0] + tx[1]) & M, (una + wnd) & M), "new data stays inside the peer's window")
        if e == TX.ACK: chk(not (R.lt(old[2], a) and una == a), "an ACK beyond SND.MAX is never accepted")
        chk(bool(s.timer_on) == (una != mx), "the retransmission timer runs exactly while data is outstanding")
    def receiver(self, t, ev_seq, ev_ln, dlv, rcv_before, iss_data, total, wnd):
        self.checks += 1
        if dlv:
            if ev_seq != rcv_before: raise Violation("data delivered from a segment that is not at RCV.NXT")
            if dlv > ev_ln: raise Violation("delivered more bytes than the segment carries")
            if dlv > wnd: raise Violation("delivered more bytes than the window offered")
            if (t.rcv - iss_data) & M > total: raise Violation("delivered more than was sent")
def forge_ack(rng, s):
    """An off-path ACK for the sender: never inside (SND.UNA, SND.MAX] (that one is indistinguishable from a real one) and never equal to SND.UNA (it would be taken as a window update): beyond SND.MAX, or before SND.UNA, with a random window."""
    k = rng.randrange(4)
    a = (s.max + rng.randint(1, 5000)) & M if k == 0 else (s.una - rng.randint(1, 3000)) & M if k == 1 else (s.max + (1 << 31)) & M if k == 2 else rng.getrandbits(32)
    if R.lt(s.una, a) and not R.lt(s.max, a) or a == s.una: a = (s.max + 1) & M
    return a, rng.getrandbits(16)
def forge_seg(rng, t, W=W):
    """An off-path segment for the receiver. ESTABLISHED: flags ACK, ACK + data, RST, SYN, SYN|ACK, at offsets from RCV.NXT inside the window, outside it, and far away, never an exact RST and never data at RCV.NXT. Other states: an ACK whose number is outside (SND.UNA, SND.NXT]."""
    if t.state == TC.ESTAB:
        f, ln = rng.choice([(TC.ACK, 0), (TC.ACK, 60), (TC.RST, 0), (TC.SYN, 0), (TC.SYN | TC.ACK, 0), (TC.ACK, 0)])
        off = rng.choice([-1, -100, 1, 7, W - 1, W, W + 50, rng.getrandbits(32), 0x80000000])
        if off == 0 and (f & TC.RST or ln): off = 1
        ack = rng.choice([t.nxt, (t.nxt + 1) & M, (t.nxt - 1) & M, rng.getrandbits(32)]) & M
        return f, (t.rcv + off) & M, ack, ln
    ack = (t.nxt + rng.randint(1, 5000)) & M if rng.random() < .5 else (t.una - rng.randint(1, 3000)) & M
    return TC.ACK, (t.rcv + rng.choice([0, 3, -5, 100])) & M, ack, 0
def run_a(seed, total, prof, mss=100, rto=None, wnd=65535, params=None, isn=1000, awnd=2048):
    """DUT sender -> reference receiver."""
    prof = dict(prof); noise = prof.pop("noise", 0); rng = random.Random(seed ^ 0x5a5a); fwd = R.Channel(random.Random(seed * 2 + 1), **prof); bwd = R.Channel(random.Random(seed * 2 + 2), **prof)
    s = TX.Sender(isn=isn, mss=mss, wnd=wnd, **(params or {})); first = s.una; rcv = R.RefReceiver(first, awnd); mon = Monitor(); events = []; inbox = []; t = 0; tx_bytes = 0; nretx = 0; nseg = 0; nf = 0
    def ev(e, a=0, w=0):
        nonlocal tx_bytes, nretx, nseg
        old = (s.una, s.nxt, s.max); r = s.event(e, t, a, w); events.append((t, e, a, w)); mon.sender(s, e, a, r, old)
        if r: sq, ln, rx = r; fwd.send(t, (R.ACK, sq, 0, ln, 0)); nseg += 1; nretx += 1 if rx else 0; tx_bytes += ln
    ev(TX.WRITE, total)
    while t < 400000:
        t += 1
        out = []
        for sg in fwd.due(t): rcv.on_seg(t, sg, out)
        for sg in out: bwd.send(t, sg)
        inbox += bwd.due(t)
        if noise and rng.random() < noise and s.una != s.end: a, w = forge_ack(rng, s); inbox.append((R.ACK, 0, a, 0, w, True))
        if inbox: forged = inbox[0][5:] != (); f, sq, ack, ln, w, *_ = inbox.pop(0); u0, w0 = s.una, s.wnd; ev(TX.ACK, ack, w); forged and check_forged(s, u0, w0); nf += 1 if forged else 0
        else:
            avail = (s.end - s.nxt) & M; wl = (s.una + s.wnd - s.nxt) & M
            ev(TX.POLL) if avail > 0 and not (wl >> 31) and wl > 0 else ev(TX.TICK)
        if s.una == s.end and not inbox and bwd.empty() and fwd.empty(): break
    ok = bytes(rcv.buf) == R.stream(0, total) and s.una == s.end
    return dict(ok=ok, ticks=t, segs=nseg, retx=nretx, wire=tx_bytes, events=events, checks=mon.checks, delivered=len(rcv.buf), lost=fwd.lost + bwd.lost, duped=fwd.duped + bwd.duped, late=fwd.late + bwd.late, sender=s, forged=nf)
def check_forged(s, u0, w0):
    if s.una != u0 or s.wnd != w0: raise Violation("a forged ACK changed the sender's state")
def tcb_listen(iss_b=5000):
    t = TC.TCB(); t.event(TC.E_OPEN_P, iss=iss_b); return t
def run_b(seed, total, prof, mss=100, ctl_rto=300, fast=True, dut=None, iss=None):
    """Reference client -> DUT receiver (the DUT does the handshake and the close). Returns a dict; `stall` if the run does not finish."""
    prof = dict(prof); noise = prof.pop("noise", 0); Wr = prof.pop("win", W); rng = random.Random(seed ^ 0x3c3c); fwd = R.Channel(random.Random(seed * 2 + 1), **prof); bwd = R.Channel(random.Random(seed * 2 + 2), **prof)
    iss_a = random.Random(seed).getrandbits(32) if iss is None else iss; c = R.RefClient(iss_a, total, mss=mss, wnd=Wr, rto=200, fast=fast); t_ = dut or tcb_listen(); mon = Monitor(); evlog = [] if dut else [dict(e=TC.E_OPEN_P, cid=0, iss=5000)]; inbox = []; t = 0; out = []; got = 0; last_ctl = None; last_ctl_t = 0; closed_sent = False; nf = [0]; dstart = (iss_a + 1) & M
    c.start(0, out)
    for sg in out: fwd.send(0, sg)
    def deliver(e, forged=False, **k):
        nonlocal got, last_ctl, last_ctl_t
        before = t_.rcv; sq = k.get("seq", 0); ln = k.get("ln", 0); k.setdefault("wnd", Wr); st0 = t_.snapshot(); tx, d = t_.event(e, **k); evlog.append(dict(e=e, cid=0, **k))
        if forged:
            if t_.snapshot() != st0 or d: raise Violation("a forged segment changed the receiver's state or delivered data")
            nf[0] += 1; return
        if e == TC.E_SEG: mon.receiver(t_, sq, ln, d, before, (dstart) & M, total, k["wnd"])
        got += d
        if tx:
            bwd.send(t, (tx[0], tx[1], tx[2], 0, Wr))
            if tx[0] & (TC.SYN | TC.FIN): last_ctl = (tx[0], tx[1], tx[2], 0, Wr); last_ctl_t = t
    while t < 400000:
        t += 1
        out = []
        for sg in fwd.due(t): inbox.append(sg)
        if noise and rng.random() < noise and t_.state in (TC.ESTAB, TC.SYN_RCVD, TC.LAST_ACK, TC.CLOSE_WAIT): f, sq, ack, ln = forge_seg(rng, t_, Wr); inbox.append((f, sq, ack, ln, Wr, True))
        if inbox:
            f, sq, ack, ln, w, *fg = inbox.pop(0); deliver(TC.E_SEG, forged=bool(fg), f=f, seq=sq, ack=ack, ln=ln)
        elif t_.state == TC.CLOSE_WAIT and not closed_sent: closed_sent = True; deliver(TC.E_CLOSE)
        elif ctl_rto and last_ctl and t_.state in (TC.SYN_RCVD, TC.LAST_ACK) and t - last_ctl_t >= ctl_rto: bwd.send(t, last_ctl); last_ctl_t = t; evlog.append(dict(e="shim", t=t))
        for sg in bwd.due(t): c.on_seg(t, sg, out)
        c.tick(t, out)
        for sg in out: fwd.send(t, sg)
        if c.done() and t_.state == TC.CLOSED and not inbox: break
    ok = c.done() and t_.state == TC.CLOSED and got == total and (t_.rcv - dstart) & M == total + 1
    return dict(ok=ok, stall=not ok, ticks=t, segs=c.segs, retx=c.retx, got=got, state=TC.SNAME[t_.state], shim=sum(1 for x in evlog if x["e"] == "shim"), evlog=[x for x in evlog if x["e"] != "shim"], checks=mon.checks, lost=fwd.lost + bwd.lost, duped=fwd.duped + bwd.duped, late=fwd.late + bwd.late, forged=nf[0])
def run_c(seed, total, prof, mss=100, params=None, isn=1000):
    """DUT sender -> DUT receiver (ESTABLISHED by a lossless handshake)."""
    prof = dict(prof); noise = prof.pop("noise", 0); Wr = prof.pop("win", W); rng = random.Random(seed ^ 0x2d2d); fwd = R.Channel(random.Random(seed * 2 + 1), **prof); bwd = R.Channel(random.Random(seed * 2 + 2), **prof)
    s = TX.Sender(isn=isn, mss=mss, **(params or {})); first = s.una; tb = tcb_listen()
    tb.event(TC.E_SEG, f=TC.SYN, seq=(first - 1) & M, ack=0, ln=0, wnd=Wr); tb.event(TC.E_SEG, f=TC.ACK, seq=first, ack=(5000 + 1) & M, ln=0, wnd=Wr); assert tb.state == TC.ESTAB and tb.rcv == first
    evlog = [dict(e=TC.E_OPEN_P, cid=0, iss=5000), dict(e=TC.E_SEG, cid=0, f=TC.SYN, seq=(first - 1) & M, ack=0, ln=0, wnd=Wr), dict(e=TC.E_SEG, cid=0, f=TC.ACK, seq=first, ack=5001, ln=0, wnd=Wr)]
    mon = Monitor(); mon2 = Monitor(); events = []; inbox = []; rin = []; t = 0; got = 0; nseg = 0; nretx = 0; nf = 0
    def ev(e, a=0, w=0):
        nonlocal nseg, nretx
        old = (s.una, s.nxt, s.max); r = s.event(e, t, a, w); events.append((t, e, a, w)); mon.sender(s, e, a, r, old)
        if r: sq, ln, rx = r; fwd.send(t, (R.ACK, sq, 5001, ln, 0)); nseg += 1; nretx += 1 if rx else 0
    ev(TX.WRITE, total)
    while t < 400000:
        t += 1
        rin += fwd.due(t)
        if noise and rng.random() < noise: f, sq, ack, ln = forge_seg(rng, tb, Wr); rin.append((f, sq, ack, ln, Wr, True))
        if rin:
            f, sq, ack, ln, w, *fg = rin.pop(0); before = tb.rcv; st0 = tb.snapshot(); tx, d = tb.event(TC.E_SEG, f, sq, ack, ln, Wr); evlog.append(dict(e=TC.E_SEG, cid=0, f=f, seq=sq, ack=ack, ln=ln, wnd=Wr)); mon2.receiver(tb, sq, ln, d, before, first, total, Wr); got += d
            if fg:
                nf += 1
                if tb.snapshot() != st0 or d: raise Violation("a forged segment changed the receiver's state or delivered data")
            elif tx: bwd.send(t, (tx[0], tx[1], tx[2], 0, Wr))
        inbox += bwd.due(t)
        if noise and rng.random() < noise and s.una != s.end: a_, w_ = forge_ack(rng, s); inbox.append((R.ACK, 0, a_, 0, w_, True))
        if inbox: forged = inbox[0][5:] != (); f, sq, ack, ln, w, *_ = inbox.pop(0); u0, w0 = s.una, s.wnd; ev(TX.ACK, ack, w); forged and check_forged(s, u0, w0); nf += 1 if forged else 0
        else:
            avail = (s.end - s.nxt) & M; wl = (s.una + s.wnd - s.nxt) & M
            ev(TX.POLL) if avail > 0 and not (wl >> 31) and wl > 0 else ev(TX.TICK)
        if s.una == s.end and not inbox and not rin and bwd.empty() and fwd.empty(): break
    ok = got == total and s.una == s.end and tb.rcv == (first + total) & M
    return dict(ok=ok, ticks=t, segs=nseg, retx=nretx, got=got, events=events, evlog=evlog, checks=mon.checks + mon2.checks, lost=fwd.lost + bwd.lost, duped=fwd.duped + bwd.duped, late=fwd.late + bwd.late, forged=nf)
BATTERY = ("clean", "loss 5%", "reorder 20%", "duplicate 10%", "harsh: loss 15, reorder 30, dup 15", "off-path noise 10%", "receive window 60 B, loss 5%")
BUDGET = {('A', 'clean'): 198, ('B', 'clean'): 289, ('C', 'clean'): 198, ('A', 'loss 5%'): 942, ('B', 'loss 5%'): 1492, ('C', 'loss 5%'): 1693, ('A', 'reorder 20%'): 333, ('B', 'reorder 20%'): 6334, ('C', 'reorder 20%'): 3513, ('A', 'duplicate 10%'): 219, ('B', 'duplicate 10%'): 300, ('C', 'duplicate 10%'): 219, ('A', 'harsh: loss 15, reorder 30, dup 15'): 2155, ('B', 'harsh: loss 15, reorder 30, dup 15'): 8092, ('C', 'harsh: loss 15, reorder 30, dup 15'): 187111, ('A', 'off-path noise 10%'): 213, ('B', 'off-path noise 10%'): 301, ('C', 'off-path noise 10%'): 214, ('B', 'receive window 60 B, loss 5%'): 40263}                                                                          # (pairing, profile) -> the most ticks any of the battery's runs may take: 1.5 x the slowest run of the unmutated design
def battery(measure=False):
    """The Chapter 14 test as one function: -> None if the design under test and the reference agree everywhere, else a string naming the first check that failed. Checks: every run finishes with every byte once and in order; no invariant is violated; the profile really did lose / duplicate / delay segments; no run takes more than 1.5 x the ticks of the unmutated design (a transfer that completes but crawls is a failure of a different kind)."""
    worst = {}
    for nm in BATTERY:
        for lab, fn in (("A", run_a), ("B", run_b), ("C", run_c)):
            if lab == "C" and PROFILES[nm].get("win", W) < 100: continue    # a long transfer over a window below one segment crawls: a measured weakness (Chapter 14, Example B), not a pass/fail test
            if lab == "A" and "win" in PROFILES[nm]: continue                                   # (pairing A has no receive-window parameter)
            for sd in range(3):
                try: r = fn(sd, 5137, PROFILES[nm])
                except Violation as v: return f"invariant, {lab}, {nm}: {v}"
                except Exception as x: return f"crash, {lab}, {nm}: {type(x).__name__}"
                if not r["ok"]: return f"bytes or completion, {lab}, {nm}"
                pr = PROFILES[nm]
                if (pr.get("loss") and r["lost"] == 0 and sd == 0) or (pr.get("dup") and r["duped"] == 0 and sd == 0) or (pr.get("reorder") and r["late"] == 0 and sd == 0) or (pr.get("noise") and r["forged"] == 0 and sd == 0): return f"the profile '{nm}' impaired nothing"
                worst[(lab, nm)] = max(worst.get((lab, nm), 0), r["ticks"])
    if measure: return worst
    for k, v in worst.items():
        if k in BUDGET and v > BUDGET[k]: return f"time budget, {k[0]}, {k[1]}: {v} > {BUDGET[k]} ticks"
    return None
if __name__ == "__main__":
    for nm, pr in PROFILES.items():
        a = run_a(1, 5000, pr); b = run_b(1, 5000, pr); c = run_c(1, 5000, pr); print(f"{nm:36s} A {a['ok']} {a['ticks']:6d}  B {b['ok']} {b['ticks']:6d} {b['state']} shim={b['shim']}  C {c['ok']} {c['ticks']:6d}")
