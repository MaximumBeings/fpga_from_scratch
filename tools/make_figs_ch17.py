#!/usr/bin/env python3
"""Chapter 17 figures -> docs/assets/fig/ch17-*.svg (data from out/ch17_*_out.txt)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figs import Fig, C, bar_chart
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "docs", "assets", "fig"); os.makedirs(OUT, exist_ok=True)
rd = lambda n: open(f"{ROOT}/out/{n}").read()
f = Fig(980, 360, "Beat"); f.text(490, 24, "W bytes per clock: the same byte step, W times in a row, and why one beat can hold the end of two blocks", 14, bold=True)
x0 = 40
for k in range(3):
    for j in range(8):
        col = C["blue2"] if (k, j) < (1, 3) else (C["orange2"] if (k, j) < (1, 6) else C["green2"])
        if k == 0: col = C["blue2"]
        f.box(x0 + (k * 8 + j) * 37, 90, 35, 40, "", col, C["gray"], 10)
    f.text(x0 + (k * 8 + 4) * 37 - 18, 80, f"beat {k}", 11, C["line"])
f.text(490, 170, "block A ends in lane 2 of beat 1; a short block B (lanes 3 to 5) ends in the SAME beat", 12, C["ink"])
f.text(490, 198, "-> error 3 (framing): the second completion cannot be reported in the beat's one message slot", 12, C["red"])
f.box(40, 240, 420, 80, ["version 1: one combinational chain of 8 byte steps", "(state, counters, fields): the longest path crosses every lane"], C["orange2"], C["orange"], 11.5, True)
f.box(520, 240, 420, 80, ["version 2: stage 1 frames (state, counters, a tag per lane);", "stage 2 builds the fields from the registered tags"], C["green2"], C["green"], 11.5, True)
f.save(f"{OUT}/ch17-beat.svg")
A = rd("ch17_example_a_out.txt"); rows = re.findall(r"^\s+(\d+)\s+(\d+) \|\s+\d+\s+\d+\s+([\d.]+)\s+([\d.]+) \|\s+\d+\s+\d+\s+([\d.]+)\s+([\d.]+)", A, re.M)
if rows:
    lab = [f"W={r[0]} v{r[1]}" for r in rows]; ch = bar_chart(900, 330, lab, [[float(r[3]) for r in rows], [float(r[5]) for r in rows]], "Throughput of the generated parser (Gbit/s = W x Fmax), behind the pin wrapper", "Gbit/s", colors=[C["blue"], C["orange"]], fmt="{:.2f}", maxv=1.8, legend=["iCE40 HX8K", "ECP5-25"])
    yy = 40 + (330 - 100) * (1 - 1.0 / 1.8); ch.line(70, yy, 880, yy, C["red"], 1.8, "6 4"); ch.text(876, yy - 6, "1 Gbit/s", 11, C["red"], "end"); ch.save(f"{OUT}/ch17-gbit.svg")
B = rd("ch17_example_b_out.txt"); rs = re.findall(r"^\s+8\s+(\d+) \|\s+([\d.]+)%\s+([\d.]+)%", B, re.M)
if rs: bar_chart(900, 320, [f"L={r[0]}" for r in rs], [[float(r[1]) for r in rs], [float(r[2]) for r in rs]], "W = 8: probability that an erroneous block of L bytes trips the framing rule (%)", "%", colors=[C["orange"], C["blue"]], fmt="{:.0f}", maxv=100, legend=["measured", "derived max(0, W - L - 2) / W"]).save(f"{OUT}/ch17-frame.svg")
print("ch17 figures written")
