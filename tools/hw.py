#!/usr/bin/env python3
"""The book's little toolbox around three open-source programs: Icarus Verilog (iverilog, vvp), Verilator, and Yosys. Every chapter's tests go through these functions, so a test that passes
here has passed in two independent simulators, and a synthesis number comes from the same script every time.
  sim_icarus(files, top)      compile with iverilog (-g2012) and run with vvp; returns (exit status, output)
  sim_verilator(files, top)   compile with Verilator (--binary --timing) and run the binary; returns (exit status, output)
  synth_stats(files, top, script)   run a Yosys script and return the cell counts it reports
  mutate(mutants, files, top)  break copies of the sources one line at a time, run the testbench on each, and report which mutants the test caught
All run in the book's root directory, because the testbenches read their vectors from out/."""
import concurrent.futures, os, re, shutil, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _run(cmd, cwd=ROOT, timeout=900):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, errors="replace"); return p.returncode, p.stdout + p.stderr
def sim_icarus(files, top, root=ROOT, defines=()):
    d = tempfile.mkdtemp(prefix="ico_"); exe = os.path.join(d, "sim")
    rc, out = _run(["iverilog", "-g2012", "-Wall", "-s", top, "-o", exe] + ["-D" + x for x in defines] + list(files), cwd=root)
    if rc != 0: shutil.rmtree(d, ignore_errors=True); return 99, "COMPILE ERROR\n" + out
    rc, out = _run(["vvp", "-n", exe], cwd=root); shutil.rmtree(d, ignore_errors=True); return rc, out
def sim_verilator(files, top, root=ROOT, defines=(), args=(), runargs=()):
    d = tempfile.mkdtemp(prefix="vlt_")
    rc, out = _run(["verilator", "--binary", "--timing", "-Wno-fatal", "-Wno-lint", "-Wno-style", "--top-module", top, "-Mdir", d, "-o", "sim"] + list(args) + ["-D" + x for x in defines] + list(files), cwd=root)
    if rc != 0: shutil.rmtree(d, ignore_errors=True); return 99, "COMPILE ERROR\n" + out
    rc, out = _run([os.path.join(d, "sim")] + list(runargs), cwd=root); shutil.rmtree(d, ignore_errors=True); return rc, out
def synth_stats(files, top, script=None, root=ROOT):
    """Runs Yosys on the files and returns {'cells': {type: count}, 'total': n, 'log': text}. The default script is the generic flow: read, elaborate, optimize, map to simple gates."""
    script = script or f"synth -flatten -top {top}; stat"
    rc, out = _run(["yosys", "-p", "; ".join(["read_verilog -sv " + " ".join(files), "hierarchy -top " + top, script])], cwd=root)
    if rc != 0: return {"cells": {}, "total": -1, "log": out}
    last = out.rsplit("Number of cells", 1)
    sec = out[out.rfind("=== " + top + " ==="):] if ("=== " + top + " ===") in out else out
    cells = {}
    for m in re.finditer(r"^\s+(\$?\w+)\s+(\d+)\s*$", sec.split("design hierarchy")[0] if "design hierarchy" in sec else sec, re.M): cells[m.group(1)] = int(m.group(2))
    m = re.search(r"(\d+)\s+cells", sec) or re.search(r"Number of cells:\s+(\d+)", sec)
    return {"cells": cells, "total": int(m.group(1)) if m else sum(cells.values()), "log": out}
def mutate(mutants, files, top, tb_files, root=ROOT, workers=4, title="", simulator="icarus", extra_files=(), defines=()):
    """mutants: list of (file, label, old, new); each `old` must occur exactly once in `file`. Returns (caught, total, lines)."""
    lines = []
    def one(i):
        fn, label, old, new = mutants[i]; d = tempfile.mkdtemp(prefix="mut_")
        for sub in ("rtl", "tb", "out", "model"):
            if os.path.isdir(os.path.join(root, sub)): shutil.copytree(os.path.join(root, sub), os.path.join(d, sub))
        p = os.path.join(d, fn); s = open(p).read()
        if s.count(old) != 1: shutil.rmtree(d, ignore_errors=True); return label, "BAD ANCHOR (%d occurrences)" % s.count(old), None
        open(p, "w").write(s.replace(old, new)); fs = list(files) + list(tb_files) + list(extra_files)
        rc, out = (sim_icarus if simulator == "icarus" else sim_verilator)(fs, top, root=d, defines=defines); shutil.rmtree(d, ignore_errors=True)
        if rc == 99: return label, "DID NOT BUILD", out
        return label, ("caught" if rc != 0 or "PASS" not in out else "NOT CAUGHT"), out
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        res = list(pool.map(one, range(len(mutants))))
    caught = 0
    for label, status, out in res:
        lines.append(f"{label}: {status}"); caught += status == "caught"
    return caught, len(mutants), lines
