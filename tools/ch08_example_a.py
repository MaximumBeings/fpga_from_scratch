#!/usr/bin/env python3
"""Chapter 8, example A: what the MAC costs. LUTs, flip-flops, block RAMs and Fmax (nextpnr seed 1, asked for 300 MHz) of mac_rx, mac_tx, frame_fifo at 256 bytes and 2 KB, and the whole receive path (mac_rx + crossing FIFO + 2 KB frame buffer) and transmit path, on iCE40 and ECP5. The Gbit/s column is the byte rate the clock supports (derived: 8 bits x Fmax), against the 1 Gbit/s (125 MHz) that GMII needs. Usage: ch08_example_a.py"""
import os, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import flow
RX = ["rtl/crc32_stream.sv", "rtl/cdc_sync.sv", "rtl/cdc.sv", "rtl/mac.sv"]
CASES = [("mac_rx", "mac_rx", None), ("mac_tx", "mac_tx", None), ("frame_fifo 256 B", "frame_fifo", {"AW": 8}), ("frame_fifo 2 KB", "frame_fifo", {"AW": 11}), ("mac_rx_path (2 KB)", "mac_rx_path", {"AW": 11}), ("mac_tx_path (2 KB)", "mac_tx_path", {"AW": 11})]
import re
def clocks(log):
    """Final maximum frequency per clock domain, from the last report line of each clock (the log repeats them before and after routing)."""
    d = {}
    for name, f in re.findall(r"Max frequency for clock\s+'([^']*)': ([\d.]+) MHz", log): d[re.sub(r"\$.*", "", name.replace("$glbnet$", ""))] = float(f)
    return d
def job(a):
    k, fam = a; name, top, params = CASES[k]; tag = f"mac_{top}_{params['AW'] if params else 0}_{fam}"; r = flow.run(RX, top, fam, 300, tag=tag, params=params); r['clk'] = clocks(r['pnr_log']); return a, r
if __name__ == "__main__":
    with cf.ThreadPoolExecutor(4) as ex: res = dict(ex.map(job, [(k, f) for k in range(len(CASES)) for f in ("ice40", "ecp5")]))
    print("== resources and clock of the MAC pieces (Yosys + nextpnr, seed 1, asked for 300 MHz); 'RAM' = SB_RAM40_4K (iCE40, 4 kbit) or DP16KD (ECP5, 18 kbit); Fmax = the SLOWEST clock domain of the module")
    print(f"  {'module':22s} | {'iCE40 LUT':>9s} {'FF':>5s} {'RAM':>4s} {'Fmax MHz':>9s} | {'ECP5 LUT':>8s} {'FF':>5s} {'RAM':>4s} {'Fmax MHz':>9s}")
    for k, c in enumerate(CASES):
        i, e = res[(k, "ice40")], res[(k, "ecp5")]; ri = i["cells"].get("SB_RAM40_4K", 0); re_ = e["cells"].get("DP16KD", 0)
        print(f"  {c[0]:22s} | {i['luts']:9d} {i['ffs']:5d} {ri:4d} {min(i['clk'].values()):9.1f} | {e['luts']:8d} {e['ffs']:5d} {re_:4d} {min(e['clk'].values()):9.1f}")
    print("\n  per clock domain of the receive path (mac_rx_path, 2 KB buffer):")
    for fam in ("ice40", "ecp5"): print(f"    {fam}: " + ", ".join(f"{k} {v:.1f} MHz" for k, v in sorted(res[(4, fam)]['clk'].items())))
    print("  GMII at 1 Gbit/s needs 125 MHz (one byte per clock); a 64-bit 10GbE datapath needs 156.25 MHz. Compare the Fmax column with those.")
