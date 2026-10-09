#!/usr/bin/env python3
"""Chapter 2, example B: what the coding style costs. (1) three valid/ready stage styles in chains of 1 to 32 stages: LUTs, flip-flops and Fmax on two families; (2) the three frame recognizers: area and Fmax. Writes out/ch02_example_b.json. Usage: ch02_example_b.py"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import flow
R = flow.ROOT; res = {"chain": {}, "fsm": {}}; STY = ["slow", "comb", "skid"]
print("== 1. chains of N stages, 32-bit data, target 100 MHz, seed 1 (LUT4s | flip-flops | Fmax in MHz)")
print(f"  {'family':6s} {'N':>3s} | " + " | ".join(f"{s:^26s}" for s in STY))
for fam in ("ice40", "ecp5"):
    for n in (1, 2, 4, 8, 16, 32):
        row = []
        for st in range(3):
            r = flow.run(["rtl/vr.sv"], "vr_chain", fam, 100, f"c2_{fam}_{n}_{st}", {"W": 32, "N": n, "STYLE": st}); res["chain"][f"{fam}/{n}/{st}"] = [r["luts"], r["ffs"], r["fmax"]]; row.append(f"{r['luts']:5d} {r['ffs']:6d} {r['fmax']:9.1f}")
        print(f"  {fam:6s} {n:3d} | " + " | ".join(f"{c:^26s}" for c in row))
print("  three things to read. (1) The 'comb' chain's Fmax falls steadily with N (iCE40: 316 MHz at one stage, 57 at 32; ECP5: 267 to 80): its ready is a combinational path from the last stage's out_ready through every stage to the first stage's in_ready, a LUT and a routing hop per stage. (2) The 'skid' chain is nearly flat (iCE40 152 to 136 MHz from 4 to 32 stages; ECP5 244 to 209) because every ready comes from a register; at 32 stages it is 2.4 times faster than 'comb' on iCE40 and 2.6 times on ECP5. (3) The price: a skid stage has a 2:1 multiplexer on every data bit, so it uses about 37 LUTs per stage where 'comb' uses 2 to 3 (1,185 LUT4s against 75 at 32 stages on iCE40) and twice the flip-flops (66 against 33 per stage). At ONE stage 'comb' wins on speed (316 against 179 MHz) and area: skid buffers belong where the ready path would be long. 'slow' is small and fast but moves one item every two cycles. (The 'slow' and 'skid' columns also drift down a little with N for reasons of placement and reset fan-out.)")
print("\n== 2. the three frame recognizers: LUT4s, flip-flops and Fmax (target 100 MHz, seed 1)")
print(f"  {'family':6s} {'style':26s} {'LUT4':>5s} {'flip-flops':>10s} {'Fmax (MHz)':>11s}")
for fam in ("ice40", "ecp5"):
    for top, lab in (("frame_a", "one always_ff block"), ("frame_b", "two processes + enum"), ("frame_c", "one-hot")):
        r = flow.run(["rtl/frame_fsm.sv"], top, fam, 100, f"f2_{fam}_{top}"); res["fsm"][f"{fam}/{top}"] = [r["luts"], r["ffs"], r["fmax"]]; print(f"  {fam:6s} {lab:26s} {r['luts']:5d} {r['ffs']:10d} {r['fmax']:11.1f}")
print("  the three styles are proved equivalent (run section 4) and cost about the same at this size. The one-hot version is slightly faster on iCE40 (226.6 against about 190 MHz) and no different on ECP5, at one more flip-flop and LUT or two. The choice among them is mostly about readability and about the discipline each enforces (an enum with `unique case` gives the tools something to check; the single-block style makes an omitted output default easy)")
json.dump(res, open(os.path.join(R, "out", "ch02_example_b.json"), "w"))
