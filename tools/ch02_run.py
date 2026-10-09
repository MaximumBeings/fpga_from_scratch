#!/usr/bin/env python3
"""Chapter 2: the running designs. (1) lint gate on both files; (2) the valid/ready stages and chains against the golden model, five traffic profiles, two simulators; (3) the three frame recognizers against the golden model in two simulators; (4) bounded formal equivalence of the three recognizers with Yosys. Usage: ch02_run.py"""
import os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, vr_gold, frame_gold
R = flow.ROOT; STYLE = ["slow (ready = !valid)", "comb (ready = ready_out | !valid)", "skid (registered ready, two entries)"]
def line(out, keys=("PASS", "FAIL", "MISM", "COMPILE")): return ([l for l in out.splitlines() if l.startswith(keys)] or out.strip().splitlines()[-2:])[0]
print("== 1. lint gate: Verilator -Wall --lint-only and Yosys 'check' on the two design files (the files must be clean before anything is simulated)")
for f, top in (("rtl/vr.sv", "vr_chain"), ("rtl/frame_fsm.sv", "frame_b")):
    p = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", top, f], cwd=R, capture_output=True, text=True); w = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning")]
    y = subprocess.run(["yosys", "-p", f"read_verilog -sv {f}; hierarchy -top {top}; proc; opt_clean; check"], cwd=R, capture_output=True, text=True).stdout; yw = [l for l in y.splitlines() if "Warning" in l and "check" not in l.lower()[:5]]
    print(f"  {f:18s} Verilator warnings: {len(w)}   Yosys check problems: {len([l for l in y.splitlines() if 'Found and reported' in l and not l.strip().endswith(' 0 problems.')])}")
print("\n== 2. valid/ready stages: cycle-accurate golden vectors, a compliant-source protocol test and a throughput test (16-bit data, seed 1, 300 cycles of vectors)")
print(f"  {'style':40s} {'stages':>6s} {'profile':12s} {'Icarus':>8s} {'Verilator':>10s}")
tput = {}
for st in range(3):
    for n in (1, 4):
        for prof in ("free", "bursty", "slow_sink", "slow_source", "random"):
            vr_gold.write(st, n, 16, 300, 1, prof, os.path.join(R, "out", "vr_vec.hex")); d = ("WIDTH=16", f"NSTAGES={n}", f"STYLE={st}", "NCYC=300")
            rc, o = flow.sim_icarus(["rtl/vr.sv", "tb/vr_tb.sv"], "vr_tb", defines=d); ok_i = "PASS" if line(o).startswith("PASS") else line(o); m = re.search(r"TPUT style \d stages \d+: 1000 items in (\d+) cycles; first item out after (\d+) cycles", o)
            if m and prof == "random": tput[(st, n)] = (int(m.group(1)), int(m.group(2)))
            ok_v = "-"
            if n == 4 and prof in ("random", "bursty"): rc, o = flow.sim_verilator(["rtl/vr.sv", "tb/vr_tb.sv"], "vr_tb", defines=d); ok_v = "PASS" if line(o).startswith("PASS") else line(o)
            print(f"  {STYLE[st]:40s} {n:6d} {prof:12s} {ok_i:>8s} {ok_v:>10s}")
print("\n  throughput and latency (valid = ready = 1 throughout; items per 1000 cycles and cycles from offer to first output):")
for st in range(3):
    for n in (1, 4): c, f = tput[(st, n)]; print(f"  {STYLE[st]:40s} {n} stage(s): 1000 items in {c} cycles ({1000 / c:.2f} items per cycle), first item out after {f} cycles")
print("\n== 3. the three frame recognizers against the golden model (3,000 cycles, 129 frames, 88 aborts), two simulators")
frame_gold.write(3000, 1, os.path.join(R, "out", "frame_vec.hex"))
for name, fn in (("Icarus", flow.sim_icarus), ("Verilator", flow.sim_verilator)):
    rc, o = fn(["rtl/frame_fsm.sv", "tb/frame_tb.sv"], "frame_tb", defines=("NCYC=3000",)); print(f"  {name:10s}{line(o)}")
print("\n== 4. bounded formal equivalence with Yosys: a miter of two recognizers, a SAT solver, 30 cycles from reset (a longest frame is 19 bytes)")
for a, b in (("frame_a", "frame_b"), ("frame_a", "frame_c"), ("frame_b", "frame_c")):
    o = subprocess.run(["yosys", "-p", f"read_verilog -sv rtl/frame_fsm.sv; proc; opt_clean; miter -equiv -flatten -make_assert {a} {b} m; hierarchy -top m; sat -seq 30 -set-at 1 in_rst 1 -prove-asserts -prove-skip 1"], cwd=R, capture_output=True, text=True).stdout
    print(f"  {a} against {b}: " + ("equivalent for every input sequence of 30 cycles after a reset (no counterexample exists)" if "no model found: SUCCESS" in o else "DIFFERENT: a counterexample exists"))
print("  a bounded proof says nothing beyond its bound: Chapter 6 adds induction and the properties that make an unbounded proof possible")
