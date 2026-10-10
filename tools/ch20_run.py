#!/usr/bin/env python3
"""Chapter 20: the running designs. (1) lint; (2) the model: hand-checked scenarios and the statistics of the stimulus; (3) the book against the cycle model, every result, the top of book of its symbol and the readiness of the engine in every cycle, in two simulators, for five sizes (symbols, levels, orders), on realistic flow with faults and on RANDOM events (which reach the cases the realistic flow does not)."""
import os, random, subprocess, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, book2_gold as G
R = flow.ROOT; F = ["rtl/book2.sv", "tb/book2_tb.sv"]
def rows_rtl(res, ns, d, nb, k, simu="icarus", rtl=F):
    n = G.write_stim(os.path.join(R, "out", "book2_stim.hex"), res["lines"])
    o = (flow.sim_icarus if simu == "icarus" else flow.sim_verilator)(rtl, "book2_tb", defines=(f"NC={n}", f"NS={ns}", f"D={d}", f"NB={nb}", f"K={k}") + (("GARBAGE",) if simu == "icarus" else ()))[1]
    try: return [tuple(int(x) for x in l.split()[1:]) for l in o.splitlines() if l.startswith("C ")]
    except ValueError: return [("x",)]
def same(res, ns, d, nb, k, simu="icarus", rtl=F):
    got = rows_rtl(res, ns, d, nb, k, simu, rtl); exp = G.expected_rows(res); return got[:len(exp)] == exp and len(got) >= len(exp)
def random_events(rng, n, ns, d, nb, k):
    """Uniformly random events over a small space of references, symbols and prices: unknown and duplicate references, all the results, full tables and levels, every phase."""
    out = []
    for _ in range(n):
        t = rng.randrange(5); e = dict(t=t, ref=rng.randint(0, nb * k + 3), ref2=rng.randint(0, nb * k + 3), sym=rng.randrange(ns), side=rng.randrange(2), px=rng.randint(1, d + 3), sh=rng.choice([0, 1, 2, 5, 10, 1 << 20]) if rng.random() < .1 else rng.randint(1, 8))
        out.append(e)
    return out
CONFIGS = [(2, 4, 4, 2), (1, 2, 2, 2), (3, 3, 4, 1), (4, 8, 8, 4), (2, 1, 2, 3)]
def widen(ev):
    """The same events with every reference mapped through a bijection of 32 bits (so that all four bytes of a reference are used by the hash and by the comparison)."""
    f = lambda r: (r * 2654435761 + 0x5BD1E995) & G.M
    return [{**e, "ref": f(e["ref"]), "ref2": f(e["ref2"])} if "ref2" in e else ({**e, "ref": f(e["ref"])} if "ref" in e else e) for e in ev]
def near_miss(nb, k):
    """References that differ in one bit from a live one: bit b of the reference changes bit b mod 8 of the hash, so with NB below 2^(b mod 8) it stays in the SAME bucket, where the comparison (all 32 bits) must tell them apart. For every bit: ADD r, ADD r with bit b flipped (must be OK, not DUPREF), EXEC the flipped one (must find it), DELETE the first; also reference 0 (the value an empty entry holds)."""
    ev = []; base = 0x13579BDF
    for b in range(32):
        r1 = base ^ (b * 0x01010101 & G.M); r2 = r1 ^ (1 << b)
        ev += [dict(t=G.ADD, ref=r1, sym=0, side=0, px=100 + b, sh=7), dict(t=G.ADD, ref=r2, sym=0, side=1, px=200 + b, sh=3), dict(t=G.EXEC, ref=r2, sh=1), dict(t=G.DELETE, ref=r1), dict(t=G.DELETE, ref=r2)]
    ev += [dict(t=G.EXEC, ref=0, sh=1), dict(t=G.ADD, ref=0, sym=0, side=0, px=5, sh=2), dict(t=G.EXEC, ref=0, sh=1), dict(t=G.DELETE, ref=0), dict(t=G.EXEC, ref=0, sh=1), dict(t=G.DELETE, ref=0)]
    return ev
def make(kind, seed, n, ns, d, nb, k):
    rng = random.Random(seed)
    if kind == "near": ev = near_miss(nb, k)
    elif kind == "wide": ev = widen(G.gen_events(rng, n, ns, d, nb, k, spread=d + 1, faults=0.1))
    else: ev = G.gen_events(rng, n, ns, d, nb, k, spread=d + 1, faults=0.1) if kind == "flow" else random_events(rng, n, ns, d, nb, k)
    return G.run(ev, ns, d, nb, k, gaps=[rng.choice([0, 0, 0, 1, 4]) for _ in ev]), ev
def battery():
    """The mutation runs' test: five sizes, flow with faults and random events, Icarus. -> None or the first difference."""
    for ci, (ns, d, nb, k) in enumerate(CONFIGS):
        for kind in ("flow", "random", "wide", "near"):
            for seed in range(1 if kind == "near" else 2):
                try: res, _ = make(kind, seed + ci, 150, ns, d, nb, k); ok = same(res, ns, d, nb, k)
                except Exception as x: return f"crash {type(x).__name__}"
                if not ok: return f"{kind}, NS {ns}, D {d}, NB {nb}, K {k}"
    return None
def battery_model():
    """The model's own test: its hand-checked scenarios. -> None or a description."""
    q = subprocess.run([sys.executable, "model/book2_gold.py"], cwd=R, capture_output=True, text=True, timeout=300)
    return None if q.returncode == 0 else "hand-checked scenarios"
def adversarial(d, k):
    """The two longest events the rules allow, built: one symbol, bid levels of one order each. (A) d levels; the order at the best level is REPLACEd by one at a price better than all (the deletion shifts d - 1 levels up, the addition d - 1 levels down). (B) the worst level holds two orders and one of them is REPLACEd at the same price (a search to the end of the levels twice, no shifts). -> ([events of A, events of B], nb)"""
    nb = 1
    while nb < d + 5: nb *= 2
    base = [dict(t=G.ADD, ref=i + 1, sym=0, side=0, px=10 + i, sh=5) for i in range(d)]               # level i holds ref i + 1; the best (highest) is the last
    A = base + [dict(t=G.REPLACE, ref=d, ref2=d + 1, px=10 + d + 5, sh=5)]
    B = base + [dict(t=G.ADD, ref=d + 2, sym=0, side=0, px=10, sh=5), dict(t=G.REPLACE, ref=d + 2, ref2=d + 3, px=10, sh=5)]
    return [A, B], nb
def latency_rows():
    """-> list of (d, k, longest event in the model by search, the closed form, the adversarial event's cycles, RTL equal)."""
    out = []
    for d, k in ((1, 1), (2, 2), (4, 4), (8, 4), (8, 1)):
        evs, nb = adversarial(d, k); ress = [G.run(ev, 1, d, nb, k) for ev in evs]; n_adv = max(r["took"][-1][2] for r in ress)
        rng = random.Random(d * 10 + k); worst = 0
        for seed in range(30):
            e2 = G.gen_events(rng, 200, 1, d, nb, k, spread=d + 1, faults=0.1, collide=0.1); worst = max(worst, max(c for _, _, c in G.run(e2, 1, d, nb, k)["took"]))
        out.append((d, k, worst, G.worst_case(d, k), n_adv, all(same(r, 1, d, nb, k) for r in ress)))
    return out
if __name__ == "__main__":
    if "--battery-model" in sys.argv: print("RESULT", battery_model()); sys.exit(0)
    if "--battery" in sys.argv: print("RESULT", battery()); sys.exit(0)
    print("== 1. lint gate (Verilator -Wall --lint-only, Yosys 'check')")
    p = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", "book2", "rtl/book2.sv"], cwd=R, capture_output=True, text=True); w = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning") and "DECLFILENAME" not in l]
    y = subprocess.run(["yosys", "-p", "read_verilog -sv rtl/book2.sv; hierarchy -top book2; proc; opt_clean; check"], cwd=R, capture_output=True, text=True).stdout
    print(f"  book2: Verilator warnings {len(w)}, Yosys check problems {len([l for l in y.splitlines() if 'Found and reported' in l and ' 0 problems' not in l])}")
    print("\n== 2. the model (python3 model/book2_gold.py) and what the stimulus contains (8 seeds of 300 events, NS 2, D 4, NB 4, K 2)")
    print("  " + subprocess.run([sys.executable, "model/book2_gold.py"], cwd=R, capture_output=True, text=True).stdout.strip())
    for kind in ("flow", "random", "wide", "near"):
        c = Counter(); t = Counter()
        for seed in range(8):
            res, ev = make(kind, seed, 300, 2, 4, 4, 2)
            for r in res["rows"]:
                if r[1]: c[G.RN[r[1][0]]] += 1
            for e in ev: t[G.TN[e["t"]]] += 1
        print(f"  {kind:7s} events: " + ", ".join(f"{k} {v}" for k, v in sorted(t.items())) + "  | results: " + ", ".join(f"{k} {v}" for k, v in sorted(c.items(), key=lambda kv: G.RN.index(kv[0]))))
    print("\n== 3. the book against the cycle model: every result with the top of book of its symbol, and `ready`, in every cycle; 4 seeds of 300 events per row")
    print(f"  {'events':7s} {'NS':>2s} {'D':>2s} {'NB':>2s} {'K':>2s} | {'cycles':>7s} {'results':>8s} {'OK':>5s} {'rejected':>9s} | {'Icarus':>9s} {'Verilator':>10s}")
    for kind in ("flow", "random", "wide", "near"):
        for ns, d, nb, k in CONFIGS:
            ok = 0; cyc = nres = nok = 0; v = "-"
            for seed in range(4):
                res, ev = make(kind, seed, 300, ns, d, nb, k); ok += same(res, ns, d, nb, k); cyc += res["cycles"]
                for r in res["rows"]:
                    if r[1]: nres += 1; nok += r[1][0] == G.OK
                if seed == 0: v = "PASS" if same(res, ns, d, nb, k, "verilator") else "FAIL"
            print(f"  {kind:7s} {ns:2d} {d:2d} {nb:2d} {k:2d} | {cyc:7d} {nres:8d} {nok:5d} {nres - nok:9d} | {ok:6d} of 4 {v:>10s}")
    print("\n== 4. the longest event: the closed form of the model, the longest event seen in 30 x 200 random events of flow, and the longer of the two constructed events (see `adversarial`), which the RTL also executes cycle for cycle")
    print(f"  {'D':>2s} {'K':>2s} | {'closed form':>11s} {'constructed':>11s} {'random flow, longest':>20s} | RTL = model")
    for d, k, worst, cf, adv, ok in latency_rows(): print(f"  {d:2d} {k:2d} | {cf:11d} {adv:11d} {worst:20d} | {'PASS' if ok else 'FAIL'}" + ("" if adv == cf and worst <= cf else "   <-- MISMATCH"))
