#!/usr/bin/env python3
"""Chapter 15: the running designs. (1) lint; (2) the model: hand-checked scenarios and TRANSPARENCY (the split equals the single state machine) over streams, software latencies, queue depths and both policies; (3) tcp_split against the cycle model, cycle for cycle, in two simulators."""
import os, random, statistics as st, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, split_gold as S, tcp_gold as G
R = flow.ROOT; F = ["rtl/split.sv", "rtl/tcp.sv", "tb/split_tb.sv"]
def rtl_rows(r, cidw, depth, policy, simu="icarus", extra=()):
    n = S.write_stim(os.path.join(R, "out", "split_stim.hex"), r, cidw)
    d = (f"NC={n}", f"CIDW={cidw}", f"DEPTH={depth}", f"POLICY={policy}") + tuple(extra)
    o = (flow.sim_icarus if simu == "icarus" else flow.sim_verilator)(F, "split_tb", defines=d)[1]
    return [tuple(l.split()[1:]) for l in o.splitlines() if l.startswith("C ")], o
def same(r, cidw, depth, policy, simu="icarus"):
    rows, _ = rtl_rows(r, cidw, depth, policy, simu); exp = [tuple(str(x) for x in e) for e in S.expected_rows(r, cidw)]; return rows == exp
def streams(kind, seed, ncid):
    if kind == "realistic": return S.with_decoys(G.realistic_events(seed, conns=ncid, per_conn=40, p_odd=0.05), ncid)
    if kind == "random": return G.gen_events(seed, 400, cids=ncid)
    return S.with_decoys(G.directed_events(0) + G.gen_events(seed, 100, cids=ncid), ncid)
def gaps_for(n, seed, mx): rg = random.Random(seed); return [rg.randint(0, mx) for _ in range(n)]
if __name__ == "__main__":
    print("== 1. lint gate (Verilator -Wall --lint-only, Yosys 'check')")
    for top in ("tcp_split", "tcp_split_syn"):
        p = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", top, "rtl/split.sv", "rtl/tcp.sv"], cwd=R, capture_output=True, text=True); w = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning") and "DECLFILENAME" not in l]
        y = subprocess.run(["yosys", "-p", f"read_verilog -sv rtl/split.sv rtl/tcp.sv; hierarchy -top {top}; proc; opt_clean; check"], cwd=R, capture_output=True, text=True).stdout
        print(f"  {top:14s} Verilator warnings: {len(w)}   Yosys check problems: {len([l for l in y.splitlines() if 'Found and reported' in l and ' 0 problems' not in l])}")
    print("\n== 2. the model: hand-checked scenarios, then TRANSPARENCY: the dispatcher and the software together equal the single state machine of Chapter 12 on the events consumed (same segments sent, same bytes delivered, same final state), for any software timing")
    print("  " + subprocess.run([sys.executable, "model/split_gold.py"], cwd=R, capture_output=True, text=True).stdout.strip())
    print(f"  {'stream':10s} {'policy':>6s} {'latency':>14s} {'depth':>5s} {'runs':>5s} {'events':>7s} {'hot':>6s} {'punted':>7s} {'of which collateral':>20s} {'dropped':>8s} {'transparent':>12s}")
    for kind in ("realistic", "random", "directed"):
        for policy in (0, 1):
            for lat, depth in ((1, 4), (8, 4), (8, 2), (40, 8), ("jitter", 4)):
                ok = 0; ne = nh = npu = nc = nd = 0; runs = 6
                for seed in range(runs):
                    ev = streams(kind, seed, 4); L = lat if lat != "jitter" else (lambda rg: rg.choice([1, 2, 5, 20, 90]))
                    r = S.run(ev, 4, depth, policy, lat=L, gaps=gaps_for(len(ev), seed, 3), seed=seed)
                    ok += S.reference_check(r) is None; ne += len(ev); nh += r["path"].count(0); npu += r["path"].count(1); nc += r["collateral"]; nd += r["dropped"]
                print(f"  {kind:10s} {policy:6d} {str(lat):>14s} {depth:5d} {runs:5d} {ne:7d} {nh:6d} {npu:7d} {nc:20d} {nd:8d} {ok:9d} of {runs}")
    print("  (hot = handled in hardware; punted = sent to software; collateral = punted only because an earlier event of the same connection was pending, though the single state machine would have taken it on the fast path; dropped = POLICY 1 with the FIFO full)")
    print("\n== 3. tcp_split against the cycle model: every output after every edge, including the head of the punt FIFO")
    print("  (in the configurations with a FIFO of 2 or 3 entries, software also pops the FIFO when it is empty in one cycle in five: the pop must be ignored)")
    print(f"  {'stream':10s} {'CIDW':>4s} {'depth':>5s} {'policy':>6s} {'latency':>8s} | {'runs':>4s} {'cycles':>7s} {'stalled':>8s} {'dropped':>8s} | {'Icarus':>9s} {'Verilator':>10s}")
    for kind in ("realistic", "random", "directed"):
        for cidw, depth, policy, lat in ((2, 4, 0, 6), (2, 2, 0, 24), (3, 4, 1, 12), (2, 3, 1, 3), (3, 8, 0, 1)):
            ok = 0; cyc = stl = drp = 0; v = "-"; runs = 4
            for seed in range(runs):
                ev = streams(kind, seed + 20, 1 << cidw); r = S.run(ev, 1 << cidw, depth, policy, lat=lat, gaps=gaps_for(len(ev), seed, 2), seed=seed, record=True, spurious=0.2 if depth in (2, 3) else 0.0)
                ok += same(r, cidw, depth, policy); cyc += r["cycles"]; stl += r["stall"]; drp += r["dropped"]
                if seed == 0: v = "PASS" if same(r, cidw, depth, policy, "verilator") else "FAIL"
            print(f"  {kind:10s} {cidw:4d} {depth:5d} {policy:6d} {lat:8d} | {runs:4d} {cyc:7d} {stl:8d} {drp:8d} | {ok:6d} of {runs} {v:>10s}")
