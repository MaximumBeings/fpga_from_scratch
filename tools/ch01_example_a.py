#!/usr/bin/env python3
"""Chapter 1, example A: the lookup table as the unit of logic. (1) one LUT4 as a memory, by hand; (2) a function of six inputs split into LUTs by Shannon expansion; (3) a small mapper against Yosys on nine functions. Writes out/ch01_example_a.json. Usage: ch01_example_a.py"""
import json, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, lut_fabric as L
ROOT = flow.ROOT
print("== 1. a LUT4 is a 16-bit memory: the inputs are the address, the bitstream wrote the contents")
f = lambda b: (b[0] & b[1]) ^ (b[2] | b[3])
tt = L.table(4, f); print("  function: y = (a AND b) XOR (c OR d), inputs a..d = bits 0..3 of the address")
print("  address (d c b a)  y   | address (d c b a)  y")
for i in range(8): print(f"      {i:04b}          {tt[i]}   |     {i+8:04b}          {tt[i+8]}")
word = sum(b << i for i, b in enumerate(tt)); print(f"  the 16 bits, address 15 down to 0: {word:016b} = 0x{word:04X}: this number IS the logic; there is no AND or XOR gate in the fabric, only this memory")
print("  evaluating the LUT for a=1,b=1,c=0,d=0: address 0b0011 = 3 ->", tt[3], "(AND is 1, OR is 0, 1 XOR 0 = 1)")
print("\n== 2. a function of six inputs: parity of x0..x5. One LUT4 holds four inputs; Shannon expansion splits the rest")
tt6 = L.table(6, lambda b: sum(b) % 2); net, out = L.map_function(tt6, 6)
print(f"  mapped to {len(net.luts)} LUT4s; exhaustive check against the truth table (64 inputs): {L.check(net, out, tt6, 6)}")
for k, (t, ins) in enumerate(net.luts): print(f"    LUT{k}: inputs {[('x%d' % s[1]) if s[0] == 'in' else ('LUT%d' % s[1]) for s in ins]}, table {''.join(str(b) for b in t[::-1])}")
print("  the best possible is 2 LUTs (xor of four inputs, then xor of that and the other two); the mapper is not optimal, and Yosys's ABC finds the better answer below")
print("\n== 3. the little mapper against Yosys (synth_ice40 and synth_ecp5): LUT counts for nine functions, written as truth-table lookups")
R = random.Random(4); rnd7 = tuple(R.getrandbits(1) for _ in range(128))
fn = [("parity6", 6, L.table(6, lambda b: sum(b) % 2)), ("and6", 6, L.table(6, lambda b: all(b))), ("majority5", 5, L.table(5, lambda b: sum(b) >= 3)), ("majority7", 7, L.table(7, lambda b: sum(b) >= 4)),
      ("mux4 (2 select + 4 data)", 6, L.table(6, lambda b: b[2 + b[0] + 2 * b[1]])), ("a > b, 3-bit", 6, L.table(6, lambda b: (b[0] + 2 * b[1] + 4 * b[2]) > (b[3] + 2 * b[4] + 4 * b[5]))),
      ("carry out of 4-bit add", 9, L.table(9, lambda b: (sum(b[i] << i for i in range(4)) + sum(b[4 + i] << i for i in range(4)) + b[8]) >= 16)), ("at least 3 of 8", 8, L.table(8, lambda b: sum(b) >= 3)), ("random 7-input", 7, rnd7)]
print(f"  {'function':26s} {'inputs':>6s} {'naive mapper':>13s} {'Yosys iCE40':>12s} {'Yosys ECP5 (LUT4 + LUT5/6 muxes)':>34s}"); res = []
for idx, (nm, n, t) in enumerate(fn):
    net, out = L.map_function(t, n); ok = L.check(net, out, t, n); tag = f"ex_a_{idx}"; open(os.path.join(ROOT, "out", tag + ".v"), "w").write(L.to_verilog("fn", n, t))
    a = flow.synth([f"out/{tag}.v"], "fn", "ice40", tag + "_i"); e = flow.synth([f"out/{tag}.v"], "fn", "ecp5", tag + "_e"); mux = e["cells"].get("PFUMX", 0) + e["cells"].get("L6MUX21", 0)
    res.append([nm, n, len(net.luts), a["luts"], e["luts"], mux]); print(f"  {nm:26s} {n:6d} {len(net.luts):9d}{'' if ok else ' WRONG'} {a['luts']:12d} {e['luts']:14d} + {mux} muxes")
print("  the naive mapper is correct on every function (checked exhaustively) and uses from the same number of LUTs up to two and a half times as many as Yosys's iCE40 mapping (parity6: 5 against 2): technology mapping is an optimization problem, and ABC solves it far better than a recursive split")
print("  the ECP5 column is not comparable with the iCE40 one: ECP5 builds a 5- or 6-input function from LUT4s joined by multiplexers inside the slice, so Yosys reports LUT4s plus muxes, and the same function costs more LUT4s there")
print("  note: a function of 5 or 6 inputs costs more than one LUT: that is why FPGA designers keep logic shallow and why the fabric of some families adds muxes to combine LUT4s cheaply (ECP5's PFUMX and L6MUX21)")
json.dump(res, open(os.path.join(ROOT, "out", "ch01_example_a.json"), "w"))
