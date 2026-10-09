#!/usr/bin/env python3
"""Chapter 1: one circuit through the whole open flow. (1) golden vectors; (2) the registered adder in two simulators at four widths; (3) synthesis and place-and-route for two FPGA families. Usage: ch01_run.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, radd_gold
F = ["rtl/radd.v", "tb/radd_tb.v"]
def line(out): return ([l for l in out.splitlines() if l.startswith(("PASS", "FAIL", "MISMATCH"))] or out.strip().splitlines()[-2:])[0]
print("== 1+2. golden vectors (directed carry-chain patterns plus 200 random) and the testbench in two simulators, four widths")
for w in (8, 16, 32, 64):
    n = radd_gold.write(w, 200, 1, os.path.join(flow.ROOT, "out", "radd_vec.hex"))
    for name, fn in (("Icarus", flow.sim_icarus), ("Verilator", flow.sim_verilator)):
        rc, out = fn(F, "radd_tb", defines=(f"WIDTH={w}", f"NVEC={n}")); print(f"  W={w:2d} {name:10s}{line(out)} (exit {rc})")
print("\n== 3. the same two circuits (W = 16) through synthesis and place-and-route, two families, target clock 100 MHz")
print(f"  {'family':7s} {'circuit':10s} {'LUT4':>5s} {'flip-flops':>10s} {'carry cells':>12s} {'logic cells used':>17s} {'Fmax (MHz)':>11s}")
for fam in ("ice40", "ecp5"):
    for top, label in (("radd", "a + b"), ("radd_lut", "hand carry")):
        r = flow.run(["rtl/radd.v"], top, fam, 100); print(f"  {fam:7s} {label:10s} {r['luts']:5d} {r['ffs']:10d} {r['carry']:12d} {r['lcs']:>10d} of {r['of']:<5d} {r['fmax']:11.1f}")
print("  iCE40 HX8K (7,680 logic cells) and ECP5 LFE5U-25F (24,288 LUT4/FF pairs): both are real devices in nextpnr's databases. On ECP5 the carry cell (CCU2C) contains two LUT4s, so the '+' adder reports 0 plain LUT4s")
print("\n== 4. what the two devices contain, as nextpnr's own databases list them (resource: used by the 16-bit adder / available)")
for fam, dev in (("ice40", "iCE40 HX8K, package ct256"), ("ecp5", "ECP5 LFE5U-25F, package CABGA381")):
    r = flow.run(["rtl/radd.v"], "radd", fam, 100, "dev_" + fam); log = r["pnr_log"]; i = log.find("Device utilisation"); import re; blk = [l.split("Info:")[-1].strip() for l in log[i:].splitlines()[1:] if re.match(r"Info:\s+\w+:\s+\d+/\s*\d+", l)]
    print(f"  {dev}:"); [print("    " + b) for b in blk]
print("  ICESTORM_LC and TRELLIS_COMB are the logic cells; ICESTORM_RAM (4 Kbit) and DP16KD (18 Kbit) the block RAMs; MULT18X18D the ECP5's 18x18 multipliers (the HX8K has none); PLLs make clocks; DCUA is the ECP5's multi-gigabit serial transceiver, the block real Ethernet needs (Part 2 models it at its interface and does not implement it)")
