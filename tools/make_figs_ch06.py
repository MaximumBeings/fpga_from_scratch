#!/usr/bin/env python3
"""Chapter 6 figures -> docs/assets/fig/ch06-*.svg (data from out/ch06_run_out.txt and out/ch06_mut_out.txt)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
from figs import Fig, C, bar_chart, line_chart
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "docs", "assets", "fig"); os.makedirs(OUT, exist_ok=True)
R = open(f"{ROOT}/out/ch06_run_out.txt").read(); M = open(f"{ROOT}/out/ch06_mut_out.txt").read()
# 6.1 the harness
f = Fig(940, 380, "Harness"); f.text(470, 24, "The verification harness: one model, one vector file, two simulators, one formal flow", 14, bold=True)
f.box(30, 60, 150, 56, ["stimulus", "directed / random /", "constrained"], C["blue2"], C["blue"], 11, True); f.box(30, 160, 150, 50, ["golden model", "(Python: the spec)"], C["green2"], C["green"], 11.5, True)
f.box(260, 100, 150, 64, ["vector file", "inputs + expected", "outputs, per cycle"], C["yellow2"], C["line"], 11.5, True)
f.box(500, 54, 190, 56, ["Icarus: SystemVerilog", "testbench, compares"], C["orange2"], C["orange"], 11.5, True); f.box(500, 130, 190, 56, ["Verilator: C++ driver,", "compares, counts cycles/s"], C["orange2"], C["orange"], 11.5, True)
f.box(740, 92, 170, 66, ["DUT (sfifo)", "with BUG = 0..6", "or a generated mutant"], C["gray2"], C["gray"], 11.5, True)
f.arrow(182, 90, 258, 118, C["ink"], 1.8); f.arrow(182, 185, 258, 150, C["ink"], 1.8); f.arrow(412, 125, 498, 84, C["ink"], 1.8); f.arrow(412, 140, 498, 156, C["ink"], 1.8); f.arrow(692, 82, 738, 112, C["ink"], 1.6); f.arrow(692, 158, 738, 138, C["ink"], 1.6)
f.box(30, 250, 220, 56, ["coverage bins", "(on the model's state)"], C["teal2"], C["teal"], 11.5, True); f.arrow(110, 118, 110, 248, C["teal"], 1.6, 8, "5 4")
f.box(330, 250, 280, 56, ["formal: assert properties on the DUT with", "free inputs (Yosys SAT: bounded + induction)"], C["purple2"], C["purple"], 11, True)
f.box(700, 250, 210, 56, ["mutation library:", "generate, run battery, score"], C["red2"], C["red"], 11.5, True)
f.text(470, 350, "simulation checks what the stimulus reaches; formal checks every input sequence up to a bound; mutation testing checks the tests", 12, C["line"], italic=True)
f.save(f"{OUT}/ch06-harness.svg")
# 6.2 speed
sp = re.findall(r"([\d.]+) million cycles per second", R.split("== 3.")[0])
if len(sp) >= 2: bar_chart(900, 300, ["Icarus", "Verilator (whole run, incl. file)"], [[float(sp[0]), float(sp[1])]], "Simulated cycles per second (millions)", "million cycles / s", colors=[C["orange"]], fmt="{:.2f}").save(f"{OUT}/ch06-speed.svg")
# 6.3 coverage
cov = re.findall(r"^\s+(directed \(44 cycles\)|uniform 200 cycles|constrained 200 cycles|uniform 2000 cycles|constrained 2000 cycles)\s+(\d+) of", R, re.M)
bar_chart(900, 320, ["directed 44", "uniform 200", "constrained 200", "uniform 2000", "constrained 2000"], [[int(c[1]) for c in cov]], "Functional coverage: bins hit (of 18)", "bins", colors=[C["teal"]], fmt="{:.0f}", maxv=20).save(f"{OUT}/ch06-coverage.svg")
# 6.4 cycles to first detection
rows = re.findall(r"^\s+(\d)\s+(\d+)\s+(\d+)\s+(\d+) \|\s+(\d+)\s+(\d+)\s+(\d+)\s*$", R, re.M)
bar_chart(900, 320, [f"bug {r[0]}" for r in rows], [[int(r[1]) for r in rows], [int(r[4]) for r in rows]], "Median cycles until the first mismatch, 40 seeds", "cycles", colors=[C["blue"], C["orange"]], fmt="{:.0f}", legend=["uniform random", "constrained random"]).save(f"{OUT}/ch06-detect.svg")
# 6.5 injected bugs found by each technique (of 6) within the stated budget
sec = R.split("== 3.")[1].split("\n\n")[0]; rows = []
for line in sec.splitlines():
    if re.match(r"^\s+[1-6]\s", line): rows.append(re.findall(r"missed|at cycle \d+|found", line.split("  ", 3)[-1] if False else line[56:]))
cnt = [sum(1 for r in rows if not r[i].startswith("missed")) for i in range(4)]
bar_chart(900, 320, ["directed (44 cycles)", "uniform random (2000)", "constrained random (2000)", "formal (20 cycles)"], [cnt], "Injected bugs found (of 6)", "bugs", colors=[C["red"]], fmt="{:.0f}", maxv=7).save(f"{OUT}/ch06-found.svg")
print("ch06 figures written")
