#!/usr/bin/env python3
"""Chapter 27, example A: what the supervisor costs and how fast it runs. sup_syn (the supervisor and the reset generator behind a small pin wrapper) for the watchdog limits FT = 100, 10,000 and 1,000,000 cycles (the counters grow with log2 FT), synthesised and placed for iCE40 (HX8K) and ECP5 (nextpnr seed 1, asked for 300 MHz); and the whole supervised design's total next to Chapter 26's (Yosys synth_ice40 -noflatten: the supervisor is a small part of it)."""
import os, re, subprocess, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import flow
CASES = [(100, 100, 48), (10000, 100, 48), (1000000, 100, 48), (100, 1000000, 48)]
def crit(log):
    i = log.rfind("Critical path report for clock"); j = log.find("Setup", i); sec = log[i:j + 300]; src = re.findall(r"Source (\S+)", sec); snk = re.findall(r"Sink (\S+)", sec); tl = re.search(r"([\d.]+) ns logic, ([\d.]+) ns routing", sec)
    nm = lambda x: re.sub(r"_(SB_|TRELLIS_|LUT4|CCU2C|PFUMX|L6MUX|RAM)\S*", "", re.sub(r"\.\d+\.\d+(_RAM)?", "", x)); return nm(src[0]), nm(snk[-1]), tl.groups() if tl else ("?", "?")
def job(a):
    (ft, st, warm), fam = a
    try: return a, flow.run(["rtl/sup.sv"], "sup_syn", fam, 300, tag=f"t27_{ft}_{st}_{fam}", params={"FT": ft, "ST": st, "WARM": warm})
    except subprocess.TimeoutExpired: return a, {"timeout": True}
if __name__ == "__main__":
    with cf.ThreadPoolExecutor(4) as ex: res = dict(ex.map(job, [(c, f) for c in CASES for f in ("ice40", "ecp5")]))
    print("== 1. the supervisor and the reset generator (Yosys + nextpnr, seed 1, asked for 300 MHz), behind the pin wrapper (10 input flip-flops and 9 output flip-flops are in the counts)")
    print(f"  {'FT':>8s} {'ST':>8s} | {'iCE40 LUT':>9s} {'FF':>4s} {'Fmax':>6s} | {'ECP5 LUT':>8s} {'FF':>4s} {'Fmax':>6s}")
    for c in CASES:
        i, e = res[(c, "ice40")], res[(c, "ecp5")]; fm = lambda x: f"{x['fmax']:6.1f}" if x.get("fmax") else "no fit"
        if i.get("timeout") or e.get("timeout"): print(f"  {c[0]:8d} {c[1]:8d} | did not finish"); continue
        print(f"  {c[0]:8d} {c[1]:8d} | {i['luts']:9d} {i['ffs']:4d} {fm(i):>6s} | {e['luts']:8d} {e['ffs']:4d} {fm(e):>6s}")
    print("\n== the end points of the critical path (nextpnr's last report for the clock)")
    for c in CASES[:1] + CASES[2:3]:
        for fam in ("ice40", "ecp5"):
            if res[(c, fam)].get("timeout") or not res[(c, fam)].get("fmax"): continue
            a, b, (lg, rt) = crit(res[(c, fam)]["pnr_log"]); print(f"  FT {c[0]:8d} {fam:6s} {a:20s} -> {b:20s} {lg} ns logic, {rt} ns routing")
    files = ["rtl/mold_itch.sv", "rtl/book2.sv", "rtl/sig.sv", "rtl/trig.sv", "rtl/risk.sv", "rtl/track.sv", "rtl/life.sv", "rtl/sess.sv", "rtl/w2w.sv", "rtl/sup.sv", "rtl/safe.sv"]
    rc, out = flow._run(["yosys", "-p", "read_verilog -sv " + " ".join(files) + "; hierarchy -top safe; synth_ice40 -top safe -noflatten; stat"], cwd=flow.ROOT)
    rows = {}; cur = None
    for line in out.splitlines():
        m = re.match(r"=== (\S+) ===", line)
        if m: cur = m.group(1); rows[cur] = {}; continue
        m = re.match(r"\s+(SB_LUT4|SB_DFF\w*)\s+(\d+)", line)
        if m and cur: rows[cur][m.group(1)] = rows[cur].get(m.group(1), 0) + int(m.group(2))
    print("\n== 2. the supervised design, unit by unit (Yosys synth_ice40 -noflatten; FT 400, ST 100, WARM 48)")
    print(f"  {'module':26s} {'LUT4':>6s} {'FF':>6s}")
    for m, d in sorted(rows.items(), key=lambda kv: -kv[1].get("SB_LUT4", 0)):
        if d and re.search(r"\\(sup|rst_gen)$|^safe$", m) or m == "safe" or re.search(r"w2w$", m): print(f"  {re.sub(r'^.paramod.[0-9a-f]+.', '', m) if m != 'safe' else 'TOTAL (safe)':26s} {d.get('SB_LUT4', 0):6d} {sum(v for k, v in d.items() if k.startswith('SB_DFF')):6d}")
