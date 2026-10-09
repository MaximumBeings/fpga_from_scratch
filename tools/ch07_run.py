#!/usr/bin/env python3
"""Chapter 7: the running designs. (1) the three software CRCs agree; (2) lint; (3) the generated streaming CRC against zlib: random frames at W = 8, 16, 32, 64 in two simulators, and frames of EVERY length from 1 to 80 bytes at every width (all partial-last-beat cases); (4) the 8-byte update against eight 1-byte updates on a basis, and the gate-type check that makes the basis argument valid. Usage: ch07_run.py"""
import os, re, subprocess, sys, zlib, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, crc_gold as g
R = flow.ROOT; V = os.path.join(R, "out", "crc_vec.hex")
def first(o): return next((l for l in o.splitlines() if l.startswith(("PASS", "FAIL", "MISM", "COMPILE"))), "no output")
def run_w(w, frames, seed, sims=("icarus",), fast=0):
    ins = g.schedule(frames, w, seed); g.write_vectors(V, ins, g.expected(ins, w, 5 if fast else 1), w); out = []
    for s in sims:
        fn = flow.sim_icarus if s == "icarus" else flow.sim_verilator; out.append(first(fn(["rtl/crc32_stream.sv", "tb/crc_tb.sv"], "crc_tb", defines=(f"W={w}", f"NC={len(ins)}", f"FAST={fast}"))[1]).startswith("PASS"))
    return out
if __name__ == "__main__":
    print("== 1. three implementations of the CRC-32 in software: bit-serial from the definition, table-driven, and zlib; 20,000 random messages of 0 to 2,000 bytes")
    rng = random.Random(1); ok = sum(g.crc_bitwise(d) == g.crc_table(d) == zlib.crc32(d) for d in (bytes(rng.getrandbits(8) for _ in range(rng.randint(0, 2000))) for _ in range(20000)))
    print(f"  all three agree on {ok} of 20000;  residue 0x{g.RESIDUE:08X} reproduced for a frame + FCS: {zlib.crc32(g.with_fcs(b'hello world')) == g.RESIDUE};  the standard check value zlib.crc32(b'123456789') = 0x{zlib.crc32(b'123456789'):08X} (expected 0xCBF43926)")
    print("\n== 2. lint gate")
    for top in ("crc32_comb", "crc32_stream", "crc32_fast"):
        p = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", top, "rtl/crc32_stream.sv"], cwd=R, capture_output=True, text=True); w = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning")]
        y = subprocess.run(["yosys", "-p", f"read_verilog -sv rtl/crc32_stream.sv; hierarchy -top {top}; proc; opt_clean; check"], cwd=R, capture_output=True, text=True).stdout
        print(f"  {top:13s} Verilator warnings: {len(w)}   Yosys check problems: {len([l for l in y.splitlines() if 'Found and reported' in l and ' 0 problems' not in l])}")
    print("\n== 3. both designs against zlib.crc32 (crc32_stream: result 1 cycle after the last beat; crc32_fast: 5 cycles; each frame is checked for the CRC of all its bytes and for the good/bad flag)")
    print(f"  {'design':13s} {'W':>3s} {'random frames, 3 seeds x 60':>28s} {'Icarus':>7s} {'Verilator':>10s} | {'every length 1-80 bytes, good+bad':>34s} {'Icarus':>7s}")
    for fast, name in ((0, "crc32_stream"), (1, "crc32_fast")):
        for w in (8, 16, 32, 64):
            r = [run_w(w, g.make_frames(sd, 60), sd, ("icarus", "verilator"), fast) for sd in (1, 2, 3)]
            a = run_w(w, g.frames_all_lengths(1, 80), 9, ("icarus",), fast)[0]
            print(f"  {name:13s} {w:3d} {'':>28s} {('PASS' if all(x[0] for x in r) else 'FAIL'):>7s} {('PASS' if all(x[1] for x in r) else 'FAIL'):>10s} | {'':>34s} {('PASS' if a else 'FAIL'):>7s}")
    print("\n== 4. the 64-bit update against eight 1-byte updates: all 97 basis inputs (Icarus), and the gate types of the generated XOR networks")
    print("  " + first(flow.sim_icarus(["rtl/crc32_stream.sv", "tb/crc_linear_tb.sv"], "crc_linear_tb")[1]))
    for K in (1, 4, 8):
        y = subprocess.run(["yosys", "-p", f"read_verilog -sv rtl/crc32_stream.sv formal/crc_lin_chk.sv; chparam -set K {K} crc_lin_chk; hierarchy -top crc_lin_chk; synth -top crc_lin_chk -flatten; abc -g XOR,AND,OR,MUX; stat"], cwd=R, capture_output=True, text=True).stdout
        cells = dict(re.findall(r"^\s+(\$_\w+_)\s+(\d+)", y.rsplit("Number of cells", 1)[-1], re.M)); print(f"  step{K} ({8 * K} bits): gates after mapping: {cells}   only XOR and NOT gates (so affine): {set(cells) <= {'$_XOR_', '$_NOT_'}}")
    print("  XOR and NOT gates make an AFFINE function (linear plus a constant); the basis test also checks that the all-zero input gives zero for both circuits, so the constant is zero and the functions are linear, which is what the basis argument needs")
    print("  a SAT miter of the 64-bit and the eight 1-byte updates (96 free input bits) did not finish within 100 seconds even for the 2-byte case: CDCL solvers are poor at long XOR chains, so the proof above is by linearity instead")
