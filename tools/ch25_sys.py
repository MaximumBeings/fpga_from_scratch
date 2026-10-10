#!/usr/bin/env python3
"""Chapter 25: the joined design (rtl/life.sv = gate + tracker + state machine) against its cycle model (model/sys_gold.py): every cycle, ready, the answer of each order, the answer of each cancel request, the gate's answer to every event it gets (so every release the tracker makes is checked, with account, symbol, side, price and quantity, by the effect on the gate's books), the count of live orders, the fault and the state; in two simulators, for three table sizes, on six traffic mixes; and the reconciliation check of the model (gate books = tracker books) in every quiet cycle."""
import os, random, subprocess, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, life_gold as LG, risk_gold as RG, sys_gold as SG
R_ = flow.ROOT; F_ = ["rtl/risk.sv", "rtl/track.sv", "rtl/life.sv", "tb/sys_tb.sv"]
def rows_rtl(res, nt, simu="icarus", rtl=F_):
    n = SG.write_stim(os.path.join(R_, "out", "sys_stim.hex"), res)
    o = (flow.sim_icarus if simu == "icarus" else flow.sim_verilator)(rtl, "sys_tb", defines=(f"NC={n}", f"NT={nt}") + (("GARBAGE",) if simu == "icarus" else ()))[1]
    try: return [tuple(int(x) for x in l.split()[2:]) for l in o.splitlines() if l.startswith("C ")]
    except ValueError: return [("x",)]
def same(cy, nt, simu="icarus", rtl=F_):
    res = SG.run(cy, nt); got = rows_rtl(res, nt, simu, rtl); exp = SG.expected_rows(res)
    return got[:len(exp)] == exp and len(got) >= len(exp) and res["sys"].bad == 0
CONFIGS = [1, 2, 4]
def rcfg(rng, kind):
    if kind == "tight": return dict(maxlong=rng.randint(10, 60), maxshort=rng.randint(10, 60), maxqty=rng.randint(5, 30), maxonot=rng.randint(200, 1500), maxnot=rng.randint(500, 3000), cap=rng.randint(1, 4))
    return dict(maxlong=rng.randint(200, 2000), maxshort=rng.randint(200, 2000), maxqty=rng.randint(30, 200), maxonot=rng.randint(3000, 20000), maxnot=rng.randint(20000, 100000), cap=rng.randint(4, 8))
def gen(kind, rng, nt, n=400):
    S = SG.Sys(nt); cy = []; ntok = [100]
    def put(d):
        cy.append(d); S.step(d)
    for a in range(4): put(dict(cfg=(a, rcfg(rng, kind))))
    for s in range(4): put(dict(band=(s, rng.randint(1, 30), rng.randint(70, 100))))
    put(dict(arm=1)); put({}); put({})
    prate = {"flow": .25, "tight": .5, "dups": .4, "faults": .3, "cancels": .3, "random": .4}[kind]
    for _ in range(n):
        d = {}
        if rng.random() < prate and len(S.ordq) < 2:
            if kind in ("dups", "random") and rng.random() < .45: tok = rng.randrange(max(101, ntok[0] - 5), max(102, ntok[0] + 1))            # a token issued a moment ago: usually still open
            else: ntok[0] += 1; tok = ntok[0]
            d["ord"] = dict(tok=tok, acct=rng.randrange(4) if rng.random() < .99 else 4, sym=rng.randrange(4) if rng.random() < .99 else 5, side=rng.randrange(2), px=rng.choice([rng.randint(30, 70)] * 12 + [rng.randint(1, 100), 0, 101]), qty=rng.choice([rng.randint(1, 30)] * 12 + [0, 1, 250]) if kind != "tight" else rng.randint(1, 40))
        live = [x for x in S.T.e if x]
        if rng.random() < (.35 if kind != "faults" else .3) and live:
            x = rng.choice(live)
            k = rng.choice([LG.FILL, LG.FILL, LG.FILL, LG.ACK, LG.CANCELED, LG.REJECT]) if x["st"] == LG.PNEW else rng.choice([LG.FILL, LG.FILL, LG.FILL, LG.CANCELED])
            if x["st"] != LG.PNEW and k == LG.ACK: k = LG.FILL
            q = rng.choice([x["rem"], rng.randint(1, x["rem"]), 1])
            if kind in ("faults", "random") and rng.random() < (.004 if kind == "faults" else .001): k, q = rng.choice([(LG.FILL, x["rem"] + 1), (LG.FILL, 0), (LG.ACK, 0), (LG.REJECT, 0)]) if x["st"] != LG.PNEW else (LG.FILL, x["rem"] + 1)
            d["rep"] = (k, dict(tok=x["tok"], qty=q))
        elif kind in ("faults", "random") and rng.random() < .0007: d["rep"] = (rng.randrange(4), dict(tok=rng.randrange(1, 130), qty=rng.randint(0, 5)))
        if rng.random() < (.25 if kind == "cancels" else .06) and len(S.crq) < 1: d["cr"] = dict(tok=rng.choice([x["tok"] for x in live]) if live and rng.random() < .85 else rng.randrange(100, 130))
        if rng.random() < .01: d["cfg"] = (rng.randrange(4), rcfg(rng, kind))
        if rng.random() < .01: d["band"] = (rng.randrange(4), rng.randint(1, 30), rng.randint(70, 100))
        if rng.random() < .08: d["arm"] = 1
        if rng.random() < (.004 if kind != "faults" else .01): d["disarm"] = 1
        if rng.random() < (.003 if kind == "faults" else .0005 if kind == "random" else .0): d["kill"] = 1
        put(d)
    return cy
KINDS = ("flow", "tight", "dups", "faults", "cancels", "random")
def make(kind, seed, nt): return gen(kind, random.Random(seed * 1000 + sum(map(ord, kind))), nt)
def collide(k):
    """directed: a rollback (duplicate token) waits for the gate's port while the report of a fill makes the tracker release: the release goes first. k delays the report."""
    u = dict(maxlong=100, maxshort=100, maxqty=50, maxonot=10000, maxnot=100000, cap=5); o = lambda t: dict(tok=t, acct=0, sym=0, side=0, px=20, qty=10)
    return [dict(cfg=(a, u)) for a in range(4)] + [dict(band=(s, 1, 100)) for s in range(4)] + [dict(arm=1), {}, {}, dict(ord=o(1)), {}, {}, {}, {}, {}, dict(ord=o(1))] + [{}] * k + [dict(rep=(LG.FILL, dict(tok=1, qty=4)))] + [{}] * 12
def battery():
    """The mutation runs' test: three table sizes, six mixes, Icarus. -> None or the first difference."""
    for nt in CONFIGS:
        for kind in KINDS:
            try: ok = same(make(kind, nt, nt), nt)
            except Exception as x: return f"crash {type(x).__name__}"
            if not ok: return f"{kind}, NT {nt}"
    for k in range(14):
        if not same(collide(k), 2): return f"collision, delay {k}"
    return None
def battery_model():
    q = subprocess.run([sys.executable, "model/sys_gold.py"], cwd=R_, capture_output=True, text=True, timeout=300)
    return None if q.returncode == 0 else "hand-checked scenarios"
if __name__ == "__main__":
    if "--battery-model" in sys.argv: print("RESULT", battery_model()); sys.exit(0)
    if "--battery" in sys.argv: print("RESULT", battery()); sys.exit(0)
    print("== 1. lint gate (Verilator -Wall --lint-only, Yosys 'check')")
    p = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", "life", "rtl/risk.sv", "rtl/track.sv", "rtl/life.sv"], cwd=R_, capture_output=True, text=True); w_ = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning") and "DECLFILENAME" not in l]
    y = subprocess.run(["yosys", "-p", "read_verilog -sv rtl/risk.sv rtl/track.sv rtl/life.sv; hierarchy -top life; proc; opt_clean; check"], cwd=R_, capture_output=True, text=True).stdout
    print(f"  life: Verilator warnings {len(w_)}, Yosys check problems {len([l for l in y.splitlines() if 'Found and reported' in l and ' 0 problems' not in l])}")
    print("\n== 2. the model's hand-checked scenarios (python3 model/sys_gold.py) and what the traffic contains (NT 4, seed 1)")
    print("  " + subprocess.run([sys.executable, "model/sys_gold.py"], cwd=R_, capture_output=True, text=True).stdout.strip())
    for kind in KINDS:
        r = SG.run(make(kind, 1, 4), 4); S = r["sys"]; d = Counter((RG.RN + [""] * 5)[x[3]] if x[3] < 16 else "TRK_" + LG.RN[x[3] - 16] for x in r["rows"] if x[2]); gk = Counter(RG.RN[x[9]] for x in r["rows"] if x[7] and x[8] == 1 or x[7] and x[8] == 2)
        print(f"  {kind:7s} orders answered {sum(d.values()):3d}: " + ", ".join(f"{k} {n}" for k, n in sorted(d.items())) + f" | quiet cycles checked {S.checks}, books differ in {S.bad} | fault {r['rows'][-1][16]}")
    print("  collision cases (rollback and a tracker release want the gate's port in the same cycle), report delay 0..13: " + str(sum(SG.run(collide(k), 2)["sys"].collide > 0 for k in range(14))) + " of 14 collide")
    print("\n== 3. the joined design against the model: every output, every cycle")
    print(f"  {'mix':8s} {'NT':>3s} | {'cycles':>7s} {'orders':>7s} {'sent':>5s} {'rolled back':>11s} | {'Icarus':>7s} {'Verilator':>10s}")
    for kind in KINDS:
        for nt in CONFIGS:
            cy = make(kind, 1, nt); res = SG.run(cy, nt); i = same(cy, nt); v = same(cy, nt, "verilator"); ds = [x for x in res["rows"] if x[2]]
            print(f"  {kind:8s} {nt:3d} | {len(res['rows']):7d} {len(ds):7d} {sum(x[3] == 0 for x in ds):5d} {sum(x[3] >= 16 for x in ds):11d} | {'PASS' if i else 'FAIL':>7s} {'PASS' if v else 'FAIL':>10s}")
    ci = [same(collide(k), 2) for k in range(14)]; cv = [same(collide(k), 2, "verilator") for k in range(14)]
    print(f"  collision 0..13 | {'PASS' if all(ci) else 'FAIL':>7s} {'PASS' if all(cv) else 'FAIL':>10s}")
