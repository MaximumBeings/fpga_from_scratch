#!/usr/bin/env python3
"""Chapter 10: the running designs. (1) lint; (2) the model's hand-checked cases; (3) the three CAM engines (exact, ternary, range) against the specification: 3 modes x 3 sizes x 6 seeds in Icarus, one run each in Verilator; (4) the hash engines (one and two tables, exact and fingerprint) against the control plane's structure, four key types; (5) latency and one query per cycle; (6) multicast: the 28-bit group id against the 23 bits a MAC address keeps. Usage: ch10_run.py"""
import os, random, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, match_gold as g
R = flow.ROOT; F = ["rtl/match.sv", "tb/match_tb.sv"]; NM = ["exact CAM", "ternary CAM", "range matcher"]
def res(o): return [(int(a), int(b)) for a, b in re.findall(r"RES (\d+) (\d+)", o)]
def run(lines, eng, sim="icarus", **kw):
    n = g.write_stim(os.path.join(R, "out", "match_stim.hex"), lines); d = (f"NC={n}", f"ENG={eng}") + tuple(f"{k}={v}" for k, v in kw.items()); f = flow.sim_icarus if sim == "icarus" else flow.sim_verilator
    return f(F, "match_tb", defines=d)[1]
if __name__ == "__main__":
    print("== 1. lint gate (Verilator -Wall --lint-only, Yosys 'check')")
    for top in ("match_cam", "hash_tab"):
        p = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", top, "rtl/match.sv"], cwd=R, capture_output=True, text=True); w = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning")]
        y = subprocess.run(["yosys", "-p", f"read_verilog -sv rtl/match.sv; hierarchy -top {top}; proc; opt_clean; check"], cwd=R, capture_output=True, text=True).stdout
        print(f"  {top:10s} Verilator warnings: {len(w)}   Yosys check problems: {len([l for l in y.splitlines() if 'Found and reported' in l and ' 0 problems' not in l])}")
    e = [(0x0A000000, 0xFF000000, 1, 1), (0x0A010000, 0xFFFF0000, 2, 1), None]
    print("\n== 2. the model's hand-checked cases (priority and the range edges)")
    print(f"  ternary 10.0.0.0/8 in slot 0 and 10.1.0.0/16 in slot 1: 10.1.2.3 -> {g.cam_lookup(g.TERNARY, e, 0x0A010203)} (the LOWEST slot wins, though slot 1 is more specific); 11.0.0.0 -> {g.cam_lookup(g.TERNARY, e, 0x0B000000)}")
    rg = [(0, 80 | (90 << 16), 7, 1)]; print(f"  range [80, 90]: 80 -> {g.cam_lookup(g.RANGE, rg, 80)}, 90 -> {g.cam_lookup(g.RANGE, rg, 90)}, 79 -> {g.cam_lookup(g.RANGE, rg, 79)}, 91 -> {g.cam_lookup(g.RANGE, rg, 91)}; an empty range [90, 80]: 85 -> {g.cam_lookup(g.RANGE, [(0, 90 | (80 << 16), 7, 1)], 85)}")
    print("\n== 3. the CAM engines against the specification (writes, deletes and queries interleaved; idle cycles carry junk; every query's expected result is taken at that point of the sequence)")
    print(f"  {'engine':14s} {'slots':>5s} {'queries':>8s} {'hits':>6s} {'multi-match':>11s} | {'Icarus 6 seeds':>14s} {'Verilator':>10s}")
    for mode in (0, 1, 2):
        for n in (8, 16, 32):
            ok = 0; nq = nh = nm = 0; v = "-"
            for seed in range(6):
                lines, exp = g.cam_ops(seed, mode, n, clear=seed % 2 == 0); o = run(lines, mode, N=n); ok += res(o) == exp; nq += len(exp); nh += sum(h for h, _ in exp)
                if seed == 0: v = "PASS" if res(run(lines, mode, "verilator", N=n)) == exp else "FAIL"
            # multi-match: queries for which more than one valid slot matches (computed by replaying the model)
            for seed in range(6):
                rng = random.Random(seed * 7919 + mode); lines, exp = g.cam_ops(seed, mode, n, clear=seed % 2 == 0); ent = [None] * n; cnt = 0
                for l in lines:
                    t = int(l[0], 16); a = int(l[2:6], 16); k = int(l[6:14], 16); ax = int(l[14:22], 16); vl = int(l[22:24], 16); vd = int(l[24], 16)
                    if t == 1: ent[a] = (k, ax, vl, 1) if vd else None
                    elif t == 2: cnt += sum(1 for x in ent if x and g.cam_match(mode, x, k)) > 1
                nm += cnt
            print(f"  {NM[mode]:14s} {n:5d} {nq:8d} {nh:6d} {nm:11d} | {ok:11d} of 6 {v:>10s}")
    print("\n== 4. the hash engines against the control plane's structure (the table is cleared, filled to a load, queried, 25% deleted, refilled, queried again)")
    print(f"  {'tables x slots':>14s} {'stored key':>10s} {'key type':>8s} {'load':>6s} {'placed':>7s} {'failed':>7s} {'queries':>8s} {'hits':>6s} | {'Icarus 4 seeds':>14s} {'Verilator':>10s}")
    for ch, aw, kw in ((1, 7, 32), (2, 6, 32), (2, 6, 16), (1, 7, 12)):
        for kind in ("random", "seq", "mcast", "stride"):
            ok = 0; st = None; nq = nh = 0; v = "-"; pl = fl = 0
            for seed in range(4):
                lines, exp, st = g.hash_ops(seed, aw, ch, kw, int(0.8 * ch * (1 << aw)), kind, 250); o = run(lines, 2 + ch, AW=aw, KW=kw); ok += res(o) == exp; nq += len(exp); nh += sum(h for h, _ in exp); pl += st["placed"]; fl += st["failed"]
                if seed == 0: v = "PASS" if res(run(lines, 2 + ch, "verilator", AW=aw, KW=kw)) == exp else "FAIL"
            print(f"  {ch} x {1 << aw:<9d} {kw:7d} bit {kind:>8s} {'80%':>6s} {pl // 4:7d} {fl // 4:7d} {nq:8d} {nh:6d} | {ok:11d} of 4 {v:>10s}")
    print("  (placed and failed are per run, rounded down: 'failed' = keys the control plane could not place in either slot; the hardware must answer miss for them. 'stride' = multiples of 4,096, 'mcast' = 224.0.0.0/4, 'seq' = consecutive addresses.)")
    print("\n== 5. latency and throughput: a query in every cycle")
    for eng, kw, nm in ((0, {"N": 16}, "exact CAM"), (2, {"N": 16}, "range matcher"), (4, {"AW": 6}, "two-table hash")):
        rng = random.Random(5); lines = []; exp = []
        if eng == 4: hp = g.HashPlane(6, 2); lines = hp.clear_lines(); ks = []
        else: ks = []
        if eng == 4:
            for _ in range(80):
                k = rng.getrandbits(32); w, ok = hp.insert(k, rng.getrandbits(8)); lines += w; ks.append(k) if ok else None
            qs = [rng.choice(ks) if rng.random() < .5 else rng.getrandbits(32) for _ in range(300)]; exp = [hp.lookup(q) for q in qs]
        else:
            ents = [None] * 16
            for a in range(16): lines.append(g.line(1, 0, a, 0, 0, 0, 0))
            for a in range(10):
                e = (rng.getrandbits(32), (rng.getrandbits(16) | (0xFFFF << 16)) if eng == 2 else 0, rng.getrandbits(8), 1); ents[a] = e; lines.append(g.line(1, 0, a, *e))
            qs = [rng.getrandbits(32) for _ in range(300)]; exp = [g.cam_lookup(eng, ents, q) for q in qs]
        n0 = len(lines); lines += [g.line(2, 0, 0, q, 0, 0, 0) for q in qs]; o = run(lines, eng, **kw); lat = int(re.search(r"LAT (\d+)", o).group(1))
        print(f"  {nm:15s}: {len(qs)} queries in {len(qs)} consecutive cycles, {len(res(o))} results, all equal to the model: {res(o) == exp}; latency (first query to its result): {lat} cycles")
    print("\n== 6. multicast: a node subscribes to 40 IPv4 groups (224.0.0.0/4: 28 free bits). A MAC-level filter sees only the 23 low bits of the group (the MAC address 01:00:5E + 23 bits); an IP-level filter sees all 28.")
    print(f"  {'filter':26s} {'traffic':22s} {'frames':>7s} {'accepted':>9s} | {'RTL = model':>11s}")
    rng = random.Random(10); grp = [0xE0000000 | rng.getrandbits(28) for _ in range(40)]; mem = set(grp)
    traffic = {"members": [rng.choice(grp) for _ in range(300)], "random other groups": [0xE0000000 | rng.getrandbits(28) for _ in range(300)],
               "aliases of members": [(x ^ (rng.randint(1, 31) << 23)) for x in (rng.choice(grp) for _ in range(300))]}
    for name, mask in (("IP level (28 bits)", 0x0FFFFFFF), ("MAC level (23 bits)", 0x007FFFFF)):
        hp = g.HashPlane(6, 2); lines = hp.clear_lines(); keys = {}
        for x in grp:
            k = x & mask
            if k not in keys: w, ok = hp.insert(k, 1); lines += w; keys[k] = ok
        print(f"  {name:26s} subscriptions stored: {sum(keys.values())} of {len(keys)} distinct keys ({len(grp)} groups)")
        for tn, tr in traffic.items():
            ln = list(lines); exp = []
            for x in tr: ln.append(g.line(2, 0, 0, x & mask, 0, 0, 0)); exp.append(hp.lookup(x & mask))
            o = run(ln, 4, AW=6); got = res(o); print(f"  {name:26s} {tn:22s} {len(tr):7d} {sum(h for h, _ in got):9d} | {'YES' if got == exp else 'NO':>11s}")
    print("  with the 28-bit key, only members are accepted (a key the table could not place, if any, is a miss for a member); with the 23-bit key every alias of a member is accepted: five bits of the group are lost on the wire, and no filter behind the MAC can recover them. The frame must be checked again at the IP level.")
