#!/usr/bin/env python3
"""Chapter 15: the specification of the hot path / cold path split of TCP, cycle for cycle. Two parts:
  Dispatcher: what tcp_split.sv does in one clock edge, given the event offered, the pop of the punt FIFO and the write-back from software (inputs sampled BEFORE the edge; outputs are registered, so the result of the event consumed at edge t is seen before edge t + 1).
  Software:   the cold path. It pops punt entries one at a time (a new one every `svc` cycles), runs the full state machine of Chapter 12 (tcp_gold.TCB) on them, and writes the new state back `lat` cycles after the pop. A connection's state is loaded from the entry's snapshot when `first` is set (nothing was pending, so the hardware's state is current) and kept in software while events are pending.
The claim the chapter tests is TRANSPARENCY: whatever the timing of the software, the segments sent and the bytes delivered per connection, and the state at the end, are exactly those of the single state machine fed the same events in the same order (the events the dispatcher consumed: with POLICY 1 some are dropped). `reference_check` computes that comparison.
Event types and flags are those of tcp_gold: E_SEG = 5 is the only event the hot path can take."""
import os, random, sys
from collections import deque
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tcp_gold as G
M = 0xFFFFFFFF
class Dispatcher:
    def __init__(self, ncid, depth, policy):
        self.n, self.depth, self.policy = ncid, depth, policy
        self.tcb = [G.TCB() for _ in range(ncid)]; self.cnt = [0] * ncid; self.fifo = deque(); self.reg = None            # reg: the registered result of the last consumed event
    def head(self): return self.fifo[0] if self.fifo else None
    def ready(self, ev):
        if ev is None or self.policy != 0: return True
        return not (self._punt(ev) and len(self.fifo) == self.depth)
    def _hot(self, ev):
        t = self.tcb[ev["cid"]]
        return ev["e"] == G.E_SEG and self.cnt[ev["cid"]] == 0 and G.fast_path(t, ev.get("f", 0), ev.get("seq", 0) & M, ev.get("ack", 0) & M, ev.get("ln", 0), ev.get("wnd", 0))
    def _punt(self, ev): return not self._hot(ev)
    def step(self, ev, pop, wb):
        """-> (consumed, registered result of this edge or None). ev: dict or None; pop: bool; wb: dict(cid, st, pas, una, nxt, rcv) or None."""
        res = None; consumed = ev is not None and self.ready(ev); pushed = False; popped = bool(pop and self.fifo)
        if consumed:
            c = ev["cid"]; t = self.tcb[c]
            if self._hot(ev):
                tx, dlv = t.event(G.E_SEG, ev.get("f", 0), ev.get("seq", 0), ev.get("ack", 0), ev.get("ln", 0), ev.get("wnd", 0)); res = (c, 0, tx, dlv)
            elif len(self.fifo) == self.depth: res = (c, 2, None, 0)
            else:
                snap = (t.state, t.passive, t.una, t.nxt, t.rcv); self.fifo.append(dict(ev, snap=snap, first=1 if self.cnt[c] == 0 else 0)); pushed = True; res = (c, 1, None, 0)
        if popped: self.fifo.popleft()
        if pushed: self.cnt[ev["cid"]] += 1
        if wb:
            t = self.tcb[wb["cid"]]; t.state, t.passive, t.una, t.nxt, t.rcv = wb["st"], wb["pas"], wb["una"], wb["nxt"], wb["rcv"]; self.cnt[wb["cid"]] -= 1
        return consumed, res
class Software:
    def __init__(self, lat=8, svc=None, rng=None):
        self.lat, self.svc, self.rng = lat, lat if svc is None else svc, rng or random.Random(0)
        self.tcb = {}; self.free_at = 0; self.wbq = deque(); self.last_wb = -1; self.tx = []; self.tags = []                         # tx: (time, cid, segment or None, delivered)
    def _n(self, v): return v(self.rng) if callable(v) else v
    def act(self, t, head):
        """Called once per cycle with the entry at the head of the FIFO (or None): -> pop? ; and the write-back due this cycle (or None)."""
        pop = False
        if head is not None and t >= self.free_at:
            pop = True; c = head["cid"]; tcb = self.tcb.setdefault(c, G.TCB())
            if head["first"]: tcb.state, tcb.passive, tcb.una, tcb.nxt, tcb.rcv = head["snap"]
            tx, dlv = tcb.event(head["e"], head.get("f", 0), head.get("seq", 0), head.get("ack", 0), head.get("ln", 0), head.get("wnd", 0), head.get("iss", 0))
            due = max(t + self._n(self.lat), self.last_wb + 1); self.last_wb = due; self.free_at = t + self._n(self.svc)
            self.wbq.append((due, dict(cid=c, st=tcb.state, pas=tcb.passive, una=tcb.una, nxt=tcb.nxt, rcv=tcb.rcv), tx, dlv, head.get("tag")))
        wb = None
        if self.wbq and self.wbq[0][0] <= t:
            due, wb, tx, dlv, tag = self.wbq.popleft(); self.tx.append((t, wb["cid"], tx, dlv)); self.tags.append((t, wb["cid"], tag, wb["st"]))
        return pop, wb
def run(events, ncid, depth, policy, lat=8, svc=None, gaps=None, seed=1, record=False, maxcycles=2000000, arrivals=None, spurious=0.0):
    """Closed loop: events (dicts with cid) arrive in order, the i-th no earlier than cycle arrival[i] (cumulative `gaps`, default back to back); the dispatcher and the software run until everything is consumed and written back. -> dict with the per-cycle trace (if record), the statistics, the hot/software outputs."""
    rng = random.Random(seed); d = Dispatcher(ncid, depth, policy); sw = Software(lat, svc, random.Random(seed + 1)); n = len(events)
    arr = []; tt = 0
    for i in range(n): tt += (gaps[i] if gaps else 0); arr.append(tt)
    if arrivals is not None: arr = list(arrivals)
    qi = 0; t = 0; hot_tx = []; trace = []; consumed_evs = []; path = []; ctime = [None] * n; max_fifo = 0; stall_cycles = 0; ref = {}; collateral = 0; dropped = 0; idx = [None] * n; done_at = None
    while t < maxcycles:
        ev = events[qi] if qi < n and arr[qi] <= t else None
        head = d.head(); pop, wb = sw.act(t, head)
        if head is None and spurious and rng.random() < spurious: pop = True                                       # software pops an empty FIFO: ignored
        ready = d.ready(ev); consumed, res = d.step(ev, pop, wb)
        if record: trace.append(dict(t=t, ev=ev, ready=ready, pop=pop, wb=wb, head=head, res=res))
        d.reg = res
        if ev is not None and not consumed: stall_cycles += 1
        if consumed:
            ctime[qi] = t; c, p, tx, dlv = res; path.append(p)
            if p == 2: dropped += 1
            else:
                r = ref.setdefault(ev["cid"], G.TCB())
                if ev["e"] == G.E_SEG and p == 1 and G.fast_path(r, ev.get("f", 0), ev.get("seq", 0) & M, ev.get("ack", 0) & M, ev.get("ln", 0), ev.get("wnd", 0)): collateral += 1
                consumed_evs.append(ev); r.event(ev["e"], ev.get("f", 0), ev.get("seq", 0), ev.get("ack", 0), ev.get("ln", 0), ev.get("wnd", 0), ev.get("iss", 0))
            if p == 0: hot_tx.append((t, ev["cid"], tx, dlv))
            qi += 1
        max_fifo = max(max_fifo, len(d.fifo))
        t += 1
        if qi == n and not d.fifo and not sw.wbq and all(c == 0 for c in d.cnt) and d.reg is None: break
    return dict(maxc=maxcycles, policy=policy, trace=trace, cycles=t, arr=arr, ctime=ctime, path=path, dropped=dropped, collateral=collateral, max_fifo=max_fifo, stall=stall_cycles, hot_tx=hot_tx, sw_tx=sw.tx, consumed=consumed_evs, disp=d, sw=sw, n=n)
def reference_check(r):
    """Transparency: -> None if the dispatcher and the software together equal the single state machine on the consumed events, else a description."""
    if r["cycles"] >= r["maxc"]: return "the run did not finish"
    if r["policy"] == 0 and r["dropped"]: return "POLICY 0 dropped an event"
    refs = {}; exp = {}
    for ev in r["consumed"]:
        c = ev["cid"]; t = refs.setdefault(c, G.TCB()); tx, dlv = t.event(ev["e"], ev.get("f", 0), ev.get("seq", 0), ev.get("ack", 0), ev.get("ln", 0), ev.get("wnd", 0), ev.get("iss", 0))
        if tx is not None or dlv: exp.setdefault(c, []).append((tx, dlv))
    got = {}
    for (t, c, tx, dlv) in sorted(r["hot_tx"] + r["sw_tx"], key=lambda x: x[0]):
        if tx is not None or dlv: got.setdefault(c, []).append((tx, dlv))
    for c in set(exp) | set(got):
        if exp.get(c, []) != got.get(c, []): return f"connection {c}: the segments sent or the bytes delivered differ"
    d = r["disp"]
    for c, t in refs.items():
        if (d.tcb[c].state, d.tcb[c].passive, d.tcb[c].una, d.tcb[c].nxt, d.tcb[c].rcv) != t.snapshot(): return f"connection {c}: the final state differs"
    return None
def with_decoys(events, ncid):
    """Application commands (OPEN, CLOSE, ABORT, TIMEOUT) carry the segment fields of a segment the hot path WOULD take, so that a design that fails to look at the event type takes them for segments."""
    ref = [G.TCB() for _ in range(ncid)]; out = []
    for ev in events:
        t = ref[ev["cid"]]; v = dict(ev)
        if v["e"] != G.E_SEG: v.update(f=G.ACK, seq=t.rcv, ack=t.nxt, ln=0, wnd=65535)
        out.append(v); t.event(v["e"], v.get("f", 0), v.get("seq", 0), v.get("ack", 0), v.get("ln", 0), v.get("wnd", 0), v.get("iss", 0))
    return out
def battery():
    """The model's own test, as one function: transparency over streams, timings, depths and both policies. -> None or a description of the first failure."""
    for kind in ("realistic", "random", "directed"):
        for policy, lat, depth in ((0, 1, 4), (0, 8, 2), (0, 30, 8), (1, 8, 4), (1, 3, 2)):
            for seed in range(2):
                if kind == "realistic": ev = with_decoys(G.realistic_events(seed, conns=4, per_conn=25, p_odd=0.06), 4)
                elif kind == "random": ev = G.gen_events(seed, 250, cids=4)
                else: ev = with_decoys(G.directed_events(0) + G.gen_events(seed, 60, cids=4), 4)
                rg = random.Random(seed); gaps = [rg.randint(0, 3) for _ in ev]
                try: r = run(ev, 4, depth, policy, lat=lat, gaps=gaps, seed=seed, maxcycles=60000); d = reference_check(r)
                except Exception as x: return f"{kind}, policy {policy}, latency {lat}: crash {type(x).__name__}"
                if d: return f"{kind}, policy {policy}, latency {lat}, depth {depth}: {d}"
    # a passive connection left alone in SYN_RCVD (nothing pending), then reset: the state written back and the snapshot taken again must round-trip, passive flag included, or the reset closes it instead of returning it to LISTEN
    for lat in (1, 6):
        ev = [dict(cid=0, e=G.E_OPEN_P, iss=100), dict(cid=0, e=G.E_SEG, f=G.SYN, seq=500, ack=0, wnd=1000), dict(cid=0, e=G.E_SEG, f=G.RST, seq=501, ack=0, wnd=1000), dict(cid=0, e=G.E_SEG, f=G.SYN, seq=900, ack=0, wnd=1000)]
        r = run(ev, 1, 4, 0, lat=lat, gaps=[0, 60, 60, 60], maxcycles=60000); d = reference_check(r)
        if d or r["disp"].tcb[0].state != G.SYN_RCVD: return f"passive reset scenario, latency {lat}: {d or 'not back in LISTEN'}"
    return None
# ---------------------------------------------------------------- stimulus for the RTL
def pack_entry(e, cidw):
    snap = e["snap"]; v = 0
    for val, w in ((e["cid"], cidw), (e["e"], 3), (e.get("f", 0), 4), (e.get("seq", 0) & M, 32), (e.get("ack", 0) & M, 32), (e.get("ln", 0), 16), (e.get("wnd", 0), 16), (e.get("iss", 0) & M, 32), (snap[0], 4), (snap[1], 1), (snap[2], 32), (snap[3], 32), (snap[4], 32), (e["first"], 1)): v = (v << w) | (val & ((1 << w) - 1))
    return v
def pw(cidw): return cidw + 3 + 4 + 32 + 32 + 16 + 16 + 32 + 4 + 1 + 96 + 1
def write_stim(path, r, cidw, seed=1):
    """One line per cycle: ev_valid(1) cid(2) type(1) f(1) seq(8) ack(8) ln(4) wnd(4) iss(8) | pop(1) | wb_valid(1) wb_cid(2) st(1) pas(1) una(8) nxt(8) rcv(8) hex digits; junk where valid = 0."""
    rng = random.Random(seed)
    with open(path, "w") as f:
        for row in r["trace"]:
            ev, wb = row["ev"], row["wb"]
            if ev: a = "%x%02x%x%x%08x%08x%04x%04x%08x" % (1, ev["cid"], ev["e"], ev.get("f", 0), ev.get("seq", 0) & M, ev.get("ack", 0) & M, ev.get("ln", 0), ev.get("wnd", 0), ev.get("iss", 0) & M)
            else: a = "%x%02x%x%x%08x%08x%04x%04x%08x" % (0, rng.getrandbits(cidw) if cidw else 0, rng.getrandbits(3), rng.getrandbits(4), rng.getrandbits(32), rng.getrandbits(32), rng.getrandbits(16), rng.getrandbits(16), rng.getrandbits(32))
            b = "%x" % (1 if row["pop"] else 0)
            if wb: c = "%x%02x%x%x%08x%08x%08x" % (1, wb["cid"], wb["st"], wb["pas"], wb["una"], wb["nxt"], wb["rcv"])
            else: c = "%x%02x%x%x%08x%08x%08x" % (0, rng.getrandbits(cidw), rng.getrandbits(4), rng.getrandbits(1), rng.getrandbits(32), rng.getrandbits(32), rng.getrandbits(32))
            f.write(a + b + c + "\n")
    return len(r["trace"])
def expected_rows(r, cidw):
    """The tb prints, before every edge: C ready r_valid r_cid r_path txv txf txseq txack dlv pq_valid pq_data(hex). The registered result is that of the previous edge."""
    rows = []; prev = None; digits = (pw(cidw) + 3) // 4
    for row in r["trace"]:
        if prev is None: rv = (0, 0, 0, 0, 0, 0, 0, 0)
        else:
            c, p, tx, dlv = prev; rv = (1, c, p, 1 if tx else 0, tx[0] if tx else 0, tx[1] if tx else 0, tx[2] if tx else 0, dlv)
        h = row["head"]; hv = ("%0*x" % (digits, pack_entry(h, cidw))) if h else "-"
        rows.append((1 if row["ready"] else 0,) + rv + (1 if h else 0, hv))
        prev = row["res"]
    return rows
if __name__ == "__main__":
    # hand-checked: a connection established through software, then data on the hot path, then an oddity that goes to software and holds the events behind it
    ev = [dict(cid=0, e=G.E_OPEN_P, iss=100), dict(cid=0, e=G.E_SEG, f=G.SYN, seq=500, ack=0, wnd=1000), dict(cid=0, e=G.E_SEG, f=G.ACK, seq=501, ack=101, wnd=1000)]
    for i in range(5): ev.append(dict(cid=0, e=G.E_SEG, f=G.ACK, seq=501 + 100 * i, ack=101, ln=100, wnd=1000))
    r = run(ev, 1, 4, 0, lat=6); assert reference_check(r) is None
    assert r["path"][:3] == [1, 1, 1] and r["path"][3] == 1                                                    # the handshake is software's; the first data segment arrives while the third step is still pending: punted with it
    r2 = run(ev, 1, 4, 0, lat=1); assert reference_check(r2) is None
    ev2 = ev[:3] + [dict(cid=0, e=G.E_SEG, f=G.ACK, seq=501, ack=101, ln=100, wnd=1000)] * 2
    gaps = [0, 0, 0, 40, 40]; r3 = run(ev2, 1, 4, 0, lat=6, gaps=gaps); assert r3["path"][3] == 0 and reference_check(r3) is None              # with time between them the data segment is hot
    ev4 = [dict(cid=0, e=G.E_OPEN_P, iss=100), dict(cid=0, e=G.E_SEG, f=G.SYN, seq=500, ack=0, wnd=1000), dict(cid=0, e=G.E_SEG, f=G.RST, seq=501, ack=0, wnd=1000)]
    r4 = run(ev4, 1, 4, 0, lat=6, gaps=[0, 60, 60]); assert reference_check(r4) is None and r4["disp"].tcb[0].state == G.LISTEN       # reset of a passive SYN_RCVD returns to LISTEN: the passive flag survives the write-back
    print("split_gold hand-checked scenarios passed")
