#!/usr/bin/env python3
"""Chapter 25, example A: what the order tracker and the joined design cost and how fast they run. track_syn (the tracker behind its pin wrapper: inputs shifted in serially, outputs registered and folded) for the table size NT = 2, 4, 8, 16, 32, and life_syn (gate + tracker + state machine) for NT = 4 and 16, synthesised and placed for iCE40 (HX8K) and ECP5 (nextpnr seed 1, asked for 300 MHz). The table is an array of registers whose 32-bit tokens are all compared at once, so its cost grows with NT."""
import os, re, subprocess, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import flow
CASES = [("track", 2), ("track", 4), ("track", 8), ("track", 16), ("track", 32), ("life", 4), ("life", 16)]
FILES = {"track": ["rtl/track.sv"], "life": ["rtl/risk.sv", "rtl/track.sv", "rtl/life.sv"]}
def crit(log):
    i = log.rfind("Critical path report for clock"); j = log.find("Setup", i); sec = log[i:j + 300]; src = re.findall(r"Source (\S+)", sec); snk = re.findall(r"Sink (\S+)", sec); tl = re.search(r"([\d.]+) ns logic, ([\d.]+) ns routing", sec)
    nm = lambda x: re.sub(r"_(SB_|TRELLIS_|LUT4|CCU2C|PFUMX|L6MUX|RAM)\S*", "", re.sub(r"\.\d+\.\d+(_RAM)?", "", x)); return nm(src[0]), nm(snk[-1]), tl.groups() if tl else ("?", "?")
def job(a):
    (top, nt), fam = a
    try: return a, flow.run(FILES[top], top + "_syn", fam, 300, tag=f"t25_{top}_{nt}_{fam}", params={"NT": nt})
    except subprocess.TimeoutExpired: return a, {"timeout": True}
if __name__ == "__main__":
    with cf.ThreadPoolExecutor(4) as ex: res = dict(ex.map(job, [(c, f) for c in CASES for f in ("ice40", "ecp5")]))
    print("== resources and clock (Yosys + nextpnr, seed 1, asked for 300 MHz), behind the pin wrapper")
    print(f"  {'design':6s} {'NT':>3s} | {'iCE40 LUT':>9s} {'FF':>5s} {'LCs':>5s} {'Fmax':>6s} | {'ECP5 LUT':>8s} {'FF':>5s} {'Fmax':>6s}")
    for c in CASES:
        i, e = res[(c, "ice40")], res[(c, "ecp5")]
        if i.get("timeout") or e.get("timeout"): print(f"  {c[0]:6s} {c[1]:3d} | synthesis did not finish in 15 minutes"); continue
        fm = lambda x: f"{x['fmax']:6.1f}" if x.get("fmax") else "no fit"
        print(f"  {c[0]:6s} {c[1]:3d} | {i['luts']:9d} {i['ffs']:5d} {str(i.get('lcs') or '-'):>5s} {fm(i):>6s} | {e['luts']:8d} {e['ffs']:5d} {fm(e):>6s}")
    print("\n== the end points of the critical path (nextpnr's last report for the clock)")
    for c in (("track", 4), ("track", 32), ("life", 4), ("life", 16)):
        for fam in ("ice40", "ecp5"):
            if res[(c, fam)].get("timeout") or not res[(c, fam)].get("fmax"): continue
            a, b, (lg, rt) = crit(res[(c, fam)]["pnr_log"]); print(f"  {c[0]} NT {c[1]:2d} {fam:6s} {a:24s} -> {b:24s} {lg} ns logic, {rt} ns routing")
