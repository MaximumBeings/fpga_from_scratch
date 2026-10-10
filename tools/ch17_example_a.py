#!/usr/bin/env python3
"""Chapter 17, example A: what W bytes per clock cost. The generated parser for W = 1 (Chapter 16's, behind its wrapper), 2, 4 and 8, in the version(s) given, synthesised and placed for iCE40 and ECP5 (nextpnr seed 1, asked for 300 MHz) behind the pin wrapper (inputs shifted in serially, outputs registered and folded into one 16-bit word). Throughput = bytes per clock x Fmax."""
import os, re, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import subprocess, flow, grammar, gen_parser as G1, gen_parser_wide as GW
VERS = [int(a) for a in sys.argv[1:] if a.isdigit()] or [1]
SKIP = {(8, 1), (8, 2)} if "--skip-known" in sys.argv else set()     # version 1 and 2 at W = 8 hit the 15-minute synthesis limit in the first run (recorded in the page); this skips repeating those two 30-minute runs
def text(W, v):
    if W == 1: return G1.gen(grammar.ITCH, "mold_w1")
    return {1: GW.gen, 2: GW.gen_pipe, 3: GW.gen_v3}[v](grammar.ITCH, f"mold_w{W}", W)
CASES = [(1, 1)] + [(W, v) for v in VERS for W in (2, 4, 8)]
def crit(log):
    i = log.rfind("Critical path report for clock"); j = log.find("Setup", i); sec = log[i:j + 300]; src = re.findall(r"Source (\S+)", sec); snk = re.findall(r"Sink (\S+)", sec); tl = re.search(r"([\d.]+) ns logic, ([\d.]+) ns routing", sec)
    nm = lambda x: re.sub(r"_(SB_|TRELLIS_|LUT4|CCU2C|PFUMX|L6MUX|RAM)\S*", "", re.sub(r"\.\d+\.\d+(_RAM)?", "", x)); return nm(src[0]), nm(snk[-1]), tl.groups() if tl else ("?", "?")
def job(a):
    (W, v), fam = a
    if (W, v) in SKIP: return a, {"timeout": True, "known": True}
    f = f"out/ex17_w{W}_v{v}.sv"; open(os.path.join(flow.ROOT, f), "w").write(text(W, v))
    try: return a, flow.run([f], f"mold_w{W}_syn", fam, 300, tag=f"t17_{W}_{v}_{fam}")
    except subprocess.TimeoutExpired: return a, {"timeout": True}                          # the tool flow gives synthesis 15 minutes
if __name__ == "__main__":
    with cf.ThreadPoolExecutor(4) as ex: res = dict(ex.map(job, [(c, f) for c in CASES for f in ("ice40", "ecp5")]))
    print("== resources, clock and throughput (Yosys + nextpnr, seed 1, asked for 300 MHz), behind the pin wrapper; throughput = W x Fmax")
    print(f"  {'W':>2s} {'version':>7s} | {'iCE40 LUT':>9s} {'FF':>5s} {'Fmax':>6s} {'Gbit/s':>7s} | {'ECP5 LUT':>8s} {'FF':>5s} {'Fmax':>6s} {'Gbit/s':>7s}")
    for c in CASES:
        i, e = res[(c, "ice40")], res[(c, "ecp5")]; W = c[0]
        if i.get("timeout") or e.get("timeout"): print(f"  {W:2d} {c[1]:7d} | synthesis did not finish in 15 minutes (iCE40 and ECP5)"); continue
        print(f"  {W:2d} {c[1]:7d} | {i['luts']:9d} {i['ffs']:5d} {i['fmax']:6.1f} {i['fmax'] * W * 8 / 1000:7.2f} | {e['luts']:8d} {e['ffs']:5d} {e['fmax']:6.1f} {e['fmax'] * W * 8 / 1000:7.2f}")
    print("\n== the end points of each critical path (nextpnr's last report for the clock)")
    for c in CASES:
        for fam in ("ice40", "ecp5"):
            if res[(c, fam)].get("timeout"): continue
            a, b, (lg, rt) = crit(res[(c, fam)]["pnr_log"]); print(f"  W = {c[0]} v{c[1]} {fam:6s} {a:22s} -> {b:22s} {lg} ns logic, {rt} ns routing")
