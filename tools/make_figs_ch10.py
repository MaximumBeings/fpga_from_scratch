#!/usr/bin/env python3
"""Chapter 10 figures -> docs/assets/fig/ch10-*.svg (data from out/ch10_*_out.txt)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figs import Fig, C, bar_chart, line_chart
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "docs", "assets", "fig"); os.makedirs(OUT, exist_ok=True)
rd = lambda n: open(f"{ROOT}/out/{n}").read()
# 10.1 the two structures
f = Fig(960, 400, "Engines"); f.text(480, 24, "Two ways to find an entry: compare with all of them, or compute where it must be", 14, bold=True)
f.rect(20, 44, 450, 336, C["gray2"], C["gray"], 1.2, 10, op=.5); f.text(245, 68, "CAM: N comparators in parallel", 13, bold=True)
f.box(40, 190, 70, 40, "key", C["gray2"], C["gray"], 12)
for k in range(4):
    y = 90 + k * 62; f.box(160, y, 130, 40, [f"slot {k}", "key, mask or range, value"], C["blue2"], C["blue"], 9.5); f.arrow(110, 210, 158, y + 20, C["line"], 1.2); f.box(305, y + 6, 30, 28, "=", C["orange2"], C["orange"], 12, True); f.arrow(290, y + 20, 304, y + 20, C["ink"], 1.3)
    f.arrow(336, y + 20, 360, y + 20, C["ink"], 1.3)
f.text(245, 345, "...", 14); f.box(360, 120, 90, 150, ["priority", "encoder", "lowest slot", "wins"], C["green2"], C["green"], 10.5, True); f.arrow(450, 195, 468, 195, C["ink"], 1.5)
f.text(245, 372, "area grows with the number of slots; one lookup per clock", 11.5, C["red"], bold=True)
f.rect(490, 44, 450, 336, C["gray2"], C["gray"], 1.2, 10, op=.5); f.text(715, 68, "Hash table in block RAM (two choices)", 13, bold=True)
f.box(510, 190, 70, 40, "key", C["gray2"], C["gray"], 12); f.box(620, 110, 100, 40, "hash 1", C["orange2"], C["orange"], 12, True); f.box(620, 250, 100, 40, "hash 2", C["orange2"], C["orange"], 12, True)
f.arrow(580, 205, 618, 135, C["line"], 1.3); f.arrow(580, 215, 618, 265, C["line"], 1.3)
f.box(760, 90, 90, 80, ["RAM 0", "{valid, key, value}"], C["blue2"], C["blue"], 10, True); f.box(760, 230, 90, 80, ["RAM 1", "{valid, key, value}"], C["blue2"], C["blue"], 10, True); f.arrow(720, 130, 758, 130, C["ink"], 1.4); f.arrow(720, 270, 758, 270, C["ink"], 1.4)
f.box(870, 170, 60, 60, ["key", "equal?"], C["green2"], C["green"], 10, True); f.arrow(850, 130, 868, 190, C["ink"], 1.3); f.arrow(850, 270, 868, 210, C["ink"], 1.3)
f.text(715, 345, "area is a few hundred LUTs plus RAM, whatever the capacity;", 11.5, C["green"], bold=True); f.text(715, 365, "two RAM reads per lookup; the control plane places the entry", 11.5, C["green"], bold=True)
f.save(f"{OUT}/ch10-engines.svg")
# 10.2 priority
f = Fig(960, 270, "Priority"); f.text(480, 24, "Ternary match: several entries match, the lowest slot wins, not the most specific", 14, bold=True)
for k, (nm, sub, col) in enumerate((("slot 0", "10.0.0.0 / 8   (mask 0xFF000000)  value 1", C["blue"]), ("slot 1", "10.1.0.0 / 16 (mask 0xFFFF0000)  value 2", C["orange"]), ("slot 2", "empty", C["gray"]))):
    f.box(60, 56 + k * 56, 120, 40, nm, C["gray2"], C["gray"], 12, True); f.box(190, 56 + k * 56, 380, 40, sub, C["blue2"] if k == 0 else (C["orange2"] if k == 1 else C["gray2"]), col, 12, mono=True)
f.box(610, 70, 300, 70, ["query 10.1.2.3", "matches slot 0 and slot 1", "-> answer: value 1 (slot 0)"], C["green2"], C["green"], 12, True)
f.text(480, 250, "to make the longest prefix win, the control plane must write the more specific entries into LOWER slots (sort by prefix length)", 12, C["line"], italic=True)
f.save(f"{OUT}/ch10-priority.svg")
# 10.3 multicast alias
f = Fig(960, 300, "Multicast"); f.text(480, 24, "An IPv4 multicast group is 28 bits; its Ethernet address keeps 23", 14, bold=True)
f.box(40, 70, 90, 50, ["1110"], C["gray2"], C["gray"], 13, True, mono=True); f.box(130, 70, 150, 50, ["5 bits: LOST"], C["red2"], C["red"], 12, True); f.box(280, 70, 340, 50, ["23 bits kept"], C["green2"], C["green"], 13, True)
f.text(85, 140, "224.0.0.0/4", 11, C["line"]); f.text(205, 140, "bits 27..23", 11, C["line"]); f.text(450, 140, "bits 22..0", 11, C["line"])
f.box(40, 190, 580, 50, ["01:00:5E  +  0 + 23 bits   =  the destination MAC"], C["blue2"], C["blue"], 13, True, mono=True); f.arrow(450, 122, 450, 188, C["ink"], 1.6)
f.text(700, 100, "32 different groups share one MAC address:", 12, C["red"], "start", True); f.text(700, 120, "224.1.1.1, 225.1.1.1, ... 239.1.1.1", 12, C["red"], "start", mono=True); f.text(700, 150, "a filter on the MAC address cannot tell them apart", 12, C["red"], "start")
f.text(480, 280, "an exact filter on the MAC accepts every alias of a subscribed group; only the IP address tells them apart", 12, C["line"], italic=True)
f.save(f"{OUT}/ch10-alias.svg")
# 10.4 cost
A = rd("ch10_example_a_out.txt"); ra = re.findall(r"^\s+(.+?)\s+(\d+) \|\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+[\d.]+ \|\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)", A, re.M)
if ra:
    lab = [r[0].replace(" entries", "").replace("hash, 1 table x", "hash 1x").replace("hash, 2 tables x", "hash 2x").replace("range matcher", "range").replace("ternary CAM", "TCAM").replace("exact CAM", "CAM") for r in ra]
    bar_chart(980, 360, lab, [[int(r[2]) for r in ra], [int(r[6]) for r in ra]], "LUTs of each engine (the hash tables also use block RAM)", "LUTs", colors=[C["orange"], C["teal"]], fmt="{:.0f}", legend=["iCE40", "ECP5"]).save(f"{OUT}/ch10-cost.svg")
    bar_chart(980, 360, lab, [[float(r[5]) for r in ra], [float(r[10]) for r in ra]], "Fmax of each engine (MHz; a query every clock)", "MHz", colors=[C["orange"], C["teal"]], fmt="{:.0f}", legend=["iCE40", "ECP5"]).save(f"{OUT}/ch10-fmax.svg")
# 10.5 failure vs load, 10.6 false positives
B = rd("ch10_example_b_out.txt"); rows = re.findall(r"^\s+(\d+)% \|\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)% \|\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%", B, re.M)
if rows:
    xs = [int(r[0]) for r in rows]; line_chart(900, 340, xs, [[float(r[1]) for r in rows], [float(r[6]) for r in rows], [float(r[9]) for r in rows], [float(r[2]) for r in rows]], "Keys the control plane could not place, against the load (512 slots)", "load (%)", "keys not placed (%)", legend=["1 x 512, random", "2 x 256, random", "2 x 256, stride", "1 x 512, derived"], colors=[C["orange"], C["teal"], C["red"], C["gray"]]).save(f"{OUT}/ch10-fail.svg")
fp = re.findall(r"^\s+(\d+) \|\s+\d+ of\s+\d+\s+([\d.e+-]+)\s+([\d.e+-]+)\s+([\d.e+-]+) \|", B, re.M)
fp = [r for r in fp if float(r[1]) > 0 and int(r[0]) < 32]
if fp:
    line_chart(900, 340, [int(r[0]) for r in fp], [[float(r[1]) for r in fp], [float(r[2]) for r in fp], [float(r[3]) for r in fp]], "False-positive rate against the stored key bits (random keys)", "stored bits KW", "false-positive rate", logy=True, legend=["measured", "derived (2^-KW)", "derived (with hash 2 rank)"], colors=[C["orange"], C["gray"], C["teal"]], yfmt="{:.0e}").save(f"{OUT}/ch10-fp.svg")
print("ch10 figures written")
