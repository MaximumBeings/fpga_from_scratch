#!/usr/bin/env python3
"""Chapter 26, example B (model level; the model equals the RTL on every mix of ch26_run.py, for the one-byte-per-cycle parser): (1) THE CLOSED FORM of the cycle budget, checked against every order of every mix: last byte in to first byte out = wait + n + F + 12. (2) WHAT THE BOOK COSTS by type of event. (3) THE FEED RATE AGAINST THE SERVICE RATE: the strategy slot holds one message for n + F + 4 cycles, so the sustainable rate is one message per about n + F + 5 cycles; the parser at one byte per cycle gives one per ~33; what if the feed were 2, 4 or 8 times faster (Chapter 17's wide parser): how many messages does the queue drop, for which queue size. (3) is a MODEL-LEVEL study: the message times are compressed in the model, the RTL was not run on them."""
import os, random, statistics as st, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model")); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import w2w_gold as WG, book2_gold as BG, ch26_run as C
def compress(mev, s):
    """the same messages, arriving s times faster after the start of the feed (one message per cycle at most)"""
    out = {}; last = -1
    for c in sorted(mev):
        c2 = max(WG.P0 + (c - WG.P0) // s, last + 1); out[c2] = mev[c]; last = c2
    return out
if __name__ == "__main__":
    print("== 1. the closed form: total = wait + n + F + 11 + x, for every order of every mix (the mixes of ch26_run.py); x = cycles from the gate's answer to the first byte (1 if the transmitter is ready, more if it is still sending)")
    n_ord = bad = 0; tot = []; xs = []
    for i, kind in enumerate(C.KINDS):
        cm = C.make(kind, i + 1); X = WG.run(cm[0], cm[1], **cm[2])["w2w"]; f = cm[2].get("f", 12)
        for tok, lg in X.log.items():
            if "cx" not in lg: continue
            t = lg["cx"] + 1 - (lg["E"] - 1); w = lg["a"] - (lg["E"] + 1); x = lg["cx"] + 1 - lg["ca"]; n_ord += 1; bad += t != w + lg["n"] + f + 11 + x; tot.append(x); xs.append(t - f)
    print(f"  orders checked {n_ord}, closed form wrong for {bad}; x = 1 for {tot.count(1)} of them (the transmitter was ready) and up to {max(tot)} otherwise; (total - F) from {min(xs)} to {max(xs)} cycles")
    print("\n== 2. what the book costs by type of event (cycles n of Chapter 20's rules; 4000 events from the generator, D = 8, NB = 8, K = 4, 4 symbols)")
    rng = random.Random(26); evs = BG.gen_events(rng, 4000, ns=4, d=8, nb=8, k=4, faults=0.04); b = BG.Book2(4, 8, 8, 4); by = {}
    for e in evs: cy, r, s = b.event(e); by.setdefault((BG.TN[e["t"]], BG.RN[r] if r else "OK"), []).append(cy)
    print(f"  {'event':9s} {'result':6s} {'count':>6s} {'min':>4s} {'mean':>6s} {'max':>4s}")
    for k in sorted(by): v = by[k]; print(f"  {k[0]:9s} {k[1]:6s} {len(v):6d} {min(v):4d} {st.mean(v):6.1f} {max(v):4d}") if len(v) >= 20 else None
    print(f"  the worst case the rules allow (D = 8, K = 4): {BG.worst_case(8, 4)} cycles")
    print("\n== 3. the feed s times faster than one byte per cycle (model only): messages dropped of 99, by queue size QD, on the 'dense' stream; F = 12")
    cm = C.make("dense", 2); mev = cm[1]
    X = WG.W2W()
    for c in range(len(cm[0]) + 200): X.step({}, mev.get(c))
    print(f"  mean strategy-slot occupancy (n + F + 4 + 1, over all {len(X.ns_list)} events): {st.mean(X.ns_list) + 12 + 5:.1f} cycles per message; the feed at one byte per cycle gives one message per {(max(mev) - min(mev)) / len(mev):.1f} cycles")
    print(f"  {'speed':>6s} | " + " ".join(f"{'QD = ' + str(q):>8s}" for q in (2, 4, 8, 16, 32)) + " | mean queue wait at QD 32")
    for s in (1, 2, 4, 8):
        row = []; wait = None
        for q in (2, 4, 8, 16, 32):
            m2 = compress(mev, s); X = WG.W2W(qd=q)
            for c in range(len(cm[0]) + 200): X.step({}, m2.get(c))                      # no control plane: nothing trades, the queue and the strategy slot behave as they do with it
            row.append(X.drops)
            if q == 32: wait = st.mean(X.waits)
        print(f"  {s:6d} | " + " ".join(f"{d:8d}" for d in row) + f" | {wait:.1f}")
