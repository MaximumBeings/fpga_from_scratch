#!/usr/bin/env python3
"""Chapter 16 figures -> docs/assets/fig/ch16-*.svg (data from out/ch16_*_out.txt)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figs import Fig, C, bar_chart
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "docs", "assets", "fig"); os.makedirs(OUT, exist_ok=True)
rd = lambda n: open(f"{ROOT}/out/{n}").read()
f = Fig(980, 380, "Flow"); f.text(490, 24, "From a grammar to a parser: the generator, the independent model, and what is compared", 14, bold=True)
f.box(30, 70, 190, 80, ["model/grammar.py", "types, fields, widths"], C["blue2"], C["blue"], 12, True); f.box(30, 230, 190, 80, ["model/itch_gold.py", "its own struct layouts", "(from the protocol)"], C["green2"], C["green"], 12, True)
f.box(290, 70, 190, 80, ["tools/gen_parser.py"], C["orange2"], C["orange"], 12, True); f.box(550, 70, 190, 80, ["rtl/mold_itch.sv", "one byte per clock"], C["purple2"], C["purple"], 12, True)
f.box(550, 230, 190, 80, ["stimulus: packets,", "faults, gaps, resets"], C["gray2"], C["gray"], 12, True); f.box(790, 150, 160, 80, ["compare:", "every message and", "packet end, at its cycle"], C["teal2"], C["teal"], 11.5, True)
f.arrow(222, 110, 288, 110, C["ink"], 1.8); f.arrow(482, 110, 548, 110, C["ink"], 1.8); f.arrow(742, 125, 788, 175, C["ink"], 1.8); f.arrow(222, 270, 788, 205, C["ink"], 1.8); f.arrow(645, 230, 645, 152, C["ink"], 1.6, dash="5 4"); f.arrow(222, 275, 548, 275, C["ink"], 1.6, dash="5 4")
f.text(490, 350, "the model never reads the grammar or the generator: a mistake copied into both layouts is the one the test cannot see", 12, C["ink"], italic=True)
f.save(f"{OUT}/ch16-flow.svg")
A = rd("ch16_example_a_out.txt"); rows = re.findall(r"^\s+(\d+)\s+\d+ \|\s+(\d+)\s+(\d+)\s+([\d.]+) \|\s+(\d+)\s+(\d+)\s+([\d.]+)", A, re.M)
if rows:
    ch = bar_chart(900, 330, [r[0] for r in rows], [[float(r[3]) for r in rows], [float(r[6]) for r in rows]], "Fmax of the generated parser (MHz) against the number of message types (behind the pin wrapper)", "MHz", colors=[C["blue"], C["orange"]], fmt="{:.0f}", maxv=210, legend=["iCE40 HX8K", "ECP5-25"])
    yy = 40 + (330 - 100) * (1 - 125 / 210); ch.line(70, yy, 880, yy, C["red"], 1.8, "6 4"); ch.text(876, yy - 6, "125 MHz", 11, C["red"], "end"); ch.save(f"{OUT}/ch16-fmax.svg")
B = rd("ch16_example_b_out.txt"); rs = re.findall(r"^\s+([a-z ,]+?)\s+\|\s+([\d.]+)%\s+([\d.]+)\s+(\d+)", B, re.M)
if rs: bar_chart(900, 320, [r[0].replace("length, ", "len ").replace(" byte", "") for r in rs], [[float(r[2]) for r in rs]], "Messages right out of 12, after one corrupted byte at each site (400 packets per site)", "messages", colors=[C["green"]], fmt="{:.1f}", maxv=13).save(f"{OUT}/ch16-corrupt.svg")
print("ch16 figures written")
