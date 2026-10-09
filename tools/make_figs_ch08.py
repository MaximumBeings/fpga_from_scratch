#!/usr/bin/env python3
"""Chapter 8 figures -> docs/assets/fig/ch08-*.svg (data from out/ch08_*_out.txt)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
from figs import Fig, C, bar_chart, line_chart
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "docs", "assets", "fig"); os.makedirs(OUT, exist_ok=True)
rd = lambda n: open(f"{ROOT}/out/{n}").read()
# 8.1 the whole datapath
f = Fig(940, 330, "Datapath"); f.text(470, 24, "The MAC datapath: receive across a clock boundary, transmit from a buffered frame", 14, bold=True)
f.rect(20, 44, 560, 120, C["blue2"], C["blue"], 1.4, 10, "6 4", 0.45); f.text(120, 62, "PHY clock domain", 11.5, C["blue"], bold=True); f.rect(600, 44, 320, 120, C["orange2"], C["orange"], 1.4, 10, "6 4", 0.45); f.text(690, 62, "core clock domain", 11.5, C["orange"], bold=True)
f.box(30, 76, 100, 60, ["PHY", "dv, er, byte"], C["gray2"], C["gray"], 11, True); f.box(160, 76, 130, 60, ["mac_rx", "SFD, FCS, length"], C["blue2"], C["blue"], 11, True); f.box(320, 76, 130, 60, ["loss guard", "marks lost frames"], C["red2"], C["red"], 11, True); f.box(480, 76, 90, 60, ["async FIFO", "(Chapter 3)"], C["green2"], C["green"], 10.5, True)
f.box(630, 76, 140, 60, ["frame_fifo", "commit / roll back"], C["teal2"], C["teal"], 11, True); f.box(800, 76, 110, 60, ["AXI-Stream", "(valid, data, last)"], C["gray2"], C["gray"], 11, True)
for a, b in ((130, 160), (290, 320), (450, 480), (570, 630), (770, 800)): f.arrow(a + 2, 106, b - 2, 106, C["ink"], 1.8)
f.rect(20, 190, 900, 110, C["gray2"], C["gray"], 1, 10, "6 4", 0.35); f.text(130, 208, "transmit (one clock domain in this chapter)", 11.5, C["line"], bold=True)
f.box(30, 222, 130, 60, ["AXI-Stream", "source, with ready"], C["gray2"], C["gray"], 11, True); f.box(200, 222, 160, 60, ["frame_fifo", "whole frame committed"], C["teal2"], C["teal"], 11, True); f.box(400, 222, 200, 60, ["mac_tx", "preamble, pad to 60, FCS, gap 12"], C["blue2"], C["blue"], 10.5, True); f.box(640, 222, 110, 60, ["PHY", "en, byte"], C["gray2"], C["gray"], 11, True)
for a, b in ((160, 200), (360, 400), (600, 640)): f.arrow(a + 2, 252, b - 2, 252, C["ink"], 1.8)
f.arrow(530, 76, 530, 40, C["gray"], 1.2, 7, "3 3") if False else None
f.text(470, 318, "the receive side cannot stall the wire: its output has no ready; the transmit side must hold a whole frame before it starts, because the wire cannot pause", 11.5, C["line"], italic=True)
f.save(f"{OUT}/ch08-datapath.svg")
# 8.2 the receive state machine
f = Fig(940, 300, "RX FSM"); f.text(470, 24, "mac_rx: finding a frame and removing the FCS", 14, bold=True)
pos = {"IDLE": (100, 130), "PRE": (300, 130), "DATA": (520, 130), "IGN": (300, 225)}
for s_, (x, y) in pos.items(): f.circ(x, y, 40, C["blue2"], C["blue"], 2.2); f.text(x, y + 5, s_, 14, bold=True)
f.arrow(142, 125, 258, 125, C["ink"], 1.7); f.text(200, 112, "dv & byte = 0x55", 10, anchor="middle"); f.arrow(342, 125, 478, 125, C["ink"], 1.7); f.text(410, 112, "byte = 0xD5 (SFD)", 10)
f.arrow(122, 168, 262, 214, C["ink"], 1.5); f.text(150, 208, "other byte", 10, C["line"]); f.arrow(300, 172, 300, 182, C["ink"], 1.5); f.text(352, 178, "other byte", 10, C["line"])
f.arrow(262, 232, 130, 172, C["gray"], 1.3); f.text(168, 244, "dv falls", 10, C["line"], italic=True)
f.path("M520,90 C520,40 100,40 100,88", "none", C["green"], 1.7); f.text(310, 52, "dv falls: mark the held byte last; bad = er | length | FCS", 10.5, C["green"])
f.text(660, 135, "4-byte delay line removes the FCS;", 11, anchor="start"); f.text(660, 153, "CRC over every byte after the SFD;", 11, anchor="start"); f.text(660, 171, "the last data byte is held one cycle", 11, anchor="start"); f.text(660, 189, "so that dv falling can mark it", 11, anchor="start")
f.text(560, 262, "IGN: wait for dv to fall (an unrecognised start is ignored whole)", 11.5, C["line"], italic=True)
f.save(f"{OUT}/ch08-rxfsm.svg")
# 8.3 frame_fifo commit and roll back
f = Fig(940, 280, "Frame FIFO"); f.text(470, 24, "frame_fifo: write pointer, commit pointer, read pointer", 14, bold=True)
cells = 22; x0 = 60; w = 36
for k in range(cells):
    fill = C["green2"] if k < 8 else (C["yellow2"] if k < 13 else C["gray2"]); st = C["green"] if k < 8 else (C["orange"] if k < 13 else C["gray"]); f.rect(x0 + k * w, 90, w - 2, 46, fill, st, 1.2, 3)
for name, k, col in (("rptr", 3, C["blue"]), ("cptr", 8, C["green"]), ("wptr", 13, C["orange"])): f.arrow(x0 + k * w + w / 2, 70 if name != "rptr" else 64, x0 + k * w + w / 2, 88, col, 2); f.text(x0 + k * w + w / 2, 58, name, 12, col, bold=True)
f.text(x0 + 3 * w, 160, "committed frames: the reader sees only these (read pointer to commit pointer)", 11.5, C["green"], anchor="start"); f.text(x0 + 8 * w, 182, "frame being written: invisible until its last byte arrives good", 11.5, C["orange"], anchor="start")
f.text(470, 218, "last byte good: commit pointer := write pointer.    last byte bad, or no room: write pointer := commit pointer (the frame vanishes)", 12, C["line"])
f.text(470, 244, "the reader sees a frame one cycle after the commit: a synchronous read of an address being written returns the OLD data", 12, C["line"], italic=True)
f.save(f"{OUT}/ch08-framefifo.svg")
# 8.4 the clock sweep
txt = rd("ch08_example_b_out.txt"); rows = re.findall(r"^\s+(\d+) ps\s+[\d.]+ \|\s+[\d.]+ \|\s+(\d+) /60\s+(\d+)\s+(NO|YES) \|\s+(\d+) /60\s+(\d+)", txt, re.M)
if rows:
    bar_chart(900, 340, [r[0] for r in rows], [[int(r[1]) for r in rows], [int(r[4]) for r in rows]], "Frames delivered of 60 against the core clock period (ps; PHY byte period 8,000 ps)", "frames", colors=[C["red"], C["green"]], fmt="{:.0f}", legend=["crossing FIFO 16 bytes", "crossing FIFO 64 bytes"], maxv=66).save(f"{OUT}/ch08-sweep.svg")
# 8.5 resources
A = rd("ch08_example_a_out.txt"); ra = re.findall(r"^\s+(mac_\w+(?: \(2 KB\))?|frame_fifo [\w ]+?)\s+\|\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+) \|\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)", A, re.M)
if ra: bar_chart(900, 340, [r[0].strip() for r in ra], [[float(r[4]) for r in ra], [float(r[8]) for r in ra]], "Fmax of the MAC pieces (MHz); GMII needs 125", "MHz", colors=[C["orange"], C["teal"]], fmt="{:.0f}", legend=["iCE40", "ECP5"]).save(f"{OUT}/ch08-fmax.svg")
print("ch08 figures written")
