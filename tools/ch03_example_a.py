#!/usr/bin/env python3
"""Chapter 3, example A: static timing. (1) A register-logic-register design with D LUT levels: Yosys counts the levels (ltp), nextpnr reports Fmax and splits the critical path into logic and routing time; a straight line period = t0 + D * t_level is fitted. (2) The same design with 12 placer seeds: how much Fmax moves for NOTHING but the random placement, and what clock you can promise. (3) The slack arithmetic at a target clock. Usage: ch03_example_a.py"""
import os, re, subprocess, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import flow
R = flow.ROOT; DS = (1, 2, 3, 4, 6, 8, 10, 12)
def levels(js_tag, D):
    o = subprocess.run(["yosys", "-p", f"read_verilog -sv rtl/tchain.sv; chparam -set D {D} tchain; synth_ice40 -top tchain; ltp -noff"], cwd=R, capture_output=True, text=True).stdout
    m = re.search(r"Longest topological path in tchain \(length=(\d+)\)", o); return int(m.group(1)) if m else None
def split(log):
    i = log.find("Critical path report for clock"); m = re.search(r"Info: ([\d.]+) ns logic, ([\d.]+) ns routing", log[i:]); return float(m.group(1)), float(m.group(2))
def one(D, seed=1):
    s = flow.synth(["rtl/tchain.sv"], "tchain", "ice40", tag=f"tc{D}", params={"D": D}); p = flow.pnr(s["json"], "ice40", 200, seed); return s, p
def fit(xs, ys):
    n = len(xs); mx = sum(xs) / n; my = sum(ys) / n; b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs); a = my - b * mx
    ss = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys)); st = sum((y - my) ** 2 for y in ys); return a, b, 1 - ss / st
if __name__ == "__main__":
    print("== 1. logic depth against Fmax (iCE40 HX8K, seed 1, target 200 MHz so nextpnr tries hard; W = 16 bits wide)")
    print(f"  {'D':>3s} {'LUTs':>5s} {'FFs':>4s} {'levels (ltp)':>12s} {'Fmax MHz':>9s} {'period ns':>10s} {'logic ns':>9s} {'routing ns':>11s} {'routing share':>14s}")
    xs = []; ys = []; rows = {}
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(one, DS))
    for D, (s, p) in zip(DS, res):
        lg, rt = split(p["log"]); per = 1000 / p["fmax"]; xs.append(D); ys.append(per); rows[D] = (s["luts"], s["ffs"], levels(None, D), p["fmax"], per, lg, rt)
        print(f"  {D:3d} {s['luts']:5d} {s['ffs']:4d} {rows[D][2]:12d} {p['fmax']:9.1f} {per:10.2f} {lg:9.1f} {rt:11.1f} {100 * rt / (lg + rt):13.0f}%")
    lg6 = dict(zip(DS, res))[6][1]["log"]; i = lg6.find("Critical path report for clock"); rep = "\n".join(l for l in lg6[i:].split("\n\n")[0].splitlines() if not re.match(r"Info:\s{10,}(Sink|Defined|/|rtl)", l))
    mf = re.findall(r"Max frequency for clock '[^']*': [\d.]+ MHz[^\n]*", lg6)[-1]
    open(os.path.join(R, "out", "ch03_timing_report.txt"), "w").write(rep + "\n\n" + mf + "\n")
    a, b, r2 = fit(xs, ys)
    print(f"\n  fit: period = {a:.2f} ns + {b:.2f} ns per LUT level (R^2 = {r2:.3f}); the {a:.2f} ns is clock-to-q plus setup plus the first route, the {b:.2f} ns is one LUT plus one route")
    print("\n== 2. the same design (D = 6) with 12 placer seeds: only the random start of the placer changes")
    def sd(seed): return flow.pnr(f"out/tc6.json", "ice40", 200, seed)["fmax"]
    with cf.ThreadPoolExecutor(4) as ex: fm = list(ex.map(sd, range(1, 13)))
    print("  seed:  " + " ".join(f"{i:6d}" for i in range(1, 13))); print("  Fmax:  " + " ".join(f"{f:6.1f}" for f in fm))
    lo, hi, mean = min(fm), max(fm), sum(fm) / len(fm)
    print(f"  min {lo:.1f}  mean {mean:.1f}  max {hi:.1f} MHz   spread (max - min) / mean = {100 * (hi - lo) / mean:.1f}%")
    print(f"  a clock you can PROMISE for this design is below the worst seed: {lo:.1f} MHz, and a margin of 10% below that gives {0.9 * lo:.1f} MHz")
    print("\n== 3. slack at a target clock: slack = period - (clock-to-q + logic + routing + setup); negative slack = fails")
    for target in (100, 125, 150):
        per = 1000 / target; line = []
        for sd_, f in zip(range(1, 13), fm): line.append("ok" if 1000 / f <= per else "FAIL")
        print(f"  target {target} MHz (period {per:.1f} ns): seeds that meet it: {line.count('ok')} of 12   slack at the worst seed: {per - 1000 / lo:+.2f} ns")
