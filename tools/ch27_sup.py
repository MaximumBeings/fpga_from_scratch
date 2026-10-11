#!/usr/bin/env python3
"""Chapter 27, part 1: the supervisor and the reset generator on their own, against model/sup_gold.py, in two simulators, for four parameter sets, on scenarios: the sweep of every cause alone at every cycle of a run, random inputs, resets in every state, and short and long reset pulses."""
import os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, sup_gold as G
R_ = flow.ROOT; F_ = ["rtl/sup.sv", "tb/sup_tb.sv"]
CONFIGS = [(100, 100, 48, 8), (5, 4, 3, 3), (20, 7, 6, 1), (33, 40, 17, 5)]
def write_stim(path, cyc):
    with open(path, "w") as f:
        for c in cyc:
            v = c.get("go", 0) | c.get("trip", 0) << 1 | c.get("feed", 0) << 2 | c.get("slot", 0) << 3 | c.get("fault", 0) << 4 | c.get("sess", 2) << 5 | c.get("tx_ready", 1) << 8 | c.get("quiet", 1) << 9 | c.get("rst", 0) << 10 | c.get("rst_in", 0) << 11
            f.write("%03x\n" % v)
    return len(cyc)
def model_rows(cyc, cfg):
    ft, st, warm, rstn = cfg; S = G.Sup(ft, st, warm); R = G.RstGen(rstn); rows = []
    for c in cyc:
        if c.get("rst", 0): S.reset()                                                 # a synchronous reset of the supervisor: the state in this cycle is the old one, the new from the next
        ru = R.step(c.get("rst_in", 0))
        rows.append(None); rows[-1] = (ru, c)
    return rows
def run_model(cyc, cfg):
    ft, st, warm, rstn = cfg; S = G.Sup(ft, st, warm); R = G.RstGen(rstn); rows = []
    for c in cyc:
        kw = dict(go=c.get("go", 0), trip=c.get("trip", 0), feed=c.get("feed", 0), slot=c.get("slot", 0), fault=c.get("fault", 0), sess=c.get("sess", 2), tx_ready=c.get("tx_ready", 1), quiet=c.get("quiet", 1))
        ru = R.step(c.get("rst_in", 0))
        if c.get("rst", 0):
            out = (S.state, int(S.state != G.RUN), int(S.state == G.SAFE and not S.sent and kw["sess"] == G.ACTIVE and kw["tx_ready"] and kw["quiet"]), S.cause); S.reset()      # visible: the old state; the reset takes effect at the edge
        else: out = S.step(**kw)
        rows.append(out + (ru,))
    return rows
def rtl_rows(cyc, cfg, simu="icarus"):
    ft, st, warm, rstn = cfg; n = write_stim(os.path.join(R_, "out", "sup_stim.hex"), cyc)
    o = (flow.sim_icarus if simu == "icarus" else flow.sim_verilator)(F_, "sup_tb", defines=(f"NC={n}", f"FT={ft}", f"ST={st}", f"WARM={warm}", f"RSTN={rstn}") + (("GARBAGE",) if simu == "icarus" else ()))[1]
    try: return [tuple(int(x) for x in l.split()[2:]) for l in o.splitlines() if l.startswith("C ")]
    except ValueError: return [("x",)]
def same(cyc, cfg, simu="icarus"):
    got = rtl_rows(cyc, cfg, simu); exp = run_model(cyc, cfg); return got == exp
def scenarios(rng, cfg):
    ft, st, warm, rstn = cfg; out = {}
    boot = [dict(rst=1, rst_in=1)] * 2 + [dict()] * (warm + rstn + 6) + [dict(go=1, feed=1)]
    out["each_cause"] = []
    for k in range(5):
        base = boot + [dict(feed=1)] * 3
        kw = [dict(), dict(slot=1, feed=1), dict(trip=1, feed=1), dict(fault=1, feed=1), dict(sess=4, feed=1)][k]
        base += ([dict()] * (ft + 4) if k == 0 else [dict(**kw)] * (st + 3 if k == 1 else 3)) + [dict()] * 6 + [dict(rst=1)] + [dict(feed=1)] * 3
        out["each_cause"] += base
    out["boundaries"] = []
    for d in (-1, 0, 1):                                                 # a byte after ft + d silent cycles
        out["boundaries"] += boot + [dict(feed=1)] + [dict()] * (ft + d) + [dict(feed=1)] + [dict(feed=1)] * 4 + [dict()] * (ft + 8) + [dict(rst=1)] + [dict()] * 4
    for d in (-1, 0, 1):                                                 # a slot held st + d cycles
        out["boundaries"] += boot + [dict(feed=1)] + [dict(slot=1, feed=1)] * (st + d) + [dict(feed=1)] * 4 + [dict(slot=1, feed=1)] * 2 + [dict(feed=1)] * 3 + [dict(slot=1, feed=1)] * (st + 4) + [dict(rst=1)] + [dict()] * 4
    r = []
    for c in range(600):
        d = {}
        if rng.random() < .35: d["feed"] = 1
        if rng.random() < .05: d["go"] = 1
        if rng.random() < .1: d["slot"] = 1
        if rng.random() < .004: d["trip"] = 1
        if rng.random() < .004: d["fault"] = 1
        d["sess"] = 2 if rng.random() < .98 else rng.randrange(8)
        d["tx_ready"] = int(rng.random() < .8); d["quiet"] = int(rng.random() < .8)
        if rng.random() < .01: d["rst"] = 1
        if rng.random() < .01: d["rst_in"] = 1
        r.append(d)
    out["random"] = boot[:4] + r
    out["goearly"] = boot[:-1] + [dict(go=1, sess=4)] * 3 + [dict(go=1, sess=0)] + [dict(go=1, sess=2, feed=1)] + [dict(feed=1)] * 3 + [dict(go=1, trip=0, fault=0)] * 2 + [dict()] * (ft + 6) + [dict(rst=1)] + [dict(go=1)] * 3
    out["pulses"] = [dict(rst_in=1)] + [dict()] * (rstn + 6) + [dict(rst_in=1)] * 3 + [dict()] * (rstn + 6) + [dict(rst_in=1)] + [dict()] * 2 + [dict(rst_in=1)] + [dict()] * (rstn + 8)
    return out
KINDS = ("each_cause", "boundaries", "random", "goearly", "pulses")
def make(kind, ci, seed=1): return scenarios(random.Random(seed * 100 + ci), CONFIGS[ci])[kind]
def battery():
    for ci, cfg in enumerate(CONFIGS):
        for kind in KINDS:
            try: ok = same(make(kind, ci), cfg)
            except Exception as x: return f"crash {type(x).__name__}"
            if not ok: return f"{kind}, config {ci}"
    return None
def battery_model():
    import subprocess; q = subprocess.run([sys.executable, "model/sup_gold.py"], cwd=R_, capture_output=True, text=True, timeout=300)
    return None if q.returncode == 0 else "hand-checked scenarios"
if __name__ == "__main__":
    if "--battery-model" in sys.argv: print("RESULT", battery_model()); sys.exit(0)
    if "--battery" in sys.argv: print("RESULT", battery()); sys.exit(0)
    import subprocess
    print("== 1. lint gate (Verilator -Wall --lint-only, Yosys 'check')")
    for top in ("sup", "rst_gen"):
        p = subprocess.run(["verilator", "--lint-only", "-Wall", "-Wno-DECLFILENAME", "--top-module", top, "rtl/sup.sv"], cwd=R_, capture_output=True, text=True); w_ = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning")]
        y = subprocess.run(["yosys", "-p", f"read_verilog -sv rtl/sup.sv; hierarchy -top {top}; proc; opt_clean; check"], cwd=R_, capture_output=True, text=True).stdout
        print(f"  {top}: Verilator warnings {len(w_)}, Yosys check problems {len([l for l in y.splitlines() if 'Found and reported' in l and ' 0 problems' not in l])}")
    print("\n== 2. the model's hand-checked scenarios (python3 model/sup_gold.py)")
    print("  " + subprocess.run([sys.executable, "model/sup_gold.py"], cwd=R_, capture_output=True, text=True).stdout.strip())
    print("\n== 3. supervisor and reset generator against the model, every cycle, every output")
    print(f"  {'FT':>4s} {'ST':>4s} {'WARM':>4s} {'RSTN':>4s} {'scenario':11s} | {'cycles':>6s} {'trips':>5s} {'in SAFE':>7s} | {'Icarus':>7s} {'Verilator':>10s}")
    for ci, cfg in enumerate(CONFIGS):
        for kind in KINDS:
            cyc = make(kind, ci); rows = run_model(cyc, cfg); trips = sum(1 for a, b in zip(rows, rows[1:]) if a[0] == G.RUN and b[0] == G.SAFE)
            print(f"  {cfg[0]:4d} {cfg[1]:4d} {cfg[2]:4d} {cfg[3]:4d} {kind:11s} | {len(cyc):6d} {trips:5d} {sum(1 for r in rows if r[0] == G.SAFE):7d} | {'PASS' if same(cyc, cfg) else 'FAIL':>7s} {'PASS' if same(cyc, cfg, 'verilator') else 'FAIL':>10s}")
