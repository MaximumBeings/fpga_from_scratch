#!/usr/bin/env python3
"""Chapter 23: test the tests. Two families. (1) mutants of rtl/risk.sv, battery `ch23_run.py --battery`: the gate against the cycle model, every answer and the state it shows in the cycle the model says, five sizes, on random traffic, traffic with small limits, dense traffic with kills and faults, and the directed boundary sequence. (2) mutants of model/risk_gold.py, battery `--battery-model`: the model's own hand-checked scenarios (the model is the oracle; what checks IT is a handful of cases worked by hand, so this family measures how complete they are)."""
import concurrent.futures as cf, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flow
RTL = "rtl/risk.sv"; MOD = "model/risk_gold.py"
MUT = [
 (RTL, 'kill is ignored', 's1_kill <= kill;', "s1_kill <= 1'b0;"),
 (RTL, 'kill is not checked', 'if (s1_kill) res = KILL;', "if (1'b0) res = KILL;"),
 (RTL, 'kill is checked after the index', 'if (s1_kill) res = KILL;\n            else if (!armed || fault) res = DISARMED;\n            else if (bad) res = BADIDX;', 'if (!armed || fault) res = DISARMED;\n            else if (bad) res = BADIDX;\n            else if (s1_kill) res = KILL;'),
 (RTL, 'a disarmed gate lets orders through', 'else if (!armed || fault) res = DISARMED;', 'else if (fault) res = DISARMED;'),
 (RTL, 'a fault does not stop orders', 'else if (!armed || fault) res = DISARMED;', 'else if (!armed) res = DISARMED;'),
 (RTL, 'a bad index is not noticed', 'else if (bad) res = BADIDX;', "else if (1'b0) res = BADIDX;"),
 (RTL, 'a symbol equal to NS is a good index', "wire bad = (s1_a >= 4'(NA)) || (s1_s >= 4'(NS));", "wire bad = (s1_a >= 4'(NA)) || (s1_s > 4'(NS));"),
 (RTL, 'an account equal to NA is a good index', "wire bad = (s1_a >= 4'(NA)) || (s1_s >= 4'(NS));", "wire bad = (s1_a > 4'(NA)) || (s1_s >= 4'(NS));"),
 (RTL, 'a zero quantity is allowed', "else if (s1_qty == '0 || s1_qty > c_qty[a]) res = QTY;", 'else if (s1_qty > c_qty[a]) res = QTY;'),
 (RTL, 'a quantity equal to the maximum is refused', 's1_qty > c_qty[a]) res = QTY;', 's1_qty >= c_qty[a]) res = QTY;'),
 (RTL, 'a price equal to the low bound is refused', 's1_px < b_lo[s] || s1_px > b_hi[s]', 's1_px <= b_lo[s] || s1_px > b_hi[s]'),
 (RTL, 'a price equal to the high bound is refused', 's1_px < b_lo[s] || s1_px > b_hi[s]', 's1_px < b_lo[s] || s1_px >= b_hi[s]'),
 (RTL, 'the band is not checked', 'else if (s1_px < b_lo[s] || s1_px > b_hi[s]) res = BAND;', "else if (1'b0) res = BAND;"),
 (RTL, 'an order notional equal to the maximum is refused', 's1_prod > c_onot[a]) res = ONOT;', 's1_prod >= c_onot[a]) res = ONOT;'),
 (RTL, 'the order notional is not checked', 'else if (s1_prod > c_onot[a]) res = ONOT;', "else if (1'b0) res = ONOT;"),
 (RTL, 'a buy to the long limit is refused', 'buy ? (pl > mlong) : (ps < mshort)', 'buy ? (pl >= mlong) : (ps < mshort)'),
 (RTL, 'a sell to the short limit is refused', 'buy ? (pl > mlong) : (ps < mshort)', 'buy ? (pl > mlong) : (ps <= mshort)'),
 (RTL, 'the long limit is checked on the sell side', 'buy ? (pl > mlong) : (ps < mshort)', 'buy ? (ps < mshort) : (pl > mlong)'),
 (RTL, 'the position is not checked', 'else if (buy ? (pl > mlong) : (ps < mshort)) res = POS;', "else if (1'b0) res = POS;"),
 (RTL, 'the long check ignores the position', 'wire signed [PB+1:0] pl = $signed({{2{pos[a][s][PB-1]}}, pos[a][s]}) + $signed', 'wire signed [PB+1:0] pl = $signed(0) + $signed'),
 (RTL, 'the long check ignores the open buys', "+ $signed({{(PB+2-QW){1'b0}}, ob[a][s]}) + $signed({{(PB+2-QW){1'b0}}, s1_qty});      // pos + ob + qty (a buy)", "+ $signed({{(PB+2-QW){1'b0}}, 0}) + $signed({{(PB+2-QW){1'b0}}, s1_qty});      // pos + ob + qty (a buy)"),
 (RTL, 'the short check adds the open sells', "- $signed({{(PB+2-QW){1'b0}}, os[a][s]}) - $signed({{(PB+2-QW){1'b0}}, s1_qty});      // pos - os - qty (a sell)", "+ $signed({{(PB+2-QW){1'b0}}, os[a][s]}) - $signed({{(PB+2-QW){1'b0}}, s1_qty});      // pos - os - qty (a sell)"),
 (RTL, 'the short check ignores the open sells', "- $signed({{(PB+2-QW){1'b0}}, os[a][s]}) - $signed({{(PB+2-QW){1'b0}}, s1_qty});      // pos - os - qty (a sell)", "- $signed({{(PB+2-QW){1'b0}}, 0}) - $signed({{(PB+2-QW){1'b0}}, s1_qty});      // pos - os - qty (a sell)"),
 (RTL, 'the short limit has the wrong sign', "mshort = -$signed({{(PB+2-QW){1'b0}}, c_short[a]});", "mshort = $signed({{(PB+2-QW){1'b0}}, c_short[a]});"),
 (RTL, 'a notional equal to the maximum is refused', 'notl[a] + prod > c_not[a]) res = NOT;', 'notl[a] + prod >= c_not[a]) res = NOT;'),
 (RTL, 'the notional ignores the open orders', 'notl[a] + prod > c_not[a]) res = NOT;', 'prod > c_not[a]) res = NOT;'),
 (RTL, 'the notional is not checked', 'else if (notl[a] + prod > c_not[a]) res = NOT;', "else if (1'b0) res = NOT;"),
 (RTL, 'no token is not noticed', "else if (tok[a] == '0) res = RATE;", "else if (1'b0) res = RATE;"),
 (RTL, 'the last token is refused', "else if (tok[a] == '0) res = RATE;", 'else if (tok[a] <= 1) res = RATE;'),
 (RTL, 'a release of more than is open is accepted (buy)', '(buy ? (s1_qty > ob[a][s]) : (s1_qty > os[a][s]))', '(buy ? (s1_qty > ob[a][s] + 1) : (s1_qty > os[a][s]))'),
 (RTL, 'a release of more than is open is accepted (sell)', '(buy ? (s1_qty > ob[a][s]) : (s1_qty > os[a][s]))', '(buy ? (s1_qty > ob[a][s]) : (s1_qty > os[a][s] + 1))'),
 (RTL, 'a release of exactly what is open is a fault', '(buy ? (s1_qty > ob[a][s]) : (s1_qty > os[a][s]))', '(buy ? (s1_qty >= ob[a][s]) : (s1_qty > os[a][s]))'),
 (RTL, 'a release is checked on the wrong side', '(buy ? (s1_qty > ob[a][s]) : (s1_qty > os[a][s]))', '(buy ? (s1_qty > os[a][s]) : (s1_qty > ob[a][s]))'),
 (RTL, 'a release of more notional than is open is accepted', '|| prod > notl[a]) begin res = FAULT;', '|| prod > notl[a] + 1) begin res = FAULT;'),
 (RTL, 'a release for a bad index is not a fault', 'if (bad || (buy ?', 'if ((buy ? '),
 (RTL, 'a fault does not latch', "if (s1_v && fault_set) fault <= 1'b1;", 'if (s1_v && fault_set) fault <= fault;'),
 (RTL, 'an order does not take a token', "(s1_v && isord && took && a == AW'(g) && !bad) ? tok[g] - 1'b1 : tok[g]", "(s1_v && isord && 1'b0 && a == AW'(g) && !bad) ? tok[g] - 1'b1 : tok[g]"),
 (RTL, 'tokens are taken from the wrong account', "a == AW'(g) && !bad) ? tok[g] - 1'b1", "a == AW'(0) && !bad) ? tok[g] - 1'b1"),
 (RTL, 'the bucket can exceed its size', '(tick && tok_after[i] < c_cap[i])', '(tick && tok_after[i] <= c_cap[i])'),
 (RTL, 'the bucket does not refill', '(tick && tok_after[i] < c_cap[i])', "(1'b0 && tok_after[i] < c_cap[i])"),
 (RTL, 'the bucket refills on every cycle', '(tick && tok_after[i] < c_cap[i])', '(tok_after[i] < c_cap[i])'),
 (RTL, 'the tick is one cycle late', "wire tick = (phase == PHW'(R - 1));", "wire tick = (phase == PHW'(R - 2));"),
 (RTL, 'the tick is one cycle early', "wire tick = (phase == PHW'(R - 1));", "wire tick = (phase == PHW'(0));"),
 (RTL, 'an order does not add to the open buys', 'if (buy) ob[a][s] <= ob[a][s] + s1_qty; else os[a][s] <= os[a][s] + s1_qty;', 'if (buy) os[a][s] <= os[a][s] + s1_qty; else ob[a][s] <= ob[a][s] + s1_qty;'),
 (RTL, 'an order does not add to the notional', 'notl[a] <= notl[a] + prod;\n            end', 'notl[a] <= notl[a];\n            end'),
 (RTL, 'a release does not reduce the open quantity', 'if (buy) ob[a][s] <= ob[a][s] - s1_qty; else os[a][s] <= os[a][s] - s1_qty;', 'if (buy) os[a][s] <= os[a][s] - s1_qty; else ob[a][s] <= ob[a][s] - s1_qty;'),
 (RTL, 'a release does not reduce the notional', 'notl[a] <= notl[a] - prod;\n                if', 'notl[a] <= notl[a];\n                if'),
 (RTL, 'a cancel moves the position', 'if (isfill) pos[a][s] <=', "if (1'b1) pos[a][s] <="),
 (RTL, 'a fill does not move the position', 'if (isfill) pos[a][s] <=', "if (1'b0) pos[a][s] <="),
 (RTL, 'a fill moves the position the wrong way', "pos[a][s] <= buy ? pos[a][s] + $signed({{2{1'b0}}, s1_qty}) : pos[a][s] - $signed({{2{1'b0}}, s1_qty});", "pos[a][s] <= buy ? pos[a][s] - $signed({{2{1'b0}}, s1_qty}) : pos[a][s] + $signed({{2{1'b0}}, s1_qty});"),
 (RTL, 'a rejected release is applied', 'wire apply = s1_v && !isord && !fault_set;', 'wire apply = s1_v && !isord;'),
 (RTL, 'a release is not applied after a fault', 'wire apply = s1_v && !isord && !fault_set;', 'wire apply = s1_v && !isord && !fault_set && !fault;'),
 (RTL, 'a release is not applied while disarmed', 'wire apply = s1_v && !isord && !fault_set;', 'wire apply = s1_v && !isord && !fault_set && armed;'),
 (RTL, 'a configuration write does not set max long', 'c_long[i] <= cfg_maxlong;', 'c_long[i] <= c_long[i];'),
 (RTL, 'a configuration write does not set max short', 'c_short[i] <= cfg_maxshort;', 'c_short[i] <= c_short[i];'),
 (RTL, 'a configuration write does not set max quantity', 'c_qty[i] <= cfg_maxqty;', 'c_qty[i] <= c_qty[i];'),
 (RTL, 'a configuration write does not set max order notional', 'c_onot[i] <= cfg_maxonot;', 'c_onot[i] <= c_onot[i];'),
 (RTL, 'a configuration write does not set max notional', 'c_not[i] <= cfg_maxnot;', 'c_not[i] <= c_not[i];'),
 (RTL, 'a configuration write does not set the bucket size', 'c_cap[i] <= cfg_cap;', 'c_cap[i] <= c_cap[i];'),
 (RTL, 'a configuration write does not refill the bucket', 'c_cap[i] <= cfg_cap; tok[i] <= cfg_cap;', 'c_cap[i] <= cfg_cap;'),
 (RTL, 'a configuration write swaps long and short', 'c_long[i] <= cfg_maxlong; c_short[i] <= cfg_maxshort;', 'c_long[i] <= cfg_maxshort; c_short[i] <= cfg_maxlong;'),
 (RTL, 'a band write does not set the low bound', 'b_lo[j] <= cfg_lo;', 'b_lo[j] <= b_lo[j];'),
 (RTL, 'a band write does not set the high bound', 'b_hi[j] <= cfg_hi;', 'b_hi[j] <= b_hi[j];'),
 (RTL, 'arm ignores the kill input', "else if (ctl_arm && !kill) armed <= 1'b1;", "else if (ctl_arm) armed <= 1'b1;"),
 (RTL, 'arm wins over disarm', "if (ctl_disarm) armed <= 1'b0; else if (ctl_arm && !kill) armed <= 1'b1;", "if (ctl_arm && !kill) armed <= 1'b1; else if (ctl_disarm) armed <= 1'b0;"),
 (RTL, 'reset arms the gate', "armed <= 1'b0; fault <= 1'b0; phase <= '0;", "armed <= 1'b1; fault <= 1'b0; phase <= '0;"),
 (RTL, 'reset does not clear the fault', "armed <= 1'b0; fault <= 1'b0; phase <= '0;", "armed <= 1'b0; phase <= '0;"),
 (RTL, 'reset does not clear the phase', "armed <= 1'b0; fault <= 1'b0; phase <= '0;", "armed <= 1'b0; fault <= 1'b0;"),
 (RTL, 'reset does not clear the maximum quantity', "c_qty[i] <= '0;", 'c_qty[i] <= c_qty[i];'),
 (RTL, 'reset does not clear the bucket size', "c_cap[i] <= '0;", 'c_cap[i] <= c_cap[i];'),
 (RTL, 'reset does not empty the bands', "b_lo[j] <= '1; b_hi[j] <= '0;", 'b_lo[j] <= b_lo[j]; b_hi[j] <= b_hi[j];'),
 (RTL, 'reset does not clear the notional', "notl[i] <= '0;", 'notl[i] <= notl[i];'),
 (RTL, 'reset does not clear the tokens', "tok[i] <= '0; for", 'tok[i] <= tok[i]; for'),
 (RTL, 'reset does not clear the positions', "pos[i][j] <= '0; ob[i][j] <= '0; os[i][j] <= '0;", "ob[i][j] <= '0; os[i][j] <= '0;"),
 (RTL, 'reset does not clear the open buys', "pos[i][j] <= '0; ob[i][j] <= '0; os[i][j] <= '0;", "pos[i][j] <= '0; os[i][j] <= '0;"),
 (RTL, 'the notional is a sum, not a product', 's1_prod <= ev_px * ev_qty;', 's1_prod <= ev_px + ev_qty;'),
 (RTL, 'the answer shows the open sells for the open buys', "o_ob <= bad ? '0 : ob_n;", "o_ob <= bad ? '0 : os_n;"),
 (RTL, 'the answer shows the tokens after the tick', "o_tok <= bad ? '0 : tok_after[a];", "o_tok <= bad ? '0 : tok[a];"),
 (RTL, 'the answer for a bad index is not zero', "o_pos <= (bad) ? '0 : pos_n;", 'o_pos <= pos_n;'),
 (RTL, 'the answer shows the notional before the update', "o_not <= bad ? '0 : not_n;", "o_not <= bad ? '0 : notl[a];"),
 (RTL, 'the answer shows the position before the update', "o_pos <= (bad) ? '0 : pos_n;", "o_pos <= (bad) ? '0 : pos[a][s];"),
 (MOD, 'model: kill is checked after the arming', 'if kill: r = KILL\n            elif not self.armed or self.fault: r = DISARMED', 'if not self.armed or self.fault: r = DISARMED\n            elif kill: r = KILL'),
 (MOD, 'model: a fault does not refuse orders', 'elif not self.armed or self.fault: r = DISARMED', 'elif not self.armed: r = DISARMED'),
 (MOD, 'model: the band is exclusive', 'elif not lo <= px <= hi: r = BAND', 'elif not lo < px < hi: r = BAND'),
 (MOD, 'model: the long limit is checked after the open sells', '(side == BUY and self.pos[a][s] + self.ob[a][s] + qty > c["maxlong"])', '(side == BUY and self.pos[a][s] + self.ob[a][s] - self.os[a][s] + qty > c["maxlong"])'),
 (MOD, 'model: the short check uses the open buys', '(side == SELL and self.pos[a][s] - self.os[a][s] - qty < -c["maxshort"])', '(side == SELL and self.pos[a][s] - self.ob[a][s] - qty < -c["maxshort"])'),
 (MOD, 'model: the notional is checked before the order notional', 'elif prod > c["maxonot"]: r = ONOT\n                elif (side == BUY', 'elif self.notional[a] + prod > c["maxnot"]: r = NOT\n                elif prod > c["maxonot"]: r = ONOT\n                elif (side == BUY'),
 (MOD, 'model: a rejected order takes a token', 'if r == OK:\n                if side == BUY: self.ob[a][s] += qty', 'self.tokens[a] -= 1 if a < self.na and self.tokens[a] else 0\n            if r == OK:\n                if side == BUY: self.ob[a][s] += qty'),
 (MOD, 'model: a cancel moves the position', 'if t == FILL: self.pos[a][s] += qty if side == BUY else -qty', 'self.pos[a][s] += qty if side == BUY else -qty'),
 (MOD, 'model: a release of more than is open is applied', 'if bad or qty > open_ or prod > self.notional[a]: self.fault = 1', 'if bad or prod > self.notional[a]: self.fault = 1'),
 (MOD, 'model: a fault is not latched', 'self.fault = 1; return t, FAULT', 'return t, FAULT'),
 (MOD, 'model: arm is allowed while killed', 'elif cy.get("arm") and not cy.get("kill", 0): g.armed = 1', 'elif cy.get("arm"): g.armed = 1'),
 (MOD, 'model: arm wins over disarm', 'if cy.get("disarm"): g.armed = 0\n        elif cy.get("arm") and not cy.get("kill", 0): g.armed = 1', 'if cy.get("arm") and not cy.get("kill", 0): g.armed = 1\n        elif cy.get("disarm"): g.armed = 0'),
 (MOD, 'model: the tick is one cycle late', 'if c % r == r - 1 and g.tokens[a] < g.cfg[a]["cap"]', 'if c % r == 0 and g.tokens[a] < g.cfg[a]["cap"]'),
 (MOD, 'model: a configuration write does not refill', 'g.cfg[a] = dict(u); g.tokens[a] = u["cap"]', 'g.cfg[a] = dict(u)'),
 (MOD, "model: the kill of the order's cycle is not used", 'pend = (cy["ev"], cy.get("kill", 0)) if "ev" in cy else None', 'pend = (cy["ev"], 0) if "ev" in cy else None'),
 (MOD, 'model: the answer shows the state of the tick', 'rows[c + 1 if c + 1 < n else c] = (1, kind, res) + st', 'rows[c + 1 if c + 1 < n else c] = (1, kind, res) + st[:4] + (st[4] + (1 if c % r == r - 1 else 0),)'),
]
def one(j):
    f, label, old, new = j
    d = tempfile.mkdtemp(prefix="mut23_")
    for sub in ("rtl", "tb", "out", "model", "tools"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub), ignore=shutil.ignore_patterns("*.json", "*_synth.log", "*.hex", "__pycache__", "ex*_*", "t1[0-9]_*"))
    p = os.path.join(d, f); s = open(p).read()
    if old not in s: shutil.rmtree(d, ignore_errors=True); return label, "BAD ANCHOR (0 occurrences)"
    i = s.index(old); open(p, "w").write(s[:i] + new + s[i + len(old):])
    try: q = subprocess.run([sys.executable, "tools/ch23_run.py", "--battery" if f == RTL else "--battery-model"], cwd=d, capture_output=True, text=True, timeout=900); out = q.stdout.strip().splitlines()[-1] if q.stdout.strip() else "RESULT crash: " + (q.stderr.strip().splitlines() or ["?"])[-1][:70]
    except subprocess.TimeoutExpired: out = "RESULT hang (timeout)"
    shutil.rmtree(d, ignore_errors=True); r = out.replace("RESULT ", "")
    return label, ("NOT CAUGHT" if r == "None" else "caught by: " + r[:110])
if __name__ == "__main__":
    print("NOTE: this script deliberately breaks copies of the RTL and of the model. 'caught' lines are EXPECTED: they show the battery notices the mistake.")
    q1 = subprocess.run([sys.executable, "tools/ch23_run.py", "--battery"], cwd=flow.ROOT, capture_output=True, text=True); q2 = subprocess.run([sys.executable, "tools/ch23_run.py", "--battery-model"], cwd=flow.ROOT, capture_output=True, text=True)
    base = q1.stdout.strip().endswith("None") and q2.stdout.strip().endswith("None"); print("unmutated design and model pass their batteries:", base)
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(one, MUT))
    cnt = {RTL: [0, 0], MOD: [0, 0]}
    for (f, *_), (label, st) in zip(MUT, res): print(f"  {label}: {st}"); cnt[f][1] += 1; cnt[f][0] += st.startswith("caught")
    for f, (c, n) in cnt.items(): print(f"  {f}: caught {c} of {n}")
    print(f"mutants caught: {sum(c for c, n in cnt.values())} of {len(MUT)}")
