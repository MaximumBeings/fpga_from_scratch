#!/usr/bin/env python3
"""Chapter 15 figures -> docs/assets/fig/ch15-*.svg (data from out/ch15_*_out.txt)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figs import Fig, C, bar_chart, line_chart
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "docs", "assets", "fig"); os.makedirs(OUT, exist_ok=True)
rd = lambda n: open(f"{ROOT}/out/{n}").read()
f = Fig(980, 400, "Split"); f.text(490, 24, "tcp_split: one event per cycle, a hot path in hardware, a cold path in software, and a count that keeps the order", 14, bold=True)
f.box(30, 150, 130, 90, ["event", "(segment or", "command)"], C["gray2"], C["gray"], 11.5, True)
f.box(220, 120, 250, 150, ["table of connections", "state, SND.UNA, SND.NXT,", "RCV.NXT, count pending", "", "tcp_fast: ESTABLISHED, ACK,", "seq = RCV.NXT, in window,", "nothing pending?"], C["blue2"], C["blue"], 11.5, True)
f.box(560, 60, 190, 80, ["HOT: update RCV.NXT,", "ACK out, bytes delivered", "(this cycle)"], C["green2"], C["green"], 11.5, True)
f.box(560, 190, 190, 80, ["punt FIFO", "entry + state snapshot", "+ first flag"], C["orange2"], C["orange"], 11.5, True)
f.box(790, 190, 160, 80, ["SOFTWARE", "full state machine", "L cycles per entry"], C["purple2"], C["purple"], 11.5, True)
f.arrow(162, 195, 218, 195, C["ink"], 1.8); f.arrow(472, 160, 558, 110, C["ink"], 1.8); f.arrow(472, 230, 558, 230, C["ink"], 1.8); f.arrow(752, 230, 788, 230, C["ink"], 1.8)
f.path("M870,272 C870,340 345,340 345,272", "none", C["red"], 1.8); f.text(600, 334, "write-back: state, count - 1 (the count is what keeps the order of events per connection)", 11.5, C["red"])
f.text(490, 372, "FIFO full: POLICY 0 holds the event (the ones behind it wait), POLICY 1 drops it (TCP retransmits)", 12, C["ink"], italic=True)
f.save(f"{OUT}/ch15-split.svg")
B = rd("ch15_example_b_out.txt"); sec1 = B.split("== 2.")[0]
rs = re.findall(r"^\s+([\d.]+) \|\s+[\d.]+%\s+\d+\s+([\d.]+)\s+([\d.]+) \|", sec1, re.M)
if rs: line_chart(900, 330, [float(r[0]) for r in rs], [[float(r[1]) for r in rs], [float(r[2]) for r in rs]], "Events dragged into software per exception, against phi (the connection's event rate x L)", "phi", "events per exception", colors=[C["orange"], C["blue"]], legend=["measured", "derived phi / (1 - phi)"], logy=True, xfmt="{:g}", yfmt="{:.2f}").save(f"{OUT}/ch15-collateral.svg")
sec2 = B.split("== 2.")[1].split("== 3.")[0]
hs = re.findall(r"^\s+0\s+(\d+)\s+(\d+) \|\s+\d+\s+[\d.]+\s+(\d+)\s+(\d+)", sec2, re.M)
if hs: bar_chart(900, 330, [f"D={r[0]}, B={r[1]}" for r in hs], [[float(r[2]) for r in hs], [float(r[3]) for r in hs]], "POLICY 0: the longest wait of any other event during a burst (cycles), measured and derived (B - D) x L", "cycles", colors=[C["orange"], C["blue"]], legend=["measured", "derived"]).save(f"{OUT}/ch15-hol.svg")
A = rd("ch15_example_a_out.txt"); ar = re.findall(r"^\s+(tcp_\w+[^|]*?)\s+\|\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+) \|", A, re.M)
if ar: bar_chart(900, 330, [r[0].replace("tcp_split, ", "").replace(" connections", " conn").replace("tcp_fast alone (Chapter 12)", "hot path alone").replace(", FIFO ", ", F") for r in ar], [[float(r[4]) for r in ar]], "Fmax on iCE40 (MHz) behind the pin wrapper", "MHz", colors=[C["blue"]], fmt="{:.0f}").save(f"{OUT}/ch15-fmax.svg")
print("ch15 figures written")
