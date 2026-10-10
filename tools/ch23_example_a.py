#!/usr/bin/env python3
"""Chapter 23, example A: what the risk gate costs and how fast it runs. risk behind its pin wrapper (the inputs shifted in serially, outputs registered and folded) for several sizes (NA accounts, NS symbols, QW quantity bits, PW price bits), synthesised and placed for iCE40 (the HX8K has 7,680 logic cells and NO DSP blocks: a design that does not fit is reported as such), for ECP5 with DSP blocks and for ECP5 with them forbidden (`synth_ecp5 -nodsp`), nextpnr seed 1, asked for 300 MHz. All the state is registers (position, open buys, open sells per account and symbol; notional and tokens per account): this is the cost of a gate that decides in one cycle with no RAM."""
import os, re, subprocess, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import flow
flow.SYN["ecp5nodsp"] = "synth_ecp5 -nodsp -top {top} -json {json}"; flow.DEV["ecp5nodsp"] = flow.DEV["ecp5"]; flow.LUTS["ecp5nodsp"] = flow.LUTS["ecp5"]; flow.FFS["ecp5nodsp"] = flow.FFS["ecp5"]; flow.CARRY["ecp5nodsp"] = flow.CARRY["ecp5"]
CASES = [(2, 2, 16, 16), (4, 4, 16, 16), (8, 4, 16, 16), (8, 8, 16, 16), (12, 12, 16, 16), (8, 8, 8, 8), (12, 12, 8, 8)]
FAMS = ("ice40", "ecp5", "ecp5nodsp")
def crit(log):
    i = log.rfind("Critical path report for clock"); j = log.find("Setup", i); sec = log[i:j + 300]; src = re.findall(r"Source (\S+)", sec); snk = re.findall(r"Sink (\S+)", sec); tl = re.search(r"([\d.]+) ns logic, ([\d.]+) ns routing", sec)
    nm = lambda x: re.sub(r"_(SB_|TRELLIS_|LUT4|CCU2C|PFUMX|L6MUX|RAM)\S*", "", re.sub(r"\.\d+\.\d+(_RAM)?", "", x)); return nm(src[0]), nm(snk[-1]), tl.groups() if tl else ("?", "?")
def job(a):
    (na, ns, qw, pw), fam = a
    try: return a, flow.run(["rtl/risk.sv"], "risk_syn", fam, 300, tag=f"t23_{na}_{ns}_{qw}_{pw}_{fam}", params={"NA": na, "NS": ns, "QW": qw, "PW": pw})
    except subprocess.TimeoutExpired: return a, {"timeout": True}
if __name__ == "__main__":
    with cf.ThreadPoolExecutor(3) as ex: res = dict(ex.map(job, [(c, fam) for c in CASES for fam in FAMS]))
    print("== resources and clock (Yosys + nextpnr, seed 1, asked for 300 MHz), behind the pin wrapper")
    print(f"  {'NA':>3s} {'NS':>3s} {'QW':>3s} {'PW':>3s} {'state bits':>10s} | {'iCE40 LUT':>9s} {'FF':>6s} {'Fmax':>7s} | {'ECP5 LUT':>8s} {'FF':>6s} {'MULT18':>6s} {'Fmax':>6s} | {'no-DSP LUT':>10s} {'Fmax':>6s}")
    for c in CASES:
        na, ns, qw, pw = c; i, e, n = (res[(c, fam)] for fam in FAMS); bits = na * ns * (3 * qw + 2) + na * (pw + qw + 2 + 8) + 2
        if any(x.get("timeout") for x in (i, e, n)): print(f"  {na:3d} {ns:3d} {qw:3d} {pw:3d} {bits:10d} | synthesis did not finish in 15 minutes"); continue
        fm = lambda x: f"{x['fmax']:6.1f}" if x.get("fmax") else "no fit"
        print(f"  {na:3d} {ns:3d} {qw:3d} {pw:3d} {bits:10d} | {i['luts']:9d} {i['ffs']:6d} {fm(i):>7s} | {e['luts']:8d} {e['ffs']:6d} {e['cells'].get('MULT18X18D', 0):6d} {fm(e):>6s} | {n['luts']:10d} {fm(n):>6s}")
    print("\n== the end points of the critical path (nextpnr's last report for the clock)")
    for c in ((4, 4, 16, 16), (8, 8, 16, 16)):
        for fam in FAMS:
            if res[(c, fam)].get("timeout") or not res[(c, fam)].get("fmax"): continue
            a, b, (lg, rt) = crit(res[(c, fam)]["pnr_log"]); print(f"  NA {c[0]:2d} NS {c[1]:2d} QW {c[2]:2d} {fam:10s} {a:24s} -> {b:24s} {lg} ns logic, {rt} ns routing")
