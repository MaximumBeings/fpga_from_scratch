#!/usr/bin/env python3
"""Chapter 19: the running designs. (1) lint; (2) the model: hand-checked scenarios and the statistics of the stimulus; (3) the book against the cycle model, every result, the top of book of its symbol and the readiness of the engine in every cycle, in two simulators, for five sizes (symbols, levels, orders), on realistic flow with faults and on RANDOM events (which reach the cases the realistic flow does not)."""
import os, random, subprocess, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, book_gold as G
R = flow.ROOT; F = ["rtl/book.sv", "tb/book_tb.sv"]
def rows_rtl(res, ns, d, no, simu="icarus", rtl=F):
    n = G.write_stim(os.path.join(R, "out", "book_stim.hex"), res["lines"])
    o = (flow.sim_icarus if simu == "icarus" else flow.sim_verilator)(rtl, "book_tb", defines=(f"NC={n}", f"NS={ns}", f"D={d}", f"NO={no}") + (("GARBAGE",) if simu == "icarus" else ()))[1]
    try: return [tuple(int(x) for x in l.split()[1:]) for l in o.splitlines() if l.startswith("C ")]
    except ValueError: return [("x",)]
def same(res, ns, d, no, simu="icarus", rtl=F):
    got = rows_rtl(res, ns, d, no, simu, rtl); exp = G.expected_rows(res); return got[:len(exp)] == exp and len(got) >= len(exp)
def random_events(rng, n, ns, d, no):
    """Uniformly random events over a small space of references, symbols and prices: unknown and duplicate references, all the results, full tables and levels, every phase."""
    out = []
    for _ in range(n):
        t = rng.randrange(5); e = dict(t=t, ref=rng.randint(1, no + 3), ref2=rng.randint(1, no + 3), sym=rng.randrange(ns), side=rng.randrange(2), px=rng.randint(1, d + 3), sh=rng.choice([0, 1, 2, 5, 10, 0xFFFFFFFF]) if rng.random() < .1 else rng.randint(1, 8))
        out.append(e)
    return out
CONFIGS = [(2, 4, 8), (1, 2, 4), (3, 3, 6), (4, 8, 16), (2, 1, 3)]
def make(kind, seed, n, ns, d, no):
    rng = random.Random(seed)
    ev = G.gen_events(rng, n, ns, d, no, spread=d + 1, faults=0.1) if kind == "flow" else random_events(rng, n, ns, d, no)
    return G.run(ev, ns, d, no, gaps=[rng.choice([0, 0, 0, 1, 4]) for _ in ev]), ev
def battery():
    """The mutation runs' test: five sizes, flow with faults and random events, Icarus. -> None or the first difference."""
    for ci, (ns, d, no) in enumerate(CONFIGS):
        for kind in ("flow", "random"):
            for seed in range(2):
                try: res, _ = make(kind, seed + ci, 150, ns, d, no); ok = same(res, ns, d, no)
                except Exception as x: return f"crash {type(x).__name__}"
                if not ok: return f"{kind}, NS {ns}, D {d}, NO {no}"
    return None
def battery_model():
    """The model's own test: its hand-checked scenarios. -> None or a description."""
    q = subprocess.run([sys.executable, "model/book_gold.py"], cwd=R, capture_output=True, text=True, timeout=300)
    return None if q.returncode == 0 else "hand-checked scenarios"
if __name__ == "__main__":
    if "--battery-model" in sys.argv: print("RESULT", battery_model()); sys.exit(0)
    if "--battery" in sys.argv: print("RESULT", battery()); sys.exit(0)
    print("== 1. lint gate (Verilator -Wall --lint-only, Yosys 'check')")
    p = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", "book", "rtl/book.sv"], cwd=R, capture_output=True, text=True); w = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning") and "DECLFILENAME" not in l]
    y = subprocess.run(["yosys", "-p", "read_verilog -sv rtl/book.sv; hierarchy -top book; proc; opt_clean; check"], cwd=R, capture_output=True, text=True).stdout
    print(f"  book: Verilator warnings {len(w)}, Yosys check problems {len([l for l in y.splitlines() if 'Found and reported' in l and ' 0 problems' not in l])}")
    print("\n== 2. the model (python3 model/book_gold.py) and what the stimulus contains (8 seeds of 300 events, NS 2, D 4, NO 8)")
    print("  " + subprocess.run([sys.executable, "model/book_gold.py"], cwd=R, capture_output=True, text=True).stdout.strip())
    for kind in ("flow", "random"):
        c = Counter(); t = Counter()
        for seed in range(8):
            res, ev = make(kind, seed, 300, 2, 4, 8)
            for r in res["rows"]:
                if r[1]: c[G.RN[r[1][0]]] += 1
            for e in ev: t[G.TN[e["t"]]] += 1
        print(f"  {kind:7s} events: " + ", ".join(f"{k} {v}" for k, v in sorted(t.items())) + "  | results: " + ", ".join(f"{k} {v}" for k, v in sorted(c.items(), key=lambda kv: G.RN.index(kv[0]))))
    print("\n== 3. the book against the cycle model: every result with the top of book of its symbol, and `ready`, in every cycle; 4 seeds of 300 events per row")
    print(f"  {'events':7s} {'NS':>2s} {'D':>2s} {'NO':>3s} | {'cycles':>7s} {'results':>8s} {'OK':>5s} {'rejected':>9s} | {'Icarus':>9s} {'Verilator':>10s}")
    for kind in ("flow", "random"):
        for ns, d, no in CONFIGS:
            ok = 0; cyc = nres = nok = 0; v = "-"
            for seed in range(4):
                res, ev = make(kind, seed, 300, ns, d, no); ok += same(res, ns, d, no); cyc += res["cycles"]
                for r in res["rows"]:
                    if r[1]: nres += 1; nok += r[1][0] == G.OK
                if seed == 0: v = "PASS" if same(res, ns, d, no, "verilator") else "FAIL"
            print(f"  {kind:7s} {ns:2d} {d:2d} {no:3d} | {cyc:7d} {nres:8d} {nok:5d} {nres - nok:9d} | {ok:6d} of 4 {v:>10s}")
