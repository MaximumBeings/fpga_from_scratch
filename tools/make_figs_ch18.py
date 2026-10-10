#!/usr/bin/env python3
"""Chapter 18 figures -> docs/assets/fig/ch18-*.svg (data from out/ch18_*_out.txt)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figs import Fig, C, bar_chart, line_chart
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "docs", "assets", "fig"); os.makedirs(OUT, exist_ok=True)
rd = lambda n: open(f"{ROOT}/out/{n}").read()
f = Fig(980, 400, "Arbiter"); f.text(490, 24, "seq_arb: two feeds and a retransmission server into one in-order stream, with a window of pending packets and a gap timer", 14, bold=True)
f.box(30, 70, 140, 60, ["feed A"], C["blue2"], C["blue"], 12, True); f.box(30, 160, 140, 60, ["feed B"], C["blue2"], C["blue"], 12, True); f.box(30, 250, 140, 60, ["retransmission", "server"], C["orange2"], C["orange"], 11.5, True)
f.box(260, 110, 230, 170, ["classify by d = seq - next", "d = 0: forward", "behind: duplicate (or overlap: error)", "ahead: store in a slot,", "or drop if all slots are full", "stored packet in order: release"], C["gray2"], C["gray"], 11, True)
f.box(570, 70, 170, 90, ["window: PEND slots", "(distance from next,", "count, feed)"], C["purple2"], C["purple"], 11.5, True); f.box(570, 200, 170, 80, ["gap timer", "TO: request", "TO2: give up (skip)"], C["red2"] if "red2" in C else C["orange2"], C["red"], 11.5, True)
f.box(800, 110, 150, 70, ["in-order stream", "(one packet per", "cycle at most)"], C["green2"], C["green"], 11.5, True); f.box(800, 220, 150, 60, ["request / skip", "events"], C["orange2"], C["orange"], 11.5, True)
for y in (100, 190, 280): f.arrow(172, y, 258, 190 if y != 280 else 220, C["ink"], 1.6)
f.arrow(492, 160, 568, 120, C["ink"], 1.6); f.arrow(568, 130, 494, 175, C["ink"], 1.4, dash="5 4"); f.arrow(742, 120, 798, 140, C["ink"], 1.6); f.arrow(742, 240, 798, 250, C["ink"], 1.6); f.arrow(494, 230, 568, 240, C["ink"], 1.4, dash="5 4")
f.arrow(868, 282, 868, 330, C["ink"], 1.4, dash="5 4"); f.text(660, 345, "a request goes to the server; its answer comes back as feed 2", 11.5, C["line"], italic=True)
f.text(490, 385, "all decisions are taken from the state at the start of the cycle; a release or a skip stops the input for that cycle", 12, C["ink"], italic=True)
f.save(f"{OUT}/ch18-arbiter.svg")
A = rd("ch18_example_a_out.txt"); rows = re.findall(r"^\s+(\d)\s+(\d+) \|\s+\d+\s+\d+\s+([\d.]+) \|\s+\d+\s+\d+\s+\d+\s+([\d.]+)", A, re.M)
if rows:
    ns = sorted({int(r[1]) for r in rows}); ser = [[float(next(r[2] for r in rows if int(r[0]) == v and int(r[1]) == n)) for n in ns] for v in (1, 2, 3)]
    bar_chart(900, 330, [f"PEND {n}" for n in ns], ser, "Fmax of seq_arb on iCE40 (MHz) against the window, three versions", "MHz", colors=[C["gray"], C["orange"], C["green"]], fmt="{:.0f}", legend=["v1 recomputed", "v2 stored", "v3 tree min"]).save(f"{OUT}/ch18-fmax.svg")
B = rd("ch18_example_b_out.txt"); sec = B.split("== 1b.")[1].split("== 2.")[0]; rs = re.findall(r"^\s+(\d+) \|\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", sec, re.M)
if rs: bar_chart(900, 320, [f"PEND {r[0]}" for r in rs], [[float(r[2]) for r in rs]], "Messages fetched by retransmission at 5% loss per feed (400 packets' worth needed: 75 at PEND 16)", "messages", colors=[C["orange"]], fmt="{:.0f}").save(f"{OUT}/ch18-window.svg")
sec2 = B.split("== 2.")[1]; ts = re.findall(r"^\s+(\d+) \|\s+(\d+)\s+\d+", sec2, re.M)
if ts: bar_chart(900, 320, [f"TO {r[0]}" for r in ts], [[float(r[1]) for r in ts]], "Spurious retransmission requests against the gap timer (A loses 30%, B is 10 cycles late)", "requests", colors=[C["blue"]], fmt="{:.0f}").save(f"{OUT}/ch18-timer.svg")
print("ch18 figures written")
