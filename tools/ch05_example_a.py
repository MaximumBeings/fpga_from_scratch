#!/usr/bin/env python3
"""Chapter 5, example A: what arithmetic costs. (1) A registered multiplier of W x W bits on the ECP5 target with the DSP blocks (Yosys default) and without (synth_ecp5 -nodsp: LUTs and carry cells), and on iCE40 (which has no DSP in this device): LUTs, carry cells, DSP blocks, flip-flops, Fmax. (2) The multiply-accumulate of Chapter 5 the same two ways. (3) What rounding and saturation add to a 40-to-16-bit narrowing, in LUTs. Usage: ch05_example_a.py"""
import os, re, subprocess, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import flow
R = flow.ROOT
def build(files, top, family, tag, params=None, nodsp=False):
    js = f"out/{tag}.json"; ps = [f"chparam -set {k} {v} {top}" for k, v in (params or {}).items()]
    syn = {"ecp5": "synth_ecp5 " + ("-nodsp " if nodsp else "") + f"-top {top} -json {js}", "ice40": f"synth_ice40 -top {top} -json {js}"}[family]
    p = subprocess.run(["yosys", "-p", "; ".join(["read_verilog -sv " + " ".join(files)] + ps + [syn, "stat"]), "-l", f"out/{tag}_synth.log"], cwd=R, capture_output=True, text=True)
    log = open(os.path.join(R, "out", f"{tag}_synth.log")).read(); sec = log.rsplit("Number of cells", 1)[-1] if "Number of cells" in log else log
    c = {m.group(1): int(m.group(2)) for m in re.finditer(r"^\s+(\$?\w+)\s+(\d+)\s*$", sec, re.M)}
    ff = c.get("TRELLIS_FF", 0) + sum(c.get(k, 0) for k in ("SB_DFF", "SB_DFFE", "SB_DFFESR", "SB_DFFSR"))
    return {"js": js, "lut": c.get("LUT4", 0) + c.get("SB_LUT4", 0), "carry": c.get("CCU2C", 0) + c.get("SB_CARRY", 0), "dsp": c.get("MULT18X18D", 0), "ff": ff}
def fmax(js, family, freq): return flow.pnr(js, family, freq, 1)["fmax"]
def job(a):
    kind, W, how = a; fam = "ice40" if how == "ice40" else "ecp5"; tag = f"mr_{W}_{how}"
    r = build(["rtl/mulreg.sv"], "mulreg", fam, tag, {"W": W}, nodsp=(how == "lut")); r["fmax"] = fmax(r["js"], fam, 300); return a, r
if __name__ == "__main__":
    print("== 1. a registered W x W signed multiplier (operands and product registered); nextpnr seed 1, asked for 300 MHz")
    print(f"  {'W':>3s} | {'ECP5 + DSP: DSP':>15s} {'LUT':>5s} {'Fmax':>9s} | {'ECP5 LUTs only: LUT':>19s} {'carry':>6s} {'Fmax':>9s} | {'iCE40: LUT':>11s} {'carry':>6s} {'Fmax':>9s}")
    jobs = [("m", W, h) for W in (8, 12, 16, 18, 24, 32) for h in ("dsp", "lut", "ice40")]
    with cf.ThreadPoolExecutor(4) as ex: res = dict(ex.map(job, jobs))
    for W in (8, 12, 16, 18, 24, 32):
        d, l, i = res[("m", W, "dsp")], res[("m", W, "lut")], res[("m", W, "ice40")]
        print(f"  {W:3d} | {d['dsp']:15d} {d['lut']:5d} {d['fmax']:6.1f} MHz | {l['lut']:19d} {l['carry']:6d} {l['fmax']:6.1f} MHz | {i['lut']:11d} {i['carry']:6d} {i['fmax']:6.1f} MHz")
    print("\n== 2. the Chapter 5 multiply-accumulate (16 x 16, 40-bit accumulator, round and saturate on the output)")
    print(f"  {'target':28s} {'DSP':>4s} {'LUT':>5s} {'carry':>6s} {'FF':>4s} {'Fmax':>9s}")
    for name, fam, nodsp, tag in (("ECP5 with DSP blocks", "ecp5", False, "mac_dsp"), ("ECP5 LUTs only", "ecp5", True, "mac_lut"), ("iCE40 (no DSP)", "ice40", False, "mac_ice")):
        r = build(["rtl/fxp.sv"], "fx_mac", fam, tag, nodsp=nodsp); f = fmax(r["js"], fam, 300); print(f"  {name:28s} {r['dsp']:4d} {r['lut']:5d} {r['carry']:6d} {r['ff']:4d} {f:6.1f} MHz")
    print("\n== 3. what rounding and saturation add: a 40-bit value narrowed to 16 bits (shift 15), iCE40 LUT4 count, combinational")
    print(f"  {'RND':>3s} {'SAT':>3s} {'LUTs':>5s}   meaning")
    for rnd, sat, txt in ((0, 0, "truncate and wrap: just wires"), (1, 0, "round half up, wrap"), (0, 1, "truncate, saturate"), (1, 1, "round half up, saturate")):
        r = build(["rtl/fxp.sv"], "fx_round_sat", "ice40", f"rs_{rnd}{sat}", {"RND": rnd, "SAT": sat}); print(f"  {rnd:3d} {sat:3d} {r['lut']:5d}   {txt}")
