#!/usr/bin/env python3
"""Chapter 13, example A: what the send side costs. LUTs, flip-flops, block RAMs and Fmax (nextpnr seed 1, asked for 300 MHz) of one connection in registers and of 16 to 1,024 connections in a RAM with the timer scanner, on iCE40 and ECP5, with the end points of the critical path. Usage: ch13_example_a.py"""
import os, re, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import flow
CASES = [("tx_conn, 1 connection", "tx_conn_syn", None, 1)] + [(f"tx_tab, {1 << b} connections", "tx_tab_syn", {"CIDW": b}, 1 << b) for b in (4, 6, 8, 10)]
def job(a):
    k, fam = a; return a, flow.run(["rtl/tx.sv"], CASES[k][1], fam, 300, tag=f"t13_{k}_{fam}", params=CASES[k][2])
def crit(log):
    i = log.rfind("Critical path report for clock"); j = log.find("Setup", i); sec = log[i:j + 300]; src = re.findall(r"Source (\S+)", sec); snk = re.findall(r"Sink (\S+)", sec); tl = re.search(r"([\d.]+) ns logic, ([\d.]+) ns routing", sec)
    nm = lambda x: re.sub(r"_(SB_|TRELLIS_|LUT4|CCU2C|PFUMX|L6MUX|RAM)\S*", "", re.sub(r"\.\d+\.\d+(_RAM)?", "", x)); return nm(src[0]), nm(snk[-1]), tl.groups() if tl else ("?", "?")
if __name__ == "__main__":
    with cf.ThreadPoolExecutor(4) as ex: res = dict(ex.map(job, [(k, f) for k in range(len(CASES)) for f in ("ice40", "ecp5")]))
    print("== resources and clock (Yosys + nextpnr, seed 1, asked for 300 MHz), behind the pin wrapper (the 64-bit event shifted in serially, a 32-bit time counter, an output register); RAM = SB_RAM40_4K (iCE40) or DP16KD (ECP5)")
    print(f"  {'design':26s} | {'iCE40 LUT':>9s} {'FF':>5s} {'RAM':>4s} {'Fmax':>6s} | {'ECP5 LUT':>8s} {'CCU2C':>5s} {'FF':>5s} {'RAM':>4s} {'Fmax':>6s}")
    for k, c in enumerate(CASES):
        i, e = res[(k, "ice40")], res[(k, "ecp5")]
        left = f"{i['luts']:9d} {i['ffs']:5d} {i['cells'].get('SB_RAM40_4K', 0):4d} {i['fmax']:6.1f}" if i.get("fmax") else f"{'does not fit the iCE40 HX8K (131,072 bits of block RAM)':>26s}"
        right = f"{e['luts']:8d} {e['carry']:5d} {e['ffs']:5d} {e['cells'].get('DP16KD', 0):4d} {e['fmax']:6.1f}" if e.get("fmax") else "n/a"
        print(f"  {c[0]:26s} | {left} | {right}")
    print("  the state of one connection is 339 bits (ten 32-bit numbers, the 16-bit window, three flags); 1,024 connections = 347,136 bits")
    print("\n== the end points of each critical path (nextpnr's last report for the clock)")
    for k in (0, 2):
        for fam in ("ice40", "ecp5"):
            s_, t_, (lg, rt) = crit(res[(k, fam)]["pnr_log"]); print(f"  {CASES[k][0]:26s} {fam:6s} {s_:26s} -> {t_:30s} {lg} ns logic, {rt} ns routing")
