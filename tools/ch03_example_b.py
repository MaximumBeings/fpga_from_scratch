#!/usr/bin/env python3
"""Chapter 3, example B: crossing clock domains. (1) Exhaustive: for a pointer of 2 to 8 bits, which values can a mid-change capture produce, for binary and for Gray (derived, by enumeration). (2) MTBF of a synchronizer chain: the formula with ASSUMED constants. (3) What the asynchronous FIFO costs in a real device: LUTs, flip-flops, block RAM and the maximum frequency of EACH clock (measured with Yosys and nextpnr). Usage: ch03_example_b.py"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, cdc_model
if __name__ == "__main__":
    print("== 1. every pointer step, every way a mid-change capture can come out (each changing bit independently takes its old or its new value)")
    print(f"  {'bits':>4s} {'steps':>6s} | {'binary: steps with a wrong value':>34s} {'wrong values':>13s} | {'Gray: steps with a wrong value':>31s}")
    for w in range(2, 9):
        n, bs, bv = cdc_model.pointer_capture(w, False); _, gs, gv = cdc_model.pointer_capture(w, True); print(f"  {w:4d} {n:6d} | {bs:25d} of {n:<5d}{bv:13d} | {gs:20d} of {n:<5d}")
    print("  a binary step changes 1 bit half the time, 2 bits a quarter of the time, and so on; every step that changes k bits has 2^k - 2 wrong captures. A Gray step changes exactly one bit: the only captures are the old and the new value.")
    print("\n== 2. MTBF = exp(tr / tau) / (T0 * fclk * fdata): ASSUMED constants tau = 200 ps, T0 = 100 ps, 2 ns lost to clock-to-q, setup and routing between the flip-flops; data changes at fclk / 10")
    print(f"  {'fclk MHz':>9s} | " + " | ".join(f"{n} flip-flop{'s' if n > 1 else ' '}".rjust(18) for n in (1, 2, 3)))
    def fmt(s):
        if s == float("inf"): return "> 1e300 years"
        y = s / 3.156e7
        return f"{y:.1e} years" if y >= 1 else (f"{s:.1e} s" if s >= 1 else f"{s * 1e3:.1e} ms")
    for f in (50, 100, 150, 200, 250):
        T = 1e6 / f; print(f"  {f:9d} | " + " | ".join(fmt(cdc_model.mtbf(n * T - 2000, 200, 100, f * 1e6, f * 1e5)).rjust(18) for n in (1, 2, 3)))
    print("  the exponent is why one extra flip-flop turns hours into centuries and why the answer depends so sharply on the clock: tau and T0 are properties of the device and of the supply voltage and temperature (take them from the vendor), not of this book")
    print("\n== 3. the asynchronous FIFO in iCE40 HX8K (target 100 MHz on each clock; seed 1): cost and the maximum frequency of EACH clock")
    print(f"  {'W':>3s} {'depth':>6s} {'code':>7s} {'LUTs':>5s} {'FFs':>5s} {'RAM4K':>5s} {'Fmax wclk':>10s} {'Fmax rclk':>10s}")
    for W, AW, G in ((8, 3, 1), (8, 3, 0), (16, 5, 1), (32, 6, 1)):
        s = flow.synth(["rtl/cdc_sync.sv", "rtl/cdc.sv"], "cdc_afifo", "ice40", tag=f"af_{W}_{AW}_{G}", params={"W": W, "AW": AW, "GRAY": G})
        p = flow.pnr(s["json"], "ice40", 100, 1); f = dict(re.findall(r"Max frequency for clock '([^']*)': ([\d.]+) MHz", p["log"]))
        fw = [v for k, v in f.items() if "wclk" in k]; fr = [v for k, v in f.items() if "rclk" in k]
        print(f"  {W:3d} {1 << AW:6d} {'Gray' if G else 'binary':>7s} {s['luts']:5d} {s['ffs']:5d} {s['cells'].get('SB_RAM40_4K', 0):5d} {fw[0] if fw else '?':>10s} {fr[0] if fr else '?':>10s}")
    print("  the storage here is the FWFT read of Section 3.6 (a combinational read of the memory array), which an FPGA builds from LUTs and flip-flops, not block RAM: that is why the area grows with width x depth. A block-RAM FIFO has a registered read and needs a prefetch stage; Chapter 8 builds it.")
