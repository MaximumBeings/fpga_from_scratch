#!/usr/bin/env python3
"""Chapter 22: test the tests. Two families. (1) mutants of rtl/sig.sv, battery `ch22_run.py --battery`: the unit against the bit-exact model, every output bit in every cycle, five formats and both dividers, on random books with gaps and in bursts and on the directed boundary books. (2) mutants of model/sig_gold.py, battery `--battery-model`: the model's own hand-checked scenarios and the checks that the division done as the hardware does it equals the specification (the model is the oracle; what checks IT is a handful of cases worked by hand, so this family measures how complete they are)."""
import concurrent.futures as cf, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flow
RTL = "rtl/sig.sv"; MOD = "model/sig_gold.py"
MUT = [
 (RTL, 'only the bid side is checked for shares', "wire        x_ok  = (in_bsh != '0) && (in_ash != '0);", "wire        x_ok  = (in_bsh != '0);"),
 (RTL, 'only the ask side is checked for shares', "wire        x_ok  = (in_bsh != '0) && (in_ash != '0);", "wire        x_ok  = (in_ash != '0);"),
 (RTL, 'a side without shares is allowed', "wire        x_ok  = (in_bsh != '0) && (in_ash != '0);", "wire        x_ok  = (in_bsh != '0) || (in_ash != '0);"),
 (RTL, 'the total quantity is a difference', "wire [QW:0] x_d   = {1'b0, in_bsh} + {1'b0, in_ash};", "wire [QW:0] x_d   = {1'b0, in_bsh} - {1'b0, in_ash};"),
 (RTL, 'the spread has the wrong sign', "wire signed [PW:0] x_s = $signed({1'b0, in_apx}) - $signed({1'b0, in_bpx});", "wire signed [PW:0] x_s = $signed({1'b0, in_bpx}) - $signed({1'b0, in_apx});"),
 (RTL, 'the mid is a difference', "wire [PW:0] x_m2  = {1'b0, in_apx} + {1'b0, in_bpx};", "wire [PW:0] x_m2  = {1'b0, in_apx} - {1'b0, in_bpx};"),
 (RTL, 'the division step compares with >', "rem_next = (r2 >= {1'b0, d}) ? (QW + 1)'(r2 - {1'b0, d}) : r2[QW:0];", "rem_next = (r2 > {1'b0, d}) ? (QW + 1)'(r2 - {1'b0, d}) : r2[QW:0];"),
 (RTL, 'the quotient bit compares with >', "bit_next = (r2 >= {1'b0, d});", "bit_next = (r2 > {1'b0, d});"),
 (RTL, "the divider starts from the ask's shares (pipelined)", "r[0] <= {1'b0, in_bsh};", "r[0] <= {1'b0, in_ash};"),
 (RTL, "the divider starts from the ask's shares (shared)", "d_r <= {1'b0, in_bsh};", "d_r <= {1'b0, in_ash};"),
 (RTL, 'the quotient bit is inverted', 't[i+1] <= {t[i][F-2:0], bit_next(r[i], dd[i])};', 't[i+1] <= {t[i][F-2:0], !bit_next(r[i], dd[i])};'),
 (RTL, 'the quotient is not shifted', 't[i+1] <= {t[i][F-2:0], bit_next(r[i], dd[i])};', 't[i+1] <= {t[i][F-1:1], bit_next(r[i], dd[i])};'),
 (RTL, 'the remainder is not carried', 'r[i+1] <= rem_next(r[i], dd[i]);', 'r[i+1] <= r[i];'),
 (RTL, 'the total is not carried', 'dd[i+1] <= dd[i];', 'dd[i+1] <= dd[0];'),
 (RTL, 'the pipelined valid is not reset along the chain', 'v[i+1] <= v[i] && !rst;', 'v[i+1] <= v[i];'),
 (RTL, "the shared divider's result is flagged one cycle early", "if (cnt == FC - 1'b1) d_v <= 1'b1;", "if (cnt == FC - 2'd2) d_v <= 1'b1;"),
 (RTL, "the shared divider's result is flagged one cycle late", "if (cnt == FC - 1'b1) d_v <= 1'b1;", "if (cnt == FC) d_v <= 1'b1;"),
 (RTL, 'the shared divider is free one cycle early', "cnt <= cnt + 1'b1; if (cnt == FC + CW'(2)) busy <= 1'b0;", "cnt <= cnt + 1'b1; if (cnt == FC + CW'(1)) busy <= 1'b0;"),
 (RTL, 'the shared divider is free one cycle late', "cnt <= cnt + 1'b1; if (cnt == FC + CW'(2)) busy <= 1'b0;", "cnt <= cnt + 1'b1; if (cnt == FC + CW'(3)) busy <= 1'b0;"),
 (RTL, 'the shared divider is always ready', 'assign in_ready = !busy;', "assign in_ready = 1'b1;"),
 (RTL, 'the shared divider takes a message while busy', 'else if (!busy) begin\n                if (in_valid) begin', "else if (1'b1) begin\n                if (in_valid) begin"),
 (RTL, "the shared divider's valid is not reset", "if (rst) busy <= 1'b0;", "if (1'b0) busy <= 1'b0;"),
 (RTL, 'rounding is half down', "({d_r, 1'b0} >= {1'b0, d_d})", "({d_r, 1'b0} > {1'b0, d_d})"),
 (RTL, 'there is no rounding', "{1'b0, d_t} + {{F{1'b0}}, ({d_r, 1'b0} >= {1'b0, d_d})}", "{1'b0, d_t}"),
 (RTL, 'the rounding compares the remainder with the total', "({d_r, 1'b0} >= {1'b0, d_d})", "({1'b0, d_r} >= {1'b0, d_d})"),
 (RTL, 'the imbalance is 2 w - 2^F + 1', "{w_n, 1'b0} - {1'b0, 1'b1, {F{1'b0}}}", "{w_n, 1'b0} - {1'b0, 1'b1, {F{1'b0}}} + 1'b1"),
 (RTL, 'the imbalance is w - 2^(F-1)', "{w_n, 1'b0} - {1'b0, 1'b1, {F{1'b0}}}", "{1'b0, w_n} - {2'b00, 1'b1, {(F-1){1'b0}}}"),
 (RTL, 'the imbalance is not registered', 'a_imb <= imb_n;', "a_imb <= '0;"),
 (RTL, 'the product drops the top bit of w', "b_prod <= (PW + F)'(a_s * $signed({1'b0, a_w}));", "b_prod <= (PW + F)'(a_s * $signed({2'b00, a_w[F-1:0]}));"),
 (RTL, 'the product is unsigned in the spread', "b_prod <= (PW + F)'(a_s * $signed({1'b0, a_w}));", "b_prod <= (PW + F)'($signed({1'b0, a_s[PW-1:0]}) * $signed({1'b0, a_w}));"),
 (RTL, 'the product uses the spread of the previous stage', "b_prod <= (PW + F)'(a_s * $signed({1'b0, a_w}));", "b_prod <= (PW + F)'(b_s * $signed({1'b0, a_w}));"),
 (RTL, 'the microprice has no price term', "{b_pb, {F{1'b0}}} + b_prod", 'b_prod'),
 (RTL, 'the microprice price term is not shifted', "{b_pb, {F{1'b0}}} + b_prod", "{{F{1'b0}}, b_pb} + b_prod"),
 (RTL, 'the microprice starts from the mid', "{b_pb, {F{1'b0}}} + b_prod", "{b_m2, {(F-1){1'b0}}} + b_prod"),
 (RTL, 'the price is not carried', 'a_pb <= d_pb;', "a_pb <= '0;"),
 (RTL, 'the spread is not carried to the multiplier', 'a_s <= d_s;', "a_s <= '0;"),
 (RTL, 'the mid is not carried', 'a_m2 <= d_m2;', "a_m2 <= '0;"),
 (RTL, 'the mid output is not gated', "o_mid2 <= b_ok ? b_m2 : '0;", 'o_mid2 <= b_m2;'),
 (RTL, 'the spread output is not gated', "o_spread <= b_ok ? b_s : '0;", 'o_spread <= b_s;'),
 (RTL, 'the cross flag is not gated', 'o_cross <= b_ok && b_s[PW];', 'o_cross <= b_s[PW];'),
 (RTL, 'the lock flag is not gated', "o_lock <= b_ok && (b_s == '0);", "o_lock <= (b_s == '0);"),
 (RTL, 'the w output is not gated', "o_w <= b_ok ? b_w : '0;", 'o_w <= b_w;'),
 (RTL, 'the imbalance output is not gated', "o_imb <= b_ok ? b_imb : '0;", 'o_imb <= b_imb;'),
 (RTL, 'the microprice output is not gated', "o_micro <= b_ok ? micro_n : '0;", 'o_micro <= micro_n;'),
 (RTL, 'the cross flag is the wrong bit', 'o_cross <= b_ok && b_s[PW];', 'o_cross <= b_ok && b_s[PW-1];'),
 (RTL, 'the lock flag tests one bit', "o_lock <= b_ok && (b_s == '0);", "o_lock <= b_ok && (b_s[0] == 1'b0);"),
 (RTL, 'the ok flag is not carried', 'o_valid <= b_v; o_ok <= b_ok;', "o_valid <= b_v; o_ok <= 1'b1;"),
 (MOD, 'model: rounding is floor', 'w = (2 * bsh * (1 << F) + d) // (2 * d)', 'w = (bsh * (1 << F)) // d'),
 (MOD, 'model: rounding is half down', 'w = (2 * bsh * (1 << F) + d) // (2 * d)', 'w = (2 * bsh * (1 << F) + d - 1) // (2 * d)'),
 (MOD, 'model: the imbalance is 2 w', '2 * w - (1 << F), bpx', '2 * w, bpx'),
 (MOD, 'model: the microprice uses the wrong spread sign', 'bpx * (1 << F) + s * w)', 'bpx * (1 << F) - s * w)'),
 (MOD, 'model: lock is spread <= 0', 'int(s == 0)', 'int(s <= 0)'),
 (MOD, 'model: cross is spread <= 0', 'int(s < 0)', 'int(s <= 0)'),
 (MOD, 'model: a side without shares gives signals', 'if bsh == 0 or ash == 0: return (0, 0, 0, 0, 0, 0, 0, 0)', 'if bsh == 0 and ash == 0: return (0, 0, 0, 0, 0, 0, 0, 0)'),
 (MOD, 'model: the answer comes one cycle early', 'L = f + 4; n = len(msgs)', 'L = f + 3; n = len(msgs)'),
 (MOD, 'model: the shared divider is free one cycle early', 'ready = 1 if (div == 1 or t >= busy_until) else 0', 'ready = 1 if (div == 1 or t >= busy_until - 1) else 0'),
 (MOD, 'model: the pipelined divider is busy', 'ready = 1 if (div == 1 or t >= busy_until) else 0', 'ready = 1 if t >= busy_until else 0'),
 (MOD, "model: the division does not start from the bid's shares", 'd = bsh + ash; r = bsh; t = 0', 'd = bsh + ash; r = ash; t = 0'),
 (MOD, 'model: the division has one step too few', 'for _ in range(F):\n        r *= 2', 'for _ in range(F - 1):\n        r *= 2'),
 (MOD, 'model: the mid is exact in ticks', 'return (1, apx + bpx, s', 'return (1, (apx + bpx) // 2, s'),
]
def one(j):
    f, label, old, new = j
    d = tempfile.mkdtemp(prefix="mut22_")
    for sub in ("rtl", "tb", "out", "model", "tools"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub), ignore=shutil.ignore_patterns("*.json", "*_synth.log", "*.hex", "__pycache__", "ex*_*", "t1[0-9]_*"))
    p = os.path.join(d, f); s = open(p).read()
    if old not in s: shutil.rmtree(d, ignore_errors=True); return label, "BAD ANCHOR (0 occurrences)"
    i = s.index(old); open(p, "w").write(s[:i] + new + s[i + len(old):])
    try: q = subprocess.run([sys.executable, "tools/ch22_run.py", "--battery" if f == RTL else "--battery-model"], cwd=d, capture_output=True, text=True, timeout=900); out = q.stdout.strip().splitlines()[-1] if q.stdout.strip() else "RESULT crash: " + (q.stderr.strip().splitlines() or ["?"])[-1][:70]
    except subprocess.TimeoutExpired: out = "RESULT hang (timeout)"
    shutil.rmtree(d, ignore_errors=True); r = out.replace("RESULT ", "")
    return label, ("NOT CAUGHT" if r == "None" else "caught by: " + r[:110])
if __name__ == "__main__":
    print("NOTE: this script deliberately breaks copies of the RTL and of the model. 'caught' lines are EXPECTED: they show the battery notices the mistake.")
    q1 = subprocess.run([sys.executable, "tools/ch22_run.py", "--battery"], cwd=flow.ROOT, capture_output=True, text=True); q2 = subprocess.run([sys.executable, "tools/ch22_run.py", "--battery-model"], cwd=flow.ROOT, capture_output=True, text=True)
    base = q1.stdout.strip().endswith("None") and q2.stdout.strip().endswith("None"); print("unmutated design and model pass their batteries:", base)
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(one, MUT))
    cnt = {RTL: [0, 0], MOD: [0, 0]}
    for (f, *_), (label, st) in zip(MUT, res): print(f"  {label}: {st}"); cnt[f][1] += 1; cnt[f][0] += st.startswith("caught")
    for f, (c, n) in cnt.items(): print(f"  {f}: caught {c} of {n}")
    print(f"mutants caught: {sum(c for c, n in cnt.values())} of {len(MUT)}")
