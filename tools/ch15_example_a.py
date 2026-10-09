#!/usr/bin/env python3
"""Chapter 15, example A: what the split costs. LUTs, flip-flops, block RAMs and Fmax (nextpnr seed 1, asked for 300 MHz) of tcp_split behind the pin wrapper (the inputs, about 270 bits, shifted in serially; the outputs folded into one registered 16-bit word) for 4 to 16 connections and punt FIFOs of 4 and 8 entries, against the hot path alone (tcp_fast_syn of Chapter 12), on iCE40 and ECP5."""
import os, re, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import flow
CASES = [("tcp_fast alone (Chapter 12)", "tcp_fast_syn", None, ["rtl/tcp.sv"])] + [(f"tcp_split, {1 << b} connections, FIFO {d}", "tcp_split_syn", {"CIDW": b, "DEPTH": d}, ["rtl/split.sv", "rtl/tcp.sv"]) for b, d in ((2, 4), (3, 4), (4, 4), (3, 8))]
def job(a):
    k, fam = a; return a, flow.run(CASES[k][3], CASES[k][1], fam, 300, tag=f"t15_{k}_{fam}", params=CASES[k][2])
def crit(log):
    i = log.rfind("Critical path report for clock"); j = log.find("Setup", i); sec = log[i:j + 300]; src = re.findall(r"Source (\S+)", sec); snk = re.findall(r"Sink (\S+)", sec); tl = re.search(r"([\d.]+) ns logic, ([\d.]+) ns routing", sec)
    nm = lambda x: re.sub(r"_(SB_|TRELLIS_|LUT4|CCU2C|PFUMX|L6MUX|RAM)\S*", "", re.sub(r"\.\d+\.\d+(_RAM)?", "", x)); return nm(src[0]), nm(snk[-1]), tl.groups() if tl else ("?", "?")
if __name__ == "__main__":
    with cf.ThreadPoolExecutor(4) as ex: res = dict(ex.map(job, [(k, f) for k in range(len(CASES)) for f in ("ice40", "ecp5")]))
    print("== resources and clock (Yosys + nextpnr, seed 1, asked for 300 MHz), behind the pin wrapper; RAM = SB_RAM40_4K (iCE40) or DP16KD (ECP5)")
    print(f"  {'design':36s} | {'iCE40 LUT':>9s} {'FF':>5s} {'RAM':>4s} {'Fmax':>6s} | {'ECP5 LUT':>8s} {'CCU2C':>5s} {'FF':>5s} {'RAM':>4s} {'Fmax':>6s}")
    for k, c in enumerate(CASES):
        i, e = res[(k, "ice40")], res[(k, "ecp5")]
        left = f"{i['luts']:9d} {i['ffs']:5d} {i['cells'].get('SB_RAM40_4K', 0):4d} {i['fmax']:6.1f}" if i.get("fmax") else f"{'does not fit':>26s}"
        right = f"{e['luts']:8d} {e['carry']:5d} {e['ffs']:5d} {e['cells'].get('DP16KD', 0):4d} {e['fmax']:6.1f}" if e.get("fmax") else "n/a"
        print(f"  {c[0]:36s} | {left} | {right}")
    print("  the state of one connection in tcp_split: 4 + 1 + 3 x 32 + 4 = 105 bits in registers; one punt entry: CIDW + 237 bits")
    print("\n== the end points of each critical path (nextpnr's last report for the clock)")
    for k in (0, 2):
        for fam in ("ice40", "ecp5"):
            s_, t_, (lg, rt) = crit(res[(k, fam)]["pnr_log"]); print(f"  {CASES[k][0]:36s} {fam:6s} {s_:26s} -> {t_:30s} {lg} ns logic, {rt} ns routing")
