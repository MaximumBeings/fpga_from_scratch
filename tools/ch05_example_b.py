#!/usr/bin/env python3
"""Chapter 5, example B: where storage goes, and what moving registers does. (1) One memory (16 bits wide, depth 16 to 4096) with three read styles on iCE40 and ECP5: LUTs, flip-flops, block RAMs, distributed-RAM cells, Fmax. (2) The same 8-tap filter written in direct form and in transposed form (identical outputs; ch05_run.py shows it): resources and Fmax on ECP5 (DSP blocks) and iCE40. Usage: ch05_example_b.py"""
import os, re, subprocess, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, fx_gold
R = flow.ROOT; COHEX = "".join(f"{fx_gold.COEF[i] & 0xFFFF:04x}" for i in reversed(range(8)))
def build(files, top, family, tag, params):
    js = f"out/{tag}.json"; ps = [f"chparam -set {k} {v} {top}" for k, v in params.items()]
    syn = {"ecp5": f"synth_ecp5 -top {top} -json {js}", "ice40": f"synth_ice40 -top {top} -json {js}"}[family]
    subprocess.run(["yosys", "-p", "; ".join(["read_verilog -sv " + " ".join(files)] + ps + [syn, "stat"]), "-l", f"out/{tag}_synth.log"], cwd=R, capture_output=True, text=True)
    log = open(os.path.join(R, "out", f"{tag}_synth.log")).read(); sec = log.rsplit("Number of cells", 1)[-1] if "Number of cells" in log else log
    c = {m.group(1): int(m.group(2)) for m in re.finditer(r"^\s+(\$?\w+)\s+(\d+)\s*$", sec, re.M)}
    ff = c.get("TRELLIS_FF", 0) + sum(c.get(k, 0) for k in ("SB_DFF", "SB_DFFE", "SB_DFFESR", "SB_DFFSR", "SB_DFFNE"))
    p = flow.pnr(js, family, 300, 1)
    return {"lut": c.get("LUT4", 0) + c.get("SB_LUT4", 0), "ff": ff, "bram": c.get("SB_RAM40_4K", 0) + c.get("DP16KD", 0), "dpr": c.get("TRELLIS_DPR16X4", 0), "dsp": c.get("MULT18X18D", 0), "fmax": p["fmax"]}
def fm(v): return f"{v:7.1f} MHz" if v else "       n/a"   # n/a: no register-to-register path for the timing tool to measure (an asynchronous read goes from the input pins to the output pins)
def rjob(a): D, style, fam = a; return a, build(["rtl/ram_style.sv"], "ram_style", fam, f"ram_{D}_{style}_{fam}", {"W": 16, "D": D, "STYLE": style})
def fjob(a): form, fam = a; top = ["fir_direct", "fir_transposed"][form]; return a, build(["rtl/fxp.sv", "rtl/fir.sv"], top, fam, f"fir_{form}_{fam}", {"CO": f"128'h{COHEX}"})
if __name__ == "__main__":
    DEPTHS = (16, 64, 256, 1024, 4096)
    print("== 1. a 16-bit-wide memory, three read styles (0 asynchronous, 1 synchronous, 2 synchronous + output register); nextpnr seed 1")
    for fam, name in (("ice40", "iCE40 HX8K (4-kbit block RAMs: SB_RAM40_4K)"), ("ecp5", "ECP5 (18-kbit block RAMs: DP16KD; distributed RAM: TRELLIS_DPR16X4)")):
        print(f"\n  {name}")
        print(f"  {'depth':>6s} {'style':>5s} {'LUT':>6s} {'FF':>6s} {'block RAM':>9s} {'dist. RAM':>9s} {'Fmax':>10s}")
        jobs = [(D, s, fam) for D in DEPTHS for s in (0, 1, 2) if not (s == 0 and D > 64)]            # an asynchronous-read memory is built from flip-flops: a 256 x 16 array of flip-flops is 4,096 of the device's 7,680 cells before any multiplexer, and takes minutes to place
        with cf.ThreadPoolExecutor(4) as ex: res = dict(ex.map(rjob, jobs))
        for D in DEPTHS:
            for s in (0, 1, 2):
                if (D, s, fam) not in res: print(f"  {D:6d} {s:5d}   (not built: {D * 16} bits of storage as flip-flops, see the page)"); continue
                r = res[(D, s, fam)]; print(f"  {D:6d} {s:5d} {r['lut']:6d} {r['ff']:6d} {r['bram']:9d} {r['dpr']:9d} {fm(r['fmax'])}")
    print("\n== 2. the 8-tap FIR, Q1.15 coefficients, 40-bit sums: direct form against transposed form (same outputs, bit for bit)")
    print(f"  {'form':12s} {'target':6s} {'DSP':>4s} {'LUT':>5s} {'FF':>5s} {'Fmax':>10s}")
    with cf.ThreadPoolExecutor(4) as ex: res = dict(ex.map(fjob, [(f, fam) for fam in ("ecp5", "ice40") for f in (0, 1)]))
    for fam in ("ecp5", "ice40"):
        for f in (0, 1):
            r = res[(f, fam)]; print(f"  {['direct', 'transposed'][f]:12s} {fam:6s} {r['dsp']:4d} {r['lut']:5d} {r['ff']:5d} {fm(r['fmax'])}")
