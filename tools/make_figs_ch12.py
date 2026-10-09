#!/usr/bin/env python3
"""Chapter 12 figures -> docs/assets/fig/ch12-*.svg (data from out/ch12_*_out.txt)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figs import Fig, C, bar_chart, line_chart
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "docs", "assets", "fig"); os.makedirs(OUT, exist_ok=True)
rd = lambda n: open(f"{ROOT}/out/{n}").read()
# 12.1 the state machine
f = Fig(980, 560, "TCP states"); f.text(490, 24, "The eleven states and the transitions of the connection (RFC 9293), as the model and the hardware implement them", 14, bold=True)
P = {"CLOSED": (90, 90), "LISTEN": (90, 250), "SYN_SENT": (330, 90), "SYN_RCVD": (330, 250), "ESTABLISHED": (580, 170), "FIN_WAIT_1": (830, 90), "FIN_WAIT_2": (830, 230), "CLOSE_WAIT": (580, 330), "CLOSING": (700, 400), "LAST_ACK": (330, 400), "TIME_WAIT": (830, 480)}
hot = {"ESTABLISHED"}
for nm, (x, y) in P.items():
    f.rect(x - 62, y - 24, 124, 48, C["green2"] if nm in hot else C["blue2"], C["green"] if nm in hot else C["blue"], 2, 24); f.text(x, y + 5, nm, 12.5, bold=True)
import math
def arr(a, b, lab, dx=0, dy=0, col=None):
    (x1, y1), (x2, y2) = P[a], P[b]; ang = math.atan2(y2 - y1, x2 - x1); sx, sy = x1 + 66 * math.cos(ang), y1 + 26 * math.sin(ang); ex, ey = x2 - 66 * math.cos(ang), y2 - 26 * math.sin(ang)
    f.arrow(sx, sy, ex, ey, col or C["ink"], 1.6); f.text((sx + ex) / 2 + dx, (sy + ey) / 2 + dy, lab, 10.5, col or C["line"])
arr("CLOSED", "LISTEN", "passive open", -50, 0); arr("CLOSED", "SYN_SENT", "active open / SYN", 0, -8); arr("LISTEN", "SYN_RCVD", "SYN / SYN+ACK", 0, -8); arr("SYN_SENT", "ESTABLISHED", "SYN+ACK / ACK", 10, -24)
arr("SYN_SENT", "SYN_RCVD", "SYN (simultaneous)", 62, 4); arr("SYN_RCVD", "ESTABLISHED", "ACK", 24, 20); arr("ESTABLISHED", "FIN_WAIT_1", "close / FIN", 20, -18); arr("ESTABLISHED", "CLOSE_WAIT", "FIN / ACK", 44, 0)
arr("FIN_WAIT_1", "FIN_WAIT_2", "ACK of FIN", 50, 0); arr("FIN_WAIT_2", "TIME_WAIT", "FIN / ACK", 50, 0)
f.path("M892,100 C990,170 990,300 790,385", "none", C["ink"], 1.6); f.arrow(790, 385, 780, 388, C["ink"], 1.6); f.text(950, 300, "FIN / ACK", 10.5, C["line"], "end")
arr("CLOSING", "TIME_WAIT", "ACK of FIN", -10, 22); arr("CLOSE_WAIT", "LAST_ACK", "close / FIN", -10, -14)
f.arrow(268, 400, 200, 400, C["gray"], 1.5); f.text(120, 404, "ACK of FIN: CLOSED", 10.5, C["line"], "middle"); f.arrow(768, 480, 640, 480, C["gray"], 1.5); f.text(560, 484, "2MSL timeout: CLOSED", 10.5, C["line"], "middle")
f.text(490, 545, "any RST at exactly RCV.NXT, or an abort, returns to CLOSED (SYN_RCVD entered passively returns to LISTEN); green = the hot path (Example B)", 11.5, C["line"], italic=True)
f.save(f"{OUT}/ch12-states.svg")
# 12.2 the window
f = Fig(980, 330, "Window"); f.text(490, 24, "The acceptability test: where may a segment lie, relative to RCV.NXT and the window", 14, bold=True)
f.line(40, 130, 940, 130, C["ink"], 2.5); 
for x, lab in ((200, "RCV.NXT"), (620, "RCV.NXT + wnd")): f.line(x, 112, x, 148, C["red"], 2.5); f.text(x, 100, lab, 12, C["red"], bold=True)
f.rect(200, 118, 420, 24, C["green2"], C["green"], 1.5, 3, op=.7); f.text(410, 135, "the window: wnd bytes", 11.5, C["green"], bold=True)
def seg(x0, x1, y, lab, ok):
    f.rect(x0, y, x1 - x0, 24, C["green2"] if ok else C["red2"], C["green"] if ok else C["red"], 1.6, 4); f.text((x0 + x1) / 2, y + 17, lab, 10.5)
seg(215, 440, 175, "starts in the window: accepted", True); seg(70, 330, 210, "ends in the window (starts before): accepted", True); seg(60, 190, 245, "entirely before: refused", False); seg(640, 820, 175, "entirely after: refused", False)
seg(90, 760, 280, "starts before and ends after the window: refused by the RFC rule", False)
f.text(640, 222, "length 0: accepted only at offsets 0 .. wnd - 1", 11, C["line"], "start"); f.text(640, 242, "window 0: only an empty segment at RCV.NXT", 11, C["line"], "start")
f.save(f"{OUT}/ch12-window.svg")
# 12.3 the table pipeline
f = Fig(980, 380, "Pipeline"); f.text(490, 24, "tcp_tab2: the state in a RAM, the arithmetic and the choice in separate stages", 14, bold=True)
stg = [("0  event in", "read the RAM at the connection id", C["gray2"], C["gray"]), ("1  arithmetic", "differences, sums, equalities from the state read", C["orange2"], C["orange"]), ("1b  comparisons", "window and ACK tests from the differences (4-stage design)", C["orange2"], C["orange"]), ("2  choice", "new state, segment to send, bytes delivered; write back", C["green2"], C["green"]), ("result", "registered", C["teal2"], C["teal"])]
import textwrap
for k, (nm, sub, fl, st) in enumerate(stg):
    x = 30 + k * 190; f.box(x, 70, 170, 110, [nm] + textwrap.wrap(sub, 24), fl, st, 11.5, True)
    if k: f.arrow(x - 18, 125, x - 2, 125, C["ink"], 1.8)
f.text(490, 215, "an event for the SAME connection must wait until the previous one has been written back:", 12, C["red"], bold=True); f.text(490, 235, "ev_ready is low while its connection id is in any stage", 12, C["red"], bold=True)
f.text(490, 262, "events for different connections enter one per cycle; the bypass of the first design (tcp_tab) removed the wait", 12, C["line"]); f.text(490, 280, "at the price of a longer path", 12, C["line"])
f.text(490, 312, "latency 3 or 4 cycles, throughput one event per cycle across connections; for one connection one event per 3 or 4 cycles", 12, C["ink"])
f.text(490, 345, "per-connection state: 4 + 1 + 32 + 32 + 32 = 101 bits", 12, C["blue"], bold=True)
f.save(f"{OUT}/ch12-pipeline.svg")
A = rd("ch12_example_a_out.txt"); rows = re.findall(r"^\s+(tcp_\w+, [^|]+?)\s+\|\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+) \|\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)", A, re.M)
sel = [r for r in rows if "64 connections" in r[0] or "one cycle" in r[0] or "hot path" in r[0]]
if sel:
    ch = bar_chart(900, 360, [r[0].replace("tcp_tab2, ", "tab2, ").replace(", 64 connections", " (64)").replace("tcp_tab, ", "tab, ").replace("tcp_conn, one cycle, 1 connection", "conn, 1 cycle").replace("tcp_fast, the hot path alone", "hot path") for r in sel], [[float(r[4]) for r in sel], [float(r[9]) for r in sel]], "Fmax (MHz); a byte per clock at 1 Gbit/s needs 125", "MHz", colors=[C["orange"], C["teal"]], fmt="{:.0f}", legend=["iCE40", "ECP5"])
    mv = max([float(r[4]) for r in sel] + [float(r[9]) for r in sel]) * 1.12; yy = 40 + (360 - 100) * (1 - 125 / mv); ch.line(70, yy, 880, yy, C["red"], 1.8, "6 4"); ch.text(876, yy - 6, "125 MHz", 11, C["red"], "end", True); ch.save(f"{OUT}/ch12-fmax.svg")
B = rd("ch12_example_b_out.txt"); rs = re.findall(r"^\s+(\d+)% \|\s+\d+\s+\d+\s+([\d.]+)%", B, re.M)
if rs: bar_chart(900, 320, [r[0] + "%" for r in rs], [[float(r[1]) for r in rs]], "Share of events the hot path handles, against the share of oddities", "% of events", colors=[C["green"]], fmt="{:.1f}", maxv=115).save(f"{OUT}/ch12-hot.svg")
print("ch12 figures written")
