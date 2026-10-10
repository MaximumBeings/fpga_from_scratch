#!/usr/bin/env python3
"""Chapter 18: the specification of the sequencer and A/B arbiter, cycle for cycle, and the closed loop around it.
A PACKET is (feed, seq, cnt): the header of a MoldUDP64 packet (Chapters 16 and 17) seen at the packet level; feed 0 = A, 1 = B, 2 = retransmission. Feeds A and B carry IDENTICAL packet streams (same seq, same cnt); a retransmission returns exactly the range that was requested, as one packet. Sequence numbers are 32 bits here and every comparison is modular. A packet with cnt = 0 is a heartbeat.
State: next (the sequence number the output is waiting for), PEND slots of packets that arrived ahead of it (seq, cnt, feed), a gap timer (tmr) and req (a retransmission request has been sent for the present gap).
ONE cycle (all decisions are taken from the state at the START of the cycle):
  rel   = the slot with seq == next, if any (a stored packet is now in order);
  gap   = some slot is valid and there is no rel; mind = the smallest (slot seq - next);
  timer: in a gap, when req = 0 and tmr = TO: REQUEST (seq = next, cnt = min(mind, 0xFFFF)), req := 1, tmr := 0; when req = 1 and tmr = TO2: SKIP (seq = next, cnt = mind), next := next + mind, req := 0, tmr := 0; otherwise tmr := tmr + 1. Outside a gap tmr := 0, req := 0.
  stall = rel or SKIP: the input is not accepted (ready = 0). Else an input packet is classified by d = seq - next:
    cnt = 0                          HB    heartbeat, no state change
    d = 0                            FWD   forwarded in order, next := next + cnt
    d behind (top bit set)           DUP if the packet ends at or before next, else BAD (overlaps next: outside the contract, reported)
    d ahead, a slot has this seq     DUP
    d ahead, a free slot             STORE in the lowest free slot
    d ahead, no free slot            OVF   dropped (the gap will be requested again when its turn comes)
  rel: the packet is released (REL), next := next + cnt, the slot is freed.
Outputs, registered, seen the cycle after: a decision (kind, seq, cnt, feed) for the input or the release, and a timer event (REQ or SKIP); and the state after the cycle (next, number of slots in use).
Outside the contract (not tested): packets whose ranges overlap a stored one, or a retransmission that overshoots a stored packet."""
import random
M = 0xFFFFFFFF
FWD, STORE, DUP, BAD, OVF, HB, REL = range(7)
KN = ["FWD", "STORE", "DUP", "BAD", "OVF", "HB", "REL"]
REQ, SKIP = 1, 2
def behind(d): return (d >> 31) & 1
class Arb:
    def __init__(self, init=1, pend=4, to=16, to2=64):
        self.next = init & M; self.pend = pend; self.to = to; self.to2 = to2; self.slots = [None] * pend; self.tmr = 0; self.req = 0
    def npend(self): return sum(1 for s in self.slots if s)
    def _rel(self):
        for i, s in enumerate(self.slots):
            if s and s[0] == self.next: return i
        return None
    def _mind(self): return min(((s[0] - self.next) & M for s in self.slots if s), default=None)
    def _timer(self):
        rel = self._rel(); mind = self._mind(); gap = mind is not None and rel is None
        if not gap: return None, 0, 0, (0, 0)
        if not self.req and self.tmr == self.to: return REQ, self.next, min(mind, 0xFFFF), (0, 1)
        if self.req and self.tmr == self.to2: return SKIP, self.next, mind, (0, 0)
        return None, 0, 0, (self.tmr + 1, self.req)
    def ready(self): return self._rel() is None and self._timer()[0] != SKIP
    def step(self, pkt):
        """pkt = (feed, seq, cnt) or None -> (consumed, decision or None, timer event or None). The decision is (kind, seq, cnt, feed)."""
        rel = self._rel(); tk, ts, tc, (ntmr, nreq) = self._timer(); gap = self._mind() is not None and rel is None
        dec = None; t = (tk, ts, tc) if tk else None; consumed = False
        if rel is not None:
            s = self.slots[rel]; dec = (REL, s[0], s[1], s[2]); self.slots[rel] = None; self.next = (self.next + s[1]) & M
        elif tk == SKIP: self.next = (self.next + tc) & M
        elif pkt is not None:
            consumed = True; f, q, c = pkt; d = (q - self.next) & M
            if c == 0: dec = (HB, q, c, f)
            elif d == 0: dec = (FWD, q, c, f); self.next = (self.next + c) & M
            elif behind(d): e = (d + c) & M; dec = (DUP if (behind(e) or e == 0) else BAD, q, c, f)
            elif any(s and s[0] == q for s in self.slots): dec = (DUP, q, c, f)
            elif None in self.slots: self.slots[self.slots.index(None)] = (q, c, f); dec = (STORE, q, c, f)
            else: dec = (OVF, q, c, f)
        if gap: self.tmr, self.req = ntmr, nreq
        else: self.tmr, self.req = 0, 0
        return consumed, dec, t
# ---------------------------------------------------------------- the closed loop
def make_source(rng, n, init=1, hb=0.05, maxcnt=20):
    """The exchange: n packets in sequence order (with some heartbeats): [(seq, cnt)]."""
    out = []; q = init & M
    for _ in range(n):
        if rng.random() < hb: out.append((q, 0)); continue
        c = rng.randint(1, maxcnt); out.append((q, c)); q = (q + c) & M
    return out
def arrivals(rng, src, loss_a=0.0, loss_b=0.0, dup=0.0, jitter=3, skew=0, spacing=4, rt_loss=0.0):
    """-> [(arrival cycle, feed, seq, cnt)] for feeds A and B: each packet i is sent at cycle spacing * i, delayed by 10 + skew (B only) + uniform(0, jitter) cycles, lost with the feed's probability, and delivered twice with probability dup (the copy a few cycles later)."""
    out = []
    for i, (q, c) in enumerate(src):
        for feed, loss in ((0, loss_a), (1, loss_b)):
            if rng.random() < loss: continue
            t = spacing * i + 10 + (skew if feed else 0) + rng.randint(0, jitter); out.append((t, feed, q, c))
            if rng.random() < dup: out.append((t + rng.randint(1, 6), feed, q, c))
    return out
def run(arr, init=1, pend=4, to=16, to2=64, rt=30, rt_loss=0.0, seed=1, maxcycles=400000, record=True):
    """Closed loop: the inputs arrive in the order of their arrival cycle, one is OFFERED per cycle (the oldest not yet accepted); a REQ makes the retransmission server answer after `rt` cycles with ONE packet of exactly the requested range (lost with probability rt_loss). -> dict(rows, ...)"""
    rng = random.Random(seed); a = Arb(init, pend, to, to2); queue = sorted(arr); qi = 0; pending = []; t = 0; rows = []; forwarded = []; reqs = []; skips = []; lines = []
    prev = (None, None); last_t = max((x[0] for x in arr), default=0)
    while t < maxcycles:
        while qi < len(queue) and queue[qi][0] <= t: pending.append(queue[qi][1:]); qi += 1
        offered = pending[0] if pending else None
        r = a.ready(); nxt_before, np_before = a.next, a.npend(); cons, dec, tev = a.step(offered)
        if cons: pending.pop(0)
        if record: lines.append(offered)
        rows.append((1 if r else 0, prev[0], prev[1], nxt_before, np_before))
        if dec and dec[0] in (FWD, REL): forwarded.append((t, dec[1], dec[2], dec[3]))
        if tev:
            (reqs if tev[0] == REQ else skips).append((t, tev[1], tev[2]))
            if tev[0] == REQ and rng.random() >= rt_loss: queue.append((t + rt, 2, tev[1], tev[2])); queue.sort(key=lambda x: x[0])                                      # the answer arrives after t, so the entries already consumed stay in front
        prev = (dec, tev); t += 1
        if t > last_t + 2000 + 3 * (to + to2) and not pending and a.npend() == 0 and a.tmr == 0: break
    rows.append((1, prev[0], prev[1], a.next, a.npend()))
    return dict(rows=rows, lines=lines, forwarded=forwarded, reqs=reqs, skips=skips, arb=a, cycles=t)
def check_stream(res, init=1):
    """The end-to-end property, at the level of MESSAGES: the ranges forwarded (FWD and REL, in the order of the forwarding) tile the sequence space from `init` without a gap or an overlap, except the ranges the arbiter SKIPPED (which it reported). -> None or a description. (A retransmission answers a whole gap with one packet, so the packets forwarded are not the source's packets. Where the stream STOPS is not checked: a packet dropped because the slots were full, with nothing after it to reveal the loss, is never asked for again: `tail` below measures it.)"""
    cur = init & M; skips = {s_: n for _, s_, n in res["skips"]}
    for t, q, c, f in res["forwarded"]:
        while cur in skips and cur != q: cur = (cur + skips.pop(cur)) & M
        if q != cur: return f"at cycle {t}: forwarded [{q}, +{c}) but the next message is {cur}"
        cur = (cur + c) & M
    return None
def tail(res, arr, init=1):
    """Messages that ARRIVED on A or B beyond the point where the forwarding stopped: -> (messages, first undelivered sequence number)."""
    cur = init & M
    for t, q, c, f in res["forwarded"]: cur = (q + c) & M
    for _, s_, n in res["skips"]: pass
    end = max(((q + c) & M for _, f, q, c in arr if c and f < 2), key=lambda x: (x - init) & M, default=cur)
    return (end - res["arb"].next) & M, res["arb"].next
def write_stim(path, lines, seed=1):
    """One line per cycle: the packet offered (feed, seq, cnt) or junk with valid = 0."""
    rng = random.Random(seed)
    with open(path, "w") as f:
        for p in lines:
            if p: f.write("%013x\n" % ((1 << 50) | (p[0] << 48) | (p[1] << 16) | p[2]))
            else: f.write("%013x\n" % ((rng.getrandbits(2) << 48) | (rng.getrandbits(32) << 16) | rng.getrandbits(16)))
    return len(lines)
def expected_rows(res):
    """The rows the testbench prints, as tuples of ints (cycle, ready, dv, dk, ds, dc, df, tv, tk, ts, tc, next, np)."""
    out = []
    for c, (r, dec, tev, nx, np_) in enumerate(res["rows"][:-1]):
        out.append((c, r, 1 if dec else 0, dec[0] if dec else 0, dec[1] if dec else 0, dec[2] if dec else 0, dec[3] if dec else 0, 1 if tev else 0, tev[0] if tev else 0, tev[1] if tev else 0, tev[2] if tev else 0, nx, np_))
    return out
if __name__ == "__main__":
    a = Arb(1, 4, 5, 9)
    def step(p): return a.step(p)
    c, d, t = step((0, 1, 3)); assert d[0] == FWD and a.next == 4                              # in order
    c, d, t = step((1, 1, 3)); assert d[0] == DUP                                              # the B copy
    c, d, t = step((0, 7, 2)); assert d[0] == STORE and a.npend() == 1                         # ahead: a gap of 3
    evs = [step(None)[2] for i in range(7)]
    assert evs[5] == (REQ, 4, 3) and sum(1 for e in evs if e) == 1, evs                        # the gap lasts TO = 5 cycles, then the request for [4, 7)
    c, d, t = step((2, 4, 3)); assert d[0] == FWD and a.next == 7                              # the retransmission fills it
    c, d, t = step(None); assert d[0] == REL and a.next == 9 and a.npend() == 0                # the stored packet is released
    c, d, t = step((0, 20, 1)); assert d[0] == STORE
    for i in range(5 + 9 + 2): c, d, t = step(None)
    assert a.next in (20, 21) and a.npend() <= 1                                                # no answer: SKIP, then release
    # the other classes: behind (DUP, BAD), heartbeat, full slots, a huge gap, a wrap, no input accepted while a release is possible
    b = Arb(100, 2, 4, 6)
    assert b.step((0, 50, 10))[1][0] == DUP and b.step((0, 95, 10))[1][0] == BAD and b.step((0, 100, 0))[1][0] == HB and b.step((0, 130, 0))[1][0] == HB and b.npend() == 0       # behind and ending before next; overlapping next; heartbeats
    assert b.step((0, 110, 5))[1][0] == STORE and b.step((1, 110, 5))[1][0] == DUP and b.step((0, 120, 5))[1][0] == STORE and b.step((0, 130, 5))[1][0] == OVF and b.npend() == 2
    big = Arb(1, 4, 2, 3); big.step((0, 70000, 3)); ev = [big.step(None)[2] for _ in range(4)]; assert ev[2] == (REQ, 1, 0xFFFF), ev                # a gap of 69,999 is requested as 65,535
    w = Arb(0xFFFFFFFE, 4, 99, 99); assert w.step((0, 0xFFFFFFFE, 3))[1][0] == FWD and w.next == 1 and w.step((0, 1, 2))[1][0] == FWD and w.step((1, 0xFFFFFFFE, 3))[1][0] == DUP       # sequence numbers wrap
    r = Arb(1, 4, 99, 99); r.step((0, 4, 2)); r.step(None); r.step((0, 1, 3)); assert r.next == 4 and r.ready() is False and r.step((0, 9, 1))[0] is False and r.next == 6   # a release is possible: the input waits one cycle
    print("arb_gold hand-checked scenarios passed")
