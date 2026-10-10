#!/usr/bin/env python3
"""Chapter 18, example A: what the window costs. seq_arb behind its pin wrapper (the 51-bit input shifted in serially, outputs folded into one registered 16-bit word) for 1 to 16 pending slots, version 1 (rtl/seq_arb_v1.sv: every slot's distance from the expected number recomputed in every cycle) version 2 (rtl/seq_arb_v2.sv: the distance is stored and reduced when the expected number advances) and version 3 (rtl/seq_arb.sv: as 2, the minimum taken with a tree of comparators instead of a chain), synthesised and placed for iCE40 and ECP5 (nextpnr seed 1, asked for 300 MHz). The slots are registers (no RAM): each adds a 32-bit comparator against the expected number (for the release and for the minimum), one against the incoming number (for duplicates) and 50 bits of storage."""
import os, re, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import flow
SIZES = (1, 2, 4, 8, 16)
VERS = {1: "rtl/seq_arb_v1.sv", 2: "rtl/seq_arb_v2.sv", 3: "rtl/seq_arb.sv"}
def crit(log):
    i = log.rfind("Critical path report for clock"); j = log.find("Setup", i); sec = log[i:j + 300]; src = re.findall(r"Source (\S+)", sec); snk = re.findall(r"Sink (\S+)", sec); tl = re.search(r"([\d.]+) ns logic, ([\d.]+) ns routing", sec)
    nm = lambda x: re.sub(r"_(SB_|TRELLIS_|LUT4|CCU2C|PFUMX|L6MUX|RAM)\S*", "", re.sub(r"\.\d+\.\d+(_RAM)?", "", x)); return nm(src[0]), nm(snk[-1]), tl.groups() if tl else ("?", "?")
def job(a):
    (v, n), fam = a; return a, flow.run([VERS[v]], "seq_arb_syn", fam, 300, tag=f"t18_{v}_{n}_{fam}", params={"PEND": n})
if __name__ == "__main__":
    with cf.ThreadPoolExecutor(4) as ex: res = dict(ex.map(job, [((v, n), f) for v in (1, 2, 3) for n in SIZES for f in ("ice40", "ecp5")]))
    print("== resources and clock (Yosys + nextpnr, seed 1, asked for 300 MHz), behind the pin wrapper")
    print(f"  {'version':>7s} {'PEND':>4s} | {'iCE40 LUT':>9s} {'FF':>5s} {'Fmax':>6s} | {'ECP5 LUT':>8s} {'CCU2C':>5s} {'FF':>5s} {'Fmax':>6s}")
    for v in (1, 2, 3):
        for n in SIZES:
            i, e = res[((v, n), "ice40")], res[((v, n), "ecp5")]
            print(f"  {v:7d} {n:4d} | {i['luts']:9d} {i['ffs']:5d} {i['fmax']:6.1f} | {e['luts']:8d} {e['carry']:5d} {e['ffs']:5d} {e['fmax']:6.1f}")
    print("\n== the end points of the critical path (nextpnr's last report for the clock)")
    for v in (1, 2, 3):
        for n in (1, 4, 16):
            for fam in ("ice40", "ecp5"):
                a, b, (lg, rt) = crit(res[((v, n), fam)]["pnr_log"]); print(f"  version {v} PEND = {n:2d} {fam:6s} {a:20s} -> {b:20s} {lg} ns logic, {rt} ns routing")
