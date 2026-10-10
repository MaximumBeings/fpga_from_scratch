#!/usr/bin/env python3
"""Chapter 24, example A: what the order-entry transmitter costs and how fast it runs. sess behind its pin wrapper (the inputs shifted in serially, outputs registered and folded) for the beat width W (1, 2, 4 and 8 bytes) and the number of symbols NS (4 and 15), synthesised and placed for iCE40 and ECP5 (nextpnr seed 1, asked for 300 MHz). The packet is assembled in one cycle whatever W; W changes how many cycles it takes to leave."""
import os, re, subprocess, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import flow
CASES = [(1, 4, 20, 60), (2, 4, 20, 60), (4, 4, 20, 60), (8, 4, 20, 60), (8, 15, 20, 60)]
def crit(log):
    i = log.rfind("Critical path report for clock"); j = log.find("Setup", i); sec = log[i:j + 300]; src = re.findall(r"Source (\S+)", sec); snk = re.findall(r"Sink (\S+)", sec); tl = re.search(r"([\d.]+) ns logic, ([\d.]+) ns routing", sec)
    nm = lambda x: re.sub(r"_(SB_|TRELLIS_|LUT4|CCU2C|PFUMX|L6MUX|RAM)\S*", "", re.sub(r"\.\d+\.\d+(_RAM)?", "", x)); return nm(src[0]), nm(snk[-1]), tl.groups() if tl else ("?", "?")
def job(a):
    (w, ns, hb, tl), fam = a
    try: return a, flow.run(["rtl/sess.sv"], "sess_syn", fam, 300, tag=f"t24_{w}_{ns}_{fam}", params={"W": w, "NS": ns, "HB": hb, "TL": tl})
    except subprocess.TimeoutExpired: return a, {"timeout": True}
if __name__ == "__main__":
    with cf.ThreadPoolExecutor(4) as ex: res = dict(ex.map(job, [(c, f) for c in CASES for f in ("ice40", "ecp5")]))
    print("== resources and clock (Yosys + nextpnr, seed 1, asked for 300 MHz), behind the pin wrapper")
    print(f"  {'W':>2s} {'NS':>3s} | {'iCE40 LUT':>9s} {'FF':>5s} {'Fmax':>6s} | {'ECP5 LUT':>8s} {'FF':>5s} {'Fmax':>6s}")
    for c in CASES:
        w, ns, hb, tl = c; i, e = res[(c, "ice40")], res[(c, "ecp5")]
        if i.get("timeout") or e.get("timeout"): print(f"  {w:2d} {ns:3d} | synthesis did not finish in 15 minutes"); continue
        fm = lambda x: f"{x['fmax']:6.1f}" if x.get("fmax") else "no fit"
        print(f"  {w:2d} {ns:3d} | {i['luts']:9d} {i['ffs']:5d} {fm(i):>6s} | {e['luts']:8d} {e['ffs']:5d} {fm(e):>6s}")
    print("\n== the end points of the critical path (nextpnr's last report for the clock)")
    for c in ((1, 4, 20, 60), (8, 4, 20, 60), (8, 15, 20, 60)):
        for fam in ("ice40", "ecp5"):
            if res[(c, fam)].get("timeout") or not res[(c, fam)].get("fmax"): continue
            a, b, (lg, rt) = crit(res[(c, fam)]["pnr_log"]); print(f"  W {c[0]} NS {c[1]:2d} {fam:6s} {a:24s} -> {b:24s} {lg} ns logic, {rt} ns routing")
