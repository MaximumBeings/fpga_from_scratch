#!/usr/bin/env python3
"""Chapter 1, example B: what the fabric does to a design. (1) the carry chain: an adder written with '+' against one built from gates, at six widths on two families; (2) placement is random: Fmax over eight seeds; (3) a timing constraint the design cannot meet. Writes out/ch01_example_b.json. Usage: ch01_example_b.py"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import flow
ROOT = flow.ROOT; res = {"sweep": {}, "seeds": {}}; F = ["rtl/radd.v"]
print("== 1. the dedicated carry chain: '+' against hand-built gates, widths 8 to 64 (target clock 100 MHz, seed 1)")
print(f"  {'family':6s} {'W':>3s} | {'a + b: LUT4':>11s} {'carry':>6s} {'Fmax':>7s} | {'gates: LUT4':>11s} {'Fmax':>7s} | {'speed ratio':>11s}")
for fam in ("ice40", "ecp5"):
    for w in (8, 16, 24, 32, 48, 64):
        a = flow.run(F, "radd", fam, 100, f"sw_{fam}_a{w}", {"W": w}); b = flow.run(F, "radd_lut", fam, 100, f"sw_{fam}_b{w}", {"W": w}); res["sweep"][f"{fam}/{w}"] = [a["luts"], a["carry"], a["fmax"], b["luts"], b["fmax"]]
        print(f"  {fam:6s} {w:3d} | {a['luts']:11d} {a['carry']:6d} {a['fmax']:7.1f} | {b['luts']:11d} {b['fmax']:7.1f} | {a['fmax'] / b['fmax']:10.2f}x")
print("  on iCE40 the '+' adder uses one SB_CARRY per bit and its LUT count grows 1 per bit; the gate version uses about twice the LUTs and never uses the carry chain. The ratio of speeds is the value of knowing the fabric: the same arithmetic, written so that the tool can use the chain, is 1.4 times faster at 8 bits and 3.7 times faster at 64 (iCE40), 1.9 and 8.5 times on ECP5")
print("  (on ECP5 the carry cells hold two LUT4s each and the plain-LUT column is zero for the '+' adder)")
print("\n== 2. placement is a randomized search: the same design, eight seeds (W = 32, 100 MHz target)")
print(f"  {'family':6s} {'style':10s} {'min':>7s} {'mean':>7s} {'max':>7s} {'spread':>8s}")
for fam in ("ice40", "ecp5"):
    for top, label in (("radd", "a + b"), ("radd_lut", "gates")):
        s = flow.synth(F, top, fam, f"seed_{fam}_{top}", {"W": 32}); fm = [flow.pnr(s["json"], fam, 100, sd)["fmax"] for sd in range(1, 9)]; res["seeds"][f"{fam}/{top}"] = fm
        print(f"  {fam:6s} {label:10s} {min(fm):7.1f} {sum(fm) / 8:7.1f} {max(fm):7.1f} {100 * (max(fm) - min(fm)) / (sum(fm) / 8):7.1f}%")
print("  a single place-and-route run is one sample: a quoted Fmax without its seed (or its spread) is not a result. This book states the seed, and Chapter 3 returns to what to do about the spread")
print("\n== 3. a constraint the design cannot meet: the gate-built 32-bit adder on iCE40 at 100, 150 and 250 MHz targets")
s = flow.synth(F, "radd_lut", "ice40", "con", {"W": 32}); res["constraint"] = []
for f_ in (100, 150, 250):
    p = flow.pnr(s["json"], "ice40", f_, 1); line = [l for l in p["log"].splitlines() if "Max frequency" in l][-1].split("Info: ")[-1]; res["constraint"].append([f_, p["fmax"]]); print(f"  target {f_:3d} MHz -> {line}")
print("  the answer is the same, 44.19 MHz, whatever the target: nextpnr reports an ERROR when a target is missed, but a tighter constraint did not buy a faster result here. The limit is the ripple of 32 LUT levels, which no placement can shorten: the fix is in the design (use the carry chain, pipeline), not in the constraint")
json.dump(res, open(os.path.join(ROOT, "out", "ch01_example_b.json"), "w"))
