#!/usr/bin/env python3
"""Chapter 23: the running designs. (1) lint; (2) the model: hand-checked scenarios and what the stimulus contains (every result code, faults, kills); (3) the gate against the model, every answer (kind, result, and the touched account and symbol's position, open quantities, notional and tokens after the update) in the cycle the model says, in two simulators, for five sizes, on random traffic, on traffic with small limits (so that the boundaries are hit often), on dense traffic with kills and faults, on the directed boundary sequence, and on the first cycles after reset."""
import os, random, subprocess, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, risk_gold as G
R_ = flow.ROOT; F_ = ["rtl/risk.sv", "tb/risk_tb.sv"]
def rows_rtl(cyc, cfg, simu="icarus", rtl=F_):
    na, ns, qw, pw, r = cfg; n = G.write_stim(os.path.join(R_, "out", "risk_stim.hex"), cyc)
    o = (flow.sim_icarus if simu == "icarus" else flow.sim_verilator)(rtl, "risk_tb", defines=(f"NC={n}", f"NA={na}", f"NS={ns}", f"QW={qw}", f"PW={pw}", f"R={r}") + (("GARBAGE",) if simu == "icarus" else ()))[1]
    try: return [tuple(int(x) for x in l.split()[1:]) for l in o.splitlines() if l.startswith("C ")]
    except ValueError: return [("x",)]
def same(cyc, cfg, simu="icarus", rtl=F_):
    got = rows_rtl(cyc, cfg, simu, rtl); exp = G.expected_rows(G.run(cyc, cfg[0], cfg[1], cfg[4])); return got[:len(exp)] == exp and len(got) >= len(exp)
CONFIGS = [(4, 4, 16, 16, 4), (2, 2, 8, 8, 3), (8, 4, 12, 10, 5), (3, 5, 16, 16, 7), (12, 14, 8, 8, 2)]
KINDS = ("random", "tight", "dense", "edge", "reset", "fault")
def make(kind, seed, n, cfg):
    na, ns, qw, pw, r = cfg; rng = random.Random(seed)
    if kind == "edge": return G.edge_cycles(na, ns), 1000
    if kind == "reset": return G.reset_cycles(na, ns, r), r
    if kind == "fault": return G.fault_cycles(seed % 5, na, ns), r
    if kind == "tight": return G.gen_cycles(rng, n, na, ns, r, qmax=8, pmax=12), r
    if kind == "dense": return G.gen_cycles(rng, n, na, ns, r, density=1.0, kill_rate=0.05, malformed=0.004, bad=0.1), r
    return G.gen_cycles(rng, n, na, ns, r), r
def battery():
    """The mutation runs' test: five sizes, the four kinds, Icarus. -> None or the first difference."""
    for ci, cfg in enumerate(CONFIGS):
        for kind in KINDS:
            for seed in range(5 if kind == "fault" else (1 if kind in ("edge", "reset") else 2)):
                try: cyc, r = make(kind, seed + ci, 200, cfg); c2 = cfg[:4] + (r,); ok = same(cyc, c2)
                except Exception as x: return f"crash {type(x).__name__}"
                if not ok: return f"{kind}, NA {cfg[0]}, NS {cfg[1]}, QW {cfg[2]}, PW {cfg[3]}, R {cfg[4]}"
    return None
def battery_model():
    q = subprocess.run([sys.executable, "model/risk_gold.py"], cwd=R_, capture_output=True, text=True, timeout=300)
    return None if q.returncode == 0 else "hand-checked scenarios"
if __name__ == "__main__":
    if "--battery-model" in sys.argv: print("RESULT", battery_model()); sys.exit(0)
    if "--battery" in sys.argv: print("RESULT", battery()); sys.exit(0)
    print("== 1. lint gate (Verilator -Wall --lint-only, Yosys 'check')")
    p = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", "risk", "rtl/risk.sv"], cwd=R_, capture_output=True, text=True); w = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning") and "DECLFILENAME" not in l]
    y = subprocess.run(["yosys", "-p", "read_verilog -sv rtl/risk.sv; hierarchy -top risk; proc; opt_clean; check"], cwd=R_, capture_output=True, text=True).stdout
    print(f"  risk: Verilator warnings {len(w)}, Yosys check problems {len([l for l in y.splitlines() if 'Found and reported' in l and ' 0 problems' not in l])}")
    print("\n== 2. the model (python3 model/risk_gold.py) and what the stimulus contains (NA 4, NS 4, R 4; 8 seeds of 300 cycles, edge: the directed set)")
    print("  " + subprocess.run([sys.executable, "model/risk_gold.py"], cwd=R_, capture_output=True, text=True).stdout.strip())
    cfg0 = CONFIGS[0]
    for kind in KINDS:
        c = Counter(); k = Counter(); armed_no = 0
        for seed in range(5 if kind == "fault" else (1 if kind in ("edge", "reset") else 8)):
            cyc, r = make(kind, seed, 300, cfg0); res = G.run(cyc, cfg0[0], cfg0[1], r)
            for row in res["rows"]:
                if row[0]: c[G.RN[row[2]]] += 1; k[G.KN[row[1]]] += 1
        print(f"  {kind:7s} answers: " + ", ".join(f"{x} {c[x]}" for x in G.RN if c[x]) + "  | events: " + ", ".join(f"{x} {v}" for x, v in sorted(k.items())))
    print("\n== 3. the gate against the model, in every cycle; 4 seeds of 300 cycles per row (edge, reset, fault: the directed sets)")
    print(f"  {'traffic':7s} {'NA':>3s} {'NS':>3s} {'QW':>3s} {'PW':>3s} {'R':>3s} | {'cycles':>7s} {'answers':>8s} {'accepted':>9s} | {'Icarus':>9s} {'Verilator':>10s}")
    for kind in KINDS:
        for cfg in CONFIGS:
            ok = ncyc = nans = nok = 0; v = "-"; seeds = 5 if kind == "fault" else (1 if kind in ("edge", "reset") else 4)
            for seed in range(seeds):
                cyc, r = make(kind, seed, 300, cfg); c2 = cfg[:4] + (r,); res = G.run(cyc, cfg[0], cfg[1], r); ok += same(cyc, c2); ncyc += len(cyc)
                for row in res["rows"]:
                    if row[0] and row[1] == G.ORDER: nans += 1; nok += row[2] == G.OK
                if seed == 0: v = "PASS" if same(cyc, c2, "verilator") else "FAIL"
            print(f"  {kind:7s} {cfg[0]:3d} {cfg[1]:3d} {cfg[2]:3d} {cfg[3]:3d} {cfg[4]:3d} | {ncyc:7d} {nans:8d} {nok:9d} | {ok:6d} of {seeds} {v:>10s}")
