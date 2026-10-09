#!/usr/bin/env python3
"""Chapter 11: the running designs. (1) lint; (2) the model: its frames are accepted by Chapter 9's filter, with the right fields; (3) both builders against the specification (every wire byte, including padding and FCS): 8 seeds each, Icarus, Verilator on one; the store-and-forward builder also with a slow source and with oversize payloads; (4) the cut-through builder with a source that stalls inside a payload: underruns; (5) the pacer alone against the cycle-exact model; (6) the pacer in the system: frames exact, and the token-bucket bound on the frame start times. Usage: ch11_run.py"""
import os, random, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, ip_gold as ipg, mac_gold as mg, udp_gold as g
R = flow.ROOT; F = ["rtl/crc32_stream.sv", "rtl/mac.sv", "rtl/udp.sv", "tb/udp_tb.sv"]; NAME = ["store-and-forward", "cut-through"]
def run(pk, ct, pace=0, rate=256, src=100, sim="icarus", **kw):
    g.write_pkts(pk, os.path.join(R, "out", "udp_desc.hex"), os.path.join(R, "out", "udp_bytes.hex"))
    d = (f"NP={len(pk)}", f"TOT={sum(len(q['payload']) for q in pk)}", f"CT={ct}", f"PACE={pace}", f"RATE={rate}", f"SRC={src}") + tuple(f"{k}={v}" for k, v in kw.items())
    return (flow.sim_icarus if sim == "icarus" else flow.sim_verilator)(F, "udp_tb", defines=d)[1]
def wires(o): return [w for w, _ in mg.parse_frames(o, "WIRE")]
def stats(o): m = re.search(r"STATS (\d+) (\d+) (\d+) (\d+)", o); return tuple(int(x) for x in m.groups()) if m else None
def starts(o): return [int(x) for x in re.findall(r"START (\d+)", o)]
if __name__ == "__main__":
    print("== 1. lint gate (Verilator -Wall --lint-only, Yosys 'check')")
    for top in ("udp_sf", "udp_ct", "pacer", "udp_tx_path"):
        p = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", top] + F[:3], cwd=R, capture_output=True, text=True); w = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning")]
        y = subprocess.run(["yosys", "-p", f"read_verilog -sv {' '.join(F[:3])}; hierarchy -top {top}; proc; opt_clean; check"], cwd=R, capture_output=True, text=True).stdout
        print(f"  {top:12s} Verilator warnings: {len(w)}   Yosys check problems: {len([l for l in y.splitlines() if 'Found and reported' in l and ' 0 problems' not in l])}")
    print("\n== 2. the model: the builder's frames are accepted by Chapter 9's header filter model, with the right addresses and ports")
    cfg = ipg.DEFAULT_CFG | {"ip_en": 0, "plo": 0, "phi": 65535}; pk = g.make_packets(1, 200); ok = 0; z = 0
    for i, q in enumerate(pk):
        b = g.build_body(q["payload"], q["dport"], q["dip"], i); b += bytes(max(0, 60 - len(b))); s = ipg.spec(b, 0, cfg); ok += s["cause"] == 0 and s["dport"] == q["dport"] and s["dip"] == q["dip"] and s["sport"] == g.SPORT and s["ulen"] == 8 + len(q["payload"]); z += g.build_body(q["payload"], q["dport"], q["dip"], i)[40:42] == b"\xff\xff"
    print(f"  {ok} of {len(pk)} frames forwarded with the fields intended; {z} of them carry a UDP checksum of 0xFFFF (a sum that comes out as zero is sent as all ones)")
    print("\n== 3. the builders against the specification: the whole wire frame (preamble, headers, payload, padding, FCS), every frame of every run")
    print(f"  {'builder':18s} {'source':>7s} {'seeds':>5s} {'packets':>8s} {'sent':>6s} {'dropped':>8s} | {'Icarus':>9s} {'Verilator':>10s}   underruns")
    for ct in (0, 1):
        for src in (100, 60) if ct == 0 else (100,):
            ok = 0; npk = nsent = ndrop = 0; v = "-"; un = 0
            for seed in range(8):
                pk = g.make_packets(seed, 30, oversize=(ct == 0)); o = run(pk, ct, src=src); exp, drop = g.expected_frames(pk, ct=bool(ct)); got = wires(o); ok += got == exp; npk += len(pk); nsent += len(exp); ndrop += drop; un += (stats(o) or (0, 0, 0, 0))[2]
                if seed == 0: v = "PASS" if wires(run(pk, ct, src=src, sim="verilator")) == exp else "FAIL"
            print(f"  {NAME[ct]:18s} {src:6d}% {8:5d} {npk:8d} {nsent:6d} {ndrop:8d} | {ok:6d} of 8 {v:>10s}   {un}")
    print(f"  (the store-and-forward builder drops a payload above {g.MAXP} bytes, whole, and counts it; the cut-through builder is given only lengths it can send; the frame id counts frames sent, so a dropped packet leaves no gap)")
    print("\n== 4. the cut-through builder cannot wait: a source that stalls inside a payload makes the MAC underrun (the wire cannot pause)")
    print(f"  {'source speed':>12s} | {'frames exact':>13s} {'underrun flag':>14s}   (8 seeds, 12 packets each; store-and-forward for comparison)")
    for src in (100, 90, 60):
        r = {}
        for ct in (1, 0):
            ex = un = 0
            for seed in range(8):
                pk = g.make_packets(100 + seed, 12); o = run(pk, ct, src=src); e, _ = g.expected_frames(pk, ct=bool(ct)); ex += wires(o) == e; un += (stats(o) or (0, 0, 0, 0))[2]
            r[ct] = (ex, un)
        print(f"  {src:11d}% | cut-through {r[1][0]} of 8, underrun in {r[1][1]} of 8 runs;   store-and-forward {r[0][0]} of 8, underrun in {r[0][1]}")
    print("\n== 5. the pacers alone against their cycle-exact models: every grant cycle and length (20,000 cycles of random requests that hold their length for at least 4 cycles)")
    print(f"  {'pacer':26s} {'rate /256':>9s} {'grants':>7s} | {'3 seeds equal':>14s}")
    for comb, nm in ((0, "pipelined (final)"), (1, "combinational (first)")):
        for rate in (4, 16, 64, 200, 256):
            ok = 0; ng = 0
            for seed in range(3):
                st = g.pacer_stim(seed, 20000); g.write_pacer(os.path.join(R, "out", "pacer_stim.hex"), st)
                o = flow.sim_icarus(["rtl/udp.sv", "tb/pacer_tb.sv"], "pacer_tb", defines=(f"NC={len(st)}", f"RATE={rate}", f"COMB={comb}"))[1]; got = [(int(a), int(b)) for a, b in re.findall(r"G (\d+) (\d+)", o)]
                m = g.PacerModelComb() if comb else g.PacerModel(rate=rate); exp = [(k, ln) for k, (r, ln) in enumerate(st) if m.step(r, ln, rate)]; ok += got == exp; ng += len(got)
            print(f"  {nm:26s} {rate:9d} {ng // 3:7d} | {ok:11d} of 3")
    print("\n== 6. the pacer in the system: frames exact, and the token-bucket bound on the frame start times (any frames i..j: the sum of their costs <= bucket + rate x (start j - start i))")
    print(f"  {'builder':18s} {'pacer':>12s} {'rate':>5s} {'frames':>7s} {'exact':>6s} {'bound holds':>12s} {'tightest slack':>15s}")
    for ct, pace, rate in ((0, 1, 16), (0, 1, 64), (0, 1, 160), (1, 1, 16), (1, 1, 64), (1, 1, 160), (1, 2, 64)):
        pk = g.make_packets(7, 40, sizes=[18, 100, 400, 1000]); pk = [q for q in pk if len(q["payload"]) <= g.MAXP]; o = run(pk, ct, pace=pace, rate=rate); e, _ = g.expected_frames(pk, ct=bool(ct)); st = starts(o); cost = [g.wire_cost(len(q["payload"])) for q in pk]
        worst = None; ok = True
        for i in range(len(st)):
            tot = 0
            for j in range(i, len(st)):
                tot += cost[j]; sl = 4096 + rate * (st[j] - st[i]) / 256 - tot; worst = sl if worst is None else min(worst, sl); ok &= sl >= -1e-9
        print(f"  {NAME[ct]:18s} {'pipelined' if pace == 1 else 'combinational':>12s} {rate:5d} {len(st):7d} {'YES' if wires(o) == e else 'NO':>6s} {'YES' if ok else 'NO':>12s} {worst:12.1f} B")
    print("  (the rate is in 1/256 byte per cycle: 64 = a quarter of line rate; the bucket is 4,096 bytes; cost = preamble + frame (padded) + FCS + gap in bytes = cycles at line rate)")
