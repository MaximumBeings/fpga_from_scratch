#!/usr/bin/env python3
"""Chapter 8, example B: how slow may the core clock be? The PHY delivers a byte every 8,000 ps and cannot be stalled; the core drains the clock-crossing FIFO at one byte per core clock.
DERIVED, two conditions. (a) Within one frame the FIFO must not overflow: the pile-up of the frame's n data bytes, n x (1 - PHY period / core period), is below the depth, i.e. core period < PHY period / (1 - depth / n). (b) Over many back-to-back frames the core must keep up on average: the n data bytes plus the preamble, SFD, FCS and the 12-byte gap (n + 24 byte times in all) must be drained in the time they take to arrive, i.e. core period <= PHY period x (n + 24) / n.
MEASURED: 60 back-to-back maximum frames (1,518 bytes, minimum gap) at core periods from 6,400 to 8,400 ps, crossing FIFO depths 16 and 64: frames delivered, bytes lost, and whether anything delivered was corrupt. Usage: ch08_example_b.py"""
import os, random, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, mac_gold as g
F = ["rtl/crc32_stream.sv", "rtl/cdc_sync.sv", "rtl/cdc.sv", "rtl/mac.sv", "tb/mac_path_tb.sv"]
def subseq(got, exp):
    it = iter(exp); return all(any(x == y for y in it) for x in got)
def main():
    rng = random.Random(4); items = [{"kind": "good", "body": bytes(rng.getrandbits(8) for _ in range(1514)), "gap": g.IFG} for _ in range(60)]
    st = g.phy_stream(items); g.write_stream(os.path.join(flow.ROOT, "out", "mac_stream.hex"), st); good = [p for p, b in g.spec_rx(st) if not b]; n = 1514
    print("== 60 back-to-back frames of 1,518 bytes (preamble and SFD before, minimum 12-byte gap after); PHY clock 8,000 ps; the crossing FIFO is 16 or 64 bytes deep")
    print(f"  {'core period':>11s} {'core MHz':>9s} | {'derived: bytes piled up in a frame':>34s} | {'depth 16: delivered':>20s} {'lost bytes':>11s} {'corrupt?':>9s} | {'depth 64: delivered':>20s} {'lost bytes':>11s} {'corrupt?':>9s}")
    for core in (6400, 8000, 8050, 8100, 8200, 8350, 8400):
        row = []
        for caw in (4, 6):
            o = flow.sim_icarus(F, "mac_path_tb", defines=(f"NC={len(st)}", f"COREP={core}", f"CAW={caw}", "RDY=100"))[1]; got = [p for p, _ in g.parse_frames(o)]; s = [int(x) for x in re.search(r"STATS (.*)", o).group(1).split()]
            row.append((len(got), s[3], subseq(got, good)))
        pile = max(0.0, n * (1 - 8000 / core))
        print(f"  {core:8d} ps {1e6 / core:9.2f} | {pile:34.1f} | {row[0][0]:>16d} /60 {row[0][1]:11d} {'NO' if row[0][2] else 'YES':>9s} | {row[1][0]:>16d} /60 {row[1][1]:11d} {'NO' if row[1][2] else 'YES':>9s}")
    for depth in (16, 64): print(f"  derived (a), depth {depth}: core period < 8000 / (1 - {depth} / {n}) = {8000 / (1 - depth / n):.0f} ps")
    print(f"  derived (b), any depth: core period <= 8000 x ({n} + 24) / {n} = {8000 * (n + 24) / n:.0f} ps")
    print("  the measured losses begin where the first limit that applies is crossed: depth 16 between 8,050 and 8,100 ps (limit (a)), depth 64 between 8,100 and 8,200 ps (limit (b)). A core clock FASTER than the PHY byte rate (6,400 ps here) never loses anything. 'corrupt?' = a delivered frame that is not byte-exact or out of order.")
main()
