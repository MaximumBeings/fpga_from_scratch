#!/usr/bin/env python3
"""Chapter 10, example A: what a match costs. LUTs, flip-flops, block RAMs and Fmax (nextpnr seed 1, asked for 300 MHz) of the exact CAM, the ternary CAM and the range matcher at 16, 32 and 64 entries, and of the hash tables of equal and larger capacity, on iCE40 and ECP5. Usage: ch10_example_a.py"""
import os, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import flow
CASES = []
for mode, nm in ((0, "exact CAM"), (1, "ternary CAM"), (2, "range matcher")):
    for n in (16, 32, 64): CASES.append((f"{nm}, {n} entries", "match_cam", {"N": n, "MODE": mode}, n))
for ch, aw in ((1, 8), (2, 7), (2, 8)): CASES.append((f"hash, {ch} table{'s' if ch > 1 else ''} x {1 << aw}", "hash_tab", {"AW": aw, "CH": ch}, ch << aw))
def job(a):
    k, fam = a; nm, top, params, cap = CASES[k]; return a, flow.run(["rtl/match.sv"], top, fam, 300, tag=f"m10_{k}_{fam}", params=params)
if __name__ == "__main__":
    with cf.ThreadPoolExecutor(4) as ex: res = dict(ex.map(job, [(k, f) for k in range(len(CASES)) for f in ("ice40", "ecp5")]))
    print("== resources and clock of the match engines (Yosys + nextpnr, seed 1, asked for 300 MHz); 'RAM' = SB_RAM40_4K (iCE40) or DP16KD (ECP5); LUT/entry = LUTs divided by the entries (slots) held")
    print(f"  {'engine':26s} {'slots':>5s} | {'iCE40 LUT':>9s} {'FF':>6s} {'RAM':>4s} {'Fmax':>6s} {'LUT/slot':>8s} | {'ECP5 LUT':>8s} {'CCU2C':>5s} {'FF':>6s} {'RAM':>4s} {'Fmax':>6s} {'LUT/slot':>8s}")
    for k, (nm, top, params, cap) in enumerate(CASES):
        i, e = res[(k, "ice40")], res[(k, "ecp5")]; ri = i["cells"].get("SB_RAM40_4K", 0); re_ = e["cells"].get("DP16KD", 0)
        print(f"  {nm:26s} {cap:5d} | {i['luts']:9d} {i['ffs']:6d} {ri:4d} {i['fmax']:6.1f} {i['luts'] / cap:8.1f} | {e['luts']:8d} {e['carry']:5d} {e['ffs']:6d} {re_:4d} {e['fmax']:6.1f} {e['luts'] / cap:8.1f}")
    print("  a query every cycle at the Fmax shown = Fmax million lookups per second (derived); a 64-byte frame needs one lookup per 84 byte times at 1 Gbit/s, so even 10 MHz is enough for line rate on minimum frames; the cost is area.")
