#!/usr/bin/env python3
"""Chapter 21, example A: what the trigger engine costs and how fast it runs. trig behind its pin wrapper (270 bits shifted in serially, outputs registered and folded) for several sizes, synthesised and placed for iCE40 and ECP5 (nextpnr seed 1, asked for 300 MHz): the number of rules R (4, 8, 16) with the comparisons in one stage (PIPE = 0) and in two (PIPE = 1), and the symbol table (NB buckets x K ways: 8 x 2 = 16 symbols, 64 x 4 = 256, 256 x 4 = 1,024). The RAM cells Yosys inferred are counted (SB_RAM40_4K on iCE40; DP16KD and the LUT RAM TRELLIS_DPR16X4 on ECP5). One message per cycle at every size: the throughput is the clock."""
import os, re, subprocess, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import flow
CASES = [(8, 2, 4, 0), (8, 2, 8, 0), (8, 2, 16, 0), (8, 2, 4, 1), (8, 2, 8, 1), (8, 2, 16, 1), (64, 4, 8, 1), (256, 4, 8, 1)]
def crit(log):
    i = log.rfind("Critical path report for clock"); j = log.find("Setup", i); sec = log[i:j + 300]; src = re.findall(r"Source (\S+)", sec); snk = re.findall(r"Sink (\S+)", sec); tl = re.search(r"([\d.]+) ns logic, ([\d.]+) ns routing", sec)
    nm = lambda x: re.sub(r"_(SB_|TRELLIS_|LUT4|CCU2C|PFUMX|L6MUX|RAM)\S*", "", re.sub(r"\.\d+\.\d+(_RAM)?", "", x)); return nm(src[0]), nm(snk[-1]), tl.groups() if tl else ("?", "?")
def job(a):
    (nb, k, r, p), fam = a
    try: return a, flow.run(["rtl/trig.sv"], "trig_syn", fam, 300, tag=f"t21_{nb}_{k}_{r}_{p}_{fam}", params={"NB": nb, "K": k, "R": r, "PIPE": p})
    except subprocess.TimeoutExpired: return a, {"timeout": True}
if __name__ == "__main__":
    with cf.ThreadPoolExecutor(4) as ex: res = dict(ex.map(job, [(c, f) for c in CASES for f in ("ice40", "ecp5")]))
    print("== resources and clock (Yosys + nextpnr, seed 1, asked for 300 MHz), behind the pin wrapper; one message per cycle")
    print(f"  {'NB':>3s} {'K':>2s} {'R':>3s} {'stages':>6s} {'latency':>7s} | {'iCE40 LUT':>9s} {'FF':>5s} {'EBR':>4s} {'Fmax':>6s} | {'ECP5 LUT':>8s} {'FF':>5s} {'DP16KD':>6s} {'DPR16X4':>7s} {'Fmax':>6s}")
    for c in CASES:
        nb, k, r, p = c; i, e = res[(c, "ice40")], res[(c, "ecp5")]
        if i.get("timeout") or e.get("timeout"): print(f"  {nb:3d} {k:2d} {r:3d} {p + 1:6d} {4 + p:7d} | synthesis did not finish in 15 minutes"); continue
        fm = lambda x: f"{x['fmax']:6.1f}" if x.get("fmax") else "no fit"
        print(f"  {nb:3d} {k:2d} {r:3d} {p + 1:6d} {4 + p:7d} | {i['luts']:9d} {i['ffs']:5d} {i['cells'].get('SB_RAM40_4K', 0):4d} {fm(i):>6s} | {e['luts']:8d} {e['ffs']:5d} {e['cells'].get('DP16KD', 0):6d} {e['cells'].get('TRELLIS_DPR16X4', 0):7d} {fm(e):>6s}")
    print("\n== the end points of the critical path (nextpnr's last report for the clock)")
    for c in ((8, 2, 16, 0), (8, 2, 16, 1), (256, 4, 8, 1)):
        for fam in ("ice40", "ecp5"):
            if res[(c, fam)].get("timeout") or not res[(c, fam)].get("fmax"): continue
            a, b, (lg, rt) = crit(res[(c, fam)]["pnr_log"]); print(f"  NB {c[0]:3d} K {c[1]} R {c[2]:2d} PIPE {c[3]} {fam:6s} {a:24s} -> {b:24s} {lg} ns logic, {rt} ns routing")
