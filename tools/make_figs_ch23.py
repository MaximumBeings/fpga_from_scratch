#!/usr/bin/env python3
"""Chapter 23 figures -> docs/assets/fig/ch23-*.svg (data from out/ch23_*_out.txt)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figs import Fig, C, bar_chart, line_chart
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "docs", "assets", "fig"); os.makedirs(OUT, exist_ok=True)
rd = lambda n: open(f"{ROOT}/out/{n}").read()
f = Fig(980, 420, "Risk gate"); f.text(490, 24, "The risk gate: an order passes only if every limit holds after it; the gate fails closed", 14, bold=True)
f.box(20, 150, 110, 80, ["event", "order, fill,", "cancel"], C["gray2"], C["gray"], 11, True)
f.box(160, 150, 130, 80, ["stage 1", "register the event,", "price x quantity", "(the multiplier)"], C["blue2"], C["blue"], 11, True)
f.box(320, 60, 330, 110, ["stage 2: the checks, in order", "KILL, DISARMED (or a fault), BADIDX, QTY, BAND,", "ONOT, POS (worst case, open orders counted),", "NOT (total open notional), RATE (a token)"], C["purple2"], C["purple"], 11, True)
f.box(320, 200, 330, 90, ["stage 2: the update (same cycle)", "an accepted order adds to the open quantity, the", "notional and takes a token; a release subtracts;", "a release of more than is open is a FAULT (latched)"], C["purple2"], C["purple"], 11, True)
f.box(680, 150, 130, 80, ["answer", "result + the", "state touched"], C["orange2"], C["orange"], 11, True)
f.box(840, 150, 120, 80, ["fail closed", "disarmed at reset,", "limits 0, kill,", "fault latch"], C["green2"], C["green"], 11, True)
f.arrow(132, 190, 158, 190, C["ink"], 1.7); f.arrow(292, 175, 318, 125, C["ink"], 1.7); f.arrow(292, 200, 318, 240, C["ink"], 1.7); f.arrow(652, 125, 678, 175, C["ink"], 1.7); f.arrow(652, 240, 678, 205, C["ink"], 1.7); f.arrow(812, 190, 838, 190, C["ink"], 1.7)
f.text(490, 330, "one event per cycle, answered two cycles after it is offered; state in registers; decision and update in ONE cycle (no hazard between events)", 12, C["ink"], italic=True)
f.text(490, 355, "limits at run time: max long / short, max quantity, max order notional, max total notional, token bucket; per symbol a price band", 12, C["ink"], italic=True)
f.save(f"{OUT}/ch23-gate.svg")
B = rd("ch23_example_b_out.txt"); s1 = B.split("== 2.")[0]
rows = re.findall(r"^\s+(\d+) \|\s+\d+\s+([\d.]+)%", s1, re.M)
if rows: bar_chart(900, 320, [f"limit {r[0]}" for r in rows], [[float(r[1]) for r in rows]], "Orders refused for the position limit (%), by limit", "% refused", colors=[C["purple"]], fmt="{:.1f}", maxv=60).save(f"{OUT}/ch23-pos.svg")
s2 = B.split("== 2.")[1].split("== 3.")[0]; rr = re.findall(r"^\s+(\d+) \|\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%", s2, re.M)
if rr: bar_chart(900, 330, [f"R = {x}" for x in (2, 4, 8, 16)], [[float(r[i]) for r in [row for row in rr if row[0] == c]][0:1] and [float(row[1 + k]) for row in [x for x in rr if x[0] == c] for k in range(4)] for i, c in enumerate(("1", "4"))], "Orders refused for the rate limit (%), by refill period; buckets of 1 and 4", "% refused", colors=[C["orange"], C["blue"]], legend=["bucket 1", "bucket 4"], fmt="{:.0f}", maxv=100).save(f"{OUT}/ch23-rate.svg")
A = rd("ch23_example_a_out.txt"); ar = re.findall(r"^\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+) \|\s+(\d+)\s+(\d+)\s+(\S+(?: fit)?)\s+\|\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+) \|\s+(\d+)\s+([\d.]+)", A, re.M)
if ar: bar_chart(900, 340, [f"{r[0]}x{r[1]} q{r[2]}" for r in ar], [[float(r[5]) / 1000 for r in ar], [float(r[8]) / 1000 for r in ar]], "LUTs (thousands) of the register-based gate: iCE40 and ECP5", "kLUT", colors=[C["blue"], C["orange"]], legend=["iCE40", "ECP5"], fmt="{:.1f}").save(f"{OUT}/ch23-cost.svg")
print("ch23 figures written")
