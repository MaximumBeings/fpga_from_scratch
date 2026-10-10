#!/usr/bin/env python3
"""Chapter 21 figures -> docs/assets/fig/ch21-*.svg (data from out/ch21_*_out.txt)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figs import Fig, C, bar_chart
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "docs", "assets", "fig"); os.makedirs(OUT, exist_ok=True)
rd = lambda n: open(f"{ROOT}/out/{n}").read()
f = Fig(980, 400, "Trigger engine"); f.text(490, 24, "The trigger engine: a pipeline, one message per cycle, never stalled", 14, bold=True)
f.box(20, 150, 110, 80, ["message", "type key side", "price shares"], C["gray2"], C["gray"], 11, True)
f.box(160, 60, 150, 100, ["stage 1", "K banks read the", "row h(key);", "message registered"], C["blue2"], C["blue"], 11, True)
f.box(160, 200, 150, 100, ["symbol table", "K banks x NB rows", "{valid, key, index}", "written by address"], C["blue2"], C["blue"], 11, True)
f.box(340, 60, 150, 100, ["stage 2", "K comparators:", "found, index", "(at most one hit)"], C["blue2"], C["blue"], 11, True)
f.box(520, 60, 170, 100, ["stage 3 (+ 3b)", "R rules in parallel:", "type, symbol, side,", "price and shares compares"], C["purple2"], C["purple"], 11, True)
f.box(520, 200, 170, 100, ["rule registers", "R x (en, neg, masks,", "ops, constants)", "written by index"], C["purple2"], C["purple"], 11, True)
f.box(720, 60, 120, 100, ["last stage", "mask, fire,", "first"], C["orange2"], C["orange"], 11, True)
f.box(860, 60, 100, 100, ["answer", "cycle a + 4", "(+1 with", "PIPE 1)"], C["green2"], C["green"], 11, True)
f.arrow(132, 190, 158, 120, C["ink"], 1.6); f.arrow(312, 110, 338, 110, C["ink"], 1.6); f.arrow(492, 110, 518, 110, C["ink"], 1.6); f.arrow(692, 110, 718, 110, C["ink"], 1.6); f.arrow(842, 110, 858, 110, C["ink"], 1.6)
f.arrow(235, 198, 235, 162, C["blue"], 1.4); f.arrow(605, 198, 605, 162, C["purple"], 1.4)
f.text(490, 380, "a write is seen by the messages whose lookup (table) or whose comparison (rules) comes after it; both rules are exact in the model", 12, C["ink"], italic=True)
f.save(f"{OUT}/ch21-engine.svg")
A = rd("ch21_example_a_out.txt"); ar = re.findall(r"^\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+) \|\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+) \|\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)", A, re.M)
if ar: bar_chart(900, 340, [f"{r[0]}x{r[1]} R{r[2]} {r[3]}st" for r in ar], [[float(r[8]) for r in ar], [float(r[13]) for r in ar]], "Fmax (MHz) of the trigger engine; st = comparison stages", "MHz", colors=[C["blue"], C["orange"]], legend=["iCE40", "ECP5"], fmt="{:.0f}").save(f"{OUT}/ch21-fmax.svg")
B = rd("ch21_example_b_out.txt").split("== 2.")[0]
rows = re.findall(r"^\s+(random|ticker)\s+(xor|mult)\s+(\d+) x (\d+)\s+\|\s+[\d.]+%\s+\|\s+[\d.]+%\s+([\d.]+)%", B, re.M)
if rows:
    get = lambda kind, h: [float(r[4]) for r in rows if r[0] == kind and r[1] == h]
    bar_chart(900, 330, ["1024 x 1", "512 x 2", "256 x 4", "128 x 8"], [get("random", "xor"), get("ticker", "xor"), get("ticker", "mult")], "Insertions refused (%) by the time the table is 75% loaded", "% refused", colors=[C["blue"], C["red"], C["green"]], legend=["random keys, XOR fold", "ticker keys, XOR fold", "ticker keys, multiplicative"], fmt="{:.0f}", maxv=100).save(f"{OUT}/ch21-place.svg")
print("ch21 figures written")
