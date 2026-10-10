#!/usr/bin/env python3
"""Chapter 22, example A: what the signal unit costs and how fast it runs, and what a DSP block buys. sig behind its pin wrapper (the message shifted in serially, outputs registered and folded) for several formats (PW price bits, QW share bits, F fraction bits) and both dividers (DIV 1 pipelined, DIV 0 shared), synthesised and placed for iCE40 (the HX8K has NO DSP blocks: the multiplication is LUTs), for ECP5 with DSP blocks allowed, and for ECP5 with them forbidden (Yosys `synth_ecp5 -nodsp`), nextpnr seed 1, asked for 300 MHz."""
import os, re, subprocess, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import flow
flow.SYN["ecp5nodsp"] = "synth_ecp5 -nodsp -top {top} -json {json}"; flow.DEV["ecp5nodsp"] = flow.DEV["ecp5"]; flow.LUTS["ecp5nodsp"] = flow.LUTS["ecp5"]; flow.FFS["ecp5nodsp"] = flow.FFS["ecp5"]; flow.CARRY["ecp5nodsp"] = flow.CARRY["ecp5"]
CASES = [(24, 20, 12, 1), (24, 20, 12, 0), (24, 20, 8, 1), (24, 20, 16, 1), (16, 12, 8, 1), (32, 24, 16, 1), (32, 24, 16, 0)]
FAMS = ("ice40", "ecp5", "ecp5nodsp")
def crit(log):
    i = log.rfind("Critical path report for clock"); j = log.find("Setup", i); sec = log[i:j + 300]; src = re.findall(r"Source (\S+)", sec); snk = re.findall(r"Sink (\S+)", sec); tl = re.search(r"([\d.]+) ns logic, ([\d.]+) ns routing", sec)
    nm = lambda x: re.sub(r"_(SB_|TRELLIS_|LUT4|CCU2C|PFUMX|L6MUX|RAM)\S*", "", re.sub(r"\.\d+\.\d+(_RAM)?", "", x)); return nm(src[0]), nm(snk[-1]), tl.groups() if tl else ("?", "?")
def job(a):
    (pw, qw, f, div), fam = a
    try: return a, flow.run(["rtl/sig.sv"], "sig_syn", fam, 300, tag=f"t22_{pw}_{qw}_{f}_{div}_{fam}", params={"PW": pw, "QW": qw, "F": f, "DIV": div})
    except subprocess.TimeoutExpired: return a, {"timeout": True}
if __name__ == "__main__":
    with cf.ThreadPoolExecutor(4) as ex: res = dict(ex.map(job, [(c, fam) for c in CASES for fam in FAMS]))
    print("== resources and clock (Yosys + nextpnr, seed 1, asked for 300 MHz), behind the pin wrapper")
    print(f"  {'PW':>3s} {'QW':>3s} {'F':>3s} {'DIV':>3s} {'latency':>7s} | {'iCE40 LUT':>9s} {'FF':>5s} {'Fmax':>6s} | {'ECP5 LUT':>8s} {'FF':>5s} {'MULT18':>6s} {'Fmax':>6s} | {'no-DSP LUT':>10s} {'Fmax':>6s}")
    for c in CASES:
        pw, qw, f, div = c; i, e, n = (res[(c, fam)] for fam in FAMS)
        if any(x.get("timeout") for x in (i, e, n)): print(f"  {pw:3d} {qw:3d} {f:3d} {div:3d} {f + 4:7d} | synthesis did not finish in 15 minutes"); continue
        fm = lambda x: f"{x['fmax']:6.1f}" if x.get("fmax") else "no fit"
        print(f"  {pw:3d} {qw:3d} {f:3d} {div:3d} {f + 4:7d} | {i['luts']:9d} {i['ffs']:5d} {fm(i):>6s} | {e['luts']:8d} {e['ffs']:5d} {e['cells'].get('MULT18X18D', 0):6d} {fm(e):>6s} | {n['luts']:10d} {fm(n):>6s}")
    print("\n== the end points of the critical path (nextpnr's last report for the clock)")
    for c in ((24, 20, 12, 1), (24, 20, 12, 0), (32, 24, 16, 1)):
        for fam in FAMS:
            if res[(c, fam)].get("timeout") or not res[(c, fam)].get("fmax"): continue
            a, b, (lg, rt) = crit(res[(c, fam)]["pnr_log"]); print(f"  PW {c[0]} QW {c[1]} F {c[2]:2d} DIV {c[3]} {fam:10s} {a:22s} -> {b:22s} {lg} ns logic, {rt} ns routing")
