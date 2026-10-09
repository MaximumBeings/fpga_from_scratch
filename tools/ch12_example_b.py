#!/usr/bin/env python3
"""Chapter 12, example B: what must be in hardware. Realistic traffic (8 connections, 200 steps each: a handshake, in-order data and pure ACKs, a few percent of oddities, a close) is run through the model; every event is classified by (state, kind) and by whether the hot path (tcp_fast) would handle it. Then the share handled by the hot path against the rate of oddities. Usage: ch12_example_b.py"""
import os, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import tcp_gold as g
def classify(evs):
    tcb = {}; rows = Counter(); hot = 0
    for v in evs:
        t = tcb.setdefault(v["cid"], g.TCB()); st = t.state
        if v["e"] == g.E_SEG:
            f = v.get("f", 0); h = g.fast_path(t, f, v.get("seq", 0), v.get("ack", 0), v.get("ln", 0), v.get("wnd", 0))
            kind = "segment " + g.fl(f) + (" +data" if v.get("ln", 0) else "") + ("" if h else " (odd)" if st == g.ESTAB else "")
        else: h = False; kind = g.ENAME[v["e"]]
        rows[(g.SNAME[st], kind, h)] += 1; hot += h
        t.event(v["e"], v.get("f", 0), v.get("seq", 0), v.get("ack", 0), v.get("ln", 0), v.get("wnd", 0), v.get("iss", 0))
    return rows, hot
if __name__ == "__main__":
    evs = g.realistic_events(1, 8, 200, p_odd=0.03); rows, hot = classify(evs); n = len(evs)
    print(f"== 1. {n} events of realistic traffic (8 connections x 200 steps, 3% oddities), by the state the connection was in and the kind of event")
    print(f"  {'state':13s} {'kind':26s} {'events':>7s} {'share':>7s}  path")
    for (st, kind, h), c in sorted(rows.items(), key=lambda kv: -kv[1]): print(f"  {st:13s} {kind:26s} {c:7d} {c / n * 100:6.1f}%  {'HOT (tcp_fast)' if h else 'cold'}")
    print(f"  hot path: {hot} of {n} events ({hot / n * 100:.1f}%) in {len({(a, b) for (a, b, h), c in rows.items() if h})} state/kind classes; cold path: {n - hot} events ({(n - hot) / n * 100:.1f}%) in {len({(a, b) for (a, b, h), c in rows.items() if not h})} classes")
    print("\n== 2. the share of events the hot path handles against the share of oddities (an old duplicate, a gap, an ACK for data never sent) among the segments of an established connection; 8 connections x 2,000 steps")
    print(f"  {'oddities':>9s} | {'events':>7s} {'hot path':>9s} {'share':>7s}   {'cold events per hot event':>26s}")
    for p in (0.0, 0.01, 0.03, 0.1, 0.3):
        e = g.realistic_events(2, 8, 2000, p_odd=p); r, h = classify(e); print(f"  {p * 100:8.0f}% | {len(e):7d} {h:9d} {h / len(e) * 100:6.1f}%   {(len(e) - h) / h:26.3f}")
    print("  an established connection's handshake and close (about 10 events) are a fixed cost per connection; the oddities set the rest. The hot path needs no state machine at all: one state test, one flag test, three comparisons.")
