#!/usr/bin/env python3
"""Chapter 12: the specification of the TCP connection state machine and its segment checks, written from RFC 9293 section 3.10 (the SEGMENT ARRIVES rules) with the blind-attack mitigations of RFC 5961 (a RST is accepted only at exactly RCV.NXT; a SYN in a synchronised state draws a challenge ACK).
Simplifications, stated so that nothing is hidden: no options, no urgent data, no retransmission timer (Chapter 13), no congestion control, no application data to send (only control segments are produced), data is accepted only IN ORDER (a segment that does not start at RCV.NXT is acknowledged and its data dropped: no reassembly), the payload of a SYN is ignored, the peer's window is ignored, and our receive window is a constant given with each event.
Sequence numbers are 32 bits and every comparison is modular: x is in [lo, lo + w) iff (x - lo) mod 2^32 < w; a < b iff the top bit of (a - b) is set.
An event is one of OPEN_PASSIVE, OPEN_ACTIVE (with an initial sequence number), CLOSE, ABORT, TIMEOUT (the 2MSL timer) or SEGMENT(flags, seq, ack, len). Result of an event: the new state, the segment to send (flags, seq, ack) or None, the number of payload bytes delivered, and the three sequence variables."""
import random
M = 0xFFFFFFFF
CLOSED, LISTEN, SYN_SENT, SYN_RCVD, ESTAB, FW1, FW2, CLOSE_WAIT, CLOSING, LAST_ACK, TIME_WAIT = range(11)
SNAME = ["CLOSED", "LISTEN", "SYN_SENT", "SYN_RCVD", "ESTABLISHED", "FIN_WAIT_1", "FIN_WAIT_2", "CLOSE_WAIT", "CLOSING", "LAST_ACK", "TIME_WAIT"]
SYN, ACK, FIN, RST = 1, 2, 4, 8
E_OPEN_P, E_OPEN_A, E_CLOSE, E_ABORT, E_TIMEOUT, E_SEG = range(6)
ENAME = ["OPEN_PASSIVE", "OPEN_ACTIVE", "CLOSE", "ABORT", "TIMEOUT", "SEGMENT"]
def lt(a, b): return ((a - b) & M) >> 31 == 1
def fl(f): return "".join(c for c, b in (("S", SYN), ("A", ACK), ("F", FIN), ("R", RST)) if f & b) or "-"
class TCB:
    def __init__(self): self.state = CLOSED; self.passive = 0; self.una = 0; self.nxt = 0; self.rcv = 0
    def snapshot(self): return (self.state, self.passive, self.una, self.nxt, self.rcv)
    def _ack_seg(self): return (ACK, self.nxt, self.rcv)
    def event(self, e, f=0, seq=0, ack=0, ln=0, wnd=0, iss=0):
        """-> (tx or None, delivered bytes). Updates the state in place."""
        seq &= M; ack &= M; tx = None; dlv = 0; st = self.state
        if e == E_OPEN_P:
            if st == CLOSED: self.state = LISTEN; self.passive = 1; self.una = self.nxt = iss & M
        elif e == E_OPEN_A:
            if st in (CLOSED, LISTEN):
                self.state = SYN_SENT; self.passive = 0; self.una = iss & M; self.nxt = (iss + 1) & M; tx = (SYN, iss & M, 0)
        elif e == E_CLOSE:
            if st in (LISTEN, SYN_SENT): self.state = CLOSED
            elif st in (SYN_RCVD, ESTAB, CLOSE_WAIT):
                tx = (FIN | ACK, self.nxt, self.rcv); self.nxt = (self.nxt + 1) & M; self.state = LAST_ACK if st == CLOSE_WAIT else FW1
        elif e == E_ABORT:
            if st in (SYN_RCVD, ESTAB, FW1, FW2, CLOSE_WAIT): tx = (RST, self.nxt, 0)
            if st != CLOSED: self.state = CLOSED
        elif e == E_TIMEOUT:
            if st == TIME_WAIT: self.state = CLOSED
        else: tx, dlv = self._segment(f, seq, ack, ln, wnd)
        return tx, dlv
    def _segment(self, f, seq, ack, ln, wnd):
        s_syn, s_ack, s_fin, s_rst = f & SYN, f & ACK, f & FIN, f & RST; st = self.state; segl = ln + (1 if s_syn else 0) + (1 if s_fin else 0)
        if st == CLOSED:
            if s_rst: return None, 0
            return ((RST, ack & M, 0) if s_ack else (RST | ACK, 0, (seq + segl) & M)), 0
        if st == LISTEN:
            if s_rst: return None, 0
            if s_ack: return (RST, ack & M, 0), 0
            if s_syn:
                self.rcv = (seq + 1) & M; self.una = self.nxt; iss = self.nxt; self.nxt = (iss + 1) & M; self.state = SYN_RCVD; self.passive = 1
                return (SYN | ACK, iss, self.rcv), 0
            return None, 0
        if st == SYN_SENT:
            ack_ok = True
            if s_ack:
                d = (ack - self.una) & M; dn = (self.nxt - self.una) & M
                ack_ok = d != 0 and d <= dn
                if not ack_ok: return (None if s_rst else (RST, ack & M, 0)), 0
            if s_rst: 
                if s_ack and ack_ok: self.state = CLOSED
                return None, 0
            if s_syn:
                self.rcv = (seq + 1) & M
                if s_ack:
                    self.una = ack & M; self.state = ESTAB; return (ACK, self.nxt, self.rcv), 0
                self.state = SYN_RCVD; self.passive = 0; return (SYN | ACK, self.una, self.rcv), 0
            return None, 0
        # synchronised states and SYN_RCVD
        d = (seq - self.rcv) & M
        if segl == 0: ok = (seq == self.rcv) if wnd == 0 else d < wnd
        else: ok = False if wnd == 0 else (d < wnd) or (((seq + segl - 1 - self.rcv) & M) < wnd)
        if not ok: return (None if s_rst else self._ack_seg()), 0
        if s_rst:
            if seq == self.rcv:
                if st == SYN_RCVD and self.passive: self.state = LISTEN
                else: self.state = CLOSED
                return None, 0
            return self._ack_seg(), 0                                              # challenge ACK (RFC 5961)
        if s_syn: return self._ack_seg(), 0                                        # challenge ACK
        if not s_ack: return None, 0
        du = (ack - self.una) & M; dn = (self.nxt - self.una) & M
        if st == SYN_RCVD:
            if du != 0 and du <= dn: self.state = ESTAB; self.una = ack & M; st = ESTAB
            else: return (RST, ack & M, 0), 0
        else:
            old = lt(ack, self.una)
            if not old and du > dn: return self._ack_seg(), 0                      # acks something not yet sent
            if not old and du != 0: self.una = ack & M
        acked = self.una == self.nxt
        if st == FW1 and acked: self.state = st = FW2
        elif st == CLOSING and acked: self.state = st = TIME_WAIT
        elif st == LAST_ACK and acked: self.state = CLOSED; return None, 0
        tx = None; dlv = 0
        if st in (ESTAB, FW1, FW2):
            if ln > 0:
                if seq == self.rcv: n = min(ln, wnd); dlv = n; self.rcv = (self.rcv + n) & M; fin_ok = n == ln
                else: fin_ok = False                                                # out of order: data dropped
                tx = self._ack_seg()                                                # new data or duplicate ACK
            else: fin_ok = seq == self.rcv
            if s_fin:
                if fin_ok:
                    self.rcv = (self.rcv + 1) & M; tx = self._ack_seg()
                    self.state = CLOSE_WAIT if st == ESTAB else (TIME_WAIT if st == FW2 else CLOSING)
                elif tx is None: tx = self._ack_seg()
        elif s_fin: tx = self._ack_seg()                                            # a retransmitted FIN in CLOSE_WAIT, CLOSING, LAST_ACK or TIME_WAIT: acknowledge again
        return tx, dlv
def run_events(evs):
    """evs: list of dicts(e, f, seq, ack, ln, wnd, iss, [cid]); returns the list of result tuples for one connection."""
    t = TCB(); out = []
    for v in evs:
        tx, dlv = t.event(v["e"], v.get("f", 0), v.get("seq", 0), v.get("ack", 0), v.get("ln", 0), v.get("wnd", 0), v.get("iss", 0)); out.append((t.state, tx, dlv, t.una, t.nxt, t.rcv, t.passive))
    return out
if __name__ == "__main__":
    # a hand-checked life: active open, established, we close first, peer closes, time-wait, closed
    t = TCB(); ISS = 0xFFFFFFF0; PEER = 5000
    tx, _ = t.event(E_OPEN_A, iss=ISS); assert t.state == SYN_SENT and tx == (SYN, ISS, 0)
    tx, _ = t.event(E_SEG, SYN | ACK, PEER, (ISS + 1) & M, 0, 1000); assert t.state == ESTAB and tx == (ACK, (ISS + 1) & M, PEER + 1)
    tx, d = t.event(E_SEG, ACK, PEER + 1, (ISS + 1) & M, 100, 1000); assert d == 100 and t.rcv == PEER + 101 and tx == (ACK, (ISS + 1) & M, PEER + 101)
    tx, d = t.event(E_SEG, ACK, PEER + 1, (ISS + 1) & M, 100, 1000); assert d == 0 and tx == (ACK, (ISS + 1) & M, PEER + 101)      # a duplicate: acknowledged, not delivered again
    tx, _ = t.event(E_CLOSE); assert t.state == FW1 and tx[0] == FIN | ACK and t.nxt == (ISS + 2) & M
    tx, _ = t.event(E_SEG, ACK, PEER + 101, (ISS + 2) & M, 0, 1000); assert t.state == FW2 and tx is None
    tx, _ = t.event(E_SEG, FIN | ACK, PEER + 101, (ISS + 2) & M, 0, 1000); assert t.state == TIME_WAIT and tx == (ACK, (ISS + 2) & M, PEER + 102)
    t.event(E_TIMEOUT); assert t.state == CLOSED
    # passive open and a blind reset: only a RST at exactly RCV.NXT closes the connection
    t = TCB(); t.event(E_OPEN_P, iss=77); tx, _ = t.event(E_SEG, SYN, 9, 0, 0, 1000); assert t.state == SYN_RCVD and tx == (SYN | ACK, 77, 10)
    t.event(E_SEG, ACK, 10, 78, 0, 1000); assert t.state == ESTAB
    tx, _ = t.event(E_SEG, RST, 20, 0, 0, 1000); assert t.state == ESTAB and tx == (ACK, 78, 10)          # in window, not exact: challenge ACK
    tx, _ = t.event(E_SEG, RST, 10, 0, 0, 1000); assert t.state == CLOSED
    # ---- added in Chapter 14: an unacceptable segment is only acknowledged; a second FIN is acknowledged again
    t = TCB(); t.event(E_OPEN_A, iss=100); t.event(E_SEG, SYN | ACK, 500, 101, 0, 1000); t.event(E_CLOSE); assert t.state == FW1
    tx, d = t.event(E_SEG, ACK, 500 + 1 + 5000, 102, 10, 1000); assert t.state == FW1 and t.una == 101 and tx == (ACK, 102, 501) and d == 0     # out of the window: its ACK field is not looked at
    t.event(E_SEG, ACK, 501, 102, 0, 1000); t.event(E_SEG, FIN | ACK, 501, 102, 0, 1000); assert t.state == TIME_WAIT and t.rcv == 502
    tx, _ = t.event(E_SEG, FIN | ACK, 502, 102, 0, 1000); assert tx == (ACK, 102, 502)                                                           # a further FIN at RCV.NXT: acknowledged again
    # ---- end of the Chapter 14 additions
    print("tcp_gold hand-checked scenarios passed")
# ---------------------------------------------------------------- stimulus
def seg_near(rng, t, wnd):
    """A segment relative to a connection's state, chosen to land on the edges of every test: the sequence number at RCV.NXT, one before, the last byte of the window, one past it; the ACK at SND.UNA, SND.NXT and one either side."""
    seq = (t.rcv + rng.choice([0, 0, 0, -1, 1, wnd - 1, wnd, wnd + 1, -2, rng.randint(0, 3 * max(wnd, 1)), -rng.randint(1, 100), 0x7FFFFFFF, 0x80000000])) & M
    ack = (rng.choice([t.nxt, t.nxt, t.una, t.nxt + 1, t.nxt - 1, t.una - 1, t.una + 1, rng.getrandbits(32), t.nxt + rng.randint(2, 50)])) & M
    return seq, ack
def gen_events(seed, n, cids=1, wnds=(0, 1, 5, 100, 4096, 65535)):
    """-> list of events (dicts with cid). A model per connection is run alongside so that the segments aimed at its state are well chosen: legitimate handshakes and closes mixed with every kind of wrong segment."""
    rng = random.Random(seed); tcb = [TCB() for _ in range(cids)]; evs = []
    iss_pool = [0, 1, 0xFFFFFFF0, 0xFFFFFFFF, 0x7FFFFFFF, 0x80000000, 12345]
    for _ in range(n):
        c = rng.randrange(cids); t = tcb[c]; wnd = rng.choice(wnds)
        r = rng.random()
        if r < .18:
            e = rng.choice([E_OPEN_P, E_OPEN_A, E_OPEN_P, E_OPEN_A, E_CLOSE, E_CLOSE, E_ABORT, E_TIMEOUT, E_TIMEOUT]); v = dict(e=e, iss=rng.choice(iss_pool + [rng.getrandbits(32)]))
        else:
            seq, ack = seg_near(rng, t, wnd); ln = rng.choice([0, 0, 0, 1, 5, 100, wnd, wnd + 1, 1460, rng.randint(0, 2000)]) & 0xFFFF
            st = t.state
            if st == SYN_SENT and rng.random() < .6: f = rng.choice([SYN | ACK, SYN | ACK, SYN, RST | ACK, RST, ACK]); ack = (t.nxt if rng.random() < .8 else ack); seq = rng.choice([seq, rng.getrandbits(32)])
            elif st == LISTEN and rng.random() < .6: f = rng.choice([SYN, SYN, SYN | ACK, ACK, RST]); seq = rng.getrandbits(32) if rng.random() < .8 else seq
            elif st in (CLOSED,): f = rng.choice([SYN, ACK, SYN | ACK, RST, FIN | ACK, ACK | RST]); seq = rng.getrandbits(32)
            else: f = rng.choice([ACK, ACK, ACK, ACK, ACK | FIN, ACK | FIN, FIN, SYN, SYN | ACK, RST, RST | ACK, 0, ACK | FIN | SYN, RST | FIN])
            if st in (SYN_RCVD, ESTAB, FW1, FW2) and rng.random() < .15: seq = t.rcv; ack = t.nxt if rng.random() < .8 else ack
            v = dict(e=E_SEG, f=f, seq=seq, ack=ack, ln=ln, wnd=wnd)
        v["cid"] = c; evs.append(v); t.event(v["e"], v.get("f", 0), v.get("seq", 0), v.get("ack", 0), v.get("ln", 0), v.get("wnd", 0), v.get("iss", 0))
    return evs
def directed_events(cid=0):
    """Hand-built lives of a connection: every close path, simultaneous open, resets of each kind, a SYN to a LISTEN with an ACK, wraparound of the sequence space."""
    ev = []; w = 1000
    def add(e, **k): ev.append(dict(e=e, cid=cid, wnd=k.pop("wnd", w), **k))
    for iss, peer in ((0xFFFFFF00, 0xFFFFFFF0), (100, 200)):
        add(E_OPEN_A, iss=iss); add(E_SEG, f=SYN | ACK, seq=peer, ack=iss + 1); add(E_SEG, f=ACK, seq=peer + 1, ack=iss + 1, ln=300); add(E_SEG, f=ACK | FIN, seq=peer + 301, ack=iss + 1); add(E_CLOSE)       # passive close: ESTABLISHED, CLOSE_WAIT, LAST_ACK
        add(E_SEG, f=ACK, seq=peer + 302, ack=iss + 2); add(E_OPEN_P, iss=iss); add(E_SEG, f=SYN, seq=peer, ack=0); add(E_SEG, f=ACK, seq=peer + 1, ack=iss + 1); add(E_CLOSE)         # active close: FIN_WAIT_1
        add(E_SEG, f=FIN | ACK, seq=peer + 1, ack=iss + 1); add(E_SEG, f=ACK, seq=peer + 2, ack=iss + 2); add(E_TIMEOUT)                                                          # simultaneous close: CLOSING, TIME_WAIT
        add(E_OPEN_A, iss=iss); add(E_SEG, f=SYN, seq=peer, ack=0); add(E_SEG, f=SYN | ACK, seq=peer, ack=iss + 1); add(E_SEG, f=ACK, seq=peer + 1, ack=iss + 1); add(E_ABORT)             # simultaneous open
        add(E_OPEN_P, iss=iss); add(E_SEG, f=ACK, seq=5, ack=9); add(E_SEG, f=SYN, seq=peer, ack=0); add(E_SEG, f=RST, seq=peer + 1, ack=0); add(E_SEG, f=SYN, seq=peer, ack=0)       # reset in SYN_RCVD returns to LISTEN
        add(E_SEG, f=ACK, seq=peer + 1, ack=iss + 1); add(E_SEG, f=ACK, seq=peer + 1 + w, ack=iss + 1); add(E_SEG, f=ACK, seq=peer + w, ack=iss + 1, ln=1); add(E_SEG, f=RST, seq=peer + 50, ack=0)
        add(E_SEG, f=RST, seq=peer + 1, ack=0); add(E_SEG, f=ACK, seq=1, ack=2); add(E_SEG, f=RST, seq=1)
    return ev
def write_events(path, evs, seed=1, idle=15):
    rng = random.Random(seed ^ 0x77); lines = []
    def junk(): return "%x%x%02x%x%04x%04x%08x%08x%08x" % (0, rng.getrandbits(3), rng.getrandbits(8), rng.getrandbits(4), rng.getrandbits(16), rng.getrandbits(16), rng.getrandbits(32), rng.getrandbits(32), rng.getrandbits(32))
    for v in evs:
        while rng.randrange(100) < idle: lines.append(junk())
        lines.append("%x%x%02x%x%04x%04x%08x%08x%08x" % (1, v["e"], v.get("cid", 0), v.get("f", 0), v.get("ln", 0), v.get("wnd", 0), v.get("seq", 0) & M, v.get("ack", 0) & M, v.get("iss", 0) & M))
    with open(path, "w") as f: f.write("\n".join(lines) + "\n")
    return len(lines)
def expected_results(evs):
    """-> list of (cid, state, passive, una, nxt, rcv, txv, txflags, txseq, txack, delivered), one per event, connections independent."""
    tcb = {}; out = []
    for v in evs:
        c = v.get("cid", 0); t = tcb.setdefault(c, TCB()); tx, d = t.event(v["e"], v.get("f", 0), v.get("seq", 0), v.get("ack", 0), v.get("ln", 0), v.get("wnd", 0), v.get("iss", 0))
        out.append((c, t.state, t.passive, t.una, t.nxt, t.rcv, 1 if tx else 0, tx[0] if tx else 0, tx[1] if tx else 0, tx[2] if tx else 0, d))
    return out
def transitions(evs):
    """Coverage: the set of (state before, event class, state after) triples and (state, event class, reaction) seen; an event class of a segment is its flags."""
    tcb = {}; tr = set()
    for v in evs:
        t = tcb.setdefault(v.get("cid", 0), TCB()); s0 = t.state; tx, d = t.event(v["e"], v.get("f", 0), v.get("seq", 0), v.get("ack", 0), v.get("ln", 0), v.get("wnd", 0), v.get("iss", 0))
        cls = ENAME[v["e"]] if v["e"] != E_SEG else "SEG " + fl(v.get("f", 0)); tr.add((s0, cls, t.state, tx[0] if tx else -1, d > 0))
    return tr
def fast_path(t, f, seq, ack, ln, wnd):
    """The hot path of tcp_fast: True if the segment is handled by it."""
    return t.state == ESTAB and f == ACK and seq == t.rcv and ln <= wnd and ((ack - t.una) & M) <= ((t.nxt - t.una) & M)
def realistic_events(seed, conns=8, per_conn=200, p_odd=0.03, wnd=65535):
    """Traffic as a server sees it: each connection is opened by a peer, receives in-order data segments and pure ACKs, with a few percent of oddities (an old duplicate, a gap, a bad ACK, a reset probe), and is closed by FIN; connections are interleaved at random."""
    rng = random.Random(seed); tcb = [TCB() for _ in range(conns)]; todo = [per_conn] * conns; evs = []; phase = [0] * conns; peer = [rng.getrandbits(32) for _ in range(conns)]
    def add(c, e, **k): v = dict(e=e, cid=c, wnd=wnd, **k); evs.append(v); tcb[c].event(e, k.get("f", 0), k.get("seq", 0), k.get("ack", 0), k.get("ln", 0), wnd, k.get("iss", 0))
    live = list(range(conns))
    while live:
        c = rng.choice(live); t = tcb[c]
        if phase[c] == 0: add(c, E_OPEN_P, iss=rng.getrandbits(32)); phase[c] = 1
        elif phase[c] == 1: add(c, E_SEG, f=SYN, seq=peer[c], ack=0); phase[c] = 2
        elif phase[c] == 2: add(c, E_SEG, f=ACK, seq=(peer[c] + 1) & M, ack=t.nxt); phase[c] = 3
        elif phase[c] == 3:
            if todo[c] == 0: add(c, E_SEG, f=FIN | ACK, seq=t.rcv, ack=t.nxt); phase[c] = 4; continue
            todo[c] -= 1; r = rng.random()
            if r < p_odd / 3: add(c, E_SEG, f=ACK, seq=(t.rcv - rng.randint(1, 1460)) & M, ack=t.nxt, ln=rng.randint(1, 1460))      # an old duplicate
            elif r < 2 * p_odd / 3: add(c, E_SEG, f=ACK, seq=(t.rcv + rng.randint(1, 3000)) & M, ack=t.nxt, ln=rng.randint(1, 1460))   # a gap
            elif r < p_odd: add(c, E_SEG, f=ACK, seq=t.rcv, ack=(t.nxt + rng.randint(1, 100)) & M)                                      # an ACK for something never sent
            elif r < 0.55: add(c, E_SEG, f=ACK, seq=t.rcv, ack=t.nxt, ln=rng.choice([1460, 1460, 1460, 536, rng.randint(1, 1460)]))     # data
            else: add(c, E_SEG, f=ACK, seq=t.rcv, ack=t.nxt)                                                                        # a pure ACK
        elif phase[c] == 4: add(c, E_CLOSE); phase[c] = 5
        elif phase[c] == 5: add(c, E_SEG, f=ACK, seq=t.rcv, ack=t.nxt); phase[c] = 6
        else: add(c, E_TIMEOUT); live.remove(c)
    return evs
def fast_random_cases(seed, n):
    """Uniformly random connection states (mostly ESTABLISHED, with data outstanding half the time) and segments aimed at them, for the hot path: [(snapshot, event)]."""
    rng = random.Random(seed); cases = []
    for _ in range(n):
        t = TCB(); t.state = ESTAB if rng.random() < .8 else rng.randrange(11); t.una = rng.getrandbits(32); t.nxt = (t.una + rng.choice([0, 0, 1, 5, 1000])) & M; t.rcv = rng.getrandbits(32)
        v = dict(e=E_SEG, f=rng.choice([ACK, ACK, ACK, ACK | FIN, SYN, 0]), seq=rng.choice([t.rcv, t.rcv, (t.rcv + 1) & M, rng.getrandbits(32)]), ack=rng.choice([t.nxt, t.una, (t.nxt + 1) & M, (t.una - 1) & M, rng.getrandbits(32)]), ln=rng.choice([0, 1, 100, 1460]), wnd=rng.choice([0, 100, 1460, 65535])); cases.append((t.snapshot(), v))
    return cases
