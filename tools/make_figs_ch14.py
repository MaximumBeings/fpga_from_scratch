#!/usr/bin/env python3
"""Chapter 14 figures -> docs/assets/fig/ch14-*.svg (data from out/ch14_*_out.txt)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figs import Fig, C, bar_chart, line_chart
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "docs", "assets", "fig"); os.makedirs(OUT, exist_ok=True)
rd = lambda n: open(f"{ROOT}/out/{n}").read()
# 14.1 the three pairings
f = Fig(980, 420, "Pairings"); f.text(490, 24, "Three pairings of the designs of Chapters 12 and 13 with an independent reference, over one impaired network", 14, bold=True)
def row(y, left, mid, right, tag, fl_l, st_l, fl_r, st_r):
    f.box(30, y, 200, 80, left, fl_l, st_l, 11.5, True); f.box(380, y + 10, 220, 60, mid, C["gray2"], C["gray"], 11, False); f.box(750, y, 200, 80, right, fl_r, st_r, 11.5, True)
    f.arrow(232, y + 28, 378, y + 28, C["ink"], 1.8); f.arrow(602, y + 28, 748, y + 28, C["ink"], 1.8); f.arrow(748, y + 56, 604, y + 56, C["ink"], 1.4, dash="5 4"); f.arrow(378, y + 56, 234, y + 56, C["ink"], 1.4, dash="5 4")
    f.text(490, y + 100, tag, 11.5, C["line"], italic=True)
row(50, ["DUT sender", "tx_gold / tx_conn", "(Chapter 13)"], ["network: loss,", "duplication, reordering,", "forged segments"], ["reference receiver", "(out-of-order buffer,", "real bytes)"], "A: the DUT's data, retransmissions and timer meet an independent receiver", C["blue2"], C["blue"], C["green2"], C["green"])
row(170, ["reference client", "(handshake, fixed timeout,", "fast retransmit, close)"], ["the same network", ""], ["DUT receiver", "tcp_gold / tcp_conn", "(Chapter 12)"], "B: an independent sender drives the DUT's handshake, data and close", C["green2"], C["green"], C["blue2"], C["blue"])
row(290, ["DUT sender", "(Chapter 13)"], ["the same network", ""], ["DUT receiver", "(Chapter 12)"], "C: the two designs against each other", C["blue2"], C["blue"], C["blue2"], C["blue"])
f.text(490, 408, "after every event: the invariants; at the end: every byte once, in order; then the recorded events replay on the RTL", 12, C["ink"], italic=True)
f.save(f"{OUT}/ch14-pairings.svg")
# 14.2 ticks by profile
R = rd("ch14_run_out.txt"); sec = R.split("== 2b.")[0]
rows = re.findall(r"^\s+(.+?)\s+\|\s+([ABC])\s+(\d+)/20\s+(\d+)\s+(\d+)\s+([\d.]+)", sec, re.M)
prof = []
for nm, lab, ok, mean, mx, rt in rows:
    if nm not in prof: prof.append(nm)
ser = {l: [float(next(r[3] for r in rows if r[0] == p and r[1] == l)) for p in prof] for l in "ABC"}
short = {"clean": "clean", "loss 5%": "loss 5%", "reorder 20%": "reorder 20%", "duplicate 10%": "dup 10%", "loss 5, reorder 10, dup 5": "mixed", "harsh: loss 15, reorder 30, dup 15": "harsh", "off-path noise 10%": "noise"}
if prof: bar_chart(980, 340, [short.get(p, p) for p in prof], [ser["A"], ser["B"], ser["C"]], "Mean ticks to deliver 5,137 bytes (20 seeds) in each pairing", "ticks", colors=[C["blue"], C["green"], C["orange"]], fmt="{:.0f}", legend=["A: DUT to ref", "B: ref to DUT", "C: DUT to DUT"]).save(f"{OUT}/ch14-profiles.svg")
# 14.3 reorder sweep
A = rd("ch14_example_a_out.txt"); rs = re.findall(r"^\s+([\d.]+)% \|\s+(\d+)\s+[\d.]+\s+[\d.]+\s+\d+ \|\s+(\d+)", A, re.M)
if rs: line_chart(900, 340, [float(r[0]) for r in rs], [[float(r[1]) for r in rs], [float(r[2]) for r in rs]], "Ticks to deliver 5,137 bytes against the probability a segment is delayed (log scale)", "reordered segments (%)", "ticks", colors=[C["blue"], C["orange"]], legend=["reference receiver", "Chapter 12 receiver"], logy=True, xfmt="{:g}", yfmt="{:.0f}").save(f"{OUT}/ch14-reorder.svg")
# 14.4 window sweep
B = rd("ch14_example_b_out.txt"); ws = re.findall(r"^\s+(\d+) \|\s+\d/5\s+(\d+)\s+[\d.]+\s+[\d.]+ \|\s+\d/5\s+(\d+)", B, re.M)
import math
if ws: bar_chart(900, 320, [r[0] for r in ws], [[math.log10(float(r[1])) for r in ws], [math.log10(float(r[2])) for r in ws]], "log10 of ticks to deliver 5,137 bytes, by receive window (bytes)", "log10 ticks (5.6 = cut at 400,000)", colors=[C["green"], C["orange"]], fmt="{:.1f}", maxv=6.0, legend=["B: reference client", "C: Chapter 13 sender"]).save(f"{OUT}/ch14-window.svg")
# 14.5 mutants caught by the interop evidence alone
M = rd("ch14_mut_out.txt"); fam = re.findall(r"^\s+(model/\w+\.py|rtl/\w+\.sv)[^:]*: caught (\d+) of (\d+)", M, re.M)
if fam:
    nm = {"model/ref_stack.py": "reference", "model/tx_gold.py": "Ch13 model", "model/tcp_gold.py": "Ch12 model", "rtl/tx.sv": "Ch13 RTL", "rtl/tcp.sv": "Ch12 RTL"}
    bar_chart(900, 320, [nm.get(a, a) for a, c, n in fam], [[100.0 * int(c) / int(n) for a, c, n in fam]], "Mutants caught by the interoperability evidence alone (%)", "% caught", colors=[C["purple"]], fmt="{:.0f}", maxv=100).save(f"{OUT}/ch14-mut.svg")
print("ch14 figures written")
