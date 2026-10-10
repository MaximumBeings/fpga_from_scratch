#!/usr/bin/env python3
"""Chapter 21: test the tests. Two families. (1) mutants of rtl/trig.sv, battery `ch21_run.py --battery`: the engine against the cycle model, every answer in the cycle the model says, five sizes (one and two comparison stages), on random traffic, 32-bit keys, keys one bit apart, a message in every cycle and the directed edge cases of every comparison. (2) mutants of model/trig_gold.py, battery `--battery-model`: the model's own hand-checked scenarios (the model is the oracle; what checks IT is a handful of cases worked by hand, so this family measures how complete they are)."""
import concurrent.futures as cf, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flow
RTL = "rtl/trig.sv"; MOD = "model/trig_gold.py"
MUT = [
 (RTL, 'the hash ignores byte 1', '(in_key ^ (in_key >> 8) ^ (in_key >> 16) ^ (in_key >> 24))', '(in_key ^ (in_key >> 16) ^ (in_key >> 24))'),
 (RTL, 'the hash ignores byte 2', '(in_key ^ (in_key >> 8) ^ (in_key >> 16) ^ (in_key >> 24))', '(in_key ^ (in_key >> 8) ^ (in_key >> 24))'),
 (RTL, 'the hash ignores byte 3', '(in_key ^ (in_key >> 8) ^ (in_key >> 16) ^ (in_key >> 24))', '(in_key ^ (in_key >> 8) ^ (in_key >> 16))'),
 (RTL, 'the hash is of the low bits of the key only', "wire [BW-1:0] hrow = BW'(in_key ^ (in_key >> 8) ^ (in_key >> 16) ^ (in_key >> 24));", "wire [BW-1:0] hrow = BW'(in_key);"),
 (RTL, 'a table write goes to the wrong row', "mem[BW'(ld_addr / 12'(K))] <= {ld_val, ld_key[31:BW], ld_idx};", "mem[BW'(ld_addr)] <= {ld_val, ld_key[31:BW], ld_idx};"),
 (RTL, 'a table write ignores the valid bit', '<= {ld_val, ld_key[31:BW], ld_idx};', "<= {1'b1, ld_key[31:BW], ld_idx};"),
 (RTL, 'a table write ignores the index', '<= {ld_val, ld_key[31:BW], ld_idx};', "<= {ld_val, ld_key[31:BW], 5'd0};"),
 (RTL, 'a table write drops a key bit', '<= {ld_val, ld_key[31:BW], ld_idx};', "<= {ld_val, ld_key[31:BW+1], 1'b0, ld_idx};"),
 (RTL, 'a table write is not conditioned on its way', "else if (ld_valid && (ld_addr % 12'(K)) == 12'(g)) mem", 'else if (ld_valid) mem'),
 (RTL, 'a table write is not conditioned on ld_valid', "else if (ld_valid && (ld_addr % 12'(K)) == 12'(g)) mem", "else if ((ld_addr % 12'(K)) == 12'(g)) mem"),
 (RTL, 'the clearing sweep stops one row early', "if (ini == BW'(NB - 1)) ini_run <= 1'b0;", "if (ini == BW'(NB - 2)) ini_run <= 1'b0;"),
 (RTL, 'the clearing sweep writes nothing', "if (ini_run) mem[ini] <= '0;", 'if (ini_run) mem[ini] <= mem[ini];'),
 (RTL, 'the engine is always ready', 'assign o_ready = !ini_run;', "assign o_ready = 1'b1;"),
 (RTL, 'the lookup reads another row', 'rd <= mem[hrow];', "rd <= mem[hrow + 1'b1];"),
 (RTL, 'an invalid entry can match', 'hitw[g] = rdw[g][WW-1] && (rdw[g][WW-2 -: KB] == s1_key[31:BW]);', 'hitw[g] = (rdw[g][WW-2 -: KB] == s1_key[31:BW]);'),
 (RTL, 'one bit fewer of the key is compared', '(rdw[g][WW-2 -: KB] == s1_key[31:BW])', '(rdw[g][WW-2 -: KB-1] == s1_key[31:BW+1])'),
 (RTL, 'only the high 16 bits of the key are compared', '(rdw[g][WW-2 -: KB] == s1_key[31:BW])', '(rdw[g][WW-2 -: 16] == s1_key[31:16])'),
 (RTL, 'the index drops its top bit', 'idx_or = idx_or | rdw[g][4:0];', "idx_or = idx_or | {1'b0, rdw[g][3:0]};"),
 (RTL, 'the found flag needs all the ways to match', 's2_found <= |hitw;', 's2_found <= &hitw;'),
 (RTL, 'the found flag is always set', 's2_found <= |hitw;', "s2_found <= 1'b1;"),
 (RTL, 'a rule write ignores the rule index', "else if (cfg_valid) for (int r = 0; r < R; r++) if (cfg_rule == 4'(r)) begin", "else if (cfg_valid) for (int r = 0; r < R; r++) if (cfg_rule == 4'(0)) begin"),
 (RTL, 'a rule write is not conditioned on cfg_valid', 'else if (cfg_valid) for (int r = 0; r < R; r++) if (cfg_rule', "else if (1'b1) for (int r = 0; r < R; r++) if (cfg_rule"),
 (RTL, 'a rule write does not set en', 'r_en[r] <= cfg_en; r_neg', 'r_neg'),
 (RTL, 'a rule write does not set neg', 'r_neg[r] <= cfg_neg; r_tmask', 'r_tmask'),
 (RTL, 'a rule write does not set the type mask', 'r_tmask[r] <= cfg_tmask; r_symany', 'r_symany'),
 (RTL, 'a rule write does not set symany', 'r_symany[r] <= cfg_symany; r_sideany', 'r_sideany'),
 (RTL, 'a rule write does not set sideany', 'r_sideany[r] <= cfg_sideany; r_side[r]', 'r_side[r]'),
 (RTL, 'a rule write does not set the side', 'r_side[r] <= cfg_side; r_pxop', 'r_pxop'),
 (RTL, 'a rule write does not set the price op', 'r_pxop[r] <= cfg_pxop; r_shop', 'r_shop'),
 (RTL, 'a rule write does not set the shares op', 'r_shop[r] <= cfg_shop;\n', '\n'),
 (RTL, 'a rule write does not set the symbol mask', 'r_symmask[r] <= cfg_symmask; r_pxval', 'r_pxval'),
 (RTL, 'a rule write does not set the price value', 'r_pxval[r] <= cfg_pxval; r_shval', 'r_shval'),
 (RTL, 'a rule write does not set the shares value', 'r_shval[r] <= cfg_shval;\n', '\n'),
 (RTL, 'a rule write swaps the two values', 'r_pxval[r] <= cfg_pxval; r_shval[r] <= cfg_shval;', 'r_pxval[r] <= cfg_shval; r_shval[r] <= cfg_pxval;'),
 (RTL, 'reset does not disable the rules', "if (rst) for (int r = 0; r < R; r++) r_en[r] <= 1'b0;\n        else if (cfg_valid)", 'if (rst) ;\n        else if (cfg_valid)'),
 (RTL, 'the type mask is indexed by bit 0 only', 'r_tmask[r][s2_t[2:0]]', 'r_tmask[r][s2_t[0]]'),
 (RTL, 'the type mask is indexed by the wrong type', 'r_tmask[r][s2_t[2:0]]', "r_tmask[r][s2_t[2:0] ^ 3'd1]"),
 (RTL, 'symany does not admit an unknown key', '(r_symany[r] || (s2_found', "(1'b0 || (s2_found"),
 (RTL, 'symany is ignored', '(r_symany[r] || (s2_found', "(1'b1 || (s2_found"),
 (RTL, 'an unknown key can match a symbol mask', '(s2_found && r_symmask[r][s2_idx])', '(r_symmask[r][s2_idx])'),
 (RTL, 'the symbol mask is read at the wrong index', 'r_symmask[r][s2_idx]', "r_symmask[r][s2_idx ^ 5'd1]"),
 (RTL, 'sideany is ignored', '(r_sideany[r] || (s2_side == r_side[r]))', "(1'b1)"),
 (RTL, 'the side test is inverted', '(s2_side == r_side[r])', '(s2_side != r_side[r])'),
 (RTL, 'ANY is not always true', "3'd0: cmpf = 1'b1;", "3'd0: cmpf = lt;"),
 (RTL, 'LT is LE', "3'd1: cmpf = lt;", "3'd1: cmpf = lt | eq;"),
 (RTL, 'LE is LT', "3'd2: cmpf = lt | eq;", "3'd2: cmpf = lt;"),
 (RTL, 'EQ is NE', "3'd3: cmpf = eq;", "3'd3: cmpf = !eq;"),
 (RTL, 'NE is EQ', "3'd4: cmpf = !eq;", "3'd4: cmpf = eq;"),
 (RTL, 'GE is GT', "3'd5: cmpf = !lt;", "3'd5: cmpf = !(lt | eq);"),
 (RTL, 'GT is GE', "3'd6: cmpf = !(lt | eq);", "3'd6: cmpf = !lt;"),
 (RTL, 'NEVER is always true', "default: cmpf = 1'b0;", "default: cmpf = 1'b1;"),
 (RTL, 'a rule needs no enable', 's3_m[r] <= r_en[r] && ((pre[r] && cmpf(r_pxop', 's3_m[r] <= ((pre[r] && cmpf(r_pxop'),
 (RTL, 'negation is ignored', '&& cmpf(r_shop[r], s2_sh < r_shval[r], s2_sh == r_shval[r])) != r_neg[r]);', "&& cmpf(r_shop[r], s2_sh < r_shval[r], s2_sh == r_shval[r])) != 1'b0);"),
 (RTL, 'the price is compared signed', 'cmpf(r_pxop[r], s2_px < r_pxval[r],', 'cmpf(r_pxop[r], $signed(s2_px) < $signed(r_pxval[r]),'),
 (RTL, 'the shares are compared signed', 'cmpf(r_shop[r], s2_sh < r_shval[r],', 'cmpf(r_shop[r], $signed(s2_sh) < $signed(r_shval[r]),'),
 (RTL, 'the shares are compared with the price value', 'cmpf(r_shop[r], s2_sh < r_shval[r], s2_sh == r_shval[r])', 'cmpf(r_shop[r], s2_sh < r_pxval[r], s2_sh == r_shval[r])'),
 (RTL, 'the price equality is on 31 bits', 's2_px == r_pxval[r])', 's2_px[30:0] == r_pxval[r][30:0])'),
 (RTL, 'the low halves are compared with LE (price, two stages)', 'p_llt[r] <= s2_px[15:0] < r_pxval[r][15:0];', 'p_llt[r] <= s2_px[15:0] <= r_pxval[r][15:0];'),
 (RTL, 'the high halves are compared on 15 bits (price, two stages)', 'p_hlt[r] <= s2_px[31:16] < r_pxval[r][31:16];', 'p_hlt[r] <= s2_px[30:16] < r_pxval[r][30:16];'),
 (RTL, 'the halves are not combined (price, two stages)', 'p_hlt[r] | (p_heq[r] & p_llt[r])', 'p_hlt[r] | p_llt[r]'),
 (RTL, 'equality needs only the low halves (price, two stages)', 'p_heq[r] & p_leq[r]', 'p_leq[r]'),
 (RTL, 'equality needs only the high halves (price, two stages)', 'p_heq[r] & p_leq[r]', 'p_heq[r]'),
 (RTL, 'the halves are not combined (shares, two stages)', 'q_hlt[r] | (q_heq[r] & q_llt[r])', 'q_hlt[r] | q_llt[r]'),
 (RTL, 'equality needs only the low halves (shares, two stages)', 'q_heq[r] & q_leq[r]', 'q_leq[r]'),
 (RTL, 'the low halves of the shares are not compared (two stages)', 'q_leq[r] <= s2_sh[15:0] == r_shval[r][15:0];', "q_leq[r] <= 1'b1;"),
 (RTL, 'the price op is taken from the shares op (two stages)', 'a_pxop[r] <= r_pxop[r];', 'a_pxop[r] <= r_shop[r];'),
 (RTL, 'the shares op is taken from the price op (two stages)', 'a_shop[r] <= r_shop[r];', 'a_shop[r] <= r_pxop[r];'),
 (RTL, "the rule's enable is lost between the stages (two stages)", 'a_en[r] <= r_en[r];', "a_en[r] <= 1'b1;"),
 (RTL, 'the negation is lost between the stages (two stages)', 'a_neg[r] <= r_neg[r];', "a_neg[r] <= 1'b0;"),
 (RTL, 'the symbol and type part is lost between the stages (two stages)', 'a_pre[r] <= pre[r];', "a_pre[r] <= 1'b1;"),
 (RTL, 'fire is the first rule only', 'o_fire <= |s3_m;', 'o_fire <= s3_m[0];'),
 (RTL, 'first is the highest matching rule', "for (int r = R - 1; r >= 0; r--) if (s3_m[r]) o_first <= 4'(r);", "for (int r = 0; r < R; r++) if (s3_m[r]) o_first <= 4'(r);"),
 (RTL, 'the last stage is not reset (one comparison stage)', 's3_v <= s2_v && !rst;', 's3_v <= s2_v;'),
 (RTL, 'the last stage is not reset (two comparison stages)', 's3_v <= a_v && !rst;', 's3_v <= a_v;'),
 (MOD, 'model: the hash ignores byte 1', 'return (key ^ (key >> 8) ^ (key >> 16) ^ (key >> 24)) & (nb - 1)', 'return (key ^ (key >> 16) ^ (key >> 24)) & (nb - 1)'),
 (MOD, 'model: the hash ignores byte 3', 'return (key ^ (key >> 8) ^ (key >> 16) ^ (key >> 24)) & (nb - 1)', 'return (key ^ (key >> 8) ^ (key >> 16)) & (nb - 1)'),
 (MOD, 'model: LT is LE', '[True, x < c, x <= c', '[True, x <= c, x <= c'),
 (MOD, 'model: GE is GT', 'x >= c, x > c, False]', 'x > c, x > c, False]'),
 (MOD, 'model: NE is EQ', 'x == c, x != c,', 'x == c, x == c,'),
 (MOD, 'model: NEVER is true', 'x > c, False][op]', 'x > c, True][op]'),
 (MOD, 'model: a duplicate key can be placed', 'if any(self.e[b * self.k + w] is not None and self.e[b * self.k + w][0] == key for w in range(self.k)): return None', 'if False: return None'),
 (MOD, 'model: a full bucket is not refused', 'return b * self.k + w\n        return None', 'return b * self.k + w\n        return b * self.k'),
 (MOD, 'model: a table lookup returns the wrong index', 'if x is not None and x[0] == key: return 1, x[1]', 'if x is not None and x[0] == key: return 1, x[1] + 1'),
 (MOD, 'model: an unknown key matches a symbol mask', '(u["symany"] or (found and (u["symmask"] >> idx) & 1))', '(u["symany"] or ((u["symmask"] >> idx) & 1))'),
 (MOD, 'model: a negated rule ignores the enable', 'if u["en"] and (inner != bool(u["neg"])): mask |= 1 << r', 'if (u["en"] or u["neg"]) and (inner != bool(u["neg"])): mask |= 1 << r'),
 (MOD, 'model: first is the highest rule', 'first = (mask & -mask).bit_length() - 1 if mask else 0', 'first = mask.bit_length() - 1 if mask else 0'),
 (MOD, 'model: a message sees a table write of its own cycle', 'if "msg" in cy: f, i = T.lookup(cy["msg"]["key"]); look[c] = (f, i, cy["msg"])           # the table as of the start of cycle a: the writes of cycles before a\n        if "cfg" in cy', 'if "ld" in cy: a, v, key, i = cy["ld"]; T.write(a, v, key, i)\n        if "msg" in cy: f, i = T.lookup(cy["msg"]["key"]); look[c] = (f, i, cy["msg"])           # the table as of the start of cycle a: the writes of cycles before a\n        if "cfg" in cy'),
 (MOD, 'model: the rules are read in cycle a + 1', 'if c - 2 in look:', 'if c - 1 in look:'),
 (MOD, 'model: the rules are read in cycle a + 3', 'if c - 2 in look:', 'if c - 3 in look:'),
 (MOD, 'model: the answer comes one cycle early', 'L = 4 + pipe;', 'L = 3 + pipe;'),
 (MOD, 'model: two stages do not add a cycle', 'L = 4 + pipe;', 'L = 4;'),
 (MOD, 'model: ready one cycle early', '(c, 1 if c >= nb else 0)', '(c, 1 if c >= nb - 1 else 0)'),
 (MOD, 'model: an answer without a match has a first rule', 'first = (mask & -mask).bit_length() - 1 if mask else 0', 'first = (mask & -mask).bit_length() - 1 if mask else 1'),
 (MOD, 'model: the side test is ignored', '(u["sideany"] or msg["side"] == u["side"])', '(True)'),
 (MOD, 'model: the type test is ignored', 'bool((u["tmask"] >> msg["t"]) & 1) and', 'True and'),
]
def one(j):
    f, label, old, new = j
    d = tempfile.mkdtemp(prefix="mut21_")
    for sub in ("rtl", "tb", "out", "model", "tools"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub), ignore=shutil.ignore_patterns("*.json", "*_synth.log", "*.hex", "__pycache__", "ex*_*", "t1[0-9]_*"))
    p = os.path.join(d, f); s = open(p).read()
    if old not in s: shutil.rmtree(d, ignore_errors=True); return label, "BAD ANCHOR (0 occurrences)"
    i = s.index(old); open(p, "w").write(s[:i] + new + s[i + len(old):])
    try: q = subprocess.run([sys.executable, "tools/ch21_run.py", "--battery" if f == RTL else "--battery-model"], cwd=d, capture_output=True, text=True, timeout=900); out = q.stdout.strip().splitlines()[-1] if q.stdout.strip() else "RESULT crash: " + (q.stderr.strip().splitlines() or ["?"])[-1][:70]
    except subprocess.TimeoutExpired: out = "RESULT hang (timeout)"
    shutil.rmtree(d, ignore_errors=True); r = out.replace("RESULT ", "")
    return label, ("NOT CAUGHT" if r == "None" else "caught by: " + r[:110])
if __name__ == "__main__":
    print("NOTE: this script deliberately breaks copies of the RTL and of the model. 'caught' lines are EXPECTED: they show the battery notices the mistake.")
    q1 = subprocess.run([sys.executable, "tools/ch21_run.py", "--battery"], cwd=flow.ROOT, capture_output=True, text=True); q2 = subprocess.run([sys.executable, "tools/ch21_run.py", "--battery-model"], cwd=flow.ROOT, capture_output=True, text=True)
    base = q1.stdout.strip().endswith("None") and q2.stdout.strip().endswith("None"); print("unmutated design and model pass their batteries:", base)
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(one, MUT))
    cnt = {RTL: [0, 0], MOD: [0, 0]}
    for (f, *_), (label, st) in zip(MUT, res): print(f"  {label}: {st}"); cnt[f][1] += 1; cnt[f][0] += st.startswith("caught")
    for f, (c, n) in cnt.items(): print(f"  {f}: caught {c} of {n}")
    print(f"mutants caught: {sum(c for c, n in cnt.values())} of {len(MUT)}")
