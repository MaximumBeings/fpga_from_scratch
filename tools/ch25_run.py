#!/usr/bin/env python3
"""Chapter 25: the running designs. (1) lint; (2) the model's hand-checked scenarios and the statistics of the stimulus; (3) the tracker against the model in every cycle (ready, answer, release, live count, fault), in two simulators, for four table sizes, on scenarios: clean traffic, a table that is always full, token near-misses (tokens that differ in one bit), reports every cycle (the requester starves), fault injection (each kind of anomalous report), and random mixes."""
import os, random, subprocess, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, life_gold as G
R_ = flow.ROOT; F_ = ["rtl/track.sv", "tb/life_tb.sv"]
def rows_rtl(res, nt, simu="icarus", rtl=F_):
    n = G.write_stim(os.path.join(R_, "out", "life_stim.hex"), res)
    o = (flow.sim_icarus if simu == "icarus" else flow.sim_verilator)(rtl, "life_tb", defines=(f"NC={n}", f"NT={nt}") + (("GARBAGE",) if simu == "icarus" else ()))[1]
    try: return [tuple(int(x) for x in l.split()[2:]) for l in o.splitlines() if l.startswith("C ")]
    except ValueError: return [("x",)]
def same(cy, nt, simu="icarus", rtl=F_):
    res = G.run(cy, nt); got = rows_rtl(res, nt, simu, rtl); exp = G.expected_rows(res)
    return got[:len(exp)] == exp and len(got) >= len(exp)
CONFIGS = [1, 2, 4, 5, 8]
def gen(kind, rng, nt, n=300):
    """Cycle list built by stepping a shadow tracker with the same rules as G.run, so that reports are (mostly) well formed."""
    T = G.Tracker(nt); cy = []; held = None; pool = [rng.getrandbits(32) for _ in range(max(3, nt))]
    pool += [pool[0] ^ (1 << rng.randrange(32)) for _ in range(3)] + [pool[1] ^ 0x80000000, pool[0] & 0xFFFF]
    prate = {"clean": .5, "full": .8, "near": .5, "burst": .3, "fault": .5, "random": .5}[kind]
    rrate = {"clean": .35, "full": .1, "near": .35, "burst": 1.0, "fault": .35, "random": .4}[kind]
    for c in range(n):
        d = {}
        if held is None and rng.random() < prate:
            if rng.random() < .65 or not T.nlive():
                qty = rng.choice([0, 1, 1, 2, 5, 10, 100, 65535]) if rng.random() < .9 or kind == "random" else rng.randint(1, 65535)
                if kind != "random" and rng.random() < .93: qty = max(qty, 1)
                held = (G.NEW, dict(tok=rng.choice(pool), acct=rng.randrange(16), sym=rng.randrange(16), side=rng.randrange(2), px=rng.choice([0, 1, 1000, rng.randrange(65536), 65535]), qty=qty))
            else:
                live = [x["tok"] for x in T.e if x]; held = (G.CANCELREQ, dict(tok=rng.choice(live) if rng.random() < .8 else rng.choice(pool)))
            d["loc"] = held
        rep = None
        if rng.random() < rrate:
            live = [x for x in T.e if x]
            if live and rng.random() < (.97 if kind in ("clean", "full", "near", "burst") else .8):
                x = rng.choice(live); k = rng.choice([G.FILL, G.FILL, G.FILL, G.ACK, G.CANCELED, G.REJECT]) if x["st"] == G.PNEW else rng.choice([G.FILL, G.FILL, G.FILL, G.CANCELED])
                if kind in ("clean", "full", "near", "burst") and x["st"] != G.PNEW and k == G.ACK: k = G.FILL
                q = rng.choice([x["rem"], x["rem"], 1, rng.randint(1, x["rem"])]) if x["rem"] else 1
                rep = (k, dict(tok=x["tok"], qty=q))
            elif kind in ("fault", "random"):
                live = [x for x in T.e if x]
                if live and rng.random() < .6:
                    x = rng.choice(live); w = rng.choice(["over", "zero", "ack", "rej"]) if x["rem"] < 65535 else "zero"
                    rep = (G.FILL, dict(tok=x["tok"], qty=x["rem"] + 1)) if w == "over" else (G.FILL, dict(tok=x["tok"], qty=0)) if w == "zero" else (G.ACK, dict(tok=x["tok"])) if (w == "ack" and x["st"] != G.PNEW) else (G.REJECT, dict(tok=x["tok"])) if x["st"] != G.PNEW else (G.FILL, dict(tok=x["tok"], qty=x["rem"] + 1))
                else: rep = (rng.choice([G.ACK, G.FILL, G.CANCELED, G.REJECT]), dict(tok=rng.choice(pool + [rng.getrandbits(32)]), qty=rng.randint(0, 5)))
        if rep: d["rep"] = rep
        cy.append(d)
        if rep: T.report(*rep)
        elif held is not None: T.local(*held); held = None
        if kind == "fault" and T.fault and rng.random() < .05: pass
    return cy
KINDS = ("clean", "full", "near", "burst", "fault", "random")
def make(kind, seed, nt): return gen(kind, random.Random(seed * 1000 + sum(map(ord, kind))), nt)
def battery():
    """The mutation runs' test: five table sizes, six scenarios, Icarus. -> None or the first difference."""
    for nt in CONFIGS:
        for kind in KINDS:
            try: ok = same(make(kind, nt, nt), nt)
            except Exception as x: return f"crash {type(x).__name__}"
            if not ok: return f"{kind}, NT {nt}"
    return None
def battery_model():
    q = subprocess.run([sys.executable, "model/life_gold.py"], cwd=R_, capture_output=True, text=True, timeout=300)
    return None if q.returncode == 0 else "hand-checked scenarios"
if __name__ == "__main__":
    if "--battery-model" in sys.argv: print("RESULT", battery_model()); sys.exit(0)
    if "--battery" in sys.argv: print("RESULT", battery()); sys.exit(0)
    print("== 1. lint gate (Verilator -Wall --lint-only, Yosys 'check')")
    p = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", "track", "rtl/track.sv"], cwd=R_, capture_output=True, text=True); w_ = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning") and "DECLFILENAME" not in l]
    y = subprocess.run(["yosys", "-p", "read_verilog -sv rtl/track.sv; hierarchy -top track; proc; opt_clean; check"], cwd=R_, capture_output=True, text=True).stdout
    print(f"  track: Verilator warnings {len(w_)}, Yosys check problems {len([l for l in y.splitlines() if 'Found and reported' in l and ' 0 problems' not in l])}")
    print("\n== 2. the model's hand-checked scenarios (python3 model/life_gold.py) and what the stimulus contains (NT 4, seed 1)")
    print("  " + subprocess.run([sys.executable, "model/life_gold.py"], cwd=R_, capture_output=True, text=True).stdout.strip())
    for kind in KINDS:
        res = G.run(make(kind, 1, 4), 4); an = Counter(G.RN[r[3]] for r in res["rows"] if r[1]); rl = Counter(r[5] for r in res["rows"] if r[4])
        print(f"  {kind:7s} answers: " + ", ".join(f"{k} {n}" for k, n in sorted(an.items())) + f" | releases: FILL {rl[1]}, CANCEL {rl[2]} | live max {max(r[11] for r in res['rows'])} | fault {res['rows'][-1][12]}")
    print("\n== 3. the tracker against the model: ready, answer, release, live count and fault in every cycle")
    print(f"  {'scenario':8s} {'NT':>3s} | {'cycles':>7s} {'answers':>8s} {'releases':>9s} | {'Icarus':>7s} {'Verilator':>10s}")
    for kind in KINDS:
        for nt in CONFIGS:
            cy = make(kind, 1, nt); res = G.run(cy, nt); i = same(cy, nt); v = same(cy, nt, "verilator")
            print(f"  {kind:8s} {nt:3d} | {len(res['rows']):7d} {sum(r[1] for r in res['rows']):8d} {sum(r[4] for r in res['rows']):9d} | {'PASS' if i else 'FAIL':>7s} {'PASS' if v else 'FAIL':>10s}")
