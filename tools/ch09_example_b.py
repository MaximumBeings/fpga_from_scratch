#!/usr/bin/env python3
"""Chapter 9, example B: three ways to accumulate the Internet checksum one byte per clock (rtl/csum.sv): the carry folded back in the same cycle (csum_e2e), the carry deferred into bit 16 (csum_def), two lane accumulators combined at the end (csum_lane). LUTs, flip-flops and Fmax (nextpnr seed 1, asked for 400 MHz) on iCE40 and ECP5. The correctness of all three is shown by ch09_run.py section 6. Usage: ch09_example_b.py"""
import os, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import flow
VARS = [("csum_e2e", "carry folded in the same cycle"), ("csum_def", "carry deferred (bit 16)"), ("csum_lane", "two lanes, folded at the end")]
def job(a):
    v, fam = a; return a, flow.run(["rtl/csum.sv"], v, fam, 400, tag=f"{v}_{fam}")
if __name__ == "__main__":
    with cf.ThreadPoolExecutor(4) as ex: res = dict(ex.map(job, [(v[0], f) for v in VARS for f in ("ice40", "ecp5")]))
    print("== the checksum accumulator, three ways (Yosys + nextpnr, seed 1, asked for 400 MHz); Fmax is register to register: the combinational `sum` output is a pin path and is not timed")
    print(f"  {'accumulator':12s} {'idea':32s} | {'iCE40 LUT':>9s} {'FF':>4s} {'Fmax MHz':>9s} | {'ECP5 LUT':>8s} {'FF':>4s} {'Fmax MHz':>9s}")
    for v, idea in VARS:
        i, e = res[(v, "ice40")], res[(v, "ecp5")]
        print(f"  {v:12s} {idea:32s} | {i['luts']:9d} {i['ffs']:4d} {i['fmax']:9.1f} | {e['luts']:8d} {e['ffs']:4d} {e['fmax']:9.1f}")
