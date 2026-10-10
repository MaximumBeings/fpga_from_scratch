#!/usr/bin/env python3
"""Chapter 19, example A: what the book costs. book behind its pin wrapper (the 140-bit event shifted in serially, outputs registered and folded) for several sizes, synthesised and placed for iCE40 and ECP5 (nextpnr seed 1, asked for 300 MHz). Three sweeps around NS = 2, D = 4, NO = 16 (the iCE40 HX8K has 7,680 logic cells: a design that does not fit is reported as such): the number of levels per side D, the order table NO, and the number of symbols NS. Everything is registers (no RAM)."""
import os, re, subprocess, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import flow
CASES = [(2, 2, 16), (2, 4, 16), (2, 8, 16), (2, 4, 8), (2, 4, 32), (1, 4, 16), (4, 4, 16)]
def crit(log):
    i = log.rfind("Critical path report for clock"); j = log.find("Setup", i); sec = log[i:j + 300]; src = re.findall(r"Source (\S+)", sec); snk = re.findall(r"Sink (\S+)", sec); tl = re.search(r"([\d.]+) ns logic, ([\d.]+) ns routing", sec)
    nm = lambda x: re.sub(r"_(SB_|TRELLIS_|LUT4|CCU2C|PFUMX|L6MUX|RAM)\S*", "", re.sub(r"\.\d+\.\d+(_RAM)?", "", x)); return nm(src[0]), nm(snk[-1]), tl.groups() if tl else ("?", "?")
def job(a):
    (ns, d, no), fam = a
    try: return a, flow.run(["rtl/book.sv"], "book_syn", fam, 300, tag=f"t19_{ns}_{d}_{no}_{fam}", params={"NS": ns, "D": d, "NO": no})
    except subprocess.TimeoutExpired: return a, {"timeout": True}
if __name__ == "__main__":
    with cf.ThreadPoolExecutor(4) as ex: res = dict(ex.map(job, [(c, f) for c in CASES for f in ("ice40", "ecp5")]))
    print("== resources and clock (Yosys + nextpnr, seed 1, asked for 300 MHz), behind the pin wrapper; the book is registers only")
    print(f"  {'NS':>2s} {'D':>3s} {'NO':>3s} | {'iCE40 LUT':>9s} {'FF':>6s} {'Fmax':>6s} | {'ECP5 LUT':>8s} {'CCU2C':>5s} {'FF':>6s} {'Fmax':>6s} | {'bits of state':>13s}")
    for c in CASES:
        ns, d, no = c; i, e = res[(c, "ice40")], res[(c, "ecp5")]; bits = no * (1 + 32 + max(1, (ns - 1).bit_length()) + 1 + 32 + 32) + ns * 2 * d * (1 + 32 + 32)
        if i.get("timeout") or e.get("timeout"): print(f"  {ns:2d} {d:3d} {no:3d} | synthesis did not finish in 15 minutes {'':>30s} | {bits:13d}"); continue
        fm = lambda r: f"{r['fmax']:6.1f}" if r.get("fmax") else "no fit"
        print(f"  {ns:2d} {d:3d} {no:3d} | {i['luts']:9d} {i['ffs']:6d} {fm(i):>6s} | {e['luts']:8d} {e['carry']:5d} {e['ffs']:6d} {fm(e):>6s} | {bits:13d}")
    print("\n== the end points of the critical path (nextpnr's last report for the clock)")
    for c in ((2, 4, 16), (2, 8, 16), (2, 4, 32)):
        for fam in ("ice40", "ecp5"):
            if res[(c, fam)].get("timeout") or not res[(c, fam)].get("fmax"): continue
            a, b, (lg, rt) = crit(res[(c, fam)]["pnr_log"]); print(f"  NS {c[0]} D {c[1]:2d} NO {c[2]:2d} {fam:6s} {a:22s} -> {b:22s} {lg} ns logic, {rt} ns routing")
