#!/usr/bin/env python3
"""Chapter 13 figures -> docs/assets/fig/ch13-*.svg (data from out/ch13_*_out.txt)."""
import os, re, sys, textwrap
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figs import Fig, C, bar_chart, line_chart
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "docs", "assets", "fig"); os.makedirs(OUT, exist_ok=True)
rd = lambda n: open(f"{ROOT}/out/{n}").read()
# 13.1 the sender's sequence space
f = Fig(980, 330, "Sender"); f.text(490, 24, "The sender's view of the sequence space: what is acknowledged, in flight, allowed, and still to come", 14, bold=True)
x0 = 40; y = 110; h = 50
segs = [(x0, 200, "acknowledged", C["gray2"], C["gray"]), (240, 240, "in flight (sent, not acknowledged)", C["orange2"], C["orange"]), (480, 200, "may be sent now (inside the window)", C["green2"], C["green"]), (680, 120, "beyond the window", C["red2"], C["red"]), (800, 140, "not yet written", C["gray2"], C["gray"])]
for x, w, lab, fl, st in segs: f.box(x, y, w - 4, h, textwrap.wrap(lab, max(12, w // 8)), fl, st, 10.5)
for x, nm, sub in ((240, "SND.UNA", "oldest unacknowledged"), (480, "SND.NXT", "next to send"), (680, "SND.UNA + wnd", "window edge"), (800, "end", "data the application has written")):
    f.line(x - 2, 90, x - 2, 175, C["ink"], 2); f.text(x - 2, 82, nm, 12, bold=True); f.text(x - 2, 192, sub, 10, C["line"])
f.text(360, 236, "SND.MAX (not drawn): the highest sequence number ever sent. After a timeout SND.NXT goes back to SND.UNA;", 11.5, C["line"]); f.text(360, 254, "bytes between SND.NXT and SND.MAX are then sent again and flagged as retransmissions (no RTT sample from them: Karn).", 11.5, C["line"])
f.text(490, 300, "a new ACK in (SND.UNA, SND.MAX] moves SND.UNA right; a window update moves the green/red edge", 12, C["ink"], italic=True)
f.save(f"{OUT}/ch13-sender.svg")
# 13.2 the estimator
f = Fig(980, 360, "RTO"); f.text(490, 24, "The retransmission timer (RFC 6298) in fixed point", 14, bold=True)
f.box(40, 60, 420, 110, ["each new ACK that covers the timed segment gives a sample R", "err = R - srtt", "srtt8 += err          (srtt8 = 8 x SRTT: alpha = 1/8)", "rv4 += |err| - rv4/4   (rv4 = 4 x RTTVAR: beta = 1/4)"], C["blue2"], C["blue"], 11.5, mono=True)
f.box(40, 190, 420, 70, ["RTO = SRTT + max(1 tick, 4 x RTTVAR) = (srtt8 >> 3) + max(1, rv4)", "clamped to [RTO_MIN, RTO_MAX]"], C["green2"], C["green"], 11.5, mono=True)
f.box(500, 60, 440, 80, ["timer fires (now >= deadline):", "RTO doubles (up to RTO_MAX); no sample from the retransmission", "(Karn); SND.NXT goes back to SND.UNA; one segment is resent"], C["orange2"], C["orange"], 11.5)
f.box(500, 160, 440, 100, ["the first sample sets  srtt8 = 8R,  rv4 = 2R", "(SRTT = R, RTTVAR = R/2, RTO = 3R);", "when new data is acknowledged without a sample, the backed-off", "RTO is recomputed from SRTT and RTTVAR (a deliberate deviation)"], C["gray2"], C["gray"], 11.5)
f.text(490, 320, "the integers carry the fractions, so the truncation of the shifts does not accumulate (Example B)", 12, C["line"], italic=True)
f.save(f"{OUT}/ch13-rto.svg")
# 13.3 the table and the scanner
f = Fig(980, 330, "Scanner"); f.text(490, 24, "tx_tab: a RAM of connection states and a scanner that visits one connection per idle cycle", 14, bold=True)
f.box(40, 80, 160, 70, ["outside events", "WRITE, ACK, POLL"], C["gray2"], C["gray"], 11.5, True); f.box(40, 190, 160, 70, ["scanner", "TICK for connection sp,", "sp = sp + 1"], C["orange2"], C["orange"], 11.5, True)
f.box(280, 120, 120, 80, ["choose", "one per cycle", "outside first"], C["blue2"], C["blue"], 11.5, True); f.box(470, 120, 150, 80, ["RAM read", "339 bits per", "connection"], C["teal2"], C["teal"], 11.5, True); f.box(690, 120, 120, 80, ["tx_next", "one cycle"], C["green2"], C["green"], 11.5, True); f.box(850, 120, 100, 80, ["segment,", "new state"], C["gray2"], C["gray"], 11.5, True)
for a, b in ((200, 280), (400, 470), (620, 690), (810, 850)): f.arrow(a + 2, 160, b - 2, 160, C["ink"], 1.8)
f.arrow(200, 115, 280, 140, C["ink"], 1.6); f.arrow(200, 225, 280, 180, C["ink"], 1.6)
f.path("M750,200 C750,270 540,270 540,202", "none", C["red"], 1.6); f.text(640, 262, "write back; bypass for the next event", 11, C["red"])
f.text(490, 310, "a timer is seen at most N - 1 cycles after its deadline when N connections share the scanner", 12, C["ink"], italic=True)
f.save(f"{OUT}/ch13-scanner.svg")
A = rd("ch13_example_a_out.txt"); rows = re.findall(r"^\s+(tx_\w+, [^|]+?)\s+\|\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+) \|\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)", A, re.M)
if rows:
    ch = bar_chart(900, 340, [r[0].replace("tx_conn, ", "conn, ").replace("tx_tab, ", "tab, ").replace(" connections", "").replace(" connection", "") for r in rows], [[float(r[4]) for r in rows], [float(r[9]) for r in rows]], "Fmax (MHz); a byte per clock at 1 Gbit/s needs 125", "MHz", colors=[C["orange"], C["teal"]], fmt="{:.0f}", legend=["iCE40", "ECP5"])
    mv = max([float(r[4]) for r in rows] + [float(r[9]) for r in rows]) * 1.12; yy = 40 + (340 - 100) * (1 - 125 / mv); ch.line(70, yy, 880, yy, C["red"], 1.8, "6 4"); ch.text(876, yy - 6, "125 MHz", 11, C["red"], "end", True); ch.save(f"{OUT}/ch13-fmax.svg")
B = rd("ch13_example_b_out.txt"); rs = re.findall(r"^\s+([\d.]+)% \|\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)x", B, re.M)
if rs: bar_chart(900, 320, [r[0] + "%" for r in rs], [[float(r[1]) for r in rs]], "Mean ticks to deliver 20,000 bytes against the loss (log-like growth: 434 ticks without loss)", "ticks", colors=[C["orange"]], fmt="{:.0f}").save(f"{OUT}/ch13-loss.svg")
R = rd("ch13_run_out.txt"); ls = re.findall(r"^\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+(\d+)\s+(\d+)$", R, re.M)
if ls: bar_chart(900, 300, [r[0] for r in ls], [[float(r[3]) for r in ls], [float(r[4]) for r in ls]], "Scanner lateness (cycles) against the number of connections N: mean and maximum", "cycles", colors=[C["blue"], C["red"]], fmt="{:.0f}", legend=["mean", "max (bound N - 1)"]).save(f"{OUT}/ch13-late.svg")
print("ch13 figures written")
