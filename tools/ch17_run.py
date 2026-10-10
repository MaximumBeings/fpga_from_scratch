#!/usr/bin/env python3
"""Chapter 17: the running designs. (1) the generator is deterministic and its output lints; (2) the model and the stimulus; (3) the W-bytes-per-beat parser against the model for W = 2, 4, 8 on four kinds of stream, every message, framing error and packet end at its cycle, in two simulators; (4) throughput: cycles per packet against W."""
import os, random, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, grammar, gen_parser_wide as GW, itch_gold as I, wide_gold as WG
R = flow.ROOT; FIELDS = list(grammar.fields(grammar.ITCH)); VERSION = int(os.environ.get('MOLD_VERSION', '2'))                   # the design under test: 2 is the rebuilt one (the checked-in rtl/mold_wide.sv)
def rtl_text(W, version=None): return {1: GW.gen, 2: GW.gen_pipe, 3: GW.gen_v3}[version or VERSION](grammar.ITCH, "mold_wide", W)
def sim(lines, W, simu="icarus", rtl="rtl/mold_wide.sv"):
    n = WG.write_stim(os.path.join(R, "out", "wide_stim.hex"), lines, W)
    return (flow.sim_icarus if simu == "icarus" else flow.sim_verilator)([rtl, "tb/wide_tb.sv"], "wide_tb", defines=(f"NC={n}", f"WB={W}"))[1]
def parse_out(o):
    ev = []
    for l in o.splitlines():
        t = l.split()
        if not t: continue
        if t[0] == "M": ev.append(("M", int(t[1]), int(t[2]), int(t[3]), int(t[4]), int(t[5]), dict(zip(FIELDS, t[6:]))))
        elif t[0] == "X": ev.append(("X", int(t[1]), int(t[2])))
        elif t[0] == "P": ev.append(("P", int(t[1]), int(t[2]), int(t[3]), t[4], int(t[5])))
    return ev
def compare(got, exp):
    if len(got) != len(exp): return f"{len(got)} events, expected {len(exp)}"
    for g, e in zip(got, exp):
        if g[0] != e[0]: return f"event kind {g[0]} vs {e[0]} at cycle {g[1]}"
        if g[0] == "M":
            if g[1:6] != e[1:6]: return f"message at cycle {g[1]}: {g[1:6]} vs {e[1:6]}"
            for nm, v in e[6].items():
                if g[6].get(nm, "").lower() != "%0*x" % (I.WIDTH[nm] * 2, v): return f"message at cycle {g[1]}: field {nm} = {g[6].get(nm)} vs {v:x}"
        elif g[0] == "X":
            if g[1:] != e[1:]: return f"framing error {g[1:]} vs {e[1:]}"
        elif e[4] is None:
            if g[1:4] != e[1:4]: return f"packet end {g[1:4]} vs {e[1:4]}"
        elif (g[1], g[2], g[3], int(g[4], 16), g[5]) != (e[1], e[2], e[3], e[4], e[5]): return f"packet end {g[1:]} vs {e[1:]}"
    return None
def make(seed, W, n, **kw):
    rng = random.Random(seed); pk = WG.alignment_packets(rng, n) if kw.pop("align", False) else I.random_packets(rng, n, **kw); return WG.schedule(rng, pk, W, gap=rng.choice([0, 0.1, 0.4]), stray=0.3, between=(0, 4))
def check(seed, W, n, simu="icarus", rtl="rtl/mold_wide.sv", lat=None, **kw):
    lines, packets = make(seed, W, n, **kw); return compare(parse_out(sim(lines, W, simu, rtl)), WG.decode(packets, lat or {1: 1}.get(VERSION, 2))), packets
KINDS = (("mixed", {}), ("faults only", dict(p_err=0.9)), ("well formed", dict(p_err=0.0)), ("long packets", dict(maxmsg=40, p_err=0.05)), ("alignments", dict(align=True)))
def battery():
    """The mutation runs' test: W = 8 (the checked-in design, or the regenerated one) and W = 4 on four kinds of stream, Icarus."""
    if "--no-regen" not in sys.argv:
        for W in (4, 8): open(os.path.join(R, f"out/ex_wide{W}.sv"), "w").write(rtl_text(W))
        GW.gen_tb_includes(grammar.ITCH, os.path.join(R, "out"))
    for W in (8, 4):
        rtl = "rtl/mold_wide.sv" if W == 8 else "out/ex_wide4.sv"
        if W == 8 and "--no-regen" not in sys.argv: rtl = "out/ex_wide8.sv"
        for _, kw in KINDS:
            for seed in (1, 2):
                try: err, _ = check(seed, W, 120 if kw.get("align") else 30, rtl=rtl, **kw)
                except Exception as x: return f"crash {type(x).__name__}"
                if err: return f"W={W}: {err}"
    return None
if __name__ == "__main__":
    if "--battery" in sys.argv: print("RESULT", battery()); sys.exit(0)
    print("== 1. the generator: deterministic, and its output lints")
    a = rtl_text(8); print(f"  two runs give the same text: {a == rtl_text(8)}; the checked-in rtl/mold_wide.sv (W = 8) equals it: {open(os.path.join(R, 'rtl/mold_wide.sv')).read() == a}; {len(a.splitlines())} lines for W = 8 ({len(rtl_text(4).splitlines())} for W = 4, {len(rtl_text(2).splitlines())} for W = 2)")
    for W in (2, 4, 8):
        open(os.path.join(R, f"out/ex_wide{W}.sv"), "w").write(rtl_text(W)); p = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", "mold_wide", f"out/ex_wide{W}.sv"], cwd=R, capture_output=True, text=True); w = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning")]
        y = subprocess.run(["yosys", "-p", f"read_verilog -sv out/ex_wide{W}.sv; hierarchy -top mold_wide; proc; opt_clean; check"], cwd=R, capture_output=True, text=True).stdout
        print(f"  W = {W}: Verilator warnings {len(w)}, Yosys check problems {len([l for l in y.splitlines() if 'Found and reported' in l and ' 0 problems' not in l])}")
    GW.gen_tb_includes(grammar.ITCH, os.path.join(R, "out"))
    print("\n== 2. the model (python3 model/wide_gold.py) and what the stimulus contains (W = 8, 8 seeds of 60 packets)")
    print("  " + subprocess.run([sys.executable, "model/wide_gold.py"], cwd=R, capture_output=True, text=True).stdout.strip())
    from collections import Counter
    c = Counter(); tot = 0; short = 0; multi = 0
    for seed in range(8):
        lines, packets = make(seed, 8, 60); ev = WG.decode(packets); tot += len(packets); short += sum(1 for l in lines if l[0] and l[4] < 8 and l[2] == 0 and l[1] == 0)
        for e in ev: c[e[0] + (str(e[3]) if e[0] == "M" else (str(e[2]) if e[0] == "P" else ""))] += 1
        cyc = Counter(e[1] for e in ev if e[0] == "M"); multi += sum(1 for v in cyc.values() if v > 1)
    print(f"  {tot} packets: messages ok {c['M0']}, unknown type {c['M1']}, bad length {c['M2']}; framing errors (X) {c['X']}; packet ends clean {c['P0']}, truncated or abandoned {c['P1']}")
    print("\n== 3. the parser against the model, W = 2, 4, 8: every message, framing error and packet end, each at its cycle (the cycle after the beat), 6 seeds of 40 packets per kind")
    print(f"  {'W':>2s} {'stream':>12s} {'packets':>8s} {'messages':>9s} {'beats':>7s} {'framing errors':>15s} | {'Icarus':>9s} {'Verilator':>10s}")
    for W in (2, 4, 8):
        rtl = f"out/ex_wide{W}.sv"
        for nm, kw in KINDS:
            ok = 0; npk = nm_ = nbt = nx = 0; v = "-"
            for seed in range(6):
                err, packets = check(seed, W, 40, rtl=rtl, **kw); ok += err is None; ev = WG.decode(packets, {1: 1}.get(VERSION, 2)); npk += len(packets); nm_ += sum(1 for e in ev if e[0] == "M"); nx += sum(1 for e in ev if e[0] == "X")
                lines, _ = make(seed, W, 40, **kw); nbt += sum(1 for l in lines if l[0])
                if seed == 0: ev_, _ = check(seed, W, 40, "verilator", rtl, **kw); v = "PASS" if ev_ is None else "FAIL"
            print(f"  {W:2d} {nm:>12s} {npk:8d} {nm_:9d} {nbt:7d} {nx:15d} | {ok:6d} of 6 {v:>10s}")
    print("\n== 3b. the three versions of the generator (1: the chain of byte steps unrolled; 2: framing and field assembly in two pipeline stages; 3: as 2 with the header bytes written by position), each against the model (latency 1, 2, 2), 6 seeds of 40 packets on the mixed and the faults-only streams")
    print(f"  {'W':>2s} {'version':>7s} {'latency':>8s} | {'mixed':>9s} {'faults only':>12s}")
    for W in (2, 4, 8):
        for v in (1, 2, 3):
            f = f"out/ex_v{v}_w{W}.sv"; open(os.path.join(R, f), "w").write(rtl_text(W, v)); r = []
            for _, kw in KINDS[:2]: r.append(sum(check(seed, W, 40, rtl=f, lat=1 if v == 1 else 2, **kw)[0] is None for seed in range(6)))
            print(f"  {W:2d} {v:7d} {1 if v == 1 else 2:8d} | {r[0]:6d} of 6 {r[1]:9d} of 6")
    print("\n== 4. throughput: clean packets of 12 ITCH messages (the A/D/E mix of Chapter 16, example B) back to back, no idle cycles; cycles from the first beat to the packet end")
    print(f"  {'bytes per beat':>14s} {'bytes per packet':>17s} {'cycles per packet':>18s} {'bytes per cycle':>16s} {'derived cycles':>15s}")
    rng = random.Random(5)
    for W in (1, 2, 4, 8):
        if W == 1: print(f"  {1:14d} {'(Chapter 16)':>17s} {'= bytes':>18s} {1.0:16.2f}"); continue
        msgs = [I.build_msg(rng, rng.choice("AAAADDEEXUPSF")) for _ in range(12)]; pk = I.build_packet(rng, msgs); lines, packets = WG.schedule(rng, [dict(data=pk, eop=True)] * 20, W, gap=0, stray=0, between=(0, 0))
        ev = WG.decode(packets); ends = [e[1] for e in ev if e[0] == "P"]; firsts = [p["bytes"][0][0] for p in packets]
        cyc = (ends[-1] - firsts[0]) / len(packets); print(f"  {W:14d} {len(pk):17d} {cyc:18.2f} {len(pk) / cyc:16.2f} {-(-len(pk) // W):15d}")
