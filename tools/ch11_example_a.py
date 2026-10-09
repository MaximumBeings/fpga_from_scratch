#!/usr/bin/env python3
"""Chapter 11, example A: store-and-forward against cut-through. (1) resources and Fmax (nextpnr seed 1, asked for 300 MHz) of the two builders with and without the pacer, behind the pin wrapper, iCE40 and ECP5; (2) latency: one packet alone, payload length L, from the first payload byte accepted to the first wire byte (preamble); (3) throughput: 20 packets of the same length back to back from a source that never stalls, link utilisation = wire cost / cycles per packet. Usage: ch11_example_a.py"""
import os, re, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, udp_gold as g, ch11_run as r
F = ["rtl/crc32_stream.sv", "rtl/mac.sv", "rtl/udp.sv"]
CASES = [("store-and-forward", {"CT": 0, "PACE": 0}), ("store-and-forward + pacer", {"CT": 0, "PACE": 1}), ("cut-through", {"CT": 1, "PACE": 0}), ("cut-through + pacer", {"CT": 1, "PACE": 1}), ("cut-through + first pacer", {"CT": 1, "PACE": 2})]
def job(a):
    k, fam = a; return a, flow.run(F, "udp_tx_syn", fam, 300, tag=f"u11_{k}_{fam}", params=CASES[k][1])
if __name__ == "__main__":
    with cf.ThreadPoolExecutor(4) as ex: res = dict(ex.map(job, [(k, f) for k in range(len(CASES)) for f in ("ice40", "ecp5")]))
    print("== resources and clock (Yosys + nextpnr, seed 1, asked for 300 MHz): builder + optional pacer + mac_tx, behind the pin wrapper (212 configuration flip-flops and an output register); RAM = SB_RAM40_4K (iCE40) or DP16KD (ECP5)")
    print(f"  {'design':28s} | {'iCE40 LUT':>9s} {'FF':>5s} {'RAM':>4s} {'Fmax':>6s} | {'ECP5 LUT':>8s} {'CCU2C':>5s} {'FF':>5s} {'RAM':>4s} {'Fmax':>6s}")
    for k, (nm, _) in enumerate(CASES):
        i, e = res[(k, "ice40")], res[(k, "ecp5")]
        print(f"  {nm:28s} | {i['luts']:9d} {i['ffs']:5d} {i['cells'].get('SB_RAM40_4K', 0):4d} {i['fmax']:6.1f} | {e['luts']:8d} {e['carry']:5d} {e['ffs']:5d} {e['cells'].get('DP16KD', 0):4d} {e['fmax']:6.1f}")
    print("  a byte per clock at 1 Gbit/s needs 125 MHz")
    print("\n== latency of one packet alone: cycles from the descriptor accepted to the first wire byte (the preamble) and to the last wire byte; no other traffic, source at 100%, no pacer")
    print(f"  {'payload L':>9s} | {'store-and-forward: first':>25s} {'minus L':>8s} {'last':>6s} | {'cut-through: first':>19s} {'last':>6s}")
    for L in (1, 18, 100, 500, 1000, 1472):
        q = [dict(payload=(bytes(range(256)) * 6)[:L], dport=5000, dip=0x0A000002)]; row = []
        for ct in (0, 1):
            o = r.run(q, ct); d0 = int(re.search(r"FIRSTD (\d+)", o).group(1)); row.append((r.starts(o)[0] - d0, int(re.search(r"END (\d+)", o).group(1)) - d0))
        print(f"  {L:9d} | {row[0][0]:25d} {row[0][0] - L:8d} {row[0][1]:6d} | {row[1][0]:19d} {row[1][1]:6d}")
    print("  first = descriptor accepted to the first preamble byte on the wire; last = to the last FCS byte. The store-and-forward builder must have the whole payload and both checksums before it can start; the cut-through builder needs only the length.")
    print("\n== throughput: 20 packets of the same payload length, one after another, source and descriptors never stall, no pacer; utilisation = wire bytes (cost) / (cycles per packet)")
    print(f"  {'payload L':>9s} {'wire cost':>9s} | {'store-and-forward':>18s} {'utilisation':>12s} | {'cut-through':>12s} {'utilisation':>12s}")
    for L in (18, 100, 500, 1000, 1472):
        q = [dict(payload=bytes((i * 7 + j) & 255 for j in range(L)), dport=5000, dip=0x0A000002) for i in range(20)]; cost = g.wire_cost(L); row = []
        for ct in (0, 1):
            o = r.run(q, ct); st = r.starts(o); per = (st[-1] - st[0]) / (len(st) - 1); row.append((per, cost / per))
        print(f"  {L:9d} {cost:9d} | {row[0][0]:14.1f} cyc {row[0][1] * 100:10.1f}% | {row[1][0]:8.1f} cyc {row[1][1] * 100:10.1f}%")
