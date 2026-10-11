#!/usr/bin/env python3
"""Chapter 27 figures -> docs/assets/fig/ch27-*.svg"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figs import Fig, C, bar_chart, line_chart
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "docs", "assets", "fig"); os.makedirs(OUT, exist_ok=True)
f = Fig(980, 400, "States"); f.text(490, 24, "The supervisor: four states, one way out of RUN, and no way out of SAFE except a reset", 14, bold=True)
def st(x, y, w, t, col): f.box(x, y, w, 70, t, C[col + "2"], C[col], 11, True)
st(30, 150, 150, ["INIT", "WARM cycles", "kill = 1"], "gray"); st(260, 150, 150, ["READY", "waits for go and an", "ACTIVE session"], "blue"); st(490, 150, 150, ["RUN", "orders may leave", "kill = 0"], "green"); st(740, 150, 200, ["SAFE", "kill = 1, one logout,", "absorbing"], "orange")
f.arrow(182, 185, 258, 185, C["ink"], 1.6); f.arrow(412, 185, 488, 185, C["ink"], 1.6); f.arrow(642, 185, 738, 185, C["ink"], 1.6)
f.text(220, 175, "WARM", 10); f.text(450, 175, "go", 10); f.text(690, 175, "any cause", 10)
f.text(490, 270, "causes in RUN: no feed byte for FT cycles | strategy slot held ST cycles | external trip | tracker fault | session not ACTIVE", 11, italic=True)
f.text(490, 295, "a reset (rst_u, from the reset generator) returns every state to INIT", 11, italic=True)
f.text(490, 340, "the cause is latched (a bit for each that was true) and is the only record of why", 11, C["red"], italic=True)
f.save(f"{OUT}/ch27-states.svg")
g = Fig(980, 330, "Safe"); g.text(490, 24, "What the supervisor adds to the wire-to-wire design", 14, bold=True)
g.box(20, 130, 130, 80, ["rst_in", "(asynchronous)"], C["gray2"], C["gray"], 11, True); g.box(190, 130, 140, 80, ["rst_gen", "synchronous release,", "stretched"], C["blue2"], C["blue"], 11, True)
g.box(380, 40, 150, 90, ["sup", "state, kill,", "logout, cause"], C["orange2"], C["orange"], 11, True); g.box(380, 180, 220, 100, ["w2w (Chapter 26)", "taps: slot, fault, session,", "transmitter ready, quiet"], C["green2"], C["green"], 11, True)
g.box(680, 130, 150, 80, ["order entry", "bytes"], C["gray2"], C["gray"], 11, True)
g.arrow(152, 170, 188, 170, C["ink"], 1.6); g.arrow(332, 150, 378, 100, C["ink"], 1.4); g.arrow(332, 190, 378, 220, C["ink"], 1.4); g.arrow(455, 132, 455, 178, C["red"], 1.6); g.arrow(602, 230, 678, 190, C["ink"], 1.6); g.arrow(660, 85, 532, 85, C["ink"], 1.2)
g.text(470, 160, "kill, logout", 10, C["red"], anchor="start"); g.text(670, 80, "feed byte, go, trip", 10, anchor="start")
g.save(f"{OUT}/ch27-system.svg")
print("ch27 figures written")
