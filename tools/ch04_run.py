#!/usr/bin/env python3
"""Chapter 4: the running designs. (1) lint gate; (2) the pipelined function against its golden model for six stage counts and three traffic densities (Icarus, and Verilator for two of them); (3) the model of the packet filters against the SPECIFICATION (a Python-only check over many random packet streams); (4) the two filters against their cycle-exact golden models over several seeds and packet mixes, two simulators. Usage: ch04_run.py"""
import os, sys, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, lat_gold as g
R = flow.ROOT
def first(o): return next((l for l in o.splitlines() if l.startswith(("PASS", "FAIL", "MISM", "COMPILE"))), "no output")
def packets_out(res):
    pk = []; cur = []; bad = []
    for r, ov, od, ol, ob in res:
        if ov:
            cur.append(od)
            if ol: pk.append(cur); bad.append(bool(ob)); cur = []
    return pk, bad
if __name__ == "__main__":
    print("== 1. lint gate: Verilator -Wall --lint-only and Yosys 'check'")
    for f, top in (("rtl/pipe.sv", "pipe"), ("rtl/pktfilt.sv", "ct_filter"), ("rtl/pktfilt.sv", "sf_filter")):
        p = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", top, f], cwd=R, capture_output=True, text=True); w = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning")]
        y = subprocess.run(["yosys", "-p", f"read_verilog -sv {f}; hierarchy -top {top}; proc; opt_clean; check"], cwd=R, capture_output=True, text=True).stdout; bad = [l for l in y.splitlines() if "Found and reported" in l and " 0 problems" not in l]
        print(f"  {top:10s} Verilator warnings: {len(w)}   Yosys check problems: {len(bad)}")
    print("\n== 2. pipelined function: 12 rounds, 16 bits, 2,000 cycles of random valid/data against the golden model; every output exactly S + 1 cycles after its input")
    print(f"  {'S':>3s} {'valid 100%':>11s} {'valid 70%':>10s} {'valid 20%':>10s} {'Verilator (70%)':>16s}")
    for s in (1, 2, 3, 4, 6, 12):
        row = []
        for pv in (1.0, 0.7, 0.2):
            g.pipe_vectors(os.path.join(R, "out", "pipe_vec.hex"), s, 2000, 5, p_valid=pv); row.append("PASS" if first(flow.sim_icarus(["rtl/pipe.sv", "tb/pipe_tb.sv"], "pipe_tb", defines=(f"S={s}",))[1]).startswith("PASS") else "FAIL")
        g.pipe_vectors(os.path.join(R, "out", "pipe_vec.hex"), s, 2000, 5, p_valid=0.7); v = "PASS" if first(flow.sim_verilator(["rtl/pipe.sv", "tb/pipe_tb.sv"], "pipe_tb", defines=(f"S={s}",))[1]).startswith("PASS") else "FAIL"
        print(f"  {s:3d} {row[0]:>11s} {row[1]:>10s} {row[2]:>10s} {v:>16s}")
    print("\n== 3. the filter models against the specification (Python only): 40 random streams of 100 packets; the cut-through model must output exactly the kept packets (bad ones flagged), the store-and-forward model exactly the good ones")
    ok = 0
    for seed in range(40):
        mix = [(5, 3, 2), (1, 1, 1), (8, 1, 1), (1, 8, 1)][seed % 4]; good = True
        for dense, model in ((True, g.CT), (False, g.SF)):
            pk, gp = g.gen(seed, mix, 100, 12, dense); o, b = packets_out(g.run(model, g.schedule(pk, gp)))
            if model is g.CT: exp = [(p, g.classify(p) == "bad") for p in pk if g.classify(p) != "drop"]
            else: exp = [(p, False) for p in pk if g.classify(p) == "good"]
            good &= [(p, x) for p, x in zip(o, b)] == exp and len(o) == len(exp)
        ok += good
    print(f"  {ok} of 40 streams: both models agree with the specification")
    print("\n== 4. the RTL against the golden models: 6 seeds x 3 mixes per filter (Icarus) and the first of each in Verilator")
    print(f"  {'filter':20s} {'Icarus':>10s} {'Verilator':>10s}")
    for sf, model, dense, name in ((0, g.CT, True, "cut-through"), (1, g.SF, False, "store-and-forward")):
        ok = 0; tot = 0; vok = "-"
        for seed in range(6):
            for mix in ((5, 3, 2), (1, 1, 8), (1, 8, 1)):
                pk, gp = g.gen(seed, mix, 120, 12, dense); ins = g.schedule(pk, gp); g.write_vectors(os.path.join(R, "out", "pkt_vec.hex"), ins, g.run(model, ins)); d = (f"SF={sf}", f"NC={len(ins)}")
                tot += 1; ok += first(flow.sim_icarus(["rtl/pktfilt.sv", "tb/pkt_tb.sv"], "pkt_tb", defines=d)[1]).startswith("PASS")
                if seed == 0: vok = "PASS" if first(flow.sim_verilator(["rtl/pktfilt.sv", "tb/pkt_tb.sv"], "pkt_tb", defines=d)[1]).startswith("PASS") else "FAIL"
        print(f"  {name:20s} {ok:4d} of {tot:<3d} {vok:>10s}")
