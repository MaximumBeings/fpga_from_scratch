#!/usr/bin/env python3
"""Chapter 3: the running designs. (1) lint gate; (2) the asynchronous FIFO against its scoreboard, over clock ratios and traffic, with an ideal synchronizer and with the metastability model, for Gray / binary pointers and registered / unregistered encoders; (3) the pulse crossings against the event model; (4) the reset synchronizer; (5) the Gray-code property proved by SAT for every counter value. Usage: ch03_run.py"""
import os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, cdc_model
R = flow.ROOT; SYNC = {"ideal": "rtl/cdc_sync.sv", "meta": "tb/cdc_sync_meta.sv"}
def first(o, keys=("PASS", "FAIL", "PULSES", "COMPILE")): return next((l for l in o.splitlines() if l.startswith(keys)), o.strip().splitlines()[-1] if o.strip() else "no output")
def fifo(gray, reg, sync, wp, rp, pw, pr, simulator="icarus"):
    d = (f"GRAY={gray}", f"REG={reg}", f"WP={wp}", f"RP={rp}", f"PW={pw}", f"PR={pr}"); fs = [SYNC[sync], "rtl/cdc.sv", "tb/cdc_fifo_tb.sv"]
    return (flow.sim_icarus if simulator == "icarus" else flow.sim_verilator)(fs, "cdc_fifo_tb", defines=d)[1]
if __name__ == "__main__":
    print("== 1. lint gate: Verilator -Wall --lint-only and Yosys 'check' on rtl/cdc_sync.sv + rtl/cdc.sv (top cdc_afifo) and rtl/cdc.sv alone for the pulse circuits")
    for top in ("cdc_afifo", "cdc_toggle_pulse", "cdc_naive_pulse", "cdc_rst_sync"):
        p = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", top, "rtl/cdc_sync.sv", "rtl/cdc.sv"], cwd=R, capture_output=True, text=True); w = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning")]
        y = subprocess.run(["yosys", "-p", f"read_verilog -sv rtl/cdc_sync.sv rtl/cdc.sv; hierarchy -top {top}; proc; opt_clean; check"], cwd=R, capture_output=True, text=True).stdout; bad = [l for l in y.splitlines() if "Found and reported" in l and " 0 problems" not in l]
        print(f"  {top:18s} Verilator warnings: {len(w)}   Yosys check problems: {len(bad)}")
    print("\n== 2. asynchronous FIFO (8 bits x 8 words), 3,000 words, scoreboard + occupancy checks; 4 clock pairs x 4 traffic profiles = 16 runs per row (Icarus)")
    clocks = [(10000, 7300), (7300, 10000), (10000, 10000), (4100, 10000)]; traffic = [(70, 60), (100, 100), (30, 90), (100, 30)]
    print(f"  {'pointers':8s} {'encoder':12s} {'synchronizer':14s} {'passed':>7s}   first failure")
    summary = {}
    for gray, reg in ((1, 1), (0, 1), (1, 0)):
        for sync in ("ideal", "meta"):
            ok = 0; ff = ""
            for wp, rp in clocks:
                for pw, pr in traffic:
                    o = first(fifo(gray, reg, sync, wp, rp, pw, pr))
                    if o.startswith("PASS"): ok += 1
                    elif not ff: ff = o.replace("FAIL: ", "") + f"   (wclk {wp} ps, rclk {rp} ps, offer {pw}%, ask {pr}%)"
            summary[(gray, reg, sync)] = ok
            print(f"  {'Gray' if gray else 'binary':8s} {'registered' if reg else 'combinational':12s} {sync:14s} {ok:2d} of 16   {ff}")
    print("\n  the main configuration in both simulators (wclk 10000 ps, rclk 7300 ps, offer 70%, ask 60%):")
    for name, sim in (("Icarus", "icarus"), ("Verilator", "verilator")):
        for sync in ("ideal", "meta"): print(f"  {name:10s} Gray registered, {sync:5s}: {first(fifo(1, 1, sync, 10000, 7300, 70, 60, sim))}")
        print(f"  {name:10s} binary,          meta : {first(fifo(0, 1, 'meta', 10000, 7300, 70, 60, sim))}")
    print("\n== 3. pulse crossings: 200 one-cycle pulses; the testbench's count against the event model's prediction (a clock = 10,000 ps, b-clock phase 1,234 ps)")
    print(f"  {'b period ps':>11s} {'gap (a cycles)':>14s} | {'naive sim':>9s} {'naive model':>11s} | {'toggle sim':>10s} {'toggle model':>12s}")
    bad = 0
    for bp, gap in ((2000, 6), (7300, 6), (13000, 6), (25000, 6), (41300, 6), (7300, 1), (7300, 2), (13000, 2), (13000, 3), (13000, 4), (41300, 4)):
        res = []
        for t in (0, 1):
            o = flow.sim_icarus(["rtl/cdc_sync.sv", "rtl/cdc.sv", "tb/cdc_pulse_tb.sv"], "cdc_pulse_tb", defines=(f"TOGGLE={t}", "AP=10000", f"BP={bp}", "OFF=1234", f"GAP={gap}", "NP=200"))[1]
            sim = int(re.search(r"got (\d+)", o).group(1)); mod = (cdc_model.pulses_toggle if t else cdc_model.pulses_naive)(10000, bp, 1234, gap, 200); res += [sim, mod]; bad += sim != mod
        print(f"  {bp:11d} {gap:14d} | {res[0]:9d} {res[1]:11d} | {res[2]:10d} {res[3]:12d}" + ("   <-- sim and model DIFFER" if res[0] != res[1] or res[2] != res[3] else ""))
    print(f"  simulation against model: {'all agree' if not bad else str(bad) + ' DISAGREEMENTS'}")
    print("\n== 4. reset synchronizer: assert in the middle of a clock period, release at 40 different offsets after an edge")
    for name, fn in (("Icarus", flow.sim_icarus), ("Verilator", flow.sim_verilator)):
        o = fn(["rtl/cdc_sync.sv", "rtl/cdc.sv", "tb/rst_sync_tb.sv"], "rst_sync_tb")[1]; rel = [(int(a), int(b)) for a, b in re.findall(r"REL (\d+) (\d+)", o)]; chk = re.search(r"bad_assert (\d+) bad_hold (\d+)", o)
        agree = all(e == cdc_model.reset_release_edges(off) for off, e in rel)
        print(f"  {name:10s} trials {len(rel)}, edges to release {sorted(set(e for _, e in rel))}, model agrees on every trial: {agree}, reset did not fall at once: {chk.group(1)}, reset not held low: {chk.group(2)}")
    print("\n== 5. the property that makes Gray safe, proved by SAT for EVERY counter value (4-bit counter, all 16 steps including the wrap)")
    for mode, name in ((1, "Gray"), (0, "binary")):
        o = subprocess.run(["yosys", "-p", f"read_verilog -formal -sv rtl/gray_prop.sv; chparam -set MODE {mode} gray_prop; hierarchy -top gray_prop; proc; opt_clean; sat -prove-asserts -show b"], cwd=R, capture_output=True, text=True).stdout
        if "no model found: SUCCESS" in o: print(f"  {name:7s}: exactly one bit changes at every step -- PROVED for all 16 values")
        else:
            b = int(re.search(r"\\b\s+\d+\s+\d+\s+([01]+)", o).group(1), 2); print(f"  {name:7s}: NOT true -- counterexample: the step {b} -> {(b + 1) % 16} changes more than one bit")
