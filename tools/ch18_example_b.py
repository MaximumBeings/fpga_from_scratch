#!/usr/bin/env python3
"""Chapter 18, example B (model level, cycle for cycle as seq_arb is): what a second feed buys, and what the gap timer costs. (1) Redundancy: both feeds lose each packet with probability p, independently; a packet needs a retransmission only if it is lost on both: derived p^2. Measured over 10 seeds of 200 packets: the fraction of packets lost on both feeds, the requests, the share of messages that came from a retransmission, and the forwarding delay (from the first arrival of a packet on either feed to its forwarding). (2) The timer: A loses 30% of its packets, B is clean but arrives SKEW = 10 cycles later (plus 0 to 3 of jitter); a gap opened by A's loss is normally closed by B's copy about SKEW + jitter cycles later; a request sent before that is SPURIOUS. Measured: requests and spurious requests against TO."""
import os, random, statistics as st, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import arb_gold as G
def delays(res, arr):
    first = {}
    for t, f, q, c in arr:
        if f < 2 and c: first[q] = min(first.get(q, 1 << 60), t)
    return [t - first[q] for t, q, c, f in res["forwarded"] if q in first and f < 2 and t >= first[q]]
def one(seed, n, la, lb, skew=0, to=16, to2=64, rl=0.0, pend=4):
    rng = random.Random(seed); src = G.make_source(rng, n, hb=0.0); arr = G.arrivals(rng, src, la, lb, 0.0, jitter=3, skew=skew); return G.run(arr, 1, pend, to, to2, 30, rl, seed), src, arr
if __name__ == "__main__":
    print("== 1. what the second feed buys (200 packets x 10 seeds, PEND 16, TO 16, retransmissions answered after 30 cycles)")
    print(f"  {'loss per feed p':>15s} | {'lost on both (measured)':>24s} {'p^2 (derived)':>14s} | {'requests':>9s} {'messages from retransmissions':>30s} | {'delay mean':>10s} {'p99':>5s} {'max':>5s} | {'one feed alone: lost':>21s}")
    for p in (0.01, 0.05, 0.1, 0.2, 0.3):
        both = tot = rq = rm = 0; dl = []
        for seed in range(10):
            res, src, arr = one(seed, 200, p, p, pend=16); have = {q for t, f, q, c in arr if f < 2}; both += sum(1 for q, c in src if c and q not in have); tot += len(src); rq += len(res["reqs"])
            rm += sum(c for t, q, c, f in res["forwarded"] if f == 2); dl += delays(res, arr)
        dl.sort(); print(f"  {p * 100:14.0f}% | {both / tot * 100:23.2f}% {p * p * 100:13.2f}% | {rq:9d} {rm:30d} | {st.mean(dl):10.1f} {dl[int(.99 * len(dl))]:5d} {dl[-1]:5d} | {p * 100:20.0f}%")
    print("\n== 1b. the window: loss 5% on each feed, 200 packets x 10 seeds, packets 4 cycles apart, TO 16, retransmission answered after 30 cycles: a gap stays open TO + 30 = 46 cycles, in which 46 / 4 = 11.5 packets arrive behind it")
    print(f"  {'PEND':>4s} | {'requests':>9s} {'messages from retransmissions':>30s} {'lost on both feeds':>19s} {'packets dropped for lack of a slot (OVF)':>41s}")
    for pend in (2, 4, 8, 12, 16):
        rq = rm = ov = lb = 0
        for seed in range(10):
            res, src, arr = one(seed, 200, 0.05, 0.05, pend=pend); rq += len(res["reqs"]); rm += sum(c for t, q, c, f in res["forwarded"] if f == 2); ov += sum(1 for r in res["rows"] if r[1] and r[1][0] == G.OVF)
            have = {q for t, f, q, c in arr if f < 2}; lb += sum(1 for q, c in src if c and q not in have)
        print(f"  {pend:4d} | {rq:9d} {rm:30d} {lb:19d} {ov:41d}")
    print("  (the messages from retransmissions that exceed what was lost on both feeds are packets that DID arrive and were dropped for lack of a slot, then asked for: a window shorter than (TO + answer time) / packet spacing turns a gap into a stream of needless requests)")
    print("\n== 2. the gap timer: A loses 30%, B is clean but 10 cycles late (jitter 0 to 3), 200 packets x 10 seeds, PEND 16, no retransmission is ever needed (every packet reaches the arbiter on B)")
    print(f"  {'TO':>3s} | {'requests':>9s} {'of which spurious (B copy arrived before the answer)':>54s} | {'delay mean':>10s} {'p99':>5s}")
    for to in (2, 4, 8, 11, 12, 13, 14, 16, 24):
        rq = sp = 0; dl = []
        for seed in range(10):
            res, src, arr = one(seed, 200, 0.3, 0.0, skew=10, to=to, pend=16); rq += len(res["reqs"]); sp += len(res["reqs"]); dl += delays(res, arr)
        dl.sort(); print(f"  {to:3d} | {rq:9d} {sp:54d} | {st.mean(dl):10.1f} {dl[int(.99 * len(dl))]:5d}")
    print("  (every request here is spurious: nothing was lost on both feeds. Derived: a gap opened by A's loss lasts until B's copy arrives, at about the skew + the jitter = 10 to 13 cycles after the cycle it would have arrived on A, minus the time the packets behind it take to open the gap; a TO above that never fires)")
