#!/usr/bin/env python3
"""Chapter 13, example B: (1) the fixed-point RTO against RFC 6298 in floating point; (2) a transfer under loss: ticks, retransmissions, and what the backoff and the go-back-N cost; (3) the RTO as a function of the round-trip jitter. All from the model (model/tx_gold.py), whose RTL equivalence is ch13_run.py sections 3 and 4. Usage: ch13_example_b.py"""
import os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import tx_gold as g
def series(seed, n, lo, hi):
    rng = random.Random(seed); return [rng.randint(lo, hi) for _ in range(n)]
def fixed_rtos(rs, rto_min=100, rto_max=6000):
    s = g.Sender(isn=0, rto_min=rto_min, rto_max=rto_max); out = []
    for r in rs:
        s.timing_on = 1; s.rtt_t0 = 0; s.rtt_seq = 1; s._sample(r); out.append(s.rto)
    return out
if __name__ == "__main__":
    print("== 1. the fixed-point RTO (SRTT x 8 and RTTVAR x 4 as integers, G = 1 tick) against RFC 6298 in floating point, 200 random round-trip times per series; RTO clamped to [100, 6000] ticks")
    print(f"  {'RTT range (ticks)':>18s} {'series':>7s} {'max |fixed - float|':>20s} {'mean |diff|':>12s} {'max diff / RTO':>15s}")
    for lo, hi in ((20, 60), (50, 400), (300, 3000), (1, 20)):
        mx = 0.0; sm = 0.0; n = 0; rel = 0.0
        for seed in range(50):
            rs = series(seed, 200, lo, hi); fx = fixed_rtos(rs); fl = g.rto_float(rs)
            for a, b in zip(fx, fl): d = abs(a - b); mx = max(mx, d); sm += d; n += 1; rel = max(rel, d / b)
        print(f"  {lo:8d} .. {hi:<7d} {50:7d} {mx:17.2f} ticks {sm / n:12.3f} {rel * 100:14.2f}%")
    print("  the difference is the truncation of the shifts (SRTT = srtt8 >> 3 loses up to 7/8 of a tick, RTTVAR = rv4 >> 2 up to 3/4 of a tick per update); it does not accumulate because the integers carry the fractions")
    print("\n== 2. a transfer of 20,000 bytes (200 segments of 100) over a channel with round trip 40 +- 10 ticks, the one-way loss shown, in both directions; 10 seeds each")
    print(f"  {'loss':>5s} | {'mean ticks':>11s} {'max ticks':>10s} {'mean retx segments':>19s} {'retx / loss-free segments':>26s} {'ideal ticks (loss-free)':>24s}")
    base = None
    for loss in (0.0, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2):
        rs = [g.transfer(seed, 20000, loss=loss, mss=100) for seed in range(10)]
        assert all(r["delivered"] == 20000 for r in rs)
        t = sum(r["done_tick"] for r in rs) / 10; base = base or t
        print(f"  {loss * 100:4.1f}% | {t:11.0f} {max(r['done_tick'] for r in rs):10d} {sum(r['retx'] for r in rs) / 10:19.0f} {sum(r['retx'] for r in rs) / 10 / 200:25.2f}x {base:24.0f}")
    print("  go-back-N resends everything after the loss: a loss of one segment in a flight of 100 costs about a hundred retransmissions; fast retransmit and selective acknowledgements (not modelled) avoid it")
    print("\n== 3. the RTO the estimator settles on against the round-trip jitter (RTT 100 +- jitter, 1000 samples)")
    print(f"  {'jitter':>7s} {'final SRTT':>11s} {'final RTTVAR':>13s} {'final RTO':>10s} {'RTO / mean RTT':>15s}")
    for jit in (0, 5, 20, 50, 90):
        s = g.Sender(isn=0, rto_min=1, rto_max=100000)
        for r in series(3, 1000, 100 - jit, 100 + jit): s.timing_on = 1; s.rtt_t0 = 0; s.rtt_seq = 1; s._sample(r)
        print(f"  {jit:7d} {s.srtt8 / 8:11.1f} {s.rv4 / 4:13.1f} {s.rto:10d} {s.rto / 100:14.2f}x")
