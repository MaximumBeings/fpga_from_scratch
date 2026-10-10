#!/usr/bin/env python3
"""Chapter 21: the running designs. (1) lint; (2) the model: hand-checked scenarios and what the stimulus contains; (3) the engine against the cycle model, the answer to every message (found, index, matching rules, fire, first) in the cycle the model says, in two simulators, for five sizes (buckets, ways, rules, symbols, comparison stages), on random traffic with rule writes and table writes in the same cycles as messages, on traffic with 32-bit keys, on a message in every cycle, and on directed edge cases for every comparison."""
import os, random, subprocess, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, trig_gold as G
R = flow.ROOT; F = ["rtl/trig.sv", "tb/trig_tb.sv"]
def rows_rtl(cyc, cfg, simu="icarus", rtl=F):
    nb, k, nr, ns, pipe = cfg; n = G.write_stim(os.path.join(R, "out", "trig_stim.hex"), cyc)
    o = (flow.sim_icarus if simu == "icarus" else flow.sim_verilator)(rtl, "trig_tb", defines=(f"NC={n}", f"NB={nb}", f"K={k}", f"R={nr}", f"PIPE={pipe}") + (("GARBAGE",) if simu == "icarus" else ()))[1]
    try: return [tuple(int(x) for x in l.split()[1:]) for l in o.splitlines() if l.startswith("C ")]
    except ValueError: return [("x",)]
def same(cyc, cfg, simu="icarus", rtl=F):
    got = rows_rtl(cyc, cfg, simu, rtl); exp = G.expected_rows(G.run(cyc, *cfg), cfg[0]); return got[:len(exp)] == exp and len(got) >= len(exp)
CONFIGS = [(8, 2, 4, 16, 0), (8, 2, 4, 16, 1), (4, 4, 8, 32, 0), (16, 1, 16, 8, 1), (2, 8, 3, 32, 0)]
def make(kind, seed, n, cfg):
    nb, k, nr, ns, pipe = cfg; rng = random.Random(seed)
    if kind == "edge": return G.edge_cycles(nb, ns)
    if kind == "near": return G.gen_cycles(rng, n, nb, k, nr, ns, key_space=40, near=True, ld_rate=0.15, density=0.9)
    if kind == "wide": return G.gen_cycles(rng, n, nb, k, nr, ns, wide=True)
    if kind == "dense": return G.gen_cycles(rng, n, nb, k, nr, ns, density=1.0, cfg_rate=0.2, ld_rate=0.2)
    return G.gen_cycles(rng, n, nb, k, nr, ns)
KINDS = ("random", "wide", "near", "dense", "edge")
def battery():
    """The mutation runs' test: five sizes, the four kinds, Icarus. -> None or the first difference."""
    for ci, cfg in enumerate(CONFIGS):
        for kind in KINDS:
            for seed in range(1 if kind == "edge" else 2):
                if kind == "edge" and ci not in (0, 1, 3): continue
                try: ok = same(make(kind, seed + ci, 200, cfg), cfg)
                except Exception as x: return f"crash {type(x).__name__}"
                if not ok: return f"{kind}, NB {cfg[0]}, K {cfg[1]}, R {cfg[2]}, NS {cfg[3]}, PIPE {cfg[4]}"
    return None
def battery_model():
    """The model's own test: its hand-checked scenarios. -> None or a description."""
    q = subprocess.run([sys.executable, "model/trig_gold.py"], cwd=R, capture_output=True, text=True, timeout=300)
    return None if q.returncode == 0 else "hand-checked scenarios"
if __name__ == "__main__":
    if "--battery-model" in sys.argv: print("RESULT", battery_model()); sys.exit(0)
    if "--battery" in sys.argv: print("RESULT", battery()); sys.exit(0)
    print("== 1. lint gate (Verilator -Wall --lint-only, Yosys 'check')")
    p = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", "trig", "rtl/trig.sv"], cwd=R, capture_output=True, text=True); w = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning") and "DECLFILENAME" not in l]
    y = subprocess.run(["yosys", "-p", "read_verilog -sv rtl/trig.sv; hierarchy -top trig; proc; opt_clean; check"], cwd=R, capture_output=True, text=True).stdout
    print(f"  trig: Verilator warnings {len(w)}, Yosys check problems {len([l for l in y.splitlines() if 'Found and reported' in l and ' 0 problems' not in l])}")
    print("\n== 2. the model (python3 model/trig_gold.py) and what the stimulus contains (NB 8, K 2, R 4, NS 16, 8 seeds of 300 cycles; edge: the directed set)")
    print("  " + subprocess.run([sys.executable, "model/trig_gold.py"], cwd=R, capture_output=True, text=True).stdout.strip())
    cfg0 = CONFIGS[0]
    for kind in KINDS:
        c = Counter(); nm = nf = nfire = nfirst = ncfg = nld = 0
        for seed in range(1 if kind == "edge" else 8):
            cyc = make(kind, seed, 300, cfg0); res = G.run(cyc, *cfg0)
            for cy in cyc: ncfg += "cfg" in cy; nld += "ld" in cy
            for r in res["rows"]:
                if r[0]: nm += 1; nf += r[1]; nfire += r[4]; c[bin(r[3]).count("1")] += 1
        print(f"  {kind:7s} messages {nm:5d}, key found {nf:5d}, fired {nfire:5d}, rule writes {ncfg:4d}, table writes {nld:4d}; rules matched per message: " + ", ".join(f"{k} x{v}" for k, v in sorted(c.items())))
    print("\n== 3. the engine against the cycle model: found, index, matching rules, fire, first, and ready, in every cycle; 4 seeds of 300 cycles per row (edge: the directed set)")
    print(f"  {'traffic':7s} {'NB':>3s} {'K':>2s} {'R':>3s} {'NS':>3s} {'PIPE':>4s} | {'cycles':>7s} {'answers':>8s} {'fired':>6s} | {'Icarus':>9s} {'Verilator':>10s}")
    for kind in KINDS:
        for cfg in CONFIGS:
            ok = ncyc = nans = nfire = 0; v = "-"; seeds = 1 if kind == "edge" else 4
            for seed in range(seeds):
                cyc = make(kind, seed, 300, cfg); res = G.run(cyc, *cfg); ok += same(cyc, cfg); ncyc += len(cyc)
                for r in res["rows"]: nans += r[0]; nfire += r[4]
                if seed == 0: v = "PASS" if same(cyc, cfg, "verilator") else "FAIL"
            print(f"  {kind:7s} {cfg[0]:3d} {cfg[1]:2d} {cfg[2]:3d} {cfg[3]:3d} {cfg[4]:4d} | {ncyc:7d} {nans:8d} {nfire:6d} | {ok:6d} of {seeds} {v:>10s}")
