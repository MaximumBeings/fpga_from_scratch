#!/usr/bin/env python3
"""Chapter 9: the running designs. (1) lint; (2) the model against known checksums; (3) hdr_filter (final version) against the specification on 4 configurations x 8 seeds x 2 stimulus styles (frames back to back with no idle cycle; random gaps and idle cycles inside frames), Icarus on all and Verilator on one per configuration: for every frame the bytes, the bad flag, the cause and every captured field must equal the model's; (4) one byte per clock: a back-to-back stream, bytes in = cycles, latency; (5) hdr_path (mac_rx + hdr_filter + frame_fifo) from the PHY wires: frames delivered and counts per cause; (6) the three checksum accumulators against the model. Usage: ch09_run.py"""
import os, random, re, subprocess, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, ip_gold as g, mac_gold as m
R = flow.ROOT
HF = ["rtl/hdr.sv"]; HP = ["rtl/crc32_stream.sv", "rtl/mac.sv", "rtl/hdr.sv"]
CFGS = [("any address, any port, no VLAN rule", g.DEFAULT_CFG | {"ip_en": 0, "plo": 0, "phi": 65535}),
        ("192.168.1.10, ports 5000-5999", g.DEFAULT_CFG),
        ("10.1.255.255, port 1234, VLAN 0xABC", {"ip_en": 1, "ip": g.ip4(10, 1, 255, 255), "vid_en": 1, "vid": 0xABC, "plo": 1234, "phi": 1234}),
        ("any address, any port, VLAN 0 only", g.DEFAULT_CFG | {"ip_en": 0, "plo": 0, "phi": 65535, "vid_en": 1, "vid": 0})]
W = {k: (6 if k.startswith("good") or k in ("no_csum", "odd_len") else 2) for k in g.KINDS}; W.update({"trailer": 4, "truncated": 6, "bits": 3, "carry_heavy": 4, "csum_zero": 4})
def defs(cfg, n): return (f"NC={n}", f"CFG_IP_EN={cfg['ip_en']}", f"CFG_IP=32'h{cfg['ip']:08x}", f"CFG_VID_EN={cfg['vid_en']}", f"CFG_VID=12'd{cfg['vid']}", f"CFG_PLO=16'd{cfg['plo']}", f"CFG_PHI=16'd{cfg['phi']}")
def run_filter(fr, cfg, gap, bub, seed, sim="icarus"):
    n = g.write_stimulus(os.path.join(R, "out", "hdr_stim.hex"), fr, seed, gap, bub); f = flow.sim_icarus if sim == "icarus" else flow.sim_verilator
    o = f(HF + ["tb/hdr_tb.sv"], "hdr_tb", defines=defs(cfg, n))[1]; return o, n
def check(o, fr, cfg):
    gf, gr = g.parse_results(o); ef, er = g.expected(fr, cfg); return gf == ef and gr == er
if __name__ == "__main__":
    print("== 1. lint gate (Verilator -Wall --lint-only, Yosys 'check')")
    for top, fs in (("hdr_filter", HF), ("hdr_path", HP), ("csum_e2e", ["rtl/csum.sv"]), ("csum_def", ["rtl/csum.sv"]), ("csum_lane", ["rtl/csum.sv"])):
        p = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", top] + fs, cwd=R, capture_output=True, text=True); w = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning")]
        y = subprocess.run(["yosys", "-p", f"read_verilog -sv {' '.join(fs)}; hierarchy -top {top}; proc; opt_clean; check"], cwd=R, capture_output=True, text=True).stdout
        print(f"  {top:11s} Verilator warnings: {len(w)}   Yosys check problems: {len([l for l in y.splitlines() if 'Found and reported' in l and ' 0 problems' not in l])}")
    print("\n== 2. the model against known answers")
    ex = g.csum(bytes.fromhex("0001f203f4f5f6f7")); h = bytes.fromhex("450000730000400040110000c0a80001c0a800c7")
    ok_h = g.csum(h[:10] + bytes([0xB8, 0x61]) + h[12:]) == 0xFFFF
    print(f"  RFC 1071 section 3 example: sum {ex:#06x} (expected 0xddf2): {ex == 0xDDF2};  textbook IPv4 header: checksum field {g.inet_csum(h):#06x} (expected 0xb861): {g.inet_csum(h) == 0xB861};  header with that field sums to 0xffff: {ok_h}")
    print("\n== 3. hdr_filter against the specification: every frame's bytes, bad flag, cause and captured fields (ntags, vid, addresses, ports, UDP length)")
    print(f"  {'configuration':38s} {'frames':>7s} {'forwarded':>10s} | {'back to back':>12s} {'gaps+idles':>11s} {'Verilator':>10s}")
    tot = Counter()
    for ci, (name, cfg) in enumerate(CFGS):
        ok = {"b2b": 0, "gap": 0}; nfr = 0; nfwd = 0; v = "-"
        for seed in range(8):
            fr = g.frames(100 * ci + seed, 150, cfg, W); nfr += len(fr); ef, er = g.expected(fr, cfg); nfwd += sum(1 for r in er if r[0] == 0); tot.update(r[0] for r in er)
            for style, (gap, bub) in (("b2b", ((0, 0), 0)), ("gap", ((0, 6), 12))):
                o, n = run_filter(fr, cfg, gap, bub, seed); ok[style] += check(o, fr, cfg)
            if seed == 0: o, n = run_filter(fr, cfg, (0, 0), 0, seed, "verilator"); v = "PASS" if check(o, fr, cfg) else "FAIL"
        print(f"  {name:38s} {nfr:7d} {nfwd:10d} | {ok['b2b']:9d} of 8 {ok['gap']:8d} of 8 {v:>10s}")
    print("  frames by cause over all 32 runs of the model: " + ", ".join(f"{g.NAMES[c]} {tot[c]}" for c in range(8)))
    cfg = g.DEFAULT_CFG; ok1 = 0
    for seed in range(8):
        fr = g.frames(900 + seed, 150, cfg, W); n = g.write_stimulus(os.path.join(R, "out", "hdr_stim.hex"), fr, seed, (0, 0), 0); o = flow.sim_icarus(["rtl/hdr_v1.sv", "tb/hdr_tb.sv"], "hdr_tb", defines=defs(cfg, n) + ("DUT=hdr_filter_v1",))[1]; ok1 += check(o, fr, cfg)
    print(f"  the FIRST version (rtl/hdr_v1.sv, kept for Example A) against the same specification, 8 seeds back to back: {ok1} of 8")
    print("\n== 4. one byte per clock: frames back to back with no idle cycle between bytes or frames")
    cfg = g.DEFAULT_CFG; fr = g.frames(7, 200, cfg, W); o, n = run_filter(fr, cfg, (0, 0), 0, 7); lat = int(re.search(r"LAT (\d+)", o).group(1)); nbytes = sum(len(b) for _, b, _ in fr)
    print(f"  {len(fr)} frames, {nbytes} bytes offered in {n} cycles (no idle cycle: {n == nbytes}); all frames exact: {check(o, fr, cfg)}; latency from the first byte in to the first byte out: {lat} cycles")
    print("\n== 5. hdr_path from the PHY wires (mac_rx -> hdr_filter -> frame_fifo, 2 KB, consumer at 100% and at 50%): the frames delivered must be exactly the model's forwarded frames, and the counters must equal the model's per-cause counts")
    print(f"  {'configuration':38s} {'consumer':>8s} | {'PHY frames':>10s} {'delivered':>9s} {'exact':>6s} {'counts equal':>13s}   frames per cause (model)")
    for ci, (name, cfg) in enumerate(CFGS):
        for rdy in (100, 50):
            fr = g.frames(500 + ci, 160, cfg, W); rng = random.Random(ci); it = [{"kind": rng.choices(["good", "badfcs", "er"], [88, 8, 4])[0], "body": b, "gap": rng.choice([12, 12, 12, 13, 20])} for _, b, _ in fr]
            st = m.phy_stream(it, ci); m.write_stream(os.path.join(R, "out", "mac_stream.hex"), st); sp = m.spec_rx(st); exp = [p for p, bd in sp if not g.spec(p, bd, cfg)["cause"]]; cn = [0] * 8
            for p, bd in sp: cn[g.spec(p, bd, cfg)["cause"]] += 1
            o = flow.sim_icarus(HP + ["tb/hdr_path_tb.sv"], "hdr_path_tb", defines=defs(cfg, len(st)) + (f"RDY={rdy}",))[1]; got = [p for p, _ in m.parse_frames(o)]; c = [int(x) for x in re.search(r"CNT (.*)", o).group(1).split()]
            print(f"  {name:38s} {rdy:7d}% | {len(sp):10d} {len(got):9d} {'YES' if got == exp else 'NO':>6s} {'YES' if c == cn else 'NO':>13s}   {cn}")
    print("\n== 6. the three checksum accumulators against the model (300 messages: the edge cases, then random ones heavy in 0xFF so that nearly every word carries; 1 to 1,600 bytes; 15% idle cycles carrying junk)")
    print(f"  {'accumulator':12s} {'messages':>8s} {'all equal':>10s} {'Verilator':>10s}")
    msgs = g.csum_messages(1); n = g.write_csum_stimulus(os.path.join(R, "out", "csum_stim.hex"), msgs, 1); exp = [g.csum(x) for x in msgs]
    for var in ("csum_e2e", "csum_def", "csum_lane"):
        got = [int(x, 16) for x in re.findall(r"SUM ([0-9a-f]+)", flow.sim_icarus(["rtl/csum.sv", "tb/csum_tb.sv"], "csum_tb", defines=(f"NC={n}", f"CSUM={var}"))[1])]
        gv = [int(x, 16) for x in re.findall(r"SUM ([0-9a-f]+)", flow.sim_verilator(["rtl/csum.sv", "tb/csum_tb.sv"], "csum_tb", defines=(f"NC={n}", f"CSUM={var}"))[1])]
        print(f"  {var:12s} {len(msgs):8d} {'YES' if got == exp else 'NO':>10s} {'PASS' if gv == exp else 'FAIL':>10s}")
