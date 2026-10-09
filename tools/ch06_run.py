#!/usr/bin/env python3
"""Chapter 6: the verification harness, comparing techniques on one design. (1) lint; (2) simulator speed: Icarus against a Verilator C++ driver on the same million-cycle vector file; (3) the six injected bugs against four techniques (directed, uniform random, constrained random, formal bounded model checking), and how many cycles random testing needs to find each; (4) functional coverage of each stimulus; (5) formal: the shortest counterexample for each bug, an unbounded proof of the counting properties by induction, and a bounded proof of the tagged-word property. Usage: ch06_run.py"""
import os, re, statistics, subprocess, sys, tempfile, time, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, fifo_gold as g
R = flow.ROOT; V = lambda n: os.path.join(R, "out", n)
BUGS = {1: "write when full overwrites the oldest word", 2: "read+write with one word held: count goes to 0", 3: "write pointer wraps one word late", 4: "read+write when empty loses the word", 5: "read when empty underflows the count", 6: "a write of 0xA5 at depth-1 is lost"}
def sim_first_mismatch(stim, bug, tag):
    """Runs the Icarus testbench on a private vector file; returns the first cycle with a mismatch, or None."""
    path = V(f"vec_{tag}.hex"); g.write_vectors(path, stim, g.run(stim))
    rc, o = flow.sim_icarus(["rtl/sfifo.sv", "tb/sfifo_tb.sv"], "sfifo_tb", defines=(f"BUG={bug}", f"NC={len(stim)}", f'VEC="out/vec_{tag}.hex"'))
    m = re.search(r"MISMATCH cycle (\d+)", o); os.remove(path)
    return int(m.group(1)) if m else (None if "PASS" in o else -1)
def formal(bug, mode, depth, tag=1):
    script = f"read_verilog -formal -sv rtl/sfifo.sv formal/sfifo_props.sv; chparam -set BUG {bug} -set TAG {tag} sfifo_props; hierarchy -top sfifo_props; proc; flatten; memory_map; opt_clean; " + ("sat -prove-asserts -set-init-zero -seq %d" % depth if mode == "bmc" else "sat -prove-asserts -set-init-zero -tempinduct -seq 1 -maxsteps 30")
    t = time.time(); o = subprocess.run(["yosys", "-p", script], cwd=R, capture_output=True, text=True, timeout=300).stdout
    return ("proved" if "no model found: SUCCESS" in o or "Induction step proven: SUCCESS" in o else "FAILS"), time.time() - t
if __name__ == "__main__":
    print("== 1. lint gate")
    p = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", "sfifo", "rtl/sfifo.sv"], cwd=R, capture_output=True, text=True); w = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning")]
    y = subprocess.run(["yosys", "-p", "read_verilog -sv rtl/sfifo.sv; hierarchy -top sfifo; proc; opt_clean; check"], cwd=R, capture_output=True, text=True).stdout
    print(f"  sfifo  Verilator warnings: {len(w)}   Yosys check problems: {len([l for l in y.splitlines() if 'Found and reported' in l and ' 0 problems' not in l])}")
    print("\n== 2. simulator speed on the same vector file (1,000,000 cycles of constrained-random stimulus; run time only, compile time excluded)")
    big = g.constrained(7, 1000000); g.write_vectors(V("fifo_vec_big.hex"), big, g.run(big)); d = tempfile.mkdtemp(prefix="ico6_"); exe = os.path.join(d, "sim")
    subprocess.run(["iverilog", "-g2012", "-s", "sfifo_tb", "-o", exe, "-DNC=1000000", '-DVEC="out/fifo_vec_big.hex"', "rtl/sfifo.sv", "tb/sfifo_tb.sv"], cwd=R, check=True)
    t = time.time(); o = subprocess.run(["vvp", "-n", exe], cwd=R, capture_output=True, text=True).stdout; ti = time.time() - t
    vd = tempfile.mkdtemp(prefix="vlt6_"); subprocess.run(["verilator", "--cc", "--exe", "--build", "-O3", "-Wno-fatal", "-Wno-lint", "--top-module", "sfifo", "-Mdir", vd, "-CFLAGS", "-O2", os.path.join(R, "rtl/sfifo.sv"), os.path.join(R, "tb/sfifo_drv.cpp"), "-o", "drv"], capture_output=True)
    t = time.time(); ov = subprocess.run([os.path.join(vd, "drv"), V("fifo_vec_big.hex"), "1000000", "1"], capture_output=True, text=True).stdout; tv = time.time() - t
    print(f"  Icarus (SystemVerilog testbench):  {o.strip().splitlines()[0][:48]:48s} {1e6 / ti / 1e6:6.2f} million cycles per second")
    print(f"  Verilator (C++ driver):            {ov.strip()[:48]:48s} {1e6 / tv / 1e6:6.2f} million cycles per second (includes reading the file)")
    print(f"  ratio: {ti / tv:.0f} x faster in Verilator")
    os.remove(V("fifo_vec_big.hex"))
    print("\n== 3. the six injected bugs against four techniques ('found' = a mismatch, or a counterexample, or a failed assertion)")
    N = 2000; direct = g.directed(); uni = g.uniform(1, N); con = g.constrained(1, N)
    print(f"  {'bug':3s} {'what':48s} {'directed ' + str(len(direct)):>12s} {'uniform ' + str(N):>12s} {'constrained ' + str(N):>16s} {'formal (20 cycles)':>20s}")
    rows = {}
    for b in BUGS:
        r = [sim_first_mismatch(direct, b, f"d{b}"), sim_first_mismatch(uni, b, f"u{b}"), sim_first_mismatch(con, b, f"c{b}")]; fr, ft = formal(b, "bmc", 20)
        cell = lambda x: "missed" if x is None else f"at cycle {x}"
        rows[b] = r; print(f"  {b:3d} {BUGS[b]:48s} {cell(r[0]):>12s} {cell(r[1]):>12s} {cell(r[2]):>16s} {('found' if fr == 'FAILS' else 'missed'):>14s} {ft:4.1f}s")
    print("\n  how many cycles until the first mismatch, over 40 seeds (stimulus cut off at 20,000 cycles; 'not found' counts 20,000):")
    print(f"  {'bug':3s} {'uniform: median':>16s} {'worst':>8s} {'not found':>10s} | {'constrained: median':>20s} {'worst':>8s} {'not found':>10s}")
    def trial(a): b, kind, seed = a; st = (g.uniform if kind == "u" else g.constrained)(seed, 20000); return (b, kind), sim_first_mismatch(st, b, f"s{b}{kind}{seed}")
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(trial, [(b, k, s) for b in BUGS for k in "uc" for s in range(40)]))
    agg = {}
    for key, v in res: agg.setdefault(key, []).append(v)
    for b in BUGS:
        cells = []
        for k in "uc":
            vals = agg[(b, k)]; nf = sum(1 for x in vals if x is None); nums = [20000 if x is None else x for x in vals]; cells += [statistics.median(nums), max(nums), nf]
        print(f"  {b:3d} {cells[0]:16.0f} {cells[1]:8d} {cells[2]:10d} | {cells[3]:20.0f} {cells[4]:8d} {cells[5]:10d}")
    print("\n== 4. functional coverage: bins hit on the golden model's state (%d bins)" % len(g.BINS))
    print(f"  {'stimulus':26s} {'bins hit':>9s}   bins missed")
    for name, st in (("directed (44 cycles)", direct), ("uniform 200 cycles", g.uniform(1, 200)), ("constrained 200 cycles", g.constrained(1, 200)), ("uniform 2000 cycles", uni), ("constrained 2000 cycles", con)):
        h = g.coverage(st); miss = [b for b in g.BINS if b not in h]; print(f"  {name:26s} {len(h):4d} of {len(g.BINS)}   {', '.join(miss) if miss else '-'}")
    print("\n== 5. formal (Yosys SAT): shortest counterexample, unbounded proof by induction, bounded proof of the tagged word")
    print(f"  {'bug':3s} {'shortest counterexample (cycles)':>34s}")
    for b in BUGS:
        for dpt in range(1, 41):
            if formal(b, "bmc", dpt)[0] == "FAILS": break
        else: dpt = None
        print(f"  {b:3d} {('none within 40' if dpt is None else str(dpt)):>34s}")
    r, t = formal(0, "induction", 0, tag=0); print(f"  correct design, count/full/empty properties, induction (unbounded): {r} in {t:.2f} s")
    for b in BUGS:
        r, t = formal(b, "induction", 0, tag=0); print(f"    bug {b}: induction on the same properties: {r}")
    r, t = formal(0, "bmc", 20); print(f"  correct design, all properties including the tagged word, 20 cycles from reset: {r} in {t:.1f} s")
