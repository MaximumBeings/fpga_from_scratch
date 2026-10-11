#!/usr/bin/env python3
"""Chapter 26, example A: what the whole wire-to-wire design costs and how fast it runs. (1) w2w_syn (the design behind its pin wrapper: 498 inputs shifted in, outputs registered and folded) synthesised with the hierarchy kept (Yosys `synth_ice40 -noflatten`, `stat`): the LUTs and flip-flops of each unit, as mapped for iCE40. (2) the flat design placed for iCE40 (HX8K) and ECP5 (nextpnr, seed 1, asked for 300 MHz): LUTs, flip-flops, logic cells, Fmax; for two feed-queue sizes (QD = 4 and 16) and two signal precisions (F = 12 and 24)."""
import os, re, subprocess, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import flow
FILES = ["rtl/mold_itch.sv", "rtl/book2.sv", "rtl/sig.sv", "rtl/trig.sv", "rtl/risk.sv", "rtl/track.sv", "rtl/life.sv", "rtl/sess.sv", "rtl/w2w.sv"]
CASES = [(8, 12), (4, 12), (16, 12), (8, 24)]
def crit(log):
    i = log.rfind("Critical path report for clock"); j = log.find("Setup", i); sec = log[i:j + 300]; src = re.findall(r"Source (\S+)", sec); snk = re.findall(r"Sink (\S+)", sec); tl = re.search(r"([\d.]+) ns logic, ([\d.]+) ns routing", sec)
    nm = lambda x: re.sub(r"_(SB_|TRELLIS_|LUT4|CCU2C|PFUMX|L6MUX|RAM)\S*", "", re.sub(r"\.\d+\.\d+(_RAM)?", "", x)); return nm(src[0]), nm(snk[-1]), tl.groups() if tl else ("?", "?")
def job(a):
    (qd, f), fam = a
    try: return a, flow.run(FILES, "w2w_syn", fam, 300, tag=f"t26_{qd}_{f}_{fam}", params={"QD": qd, "F": f})
    except subprocess.TimeoutExpired: return a, {"timeout": True}
def per_unit():
    rc, out = flow._run(["yosys", "-p", "read_verilog -sv " + " ".join(FILES) + "; hierarchy -top w2w_syn; synth_ice40 -top w2w_syn -noflatten; stat"], cwd=flow.ROOT)
    rows = {}; cur = None
    for line in out.splitlines():
        m = re.match(r"=== (\S+) ===", line)
        if m: cur = m.group(1); rows[cur] = {}; continue
        m = re.match(r"\s+(SB_LUT4|SB_DFF\w*|SB_RAM40_4K\w*|SB_CARRY)\s+(\d+)", line)
        if m and cur: rows[cur][m.group(1)] = rows[cur].get(m.group(1), 0) + int(m.group(2))
    return rows
if __name__ == "__main__":
    print("== 1. LUTs and flip-flops of each unit (Yosys synth_ice40 -noflatten; the pin wrapper's shift register is in w2w_syn)")
    rows = per_unit(); print(f"  {'module':32s} {'LUT4':>6s} {'FF':>6s} {'RAM4K':>6s}")
    for m, d in sorted(rows.items(), key=lambda kv: -kv[1].get("SB_LUT4", 0)):
        if not d: continue
        m = "TOTAL (all units + pin wrapper)" if m == "w2w_syn" else re.sub(r"^\$paramod\$[0-9a-f]+\\", "", m)
        print(f"  {m:32s} {d.get('SB_LUT4', 0):6d} {sum(v for k, v in d.items() if k.startswith('SB_DFF')):6d} {sum(v for k, v in d.items() if k.startswith('SB_RAM')):6d}")
    with cf.ThreadPoolExecutor(4) as ex: res = dict(ex.map(job, [(c, f) for c in CASES for f in ("ice40", "ecp5")]))
    print("\n== 2. the whole design placed (nextpnr seed 1, asked for 300 MHz), flat")
    print(f"  {'QD':>3s} {'F':>3s} | {'iCE40 LUT':>9s} {'FF':>6s} {'LCs':>6s} {'Fmax':>6s} | {'ECP5 LUT':>8s} {'FF':>6s} {'Fmax':>6s}")
    for c in CASES:
        i, e = res[(c, "ice40")], res[(c, "ecp5")]
        if i.get("timeout") or e.get("timeout"): print(f"  {c[0]:3d} {c[1]:3d} | synthesis did not finish in 15 minutes"); continue
        fm = lambda x: f"{x['fmax']:6.1f}" if x.get("fmax") else "no fit"
        print(f"  {c[0]:3d} {c[1]:3d} | {i['luts']:9d} {i['ffs']:6d} {str(i.get('lcs') or '-'):>6s} {fm(i):>6s} | {e['luts']:8d} {e['ffs']:6d} {fm(e):>6s}")
    print("\n== the end points of the critical path (nextpnr's last report for the clock)")
    for c in CASES[:1] + CASES[3:]:
        for fam in ("ice40", "ecp5"):
            if res[(c, fam)].get("timeout") or not res[(c, fam)].get("fmax"): continue
            a, b, (lg, rt) = crit(res[(c, fam)]["pnr_log"]); print(f"  QD {c[0]:2d} F {c[1]:2d} {fam:6s} {a:26s} -> {b:26s} {lg} ns logic, {rt} ns routing")
