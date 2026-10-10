#!/usr/bin/env python3
"""Chapter 22: the running designs. (1) lint; (2) the model: hand-checked scenarios and the PROPERTIES of the arithmetic checked on 200,000 random books (the microprice lies between the two prices, the imbalance in [-1, 1], the error bounds that follow from rounding w, the near-antisymmetry); (3) the signal unit against the bit-exact model, every output bit in every cycle, in two simulators, for five formats (price bits, share bits, fraction bits) and both dividers, on random books (with gaps and bursts), and on directed books: every combination of prices and shares from a set that holds the boundaries, and books whose division lands exactly on a half unit (where the rounding rule decides)."""
import os, random, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, sig_gold as G
R = flow.ROOT; F_ = ["rtl/sig.sv", "tb/sig_tb.sv"]
def rows_rtl(res, cfg, simu="icarus", rtl=F_):
    pw, qw, f, div = cfg; n = G.write_stim(os.path.join(R, "out", "sig_stim.hex"), res["lines"])
    o = (flow.sim_icarus if simu == "icarus" else flow.sim_verilator)(rtl, "sig_tb", defines=(f"NC={n}", f"PW={pw}", f"QW={qw}", f"F={f}", f"DIV={div}"))[1]
    try: return [tuple(int(x) for x in l.split()[1:]) for l in o.splitlines() if l.startswith("C ")]
    except ValueError: return [("x",)]
def same(msgs, gaps, cfg, simu="icarus", rtl=F_):
    res = G.run(msgs, *cfg, gaps=gaps); got = rows_rtl(res, cfg, simu, rtl); exp = G.expected_rows(res); return got[:len(exp)] == exp and len(got) >= len(exp)
CONFIGS = [(24, 20, 12, 1), (24, 20, 12, 0), (12, 8, 4, 1), (20, 16, 9, 0), (30, 22, 16, 1)]
def make(kind, seed, n, cfg):
    pw, qw, f, div = cfg; rng = random.Random(seed)
    if kind == "edge": m = G.edge_books(pw, qw) + G.half_books(pw, qw, f); return m, [0] * len(m)
    m = G.random_books(rng, n, pw, qw)
    if kind == "burst": return m, [0] * n
    return m, [rng.choice([0, 0, 1, 3, 20, 40]) for _ in m]
KINDS = ("random", "burst", "edge")
def battery():
    """The mutation runs' test: five formats, the three kinds, Icarus. -> None or the first difference."""
    for ci, cfg in enumerate(CONFIGS):
        for kind in KINDS:
            if kind == "edge" and ci not in (0, 2, 3): continue
            for seed in range(1 if kind == "edge" else 2):
                try: m, g = make(kind, seed + ci, 150, cfg); ok = same(m, g, cfg)
                except Exception as x: return f"crash {type(x).__name__}"
                if not ok: return f"{kind}, PW {cfg[0]}, QW {cfg[1]}, F {cfg[2]}, DIV {cfg[3]}"
    return None
def battery_model():
    """The model's own test: its hand-checked scenarios. -> None or a description."""
    q = subprocess.run([sys.executable, "model/sig_gold.py"], cwd=R, capture_output=True, text=True, timeout=300)
    return None if q.returncode == 0 else "hand-checked scenarios"
def properties(n=200000, seed=7):
    """The arithmetic's own properties on random books, in the model: -> dict of counts of violations and the worst errors seen (in units of 2^-F for the imbalance, of ticks / 2^(F+1) per tick of spread for the microprice)."""
    rng = random.Random(seed); bad = dict(micro_range=0, imb_range=0, imb_err=0, micro_err=0, antisym=0, w_range=0); worst_i = worst_m = 0.0; cnt = 0
    for (b, bs, a, as_) in G.random_books(rng, n, 24, 20):
        for F in (8, 12):
            ok, m2, s, cr, lk, w, imb, mic = G.compute(b, bs, a, as_, F)
            if not ok: continue
            cnt += 1; i_ideal, mic_ideal, _ = G.ideal(b, bs, a, as_)
            if not 0 <= w <= 1 << F: bad["w_range"] += 1
            if not -(1 << F) <= imb <= (1 << F): bad["imb_range"] += 1
            lo, hi = sorted((b, a))
            if not lo << F <= mic <= hi << F: bad["micro_range"] += 1
            ei = abs(imb / (1 << F) - float(i_ideal)) * (1 << F); em = abs(mic / (1 << F) - float(mic_ideal)); worst_i = max(worst_i, ei); worst_m = max(worst_m, em / max(1, abs(s)) * (1 << (F + 1)))
            if ei > 1 + 1e-9: bad["imb_err"] += 1
            if em > abs(s) / (1 << (F + 1)) + 1e-12: bad["micro_err"] += 1
            w2 = G.compute(b, as_, a, bs, F)[5]
            if w + w2 not in (1 << F, (1 << F) + 1): bad["antisym"] += 1
    return bad, worst_i, worst_m, cnt
if __name__ == "__main__":
    if "--battery-model" in sys.argv: print("RESULT", battery_model()); sys.exit(0)
    if "--battery" in sys.argv: print("RESULT", battery()); sys.exit(0)
    print("== 1. lint gate (Verilator -Wall --lint-only, Yosys 'check')")
    for div in (0, 1):
        p = subprocess.run(["verilator", "--lint-only", "-Wall", f"-GDIV={div}", "--top-module", "sig", "rtl/sig.sv"], cwd=R, capture_output=True, text=True); w = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning") and "DECLFILENAME" not in l]
        y = subprocess.run(["yosys", "-p", f"read_verilog -sv rtl/sig.sv; chparam -set DIV {div} sig; hierarchy -top sig; proc; opt_clean; check"], cwd=R, capture_output=True, text=True).stdout
        print(f"  sig DIV {div}: Verilator warnings {len(w)}, Yosys check problems {len([l for l in y.splitlines() if 'Found and reported' in l and ' 0 problems' not in l])}")
    print("\n== 2. the model (python3 model/sig_gold.py) and the properties of the arithmetic on random books")
    print("  " + subprocess.run([sys.executable, "model/sig_gold.py"], cwd=R, capture_output=True, text=True).stdout.strip())
    bad, wi, wm, cnt = properties()
    print(f"  {cnt} (book, F) cases with both sides present, F = 8 and 12: violations of  0 <= w <= 2^F: {bad['w_range']};  |imbalance| <= 1: {bad['imb_range']};  microprice between the two prices: {bad['micro_range']};")
    print(f"  imbalance error <= 1 unit of 2^-F: {bad['imb_err']} violations (worst {wi:.4f} units); microprice error <= spread / 2^(F+1): {bad['micro_err']} violations (worst {wm:.4f} of the bound per tick of spread);  w(Qb, Qa) + w(Qa, Qb) is 2^F or 2^F + 1: {bad['antisym']} violations")
    print("\n== 3. the unit against the model: every output in every cycle; 4 seeds of 150 messages per row (edge: the directed set, 2,916 books)")
    print(f"  {'books':7s} {'PW':>3s} {'QW':>3s} {'F':>3s} {'DIV':>3s} | {'cycles':>7s} {'answers':>8s} {'not ok':>7s} {'crossed':>8s} | {'Icarus':>9s} {'Verilator':>10s}")
    for kind in KINDS:
        for cfg in CONFIGS:
            ok = ncyc = nans = nno = ncr = 0; v = "-"; seeds = 1 if kind == "edge" else 4
            for seed in range(seeds):
                m, g = make(kind, seed, 150, cfg); res = G.run(m, *cfg, gaps=g); ok += same(m, g, cfg); ncyc += len(res["rows"])
                for r in res["rows"]:
                    if r[1]: nans += 1; nno += r[1][0] == 0; ncr += r[1][3]
                if seed == 0: v = "PASS" if same(m, g, cfg, "verilator") else "FAIL"
            print(f"  {kind:7s} {cfg[0]:3d} {cfg[1]:3d} {cfg[2]:3d} {cfg[3]:3d} | {ncyc:7d} {nans:8d} {nno:7d} {ncr:8d} | {ok:6d} of {seeds} {v:>10s}")
