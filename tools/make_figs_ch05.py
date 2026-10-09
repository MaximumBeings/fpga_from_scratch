#!/usr/bin/env python3
"""Chapter 5 figures -> docs/assets/fig/ch05-*.svg (data from out/ch05_*_out.txt)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
from figs import Fig, C, bar_chart, line_chart
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "docs", "assets", "fig"); os.makedirs(OUT, exist_ok=True)
A = open(f"{ROOT}/out/ch05_example_a_out.txt").read(); B = open(f"{ROOT}/out/ch05_example_b_out.txt").read()
# 5.1 Q format: bits of a Q1.15 number, a Q2.30 product and a 40-bit accumulator
f = Fig(940, 330, "Q formats"); f.text(470, 24, "Fixed point: where the binary point sits, and what the guard bits are for", 14, bold=True)
def row(y, label, sign, ints, fracs, x0=170, w=15):
    f.text(14, y + 22, label, 12, anchor="start", bold=True); x = x0
    f.rect(x, y, w, 36, C["red2"], C["red"], 1.3, 2); f.text(x + w / 2, y + 23, "s", 10); x += w
    for k in range(ints): f.rect(x, y, w, 36, C["blue2"], C["blue"], 1.3, 2); x += w
    xp = x
    for k in range(fracs): f.rect(x, y, w, 36, C["green2"], C["green"], 1.3, 2); x += w
    f.line(xp, y - 6, xp, y + 42, C["ink"], 2.4); return xp, x
row(50, "Q1.15 operand", 1, 0, 15); row(110, "Q2.30 product", 1, 1, 30, w=15); row(170, "40-bit sum (Q10.30)", 1, 9, 30, w=15)
row(230, "Q1.15 result", 1, 0, 15)
f.text(470, 282, "red: sign    blue: integer bits    green: fraction bits    black line: the binary point", 11.5, C["line"], italic=True)
f.text(470, 302, "the product has twice the fraction bits; the sum has eight guard bits (256 products at full scale); the result drops 15 fraction bits (round) and any integer bits (saturate)", 11.5, C["line"], italic=True)
f.save(f"{OUT}/ch05-qformat.svg")
# 5.2 rounding: truncate vs round half up, a staircase
f = Fig(940, 320, "Rounding"); f.text(470, 24, "Narrowing by 4 bits: truncate (floor) and round half up, for inputs -24 to 24", 14, bold=True)
x0, y0, sx, sy = 70, 150, 16, 12
f.line(x0, y0, x0 + 49 * sx, y0, C["gray"], 1.2); f.line(x0 + 24 * sx, 40, x0 + 24 * sx, 290, C["gray"], 1.2)
f.line(x0, y0 + 24 / 16 * 30, x0 + 49 * sx, y0 - 24 / 16 * 30, C["ink"], 1.6, "5 4")
for x in range(-24, 25):
    t = x >> 4; r = (x + 8) >> 4
    f.rect(x0 + (x + 24) * sx + 1, y0 - t * 30 - (30 if t >= 0 else 0) + (0 if t >= 0 else 0), sx - 2, 4, C["red"], None, 0, 1)
    f.rect(x0 + (x + 24) * sx + 1, y0 - r * 30 - 2, sx - 2, 4, C["green"], None, 0, 1)
f.text(470, 312, "dashed: x / 16 exactly.   red: truncate (floor), always at or below it.   green: round half up, centred on it", 11.5, C["line"], italic=True)
f.save(f"{OUT}/ch05-round.svg")
# 5.3 multiplier cost: LUTs against width, with and without DSP
rows = re.findall(r"^\s+(\d+) \|\s+(\d+)\s+(\d+)\s+([\d.]+) MHz \|\s+(\d+)\s+(\d+)\s+([\d.]+) MHz \|\s+(\d+)\s+(\d+)\s+([\d.]+) MHz", A, re.M)
ws = [int(r[0]) for r in rows]
line_chart(900, 340, ws, [[int(r[4]) for r in rows], [int(r[7]) for r in rows]], "LUTs in a registered W x W multiplier built from logic (no DSP)", "operand width W (bits)", "LUT4s", colors=[C["red"], C["orange"]], legend=["ECP5, LUTs only", "iCE40"], xfmt="{:.0f}", yfmt="{:.0f}", ymin=0).save(f"{OUT}/ch05-mulluts.svg")
line_chart(900, 340, ws, [[float(r[3]) for r in rows], [float(r[6]) for r in rows], [float(r[9]) for r in rows]], "Fmax of a registered W x W multiplier (nextpnr, seed 1)", "operand width W (bits)", "MHz", colors=[C["green"], C["red"], C["orange"]], legend=["ECP5 with DSP", "ECP5 LUTs only", "iCE40"], xfmt="{:.0f}", yfmt="{:.0f}", ymin=0).save(f"{OUT}/ch05-mulfmax.svg")
# 5.4 FIR forms
f = Fig(940, 330, "FIR forms"); f.text(470, 24, "The same eight-tap filter: direct form (one long path) and transposed form (a register between adders)", 14, bold=True)
for k in range(4):
    x = 60 + k * 100; f.box(x, 60, 70, 34, "z^-1", C["blue2"], C["blue"], 11, True); f.box(x + 6, 118, 58, 28, "x c", C["orange2"], C["orange"], 11, True)
f.box(480, 100, 130, 60, ["8-input", "adder tree"], C["red2"], C["red"], 12, True); f.box(660, 100, 100, 60, "reg", C["blue2"], C["blue"], 12, True)
f.text(40, 52, "direct", 12.5, anchor="start", bold=True); f.text(470, 190, "all the products and the whole adder tree sit between two registers", 11.5, C["line"], italic=True)
for k in range(4):
    x = 60 + k * 190; f.box(x, 232, 60, 30, "x c", C["orange2"], C["orange"], 11, True); f.box(x + 80, 232, 40, 30, "+", C["gray2"], C["gray"], 12, True); f.box(x + 130, 232, 36, 30, "reg", C["blue2"], C["blue"], 11, True)
f.text(40, 224, "transposed", 12.5, anchor="start", bold=True); f.text(470, 296, "each register-to-register path holds one multiplier and one adder; the products are added in a chain of registers", 11.5, C["line"], italic=True)
f.save(f"{OUT}/ch05-fir.svg")
# 5.5 memory: block RAM count against depth on iCE40 and ECP5 style 1
ice = re.search(r"iCE40 HX8K.*?\n\n  ECP5", B, re.S).group(0); ecp = B.split("ECP5 (18-kbit")[1].split("== 2.")[0]
def blk(txt, D): m = re.search(rf"^\s+{D}\s+1\s+\d+\s+\d+\s+(\d+)", txt, re.M); return int(m.group(1)) if m else 0
Ds = [256, 1024, 4096]
bar_chart(900, 320, [str(d) for d in Ds], [[blk(ice, d) for d in Ds], [blk(ecp, d) for d in Ds]], "Block RAMs used by a 16-bit memory with a synchronous read", "block RAMs", colors=[C["teal"], C["purple"]], fmt="{:.0f}", legend=["iCE40 (4-kbit blocks)", "ECP5 (18-kbit blocks)"]).save(f"{OUT}/ch05-bram.svg")
print("ch05 figures written")
