#!/usr/bin/env python3
"""Chapter 2 figures -> docs/assets/fig/ch02-*.svg (data from out/ch02_example_a_out.txt, ch02_example_b.json and the golden model)."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
from figs import Fig, C, bar_chart, line_chart
import vr_gold
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "docs", "assets", "fig"); os.makedirs(OUT, exist_ok=True)
B = json.load(open(f"{ROOT}/out/ch02_example_b.json")); A = open(f"{ROOT}/out/ch02_example_a_out.txt").read()
# 2.1 feature matrix
rows = re.findall(r"^  (\S.{35}?) +(ok|FAILS) +(ok|FAILS) +(ok|FAILS)\s*$", A.split("== 2.")[0], re.M)
f = Fig(820, 70 + 26 * len(rows), "Feature matrix"); f.text(410, 24, "Which SystemVerilog constructs do the three tools accept?", 14, bold=True)
for j, t in enumerate(("Icarus 12", "Verilator 5.020", "Yosys 0.33")): f.text(470 + j * 112, 52, t, 11.5, bold=True)
for i, r in enumerate(rows):
    y = 62 + i * 26; f.text(20, y + 17, r[0].strip(), 12, anchor="start", mono=True)
    for j in range(3): ok = r[1 + j] == "ok"; f.rect(420 + j * 112, y, 100, 22, C["green2"] if ok else C["red2"], C["green"] if ok else C["red"], 1.2, 4); f.text(470 + j * 112, y + 16, "ok" if ok else "fails", 11.5, C["green"] if ok else C["red"], bold=True)
f.save(f"{OUT}/ch02-features.svg")
# 2.2 waveform: comb against skid with the same stimulus
ins = [(1, k + 1, r) for k, r in enumerate([1, 1, 0, 0, 0, 1, 1, 1, 0, 1, 1, 1])]
f = Fig(940, 470, "Ready timing"); f.text(470, 22, "The same stimulus into a comb stage and a skid stage (valid = 1 throughout, one stage)", 14, bold=True)
st = 38; x0 = 190
for pi, (name, style) in enumerate((("comb stage", 1), ("skid stage", 2))):
    out = vr_gold.run_chain(style, 1, ins); y0 = 50 + pi * 205
    f.text(20, y0 + 14, name, 13, anchor="start", bold=True)
    f.wave(x0, y0 + 30, "".join(str(r) for _, _, r in ins), st, 16, C["gray"], "out_ready"); f.wave(x0, y0 + 76, "".join(str(o[0]) for o in out), st, 16, C["blue"], "in_ready"); f.wave(x0, y0 + 122, "".join(str(o[1]) for o in out), st, 16, C["green"], "out_valid")
    for k, ((vi, di, ro), (ri, ov, od)) in enumerate(zip(ins, out)):
        if vi and ri: f.rect(x0 + k * st + 3, y0 + 148, st - 6, 14, C["orange2"], C["orange"], 1, 3); f.text(x0 + k * st + st / 2, y0 + 159, str(di), 9.5, C["orange"], bold=True)
    f.text(20, y0 + 160, "accepted items (valid and ready)", 10.5, C["line"], anchor="start", italic=True)
f.text(470, 440, "comb: in_ready falls in the same cycle as out_ready (a combinational path).", 11.5, C["line"], italic=True); f.text(470, 458, "skid: in_ready falls one cycle later (it comes from a register); the skid register catches the item that arrives in that cycle.", 11.5, C["line"], italic=True); f.save(f"{OUT}/ch02-ready.svg")
# 2.3 skid block diagram
f = Fig(940, 330, "Skid buffer"); f.text(470, 22, "The skid stage: an output register, a skid register, and a ready signal that comes from a register", 14, bold=True)
f.box(60, 130, 120, 60, ["in_data", "in_valid"], C["gray2"], C["gray"], 12, True); f.box(300, 70, 150, 50, ["skid register"], C["orange2"], C["orange"], 13, True); f.box(300, 190, 150, 70, ["mux: skid or input"], C["blue2"], C["blue"], 12, True)
f.box(560, 130, 150, 60, ["output register"], C["green2"], C["green"], 13, True); f.box(790, 130, 120, 60, ["out_data", "out_valid"], C["gray2"], C["gray"], 12, True)
f.arrow(182, 160, 298, 100, C["ink"], 1.8); f.arrow(182, 165, 298, 215, C["ink"], 1.8); f.arrow(452, 95, 452, 150, C["ink"], 1.6); f.arrow(452, 225, 558, 175, C["ink"], 1.8); f.arrow(712, 160, 788, 160, C["ink"], 2)
f.arrow(790, 290, 182, 290, C["red"], 1.8); f.text(480, 282, "out_ready (from the sink)", 11.5, C["red"]); f.arrow(375, 68, 375, 40, C["blue"], 1.6) if False else None
f.text(240, 56, "in_ready = !skid_valid (a register)", 11.5, C["blue"], anchor="middle"); f.text(470, 310, "In a stall the arriving item goes to the skid register; in_ready then falls in the NEXT cycle.", 11.5, C["line"], italic=True); f.text(470, 328, "When the output frees, the skid item moves first.", 11.5, C["line"], italic=True); f.save(f"{OUT}/ch02-skid.svg")
# 2.4 chain Fmax and LUTs
ns = [1, 2, 4, 8, 16, 32]; g = lambda fam, st, i: [B["chain"][f"{fam}/{n}/{st}"][i] for n in ns]
for fam, nm in (("ice40", "iCE40"), ("ecp5", "ECP5")):
    ch = line_chart(900, 360, ns, [g(fam, 0, 2), g(fam, 1, 2), g(fam, 2, 2)], f"Fmax of a chain of N stages, 32-bit data, {nm} (nextpnr, seed 1)", "stages in the chain", "Fmax (MHz)", colors=[C["gray"], C["red"], C["green"]], legend=["slow", "comb", "skid"], xfmt="{:.0f}", yfmt="{:.0f}", ymin=0); ch.save(f"{OUT}/ch02-fmax-{fam}.svg")
ch = line_chart(900, 360, ns, [g("ice40", 0, 0), g("ice40", 1, 0), g("ice40", 2, 0)], "LUT4s used by a chain of N stages, iCE40", "stages in the chain", "LUT4s (log scale)", colors=[C["gray"], C["red"], C["green"]], legend=["slow", "comb", "skid"], xfmt="{:.0f}", yfmt="{:.0f}", logy=True); ch.save(f"{OUT}/ch02-luts.svg")
# 2.5 FSM diagram
f = Fig(940, 340, "Frame FSM"); f.text(470, 22, "The frame recognizer (a byte is consumed only when in_valid = 1)", 14, bold=True)
pos = {"IDLE": (120, 160), "LEN": (350, 160), "DATA": (580, 160), "FIN": (810, 160)}
for s_, (x, y) in pos.items(): f.circ(x, y, 46, C["blue2"], C["blue"], 2.4); f.text(x, y + 5, s_, 15, bold=True)
for a, b, lab in (("IDLE", "LEN", "0xA5"), ("LEN", "DATA", "1..16: load"), ("DATA", "FIN", "count = 1")): xa, xb = pos[a][0] + 48, pos[b][0] - 48; f.arrow(xa, 150, xb, 150, C["ink"], 1.8); f.text((xa + xb) / 2, 138, lab, 10.5, anchor="middle")
f.path("M595,208 C590,260 570,262 565,210", "none", C["gray"], 1.6); f.text(580, 276, "payload: count - 1", 10.5, C["line"], italic=True)
f.path("M800,114 C700,40 200,40 130,114", "none", C["green"], 1.8); f.text(470, 56, "byte = 0x5A: done pulse, back to IDLE", 11, C["green"])
f.path("M350,206 C350,300 160,300 130,206", "none", C["red"], 1.8); f.text(250, 318, "bad length: err pulse, abort", 11, C["red"])
f.path("M810,206 C810,320 180,322 140,204", "none", C["red"], 1.4, "5 4"); f.text(650, 330, "other end byte: err pulse, abort", 11, C["red"])
f.save(f"{OUT}/ch02-fsm.svg")
print("ch02 figures written", len(rows))
