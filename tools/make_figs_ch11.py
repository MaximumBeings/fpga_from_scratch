#!/usr/bin/env python3
"""Chapter 11 figures -> docs/assets/fig/ch11-*.svg (data from out/ch11_*_out.txt)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figs import Fig, C, bar_chart, line_chart
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "docs", "assets", "fig"); os.makedirs(OUT, exist_ok=True)
rd = lambda n: open(f"{ROOT}/out/{n}").read()
# 11.1 the two builders in time
f = Fig(960, 400, "Builders"); f.text(480, 24, "Store-and-forward against cut-through: when the first byte can leave", 14, bold=True)
f.text(20, 62, "store-and-forward", 13, C["blue"], "start", True)
f.box(160, 46, 330, 34, "payload in: memory + length + checksum sum", C["blue2"], C["blue"], 11); f.box(494, 46, 60, 34, "calc", C["orange2"], C["orange"], 11); f.box(558, 46, 40, 34, "req", C["gray2"], C["gray"], 10)
f.box(602, 46, 150, 34, "headers (42 B)", C["green2"], C["green"], 11); f.box(756, 46, 190, 34, "payload from memory", C["teal2"], C["teal"], 11)
f.text(20, 142, "cut-through", 13, C["green"], "start", True)
f.box(160, 126, 60, 34, "calc", C["orange2"], C["orange"], 11); f.box(224, 126, 40, 34, "req", C["gray2"], C["gray"], 10); f.box(268, 126, 150, 34, "headers (42 B)", C["green2"], C["green"], 11); f.box(422, 126, 330, 34, "payload passes through (one byte per clock)", C["teal2"], C["teal"], 11)
f.arrow(160, 190, 160, 100, C["red"], 1.4, 7, "4 3"); f.text(160, 210, "descriptor accepted", 11, C["red"])
f.arrow(602, 250, 602, 88, C["gray"], 1.3, 7, "4 3"); f.text(602, 266, "first byte on the wire (store-and-forward)", 11, C["line"]); f.arrow(268, 250, 268, 168, C["gray"], 1.3, 7, "4 3"); f.text(268, 266, "first byte on the wire (cut-through)", 11, C["line"])
f.text(480, 306, "store-and-forward waits for the whole payload (L cycles) and 12 cycles of arithmetic; cut-through waits only for the arithmetic on the length", 12, C["ink"])
f.text(480, 330, "but a cut-through frame cannot pause: once the preamble is out the payload must arrive every cycle, or the MAC underruns", 12, C["red"], bold=True)
f.text(480, 368, "and store-and-forward holds one frame at a time: while it sends, it cannot receive (utilisation about 51% at 1,000 bytes)", 12, C["line"], italic=True)
f.save(f"{OUT}/ch11-builders.svg")
# 11.2 token bucket
f = Fig(960, 330, "Bucket"); f.text(480, 24, "The token bucket: credit rises by the rate every cycle, a frame needs its whole wire cost", 14, bold=True)
f.rect(60, 60, 260, 200, "none", C["ink"], 2.2, 6); f.rect(62, 160, 256, 98, C["blue2"], None, 0, 2)
f.text(190, 86, "bucket: 2^BL bytes", 12, bold=True); f.text(190, 215, "credit", 13, C["blue"], bold=True); f.line(60, 100, 320, 100, C["red"], 1.5, "5 4"); f.text(326, 104, "full: more is lost", 10.5, C["red"], "start")
f.arrow(100, 40, 100, 96, C["green"], 2); f.text(112, 52, "+ rate every cycle (1/256 byte units)", 11, C["green"], "start"); f.arrow(190, 262, 190, 300, C["orange"], 2); f.text(200, 296, "- cost when a frame is granted", 11, C["orange"], "start")
f.box(520, 70, 260, 56, ["request: length L", "cost = (L + 24) bytes"], C["gray2"], C["gray"], 11); f.box(520, 170, 260, 56, ["grant when credit >= cost", "(registered comparison)"], C["green2"], C["green"], 11, True); f.arrow(560, 128, 560, 168, C["ink"], 1.6)
f.text(664, 148, "wire cost: preamble 8 + frame", 10.5, anchor="start"); f.text(664, 164, "(padded to 60) + FCS 4 + gap 12", 10.5, anchor="start")
f.text(520, 240, "long run: spacing = cost x 256 / rate cycles", 11.5, C["blue"], "start", True); f.text(520, 262, "burst: 1 + floor((bucket - cost) / (cost x (1 - rate/256)))", 11.5, C["blue"], "start", True)
f.text(480, 310, "in any interval the grants add up to at most: bucket + rate x length of the interval", 12, C["ink"], italic=True)
f.save(f"{OUT}/ch11-bucket.svg")
# 11.3 util + fmax + spacing + latency
A = rd("ch11_example_a_out.txt")
rows = re.findall(r"^\s+(\d+)\s+(\d+) \|\s+([\d.]+) cyc\s+([\d.]+)% \|\s+([\d.]+) cyc\s+([\d.]+)%", A, re.M)
if rows: bar_chart(900, 320, [r[0] for r in rows], [[float(r[3]) for r in rows], [float(r[5]) for r in rows]], "Link utilisation against payload length (bytes): packets back to back", "% of the wire", colors=[C["orange"], C["teal"]], fmt="{:.0f}", legend=["store-and-forward", "cut-through"], maxv=115).save(f"{OUT}/ch11-util.svg")
rs = re.findall(r"^\s+([a-z\- +]+?)\s+\|\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+) \|\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)", A, re.M)
if rs:
    ch = bar_chart(900, 340, [r[0].replace("store-and-forward", "S&F").replace("cut-through", "CT") for r in rs], [[float(r[4]) for r in rs], [float(r[9]) for r in rs]], "Fmax of the whole path (MHz); a byte per clock at 1 Gbit/s needs 125", "MHz", colors=[C["orange"], C["teal"]], fmt="{:.0f}", legend=["iCE40", "ECP5"])
    mv = max([float(r[4]) for r in rs] + [float(r[9]) for r in rs]) * 1.12; yy = 40 + (340 - 100) * (1 - 125 / mv); ch.line(70, yy, 880, yy, C["red"], 1.8, "6 4"); ch.text(876, yy - 6, "125 MHz", 11, C["red"], "end", True); ch.save(f"{OUT}/ch11-fmax.svg")
B = rd("ch11_example_b_out.txt"); sp = re.findall(r"^\s+(\d+)\s+[\d.]+ \|\s+([\d.]+)\s+(\d+)\s+\d+\s+\d+ \|", B, re.M)
if sp: bar_chart(900, 320, [r[0] for r in sp], [[float(r[1]) for r in sp], [float(r[2]) for r in sp]], "Cycles between frame starts against the rate (1/256 byte per cycle): derived and measured", "cycles", colors=[C["gray"], C["teal"]], fmt="{:.0f}", legend=["derived", "measured"]).save(f"{OUT}/ch11-spacing.svg")
print("ch11 figures written")
