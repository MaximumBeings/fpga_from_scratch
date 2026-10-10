#!/usr/bin/env python3
"""Chapter 25: the bounded formal proof of the tracker (formal/track_props.sv), with Yosys's SAT engine: free local events and reports in every cycle, tokens 0..3, a table of NT = 2 entries, quantities below 8. (1) the tracker, proved for DEPTH cycles from reset; (2) mutants of the tracker that matter for safety (over-release, a release for the wrong price, a fault that is not raised), against the same search."""
import concurrent.futures as cf, os, shutil, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flow
DEPTH = int(os.environ.get("DEPTH", "8"))
def formal(depth, rtl="rtl/track.sv", root=flow.ROOT):
    script = f"read_verilog -formal -sv {rtl} formal/track_props.sv; hierarchy -top track_props; proc; flatten; memory_map; opt_clean; sat -prove-asserts -set-assumes -set-init-zero -seq {depth}"
    t = time.time(); o = subprocess.run(["yosys", "-p", script], cwd=root, capture_output=True, text=True, timeout=3000); out = o.stdout + o.stderr
    return ("proved" if "no model found: SUCCESS" in out else "FAILS" if "model found: FAIL" in out else "?"), time.time() - t
MUT = [
 ("an overfilling report is believed (not an anomaly)", "else if (r_qty > hrem) res = OVERFILL;", "else if (1'b0) res = OVERFILL;"),
 ("a fill releases more than was left (clamp removed: quantity wraps)", "if (r_qty == '0) res = ZERO;\n                    else if (r_qty > hrem) res = OVERFILL;", "if (r_qty == '0) res = ZERO;\n                    else if (r_qty > hrem + 1'b1) res = OVERFILL;"),
 ("a cancel releases the original quantity, not the remainder", "CANCELED: begin rel = 1'b1; rtype = 2'd2; rq = hrem;", "CANCELED: begin rel = 1'b1; rtype = 2'd2; rq = hrem + 1'b1;"),
 ("a fill does not reduce the remaining quantity", "if (do_fill) rem[hi] <= hrem - r_qty;", "if (do_fill) rem[hi] <= hrem;"),
 ("the release carries the wrong price", "o_rpx <= px[hi];", "o_rpx <= px[fi];"),
 ("an unknown token is not a fault", "if (!hit) res = UNKNOWN;\n            else case", "if (!hit) res = OK;\n            else case"),
 ("a fully filled order stays in the table", "do_free = (r_qty == hrem); end", "do_free = 1'b0; end"),
 ("a duplicate token is accepted", "else if (hit) res = DUPTOK;", "else if (1'b0) res = DUPTOK;"),
]
def one(m):
    label, old, new = m; d = tempfile.mkdtemp(prefix="frm_")
    for sub in ("rtl", "formal"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub))
    p = os.path.join(d, "rtl", "track.sv"); s = open(p).read()
    if s.count(old) != 1: shutil.rmtree(d, ignore_errors=True); return label, "BAD ANCHOR", 0.0
    open(p, "w").write(s.replace(old, new)); r, t = formal(DEPTH, root=d); shutil.rmtree(d, ignore_errors=True); return label, r, t
if __name__ == "__main__":
    print(f"== 1. the tracker, proved for {DEPTH} cycles from reset (free inputs, under the contract; T1 no over-release, T2 exact release at exit, T3 the order's own fields, T4 answers, count and fault, T5 anomalies change nothing)")
    r, t = formal(DEPTH); print(f"  tracker: {r} in {t:.0f} s")
    print(f"\n== 2. mutants against the same search at depth {DEPTH}")
    with cf.ThreadPoolExecutor(3) as ex: res = list(ex.map(one, MUT))
    caught = 0
    for label, r, t in res: print(f"  {label}: {'counterexample found' if r == 'FAILS' else ('NOT found within ' + str(DEPTH) + ' cycles' if r == 'proved' else r)} ({t:.0f} s)"); caught += r == "FAILS"
    print(f"  counterexamples found: {caught} of {len(MUT)}")
