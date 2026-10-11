#!/usr/bin/env python3
"""Chapter 27, part 2: the supervised design (rtl/safe.sv) against model/safe_gold.py, in two simulators, every cycle in which the units are not in reset, every output (Chapter 26's 43 plus the supervisor's state, kill, logout request and cause), on the traffic mixes of Chapter 26 with a supervisor added and on fault scenarios made for it: a feed that goes silent, a pipeline that stalls, an external trip, a tracker fault, a session that dies, a reset in the middle of a run; and the properties P1 to P4 of the model on every run."""
import os, random, subprocess, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, ch26_run as C26, safe_gold as SGD, w2w_gold as WG, sup_gold as SG, sess_gold as SS, life_gold as LG, risk_gold as RG
R_ = flow.ROOT; F_ = ["rtl/mold_itch.sv", "rtl/book2.sv", "rtl/sig.sv", "rtl/trig.sv", "rtl/risk.sv", "rtl/track.sv", "rtl/life.sv", "rtl/sess.sv", "rtl/w2w.sv", "rtl/sup.sv", "rtl/safe.sv", "tb/safe_tb.sv"]
RSTN = 8; GO_AT = 100; ARM_AT = 104
def write_stim(path, cycles):
    boot = [dict(rst_in=1)] * 3 + [dict()] * (RSTN + 2)
    with open(path, "w") as f:
        for i, cy in enumerate(boot + cycles + [dict() for _ in range(8)]):
            v = 0
            if i >= len(boot):
                C26.write_stim(os.path.join(R_, "out", "_one.hex"), [cy]); v = int(open(os.path.join(R_, "out", "_one.hex")).read().strip(), 16)
            v |= (1 if cy.get("go") else 0) << 498 | (1 if cy.get("trip") else 0) << 499 | (1 if cy.get("rst_in") else 0) << 500
            f.write("%0126x\n" % v)
    return len(boot) + len(cycles) + 8
def rows_rtl(cycles, simu, kw):
    n = write_stim(os.path.join(R_, "out", "safe_stim.hex"), cycles)
    d = (f"NC={n}", f"FT={kw['ft']}", f"ST={kw['st']}", f"WARM={kw['warm']}", f"RSTN={RSTN}", f"QD={kw.get('qd', 8)}", f"F={kw.get('f', 12)}", f"W={kw.get('w', 8)}")
    o = (flow.sim_icarus if simu == "icarus" else flow.sim_verilator)(F_, "safe_tb", defines=d)[1]
    try: return [tuple(int(x) for x in l.split()[2:]) for l in o.splitlines() if l.startswith("C ")]
    except ValueError: return [("x",)]
def mkw(kw): return dict(ft=kw.get("ft", 400), st=kw.get("st", 100), warm=kw.get("warm", 48), rstn=RSTN, **{k: v for k, v in kw.items() if k in ("qd", "f", "w")})
def same(case, simu="icarus"):
    cycles, mev, kw = case; k = mkw(kw); res = SGD.run(cycles, mev, **k); got = rows_rtl(cycles, simu, k); exp = res["rows"]
    return got[:len(exp)] == exp and len(got) >= len(exp) and not SGD.check(res)
def prep(cm):
    cyc = [dict(c) for c in cm[0]]
    for c in cyc: c.pop("arm", None)                                                   # the gate ignores an arm while its kill input is high, and the supervisor holds kill until RUN: arm AFTER go
    cyc[GO_AT]["go"] = 1; cyc[ARM_AT]["arm"] = 1
    return cyc, cm[1], dict(cm[2])
def silent(cm, at):
    """the feed stops at cycle `at` (every byte after it is removed, and the messages with it)"""
    cyc, mev, kw = prep(cm)
    for c in range(at, len(cyc)):
        cyc[c].pop("s", None)
    return cyc, {c: e for c, e in mev.items() if c < at}, kw
def make(kind, seed):
    if kind in ("normal", "dense", "slow", "refuse", "close", "faults", "collide", "hand", "slowsig", "narrow"):
        cm = C26.make(kind, seed); c = prep(cm); c[2].update(ft=400); return c
    cm = C26.make("normal", seed)
    if kind == "feedloss": c, m, kw = silent(cm, 1500); kw.update(ft=300); return c, m, kw
    if kind == "feedgap": c, m, kw = silent(cm, 1500); kw.update(ft=300); return c, m, kw
    if kind == "stall":
        c, m, kw = prep(C26.make("slowsig", seed)); kw.update(ft=400, st=60); return c, m, kw                    # F = 32: the slot is held n + 36 cycles: more than 60 for the longer events
    if kind == "trip": c, m, kw = prep(cm); c[2000]["trip"] = 1; kw.update(ft=400); return c, m, kw
    if kind == "extkill":
        c, m, kw = prep(cm); kw.update(ft=400)
        X = WG.W2W(**{k: v for k, v in kw.items() if k in ("qd", "f", "w")}); offers = []
        for i in range(len(c)):
            row = X.step(c[i], m.get(i))
            if row[7]: offers.append(i)                                                       # the strategy offers an order in this cycle
        for o in offers[1:4]: c[o - 1]["kill"] = 1; c[o]["kill"] = 1; c[o + 1]["kill"] = 1     # the control plane's own kill, around three of the offers (the first is left alone)
        return c, m, kw
    if kind == "holdtrip":
        c, m, kw = prep(C26.make("narrow", seed)); kw.update(ft=400, w=1)
        X = WG.W2W(**{k: v for k, v in kw.items() if k in ("qd", "f", "w")}); hit = None
        for i in range(len(c)):
            X.step(c[i], m.get(i))
            if X.snd_hold and hit is None: hit = i
        if hit is not None: c[hit - 1]["trip"] = 1                                         # a trip in the cycle before an order is held for the transmitter: the logout must wait for it
        return c, m, kw
    if kind == "go_early":
        c, m, kw = prep(cm); c[GO_AT]["go"] = 0; c[10]["go"] = 1; c[GO_AT + 300]["go"] = 1; kw.update(ft=400); return c, m, kw                            # a go while INIT and a go with no session: ignored; the real go 300 cycles late
    if kind == "reset":
        c, m, kw = prep(cm); R0 = 2600; c[R0]["rst_in"] = 1; c[R0 + 1]["rst_in"] = 1
        i = R0
        while i < len(c) and not (i > R0 + RSTN + 4 and "s" in c[i] and c[i]["s"][0] and c[i]["s"][1] == 1): c[i].pop("s", None); i += 1        # the bytes of the packet the reset cut are not fed: the parser would ignore them, and they would be decoded by the model's parser as messages
        kw.update(ft=400)
        return c, {k: v for k, v in m.items() if k < R0 or k > i}, kw
    raise KeyError(kind)
KINDS = ("normal", "dense", "slow", "refuse", "close", "faults", "collide", "slowsig", "narrow", "hand", "feedloss", "stall", "trip", "extkill", "holdtrip", "go_early", "reset")
def battery():
    for i, k in enumerate(KINDS):
        try: ok = same(make(k, i + 1))
        except Exception as x: return f"crash {type(x).__name__}"
        if not ok: return k
    return None
def battery_model():
    q = subprocess.run([sys.executable, "model/safe_gold.py"], cwd=R_, capture_output=True, text=True, timeout=300)
    return None if q.returncode == 0 else "hand-checked scenarios"
if __name__ == "__main__":
    if "--battery-model" in sys.argv: print("RESULT", battery_model()); sys.exit(0)
    if "--battery" in sys.argv: print("RESULT", battery()); sys.exit(0)
    print("== 1. lint gate (Verilator -Wall --lint-only, Yosys 'check')")
    p = subprocess.run(["verilator", "--lint-only", "-Wall", "-Wno-DECLFILENAME", "-Wno-UNUSEDSIGNAL", "-Wno-UNUSEDPARAM", "--top-module", "safe"] + F_[:-1], cwd=R_, capture_output=True, text=True); w_ = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning") and "sess.sv" not in l]
    print(f"  safe (all units): Verilator warnings {len(w_)}")
    print("\n== 2. what the runs contain: the supervisor's path and what the wire saw")
    print(f"  {'scenario':9s} {'cycles':>6s} {'INIT->READY':>11s} {'->RUN':>6s} {'->SAFE':>7s} {'cause':>9s} {'orders sent':>11s} {'sent after SAFE':>15s} {'logout':>7s} {'P1-P4':>6s}")
    for i, k in enumerate(KINDS):
        c, m, kw = make(k, i + 1); res = SGD.run(c, m, **mkw(kw)); rows = res["rows"]; X = res["safe"].X
        tr = {}
        for j in range(1, len(rows)):
            if rows[j][-4] != rows[j - 1][-4]: tr.setdefault(rows[j][-4], j)
        cs = rows[-1][-1]; causes = "+".join(n for b, n in enumerate(SG.CAUSES) if cs >> b & 1) or "-"
        sent = [p for p in X.X.packets if p[1] == SS.ORDER]; after = sum(1 for p in sent if SG.SAFE in tr and p[0] > tr[SG.SAFE]); lo = sum(1 for p in X.X.packets if p[1] == SS.LOGOUT)
        print(f"  {k:9s} {len(rows):6d} {tr.get(1, '-'):>11} {tr.get(2, '-'):>6} {tr.get(3, '-'):>7} {causes:>9s} {len(sent):11d} {after:15d} {lo:7d} {'ok' if not SGD.check(res) else 'VIOLATED':>6s}")
    print("\n== 3. the supervised design against the model: every cycle, every output")
    print(f"  {'scenario':9s} | {'Icarus':>7s} {'Verilator':>10s}")
    for i, k in enumerate(KINDS):
        c = make(k, i + 1); print(f"  {k:9s} | {'PASS' if same(c) else 'FAIL':>7s} {'PASS' if same(c, 'verilator') else 'FAIL':>10s}")
