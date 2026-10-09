#!/usr/bin/env python3
"""Chapter 3 figures -> docs/assets/fig/ch03-*.svg (data from out/ch03_*_out.txt)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
from figs import Fig, C, bar_chart, line_chart
import cdc_model
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "docs", "assets", "fig"); os.makedirs(OUT, exist_ok=True)
A = open(f"{ROOT}/out/ch03_example_a_out.txt").read(); Rn = open(f"{ROOT}/out/ch03_run_out.txt").read()
# 3.1 the period equation
f = Fig(940, 300, "Period equation"); f.text(470, 24, "One clock period must cover everything between two flip-flops", 14, bold=True)
x0 = 60; seg = [("clock-to-q", 90, C["blue2"], C["blue"]), ("LUT", 90, C["orange2"], C["orange"]), ("route", 130, C["gray2"], C["gray"]), ("LUT", 90, C["orange2"], C["orange"]), ("route", 110, C["gray2"], C["gray"]), ("setup", 70, C["green2"], C["green"]), ("slack", 150, C["yellow2"], C["line"])]
x = x0
for name, w, fill, st in seg: f.rect(x, 90, w, 50, fill, st, 1.8, 4); f.text(x + w / 2, 120, name, 12.5, bold=True); x += w
f.line(x0, 160, x, 160, C["ink"], 2); f.text((x0 + x) / 2, 182, "clock period T", 13, bold=True)
f.arrow(x0, 60, x0, 88, C["ink"], 1.8); f.text(x0, 54, "launch edge (flip-flop 1)", 11.5, C["ink"], anchor="start"); f.arrow(x, 60, x, 88, C["ink"], 1.8); f.text(x, 54, "capture edge (flip-flop 2)", 11.5, C["ink"], anchor="end")
f.text(470, 218, "T  >=  t_clk-to-q  +  (LUT + route) x levels  +  t_setup        slack = T - (that sum); negative slack = the circuit fails at this clock", 12, C["line"])
f.text(470, 244, "hold is the other check: the data must not change too soon AFTER the capturing edge (it concerns the SAME edge, so no clock period fixes it)", 12, C["line"], italic=True)
f.text(470, 270, "the router fixes hold by adding delay; the designer fixes setup by shortening the path or slowing the clock", 12, C["line"], italic=True)
f.save(f"{OUT}/ch03-period.svg")
# 3.2 depth against period and Fmax
rows = re.findall(r"^\s+(\d+)\s+\d+\s+\d+\s+\d+\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+\d+%", A, re.M)
ds = [int(r[0]) for r in rows]; fm = [float(r[1]) for r in rows]; per = [float(r[2]) for r in rows]; lg = [float(r[3]) for r in rows]; rt = [float(r[4]) for r in rows]
fit = re.search(r"period = ([\d.]+) ns \+ ([\d.]+) ns per LUT level", A); a, b = float(fit.group(1)), float(fit.group(2))
ch = line_chart(900, 360, ds, [per, [a + b * d for d in ds]], "Clock period against logic depth (iCE40, nextpnr seed 1)", "LUT levels between the registers", "period (ns)", colors=[C["blue"], C["orange"]], legend=["measured", f"fit: {a:.2f} + {b:.2f} x levels"], xfmt="{:.0f}", yfmt="{:.0f}"); ch.save(f"{OUT}/ch03-depth.svg")
ch = bar_chart(900, 360, [str(d) for d in ds], [lg, rt], "Where the time goes on the critical path (ns)", "ns", colors=[C["orange"], C["gray"]], fmt="{:.0f}", legend=["logic", "routing"]); ch.save(f"{OUT}/ch03-split.svg")
# 3.3 seeds
sd = [float(v) for v in re.search(r"Fmax:\s+(.*)", A.split("== 2.")[1]).group(1).split()]
ch = bar_chart(900, 340, [str(i + 1) for i in range(len(sd))], [sd], "Fmax of the same design for 12 placer seeds (MHz)", "MHz", colors=[C["teal"]], fmt="{:.0f}", maxv=140); ch.save(f"{OUT}/ch03-seeds.svg")
# 3.4 synchronizer diagram
f = Fig(940, 330, "Synchronizer"); f.text(470, 22, "The two-flip-flop synchronizer", 14, bold=True)
f.box(40, 100, 120, 60, ["source flip-flop", "(clock a)"], C["blue2"], C["blue"], 12, True); f.box(300, 100, 100, 60, ["FF 1", "may go", "metastable"], C["red2"], C["red"], 11.5, True); f.box(470, 100, 100, 60, ["FF 2", "settled"], C["green2"], C["green"], 12, True); f.box(660, 100, 150, 60, ["logic in clock b"], C["gray2"], C["gray"], 12, True)
f.arrow(162, 130, 298, 130, C["ink"], 2); f.arrow(402, 130, 468, 130, C["ink"], 2); f.arrow(572, 130, 658, 130, C["ink"], 2)
f.line(350, 240, 350, 162, C["purple"], 1.8); f.line(520, 240, 520, 162, C["purple"], 1.8); f.line(350, 240, 520, 240, C["purple"], 1.8); f.text(435, 262, "clock b", 12, C["purple"], bold=True)
f.rect(262, 70, 188, 20, C["yellow2"], C["line"], 1, 4, "4 3"); f.text(356, 85, "a whole clock period to settle", 10.5, C["line"])
f.text(470, 300, "rules: the source is a flip-flop output; nothing but FF 2 reads FF 1; one bit (or a code that changes one bit per step)", 12, C["line"], italic=True)
f.save(f"{OUT}/ch03-sync.svg")
# 3.5 binary against Gray, 4-bit pointer
def cap(b, gray):
    enc = (lambda v: v ^ (v >> 1)) if gray else (lambda v: v); o, n = enc(b), enc((b + 1) % 16); return o, n, sorted(cdc_model._outcomes(o, n, 4))
f = Fig(940, 330, "Binary against Gray"); f.text(470, 22, "What a capture in the middle of a step can return: the step 3 -> 4 of a 4-bit pointer", 14, bold=True)
for i, (name, gray, col) in enumerate((("binary", False, C["red"]), ("Gray code", True, C["green"]))):
    o, n, got = cap(3, gray); x = 40 + i * 450; f.text(x + 190, 62, name, 14, col, bold=True); f.text(x + 190, 84, f"old {o:04b}  ->  new {n:04b}   ({bin(o ^ n).count('1')} bit{'s' if bin(o ^ n).count('1') > 1 else ''} change)", 12, C["line"])
    for k, v in enumerate(got):
        ok = v in (o, n); xx = x + (k % 4) * 92; yy = 108 + (k // 4) * 52; f.rect(xx, yy, 84, 40, C["green2"] if ok else C["red2"], C["green"] if ok else C["red"], 1.6, 6); f.text(xx + 42, yy + 18, f"{v:04b}", 14, bold=True, mono=True); f.text(xx + 42, yy + 33, ("old" if v == o else "new" if v == n else "WRONG"), 10.5, C["green"] if ok else C["red"])
f.text(470, 312, "a wrong value is a pointer that never existed: a FIFO using it reads a word that was never written, or overwrites one not yet read", 12, C["line"], italic=True)
f.save(f"{OUT}/ch03-gray.svg")
# 3.6 pulses delivered against the b clock period
m = re.findall(r"^\s+(\d+)\s+(\d+) \|\s+(\d+)\s+(\d+) \|\s+(\d+)\s+(\d+)", Rn.split("== 3.")[1], re.M); sel = [r for r in m if r[1] == "6"]
ch = line_chart(900, 340, [int(r[0]) for r in sel], [[int(r[2]) for r in sel], [int(r[4]) for r in sel]], "Pulses delivered out of 200 (a pulse is one 10 ns cycle; 6 cycles apart)", "period of the receiving clock (ps)", "pulses delivered", colors=[C["red"], C["green"]], legend=["naive", "toggle"], xfmt="{:.0f}", yfmt="{:.0f}", ymin=0, ymax=220); ch.save(f"{OUT}/ch03-pulses.svg")
# 3.7 asynchronous FIFO block diagram
f = Fig(940, 400, "Asynchronous FIFO"); f.text(470, 22, "The asynchronous FIFO: data stays put in the memory; only Gray-coded pointers cross", 14, bold=True)
f.rect(20, 44, 440, 312, C["blue2"], C["blue"], 1.6, 10, "6 4", 0.5); f.text(240, 66, "write clock domain", 12.5, C["blue"], bold=True); f.rect(480, 44, 440, 312, C["orange2"], C["orange"], 1.6, 10, "6 4", 0.5); f.text(700, 66, "read clock domain", 12.5, C["orange"], bold=True)
f.box(40, 90, 150, 56, ["write pointer", "binary + Gray register"], C["gray2"], C["gray"], 11.5, True); f.box(560, 90, 110, 56, ["2-FF sync", "(write ptr in)"], C["green2"], C["green"], 11, True); f.box(740, 90, 160, 56, ["empty: read pointer", "equals write pointer"], C["gray2"], C["gray"], 11, True)
f.arrow(192, 118, 558, 118, C["purple"], 2.2); f.text(375, 108, "write pointer, Gray coded", 11, C["purple"], bold=True); f.arrow(672, 118, 738, 118, C["ink"], 1.8)
f.box(40, 290, 150, 56, ["full: write pointer", "a lap ahead of read"], C["gray2"], C["gray"], 10.5, True); f.box(250, 290, 110, 56, ["2-FF sync", "(read ptr in)"], C["green2"], C["green"], 11, True); f.box(750, 290, 150, 56, ["read pointer", "binary + Gray register"], C["gray2"], C["gray"], 11.5, True)
f.arrow(748, 318, 362, 318, C["purple"], 2.2); f.text(560, 308, "read pointer, Gray coded", 11, C["purple"], bold=True); f.arrow(248, 318, 192, 318, C["ink"], 1.8)
f.box(380, 170, 180, 80, ["memory", "wclk writes, rclk reads"], C["teal2"], C["teal"], 11, True)
f.arrow(115, 148, 115, 210, C["ink"], 1.6); f.arrow(115, 210, 378, 210, C["ink"], 1.8); f.text(190, 202, "write data + address", 10.5, C["line"], anchor="start")
f.arrow(562, 210, 825, 210, C["ink"], 1.8); f.arrow(825, 210, 825, 148, C["ink"], 1.6); f.arrow(825, 288, 825, 212, C["ink"], 1.6); f.text(600, 202, "read data (address from the read pointer)", 10.5, C["line"], anchor="start")
f.text(470, 382, "full is judged in the write domain, empty in the read domain; both are conservative (a stale pointer can only hold a flag longer)", 12, C["line"], italic=True)
f.save(f"{OUT}/ch03-fifo.svg")
print("ch03 figures written")
