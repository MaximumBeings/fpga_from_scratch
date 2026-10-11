#!/usr/bin/env python3
"""Chapter 26: the running design. (1) lint; (2) the model's own checks and what the traffic contains; (3) the whole design, wire to wire, against its model: in every cycle the queue, the counters, the book's, the strategy's, the lifecycle's and the transmitter's outputs (so every byte of every order on the wire), in two simulators, on seven traffic mixes; (4) the cycle budget: for every order, the cycles in each stage from the last byte of the message that caused it to the first byte of the order, with the closed form checked against the measurement."""
import os, random, subprocess, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, itch_gold as IG, book2_gold as BG, trig_gold as TG, life_gold as LG, risk_gold as RG, sess_gold as SS, w2w_gold as WG
R_ = flow.ROOT; F_ = ["rtl/mold_itch.sv", "rtl/book2.sv", "rtl/sig.sv", "rtl/trig.sv", "rtl/risk.sv", "rtl/track.sv", "rtl/life.sv", "rtl/sess.sv", "rtl/w2w.sv", "tb/w2w_tb.sv"]
NS, P0, SHT = WG.NS, WG.P0, WG.SHT; KW = dict(slowsig=dict(qd=4, f=32), narrow=dict(w=1))
def write_stim(path, cycles):
    """one line per cycle, 498 bits as 125 hex digits (layout: see tb/w2w_tb.sv)"""
    with open(path, "w") as f:
        for cy in cycles:
            v = 0
            if "s" in cy: sv, sop, eop, d = cy["s"]; v |= sv | sop << 1 | eop << 2 | d << 3
            if "rep" in cy: k, d = cy["rep"]; v |= 1 << 11 | k << 12 | (d["tok"] & WG.M) << 14 | (d.get("qty", 0) & 0xFFFF) << 46
            if "tc" in cy:
                r, u = cy["tc"]; v |= 1 << 62 | r << 63 | u["en"] << 67 | u["neg"] << 68 | u["tmask"] << 69 | u["symany"] << 74 | u["sideany"] << 75 | u["side"] << 76 | u["pxop"] << 77 | u["shop"] << 80 | u["symmask"] << 83 | u["pxval"] << 115 | u["shval"] << 147
            if "tl" in cy: a, val, key, i = cy["tl"]; v |= 1 << 179 | a << 180 | key << 192 | i << 224 | val << 229
            if "cfg" in cy:
                a, u = cy["cfg"]; v |= 1 << 230 | a << 231 | u["maxlong"] << 235 | u["maxshort"] << 251 | u["maxqty"] << 267 | u["maxonot"] << 283 | u["maxnot"] << 323 | u["cap"] << 365
            if "band" in cy: s_, lo, hi = cy["band"]; v |= 1 << 373 | s_ << 374 | lo << 378 | hi << 394
            v |= cy.get("arm", 0) << 410 | cy.get("disarm", 0) << 411 | cy.get("kill", 0) << 412
            if "sc" in cy: w, s_, d = cy["sc"]; v |= 1 << 413 | w << 414 | s_ << 417 | d << 421
            if "rx" in cy: t, sq = cy["rx"]; v |= 1 << 453 | ord(t) << 454 | sq << 462
            if "cq" in cy: v |= 1 << 494 | cy["cq"] << 495
            f.write("%0125x\n" % v)
    return len(cycles)
def rows_rtl(cycles, simu="icarus", rtl=F_, kw={}):
    n = write_stim(os.path.join(R_, "out", "w2w_stim.hex"), cycles + [dict() for _ in range(8)])
    o = (flow.sim_icarus if simu == "icarus" else flow.sim_verilator)(rtl, "w2w_tb", defines=(f"NC={n}", f"QD={kw.get('qd', 8)}", f"F={kw.get('f', 12)}", f"W={kw.get('w', 8)}"))[1]
    try: return [tuple(int(x) for x in l.split()[2:]) for l in o.splitlines() if l.startswith("C ")]
    except ValueError: return [("x",)]
def same(cyc_mev, simu="icarus", rtl=F_):
    cycles, mev, kw = cyc_mev; res = WG.run(cycles, mev, **kw); got = rows_rtl(cycles, simu, rtl, kw); exp = res["rows"]
    return got[:len(exp)] == exp and len(got) >= len(exp)
def msg_of(rng, e, ns):
    sd = lambda x: ord("S") if x else ord("B")
    if e["t"] == BG.ADD: return IG.build_msg(rng, "A" if rng.random() < .8 else "F", locate=e["sym"], ref=e["ref"], side=sd(e["side"]), shares=e["sh"], price=e["px"])
    loc = rng.randrange(ns)
    if e["t"] == BG.EXEC: return IG.build_msg(rng, "E", locate=loc, ref=e["ref"], shares=e["sh"])
    if e["t"] == BG.CANCEL: return IG.build_msg(rng, "X", locate=loc, ref=e["ref"], shares=e["sh"])
    if e["t"] == BG.DELETE: return IG.build_msg(rng, "D", locate=loc, ref=e["ref"])
    return IG.build_msg(rng, "U", locate=loc, ref=e["ref"], newref=e["ref2"], shares=e["sh"], price=e["px"])
RULE, preamble = WG.RULE, WG.preamble
def make(kind, seed, nev=100):
    if kind in ("hand", "edge", "dead", "dead2"): c_, m_ = dict(hand=WG.directed, edge=WG.directed_edge, dead=WG.directed_dead, dead2=WG.directed_dead2)[kind](); return c_, m_, {}
    if kind == "queue": return WG.directed_queue()
    rng = random.Random(seed * 100 + sum(map(ord, kind))); ns = NS
    evs = BG.gen_events(rng, nev, ns=ns, d=8, nb=8, k=4, faults=0.04 if kind != "faults" else 0.1, sh_max=300, **(dict(p_add=0.4) if kind != "burst" else dict(p_add=0.06, p_red=0.8, p_del=0.1)))
    msgs = [msg_of(rng, e, ns) for e in evs]
    if kind != "dense_clean":
        for _ in range(4): msgs.insert(rng.randrange(len(msgs)), IG.build_msg(rng, rng.choice("SP"), locate=rng.randrange(ns)))                    # messages the adapter does not use
        for _ in range(6): msgs.insert(rng.randrange(len(msgs)), IG.build_msg(rng, "A", locate=ns, ref=5000 + rng.randrange(50), side=rng.choice(b"BS"), shares=200, price=rng.randint(990, 1010)))      # a symbol the design does not trade (the first one past its table)
        for _ in range(3): msgs.insert(rng.randrange(len(msgs)), IG.build_msg(rng, "A", locate=rng.randrange(ns), ref=6000 + rng.randrange(50), shares=200, price=1000) + b"\0")       # a known type with the wrong length (the parser's error 2)
        i = rng.randrange(len(msgs)); msgs[i] = bytes([ord("Z")]) + msgs[i][1:]                                                                        # an unknown message type
    pk = []; i = 0
    while i < len(msgs): n = rng.randint(1, 4); pk.append(dict(data=IG.build_packet(rng, msgs[i:i + n]), eop=True, reset_at=None)); i += n
    between = {"normal": (0, 40), "dense": (0, 1), "dense_clean": (0, 1), "collide": (0, 40), "burst": (0, 0), "slowsig": (0, 1), "narrow": (0, 2), "openbook": (0, 40), "slow": (40, 120), "refuse": (0, 40), "close": (0, 40), "faults": (0, 40)}[kind]
    lines, info = IG.schedule(rng, pk, gap=0.03 if kind not in ("slow", "burst") else (0.2 if kind == "slow" else 0.0), stray=0.0, between=between)
    mev = WG.parse_events(info, ns, shift=P0); total = P0 + len(lines) + 500
    cycles = preamble(rng) + [dict() for _ in range(total - P0)]
    for j, (v, sop, eop, d, _) in enumerate(lines): cycles[P0 + j]["s"] = (v, sop, eop, d)
    dead_at = P0 + len(lines) // 2 if kind == "refuse" else None
    for c in range(80, total, 30):
        if dead_at is None or c < dead_at: cycles[c]["rx"] = ("H", 0)
    if kind == "close": cycles[P0 + len(lines) // 3]["rx"] = ("Z", 0)
    if kind == "normal": cycles[P0 + len(lines) // 2]["cq"] = SS.LOGINQ                                                                                    # a second login: the transmitter refuses it, and that is not an order
    X = WG.W2W(**KW.get(kind, {})); rows = []
    for c in range(total):
        cy = cycles[c]
        if "rx" not in cy and "rep" not in cy and c > P0:
            live = [x for x in X.S.T.e if x and 'cx' in X.log.get(x['tok'], {})]                                   # only orders that reached the wire can be reported on
            decide_next = (kind == "collide" and (c + 1) in X.sig_at) or (kind in ("refuse", "close") and X.rej_pend)                                              # a report one cycle before a decision: the tracker's release will be using the gate's port when the order is offered
            if kind != "openbook" and live and (rng.random() < .06 or (decide_next and rng.random() < .8)):
                x = rng.choice(live); k = rng.choice([LG.FILL, LG.FILL, LG.ACK, LG.CANCELED]) if x["st"] == LG.PNEW else rng.choice([LG.FILL, LG.FILL, LG.CANCELED])
                if x["st"] != LG.PNEW and k == LG.ACK: k = LG.FILL
                q = rng.choice([x["rem"], 1, rng.randint(1, x["rem"])]); cy["rep"] = (k, dict(tok=x["tok"], qty=q))
                if kind == "faults" and rng.random() < .12: cy["rep"] = (LG.FILL, dict(tok=x["tok"], qty=x["rem"] + 1))
        X.step(cy, mev.get(c))
    return cycles, mev, KW.get(kind, {})
KINDS = ("normal", "dense", "dense_clean", "slow", "refuse", "close", "faults", "burst", "slowsig", "collide", "narrow", "openbook", "hand", "edge", "dead", "dead2", "queue")
def battery():
    """The mutation runs' test: seven mixes, Icarus. -> None or the first difference."""
    for i, kind in enumerate(KINDS):
        try: ok = same(make(kind, i + 1))
        except Exception as x: return f"crash {type(x).__name__}"
        if not ok: return kind
    return None
def battery_model():
    q = subprocess.run([sys.executable, "model/w2w_gold.py"], cwd=R_, capture_output=True, text=True, timeout=300)
    return None if q.returncode == 0 else "hand-checked scenarios"
if __name__ == "__main__":
    if "--battery-model" in sys.argv: print("RESULT", battery_model()); sys.exit(0)
    if "--battery" in sys.argv: print("RESULT", battery()); sys.exit(0)
    print("== 1. lint gate (Verilator -Wall --lint-only, Yosys 'check')")
    p = subprocess.run(["verilator", "--lint-only", "-Wall", "-Wno-DECLFILENAME", "-Wno-UNUSEDSIGNAL", "-Wno-UNUSEDPARAM", "--top-module", "w2w"] + F_[:-1], cwd=R_, capture_output=True, text=True); w_ = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning") and "sess.sv" not in l]
    y = subprocess.run(["yosys", "-p", "read_verilog -sv " + " ".join(F_[:-1]) + "; hierarchy -top w2w; proc; opt_clean; check"], cwd=R_, capture_output=True, text=True).stdout
    print(f"  w2w (all units): Verilator warnings {len(w_)}, Yosys check problems {len([l for l in y.splitlines() if 'Found and reported' in l and ' 0 problems' not in l])}")
    print("\n== 2. the model's self-test and what the traffic contains (seed 1)")
    print("  " + subprocess.run([sys.executable, "model/w2w_gold.py"], cwd=R_, capture_output=True, text=True).stdout.strip())
    print(f"  {'mix':11s} {'msgs kept':>9s} {'drops':>5s} {'books':>5s} {'offered':>7s} {'taken':>5s} {'missed':>6s} {'sent':>5s} {'refused':>7s} {'gate answers':>12s}")
    for i, kind in enumerate(KINDS):
        cyc, mev, kw = make(kind, i + 1); r = WG.run(cyc, mev, **kw); X = r["w2w"]; rows = r["rows"]
        sent = sum(1 for p in X.X.packets if p[1] == SS.ORDER); gate = Counter(RG.RN[row[23]] for row in rows if row[21] and row[22] == 0)
        print(f"  {kind:11s} {len(mev):9d} {X.drops:5d} {sum(row[4] for row in rows):5d} {sum(1 for row in rows if row[7]):7d} {len(X.orders):5d} {X.miss:6d} {sent:5d} {X.refused:7d} " + ", ".join(f"{k} {n}" for k, n in sorted(gate.items())))
    print("\n== 3. the whole design against the model: every cycle, every output (queue, counters, book, strategy, lifecycle, bytes on the wire)")
    print(f"  {'mix':11s} | {'cycles':>6s} {'orders':>6s} {'bytes sent':>10s} | {'Icarus':>7s} {'Verilator':>10s}")
    for i, kind in enumerate(KINDS):
        cm = make(kind, i + 1); r = WG.run(cm[0], cm[1], **cm[2]); X = r["w2w"]; nb = sum(len(p[2]) for p in X.X.packets if p[1] == SS.ORDER)
        a = same(cm); b = same(cm, "verilator")
        print(f"  {kind:11s} | {len(r['rows']):6d} {len(X.orders):6d} {nb:10d} | {'PASS' if a else 'FAIL':>7s} {'PASS' if b else 'FAIL':>10s}")
    print("\n== 4. the cycle budget: from the last byte of the message to the first byte of the order (all orders of all mixes)")
    st = {k: [] for k in ("wait", "book", "sigtrig", "life", "xmit", "total")}; byt = {}
    for i, kind in enumerate(KINDS):
        cm = make(kind, i + 1); X = WG.run(cm[0], cm[1], **cm[2])["w2w"]
        for tok, lg in X.log.items():
            if "cx" not in lg: continue
            st["wait"].append(lg["a"] - (lg["E"] + 1)); st["book"].append(lg["n"]); st["sigtrig"].append(lg["d"] - lg["r"]); st["life"].append(lg["ca"] - lg["d"]); st["xmit"].append(lg["cx"] + 1 - lg["ca"]); st["total"].append(lg["cx"] + 1 - (lg["E"] - 1))
            byt.setdefault(BG.TN[lg["t"]], []).append(lg["cx"] + 1 - (lg["E"] - 1))
    print(f"  {'stage':34s} {'min':>4s} {'mean':>6s} {'max':>4s}")
    names = {"wait": "queue wait (accepted - pushed - 1)", "book": "order book (n of the event)", "sigtrig": "signal + trigger (F + 4)", "life": "gate + tracker (offer to answer)", "xmit": "transmitter (answer to first byte)", "total": "TOTAL last byte in -> first byte out"}
    for k in ("wait", "book", "sigtrig", "life", "xmit", "total"):
        v = st[k]; print(f"  {names[k]:34s} {min(v):4d} {sum(v) / len(v):6.1f} {max(v):4d}") if v else None
    print("  by the type of the message that caused the order: " + ", ".join(f"{k} {len(v)} orders (total {min(v)}..{max(v)})" for k, v in sorted(byt.items())))
