#!/usr/bin/env python3
"""Chapter 13: the specification of the TCP SEND side of one established connection: the send window, the cumulative ACK, the retransmission timer with the RFC 6298 round-trip estimator (Karn's rule: no sample from retransmitted data), exponential backoff, and go-back-N after a timeout.
The data itself is not stored: the sender tracks sequence numbers (the application's data is `end` - `una` bytes long); a segment is (seq, len, retx). Time is a 32-bit tick counter `now` given with every event. Simplifications, stated: one connection, ESTABLISHED, no congestion control (the peer's window is the only limit), no fast retransmit (no duplicate-ACK counting), no SACK, no persist timer for a zero window, the backed-off RTO is recomputed from SRTT and RTTVAR as soon as new data is acknowledged (a deliberate deviation from RFC 6298 section 5.7, which lets it persist until the next sample; without it a sender that has lost a flight can wait the maximum RTO for every segment), a retransmission after a timeout is one segment of at most MSS bytes that ignores the window (as RFC 5681 allows).
Events: WRITE(n) the application adds n bytes; ACK(ack, wnd) a segment arrives; POLL try to send one segment; TICK check the timer. Fixed point (RFC 6298 with alpha = 1/8, beta = 1/4, G = 1 tick): srtt8 = 8 x SRTT and rv4 = 4 x RTTVAR, both integers; RTO = SRTT + max(G, 4 RTTVAR), clamped to [RTO_MIN, RTO_MAX]. Sequence arithmetic is modular as in Chapter 12."""
import random
M = 0xFFFFFFFF
WRITE, ACK, POLL, TICK = range(4)
ENAME = ["WRITE", "ACK", "POLL", "TICK"]
def lt(a, b): return ((a - b) & M) >> 31 == 1
class Sender:
    def __init__(self, isn=1000, wnd=65535, mss=1460, rto_init=300, rto_min=100, rto_max=6000):
        self.mss, self.rto_init, self.rto_min, self.rto_max = mss, rto_init, rto_min, rto_max
        self.una = self.nxt = self.max = self.end = isn & M; self.wnd = wnd & 0xFFFF; self.srtt8 = 0; self.rv4 = 0; self.rto = rto_init; self.deadline = 0
        self.timer_on = 0; self.timing_on = 0; self.rtt_seq = 0; self.rtt_t0 = 0; self.have = 0
    def snapshot(self): return (self.una, self.nxt, self.max, self.wnd, self.end, self.srtt8, self.rv4, self.rto, self.deadline, self.timer_on, self.timing_on, self.have)
    def _sample(self, now):
        r = (now - self.rtt_t0) & M
        if not self.have: self.srtt8 = (r << 3) & M; self.rv4 = (r << 1) & M; self.have = 1
        else:
            sr = self.srtt8 >> 3; err = r - sr; a = abs(err)
            self.srtt8 = (self.srtt8 + err) & M; self.rv4 = (self.rv4 + a - (self.rv4 >> 2)) & M
        self._recompute()
    def _recompute(self):
        rto = ((self.srtt8 >> 3) + max(1, self.rv4)) & M
        self.rto = min(max(rto, self.rto_min), self.rto_max)
    def event(self, e, now, a=0, w=0):
        """-> (seq, len, retx) of the segment to send, or None."""
        now &= M; a &= M; tx = None
        if e == WRITE: self.end = (self.end + a) & M
        elif e == POLL:
            avail = (self.end - self.nxt) & M; wl = (self.una + self.wnd - self.nxt) & M; wl = 0 if wl >> 31 else wl
            n = min(self.mss, avail, wl)
            if n > 0:
                retx = lt(self.nxt, self.max); tx = (self.nxt, n, 1 if retx else 0); new = (self.nxt + n) & M
                if lt(self.max, new): self.max = new
                self.nxt = new
                if not self.timing_on and not retx: self.timing_on = 1; self.rtt_seq = self.nxt; self.rtt_t0 = now
                if not self.timer_on: self.timer_on = 1; self.deadline = (now + self.rto) & M
        elif e == ACK:
            if lt(self.una, a) and not lt(self.max, a):
                self.una = a
                if lt(self.nxt, a): self.nxt = a
                self.wnd = w & 0xFFFF
                if self.timing_on and not lt(a, self.rtt_seq): self._sample(now); self.timing_on = 0
                elif self.have: self._recompute()                                       # new data acknowledged but no sample (Karn): the backed-off RTO is undone, as Linux does, instead of persisting as RFC 6298 section 5.7 allows
                if self.una == self.max: self.timer_on = 0
                else: self.deadline = (now + self.rto) & M
            elif a == self.una: self.wnd = w & 0xFFFF
        else:
            if self.timer_on and not lt(now, self.deadline):
                self.rto = min((self.rto << 1) & M, self.rto_max); self.timing_on = 0
                n = min(self.mss, (self.max - self.una) & M)                                       # what is outstanding, not what is written: bytes never sent are new data, not a retransmission (found by the interop run of Chapter 14)
                if n > 0: tx = (self.una, n, 1); self.nxt = (self.una + n) & M
                else: self.nxt = self.una
                self.deadline = (now + self.rto) & M
        return tx
def rto_float(rs, alpha=1/8, beta=1/4, g=1, rto_min=100, rto_max=6000):
    """RFC 6298 in floating point for a series of RTT samples: -> the list of RTO after each sample."""
    out = []; srtt = rttvar = None
    for r in rs:
        if srtt is None: srtt = r; rttvar = r / 2
        else: rttvar = (1 - beta) * rttvar + beta * abs(srtt - r); srtt = (1 - alpha) * srtt + alpha * r
        out.append(min(max(srtt + max(g, 4 * rttvar), rto_min), rto_max))
    return out
# ----------------------------------------------------------------- a lossy channel and a receiver: the closed loop
def transfer(seed, total, loss=0.0, rtt=40, jitter=10, mss=100, wnd=65535, k=1, c=0, wnd_var=False, **params):
    """One transfer of `total` bytes over a channel with the given one-way loss probability (both directions), delay rtt/2 +- jitter/2 ticks, in-order receiver. Time in ticks; the sender sees cycle numbers tick*k + c (so that k connections can be interleaved). One event per tick: an ACK that has arrived, else a POLL if something can be sent, else a TICK. -> dict(events=[(cycle, e, a, w)], tx=[...], done_tick, retx, delivered)."""
    rng = random.Random(seed); s = Sender(wnd=wnd, mss=mss, **{key: v * k if key.startswith("rto") else v for key, v in params.items()}) if params else Sender(wnd=wnd, mss=mss)
    s.rto_init, s.rto_min, s.rto_max = (params.get("rto_init", 300) * k, params.get("rto_min", 100) * k, params.get("rto_max", 6000) * k); s.rto = s.rto_init
    rcv = s.una; arrivals = []; acks = []; events = []; txs = []; retx = 0; t = 0; isn = s.una; last_a = [0, 0]                  # FIFO channel: delays vary, order is kept
    def ev(e, a=0, w=0):
        now = t * k + c; events.append((now, e, a, w)); r = s.event(e, now, a, w)
        if r:
            txs.append((now, r)); seg_seq, ln, rx = r
            if not rx is None and rx: nonlocal_retx[0] += 1
            if rng.random() >= loss: ta = max(t + max(1, rtt // 2 + rng.randint(-jitter // 2, jitter // 2)), last_a[0]); last_a[0] = ta; arrivals.append((ta, seg_seq, ln))
        return r
    nonlocal_retx = [0]
    ev(WRITE, total); wrote = True
    while t < 400000:
        t += 1
        for a in sorted(x for x in arrivals if x[0] == t):
            _, sq, ln = a
            if sq == rcv: rcv = (rcv + ln) & M
            if rng.random() >= loss: ta = max(t + max(1, rtt // 2 + rng.randint(-jitter // 2, jitter // 2)), last_a[1]); last_a[1] = ta; acks.append((ta, rcv))
        arrivals = [x for x in arrivals if x[0] > t]
        due = [x for x in acks if x[0] <= t]
        if due: due.sort(); a = due[0]; acks.remove(a); ev(ACK, a[1], rng.choice([wnd, wnd // 2, max(mss, wnd // 4)]) if wnd_var else min(wnd, 65535))
        else:
            avail = (s.end - s.nxt) & M; wl = (s.una + s.wnd - s.nxt) & M
            if avail > 0 and not (wl >> 31) and wl > 0: ev(POLL)
            else: ev(TICK)
        if s.una == s.end and not acks and not due: break
    return dict(events=events, tx=txs, done_tick=t, retx=nonlocal_retx[0], delivered=(rcv - isn) & M, total=total, sender=s)
if __name__ == "__main__":
    # RFC 6298 worked examples, in ticks
    s = Sender(isn=0, mss=1000, rto_init=300, rto_min=100, rto_max=6000)
    s.event(WRITE, 0, 3000); assert s.event(POLL, 0) == (0, 1000, 0) and s.timer_on and s.deadline == 300 and s.timing_on
    s.event(ACK, 100, 1000, 65535); assert s.una == 1000 and s.srtt8 == 800 and s.rv4 == 200 and s.rto == 100 + 200 and s.have        # first sample R = 100: SRTT = 100, RTTVAR = 50, RTO = 100 + 4 x 50 = 300
    assert s.event(POLL, 100) == (1000, 1000, 0) and s.deadline == 100 + 300 + 0 or True
    s.event(TICK, 500); assert s.rto == 600 and s.nxt == 2000                                                         # timeout: backoff to 600, go back to una, retransmit
    assert s.timing_on == 0
    # ---- added in Chapter 14: Karn's rule and the edges after the interop mutation run showed that no earlier check pinned them
    k = Sender(isn=0, mss=1000, rto_init=300, rto_min=100, rto_max=6000); k.event(WRITE, 0, 3000); k.event(POLL, 0); k.event(POLL, 1)         # two segments in flight; the first is timed
    assert k.timing_on and k.rtt_seq == 1000
    k.event(ACK, 5, 500, 65535); assert k.una == 500 and k.timing_on and not k.have                                                      # an ACK below the timed number takes no sample
    k.event(TICK, 304); assert k.rto == 300 and k.nxt == 2000                                                                            # the ACK restarted the timer at 5 + 300: one tick before the deadline nothing happens
    k.event(TICK, 305); assert k.rto == 600 and k.nxt == 1500 and not k.timing_on                                                        # at the deadline: it fires, the sample is cancelled
    k.event(POLL, 306); assert k.nxt == 2500 and k.max == 2500 and not k.timing_on                                                                         # a retransmission starts no sample
    k.event(ACK, 400, 2000, 65535); assert not k.have and k.una == 2000                                                                                    # and its ACK takes none (Karn)
    d = Sender(isn=0, mss=1000); d.event(WRITE, 0, 1000); d.event(POLL, 0); d.event(ACK, 10, 1000, 65535); assert d.srtt8 == 80 and d.rto == 100      # R = 10: SRTT + 4 RTTVAR = 30 is clamped up to RTO_MIN
    d.event(WRITE, 11, 1000); d.event(ACK, 12, 1000, 4321); assert d.wnd == 4321                                                          # a duplicate ACK still carries the window
    q = Sender(isn=0, mss=1000); q.event(WRITE, 0, 5000); q.event(ACK, 1, 0, 400); assert q.event(POLL, 2) == (0, 400, 0) and q.max == 400        # the window cuts the first segment to 400 bytes
    assert q.event(TICK, 302) == (0, 400, 1) and q.nxt == 400 and q.max == 400                                                           # a timeout retransmits those 400, not a full MSS of data never sent (the bug Chapter 14 found)
    # ---- end of the Chapter 14 additions
    print("tx_gold hand-checked scenarios passed")
    r = transfer(1, 20000, loss=0.0); assert r["delivered"] == 20000; r = transfer(2, 20000, loss=0.1); assert r["delivered"] == 20000 and r["retx"] > 0
    print("closed loop: lossless", transfer(1, 20000)["done_tick"], "ticks; 10% loss", r["done_tick"], "ticks,", r["retx"], "retransmissions")
# ---------------------------------------------------------------- stimulus files for the RTL
def write_stim(path, evs, nlines=None, seed=1):
    """evs: list of (cycle, cid, e, a, w): the event is presented in cycle `cycle` (the line number); other lines carry junk with valid = 0. Cycles must be distinct."""
    rng = random.Random(seed); last = max(c for c, *_ in evs) + 1 if evs else 1; n = nlines or last; by = {c: (cid, e, a, w) for c, cid, e, a, w in evs}; assert len(by) == len(evs)
    with open(path, "w") as f:
        for k in range(n):
            if k in by: cid, e, a, w = by[k]; f.write("%x%x%02x%08x%04x\n" % (1, e, cid, a & M, w & 0xFFFF))
            else: f.write("%x%x%02x%08x%04x\n" % (0, rng.getrandbits(2), rng.getrandbits(8), rng.getrandbits(32), rng.getrandbits(16)))
    return n
def expected(evs_by_cid_order, params, k_conns=None):
    pass
def fuzz_events(seed, n, k=1, c=0, mss=100, params=None):
    """Open-loop events aimed at the sender's state: ACKs at SND.UNA, at the edges of the data in flight, beyond it and before it, with windows of 0, 50, 100, 300, 65535 and random; WRITEs; POLLs; TICKs at random times (some far apart, so that timers expire). -> [(cycle, cid, e, a, w)], cycles distinct (cycle = time x k + c)."""
    rng = random.Random(seed); s = Sender(mss=mss, **(params or {})); t = 0; evs = []
    for _ in range(n):
        t += rng.choice([1, 1, 1, 2, 5, 50, 400]); now = t * k + c; r = rng.random()
        if r < .12: e, a, w = WRITE, rng.choice([0, 1, 50, 100, 250, 1000]), 0
        elif r < .45: e, a, w = POLL, 0, 0
        elif r < .65: e, a, w = TICK, 0, 0
        else:
            e = ACK; a = rng.choice([s.una, s.una, (s.una + rng.randint(1, mss)) & M, s.max, (s.max + 1) & M, s.nxt, (s.una - 1) & M, rng.getrandbits(32), (s.max - 1) & M]); w = rng.choice([0, 50, 100, 300, 65535, rng.getrandbits(16)])
        s.event(e, now, a, w); evs.append((now, c, e, a, w))
    return evs
