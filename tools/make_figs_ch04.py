#!/usr/bin/env python3
"""Chapter 4 figures -> docs/assets/fig/ch04-*.svg (data from out/ch04_*_out.txt and the golden models)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
from figs import Fig, C, bar_chart, line_chart
import lat_gold as g
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "docs", "assets", "fig"); os.makedirs(OUT, exist_ok=True)
A = open(f"{ROOT}/out/ch04_example_a_out.txt").read(); B = open(f"{ROOT}/out/ch04_example_b_out.txt").read()
# 4.1 the pipeline cut into stages
f = Fig(940, 300, "Pipeline"); f.text(470, 24, "The same 12-level function with S = 1, 3 and 12 registers between the logic", 14, bold=True)
for row, s in enumerate((1, 3, 12)):
    y = 50 + row * 80; f.text(14, y + 30, f"S = {s}", 12.5, anchor="start", bold=True)
    n = s + 1; w = 780 / n
    f.box(90, y + 8, 28, 40, "reg", C["blue2"], C["blue"], 9, True)
    for k in range(s):
        x = 90 + 28 + k * ((780 - 28) / s); lw = (780 - 28) / s - 34
        f.rect(x + 4, y + 8, lw, 40, C["orange2"], C["orange"], 1.4, 4); f.text(x + 4 + lw / 2, y + 33, f"{12 // s} levels", 11) if lw > 60 else f.text(x + 4 + lw / 2, y + 33, "1", 10)
        f.box(x + 4 + lw + 2, y + 8, 28, 40, "reg", C["blue2"], C["blue"], 9, True)
f.text(470, 290, "latency = S + 1 clock cycles; the longest path between registers is 12 / S LUT levels", 12, C["line"], italic=True)
f.save(f"{OUT}/ch04-stages.svg")
# 4.2 Fmax and latency against S
rows = re.findall(r"^\s+(\d+)\s+(\d+)\s+\d+\s+\d+\s+([\d.]+) MHz\s+([\d.]+) MHz\s+(\d+)\s+([\d.]+) ns\s+([\d.]+) ns", A, re.M)
ss = [int(r[0]) for r in rows]; fm = [float(r[2]) for r in rows]; lw = [float(r[6]) for r in rows]; l1 = [float(r[5]) for r in rows]
bar_chart(900, 340, [str(s) for s in ss], [fm], "Fmax against the number of stages S (nextpnr, seed 1)", "MHz", colors=[C["teal"]], fmt="{:.0f}").save(f"{OUT}/ch04-fmax.svg")
line_chart(900, 340, ss, [l1, lw], "Latency in nanoseconds against S (cycles / Fmax)", "stages S", "latency (ns)", colors=[C["blue"], C["red"]], legend=["seed 1", "worst of 6 seeds"], xfmt="{:.0f}", yfmt="{:.0f}", ymin=0).save(f"{OUT}/ch04-latns.svg")
# 4.3 cut-through against store-and-forward timeline for one 4-beat packet
rng = g.random.Random(7); pk = [g.make_packet(rng, 4, "good")]; ins = g.schedule(pk, [0])
f = Fig(940, 340, "Timeline"); f.text(470, 24, "One good 4-beat packet through each filter (cycle numbers from the golden models)", 14, bold=True)
x0 = 180; st = 44
for row, (name, model) in enumerate((("cut-through", g.CT), ("store-and-forward", g.SF))):
    res = g.run(model, ins); y = 50 + row * 135; f.text(14, y + 4, name, 12.5, anchor="start", bold=True)
    for k in range(2, 16):
        f.text(x0 + (k - 2) * st + st / 2, y + 6, str(k), 9.5, C["line"])
    for k, (v, d, l) in enumerate(ins[2:16], 2):
        if v: f.rect(x0 + (k - 2) * st + 3, y + 14, st - 6, 22, C["blue2"], C["blue"], 1.4, 4); f.text(x0 + (k - 2) * st + st / 2, y + 30, "in", 10.5, C["blue"], bold=True)
    for k, (r, ov, od, ol, ob) in enumerate(res[2:16], 2):
        if ov: f.rect(x0 + (k - 2) * st + 3, y + 44, st - 6, 22, C["green2"], C["green"], 1.4, 4); f.text(x0 + (k - 2) * st + st / 2, y + 60, "out", 10.5, C["green"], bold=True)
    f.text(14, y + 58, "output", 11, anchor="start", italic=True); f.text(14, y + 32, "input", 11, anchor="start", italic=True)
f.text(470, 318, "cut-through starts the output one cycle after the first beat; store-and-forward waits for the last beat, so the wait grows with the packet", 12, C["line"], italic=True)
f.save(f"{OUT}/ch04-timeline.svg")
# 4.4 first-beat latency against packet length
ns_ = [2, 3, 4, 8, 16, 32]; r = re.findall(r"^\s+(\d+) \|\s+(\d+)\s+(\d+) \|\s+(\d+)\s+(\d+)", B, re.M)
line_chart(900, 340, [int(x[0]) for x in r], [[int(x[1]) for x in r], [int(x[3]) for x in r]], "First-beat latency against packet length (cycles)", "packet length (beats)", "cycles", colors=[C["green"], C["red"]], legend=["cut-through", "store-and-forward"], xfmt="{:.0f}", yfmt="{:.0f}", ymin=0).save(f"{OUT}/ch04-lenlat.svg")
# 4.5 histogram of first-beat latency
hs = {}
for name in ("cut-through", "store-and-forward"):
    m = re.search(name + r"\s+packets with output.*?histogram (\{.*\})", B); hs[name] = eval(m.group(1))
keys = list(range(1, 14)); bar_chart(900, 340, [str(k) for k in keys], [[hs["cut-through"].get(k, 0) for k in keys], [hs["store-and-forward"].get(k, 0) for k in keys]], "How many packets had each first-beat latency (cycles), random traffic", "packets", colors=[C["green"], C["red"]], fmt="{:.0f}", legend=["cut-through", "store-and-forward"]).save(f"{OUT}/ch04-hist.svg")
print("ch04 figures written")
