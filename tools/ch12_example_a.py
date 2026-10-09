#!/usr/bin/env python3
"""Chapter 12, example A: what the TCP state machine costs, and the staircase of clocks. LUTs, flip-flops, block RAMs and Fmax (nextpnr seed 1, asked for 300 MHz) of the first design (the whole machine in one cycle: one connection in registers; 64 connections in a RAM with a bypass), of the second design in 3 and 4 stages, of the second design at 16 to 1,024 connections, and of the hot path alone, on iCE40 and ECP5; with the end points of each critical path. Usage: ch12_example_a.py"""
import os, re, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import flow
F = ["rtl/tcp.sv"]
CASES = [("tcp_conn, one cycle, 1 connection", "tcp_conn_syn", None, 1), ("tcp_tab, 2 stages, 64 connections", "tcp_tab_syn", {"CIDW": 6, "V2": 0}, 64), ("tcp_tab2, 3 stages, 64 connections", "tcp_tab_syn", {"CIDW": 6, "V2": 1}, 64), ("tcp_tab2, 4 stages, 64 connections", "tcp_tab_syn", {"CIDW": 6, "V2": 2}, 64),
         ("tcp_tab2, 4 stages, 16 connections", "tcp_tab_syn", {"CIDW": 4, "V2": 2}, 16), ("tcp_tab2, 4 stages, 256 connections", "tcp_tab_syn", {"CIDW": 8, "V2": 2}, 256), ("tcp_tab2, 4 stages, 1024 connections", "tcp_tab_syn", {"CIDW": 10, "V2": 2}, 1024), ("tcp_fast, the hot path alone", "tcp_fast_syn", None, 0)]
def job(a):
    k, fam = a; return a, flow.run(F, CASES[k][1], fam, 300, tag=f"t12_{k}_{fam}", params=CASES[k][2])
def crit(log):
    i = log.rfind("Critical path report for clock"); j = log.find("Setup", i); sec = log[i:j + 300]; src = re.findall(r"Source (\S+)", sec); snk = re.findall(r"Sink (\S+)", sec); tl = re.search(r"([\d.]+) ns logic, ([\d.]+) ns routing", sec)
    nm = lambda x: re.sub(r"_(SB_|TRELLIS_|LUT4|CCU2C|PFUMX|L6MUX|RAM)\S*", "", re.sub(r"\.\d+\.\d+(_RAM)?", "", x)); return nm(src[0]), nm(snk[-1]), tl.groups() if tl else ("?", "?")
if __name__ == "__main__":
    with cf.ThreadPoolExecutor(4) as ex: res = dict(ex.map(job, [(k, f) for k in range(len(CASES)) for f in ("ice40", "ecp5")]))
    print("== resources and clock (Yosys + nextpnr, seed 1, asked for 300 MHz), behind the pin wrapper (the 148-bit event shifted in serially, an output register); RAM = SB_RAM40_4K (iCE40) or DP16KD (ECP5)")
    print(f"  {'design':38s} | {'iCE40 LUT':>9s} {'FF':>5s} {'RAM':>4s} {'Fmax':>6s} | {'ECP5 LUT':>8s} {'CCU2C':>5s} {'FF':>5s} {'RAM':>4s} {'Fmax':>6s}")
    for k, c in enumerate(CASES):
        i, e = res[(k, "ice40")], res[(k, "ecp5")]
        print(f"  {c[0]:38s} | {i['luts']:9d} {i['ffs']:5d} {i['cells'].get('SB_RAM40_4K', 0):4d} {i['fmax']:6.1f} | {e['luts']:8d} {e['carry']:5d} {e['ffs']:5d} {e['cells'].get('DP16KD', 0):4d} {e['fmax']:6.1f}")
    print("  the per-connection state is 101 bits (state 4, passive 1, SND.UNA, SND.NXT, RCV.NXT 32 each): 1,024 connections = 103,424 bits; a 125 MHz clock gives 125 million events per second (derived: one event per cycle), a connection that sees a segment every 10 microseconds needs 1,250 cycles per segment")
    print("\n== the end points of each critical path (nextpnr's last report for the clock)")
    for k in (0, 1, 2, 3, 7):
        for fam in ("ice40", "ecp5"):
            s_, t_, (lg, rt) = crit(res[(k, fam)]["pnr_log"]); print(f"  {CASES[k][0]:38s} {fam:6s} {s_:26s} -> {t_:30s} {lg} ns logic, {rt} ns routing")
