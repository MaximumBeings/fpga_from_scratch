#!/usr/bin/env python3
"""Chapter 7 figures -> docs/assets/fig/ch07-*.svg (data from out/ch07_*_out.txt and crc_gen)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
from figs import Fig, C, bar_chart, line_chart
import crc_gen
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "docs", "assets", "fig"); os.makedirs(OUT, exist_ok=True)
A = open(f"{ROOT}/out/ch07_example_a_out.txt").read()
# 7.1 frame layout
f = Fig(940, 230, "Frame"); f.text(470, 24, "An Ethernet frame on the wire (sizes in bytes)", 14, bold=True)
parts = [("preamble", 7, C["gray2"], C["gray"]), ("SFD", 1, C["gray2"], C["gray"]), ("destination", 6, C["blue2"], C["blue"]), ("source", 6, C["blue2"], C["blue"]), ("type", 2, C["blue2"], C["blue"]), ("payload (46 to 1500)", 46, C["green2"], C["green"]), ("FCS", 4, C["red2"], C["red"])]
x = 30; scale = 880 / (7 + 1 + 6 + 6 + 2 + 46 + 4 + 8)
for name, n, fill, st in parts:
    w = max(n * scale * (1 if n < 40 else 0.55) + (10 if n < 4 else 0), 34); f.rect(x, 70, w, 56, fill, st, 1.8, 4); f.text(x + w / 2, 104, str(n) if n < 40 else "46-1500", 12, bold=True); f.text(x + w / 2, 148, name, 11); x += w + 4
f.text(470, 190, "the FCS is the CRC-32 of everything from the destination address to the end of the payload", 12, C["line"], italic=True)
f.text(470, 212, "the receiver runs the CRC over all of it, FCS included, and expects a fixed residue", 12, C["line"], italic=True)
f.save(f"{OUT}/ch07-frame.svg")
# 7.2 how the XOR equations come from the bit-serial register
f = Fig(940, 300, "Linear"); f.text(470, 24, "The CRC update is linear: each new register bit is an XOR of old register bits and data bits", 14, bold=True)
f.box(30, 60, 190, 70, ["bit-serial CRC", "shift, XOR with the", "polynomial when the", "feedback bit is 1"], C["blue2"], C["blue"], 11, True)
f.arrow(222, 95, 298, 95, C["ink"], 2); f.text(260, 85, "run it", 10.5, C["line"]); f.text(260, 109, "symbolically", 10.5, C["line"])
f.box(300, 60, 210, 70, ["each register bit is a", "SET of variables", "(old state bits, data bits)", "XOR = set difference"], C["orange2"], C["orange"], 11, True)
f.arrow(512, 95, 588, 95, C["ink"], 2); f.text(550, 85, "after N", 10.5, C["line"]); f.text(550, 109, "data bits", 10.5, C["line"])
f.box(590, 60, 320, 70, ["step_k[j] = c[1] ^ c[3] ^ ... ^ d[0] ^ d[2] ^ ...", "one XOR equation per output bit", "(the generated RTL: rtl/crc32_stream.sv)"], C["green2"], C["green"], 11, True)
f.text(470, 175, "new_state = A_k(state)  XOR  B_k(data)", 15, bold=True)
f.text(470, 205, "A is a 32 x 32 matrix over GF(2), B is 32 x (8k): the FEEDBACK needs only A; B depends on the input alone and can be pipelined freely", 12, C["line"], italic=True)
f.text(470, 235, "linearity also gives the proof used in this chapter: a linear function that agrees on a basis agrees everywhere", 12, C["line"], italic=True)
f.save(f"{OUT}/ch07-linear.svg")
# 7.3 XOR inputs per output bit
ws = [8, 16, 32, 64]; mx = [max(crc_gen.row_weights(w // 8)) for w in ws]; mn = [min(crc_gen.row_weights(w // 8)) for w in ws]
bar_chart(900, 320, [f"{w} bits" for w in ws], [mn, mx], "Inputs XORed to make one output bit (minimum and maximum over the 32 bits)", "inputs", colors=[C["teal"], C["orange"]], fmt="{:.0f}", legend=["fewest", "most"]).save(f"{OUT}/ch07-weights.svg")
# 7.4 Fmax against width, three variants on ECP5
secs = A.split("== 2.")[1].split("== 3.")
def col(txt, idx): return [float(m) for m in re.findall(r"^\s+\d+ \|\s+\d+\s+\d+\s+[\d.]+\s+[\d.]+ \|\s+\d+\s+\d+\s+([\d.]+)", txt, re.M)]
e1 = col(secs[0], 0); e2 = col(secs[1].split("== 4.")[0], 0)
line_chart(900, 340, ws, [e1, e2, [156.25] * 4], "Fmax of the CRC datapath on ECP5 against the width (nextpnr, seed 1)", "bits per beat", "MHz", colors=[C["red"], C["green"], C["gray"]], legend=["single stage", "pipelined", "156.25 MHz (10GbE at 64 bits)"], xfmt="{:.0f}", yfmt="{:.0f}", ymin=0).save(f"{OUT}/ch07-fmax.svg")
# 7.5 the pipelined design
f = Fig(940, 340, "Fast"); f.text(470, 24, "crc32_fast: the data part is feed-forward; only A_8 is in the loop", 14, bold=True)
f.box(20, 70, 120, 50, ["input regs", "d, nbytes, last"], C["blue2"], C["blue"], 11, True); f.box(180, 40, 150, 46, ["B_8(d)  (3 levels)"], C["orange2"], C["orange"], 11, True); f.box(180, 100, 150, 46, ["B_k(d), k = nbytes"], C["orange2"], C["orange"], 11, True)
f.box(370, 40, 90, 46, "reg", C["blue2"], C["blue"], 11, True); f.box(370, 100, 90, 46, "reg", C["blue2"], C["blue"], 11, True)
f.box(510, 30, 180, 70, ["loop: st <= A_8(st) ^ B_8", "(at most 19 + 1 inputs)", "restart after the last beat"], C["red2"], C["red"], 11, True)
f.box(510, 150, 180, 56, ["snapshot of st, B_k on the", "last beat"], C["blue2"], C["blue"], 11, True)
f.box(740, 150, 170, 56, ["x5 = A_k(snapshot) ^ B_k", "(k picks one of eight A_k)"], C["orange2"], C["orange"], 11, True)
f.box(740, 240, 170, 50, ["out_crc = ~x5", "out_good = (~x5 == residue)"], C["green2"], C["green"], 11, True)
for a, b in (((142, 95), (178, 63)), ((142, 100), (178, 123)), ((332, 63), (368, 63)), ((332, 123), (368, 123)), ((462, 63), (508, 63)), ((462, 123), (508, 170)), ((692, 178), (738, 178)), ((825, 208), (825, 238))): f.arrow(a[0], a[1], b[0], b[1], C["ink"], 1.7)
f.path("M600,100 C600,115 600,130 600,148", "none", C["red"], 1.6)
f.text(470, 320, "latency 5 cycles; the long pieces (B and A_k) are outside the loop, so they are cut by registers; only the 20-input loop limits the clock", 11.5, C["line"], italic=True)
f.save(f"{OUT}/ch07-fast.svg")
print("ch07 figures written")
