#!/usr/bin/env python3
"""Chapter 4, example B: cut-through against store-and-forward. (1) Latency in cycles against packet length, from the golden models (the RTL matches them cycle for cycle; ch04_run.py shows it), first beat and last beat, and the sustained packet rate. (2) Determinism: the spread of the first-beat latency over a random traffic mix. (3) What each costs in a real device and what the cut-through filter lets through (bad packets reach the output, flagged on the last beat). Usage: ch04_example_b.py"""
import os, sys, re, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, lat_gold as g
def lat(model, ins, res):
    """For each output packet: (index of its first input beat, first-output cycle - first-input cycle, last-output cycle - last-input cycle). Packets are matched in order among those that produce output."""
    starts = []; ends = []; i = 0
    for k, (v, d, l) in enumerate(ins):
        if v:
            if i == 0: starts.append(k)
            i += 1
            if l: ends.append(k); i = 0
    outs = []; cur = None
    for k, (r, ov, od, ol, ob) in enumerate(res):
        if ov:
            if cur is None: cur = [k, None]
            if ol: cur[1] = k; outs.append(tuple(cur)); cur = None
    return starts, ends, outs
def one_packet_latency(model, n):
    rng = g.random.Random(7); pk = [g.make_packet(rng, n, "good" if n >= 2 else "bad")]; ins = g.schedule(pk, [0]); res = g.run(model, ins); s, e, o = lat(model, ins, res)
    return (o[0][0] - s[0], o[0][1] - e[0]) if o else None
if __name__ == "__main__":
    print("== 1. one kept packet of n beats, alone on the link: cycles from its first input beat to its first output beat, and from its last input beat to its last output beat")
    print(f"  {'n beats':>7s} | {'cut-through first':>17s} {'last':>5s} | {'store-and-forward first':>23s} {'last':>5s}")
    for n in (2, 3, 4, 8, 16, 32):
        c = one_packet_latency(g.CT, n); s = one_packet_latency(g.SF, n); print(f"  {n:7d} | {c[0]:17d} {c[1]:5d} | {s[0]:23d} {s[1]:5d}")
    print("  cut-through: every beat is delayed by one register, whatever the length. Store-and-forward: the first beat leaves only after the last beat has arrived (2 cycles later), so its first-beat latency is n + 1 and its last-beat latency is n + 1 as well, because the packet is then streamed out one beat per cycle.")
    print("\n== 2. determinism: 400 packets of random length (1 to 12 beats; 55% good, 30% bad, 15% dropped), first-beat latency of every packet that produced output")
    for name, model, dense in (("cut-through", g.CT, True), ("store-and-forward", g.SF, False)):
        pk, gp = g.gen(3, (55, 30, 15), 400, 12, dense); ins = g.schedule(pk, gp); res = g.run(model, ins); s, e, o = lat(model, ins, res)
        # match output packets to input packets in order: the input packets that produce output are, in order, those the specification keeps (cut-through: good+bad) or only the good ones (store-and-forward)
        want = [i for i, p in enumerate(pk) if (g.classify(p) in ("good", "bad") if model is g.CT else g.classify(p) == "good")]
        L = [o[j][0] - s[want[j]] for j in range(len(want))]
        hist = {}
        for x in L: hist[x] = hist.get(x, 0) + 1
        print(f"  {name:18s} packets with output {len(L):3d}   first-beat latency min {min(L):2d} max {max(L):2d} distinct values {len(hist):2d}   " + ("histogram " + str(dict(sorted(hist.items()))) if len(hist) <= 6 else "histogram " + str(dict(sorted(hist.items())))))
    print("\n== 3. sustained rate: back-to-back packets of 8 beats (no gap) offered to each filter")
    rng = g.random.Random(5); pk = [g.make_packet(rng, 8, "good") for _ in range(40)]; ins = g.schedule(pk, [0] * 40)
    res_ct = g.run(g.CT, ins); n_ct = sum(r[1] for r in res_ct); cyc_ct = max(k for k, r in enumerate(res_ct) if r[1]) - min(k for k, r in enumerate(res_ct) if r[1]) + 1
    res_sf = g.run(g.SF, ins); acc = [k for k, (v, d, l) in enumerate(ins) if v and res_sf[k][0]]; lost = sum(1 for k, (v, d, l) in enumerate(ins) if v and not res_sf[k][0])
    print(f"  cut-through: 40 packets in, {n_ct // 8} packets out in {cyc_ct} cycles ({n_ct / cyc_ct:.2f} beats per cycle): the link rate is kept")
    print(f"  store-and-forward (one buffer): offered beats refused while it drains: {lost} of {sum(v for v, d, l in ins)}; a source that obeys in_ready is limited, by derivation, to one 8-beat packet per about 16 cycles (fill 8 + drain 8): half the link rate")
    print("\n== 4. what the cut-through filter lets through: 120 random packets, 5:3:2 good:bad:drop")
    pk, gp = g.gen(1, (5, 3, 2), 120, 12, True); ins = g.schedule(pk, gp); from collections import Counter; cl = Counter(g.classify(p) for p in pk)
    print(f"  input: {dict(cl)}   cut-through output: {cl['good'] + cl['bad']} packets, {cl['bad']} of them flagged bad on the last beat; store-and-forward output: {cl['good']} packets, none bad")
    print("  a bad packet has already left, beat by beat, before the filter could know: the receiver of a cut-through stream must be able to discard a packet whose last beat is flagged")
    print("\n== 5. the cost of each in iCE40 HX8K (asked for 200 MHz; seed 1)")
    print(f"  {'filter':20s} {'LUTs':>5s} {'FFs':>5s} {'RAM4K':>5s} {'Fmax MHz':>9s}")
    for name, top, params in (("cut-through", "ct_filter", None), ("store-and-forward 32", "sf_filter", {"DEPTH": 32})):
        r = flow.run(["rtl/pktfilt.sv"], top, "ice40", 200, tag=top, params=params); print(f"  {name:20s} {r['luts']:5d} {r['ffs']:5d} {r['cells'].get('SB_RAM40_4K', 0):5d} {r['fmax']:9.1f}")
