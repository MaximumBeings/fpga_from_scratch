#!/usr/bin/env python3
"""Chapter 5: the running designs. (1) lint gate; (2) rounding/saturation EXHAUSTIVELY (every input) in three width configurations and four modes; (3) the multiply-accumulate against the golden model, four modes, random and overflow-heavy traffic, two simulators; (4) the two FIR forms against the model, two simulators; (5) the three memory read styles against the model; (6) a quantization-error study in Python (truncation against rounding, rounding each product against rounding the sum, saturation against wrap). Usage: ch05_run.py"""
import os, sys, subprocess, random, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, fx_gold as g
R = flow.ROOT; V = lambda n: os.path.join(R, "out", n); COHEX = "".join(f"{g.COEF[i] & 0xFFFF:04x}" for i in reversed(range(8)))
def first(o): return next((l for l in o.splitlines() if l.startswith(("PASS", "FAIL", "MISM", "COMPILE"))), "no output")
def ok(o): return first(o).startswith("PASS")
if __name__ == "__main__":
    print("== 1. lint gate: Verilator -Wall --lint-only and Yosys 'check'")
    for files, top in ((["rtl/fxp.sv"], "fx_round_sat"), (["rtl/fxp.sv"], "fx_mac"), (["rtl/fxp.sv", "rtl/fir.sv"], "fir_direct"), (["rtl/fxp.sv", "rtl/fir.sv"], "fir_transposed"), (["rtl/ram_style.sv"], "ram_style"), (["rtl/mulreg.sv"], "mulreg")):
        p = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", top] + files, cwd=R, capture_output=True, text=True); w = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning")]
        y = subprocess.run(["yosys", "-p", f"read_verilog -sv {' '.join(files)}; hierarchy -top {top}; proc; opt_clean; check"], cwd=R, capture_output=True, text=True).stdout; bad = [l for l in y.splitlines() if "Found and reported" in l and " 0 problems" not in l]
        print(f"  {top:15s} Verilator warnings: {len(w)}   Yosys check problems: {len(bad)}")
    print("\n== 2. fx_round_sat: EVERY input value, against the model (Icarus); three width configurations x four modes")
    print(f"  {'IW':>3s} {'OW':>3s} {'SH':>3s} | {'trunc, wrap':>12s} {'round, wrap':>12s} {'trunc, sat':>11s} {'round, sat':>11s}   inputs per run")
    for iw, ow, sh in ((12, 6, 4), (10, 10, 0), (14, 8, 5)):
        row = []
        for rnd, sat in ((0, 0), (1, 0), (0, 1), (1, 1)):
            g.rs_vectors(V("rs_vec.hex"), iw, ow, sh, rnd, sat); row.append("PASS" if ok(flow.sim_icarus(["rtl/fxp.sv", "tb/rs_tb.sv"], "rs_tb", defines=(f"IW={iw}", f"OW={ow}", f"SH={sh}", f"RND={rnd}", f"SAT={sat}"))[1]) else "FAIL")
        print(f"  {iw:3d} {ow:3d} {sh:3d} | {row[0]:>12s} {row[1]:>12s} {row[2]:>11s} {row[3]:>11s}   {1 << iw}")
    print("  (one run also in Verilator:", "PASS" if (g.rs_vectors(V("rs_vec.hex"), 12, 6, 4, 1, 1) and ok(flow.sim_verilator(["rtl/fxp.sv", "tb/rs_tb.sv"], "rs_tb", defines=("IW=12", "OW=6", "SH=4", "RND=1", "SAT=1"))[1])) else "FAIL", ")")
    print("\n== 3. fx_mac against the model: 3,000 cycles per run (16-bit operands, 40-bit accumulator)")
    print(f"  {'traffic':10s} {'mode':14s} {'Icarus':>7s} {'Verilator':>10s}   outputs at the saturation limits")
    for mode in ("random", "overflow"):
        for rnd, sat, nm in ((1, 1, "round, sat"), (0, 1, "trunc, sat"), (1, 0, "round, wrap"), (0, 0, "trunc, wrap")):
            st = g.mac_stim(1, 3000, mode); res = g.mac_run(st, rnd, sat); g.write_mac(V("mac_vec.hex"), st, res); d = (f"RND={rnd}", f"SAT={sat}")
            i = ok(flow.sim_icarus(["rtl/fxp.sv", "tb/mac_tb.sv"], "mac_tb", defines=d)[1]); v = ok(flow.sim_verilator(["rtl/fxp.sv", "tb/mac_tb.sv"], "mac_tb", defines=d)[1]) if (mode == "overflow" or nm == "round, sat") else None
            print(f"  {mode:10s} {nm:14s} {'PASS' if i else 'FAIL':>7s} {('PASS' if v else 'FAIL') if v is not None else '-':>10s}   {sum(1 for acc, y in res if y in (32767, -32768)) if sat else 'n/a (wrap)'}")
    print("\n== 4. the two FIR forms against the model: 3,000 cycles, mostly random input with bursts of full-scale values (the filter's gain is 1.17, so full scale overflows)")
    rng = random.Random(3); xs = [rng.randint(-32768, 32767) if k % 50 < 40 else rng.choice([32767, -32768]) for k in range(3000)]
    print(f"  {'form':12s} {'round, sat':>11s} {'trunc, sat':>11s} {'round, wrap':>12s} {'Verilator (round, sat)':>24s}")
    for form in (0, 1):
        row = []
        for rnd, sat in ((1, 1), (0, 1), (1, 0)):
            g.write_fir(V("fir_vec.hex"), xs, g.fir_run(xs, rnd, sat)); row.append("PASS" if ok(flow.sim_icarus(["rtl/fxp.sv", "rtl/fir.sv", "tb/fir_tb.sv"], "fir_tb", defines=(f"FORM={form}", f"COHEX={COHEX}", f"RND={rnd}", f"SAT={sat}"))[1]) else "FAIL")
        g.write_fir(V("fir_vec.hex"), xs, g.fir_run(xs, 1, 1)); v = "PASS" if ok(flow.sim_verilator(["rtl/fxp.sv", "rtl/fir.sv", "tb/fir_tb.sv"], "fir_tb", defines=(f"FORM={form}", f"COHEX={COHEX}"))[1]) else "FAIL"
        print(f"  {['direct', 'transposed'][form]:12s} {row[0]:>11s} {row[1]:>11s} {row[2]:>12s} {v:>24s}")
    res = g.fir_run(xs); print(f"  saturated outputs in the run: {sum(1 for a, y in res if y in (32767, -32768))} of 3000; with wrap instead, {sum(1 for a, y in zip(res, g.fir_run(xs, 1, 0)) if a[1] != y[1])} outputs differ")
    print("\n== 5. ram_style against the model: 3,000 cycles of random writes and reads (a fifth of the reads hit the address being written)")
    print(f"  {'depth':>6s} {'style 0 (async)':>16s} {'style 1 (sync)':>15s} {'style 2 (sync + reg)':>21s}")
    for D in (16, 256, 4096):
        row = []
        for s in (0, 1, 2):
            ops = g.ram_ops(2, 3000, D, 16); g.write_ram(V("ram_vec.hex"), ops, g.ram_run(s, ops, D), 16); row.append("PASS" if ok(flow.sim_icarus(["rtl/ram_style.sv", "tb/ram_tb.sv"], "ram_tb", defines=(f"D={D}", f"STYLE={s}"))[1]) else "FAIL")
        print(f"  {D:6d} {row[0]:>16s} {row[1]:>15s} {row[2]:>21s}")
    print("\n== 6. quantization error (Python, model arithmetic; units: the least significant bit of Q1.15, 2^-15)")
    rng = random.Random(11); N = 100000; errs = {"truncate": [], "round half up": []}
    for _ in range(N):
        a, b = rng.randint(-32768, 32767), rng.randint(-32768, 32767); p = a * b; exact = p / 32768
        errs["truncate"].append(g.round_sat(p, 32, 17, 15, 0, 0) - exact); errs["round half up"].append(g.round_sat(p, 32, 17, 15, 1, 0) - exact)
    print(f"  one product narrowed from Q2.30 to Q1.15 ({N} random pairs):  {'mean':>8s} {'max |error|':>12s}")
    for k, v in errs.items(): print(f"    {k:14s} {statistics.mean(v):+8.3f} {max(abs(x) for x in v):12.3f}")
    print("  the sum of 256 products, each of magnitude up to full scale, 2,000 trials: error of the result against the exact sum")
    rng = random.Random(5); T = 2000; e_each = []; e_end = []
    for _ in range(T):
        ps = [rng.randint(-32768, 32767) * rng.randint(-32768, 32767) for _ in range(256)]; ex = sum(ps) / 32768
        e_each.append(sum(g.round_sat(p, 32, 17, 15, 1, 0) for p in ps) - ex); e_end.append(g.round_sat(sum(ps), 40, 32, 15, 1, 0) - ex)
    print(f"    round each product, then add:   mean {statistics.mean(e_each):+7.3f}  standard deviation {statistics.pstdev(e_each):6.3f}  max |error| {max(abs(x) for x in e_each):6.3f}")
    print(f"    add at full width, round once:  mean {statistics.mean(e_end):+7.3f}  standard deviation {statistics.pstdev(e_end):6.3f}  max |error| {max(abs(x) for x in e_end):6.3f}")
    print("  saturation against wrap: Q1.15 values 0.75 + 0.5 (24576 + 16384 = 40960): saturate gives", g.round_sat(40960 * 32768, 40, 16, 15, 1, 1), " wrap gives", g.round_sat(40960 * 32768, 40, 16, 15, 1, 0), "(that is 0.75 + 0.5 = 1.25 reported as -0.75)")
