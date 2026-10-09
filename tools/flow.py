#!/usr/bin/env python3
"""The book's FPGA flow, wrapped in four functions (all open source: Yosys, nextpnr, IceStorm, Icarus, Verilator).
  synth(files, top, family)   Yosys technology mapping to an FPGA family ('ice40' or 'ecp5'); writes out/<tag>.json; returns the cell counts Yosys reports
  pnr(json, family, freq)     nextpnr place and route against a target clock in MHz; returns the maximum frequency it found, the logic cells used and the log
  run(files, top, family, freq, params={'W': 32})   both of the above, with the counts in the vocabulary of the family (LUTs, flip-flops, carry cells)
nextpnr is run with a fixed seed so every number in the book is reproducible. 'Fmax' here is nextpnr's estimate after placement and routing on the named device with its timing database."""
import os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from hw import ROOT, _run, sim_icarus, sim_verilator, mutate
DEV = {"ice40": ["nextpnr-ice40", "--hx8k", "--package", "ct256"], "ecp5": ["nextpnr-ecp5", "--25k", "--package", "CABGA381"]}
SYN = {"ice40": "synth_ice40 -top {top} -json {json}", "ecp5": "synth_ecp5 -top {top} -json {json}"}
LUTS = {"ice40": "SB_LUT4", "ecp5": "LUT4"}; FFS = {"ice40": ("SB_DFF", "SB_DFFE", "SB_DFFESR", "SB_DFFSR", "SB_DFFNE"), "ecp5": ("TRELLIS_FF",)}; CARRY = {"ice40": "SB_CARRY", "ecp5": "CCU2C"}
def synth(files, top, family="ice40", tag=None, params=None):
    tag = tag or f"{top}_{family}"; js = os.path.join("out", tag + ".json"); script = "; ".join(["read_verilog -sv " + " ".join(files)] + [f"chparam -set {k} {v} {top}" for k, v in (params or {}).items()] + [SYN[family].format(top=top, json=js), "stat"])
    rc, out = _run(["yosys", "-q", "-p", script, "-l", os.path.join("out", tag + "_synth.log")], cwd=ROOT)
    if rc != 0: return {"ok": False, "log": out}
    log = open(os.path.join(ROOT, "out", tag + "_synth.log")).read(); sec = log.rsplit("Number of cells", 1)[-1] if "Number of cells" in log else log.rsplit("cells", 1)[-1]
    cells = {m.group(1): int(m.group(2)) for m in re.finditer(r"^\s+(\$?\w+)\s+(\d+)\s*$", sec.split("design hierarchy")[0], re.M)}
    return {"ok": True, "json": js, "cells": cells, "luts": cells.get(LUTS[family], 0), "ffs": sum(cells.get(c, 0) for c in FFS[family]), "carry": cells.get(CARRY[family], 0), "log": log}
def pnr(js, family="ice40", freq=100, seed=1):
    cmd = DEV[family] + ["--json", js, "--freq", str(freq), "--seed", str(seed)] + (["--pcf-allow-unconstrained"] if family == "ice40" else [])
    rc, out = _run(cmd, cwd=ROOT); fm = re.findall(r"Max frequency for clock '[^']*': ([\d.]+) MHz", out)
    used = re.search(r"ICESTORM_LC:\s+(\d+)/\s*(\d+)", out) or re.search(r"TRELLIS_COMB:\s+(\d+)/\s*(\d+)", out)
    return {"ok": rc == 0 and bool(fm), "fmax": float(fm[-1]) if fm else None, "lcs": int(used.group(1)) if used else None, "of": int(used.group(2)) if used else None, "log": out}
def run(files, top, family="ice40", freq=100, tag=None, params=None, seed=1):
    s = synth(files, top, family, tag, params)
    if not s["ok"]: return s
    p = pnr(s["json"], family, freq, seed); return {**s, **{k: p[k] for k in ("fmax", "lcs", "of")}, "pnr_ok": p["ok"], "pnr_log": p["log"]}
