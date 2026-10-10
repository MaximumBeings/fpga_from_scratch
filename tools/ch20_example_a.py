#!/usr/bin/env python3
"""Chapter 20, example A: what the RAM-based book costs. book2 behind its pin wrapper (the 140-bit event shifted in serially, outputs registered and folded) for several sizes, synthesised and placed for iCE40 and ECP5 (nextpnr seed 1, asked for 300 MHz). The sizes are (NS symbols, D levels per side, NB buckets, K ways); the order table holds NB x K orders. Chapter 19's register-only book needed 7,685 LUTs and did not fit the iCE40 HX8K for (2, 4, 16 orders); here the same size and ten times larger are compared. The RAM cells Yosys inferred are counted (SB_RAM40_4K on iCE40; DP16KD and the LUT RAM TRELLIS_DPR16X4 on ECP5)."""
import os, re, subprocess, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import flow
CASES = [(2, 4, 4, 4), (2, 16, 32, 4), (2, 24, 64, 4), (2, 16, 64, 2), (2, 16, 16, 8), (4, 16, 32, 4), (1, 16, 32, 4)]
def crit(log):
    i = log.rfind("Critical path report for clock"); j = log.find("Setup", i); sec = log[i:j + 300]; src = re.findall(r"Source (\S+)", sec); snk = re.findall(r"Sink (\S+)", sec); tl = re.search(r"([\d.]+) ns logic, ([\d.]+) ns routing", sec)
    nm = lambda x: re.sub(r"_(SB_|TRELLIS_|LUT4|CCU2C|PFUMX|L6MUX|RAM)\S*", "", re.sub(r"\.\d+\.\d+(_RAM)?", "", x)); return nm(src[0]), nm(snk[-1]), tl.groups() if tl else ("?", "?")
def job(a):
    (ns, d, nb, k), fam = a
    try: return a, flow.run(["rtl/book2.sv"], "book2_syn", fam, 300, tag=f"t20_{ns}_{d}_{nb}_{k}_{fam}", params={"NS": ns, "D": d, "NB": nb, "K": k})
    except subprocess.TimeoutExpired: return a, {"timeout": True}
if __name__ == "__main__":
    with cf.ThreadPoolExecutor(4) as ex: res = dict(ex.map(job, [(c, f) for c in CASES for f in ("ice40", "ecp5")]))
    print("== resources and clock (Yosys + nextpnr, seed 1, asked for 300 MHz), behind the pin wrapper; order table and levels in RAM")
    print(f"  {'NS':>2s} {'D':>3s} {'NB':>3s} {'K':>2s} {'orders':>6s} | {'iCE40 LUT':>9s} {'FF':>5s} {'EBR':>4s} {'Fmax':>6s} | {'ECP5 LUT':>8s} {'FF':>5s} {'DP16KD':>6s} {'DPR16X4':>7s} {'Fmax':>6s} | {'RAM bits':>8s} {'register bits':>13s}")
    for c in CASES:
        ns, d, nb, k = c; i, e = res[(c, "ice40")], res[(c, "ecp5")]; sw = max(1, (ns - 1).bit_length()); rb = nb * k * (1 + 32 + sw + 1 + 32 + 32) + ns * 2 * d * 64; gb = ns * 2 * (8 + 64) + 16
        if i.get("timeout") or e.get("timeout"): print(f"  {ns:2d} {d:3d} {nb:3d} {k:2d} {nb * k:6d} | synthesis did not finish in 15 minutes"); continue
        fm = lambda r: f"{r['fmax']:6.1f}" if r.get("fmax") else "no fit"
        print(f"  {ns:2d} {d:3d} {nb:3d} {k:2d} {nb * k:6d} | {i['luts']:9d} {i['ffs']:5d} {i['cells'].get('SB_RAM40_4K', 0):4d} {fm(i):>6s} | {e['luts']:8d} {e['ffs']:5d} {e['cells'].get('DP16KD', 0):6d} {e['cells'].get('TRELLIS_DPR16X4', 0):7d} {fm(e):>6s} | {rb:8d} {gb:13d}")
    print("\n== the end points of the critical path (nextpnr's last report for the clock)")
    for c in ((2, 16, 32, 4), (2, 24, 64, 4)):
        for fam in ("ice40", "ecp5"):
            if res[(c, fam)].get("timeout") or not res[(c, fam)].get("fmax"): continue
            a, b, (lg, rt) = crit(res[(c, fam)]["pnr_log"]); print(f"  NS {c[0]} D {c[1]:2d} NB {c[2]:2d} K {c[3]} {fam:6s} {a:22s} -> {b:22s} {lg} ns logic, {rt} ns routing")
