#!/usr/bin/env python3
"""Chapter 25: test the tests, for the joined design. (1) mutants of rtl/life.sv, battery `ch25_sys.py --battery` (the whole design against the system model: three table sizes, six traffic mixes, Icarus). (2) mutants of model/sys_gold.py, battery `--battery-model` (its hand-checked scenarios, which include the reconciliation check)."""
import concurrent.futures as cf, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flow
RTL = "rtl/life.sv"; MOD = "model/sys_gold.py"
MUT = [
 (RTL, 'the give-back is a fill', "else if (give_back) begin ev_type = 2'd2;", "else if (give_back) begin ev_type = 2'd1;"),
 (RTL, 'the give-back has the wrong price', 'ev_side = h_side; ev_px = h_px; ev_qty = h_qty; end', "ev_side = h_side; ev_px = h_px + 1'b1; ev_qty = h_qty; end"),
 (RTL, 'the give-back has the wrong quantity', 'ev_side = h_side; ev_px = h_px; ev_qty = h_qty; end', "ev_side = h_side; ev_px = h_px; ev_qty = h_qty - 1'b1; end"),
 (RTL, 'the give-back has the wrong side', 'ev_side = h_side; ev_px = h_px;', 'ev_side = !h_side; ev_px = h_px;'),
 (RTL, 'the give-back has the wrong account', 'ev_acct = h_acct; ev_sym = h_sym;', "ev_acct = h_acct ^ 4'd1; ev_sym = h_sym;"),
 (RTL, 'the give-back has the wrong symbol', 'ev_acct = h_acct; ev_sym = h_sym;', "ev_acct = h_acct; ev_sym = h_sym ^ 4'd1;"),
 (RTL, 'the tracker release has the wrong account', 'ev_acct = t_racct;', 'ev_acct = h_acct;'),
 (RTL, 'the tracker release has the wrong price', 'ev_px = t_rpx;', 'ev_px = h_px;'),
 (RTL, 'the tracker release has the wrong type', 'ev_type = t_rtype;', "ev_type = 2'd1;"),
 (RTL, 'the tracker release has the wrong side', 'ev_side = t_rside;', 'ev_side = h_side;'),
 (RTL, 'an order is offered while a release is waiting', 'wire take_order = (st == IDLE) && ord_valid && !t_rv;', 'wire take_order = (st == IDLE) && ord_valid;'),
 (RTL, 'ready ignores the waiting release', 'assign ord_ready = (st == IDLE) && !t_rv;', 'assign ord_ready = (st == IDLE);'),
 (RTL, "the tracker's fault does not kill the gate", '.kill(ext_kill || t_ofault)', '.kill(ext_kill)'),
 (RTL, 'the external kill is ignored', '.kill(ext_kill || t_ofault)', '.kill(t_ofault)'),
 (RTL, 'a gate refusal is passed as OK', "if (rk_res != 4'd0) begin d_valid", "if (1'b0) begin d_valid"),
 (RTL, 'the order skips the tracker', 'else st <= TNEW;', "else begin d_valid <= 1'b1; d_res <= 5'd0; d_tok <= h_tok; st <= IDLE; end"),
 (RTL, 'the tracker NEW is never held', 'TNEW: if (t_ready) st <= TANS;', 'TNEW: st <= TANS;'),
 (RTL, 'a tracker refusal is not given back', "else begin h_res <= {2'b10, t_res}; st <= RB; end", "else begin d_valid <= 1'b1; d_res <= {2'b10, t_res}; d_tok <= h_tok; st <= IDLE; end"),
 (RTL, "the tracker's code is not offset", "h_res <= {2'b10, t_res}", "h_res <= {2'b00, t_res}"),
 (RTL, 'the give-back does not wait for the port', 'RB: if (!t_rv) begin', 'RB: begin'),
 (RTL, 'the answer token is wrong', "d_valid <= 1'b1; d_res <= h_res; d_tok <= h_tok;", "d_valid <= 1'b1; d_res <= h_res; d_tok <= ord_tok;"),
 (RTL, 'a cancel request is accepted while the tracker takes the order', 'assign cr_ready = (st != TNEW) && t_ready;', 'assign cr_ready = t_ready;'),
 (RTL, 'a cancel request ignores the report', 'assign cr_ready = (st != TNEW) && t_ready;', 'assign cr_ready = (st != TNEW);'),
 (RTL, 'the cancel answer shows the NEW answer', 'assign c_valid = t_ov && !t_src && (st != TANS);', 'assign c_valid = t_ov && !t_src;'),
 (RTL, 'the cancel answer shows report answers', 'assign c_valid = t_ov && !t_src && (st != TANS);', 'assign c_valid = t_ov && (st != TANS);'),
 (RTL, 'the tracker lookup token is the cancel token for NEW', '.l_tok(st == TNEW ? h_tok : cr_tok)', '.l_tok(cr_tok)'),
 (RTL, 'the held price is not captured', 'h_side <= ord_side; h_px <= ord_px;', "h_side <= ord_side; h_px <= '0;"),
 (RTL, 'the held quantity is not captured', 'h_px <= ord_px; h_qty <= ord_qty; end', "h_px <= ord_px; h_qty <= '0; end"),
 (RTL, 'the held account is not captured', 'h_acct <= ord_acct; h_sym <= ord_sym;', "h_acct <= '0; h_sym <= ord_sym;"),
 (RTL, 'the held side is not captured', 'h_side <= ord_side; h_px', "h_side <= 1'b0; h_px"),
 (RTL, 'the held symbol is not captured', 'h_acct <= ord_acct; h_sym <= ord_sym;', "h_acct <= ord_acct; h_sym <= '0;"),
 (RTL, 'reset leaves the state', 'if (rst) begin st <= IDLE; d_valid', 'if (rst) begin d_valid'),
 (RTL, 'reset leaves the answer valid', "d_valid <= 1'b0; d_res <= '0; d_tok <= '0; h_tok", "d_res <= '0; d_tok <= '0; h_tok"),
 (MOD, 'model: a tracker release does not win', 'if trv: ev = trel\n        elif st == RB', 'if st == RB: ev = (CANCEL, self.h["acct"], self.h["sym"], self.h["side"], self.h["px"], self.h["qty"])\n        elif trv: ev = trel\n        elif st == RB'),
 (MOD, 'model: the give-back is not made', 'elif st == RB: ev = (CANCEL,', 'elif st == RB and False: ev = (CANCEL,'),
 (MOD, 'model: the fault does not kill', 'kill = cy.get("kill", 0) or T.fault', 'kill = cy.get("kill", 0)'),
 (MOD, 'model: the books are not compared', 'if st == IDLE and self.rpend is None and not trv: self.reconcile()', 'pass'),
 (MOD, 'model: the reconciliation ignores notional', 'if g.notional[a] != sum(x["px"] * x["rem"] for x in T.e if x and x["acct"] == a): self.bad += 1; return', 'pass'),
 (MOD, 'model: the reconciliation ignores sells', 'if g.ob[a][s] != b or g.os[a][s] != o:', 'if g.ob[a][s] != b:'),
]
def one(j):
    f, label, old, new = j
    d = tempfile.mkdtemp(prefix="mut25s_")
    for sub in ("rtl", "tb", "out", "model", "tools"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub), ignore=shutil.ignore_patterns("*.json", "*_synth.log", "*.hex", "__pycache__", "ex*_*", "t1[0-9]_*"))
    p = os.path.join(d, f); s = open(p).read()
    if old not in s: shutil.rmtree(d, ignore_errors=True); return label, "BAD ANCHOR (0 occurrences)"
    i = s.index(old); open(p, "w").write(s[:i] + new + s[i + len(old):])
    try: q = subprocess.run([sys.executable, "tools/ch25_sys.py", "--battery" if f == RTL else "--battery-model"], cwd=d, capture_output=True, text=True, timeout=900); out = q.stdout.strip().splitlines()[-1] if q.stdout.strip() else "RESULT crash: " + (q.stderr.strip().splitlines() or ["?"])[-1][:70]
    except subprocess.TimeoutExpired: out = "RESULT hang (timeout)"
    shutil.rmtree(d, ignore_errors=True); r = out.replace("RESULT ", "")
    return label, ("NOT CAUGHT" if r == "None" else "caught by: " + r[:110])
if __name__ == "__main__":
    print("NOTE: this script deliberately breaks copies of the RTL and of the model. 'caught' lines are EXPECTED: they show the battery notices the mistake.")
    q1 = subprocess.run([sys.executable, "tools/ch25_sys.py", "--battery"], cwd=flow.ROOT, capture_output=True, text=True); q2 = subprocess.run([sys.executable, "tools/ch25_sys.py", "--battery-model"], cwd=flow.ROOT, capture_output=True, text=True)
    base = q1.stdout.strip().endswith("None") and q2.stdout.strip().endswith("None"); print("unmutated design and model pass their batteries:", base)
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(one, MUT))
    cnt = {RTL: [0, 0], MOD: [0, 0]}
    for (f, *_), (label, st) in zip(MUT, res): print(f"  {label}: {st}"); cnt[f][1] += 1; cnt[f][0] += st.startswith("caught")
    for f, (c, n) in cnt.items(): print(f"  {f}: caught {c} of {n}")
    print(f"mutants caught: {sum(c for c, n in cnt.values())} of {len(MUT)}")
