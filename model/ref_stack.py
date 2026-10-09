#!/usr/bin/env python3
"""Chapter 14: an INDEPENDENT reference for the TCP of Chapters 12 and 13, and the impaired network between them. Nothing here imports tx_gold.py or tcp_gold.py, and it is written the other way round on purpose: a receiver that keeps out-of-order segments and holds real bytes, a sender that keeps real bytes, uses a fixed timeout with doubling (no estimator), retransmits everything after a timeout and the oldest segment after three duplicate ACKs (fast retransmit). Where the design under test (DUT) and the reference differ in design they must still agree on what the user sees: the bytes arrive, once, in order.
A segment is a tuple (flags, seq, ack, ln, wnd); flags SYN=1 ACK=2 FIN=4 RST=8 (the same values as RFC 9293 order in Chapter 12, written again here). The payload of the byte at stream offset i is stream_byte(i), so nothing needs to be stored to know what a segment carries.
The network: Channel is one direction. It loses a segment with probability `loss`, duplicates it with probability `dup`, adds `jitter` ticks of random delay (0 in the profiles: a plain wire keeps its order) and, with probability `reorder`, up to `spread` more ticks (so the segment is overtaken by later ones). Every random choice comes from one seeded generator: a run is reproducible."""
import heapq, random
M = 0xFFFFFFFF
SYN, ACK, FIN, RST = 1, 2, 4, 8
def lt(a, b): return ((a - b) & M) >> 31 == 1
def le(a, b): return a == b or lt(a, b)
def stream_byte(i): return (i * 131 + (i >> 8) * 17 + 7) & 255
def stream(off, n): return bytes(stream_byte(off + i) for i in range(n))
class Channel:
    def __init__(self, rng, delay=20, jitter=0, loss=0.0, dup=0.0, reorder=0.0, spread=60):
        self.rng, self.delay, self.jitter, self.loss, self.dup, self.reorder, self.spread = rng, delay, jitter, loss, dup, reorder, spread
        self.q = []; self.n = 0; self.sent = self.orig = 0; self.last = -1; self.overtaken = 0
    def send(self, t, seg):
        self.sent += 1
        if self.rng.random() < self.loss: return
        copies = 1
        if self.rng.random() < self.dup: copies = 2
        self.orig += 1
        for _ in range(copies):
            d = self.delay + self.rng.randint(0, self.jitter)
            if self.rng.random() < self.reorder: d += self.rng.randint(1, self.spread)
            heapq.heappush(self.q, (t + max(1, d), self.n, seg)); self.n += 1
    def due(self, t):
        out = []
        while self.q and self.q[0][0] <= t:
            _, n, seg = heapq.heappop(self.q); out.append(seg)
            if n < self.last: self.overtaken += 1
            self.last = max(self.last, n)
        return out
    @property
    def lost(self): return self.sent - self.orig                                      # what the profile asked for is counted by what the receiver could observe,
    @property
    def duped(self): return self.n - self.orig                                        # not by what the channel meant to do: copies that were queued,
    @property
    def late(self): return self.overtaken                                             # and segments that arrived after one sent later
    def empty(self): return not self.q
class RefReceiver:
    """An established connection's receiving end: reassembles out-of-order segments, acknowledges cumulatively (a duplicate ACK for anything out of order), holds the bytes."""
    def __init__(self, first, wnd=65535):
        self.nxt = first & M; self.first = first & M; self.wnd = wnd; self.ooo = {}; self.buf = bytearray()
    def on_seg(self, t, sg, out):
        f, seq, ack, ln, wnd = sg
        if ln > 0:
            if lt(self.nxt, (seq + ln) & M):                                          # carries something we still need
                self.ooo[seq] = max(self.ooo.get(seq, 0), ln)
            progressed = True
            while progressed:
                progressed = False
                for sq in sorted(self.ooo, key=lambda x: (x - self.nxt) & M):
                    l = self.ooo[sq]
                    if le(sq, self.nxt):
                        end = (sq + l) & M
                        if lt(self.nxt, end):
                            n = (end - self.nxt) & M; self.buf += stream((self.nxt - self.first) & M, n); self.nxt = end
                        del self.ooo[sq]; progressed = True; break
            out.append((ACK, 0, self.nxt, 0, self.wnd))
class RefClient:
    """Active opener and sender: SYN (retransmitted), data, FIN, waits for the peer's FIN. Fixed timeout `rto` doubled up to `rto_max` on each expiry, reset by an ACK that advances."""
    def __init__(self, iss, total, mss=100, wnd=4096, rto=200, rto_max=3200, fast=True):
        self.iss = iss & M; self.total = total; self.mss = mss; self.win = wnd; self.rto0 = rto; self.rto_max = rto_max; self.fast = fast
        self.state = "CLOSED"; self.una = self.nxt = self.iss; self.rcv = 0; self.timer = None; self.rto = rto; self.dup = 0; self.retx = 0; self.segs = 0; self.peer_wnd = wnd
    @property
    def dstart(self): return (self.iss + 1) & M
    @property
    def dend(self): return (self.iss + 1 + self.total) & M
    def start(self, t, out):
        self.state = "SYN_SENT"; self.nxt = (self.iss + 1) & M; out.append((SYN, self.iss, 0, 0, self.win)); self.timer = t + self.rto
    def _data(self, t, out):
        while self.state == "EST" and lt(self.nxt, self.dend) and ((self.nxt - self.una) & M) < min(self.win, self.peer_wnd):
            n = min(self.mss, (self.dend - self.nxt) & M); out.append((ACK, self.nxt, self.rcv, n, self.win)); self.segs += 1
            if lt(self.nxt, self.high): self.retx += 1
            self.nxt = (self.nxt + n) & M
            if lt(self.high, self.nxt): self.high = self.nxt
            if self.timer is None: self.timer = t + self.rto
        if self.state == "EST" and self.nxt == self.dend and self.una == self.dend:
            out.append((FIN | ACK, self.dend, self.rcv, 0, self.win)); self.nxt = (self.dend + 1) & M; self.state = "FIN_WAIT_1"; self.timer = t + self.rto
    def on_seg(self, t, sg, out):
        f, seq, ack, ln, wnd = sg
        if self.state == "SYN_SENT":
            if f & SYN and f & ACK and ack == (self.iss + 1) & M:
                self.rcv = (seq + 1) & M; self.una = ack; self.state = "EST"; self.high = self.nxt; self.timer = None; self.rto = self.rto0; self.peer_wnd = wnd
                out.append((ACK, self.nxt, self.rcv, 0, self.win)); self._data(t, out)
            return
        if self.state in ("EST", "FIN_WAIT_1", "FIN_WAIT_2"):
            if f & ACK:
                self.peer_wnd = wnd
                if lt(self.una, ack) and le(ack, self.nxt):
                    self.una = ack; self.dup = 0; self.rto = self.rto0; self.timer = t + self.rto if self.una != self.nxt else None
                    if self.state == "FIN_WAIT_1" and self.una == self.nxt: self.state = "FIN_WAIT_2"; self.timer = None
                elif ack == self.una and self.una != self.nxt and ln == 0 and not f & FIN:
                    self.dup += 1
                    if self.fast and self.dup == 3 and self.state == "EST":
                        n = min(self.mss, (self.dend - self.una) & M); out.append((ACK, self.una, self.rcv, n, self.win)); self.retx += 1; self.segs += 1
            if f & FIN and seq == self.rcv:
                self.rcv = (self.rcv + 1) & M; out.append((ACK, self.nxt, self.rcv, 0, self.win))
                if self.state == "FIN_WAIT_2" or (self.state == "FIN_WAIT_1" and self.una == self.nxt): self.state = "DONE"; self.timer = None
            elif f & FIN: out.append((ACK, self.nxt, self.rcv, 0, self.win))
            self._data(t, out)
        elif self.state == "DONE" and f & FIN: out.append((ACK, self.nxt, self.rcv, 0, self.win))
    def tick(self, t, out):
        if self.timer is not None and t >= self.timer:
            self.rto = min(self.rto * 2, self.rto_max)
            if self.state == "SYN_SENT": out.append((SYN, self.iss, 0, 0, self.win))
            elif self.state == "EST": self.nxt = self.una; self.dup = 0; self._data(t, out)
            elif self.state == "FIN_WAIT_1":
                if lt(self.una, self.dend): self.nxt = self.una; self.state = "EST"; self._data(t, out)
                else: out.append((FIN | ACK, self.dend, self.rcv, 0, self.win))
            self.timer = t + self.rto if self.state != "DONE" else None
    def done(self): return self.state == "DONE"
if __name__ == "__main__":
    rng = random.Random(1); r = RefReceiver(1000); o = []
    r.on_seg(0, (ACK, 1100, 0, 100, 0), o); assert r.nxt == 1000 and o[-1][2] == 1000          # out of order: duplicate ACK
    r.on_seg(0, (ACK, 1000, 0, 100, 0), o); assert r.nxt == 1200 and bytes(r.buf) == stream(0, 200)   # the hole fills: both segments delivered
    r.on_seg(0, (ACK, 1000, 0, 100, 0), o); assert r.nxt == 1200 and len(r.buf) == 200         # a duplicate adds nothing
    c = Channel(rng, loss=0.5); [c.send(0, (0, i, 0, 0, 0)) for i in range(1000)]; assert 400 < c.lost < 600
    c = Channel(rng, dup=0.5, reorder=0.5); [c.send(0, (0, i, 0, 0, 0)) for i in range(1000)]; c.due(10**6); assert 400 < c.duped < 600 and c.late > 100
    # ---- added in Chapter 14: a segment that overlaps data already delivered adds only its new bytes
    r = RefReceiver(1000); o = []; r.on_seg(0, (ACK, 1000, 0, 100, 0), o); r.on_seg(0, (ACK, 1050, 0, 100, 0), o); assert r.nxt == 1150 and bytes(r.buf) == stream(0, 150)
    # ---- end of the Chapter 14 additions
    print("ref_stack hand-checked scenarios passed")
