#!/usr/bin/env python3
"""Chapter 16: the running designs. (1) the generator is deterministic and its output lints; (2) the model: hand-checked scenarios and the properties of the stimulus; (3) the generated parser against the model, every message and packet end with its cycle, in two simulators; (4) the generator on a second grammar (two message types, different widths): the same tests, the same model machinery."""
import os, random, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, grammar, gen_parser as GP, itch_gold as G
R = flow.ROOT; F = ["rtl/mold_itch.sv", "tb/mold_tb.sv"]
FIELDS = list(grammar.fields(grammar.ITCH))                                              # the order of the tb's print list
def sim(lines, simu="icarus"):
    n = G.write_stim(os.path.join(R, "out", "mold_stim.hex"), lines)
    o = (flow.sim_icarus if simu == "icarus" else flow.sim_verilator)(F, "mold_tb", defines=(f"NC={n}",))[1]
    return o
def parse_out(o, fields=FIELDS):
    ev = []
    for l in o.splitlines():
        t = l.split()
        if not t: continue
        if t[0] == "M": ev.append(("M", int(t[1]), int(t[2]), int(t[3]), int(t[4]), int(t[5], 16 if False else 10), dict(zip(fields, t[6:]))))
        elif t[0] == "P": ev.append(("P", int(t[1]), int(t[2]), int(t[3]), t[4], int(t[5])))
    return ev
def compare(got, exp, fields=FIELDS, widths=None):
    """-> None or the first difference. Messages are compared on type, err, idx, seq and (for err 0) the fields the type has, as hex."""
    if len(got) != len(exp): return f"{len(got)} events, expected {len(exp)}"
    for g, e in zip(got, exp):
        if g[0] != e[0]: return f"event kind {g[0]} vs {e[0]}"
        if g[0] == "M":
            if g[1:6] != e[1:6]: return f"message at cycle {g[1]}: {g[1:6]} vs {e[1:6]}"
            for nm, v in e[6].items():
                w = (G.WIDTH if widths is None else widths)[nm] * 2                                   # widths from the MODEL, not from the grammar under test
                if g[6].get(nm, "").lower() != "%0*x" % (w, v): return f"message at cycle {g[1]}: field {nm} = {g[6][nm]} vs {v:x}"
        else:
            if e[4] is None:
                if g[1:4] != e[1:4]: return f"packet end at {g[1]}: {g[1:4]} vs {e[1:4]}"
            elif (g[1], g[2], g[3], int(g[4], 16), g[5]) != (e[1], e[2], e[3], e[4], e[5]): return f"packet end at {g[1]}: {g[1:]} vs {e[1:]}"
    return None
def make(seed, n, **kw):
    rng = random.Random(seed); pk = G.random_packets(rng, n, **kw); lines, packets = G.schedule(rng, pk, gap=rng.choice([0, 0.1, 0.4]), stray=0.3, between=(0, 4)); return lines, packets
def check(seed, n, simu="icarus", **kw):
    lines, packets = make(seed, n, **kw); return compare(parse_out(sim(lines, simu)), G.decode(packets)), packets
def battery():
    """The test of the mutation runs: regenerate (unless --no-regen), then the parser against the model on four kinds of stream, Icarus only. -> None or the first difference."""
    if "--no-regen" not in sys.argv: GP.gen_tb_includes(grammar.ITCH, os.path.join(R, "out")); open(os.path.join(R, "rtl/mold_itch.sv"), "w").write(GP.gen(grammar.ITCH))
    global FIELDS; FIELDS = list(grammar.fields(grammar.ITCH))
    for kw in ({}, dict(p_err=0.9), dict(p_err=0.0), dict(maxmsg=30, p_err=0.05)):
        for seed in (1, 2, 3):
            try: err, _ = check(seed, 30, **kw)
            except Exception as x: return f"crash {type(x).__name__}"
            if err: return err
    return None
if __name__ == "__main__":
    if "--battery" in sys.argv: print("RESULT", battery()); sys.exit(0)
    print("== 1. the generator: deterministic, and its output lints")
    a = GP.gen(grammar.ITCH); b = GP.gen(grammar.ITCH); print(f"  two runs give the same text: {a == b}; the checked-in rtl/mold_itch.sv equals it: {open(os.path.join(R, 'rtl/mold_itch.sv')).read() == a}; {len(a.splitlines())} lines for {len(grammar.ITCH)} message types and {len(FIELDS)} fields")
    p = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", "mold_itch", "rtl/mold_itch.sv"], cwd=R, capture_output=True, text=True); w = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning")]
    y = subprocess.run(["yosys", "-p", "read_verilog -sv rtl/mold_itch.sv; hierarchy -top mold_itch; proc; opt_clean; check"], cwd=R, capture_output=True, text=True).stdout
    print(f"  Verilator warnings: {len(w)}   Yosys check problems: {len([l for l in y.splitlines() if 'Found and reported' in l and ' 0 problems' not in l])}")
    print("\n== 2. the model (python3 model/itch_gold.py) and what the stimulus contains (8 seeds of 60 packets)")
    print("  " + subprocess.run([sys.executable, "model/itch_gold.py"], cwd=R, capture_output=True, text=True).stdout.strip())
    from collections import Counter
    c = Counter(); k = Counter(); tot = 0
    for seed in range(8):
        _, packets = make(seed, 60); ev = G.decode(packets); tot += len(packets)
        for e in ev:
            if e[0] == "M": c[("ok " if e[3] == 0 else "err%d" % e[3]) + (" " + chr(e[2]) if e[3] == 0 else "")] += 1
            else: k[("trunc " if e[2] else "") + ("cntbad" if e[3] else "") or "clean"] += 1
        k["no eop (abandoned)"] += sum(1 for p in packets if not p["eop"])
    print(f"  {tot} packets: " + ", ".join(f"{a} {b}" for a, b in sorted(k.items())))
    print("  messages: " + ", ".join(f"{a} {b}" for a, b in sorted(c.items())))
    print("\n== 3. the generated parser against the model: every message (type, error, index, sequence number, the fields the type has) and every packet end, each at its cycle (the cycle after the last byte)")
    print(f"  {'idle cycles':>11s} {'seeds':>5s} {'packets':>8s} {'messages':>9s} {'bytes':>7s} | {'Icarus':>9s} {'Verilator':>10s}")
    for gap_name, kw in (("mixed", {}), ("faults only", dict(p_err=0.9)), ("well formed", dict(p_err=0.0)), ("long packets", dict(maxmsg=40, p_err=0.05))):
        ok = 0; npk = nm = nb = 0; v = "-"
        for seed in range(6):
            err, packets = check(seed, 40, **kw); ok += err is None; npk += len(packets); nm += sum(1 for e in G.decode(packets) if e[0] == "M"); nb += sum(len(p["bytes"]) for p in packets)
            if seed == 0: err_v, _ = check(seed, 40, "verilator", **kw); v = "PASS" if err_v is None else "FAIL"
        print(f"  {gap_name:>11s} {6:5d} {npk:8d} {nm:9d} {nb:7d} | {ok:6d} of 6 {v:>10s}")
    print("\n== 4. the same generator on a second grammar (two message types, a 3-byte and a 10-byte field): generated, simulated, compared with a model built from the same struct idea")
    g2 = {"Q": [("a", 3), ("b", 1)], "R": [("a", 3), ("c", 10)]}
    import shutil, tempfile
    d = tempfile.mkdtemp(prefix="g2_"); os.makedirs(os.path.join(d, "rtl")); os.makedirs(os.path.join(d, "tb")); os.makedirs(os.path.join(d, "out"))
    open(os.path.join(d, "rtl/mold_itch.sv"), "w").write(GP.gen(g2)); GP.gen_tb_includes(g2, os.path.join(d, "out")); shutil.copy(os.path.join(R, "tb/mold_tb.sv"), os.path.join(d, "tb/mold_tb.sv"))
    rng = random.Random(5); msgs = []
    def m2(t): return (b"Q" + bytes(rng.getrandbits(8) for _ in range(4))) if t == "Q" else (b"R" + bytes(rng.getrandbits(8) for _ in range(13)))
    pk = [dict(data=G.build_packet(rng, [m2(rng.choice("QR")) for _ in range(rng.randint(0, 5))]), eop=True) for _ in range(40)]
    lines, packets = G.schedule(rng, pk, gap=0.1); n = G.write_stim(os.path.join(d, "out/mold_stim.hex"), lines)
    o = flow.sim_icarus(["rtl/mold_itch.sv", "tb/mold_tb.sv"], "mold_tb", root=d, defines=(f"NC={n}",))[1]; got = parse_out(o, ["a", "b", "c"]); ok = 0; nmsg = 0; bad = None
    # expected from the packet bytes directly
    exp = []
    for p in packets:
        b = [x for _, x in p["bytes"]]; cy = [c for c, _ in p["bytes"]]; seq = int.from_bytes(bytes(b[10:18]), "big"); pos = 20; idx = 0
        while pos < len(b):
            L = b[pos] * 256 + b[pos + 1]; body = bytes(b[pos + 2:pos + 2 + L]); end = cy[pos + 1 + L] + 1
            f = {"a": int.from_bytes(body[1:4], "big"), "b": body[4]} if body[0] == ord("Q") else {"a": int.from_bytes(body[1:4], "big"), "c": int.from_bytes(body[4:14], "big")}
            exp.append(("M", end, body[0], 0, idx, seq, f)); idx += 1; pos += 2 + L
        exp.append(("P", cy[-1] + 1, 0, 0, int.from_bytes(bytes(b[0:10]), "big"), int.from_bytes(bytes(b[18:20]), "big")))
    err = compare(got, exp, ["a", "b", "c"], {"a": 3, "b": 1, "c": 10}); nmsg = sum(1 for e in exp if e[0] == "M")
    print(f"  {len(a.splitlines())} lines of ITCH parser, {len(GP.gen(g2).splitlines())} lines for the second grammar; {len(packets)} packets, {nmsg} messages: {'all equal' if err is None else 'DIFFERENT: ' + err}")
    shutil.rmtree(d, ignore_errors=True)
