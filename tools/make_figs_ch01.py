#!/usr/bin/env python3
"""Chapter 1 figures -> docs/assets/fig/ch01-*.svg (data from out/ch01_example_a.json and ch01_example_b.json)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from figs import Fig, C, bar_chart, line_chart
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "docs", "assets", "fig"); os.makedirs(OUT, exist_ok=True)
A = json.load(open(f"{ROOT}/out/ch01_example_a.json")); B = json.load(open(f"{ROOT}/out/ch01_example_b.json"))
# 1.1 fabric
f = Fig(940, 450, "The fabric"); f.text(470, 22, "An FPGA is a grid of identical tiles joined by programmable wiring", 14, bold=True)
cols = ["L", "L", "L", "B", "L", "L", "D", "L", "L", "L"]; x0, y0, cw, ch = 70, 60, 78, 40
for r in range(7):
    for c, k in enumerate(cols):
        fl, st, lab = {"L": (C["blue2"], C["blue"], "LUT+FF"), "B": (C["orange2"], C["orange"], "BRAM"), "D": (C["green2"], C["green"], "DSP")}[k]
        f.box(x0 + c * cw, y0 + r * (ch + 8), cw - 10, ch, [lab] if r % 3 == 0 or k != "L" else [], fl, st, 10.5, k != "L")
for c in range(len(cols)): f.box(x0 + c * cw, 20 + 0, cw - 10, 0.1, [], "none", "none") if False else None
f.rect(x0 - 40, y0 - 22, len(cols) * cw + 60, 7 * (ch + 8) + 32, "none", C["gray"], 2, 10, "6 4")
for i in range(12): f.box(x0 - 36, y0 + i * 26, 24, 20, [], C["gray2"], C["gray"], 9) if i < 11 else None
f.text(470, 438, "blue: logic tiles (LUTs and flip-flops, the bulk of the chip)   orange: block RAM columns   green: multiplier (DSP) columns   grey ring: I/O pads   all joined by programmable routing", 11, C["line"], italic=True); f.save(f"{OUT}/ch01-fabric.svg")
# 1.2 LUT as memory
tt = [(0x7778 >> i) & 1 for i in range(16)]; f = Fig(940, 400, "A LUT4"); f.text(470, 22, "A LUT4 is a 16-bit memory: the inputs are the address, the bitstream wrote the contents", 14, bold=True)
for i in range(16): x = 60 + (i % 8) * 70; y = 70 + (i // 8) * 80; f.box(x, y, 60, 40, [str(tt[i])], C["blue2"] if tt[i] else C["gray2"], C["blue"] if tt[i] else C["gray"], 16, True, mono=True); f.text(x + 30, y + 58, f"{i:04b}", 10.5, C["line"], mono=True)
f.text(60, 60, "address (d c b a) -> stored bit", 11.5, C["line"], anchor="start"); f.box(640, 250, 120, 50, ["LUT4"], C["orange2"], C["orange"], 15, True)
for k, nm in enumerate("abcd"): f.arrow(560, 252 + k * 14, 638, 252 + k * 14, C["ink"], 1.6, 6); f.text(550, 256 + k * 14, nm, 11, anchor="end", mono=True)
f.arrow(762, 275, 830, 275, C["ink"], 2); f.text(850, 280, "y", 14, bold=True, mono=True)
f.text(470, 370, "y = (a AND b) XOR (c OR d): the sixteen bits above, read as one number, are 0x7778. Any function of four inputs is one such table.", 12, C["line"], italic=True); f.save(f"{OUT}/ch01-lut.svg")
# 1.3 logic cell
f = Fig(940, 360, "Logic cell"); f.text(470, 22, "One logic cell: a LUT, a carry link, a flip-flop and a choice between registered and direct output", 14, bold=True)
f.box(150, 100, 190, 150, ["LUT4"], C["orange2"], C["orange"], 16, True, sub="16-bit memory"); f.box(430, 120, 120, 60, ["D flip-flop"], C["blue2"], C["blue"], 13, True); f.box(430, 200, 120, 40, ["carry logic"], C["green2"], C["green"], 12, True)
f.box(640, 130, 70, 50, ["mux"], C["gray2"], C["gray"], 12, True)
for k, nm in enumerate(("in 0", "in 1", "in 2", "in 3")): f.arrow(60, 120 + k * 32, 148, 120 + k * 32, C["ink"], 1.6, 6); f.text(52, 124 + k * 32, nm, 11, anchor="end", mono=True)
f.arrow(342, 150, 428, 150, C["ink"], 1.8); f.arrow(552, 150, 638, 150, C["ink"], 1.8); f.path("M390,150 L390,92 L610,92 L610,138 L638,138", "none", C["ink"], 1.8); f.arrow(712, 155, 800, 155, C["ink"], 2); f.text(820, 160, "out", 13, mono=True, bold=True)
f.arrow(342, 225, 428, 220, C["ink"], 1.6, 6)
f.arrow(458, 316, 458, 242, C["green"], 1.8); f.text(458, 334, "carry in (from the cell below)", 11, C["green"]); f.arrow(522, 242, 522, 316, C["green"], 1.8); f.text(560, 334, "carry out (to the cell above)", 11, C["green"], anchor="start")
f.text(675, 118, "registered or direct output", 11, C["line"], italic=True); f.save(f"{OUT}/ch01-cell.svg")
# 1.4 flow
f = Fig(940, 300, "The open flow"); f.text(470, 22, "From Verilog to a configured chip, with the open tools this book uses", 14, bold=True)
st = [("Verilog", "your design", C["gray2"], C["gray"]), ("Yosys", "synthesis: gates, then LUTs", C["blue2"], C["blue"]), ("nextpnr", "place and route, timing", C["green2"], C["green"]), ("IceStorm / Trellis", "bitstream", C["orange2"], C["orange"]), ("chip", "configured", C["gray2"], C["gray"])]
for i, (a, b, fl, s_) in enumerate(st):
    x = 20 + i * 184; f.box(x, 90, 160, 80, [a], fl, s_, 13.5, True, sub=b)
    if i < 4: f.arrow(x + 162, 130, x + 182, 130, C["ink"], 1.8, 7)
f.box(190, 210, 330, 44, ["Icarus Verilog and Verilator: simulate the Verilog (and the netlist)"], C["red2"], C["red"], 11.5); f.arrow(100, 172, 280, 208, C["red"], 1.4, 7); f.arrow(520, 210, 360, 172, C["red"], 1.4, 7)
f.text(470, 282, "This book runs everything except the last two boxes (no board): the tests stop at the netlist and the timing report", 11.5, C["line"], italic=True); f.save(f"{OUT}/ch01-flow.svg")
# 1.5 mapper bars
ch = bar_chart(900, 360, [r[0].replace(" (2 select + 4 data)", "").replace("carry out of 4-bit add", "carry out, 4-bit add") for r in A], [[r[2] for r in A], [r[3] for r in A]], "LUT4s needed: the small mapper against Yosys (iCE40)", "LUT4s", colors=[C["gray"], C["blue"]], fmt="{:.0f}", legend=["naive Shannon mapper", "Yosys synth_ice40"]); ch.save(f"{OUT}/ch01-mapper.svg")
# 1.6 Fmax vs width
ws = [8, 16, 24, 32, 48, 64]; g = lambda fam, i: [B["sweep"][f"{fam}/{w}"][i] for w in ws]
ch = line_chart(900, 380, ws, [g("ecp5", 2), g("ecp5", 4), g("ice40", 2), g("ice40", 4)], "Fmax of the registered adder against width (nextpnr, seed 1)", "adder width (bits)", "Fmax (MHz)", colors=[C["green"], C["red"], C["blue"], C["orange"]], legend=["ECP5, a + b", "ECP5, hand gates", "iCE40, a + b", "iCE40, hand gates"], xfmt="{:.0f}", yfmt="{:.0f}", logy=True); ch.save(f"{OUT}/ch01-fmax.svg")
ch = line_chart(900, 360, ws, [g("ice40", 3), g("ice40", 0)], "LUT4s used by the two iCE40 adders against width", "adder width (bits)", "LUT4s", colors=[C["orange"], C["blue"]], legend=["hand gates", "a + b (uses the carry chain)"], xfmt="{:.0f}", yfmt="{:.0f}", ymin=0); ch.save(f"{OUT}/ch01-luts.svg")
# 1.7 seeds
ks = ["ice40/radd", "ice40/radd_lut", "ecp5/radd", "ecp5/radd_lut"]; ch = bar_chart(860, 360, ["iCE40 a+b", "iCE40 gates", "ECP5 a+b", "ECP5 gates"], [[min(B["seeds"][k]) for k in ks], [sum(B["seeds"][k]) / 8 for k in ks], [max(B["seeds"][k]) for k in ks]], "Fmax over eight placement seeds (W = 32): minimum, mean and maximum", "MHz", colors=[C["red"], C["gray"], C["green"]], fmt="{:.0f}", legend=["minimum", "mean", "maximum"]); ch.save(f"{OUT}/ch01-seeds.svg")
print("ch01 figures written")
