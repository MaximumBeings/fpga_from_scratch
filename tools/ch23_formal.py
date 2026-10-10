#!/usr/bin/env python3
"""Chapter 23: the bounded formal proof. Yosys's SAT engine (`sat -prove-asserts -set-assumes -set-init-zero -seq N`) unrolls the gate and the wrapper of formal/risk_props.sv for N cycles from reset, with FREE inputs (any event, configuration, control and kill in every cycle, under the stated contract), and looks for a cycle in which an assertion fails. (1) the correct gate: proved for N cycles (a bounded proof: nothing is said about cycle N + 1). (2) the mutants of the gate that matter for safety: each is run through the same search at depth DEPTH, and compared with the simulation battery of ch23_run.py (the cycle at which the counterexample appears, and how long the search took). Mutants whose counterexample needs more than DEPTH cycles are reported as not found: that is a limit of the bound, not a proof."""
import concurrent.futures as cf, os, shutil, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flow
DEPTH = int(os.environ.get("DEPTH", "7"))
def formal(depth, rtl="rtl/risk.sv", root=flow.ROOT):
    script = f"read_verilog -formal -sv {rtl} formal/risk_props.sv; hierarchy -top risk_props; proc; flatten; memory_map; opt_clean; sat -prove-asserts -set-assumes -set-init-zero -seq {depth}"
    t = time.time(); o = subprocess.run(["yosys", "-p", script], cwd=root, capture_output=True, text=True, timeout=3000); out = o.stdout + o.stderr
    return ("proved" if "no model found: SUCCESS" in out else "FAILS" if "model found: FAIL" in out else "?"), time.time() - t
# (label, old, new): the mutants of the gate whose effect is a safety violation or a wrong answer
MUT = [
 ("the long limit is checked with >= (a buy to the limit is refused: a wrong answer, not unsafe)", "buy ? (pl > mlong) : (ps < mshort)", "buy ? (pl >= mlong) : (ps < mshort)"),
 ("the long check ignores the open buys", "+ $signed({{(PB+2-QW){1'b0}}, ob[a][s]}) + $signed({{(PB+2-QW){1'b0}}, s1_qty});      // pos + ob + qty (a buy)", "+ $signed({{(PB+2-QW){1'b0}}, 0}) + $signed({{(PB+2-QW){1'b0}}, s1_qty});      // pos + ob + qty (a buy)"),
 ("the position is not checked", "else if (buy ? (pl > mlong) : (ps < mshort)) res = POS;", "else if (1'b0) res = POS;"),
 ("the notional ignores the open orders", "notl[a] + prod > c_not[a]) res = NOT;", "prod > c_not[a]) res = NOT;"),
 ("the notional is not checked", "else if (notl[a] + prod > c_not[a]) res = NOT;", "else if (1'b0) res = NOT;"),
 ("the price band is not checked", "else if (s1_px < b_lo[s] || s1_px > b_hi[s]) res = BAND;", "else if (1'b0) res = BAND;"),
 ("the order notional limit is not checked", "else if (s1_prod > c_onot[a]) res = ONOT;", "else if (1'b0) res = ONOT;"),
 ("the quantity limit is not checked", "else if (s1_qty == '0 || s1_qty > c_qty[a]) res = QTY;", "else if (1'b0) res = QTY;"),
 ("the kill input is ignored", "if (s1_kill) res = KILL;", "if (1'b0) res = KILL;"),
 ("a fault does not stop orders", "else if (!armed || fault) res = DISARMED;", "else if (!armed) res = DISARMED;"),
 ("a disarmed gate lets orders through", "else if (!armed || fault) res = DISARMED;", "else if (fault) res = DISARMED;"),
 ("an order does not take a token", "(s1_v && isord && took && a == AW'(g) && !bad) ? tok[g] - 1'b1 : tok[g]", "(s1_v && isord && 1'b0 && a == AW'(g) && !bad) ? tok[g] - 1'b1 : tok[g]"),
 ("an order does not add to the open buys", "if (buy) ob[a][s] <= ob[a][s] + s1_qty; else os[a][s] <= os[a][s] + s1_qty;", "if (buy) ob[a][s] <= ob[a][s]; else os[a][s] <= os[a][s] + s1_qty;"),
 ("a fill does not move the position", "if (isfill) pos[a][s] <=", "if (1'b0) pos[a][s] <="),
 ("the bucket can exceed its size", "(tick && tok_after[i] < c_cap[i])", "(tick && tok_after[i] <= c_cap[i])"),
]
def one(m):
    label, old, new = m; d = tempfile.mkdtemp(prefix="frm_")
    for sub in ("rtl", "formal"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub))
    p = os.path.join(d, "rtl", "risk.sv"); s = open(p).read()
    if s.count(old) != 1: shutil.rmtree(d, ignore_errors=True); return label, "BAD ANCHOR", 0.0
    open(p, "w").write(s.replace(old, new)); r, t = formal(DEPTH, root=d); shutil.rmtree(d, ignore_errors=True); return label, r, t
if __name__ == "__main__":
    print(f"== 1. the gate, proved for {DEPTH} cycles from reset (free inputs, under the contract; S1 safety, S2 answers, S3 state, S4 bucket)")
    r, t = formal(DEPTH); print(f"  gate: {r} in {t:.0f} s")
    print(f"\n== 2. mutants of the gate against the same search at depth {DEPTH} (counterexample found = the formal run catches it)")
    with cf.ThreadPoolExecutor(3) as ex: res = list(ex.map(one, MUT))
    caught = 0
    for label, r, t in res: print(f"  {label}: {'counterexample found' if r == 'FAILS' else ('NOT found within ' + str(DEPTH) + ' cycles' if r == 'proved' else r)} ({t:.0f} s)"); caught += r == "FAILS"
    print(f"  counterexamples found: {caught} of {len(MUT)}")
