#!/usr/bin/env python3
"""Chapter 27: the bounded formal proof of the supervisor (formal/sup_props.sv), with Yosys's SAT engine: free inputs in every cycle, small parameters (FT 4, ST 3, WARM 2). (1) the supervisor, proved for DEPTH cycles from reset; (2) mutants of the supervisor against the same search."""
import concurrent.futures as cf, os, shutil, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flow
DEPTH = int(os.environ.get("DEPTH", "16"))
def formal(depth, rtl="rtl/sup.sv", root=flow.ROOT):
    script = f"read_verilog -formal -sv {rtl} formal/sup_props.sv; hierarchy -top sup_props; proc; flatten; memory_map; opt_clean; sat -prove-asserts -set-assumes -set-init-zero -seq {depth}"
    t = time.time(); o = subprocess.run(["yosys", "-p", script], cwd=root, capture_output=True, text=True, timeout=3000); out = o.stdout + o.stderr
    return ("proved" if "no model found: SUCCESS" in out else "FAILS" if "model found: FAIL" in out else "?"), time.time() - t
MUT = [
 ("SAFE can be left by go", "default: if (cq_valid) sent <= 1'b1;", "default: begin if (cq_valid) sent <= 1'b1; if (go) state <= RUN; end"),
 ("RUN is entered without the session ACTIVE", "READY: if (go && sess == ACTIVE) state <= RUN;", "READY: if (go) state <= RUN;"),
 ("RUN is entered without a go", "READY: if (go && sess == ACTIVE) state <= RUN;", "READY: if (sess == ACTIVE) state <= RUN;"),
 ("INIT lasts one cycle too long", "if (cnt + 1'b1 >= CW'(WARM)) state <= READY;", "if (cnt + 1'b1 > CW'(WARM)) state <= READY;"),
 ("INIT lasts one cycle too short", "if (cnt + 1'b1 >= CW'(WARM)) state <= READY;", "if (cnt + 1'b1 >= CW'(WARM - 1)) state <= READY;"),
 ("the feed watchdog is one cycle late", "wire f_t = (fc >= CW'(FT))", "wire f_t = (fc > CW'(FT))"),
 ("the feed watchdog counts in the slot's cycles", "fc <= feed ? '0 : fc + 1'b1;", "fc <= (feed || slot) ? '0 : fc + 1'b1;"),
 ("a feed byte does not restart the watchdog", "fc <= feed ? '0 : fc + 1'b1;", "fc <= fc + 1'b1;"),
 ("the stall watchdog is one cycle late", "s_t = (sc >= CW'(ST))", "s_t = (sc > CW'(ST))"),
 ("a free slot does not restart the stall count", "sc <= slot ? sc + 1'b1 : '0;", "sc <= slot ? sc + 1'b1 : sc;"),
 ("the tracker's fault is ignored", "x_f = fault,", "x_f = 1'b0,"),
 ("a dead session is ignored", "x_s = (sess != ACTIVE),", "x_s = 1'b0,"),
 ("the external trip is ignored", "x_t = trip;", "x_t = 1'b0;"),
 ("kill is low in READY", "assign kill = (state != RUN);", "assign kill = (state != RUN) && (state != READY);"),
 ("kill is low in SAFE", "assign kill = (state != RUN);", "assign kill = (state != RUN) && (state != SAFE);"),
 ("the logout is offered without waiting for quiet", "tx_ready && quiet;", "tx_ready;"),
 ("the logout is offered without the transmitter ready", "(sess == ACTIVE) && tx_ready && quiet;", "(sess == ACTIVE) && quiet;"),
 ("the logout is offered again and again", "default: if (cq_valid) sent <= 1'b1;", "default: sent <= 1'b0;"),
 ("the logout is offered in RUN", "assign cq_valid = (state == SAFE) &&", "assign cq_valid = (state == SAFE || state == RUN) &&"),
]
def one(m):
    label, old, new = m; d = tempfile.mkdtemp(prefix="frm27_")
    for sub in ("rtl", "formal"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub))
    p = os.path.join(d, "rtl", "sup.sv"); s = open(p).read()
    if s.count(old) != 1: shutil.rmtree(d, ignore_errors=True); return label, "BAD ANCHOR", 0.0
    open(p, "w").write(s.replace(old, new)); r, t = formal(DEPTH, root=d); shutil.rmtree(d, ignore_errors=True); return label, r, t
if __name__ == "__main__":
    print(f"== 1. the supervisor, proved for {DEPTH} cycles from reset (free inputs; S1 absorbing, S2 entry, S3 causes, S4 detection bound, S5 kill, S6 logout, S7 warm-up)")
    r, t = formal(DEPTH); print(f"  supervisor: {r} in {t:.0f} s")
    print(f"\n== 2. mutants against the same search at depth {DEPTH}")
    with cf.ThreadPoolExecutor(3) as ex: res = list(ex.map(one, MUT))
    caught = 0
    for label, r, t in res: print(f"  {label}: {'counterexample found' if r == 'FAILS' else ('NOT found within ' + str(DEPTH) + ' cycles' if r == 'proved' else r)} ({t:.0f} s)"); caught += r == "FAILS"
    print(f"  counterexamples found: {caught} of {len(MUT)}")
