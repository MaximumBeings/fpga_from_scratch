#!/usr/bin/env python3
"""Chapter 26 figures -> docs/assets/fig/ch26-*.svg (data from out/ch26_*_out.txt)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figs import Fig, C, bar_chart, line_chart
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "docs", "assets", "fig"); os.makedirs(OUT, exist_ok=True)
rd = lambda n: open(f"{ROOT}/out/{n}").read()
f = Fig(1000, 380, "Pipeline"); f.text(500, 24, "Wire to wire: bytes of a market data feed in, bytes of an order out", 14, bold=True)
xs = [20, 150, 280, 420, 560, 700, 840]
def blk(i, y, w, lines, col): f.box(xs[i], y, w, 90, lines, C[col + "2"], C[col], 11, True)
blk(0, 100, 110, ["parser", "Ch 16", "1 byte/cycle"], "blue"); blk(1, 100, 110, ["adapter + FIFO", "QD entries", "drops if full"], "gray")
blk(2, 100, 120, ["order book", "Ch 20", "n cycles"], "green"); blk(3, 40, 120, ["signal", "Ch 22", "F + 4 cycles"], "purple"); blk(3, 170, 120, ["trigger", "Ch 21", "4 + PIPE cycles"], "purple")
blk(4, 100, 120, ["strategy", "one message in", "the slot"], "orange"); blk(5, 100, 120, ["lifecycle", "Ch 25: gate +", "tracker, 5 cycles"], "blue"); blk(6, 100, 130, ["transmitter", "Ch 24", "first byte +1"], "green")
for a, b in ((130, 150), (260, 280), (400, 420), (540, 560), (680, 700), (820, 840)): f.arrow(a, 145, b, 145, C["ink"], 1.6)
f.arrow(400, 130, 418, 85, C["ink"], 1.2); f.arrow(400, 160, 418, 210, C["ink"], 1.2); f.arrow(540, 85, 558, 130, C["ink"], 1.2); f.arrow(540, 210, 558, 160, C["ink"], 1.2)
f.arrow(900, 192, 900, 300, C["red"], 1.4, dash="4 3"); f.text(700, 318, "a refusal by the transmitter comes back as a REJECT to the tracker, which gives the gate's charge back", 11, C["red"], italic=True)
f.text(500, 360, "total = wait + n + F + 11 + x: 35 cycles at best (n = 11, F = 12, x = 1)", 12, italic=True)
f.save(f"{OUT}/ch26-pipeline.svg")
R = rd("ch26_run_out.txt"); s4 = R.split("== 4.")[1]
st = {}
for k, name in (("wait", "queue wait"), ("book", "order book"), ("sigtrig", "signal + trigger"), ("life", "gate + tracker"), ("xmit", "transmitter")):
    m = re.search(rf"^\s+{re.escape(name)}.*?\s+(\d+)\s+([\d.]+)\s+(\d+)\s*$", s4, re.M)
    if m: st[name] = (int(m.group(1)), float(m.group(2)), int(m.group(3)))
if st: bar_chart(900, 330, list(st), [[v[0] for v in st.values()], [v[1] for v in st.values()], [v[2] for v in st.values()]], "Cycles in each stage, per order (min, mean, max)", "cycles", colors=[C["green"], C["blue"], C["orange"]], legend=["min", "mean", "max"], fmt="{:.1f}").save(f"{OUT}/ch26-budget.svg")
B = rd("ch26_example_b_out.txt"); s3 = B.split("== 3.")[1]
rows = re.findall(r"^\s+(\d+) \|\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+) \|", s3, re.M)
if rows: line_chart(900, 330, [2, 4, 8, 16, 32], [[float(r[1 + k]) for k in range(5)] for r in rows], "Messages dropped of 99 against the queue size, by how much faster the feed is", "QD (queue entries)", "dropped", colors=[C["blue"], C["green"], C["orange"], C["red"]], legend=[f"feed {r[0]}x" for r in rows], logx=True, xfmt="{:g}", yfmt="{:.0f}", ymin=0).save(f"{OUT}/ch26-drops.svg")
print("ch26 figures written")
