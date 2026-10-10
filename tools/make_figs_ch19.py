#!/usr/bin/env python3
"""Chapter 19 figures -> docs/assets/fig/ch19-*.svg (data from out/ch19_*_out.txt)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figs import Fig, C, bar_chart, line_chart
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "docs", "assets", "fig"); os.makedirs(OUT, exist_ok=True)
rd = lambda n: open(f"{ROOT}/out/{n}").read()
f = Fig(980, 400, "Book"); f.text(490, 24, "The book: an associative order table, and per symbol two sorted arrays of price levels", 14, bold=True)
f.box(30, 140, 150, 90, ["event", "ADD, EXEC, CANCEL,", "DELETE, REPLACE"], C["gray2"], C["gray"], 11.5, True)
f.box(260, 70, 270, 130, ["order table (NO entries)", "ref, symbol, side, price, shares", "every entry compared with the reference", "in one cycle (an associative search)"], C["blue2"], C["blue"], 11.5, True)
f.box(260, 230, 270, 130, ["levels: NS symbols x 2 sides x D", "sorted, best price first, contiguous", "p = levels better than the price", "insert: shift down; remove: shift up"], C["purple2"], C["purple"], 11.5, True)
f.box(620, 140, 170, 90, ["result + symbol", "OK, UNK, FULL, LVL,", "OVER, DUPREF, ZERO"], C["orange2"], C["orange"], 11.5, True); f.box(820, 140, 140, 90, ["top of book", "bid, ask, levels,", "orders"], C["green2"], C["green"], 11.5, True)
f.arrow(182, 170, 258, 130, C["ink"], 1.8); f.arrow(395, 202, 395, 228, C["ink"], 1.8); f.arrow(532, 130, 618, 175, C["ink"], 1.8); f.arrow(532, 290, 618, 205, C["ink"], 1.8); f.arrow(792, 185, 818, 185, C["ink"], 1.8)
f.text(490, 385, "one event per cycle; REPLACE takes two (delete the old order, add the new) and the input waits", 12, C["ink"], italic=True)
f.save(f"{OUT}/ch19-book.svg")
A = rd("ch19_example_a_out.txt"); rows = re.findall(r"^\s+(\d+)\s+(\d+)\s+(\d+) \|\s+(\d+)\s+(\d+)\s+(\S+(?: fit)?)\s+\|\s+(\d+)\s+\d+\s+\d+\s+([\d.]+)\s+\|\s+(\d+)", A, re.M)
if rows:
    bar_chart(900, 330, [f"NS{r[0]} D{r[1]} NO{r[2]}" for r in rows], [[float(r[6]) / 1000 for r in rows]], "ECP5 LUTs (thousands) of the register-only book, against its size", "kLUT", colors=[C["blue"]], fmt="{:.1f}").save(f"{OUT}/ch19-cost.svg")
    bar_chart(900, 330, [f"NS{r[0]} D{r[1]} NO{r[2]}" for r in rows], [[float(r[7]) for r in rows]], "ECP5 Fmax (MHz) of the register-only book", "MHz", colors=[C["orange"]], fmt="{:.0f}").save(f"{OUT}/ch19-fmax.svg")
B = rd("ch19_example_b_out.txt"); s1 = B.split("== 2.")[0]; rs = re.findall(r"^\s+(\d+) \|\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%", s1, re.M)
if rs: line_chart(900, 330, [float(r[0]) for r in rs], [[float(r[1]) for r in rs], [float(r[2]) for r in rs], [float(r[3]) for r in rs]], "ADDs rejected for lack of a price level (%) against D", "levels per side D", "% rejected", colors=[C["blue"], C["orange"], C["red"]], legend=["spread 4", "spread 8", "spread 16"], xfmt="{:g}", yfmt="{:.0f}").save(f"{OUT}/ch19-levels.svg")
s2 = B.split("== 2.")[1].split("== 3.")[0]; no = re.findall(r"^\s+(\d+) \|\s+([\d.]+)%", s2, re.M)
if no: bar_chart(900, 320, [f"NO {r[0]}" for r in no], [[float(r[1]) for r in no]], "ADDs rejected because the order table is full (%), against NO (target 64 live orders)", "% rejected", colors=[C["purple"]], fmt="{:.1f}", maxv=90).save(f"{OUT}/ch19-orders.svg")
print("ch19 figures written")
