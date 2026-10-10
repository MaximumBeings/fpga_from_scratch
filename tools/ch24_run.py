#!/usr/bin/env python3
"""Chapter 24: the running designs. (1) lint; (2) the model: the BYTES of every packet against an encoder written with Python's struct module (independent of the model's own encoder), and the session scenarios the stimulus contains; (3) the transmitter against the model, every beat (data, last, bytes), the state, the expected sequence number, `ready` and the answer to every request in every cycle, in two simulators, for five formats (beat width W, symbols, heartbeat interval, login timeout), on scenarios: a normal session, a rejected login, a login that is never answered, a server that falls silent, a sequence gap, an end of session (and one while logging in), a logout, server heartbeats on the very last cycle that saves the session, a session that was never configured, and random mixes with random server events."""
import os, random, struct, subprocess, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, sess_gold as G
R_ = flow.ROOT; F_ = ["rtl/sess.sv", "tb/sess_tb.sv"]
def rows_rtl(res, cfg, simu="icarus", rtl=F_):
    w, ns, hb, tl = cfg; n = G.write_stim(os.path.join(R_, "out", "sess_stim.hex"), res["lines"])
    o = (flow.sim_icarus if simu == "icarus" else flow.sim_verilator)(rtl, "sess_tb", defines=(f"NC={n}", f"W={w}", f"NS={ns}", f"HB={hb}", f"TL={tl}") + (("GARBAGE",) if simu == "icarus" else ()))[1]
    try: return [tuple(int(x, 16) if i == 3 else int(x) for i, x in enumerate(l.split()[1:])) for l in o.splitlines() if l.startswith("C ")]
    except ValueError: return [("x",)]
def same(cy, cfg, simu="icarus", rtl=F_):
    res = G.run(cy, *cfg); got = rows_rtl(res, cfg, simu, rtl); exp = G.expected_rows(res)
    return got[:len(exp)] == exp and len(got) >= len(exp)
CONFIGS = [(8, 4, 20, 60), (1, 4, 20, 60), (2, 3, 9, 25), (4, 15, 12, 40), (8, 1, 7, 15)]
CFGW = [(0, 0, 0x41424344), (0, 1, 0x49424D20), (0, 2, 0x474F4F47), (0, 3, 0x4D534654), (1, 0, 0x55534552), (2, 0, 0x50415353), (3, 0, 0x46495230), (4, 0, 0x5943), (5, 0, 1000)]
def cfg_cycles(ns): return [dict(cfg=c) for c in CFGW if not (c[0] == 0 and c[1] >= ns)] + [dict(), dict()]
def rq(kind, rng, ns, **kw):
    d = dict(tok=rng.getrandbits(32), tok2=rng.getrandbits(32), sym=rng.randrange(ns + (1 if rng.random() < .1 else 0)), side=rng.randrange(2), shares=rng.randint(1, 10 ** 6), px=rng.randint(1, 10 ** 6), tif=rng.choice([0, 99999, rng.getrandbits(32)])); d.update(kw); return (kind, d)
def scenario(kind, rng, w, ns, hb, tl, n=260):
    cy = cfg_cycles(ns) if kind != "bare" else [dict(), dict()]; L = len(cy); cy += [dict() for _ in range(n)]
    def put(c, k, v):
        while c >= len(cy): cy.append(dict())
        cy[c][k] = v
    put(L + 2, "req", (G.LOGINQ, {}))
    acc_at = L + 2 + rng.randint(4, 12)
    if kind == "closelogin": put(acc_at - 2 if acc_at - 2 > L + 3 else L + 4, "rx", ("Z", 0)); put(acc_at + 5, "rx", ("A", 5))     # an end of session before the login is answered; a late 'A' changes nothing
    elif kind == "silent": pass                                                                               # no answer to the login: DEAD after TL
    elif kind == "reject": put(acc_at, "rx", ("J", 0))
    elif kind != "closelogin": put(acc_at, "rx", ("A", rng.getrandbits(32) if rng.random() < .3 else 1000))
    seq = None
    for c in range(acc_at + 3, acc_at + n - 10):
        cyc = cy[c] if c < len(cy) else {}
        if rng.random() < 0.3 and "req" not in cyc: put(c, "req", rq(rng.choice([G.ORDER, G.ORDER, G.ORDER, G.CANCEL, G.REPLACE, G.LOGINQ, G.ORDER]), rng, ns))
    if kind in ("normal", "gap", "close", "logout", "random"):
        sq = 1000
        for c in range(acc_at + 5, acc_at + n - 10, 1):
            if rng.random() < (1.0 / max(2, hb // 2)): put(c, "rx", rng.choice([("H", 0), ("S", sq)])); sq += 1 if cy[c]["rx"][0] == "S" else 0
        if kind == "random":
            for _ in range(3):
                c = rng.randrange(acc_at + 5, acc_at + n - 10); put(c, "rx", rng.choice([("S", rng.getrandbits(32)), ("H", 0), ("A", 5), ("J", 0), ("Z", 0)]))
            if rng.random() < .5:
                c = rng.randrange(acc_at + 20, acc_at + n - 10); put(c, "req", (G.LOGOUT, {}))
        if kind == "gap": put(acc_at + rng.randint(30, 80), "rx", ("S", 4242))
        if kind == "close": put(acc_at + rng.randint(30, 80), "rx", ("Z", 0))
        if kind == "logout": put(acc_at + rng.randint(30, 80), "req", (G.LOGOUT, {}))
    if kind == "limit":                                                                                       # heartbeats from the server spaced exactly 3 HB apart (each is the last chance), then one cycle too late
        c = acc_at
        for _ in range(4): c += 3 * hb; put(c, "rx", ("H", 0))
        c += 3 * hb + 1; put(c, "rx", ("H", 0))
    if kind == "dead":
        for c in range(acc_at + 5, acc_at + 60, max(3, hb // 2)): put(c, "rx", ("H", 0))                  # the server speaks for a while, then falls silent
    return cy
KINDS = ("normal", "reject", "silent", "dead", "gap", "close", "logout", "random", "closelogin", "limit", "bare")
def make(kind, seed, cfg): w, ns, hb, tl = cfg; return scenario(kind, random.Random(seed * 100 + hash(kind) % 97), *cfg)
def battery():
    """The mutation runs' test: five formats, the eight scenarios, Icarus. -> None or the first difference."""
    for ci, cfg in enumerate(CONFIGS):
        for kind in KINDS:
            try: ok = same(make(kind, ci, cfg), cfg)
            except Exception as x: return f"crash {type(x).__name__}"
            if not ok: return f"{kind}, W {cfg[0]}, NS {cfg[1]}, HB {cfg[2]}, TL {cfg[3]}"
    return None
def battery_model():
    q = subprocess.run([sys.executable, "model/sess_gold.py"], cwd=R_, capture_output=True, text=True, timeout=300)
    return None if q.returncode == 0 else "hand-checked scenarios"
def struct_packet(kind, r, cfg):
    """An independent encoder, with struct.pack (formats as written in the specification)."""
    if kind == G.ORDER: return struct.pack(">HcccI c I 4s I I 4s B B".replace(" ", ""), 29, b"U", b"O", b"", r["tok"], b"S" if r["side"] else b"B", r["shares"], cfg["stock"][r["sym"]], r["px"], r["tif"], cfg["firm"], cfg["display"], cfg["capacity"]) if False else struct.pack(">H2sIc I4sII4sBB".replace(" ", ""), 29, b"UO", r["tok"], b"S" if r["side"] else b"B", r["shares"], cfg["stock"][r["sym"]], r["px"], r["tif"], cfg["firm"], cfg["display"], cfg["capacity"])
    if kind == G.CANCEL: return struct.pack(">H2sII", 10, b"UX", r["tok"], r["shares"])
    if kind == G.REPLACE: return struct.pack(">H2sIIIIIB", 23, b"UN", r["tok"], r["tok2"], r["shares"], r["px"], r["tif"], cfg["display"])
    if kind == G.LOGINQ: return struct.pack(">Hc4s4sI", 13, b"L", cfg["user"], cfg["pw"], cfg["seq"])
    if kind == G.LOGOUT: return struct.pack(">Hc", 1, b"O")
    return struct.pack(">Hc", 1, b"R")
if __name__ == "__main__":
    if "--battery-model" in sys.argv: print("RESULT", battery_model()); sys.exit(0)
    if "--battery" in sys.argv: print("RESULT", battery()); sys.exit(0)
    print("== 1. lint gate (Verilator -Wall --lint-only, Yosys 'check')")
    p = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", "sess", "rtl/sess.sv"], cwd=R_, capture_output=True, text=True); w_ = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning") and "DECLFILENAME" not in l]
    y = subprocess.run(["yosys", "-p", "read_verilog -sv rtl/sess.sv; hierarchy -top sess; proc; opt_clean; check"], cwd=R_, capture_output=True, text=True).stdout
    print(f"  sess: Verilator warnings {len(w_)}, Yosys check problems {len([l for l in y.splitlines() if 'Found and reported' in l and ' 0 problems' not in l])}")
    print("\n== 2. the model (python3 model/sess_gold.py); the bytes of 2,000 random packets of every kind against struct.pack; the scenarios (W 8, NS 4, HB 20, TL 60, seed 0)")
    print("  " + subprocess.run([sys.executable, "model/sess_gold.py"], cwd=R_, capture_output=True, text=True).stdout.strip())
    rng = random.Random(4); bad = 0; sizes = Counter()
    for _ in range(2000):
        cfg = G.new_cfg(4); cfg.update(user=rng.randbytes(4), pw=rng.randbytes(4), seq=rng.getrandbits(32), firm=rng.randbytes(4), display=rng.randrange(256), capacity=rng.randrange(256)); cfg["stock"] = [rng.randbytes(4) for _ in range(4)]
        k = rng.choice([G.ORDER, G.CANCEL, G.REPLACE, G.LOGINQ, G.LOGOUT, G.HEARTBEAT]); r = rq(k, rng, 4)[1]; r["sym"] %= 4
        a = G.packet(k, r, cfg, 4); b = struct_packet(k, r, cfg); bad += a != b; sizes[(k, len(a))] += 1
    print(f"  packets whose bytes differ from struct.pack: {bad} of 2000; sizes on the wire: " + ", ".join(f"{(['ORDER', 'CANCEL', 'REPLACE', 'LOGIN', 'LOGOUT'] + ['HEARTBEAT'])[k if k >= 0 else 5]} {n}" for (k, n) in sorted(set(sizes))))
    for kind in KINDS:
        cy = make(kind, 0, CONFIGS[0]); res = G.run(cy, *CONFIGS[0]); st = Counter(r[5] for r in res["rows"]); pk = Counter(G.KN[k] if k >= 0 else "HEARTBEAT" for _, k, _ in res["packets"]); an = Counter(G.RN[r[8]] for r in res["rows"] if r[7])
        print(f"  {kind:7s} states: " + ", ".join(f"{G.SN[s]} {n}" for s, n in sorted(st.items())) + " | packets: " + ", ".join(f"{k} {n}" for k, n in sorted(pk.items())) + " | answers: " + ", ".join(f"{k} {n}" for k, n in sorted(an.items())))
    print("\n== 3. the transmitter against the model: beats, state, expected sequence number, ready and answers in every cycle")
    print(f"  {'scenario':8s} {'W':>2s} {'NS':>3s} {'HB':>3s} {'TL':>3s} | {'cycles':>7s} {'beats':>6s} {'packets':>8s} | {'Icarus':>7s} {'Verilator':>10s}")
    for kind in KINDS:
        for cfg in CONFIGS:
            cy = make(kind, 1, cfg); res = G.run(cy, *cfg); i = same(cy, cfg); v = same(cy, cfg, "verilator")
            print(f"  {kind:8s} {cfg[0]:2d} {cfg[1]:3d} {cfg[2]:3d} {cfg[3]:3d} | {len(res['rows']):7d} {sum(r[1] for r in res['rows']):6d} {len(res['packets']):8d} | {'PASS' if i else 'FAIL':>7s} {'PASS' if v else 'FAIL':>10s}")
