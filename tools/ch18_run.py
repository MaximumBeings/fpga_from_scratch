#!/usr/bin/env python3
"""Chapter 18: the running designs. (1) lint; (2) the model: hand-checked scenarios and the END-TO-END PROPERTY in a closed loop with lossy, duplicating, reordering A and B feeds and a retransmission server (the messages forwarded tile the sequence space in order, every skipped range reported); (3) seq_arb against the cycle model, every output and the state after every cycle, in two simulators, for several sizes of window and timer and with the sequence numbers about to wrap, on closed-loop runs and on RANDOM inputs (which reach the cases the loop does not: overlaps, full slots)."""
import os, random, statistics as st, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, arb_gold as G
R = flow.ROOT; F = ["rtl/seq_arb.sv", "tb/arb_tb.sv"]
def rtl_rows(res, pend, to, to2, init, simu="icarus", rtl=F):
    n = G.write_stim(os.path.join(R, "out", "arb_stim.hex"), res["lines"])
    o = (flow.sim_icarus if simu == "icarus" else flow.sim_verilator)(rtl, "arb_tb", defines=(f"NC={n}", f"PEND={pend}", f"TO={to}", f"TO2={to2}", f"INIT={init}") + (("GARBAGE",) if simu == "icarus" else ()))[1]
    try: return [tuple(int(x) for x in l.split()[1:]) for l in o.splitlines() if l.startswith("C ")]
    except ValueError: return [("x",)]
def same(res, pend, to, to2, init, simu="icarus", rtl=F):
    got = rtl_rows(res, pend, to, to2, init, simu, rtl); exp = G.expected_rows(res); return got[:len(exp)] == exp and len(got) >= len(exp)
PROFILES = {"clean": dict(), "loss 5% each": dict(la=.05, lb=.05), "loss 20% each": dict(la=.2, lb=.2), "A lossy, B clean": dict(la=.3, lb=0), "loss 30% each, retransmissions lost half the time": dict(la=.3, lb=.3, rl=.5), "duplicates 20%, B 6 cycles late": dict(dup=.2, skew=6), "loss 50% each, retransmissions lost half the time": dict(la=.5, lb=.5, rl=.5)}
def closed(seed, n, prof, init=1, pend=4, to=16, to2=64, rt=30):
    rng = random.Random(seed); src = G.make_source(rng, n, init); arr = G.arrivals(rng, src, prof.get("la", 0), prof.get("lb", 0), prof.get("dup", 0), jitter=prof.get("jitter", 3), skew=prof.get("skew", 0))
    return G.run(arr, init, pend, to, to2, rt, prof.get("rl", 0), seed), src, arr
def random_inputs(seed, n, init=1, pend=4, to=16, to2=64):
    """Random packets near a slowly advancing cursor: behind, equal, ahead, overlapping, heartbeats, duplicates; no contract."""
    rng = random.Random(seed); cur = init & G.M; arr = []; t = 0
    for _ in range(n):
        t += rng.choice([0, 0, 1, 1, 2, 5, 30]); off = rng.choice([0, 0, 0, 1, 2, 5, 12, 40, -1, -3, -10, 0x7FFFFFFF]); c = rng.choice([0, 1, 3, 7, 20, 0xFFFF]) if rng.random() < .15 else rng.randint(1, 12)
        arr.append((t, rng.randrange(3), (cur + off) & G.M, c))
        if rng.random() < .5: cur = (cur + rng.randint(1, 10)) & G.M
    return G.run(arr, init, pend, to, to2, 20, 0.3, seed)
CONFIGS = [(4, 16, 64, 1), (2, 8, 24, 0xFFFFFF00), (8, 20, 40, 1), (1, 6, 12, 0xFFFFFFF0), (4, 20, 8, 1)]       # the last has TO2 < TO: the skip must still wait for a request
def battery():
    """The mutation runs' test: four configurations, closed-loop runs and random inputs, Icarus. -> None or the first difference."""
    for ci, (pend, to, to2, init) in enumerate(CONFIGS):
        for kind in ("closed", "random"):
            for seed in range(2):
                res = closed(seed + ci, 60, PROFILES["loss 30% each, retransmissions lost half the time"], init, pend, to, to2)[0] if kind == "closed" else random_inputs(seed + 7 * ci, 150, init, pend, to, to2)
                try: ok = same(res, pend, to, to2, init)
                except Exception as x: return f"crash {type(x).__name__}"
                if not ok: return f"{kind}, PEND {pend}, TO {to}, TO2 {to2}, INIT {init:#x}"
    return None
def battery_model():
    """The model's own test (mutation runs): its hand-checked scenarios, and the end-to-end property on closed-loop runs. -> None or a description."""
    q = subprocess.run([sys.executable, "model/arb_gold.py"], cwd=R, capture_output=True, text=True, timeout=300)
    if q.returncode != 0: return "hand-checked scenarios"
    for nm in ("loss 20% each", "loss 30% each, retransmissions lost half the time", "duplicates 20%, B 6 cycles late"):
        for seed in range(3):
            res, src, arr = closed(seed, 80, PROFILES[nm]); e = G.check_stream(res)
            if e: return f"{nm}: {e}"
    return None
if __name__ == "__main__":
    if "--battery-model" in sys.argv: print("RESULT", battery_model()); sys.exit(0)
    if "--battery" in sys.argv: print("RESULT", battery()); sys.exit(0)
    print("== 1. lint gate (Verilator -Wall --lint-only, Yosys 'check')")
    for top in ("seq_arb", "seq_arb_syn"):
        p = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", top, "rtl/seq_arb.sv"], cwd=R, capture_output=True, text=True); w = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning") and "DECLFILENAME" not in l]
        y = subprocess.run(["yosys", "-p", f"read_verilog -sv rtl/seq_arb.sv; hierarchy -top {top}; proc; opt_clean; check"], cwd=R, capture_output=True, text=True).stdout
        print(f"  {top:12s} Verilator warnings: {len(w)}   Yosys check problems: {len([l for l in y.splitlines() if 'Found and reported' in l and ' 0 problems' not in l])}")
    print("\n== 2. the model: hand-checked scenarios, then the END-TO-END PROPERTY in a closed loop: 10 seeds of 200 packets per profile (PEND 4, TO 16, TO2 64, retransmission answered after 30 cycles); the messages forwarded must tile the sequence space in order, with every skipped range reported")
    print("  " + subprocess.run([sys.executable, "model/arb_gold.py"], cwd=R, capture_output=True, text=True).stdout.strip())
    print(f"  {'profile':52s} | {'tiled':>7s} {'forwarded':>10s} {'requests':>9s} {'skips':>6s} {'messages lost':>14s} {'OVF':>5s} {'undelivered at the end':>23s}")
    for nm, prof in PROFILES.items():
        ok = 0; fw = rq = sk = lost = ovf = tl = 0
        for seed in range(10):
            res, src, arr = closed(seed, 200, prof); ok += G.check_stream(res) is None; fw += len(res["forwarded"]); rq += len(res["reqs"]); sk += len(res["skips"]); lost += sum(n for _, _, n in res["skips"]); tl += G.tail(res, arr)[0]
            ovf += sum(1 for r in res['rows'] if r[1] and r[1][0] == G.OVF)
        print(f"  {nm:52s} | {ok:4d} of 10 {fw:10d} {rq:9d} {sk:6d} {lost:14d} {ovf:5d} {tl:23d}")
    print("  (undelivered at the end: messages that arrived on A or B beyond where the forwarding stopped; the last packets of the stream, dropped because the slots were full, have nothing after them to reveal the loss)")
    print("\n== 3. seq_arb against the cycle model: every output and the state after every cycle, 3 seeds per row")
    print(f"  {'inputs':11s} {'PEND':>4s} {'TO':>3s} {'TO2':>4s} {'INIT':>10s} | {'cycles':>7s} {'FWD':>5s} {'STORE':>6s} {'DUP':>5s} {'BAD':>4s} {'OVF':>4s} {'HB':>3s} {'REL':>4s} {'REQ':>4s} {'SKIP':>5s} | {'Icarus':>9s} {'Verilator':>10s}")
    for kind in ("closed loop", "random"):
        for (pend, to, to2, init) in CONFIGS:
            ok = 0; cyc = 0; cnt = {}; v = "-"
            for seed in range(3):
                res = closed(seed, 80, PROFILES["loss 30% each, retransmissions lost half the time"], init, pend, to, to2)[0] if kind == "closed loop" else random_inputs(seed, 200, init, pend, to, to2)
                ok += same(res, pend, to, to2, init); cyc += res["cycles"]
                for r in res["rows"]:
                    if r[1]: cnt[G.KN[r[1][0]]] = cnt.get(G.KN[r[1][0]], 0) + 1
                    if r[2]: cnt["REQ" if r[2][0] == G.REQ else "SKIP"] = cnt.get("REQ" if r[2][0] == G.REQ else "SKIP", 0) + 1
                if seed == 0: v = "PASS" if same(res, pend, to, to2, init, "verilator") else "FAIL"
            print(f"  {kind:11s} {pend:4d} {to:3d} {to2:4d} {init:#10x} | {cyc:7d} " + " ".join(f"{cnt.get(k, 0):{w}d}" for k, w in (("FWD", 5), ("STORE", 6), ("DUP", 5), ("BAD", 4), ("OVF", 4), ("HB", 3), ("REL", 4), ("REQ", 4), ("SKIP", 5))) + f" | {ok:6d} of 3 {v:>10s}")
