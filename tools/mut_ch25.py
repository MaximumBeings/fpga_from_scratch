#!/usr/bin/env python3
"""Chapter 25: test the tests. Two families. (1) mutants of rtl/track.sv, battery `ch25_run.py --battery`: the tracker against the cycle model (answers, releases, live count, fault, ready), five table sizes, six scenarios. (2) mutants of model/life_gold.py, battery `--battery-model`: the model's own hand-checked scenarios (the model is the oracle; a handful of cases worked by hand check IT, so this family measures how complete they are)."""
import concurrent.futures as cf, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flow
RTL = "rtl/track.sv"; MOD = "model/life_gold.py"
MUT = [
 (RTL, 'a report does not win over a local event', 'assign ready = !r_valid;', "assign ready = 1'b1;"),
 (RTL, 'the lookup uses the local token for reports', 'wire [31:0] etok = r_valid ? r_tok : l_tok;', 'wire [31:0] etok = l_tok;'),
 (RTL, 'the lookup uses only 31 token bits', 'if (used[i] && tok[i] == etok) begin', 'if (used[i] && tok[i][30:0] == etok[30:0]) begin'),
 (RTL, 'a zero-quantity order is recorded', "if (l_qty == '0) res = ZERO; else if (hit) res = DUPTOK;", "if (1'b0) res = ZERO; else if (hit) res = DUPTOK;"),
 (RTL, 'a duplicate token is recorded', 'else if (hit) res = DUPTOK; else if (!free)', "else if (1'b0) res = DUPTOK; else if (!free)"),
 (RTL, 'a full table overwrites entry 0', 'else if (!free) res = FULL; else do_new', "else if (1'b0) res = FULL; else do_new"),
 (RTL, 'a new order starts LIVE', 'st[fi] <= PNEW;', 'st[fi] <= LIVE;'),
 (RTL, 'a new order stores no price', 'px[fi] <= l_px;', "px[fi] <= '0;"),
 (RTL, 'a new order stores the wrong side', 'side[fi] <= l_side;', 'side[fi] <= !l_side;'),
 (RTL, 'a new order stores no account', 'acct[fi] <= l_acct;', "acct[fi] <= '0;"),
 (RTL, 'a new order stores no symbol', 'sym[fi] <= l_sym;', "sym[fi] <= '0;"),
 (RTL, 'a new order stores one quantity too few', 'rem[fi] <= l_qty;', "rem[fi] <= l_qty - 1'b1;"),
 (RTL, 'a cancel request of an unknown token is OK', 'if (!hit) res = UNKNOWN; else if (hst != LIVE)', 'if (!hit) res = OK; else if (hst != LIVE)'),
 (RTL, 'a cancel request is allowed in PENDING_NEW', 'else if (hst != LIVE) res = BADSTATE; else do_pcan', 'else if (hst == PCAN) res = BADSTATE; else do_pcan'),
 (RTL, 'a cancel request does not change the state', 'if (do_pcan) st[hi] <= PCAN;', 'if (do_pcan) st[hi] <= st[hi];'),
 (RTL, 'an ack is allowed in any state', "ACK: if (hst != PNEW) res = BADSTATE; else do_live = 1'b1;", "ACK: do_live = 1'b1;"),
 (RTL, 'an ack does not make the order live', 'if (do_live) st[hi] <= LIVE;', 'if (do_live && r_kind != ACK) st[hi] <= LIVE;'),
 (RTL, 'a fill is not an implicit ack', 'do_live = (hst == PNEW);', "do_live = 1'b0;"),
 (RTL, 'a fill makes a cancelling order live', 'do_live = (hst == PNEW);', 'do_live = (hst != LIVE);'),
 (RTL, 'a fill of zero is believed', "if (r_qty == '0) res = ZERO;\n                    else if", "if (1'b0) res = ZERO;\n                    else if"),
 (RTL, 'an overfill is allowed by one', 'else if (r_qty > hrem) res = OVERFILL;', "else if (r_qty > hrem + 1'b1) res = OVERFILL;"),
 (RTL, 'a fill of exactly the remainder is an overfill', 'else if (r_qty > hrem) res = OVERFILL;', 'else if (r_qty >= hrem) res = OVERFILL;'),
 (RTL, 'a full fill does not free the entry', 'do_free = (r_qty == hrem); end', "do_free = 1'b0; end"),
 (RTL, 'every fill frees the entry', 'do_free = (r_qty == hrem); end', "do_free = 1'b1; end"),
 (RTL, 'a fill releases a cancel', "rtype = 2'd1; rq = r_qty;", "rtype = 2'd2; rq = r_qty;"),
 (RTL, 'a fill releases the remainder', "rtype = 2'd1; rq = r_qty;", "rtype = 2'd1; rq = hrem;"),
 (RTL, 'a cancel report releases a fill', "CANCELED: begin rel = 1'b1; rtype = 2'd2;", "CANCELED: begin rel = 1'b1; rtype = 2'd1;"),
 (RTL, 'a cancel report releases nothing', "CANCELED: begin rel = 1'b1;", "CANCELED: begin rel = 1'b0;"),
 (RTL, 'a cancel report releases the report quantity', "rtype = 2'd2; rq = hrem; do_free = 1'b1; end\n                default", "rtype = 2'd2; rq = r_qty; do_free = 1'b1; end\n                default"),
 (RTL, 'a cancel report does not free', "rtype = 2'd2; rq = hrem; do_free = 1'b1; end\n                default", "rtype = 2'd2; rq = hrem; do_free = 1'b0; end\n                default"),
 (RTL, 'a reject is allowed in any state', 'default: if (hst != PNEW) res = BADSTATE; else begin', "default: if (1'b0) res = BADSTATE; else begin"),
 (RTL, 'a reject releases a fill', "else begin rel = 1'b1; rtype = 2'd2; rq = hrem; do_free = 1'b1; end\n            endcase", "else begin rel = 1'b1; rtype = 2'd1; rq = hrem; do_free = 1'b1; end\n            endcase"),
 (RTL, 'a reject does not free', "else begin rel = 1'b1; rtype = 2'd2; rq = hrem; do_free = 1'b1; end\n            endcase", "else begin rel = 1'b1; rtype = 2'd2; rq = hrem; do_free = 1'b0; end\n            endcase"),
 (RTL, 'an unknown report is not an anomaly', 'if (!hit) res = UNKNOWN;\n            else case', 'if (!hit) res = OK;\n            else case'),
 (RTL, 'an anomaly is not a fault', "if (anomaly) fault <= 1'b1;", "if (1'b0) fault <= 1'b1;"),
 (RTL, 'a local refusal is a fault', "if (anomaly) fault <= 1'b1;", "if (anomaly || (l_valid && !r_valid && res != OK)) fault <= 1'b1;"),
 (RTL, 'the fault clears when a good report arrives', "if (anomaly) fault <= 1'b1;", "if (anomaly) fault <= 1'b1; else if (r_valid) fault <= 1'b0;"),
 (RTL, 'the answer is valid every cycle', 'o_valid <= r_valid || l_valid;', "o_valid <= 1'b1;"),
 (RTL, 'the answer ignores the source', 'o_src <= r_valid;', "o_src <= 1'b0;"),
 (RTL, 'the release carries the wrong account', "o_racct <= acct[hi];", "o_racct <= acct[fi];"),
 (RTL, 'the release carries the wrong symbol', "o_rsym <= sym[hi];", "o_rsym <= sym[fi];"),
 (RTL, 'the release carries the wrong side', "o_rside <= side[hi];", "o_rside <= !side[hi];"),
 (RTL, 'the release carries the wrong price', "o_rpx <= px[hi];", "o_rpx <= px[fi];"),
 (RTL, 'a fill does not reduce the remainder', 'if (do_fill) rem[hi] <= hrem - r_qty;', 'if (do_fill) rem[hi] <= hrem;'),
 (RTL, 'a fill reduces by one', 'if (do_fill) rem[hi] <= hrem - r_qty;', "if (do_fill) rem[hi] <= hrem - 1'b1;"),
 (RTL, 'the live count counts only live', 'o_live = o_live + (used[i] ? 1 : 0);', 'o_live = o_live + ((used[i] && st[i] == LIVE) ? 1 : 0);'),
 (RTL, 'reset leaves entries in use', "for (int i = 0; i < NT; i++) begin used[i] <= 1'b0;", 'for (int i = 0; i < NT; i++) begin used[i] <= used[i];'),
 (RTL, 'reset leaves the fault', "fault <= 1'b0; o_valid <= 1'b0;", "o_valid <= 1'b0;"),
 (RTL, 'reset leaves the answer valid', "o_valid <= 1'b0; o_src <= 1'b0;", "o_src <= 1'b0;"),
 (RTL, 'reset leaves the release valid', "o_rv <= 1'b0; o_rtype <= '0;", "o_rtype <= '0;"),
 (MOD, 'model: a zero order is accepted', 'if f["qty"] == 0: return ZERO, None\n            if self.find', 'if self.find'),
 (MOD, 'model: duplicates are accepted', 'if self.find(tok) is not None: return DUPTOK, None', 'pass'),
 (MOD, 'model: a cancel request needs no live state', 'if self.e[i]["st"] != LIVE: return BADSTATE, None', 'pass'),
 (MOD, 'model: overfill allowed', 'elif q > x["rem"]: anomaly = OVERFILL', 'elif q > x["rem"] + 1: anomaly = OVERFILL'),
 (MOD, 'model: a fill is not an implicit ack', 'x["st"] = LIVE if x["st"] == PNEW else x["st"];', 'pass;'),
 (MOD, 'model: a fill releases the wrong price', 'rel = (REL_FILL, x["acct"], x["sym"], x["side"], x["px"], q)', 'rel = (REL_FILL, x["acct"], x["sym"], x["side"], x["px"] + 1, q)'),
 (MOD, 'model: a cancel report keeps the entry', 'rel = (REL_CANCEL, x["acct"], x["sym"], x["side"], x["px"], x["rem"]); self.e[i] = None\n            else:', 'rel = (REL_CANCEL, x["acct"], x["sym"], x["side"], x["px"], x["rem"])\n            else:'),
 (MOD, 'model: a reject works in any state', 'if x["st"] != PNEW: anomaly = BADSTATE\n                else: rel', 'if False: anomaly = BADSTATE\n                else: rel'),
 (MOD, 'model: an anomaly is not a fault', 'if anomaly is not None: self.fault = 1;', 'if anomaly is not None:'),
 (MOD, 'model: the report does not win', 'rep = cy.get("rep"); ready = 0 if rep is not None else 1', 'rep = cy.get("rep"); ready = 1'),
]
def one(j):
    f, label, old, new = j
    d = tempfile.mkdtemp(prefix="mut25_")
    for sub in ("rtl", "tb", "out", "model", "tools"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub), ignore=shutil.ignore_patterns("*.json", "*_synth.log", "*.hex", "__pycache__", "ex*_*", "t1[0-9]_*"))
    p = os.path.join(d, f); s = open(p).read()
    if old not in s: shutil.rmtree(d, ignore_errors=True); return label, "BAD ANCHOR (0 occurrences)"
    i = s.index(old); open(p, "w").write(s[:i] + new + s[i + len(old):])
    try: q = subprocess.run([sys.executable, "tools/ch25_run.py", "--battery" if f == RTL else "--battery-model"], cwd=d, capture_output=True, text=True, timeout=900); out = q.stdout.strip().splitlines()[-1] if q.stdout.strip() else "RESULT crash: " + (q.stderr.strip().splitlines() or ["?"])[-1][:70]
    except subprocess.TimeoutExpired: out = "RESULT hang (timeout)"
    shutil.rmtree(d, ignore_errors=True); r = out.replace("RESULT ", "")
    return label, ("NOT CAUGHT" if r == "None" else "caught by: " + r[:110])
if __name__ == "__main__":
    print("NOTE: this script deliberately breaks copies of the RTL and of the model. 'caught' lines are EXPECTED: they show the battery notices the mistake.")
    q1 = subprocess.run([sys.executable, "tools/ch25_run.py", "--battery"], cwd=flow.ROOT, capture_output=True, text=True); q2 = subprocess.run([sys.executable, "tools/ch25_run.py", "--battery-model"], cwd=flow.ROOT, capture_output=True, text=True)
    base = q1.stdout.strip().endswith("None") and q2.stdout.strip().endswith("None"); print("unmutated design and model pass their batteries:", base)
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(one, MUT))
    cnt = {RTL: [0, 0], MOD: [0, 0]}
    for (f, *_), (label, st) in zip(MUT, res): print(f"  {label}: {st}"); cnt[f][1] += 1; cnt[f][0] += st.startswith("caught")
    for f, (c, n) in cnt.items(): print(f"  {f}: caught {c} of {n}")
    print(f"mutants caught: {sum(c for c, n in cnt.values())} of {len(MUT)}")
