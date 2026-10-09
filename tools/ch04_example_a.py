#!/usr/bin/env python3
"""Chapter 4, example A: how many pipeline stages? The same 12-round function cut into S = 1, 2, 3, 4, 6, 12 stages: area (Yosys), Fmax (nextpnr, iCE40 HX8K, seed 1 and the spread over 6 seeds), latency in cycles (exact: S + 1) and in nanoseconds (cycles / Fmax), and the throughput (one item per clock = Fmax items per second). Usage: ch04_example_a.py"""
import os, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import flow
SS = (1, 2, 3, 4, 6, 12)
def build(s):
    r = flow.synth(["rtl/pipe.sv"], "pipe", "ice40", tag=f"p{s}", params={"S": s}); return r
def fm(args): s, seed = args; return flow.pnr(f"out/p{s}.json", "ice40", 400, seed)["fmax"]
if __name__ == "__main__":
    with cf.ThreadPoolExecutor(4) as ex: syn = list(ex.map(build, SS)); runs = list(ex.map(fm, [(s, sd) for s in SS for sd in range(1, 7)]))
    F = {s: runs[i * 6:(i + 1) * 6] for i, s in enumerate(SS)}
    print("== latency, throughput and area of a 12-level function cut into S stages (W = 16 bits; asked for 400 MHz so that nextpnr works as hard as it can)")
    print(f"  {'S':>3s} {'levels/stage':>12s} {'LUTs':>5s} {'FFs':>5s} {'Fmax (seed 1)':>14s} {'Fmax worst of 6':>16s} {'latency cycles':>15s} {'latency ns (seed 1)':>20s} {'latency ns (worst of 6)':>24s}")
    best = None
    for s, y in zip(SS, syn):
        f1 = F[s][0]; fw = min(F[s]); cyc = s + 1; l1 = 1000 * cyc / f1; lw = 1000 * cyc / fw
        print(f"  {s:3d} {12 // s:12d} {y['luts']:5d} {y['ffs']:5d} {f1:11.1f} MHz {fw:13.1f} MHz {cyc:15d} {l1:17.1f} ns {lw:21.1f} ns")
        if best is None or lw < best[1]: best = (s, lw)
    mid = [1000 * (t + 1) / min(F[t]) for t in SS if 2 <= t <= 6]
    print(f"\n  lowest latency in nanoseconds with the worst-of-6 clock: S = {best[0]} ({best[1]:.1f} ns); for S = 2 to 6 the worst-of-6 latency lies between {min(mid):.1f} and {max(mid):.1f} ns, a range smaller than the seed-to-seed spread below")
    print("  adding stages raises Fmax but adds a cycle each, and the clock-to-q, setup and routing of each stage are paid S + 1 times: the latency in ns falls steeply from S = 1, is flat over the middle, and rises again when each stage holds one level")
    print("\n== the spread over six placer seeds (Fmax, MHz)")
    for s in SS: print(f"  S = {s:2d}: " + " ".join(f"{f:6.1f}" for f in F[s]) + f"   spread {100 * (max(F[s]) - min(F[s])) / (sum(F[s]) / 6):.1f}%")
