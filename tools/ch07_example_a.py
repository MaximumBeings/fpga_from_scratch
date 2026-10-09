#!/usr/bin/env python3
"""Chapter 7, example A: what the width of the datapath costs. For W = 8, 16, 32, 64 bits per beat: the XOR-equation statistics from the generator (derived), the LUT4/flip-flop count and Fmax from Yosys and nextpnr on iCE40 and ECP5 (measured), the throughput W x Fmax (derived), and how many beats a 64-byte and a 1,518-byte frame take. Usage: ch07_example_a.py"""
import os, sys, concurrent.futures as cf, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import flow, crc_gen
WS = (8, 16, 32, 64)
def job(a):
    top, W, fam = a; r = flow.run(["rtl/crc32_stream.sv"], top, fam, 400, tag=f"{top}_{W}_{fam}", params={"W": W}); return a, r
if __name__ == "__main__":
    with cf.ThreadPoolExecutor(4) as ex: res = dict(ex.map(job, [(t, W, f) for t in ("crc32_stream", "crc32_fast") for W in WS for f in ("ice40", "ecp5")]))
    print("== 1. the XOR equations (derived by crc_gen.py): inputs XORed to make each of the 32 output bits, for a full beat")
    print(f"  {'W':>3s} {'min inputs':>10s} {'max inputs':>10s} {'total terms':>11s} {'XOR depth with 4-input LUTs':>28s}")
    for W in WS:
        w = crc_gen.row_weights(W // 8); print(f"  {W:3d} {min(w):10d} {max(w):10d} {sum(w):11d} {math.ceil(math.log(max(w), 4)):28d}")
    print("  (an n-input XOR needs ceil(log4 n) levels of 4-input LUTs; the generated function for a partial last beat shares the same registers, so the real depth also includes the byte-count multiplexer)")
    for top, title in (("crc32_stream", "2. measured: the single-stage design crc32_stream (latency 1; one register loop through the whole update and the byte-count multiplexer)"), ("crc32_fast", "3. measured: the pipelined design crc32_fast (latency 5; the loop through the state register is only A8 XOR one precomputed word)")):
        print(f"\n== {title}; nextpnr seed 1, asked for 400 MHz")
        print(f"  {'W':>3s} | {'iCE40 LUT':>9s} {'FF':>4s} {'Fmax MHz':>9s} {'Gbit/s':>7s} | {'ECP5 LUT':>8s} {'FF':>4s} {'Fmax MHz':>9s} {'Gbit/s':>7s}")
        for W in WS:
            i, e = res[(top, W, "ice40")], res[(top, W, "ecp5")]
            print(f"  {W:3d} | {i['luts']:9d} {i['ffs']:4d} {i['fmax']:9.1f} {W * i['fmax'] / 1000:7.1f} | {e['luts']:8d} {e['ffs']:4d} {e['fmax']:9.1f} {W * e['fmax'] / 1000:7.1f}")
        print("  Gbit/s = W x Fmax: the line rate the datapath could sustain if every clock carried a full beat (derived from nextpnr's estimate)")
    print("\n== 4. what a 10 Gigabit Ethernet link needs: 10 Gbit/s / W bits per beat = the clock (derived) and the beats per frame")
    print(f"  {'W':>3s} {'clock for 10 Gbit/s':>20s} {'beats, 64-byte frame':>21s} {'beats, 1518-byte frame':>23s}")
    for W in WS: print(f"  {W:3d} {10000 / W:17.2f} MHz {math.ceil(64 / (W // 8)):21d} {math.ceil(1518 / (W // 8)):23d}")
    print("  the standard 10GbE datapath is 64 bits at 156.25 MHz")
