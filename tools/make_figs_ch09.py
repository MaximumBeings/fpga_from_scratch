#!/usr/bin/env python3
"""Chapter 9 figures -> docs/assets/fig/ch09-*.svg (data from out/ch09_*_out.txt)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figs import Fig, C, bar_chart
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "docs", "assets", "fig"); os.makedirs(OUT, exist_ok=True)
rd = lambda n: open(f"{ROOT}/out/{n}").read()
# 9.1 the headers and what the filter takes from them
f = Fig(960, 490, "Headers"); f.text(480, 24, "A UDP frame: the headers the filter follows, the fields it captures, the bytes each checksum covers", 14, bold=True)
x = 20; y = 48; h = 50
for name, sub, w, fill, st in (("dst MAC", "6", 88, C["gray2"], C["gray"]), ("src MAC", "6", 88, C["gray2"], C["gray"]), ("type", "2", 64, C["yellow2"], C["orange"]), ("VLAN tags", "0 to 2 x 4", 122, C["purple2"], C["purple"]), ("IPv4 header", "20 to 60", 150, C["blue2"], C["blue"]), ("UDP header", "8", 110, C["green2"], C["green"]), ("payload", "UDP length - 8", 150, C["gray2"], C["gray"]), ("pad", "to 60 bytes", 90, C["gray2"], C["gray"])):
    f.box(x, y, w - 4, h, [name], fill, st, 11.5, True, sub=sub + " bytes" if sub[0].isdigit() or sub.startswith("U") or sub.startswith("to") else sub); x += w
f.text(20, 118, "A VLAN tag is a type 0x8100 or 0x88A8 followed by 2 bytes of tag (the low 12 bits are the VLAN id) and the real type; the filter follows at most two.", 11, C["line"], "start", italic=True)
# IPv4 expanded
f.text(20, 148, "IPv4 header, byte by byte (blue = captured; the options of a longer header are summed and skipped):", 12, C["blue"], "start", True)
ix = 40; bw = 43; fy = 160
for nm, b0, n, cap in (("ver", 0, 1, 1), ("tos", 1, 1, 0), ("total length", 2, 2, 1), ("id", 4, 2, 0), ("flags/offset", 6, 2, 1), ("ttl", 8, 1, 0), ("proto", 9, 1, 1), ("checksum", 10, 2, 0), ("source address", 12, 4, 1), ("destination address", 16, 4, 1)):
    f.box(ix + b0 * bw, fy, n * bw - 3, 38, [nm], C["blue2"] if cap else C["gray2"], C["blue"] if cap else C["gray"], 9.5 if n > 1 else 8.5, bool(cap))
    f.text(ix + b0 * bw + (n * bw - 3) / 2, fy + 52, str(b0), 9.5, C["line"])
f.text(ix, fy + 70, "byte 0 holds the version (must be 4) and IHL (the header is IHL x 4 bytes, at least 20)", 10.5, C["line"], "start", italic=True)
# UDP expanded
f.text(20, 262, "UDP header (green = captured):", 12, C["green"], "start", True)
ux = 40; uy = 274
for nm, b0, n in (("source port", 0, 2), ("destination port", 2, 2), ("length", 4, 2), ("checksum", 6, 2)):
    f.box(ux + b0 * 2 * bw * 0.5 * 1.0 * 2 / 2 * 1.0, uy, 0, 0, "") if False else None
    f.box(ux + b0 * bw * 1.4, uy, n * bw * 1.4 - 3, 38, [nm], C["green2"], C["green"], 10, True); f.text(ux + b0 * bw * 1.4 + (n * bw * 1.4 - 3) / 2, uy + 52, str(b0), 9.5, C["line"])
f.text(ux + 8 * bw * 1.4 + 20, 288, "pseudo-header (not on the wire):", 11.5, C["green"], "start", True); f.text(ux + 8 * bw * 1.4 + 20, 306, "source address, destination address,", 11, C["green"], "start"); f.text(ux + 8 * bw * 1.4 + 20, 322, "0x00 + protocol (17), UDP length", 11, C["green"], "start")
# coverage
cy = 372
def bracket(x0, x1, yy, col, label):
    f.path(f"M{x0},{yy-9} L{x0},{yy} L{x1},{yy} L{x1},{yy-9}", "none", col, 2.2); f.text((x0 + x1) / 2, yy + 18, label, 11.5, col, bold=True)
bracket(40, 40 + 20 * bw, cy, C["blue"], "IP header checksum: sum of the header's 16-bit words is 0xFFFF (IHL x 4 bytes)")
bracket(40, 40 + 8 * bw * 1.4 + 330, cy + 56, C["green"], "UDP checksum: pseudo-header + UDP header + payload, UDP length bytes only (not the pad); a checksum field of 0 means 'none'")
f.text(480, 478, "type 0x0800 = IPv4; any other type (after at most two tags) is not_ip", 11, C["line"], italic=True)
f.save(f"{OUT}/ch09-headers.svg")
# 9.2 the state machine
f = Fig(960, 400, "FSM"); f.text(480, 24, "hdr_filter: follow the headers one byte per clock", 14, bold=True)
P = {"ETH": (110, 100), "VLAN": (110, 240), "NIP": (110, 350), "IP": (400, 100), "UDP": (690, 70), "XIP": (690, 200)}
for s_, (px, py) in P.items(): f.circ(px, py, 36, C["blue2"] if s_ not in ("NIP", "XIP") else C["gray2"], C["blue"] if s_ not in ("NIP", "XIP") else C["gray"], 2.2); f.text(px, py + 5, s_, 14, bold=True)
f.arrow(147, 96, 361, 96, C["ink"], 1.7); f.text(255, 86, "type = 0x0800", 11); f.arrow(110, 138, 110, 202, C["ink"], 1.7); f.text(118, 178, "VLAN type", 11, anchor="start")
f.path("M146,232 C250,232 300,150 366,118", "none", C["ink"], 1.7); f.text(300, 205, "type = 0x0800", 11, anchor="start")
f.path("M78,222 C30,200 30,140 78,118", "none", C["ink"], 1.5); f.text(18, 172, "2nd tag", 10.5, C["line"], anchor="start"); f.text(150, 340, "(from ETH or VLAN: any type that is not a tag or 0x0800)", 10.5, C["line"], anchor="start")
f.arrow(110, 277, 110, 312, C["gray"], 1.5, dash="4 3"); f.text(120, 296, "any other type", 10.5, C["line"], anchor="start")
f.arrow(436, 90, 654, 72, C["ink"], 1.7); f.text(545, 66, "header done, protocol 17", 11); f.arrow(432, 120, 658, 188, C["ink"], 1.7); f.text(520, 168, "header done, other protocol", 11, anchor="start")
f.text(740, 62, "UDP: ports, length, checksum;", 11, anchor="start"); f.text(740, 80, "the segment is summed up to its", 11, anchor="start"); f.text(740, 98, "length; an odd last byte is the", 11, anchor="start"); f.text(740, 116, "high half of a word", 11, anchor="start")
f.text(740, 205, "XIP: count the bytes only", 11, anchor="start"); f.text(740, 250, "NIP: not IP, nothing more to follow", 11, C["line"], anchor="start")
f.text(560, 340, "the last byte of the frame (valid and last) returns every control register to ETH;", 11.5, C["line"], italic=True); f.text(560, 358, "the state it ended in is copied for the verdict", 11.5, C["line"], italic=True)
f.text(480, 388, "positions are one-hot shift registers (IP bytes 0 to 19, UDP bytes 0 to 7): a field is captured by one LUT, if (position) field <= byte", 11.5, C["orange"], bold=True)
f.save(f"{OUT}/ch09-fsm.svg")
# 9.3 the accumulators
f = Fig(960, 340, "Accumulators"); f.text(480, 24, "Three ways to add 16-bit words with a ones' complement carry, one byte per clock", 14, bold=True)
for k, (ttl, sub) in enumerate((("csum_e2e: fold in the same cycle", "register(16) = fold(register + word)"), ("csum_def: defer the carry (bit 16)", "register(17) = low16 + carry + word"), ("csum_lane: two lanes, fold once", "even bytes + odd bytes, 20 bits each"))):
    ox = 20 + k * 315; f.rect(ox, 44, 300, 275, C["gray2"], C["gray"], 1.2, 10, op=.5); f.text(ox + 150, 66, ttl, 12.5, bold=True); f.text(ox + 150, 84, sub, 10.5, C["line"], italic=True)
f.box(40, 130, 90, 40, "word", C["gray2"], C["gray"], 11); f.box(160, 120, 70, 60, ["adder 1", "16 + 16"], C["blue2"], C["blue"], 10.5, True); f.box(40, 205, 90, 40, "register 16", C["green2"], C["green"], 11); f.box(160, 200, 70, 50, ["adder 2", "+ carry"], C["orange2"], C["orange"], 10.5, True); f.box(250, 205, 56, 40, "reg", C["green2"], C["green"], 10)
f.arrow(130, 150, 158, 150, C["ink"], 1.6); f.arrow(195, 182, 195, 198, C["ink"], 1.6); f.text(240, 195, "carry", 10, C["line"], italic=True); f.arrow(228, 225, 248, 225, C["ink"], 1.6); f.text(160, 270, "two carry chains in a row", 11, C["red"], bold=True)
f.box(355, 130, 90, 40, "word", C["gray2"], C["gray"], 11); f.box(468, 120, 110, 60, ["adder", "low16 + carry", "+ word"], C["blue2"], C["blue"], 10, True); f.box(475, 205, 120, 40, "register 17 (carry in bit 16)", C["green2"], C["green"], 10); f.arrow(445, 150, 466, 150, C["ink"], 1.6); f.arrow(520, 182, 520, 203, C["ink"], 1.6)
f.path("M600,225 C625,225 625,150 568,150", "none", C["ink"], 1.6); f.text(380, 270, "one carry chain; fold once at the end (or compare:", 11, C["green"], anchor="start", bold=True); f.text(380, 286, "0xFFFF without carry, 0xFFFE with carry)", 11, C["green"], anchor="start", bold=True)
f.box(670, 120, 70, 40, "even byte", C["gray2"], C["gray"], 10); f.box(670, 172, 70, 40, "odd byte", C["gray2"], C["gray"], 10); f.box(760, 120, 80, 40, "+= lane A", C["blue2"], C["blue"], 10.5); f.box(760, 172, 80, 40, "+= lane B", C["blue2"], C["blue"], 10.5)
f.arrow(740, 140, 758, 140, C["ink"], 1.6); f.arrow(740, 192, 758, 192, C["ink"], 1.6); f.box(740, 228, 150, 36, "A x 256 + B, fold once", C["orange2"], C["orange"], 10.5); f.text(800, 285, "8-bit additions, no word formed", 11, C["green"], bold=True); f.text(800, 300, "in the stream", 11, C["green"], bold=True)
f.save(f"{OUT}/ch09-csum.svg")
# 9.4 the pipeline
f = Fig(960, 300, "Pipeline"); f.text(480, 24, "The verdict is pipelined: latency 3, throughput one byte per clock", 14, bold=True)
stg = [("absorb", "state and sums update with the byte; the last byte arrives", C["blue2"], C["blue"]), ("facts", "registers become single-bit facts, each one comparison deep", C["orange2"], C["orange"]), ("cause", "priority of the facts; field copies; count strobes", C["green2"], C["green"]), ("out", "m_data, m_last, m_bad, cause and fields leave", C["teal2"], C["teal"])]
import textwrap
for k, (nm, sub, fl, st) in enumerate(stg):
    bx = 50 + k * 225; f.box(bx, 70, 190, 96, [nm] + textwrap.wrap(sub, 26), fl, st, 12, True)
    if k: f.arrow(bx - 33, 118, bx - 2, 118, C["ink"], 1.8)
    f.text(bx + 95, 190, ["cycle t (last byte in)", "cycle t+1", "cycle t+2", "cycle t+3 (out)"][k], 11, C["line"], italic=True)
f.text(480, 226, "the registers of the frame are cleared by the first byte of the next frame, which can arrive in cycle t+1: the facts are taken in t+1", 12, C["line"])
f.text(480, 248, "back-to-back frames therefore never wait: each stage holds a different frame", 12, C["line"])
f.text(480, 276, "cause priority: mac_bad > trunc > not_ip > ip_bad > not_udp > udp_bad > not_ours > forward", 12.5, C["orange"], bold=True)
f.save(f"{OUT}/ch09-pipeline.svg")
# 9.5 Fmax of the filter versions
A = rd("ch09_example_a_out.txt"); ra = re.findall(r"^\s+(hdr_\w+(?:, \w+(?: version)?)?(?: \(2 KB buffer\))?)\s+\|\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+[\d.]+ \|\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)", A, re.M)
if ra:
    ch = bar_chart(900, 340, [r[0].replace("hdr_filter, ", "filter, ") for r in ra], [[float(r[4]) for r in ra], [float(r[9]) for r in ra]], "Fmax of the header filter (MHz); a byte per clock at 1 Gbit/s needs 125", "MHz", colors=[C["orange"], C["teal"]], fmt="{:.0f}", legend=["iCE40", "ECP5"])
    mv = max(float(r[4]) for r in ra + []) if False else max([float(r[4]) for r in ra] + [float(r[9]) for r in ra]) * 1.12; yy = 40 + (340 - 100) * (1 - 125 / mv); ch.line(70, yy, 880, yy, C["red"], 1.8, "6 4"); ch.text(876, yy - 6, "125 MHz", 11, C["red"], "end", True); ch.save(f"{OUT}/ch09-fmax.svg")
# 9.6 Fmax of the accumulators
B = rd("ch09_example_b_out.txt"); rb = re.findall(r"^\s+(csum_\w+)\s+.+?\|\s+(\d+)\s+(\d+)\s+([\d.]+) \|\s+(\d+)\s+(\d+)\s+([\d.]+)", B, re.M)
if rb: bar_chart(900, 320, [r[0] for r in rb], [[float(r[3]) for r in rb], [float(r[6]) for r in rb]], "Fmax of the checksum accumulators (MHz)", "MHz", colors=[C["orange"], C["teal"]], fmt="{:.0f}", legend=["iCE40", "ECP5"]).save(f"{OUT}/ch09-csum-fmax.svg")
# 9.7 frames by cause
R = rd("ch09_run_out.txt"); m = re.search(r"frames by cause over all \d+ runs of the model: (.*)", R)
if m:
    pairs = re.findall(r"([a-z_]+) (\d+)", m.group(1)); bar_chart(900, 320, [p[0] for p in pairs], [[int(p[1]) for p in pairs]], "Frames by cause in the stimulus (all runs of section 3)", "frames", colors=[C["blue"]], fmt="{:.0f}").save(f"{OUT}/ch09-causes.svg")
print("ch09 figures written")
