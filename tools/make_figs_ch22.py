#!/usr/bin/env python3
"""Chapter 22 figures -> docs/assets/fig/ch22-*.svg (data from out/ch22_*_out.txt)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figs import Fig, C, bar_chart, line_chart
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "docs", "assets", "fig"); os.makedirs(OUT, exist_ok=True)
rd = lambda n: open(f"{ROOT}/out/{n}").read()
f = Fig(980, 380, "Signal unit"); f.text(490, 24, "The signal unit: one division, one multiplication, one addition, bit for bit", 14, bold=True)
f.box(20, 140, 120, 90, ["top of book", "bid price, shares", "ask price, shares"], C["gray2"], C["gray"], 11, True)
f.box(170, 140, 130, 90, ["stage 0", "both sides?", "D = Qb + Qa", "S = Pa - Pb, Pa + Pb"], C["blue2"], C["blue"], 11, True)
f.box(330, 140, 150, 90, ["divider: F steps", "r = Qb; double,", "subtract D if it fits;", "pipelined or shared"], C["purple2"], C["purple"], 11, True)
f.box(510, 140, 130, 90, ["A: round", "w = t + (2r >= D)", "imb = 2w - 2^F"], C["purple2"], C["purple"], 11, True)
f.box(670, 140, 120, 90, ["B: multiply", "S x w", "(a DSP block)"], C["orange2"], C["orange"], 11, True)
f.box(820, 140, 140, 90, ["C: add, gate", "micro = Pb 2^F + S w", "all 0 if a side is empty"], C["green2"], C["green"], 11, True)
for x1, x2 in ((142, 168), (302, 328), (482, 508), (642, 668), (792, 818)): f.arrow(x1, 185, x2, 185, C["ink"], 1.7)
f.text(490, 290, "answer in cycle a + F + 4;  pipelined divider: one book per cycle;  shared divider: one book per F + 4 cycles", 12, C["ink"], italic=True)
f.text(490, 315, "outputs: ok, mid (half ticks), spread, cross, lock, w, imbalance (Q1.F), microprice (ticks x 2^F)", 12, C["ink"], italic=True)
f.save(f"{OUT}/ch22-unit.svg")
B = rd("ch22_example_b_out.txt"); s1 = B.split("== 2.")[0]
rows = re.findall(r"^\s+(\d+) \|\s+([\d.]+)\s+([\d.]+) \|\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", s1, re.M)
if rows: line_chart(900, 330, [float(r[0]) for r in rows], [[float(r[1]) for r in rows], [float(r[3]) for r in rows]], "Largest error against the exact value, by fraction bits F", "fraction bits F", "error", colors=[C["blue"], C["red"]], legend=["imbalance (units of 1)", "microprice (ticks)"], logy=True, xfmt="{:g}", yfmt="{:.0e}").save(f"{OUT}/ch22-error.svg")
s3 = B.split("== 3.")[1]; wr = re.findall(r"^\s+([\d.]+)\s+([\d.]+)\s+\|\s+([\d.]+)\s+(\d+)", s3, re.M)
if wr: line_chart(900, 330, [float(r[1]) for r in wr], [[max(0.5, float(r[2])) for r in wr]], "Mean wait for the shared divider (cycles) against load (books per 16 cycles)", "offered books per 16 cycles (1.0 = the divider's capacity)", "mean wait, cycles", colors=[C["orange"]], legend=["shared divider (F = 12)"], logy=True, xfmt="{:g}", yfmt="{:.0f}").save(f"{OUT}/ch22-wait.svg")
A = rd("ch22_example_a_out.txt"); ar = re.findall(r"^\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d)\s+(\d+) \|\s+(\d+)\s+(\d+)\s+([\d.]+) \|\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+) \|\s+(\d+)\s+([\d.]+)", A, re.M)
if ar: bar_chart(900, 340, [f"{r[0]}/{r[1]}/F{r[2]}/D{r[3]}" for r in ar], [[float(r[7]) for r in ar], [float(r[11]) for r in ar], [float(r[13]) for r in ar]], "Fmax (MHz): PW/QW/F/DIV", "MHz", colors=[C["blue"], C["orange"], C["gray"]], legend=["iCE40 (no DSP)", "ECP5 with DSP", "ECP5 without DSP"], fmt="{:.0f}").save(f"{OUT}/ch22-fmax.svg")
print("ch22 figures written")
