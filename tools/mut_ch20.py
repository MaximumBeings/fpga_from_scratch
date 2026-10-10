#!/usr/bin/env python3
"""Chapter 20: test the tests. Two families. (1) mutants of rtl/book2.sv, battery `ch20_run.py --battery`: the engine against the cycle model, results, top of book and readiness (that is, the TIME of every event) in every cycle, five sizes, on flow with faults, random events, references that use all 32 bits, and references one bit apart. (2) mutants of model/book2_gold.py, battery `--battery-model`: the model's own hand-checked scenarios (the model is the oracle; what checks IT is a handful of cases worked by hand, so this family measures how complete they are)."""
import concurrent.futures as cf, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flow
RTL = "rtl/book2.sv"; MOD = "model/book2_gold.py"
MUT = [
 (RTL, 'the hash ignores byte 2', 'in_ref ^ (in_ref >> 8) ^ (in_ref >> 16) ^ (in_ref >> 24)', 'in_ref ^ (in_ref >> 8) ^ (in_ref >> 24)'),
 (RTL, 'the hash ignores byte 3', 'in_ref ^ (in_ref >> 8) ^ (in_ref >> 16) ^ (in_ref >> 24)', 'in_ref ^ (in_ref >> 8) ^ (in_ref >> 16)'),
 (RTL, "the hash of a replace's new reference ignores byte 1", 'r_ref2 ^ (r_ref2 >> 8) ^ (r_ref2 >> 16)', 'r_ref2 ^ (r_ref2 >> 16)'),
 (RTL, "the hash of a replace's new reference ignores byte 3", '^ (r_ref2 >> 24)', '^ (r_ref2 >> 24) ^ (r_ref2 >> 24)'),
 (RTL, 'the bucket starts at the wrong way', "OA'(hx_in) * OA'(K)", "OA'(hx_in) * OA'(K - 1)"),
 (RTL, 'the clearing sweep stops one entry early', "if (ini == OA'(NOW - 1)) st <= S_IDLE;", "if (ini == OA'(NOW - 2)) st <= S_IDLE;"),
 (RTL, 'the clearing sweep writes nothing', "if (st == S_INIT) begin om_we = 1'b1; om_wa = ini; end", "if (st == S_INIT) begin om_we = 1'b0; om_wa = ini; end"),
 (RTL, 'reset does not clear the order count', "st <= S_INIT; ini <= '0; nord <= '0;", "st <= S_INIT; ini <= '0;"),
 (RTL, 'reset does not clear the level counts', "for (i = 0; i < NL; i++) cnt[i] <= '0;", 'for (i = 0; i < NL; i++) ;'),
 (RTL, 'the lookup reads one way too few', "if (lk_i == KW'(K)) st <= S_DEC;", "if (lk_i == KW'(K - 1)) st <= S_DEC;"),
 (RTL, 'an empty entry matches a reference', "if (w_v && w_ref == r_ref) begin fv <= 1'b1;", "if (w_ref == r_ref) begin fv <= 1'b1;"),
 (RTL, 'only 16 bits of the reference are compared', "if (w_v && w_ref == r_ref) begin fv <= 1'b1;", "if (w_v && w_ref[15:0] == r_ref[15:0]) begin fv <= 1'b1;"),
 (RTL, 'only 31 bits of the reference are compared', "if (w_v && w_ref == r_ref) begin fv <= 1'b1;", "if (w_v && w_ref[30:0] == r_ref[30:0]) begin fv <= 1'b1;"),
 (RTL, "the found order's side is not remembered", 'f_side <= w_side;', 'f_side <= f_side;'),
 (RTL, "the found order's price is not remembered", 'f_px <= w_px;', 'f_px <= f_sh;'),
 (RTL, 'the found way is off by one', "fw <= lk_i - 1'b1;", 'fw <= lk_i;'),
 (RTL, 'the free way is off by one', "ff <= lk_i - 1'b1;", 'ff <= lk_i;'),
 (RTL, 'the free flag is not cleared for a new event', "else begin st <= S_LK; lk_i <= '0; fv <= 1'b0; fvv <= 1'b0; bkt <= hb_in; end", "else begin st <= S_LK; lk_i <= '0; fv <= 1'b0; bkt <= hb_in; end"),
 (RTL, 'the found flag is not cleared for a new event', "else begin st <= S_LK; lk_i <= '0; fv <= 1'b0; fvv <= 1'b0; bkt <= hb_in; end", "else begin st <= S_LK; lk_i <= '0; fvv <= 1'b0; bkt <= hb_in; end"),
 (RTL, 'the found flag is not cleared for the new order of a replace', "else begin st <= S_LK; lk_i <= '0; fv <= 1'b0; fvv <= 1'b0; bkt <= hb_2; end", "else begin st <= S_LK; lk_i <= '0; fvv <= 1'b0; bkt <= hb_2; end"),
 (RTL, 'the new order of a replace is looked up in the old bucket', 'bkt <= hb_2;', 'bkt <= bkt;'),
 (RTL, 'zero shares are refused for every type before the lookup', "if (in_type == 3'(0) && in_sh == 32'd0) begin", "if (in_sh == 32'd0) begin"),
 (RTL, 'a duplicate is not noticed', "if (fv) begin res_v <= 1'b1; res <= 3'd5;", "if (1'b0) begin res_v <= 1'b1; res <= 3'd5;"),
 (RTL, 'a full bucket is not noticed', "else if (!fvv) begin res_v <= 1'b1; res <= 3'd2;", "else if (1'b0) begin res_v <= 1'b1; res <= 3'd2;"),
 (RTL, 'DUPREF is reported as FULL', "res <= 3'd5;", "res <= 3'd2;"),
 (RTL, "an unknown reference is reported with the input's symbol", "res <= 3'd1; res_sym <= '0;", "res <= 3'd1; res_sym <= r_sym;"),
 (RTL, 'a reduction by zero is accepted', "else if (is_red && r_sh == 32'd0) begin", "else if (1'b0) begin"),
 (RTL, 'an over-reduction is accepted', 'else if (is_red && r_sh > f_sh) begin', "else if (1'b0) begin"),
 (RTL, 'a reduction by the whole order is an over-reduction', 'else if (is_red && r_sh > f_sh) begin', 'else if (is_red && r_sh >= f_sh) begin'),
 (RTL, "a delete reduces by the input's shares", 'tk <= is_red ? r_sh : f_sh;', 'tk <= r_sh;'),
 (RTL, 'the level search starts at index 1', "fst <= 1'b1; fi <= '0;", "fst <= 1'b1; fi <= 1'b1;"),
 (RTL, 'the level read is one ahead', "lm_ra = lbase + (fst ? '0 : LA'(fi) + 1'b1);", "lm_ra = lbase + (fst ? '0 : LA'(fi));"),
 (RTL, 'an equal price is not a hit', 'end else if (l_px == tgt) begin', "end else if (l_px == tgt && 1'b0) begin"),
 (RTL, 'a price at or above the level is a hit', 'end else if (l_px == tgt) begin', 'end else if (l_px <= tgt) begin'),
 (RTL, 'the better price is judged on the wrong side', 'wire l_better = r_side ? (r_px < l_px) : (r_px > l_px);', 'wire l_better = r_side ? (r_px > l_px) : (r_px < l_px);'),
 (RTL, 'an add to an existing level replaces its shares', 'wsh <= l_sh + r_sh;', 'wsh <= r_sh;'),
 (RTL, 'a reduction subtracts one from the level', 'wsh <= l_sh - tk;', "wsh <= l_sh - 32'd1;"),
 (RTL, 'the side is not full when D levels are in use (insert at the end)', "p <= fi;\n                    if (cnt_l == DW'(D)) begin res_v <= 1'b1; res <= 3'd3; res_sym <= r_sym; st <= S_IDLE; end\n                    else begin srem <= '0;", "p <= fi;\n                    if (1'b0) begin res_v <= 1'b1; res <= 3'd3; res_sym <= r_sym; st <= S_IDLE; end\n                    else begin srem <= '0;"),
 (RTL, 'the side is not full when D levels are in use (insert before)', "p <= fi;\n                    if (cnt_l == DW'(D)) begin res_v <= 1'b1; res <= 3'd3; res_sym <= r_sym; st <= S_IDLE; end\n                    else begin srem <= cnt_l - fi;", "p <= fi;\n                    if (1'b0) begin res_v <= 1'b1; res <= 3'd3; res_sym <= r_sym; st <= S_IDLE; end\n                    else begin srem <= cnt_l - fi;"),
 (RTL, 'a side is full one level early', 'else begin srem <= cnt_l - fi; sj', "else if (cnt_l == DW'(D - 1)) begin res_v <= 1'b1; res <= 3'd3; res_sym <= r_sym; st <= S_IDLE; end else begin srem <= cnt_l - fi; sj"),
 (RTL, 'the shift down moves one level too few', "srem <= cnt_l - fi; sj <= cnt_l - 1'b1;", "srem <= cnt_l - fi - 1'b1; sj <= cnt_l - 1'b1;"),
 (RTL, 'the shift down starts at the wrong level', "sj <= cnt_l - 1'b1; sw <= 1'b0; st <= (cnt_l > fi)", "sj <= cnt_l; sw <= 1'b0; st <= (cnt_l > fi)"),
 (RTL, 'the shift down writes to the same index', "sdst <= sj + 1'b1; sj <= sj - 1'b1;", "sdst <= sj; sj <= sj - 1'b1;"),
 (RTL, 'the shift down is skipped', 'st <= (cnt_l > fi) ? S_SHD : S_WINS;', 'st <= S_WINS;'),
 (RTL, 'the shift up moves one level too many', "srem <= cnt_l - 1'b1 - fi; sj <= fi + 1'b1;", "srem <= cnt_l - fi; sj <= fi + 1'b1;"),
 (RTL, 'the shift up starts at the removed level', "srem <= cnt_l - 1'b1 - fi; sj <= fi + 1'b1;", "srem <= cnt_l - 1'b1 - fi; sj <= fi;"),
 (RTL, 'the shift up writes to the same index', "sdst <= sj - 1'b1; sj <= sj + 1'b1;", "sdst <= sj; sj <= sj + 1'b1;"),
 (RTL, 'the shift up is always entered', "st <= (cnt_l - 1'b1 - fi > 0) ? S_SHU : S_WOM;", 'st <= S_SHU;'),
 (RTL, 'the shift up does not refresh the best level', 'if (sw && sdst == 0) begin tpx[lidx] <= l_px; tsh[lidx] <= l_sh; end', 'if (sw && sdst == 0) begin end'),
 (RTL, 'the shift up refreshes the best level from the wrong index', 'if (sw && sdst == 0) begin tpx[lidx] <= l_px;', 'if (sw && sdst == 1) begin tpx[lidx] <= l_px;'),
 (RTL, "an addition to a level always changes the best level's shares", 'S_WLV: begin if (p == 0) tsh[lidx] <= wsh;', 'S_WLV: begin tsh[lidx] <= wsh;'),
 (RTL, 'an addition to the best level does not change its shares', 'S_WLV: begin if (p == 0) tsh[lidx] <= wsh;', 'S_WLV: begin'),
 (RTL, 'an inserted level always becomes the best', "cnt[lidx] <= cnt_l + 1'b1; if (p == 0) begin tpx[lidx] <= r_px; tsh[lidx] <= r_sh; end", "cnt[lidx] <= cnt_l + 1'b1; begin tpx[lidx] <= r_px; tsh[lidx] <= r_sh; end"),
 (RTL, 'an inserted best level is not recorded', "cnt[lidx] <= cnt_l + 1'b1; if (p == 0) begin tpx[lidx] <= r_px; tsh[lidx] <= r_sh; end", "cnt[lidx] <= cnt_l + 1'b1;"),
 (RTL, 'the level count goes up by two', "cnt[lidx] <= cnt_l + 1'b1; if (p == 0)", "cnt[lidx] <= cnt_l + 2'd2; if (p == 0)"),
 (RTL, 'the level count does not go down after a removal', "cnt[lidx] <= cnt_l - 1'b1; srem", 'srem'),
 (RTL, 'the order count does not go up', "nord <= nord + 1'b1;", 'nord <= nord;'),
 (RTL, 'the order count goes down for a partial reduction', "if (tk == f_sh) nord <= nord - 1'b1;", "nord <= nord - 1'b1;"),
 (RTL, 'the order count does not go down', "if (tk == f_sh) nord <= nord - 1'b1;", ''),
 (RTL, 'a new order goes to the wrong way', "om_wa = bkt + OA'(ff);", "om_wa = bkt + OA'(fw);"),
 (RTL, 'a reduced order is written to the wrong way', "om_wa = bkt + OA'(fw);", "om_wa = bkt + OA'(ff);"),
 (RTL, 'a reduced order keeps its shares', "om_wd = {1'b1, r_ref, f_sym, f_side, f_px, f_sh - tk};", "om_wd = {1'b1, r_ref, f_sym, f_side, f_px, f_sh};"),
 (RTL, 'a reduced order gets the reduction as its shares', "om_wd = {1'b1, r_ref, f_sym, f_side, f_px, f_sh - tk};", "om_wd = {1'b1, r_ref, f_sym, f_side, f_px, tk};"),
 (RTL, 'a fully reduced order is not freed', "if (tk == f_sh) om_wd = '0; else", "if (1'b0) om_wd = '0; else"),
 (RTL, 'a new order stores the wrong side', "om_wd = {1'b1, r_ref, r_sym, r_side, r_px, r_sh};", "om_wd = {1'b1, r_ref, r_sym, 1'b0, r_px, r_sh};"),
 (RTL, 'a new order stores the wrong price', "om_wd = {1'b1, r_ref, r_sym, r_side, r_px, r_sh};", "om_wd = {1'b1, r_ref, r_sym, r_side, r_sh, r_sh};"),
 (RTL, "the level index of a reduction uses the input's symbol", 'else lidx = {f_sym, f_side};', 'else lidx = {r_sym, f_side};'),
 (RTL, "the level index of a reduction uses the input's side", 'else lidx = {f_sym, f_side};', 'else lidx = {f_sym, r_side};'),
 (RTL, 'the level base is off', "lbase = LA'(lidx) * LA'(D);", "lbase = LA'(lidx) * LA'(D) + LA'(lidx);"),
 (RTL, 'a replace keeps the old reference for the new order', "r_t <= 3'(0); r_ref <= r_ref2;", "r_t <= 3'(0);"),
 (RTL, "a replace adds at the input's symbol", 'r_sym <= f_sym; r_side <= f_side;\n', 'r_side <= f_side;\n'),
 (RTL, "a replace adds at the input's side", 'r_sym <= f_sym; r_side <= f_side;\n', 'r_sym <= f_sym;\n'),
 (RTL, "a replace with zero new shares reports the input's symbol", "begin res_v <= 1'b1; res <= 3'd6; res_sym <= f_sym; st <= S_IDLE; end\n                        else", "begin res_v <= 1'b1; res <= 3'd6; res_sym <= r_sym; st <= S_IDLE; end\n                        else"),
 (RTL, 'a replace does not become an add', "r_t <= 3'(0); r_ref <= r_ref2;", 'r_ref <= r_ref2;'),
 (RTL, "a delete reports the input's symbol", "end else begin res_v <= 1'b1; res <= 3'd0; res_sym <= f_sym; st <= S_IDLE; end", "end else begin res_v <= 1'b1; res <= 3'd0; res_sym <= r_sym; st <= S_IDLE; end"),
 (RTL, 'the engine is ready while it writes the order', 'assign in_ready = (st == S_IDLE);', 'assign in_ready = (st == S_IDLE) || (st == S_WOM);'),
 (RTL, 'the best bid is shown when the side is empty', "o_bpx = (cnt[{o_sym, 1'b0}] != 0) ? tpx[{o_sym, 1'b0}] : 32'd0;", "o_bpx = tpx[{o_sym, 1'b0}];"),
 (RTL, "the best ask's shares are shown when the side is empty", "o_ash = (cnt[{o_sym, 1'b1}] != 0) ? tsh[{o_sym, 1'b1}] : 32'd0;", "o_ash = tsh[{o_sym, 1'b1}];"),
 (RTL, "the ask level count is the bid's", "o_an = 8'(cnt[{o_sym, 1'b1}]);", "o_an = 8'(cnt[{o_sym, 1'b0}]);"),
 (MOD, 'model: the lookup costs one cycle less', 'lk = self.k + 2', 'lk = self.k + 1'),
 (MOD, 'model: the level search costs one cycle less', 'c = p + 2\n        L[px]', 'c = p + 1\n        L[px]'),
 (MOD, 'model: the bucket is full one order early', 'for r in self.orders if h(r, self.nb) == h(ref, self.nb)) >= self.k', 'for r in self.orders if h(r, self.nb) == h(ref, self.nb)) >= self.k - 1'),
 (MOD, 'model: the bucket is never full', 'for r in self.orders if h(r, self.nb) == h(ref, self.nb)) >= self.k', 'for r in self.orders if h(r, self.nb) == h(ref, self.nb)) >= self.k + 100'),
 (MOD, 'model: the hash ignores byte 1', '(ref ^ (ref >> 8) ^ (ref >> 16) ^ (ref >> 24))', '(ref ^ (ref >> 16) ^ (ref >> 24))'),
 (MOD, 'model: zero shares on an add cost the lookup', 'if sh == 0: return ZERO, 0', 'if sh == 0: return ZERO, 1'),
 (MOD, 'model: a duplicate is found after the table is full', 'if ref in self.orders: return DUPREF, c\n        if self._bucket_full(ref): return FULL, c', 'if self._bucket_full(ref): return FULL, c\n        if ref in self.orders: return DUPREF, c'),
 (MOD, 'model: a hit costs one cycle more', 'if px in L: c += 2', 'if px in L: c += 3'),
 (MOD, 'model: an insertion shifts one level too few', 'c += (n - p + 1 if n > p else 0) + 2', 'c += (n - p if n > p else 0) + 2'),
 (MOD, 'model: an insertion at the end shifts', 'c += (n - p + 1 if n > p else 0) + 2', 'c += (n - p + 1) + 2'),
 (MOD, 'model: a removal shifts one level too many', 'c += (n - 1 - p + 1 if n - 1 - p > 0 else 0) + 1', 'c += (n - 1 - p + 2 if n - 1 - p > 0 else 0) + 1'),
 (MOD, 'model: a removal of the last level shifts', 'c += (n - 1 - p + 1 if n - 1 - p > 0 else 0) + 1', 'c += (n - 1 - p + 1) + 1'),
 (MOD, 'model: a partial reduction costs one cycle less', 'else: c += 2\n        if sh == osh', 'else: c += 1\n        if sh == osh'),
 (MOD, 'model: a refused add (LVL) costs the whole insertion', 'if len(L) >= self.d: return LVL, c', 'if len(L) >= self.d: return LVL, c + 2'),
 (MOD, 'model: an emptied level stays', 'if L[px] == 0: del L[px]; c +=', 'if False: del L[px]; c +='),
 (MOD, 'model: a replace keeps the old order on failure', 'c = lk + self._take(ref, osh)\n        if t == DELETE', 'c = lk\n        if t == DELETE'),
 (MOD, 'model: an unknown reference is reported with symbol 1', 'if ref not in self.orders: return 1 + lk, UNK, 0', 'if ref not in self.orders: return 1 + lk, UNK, 1'),
 (MOD, 'model: the order count in the top of book is off', 'len(self.orders))\n    def pos', 'len(self.orders) + 1)\n    def pos'),
 (MOD, 'model: the clearing sweep takes one cycle too few', 'busy_until = nb * k;', 'busy_until = nb * k - 1;'),
 (MOD, "model: the bucket's capacity is checked on the symbol", 'return sum(1 for r in self.orders if h(r, self.nb) == h(ref, self.nb)) >= self.k', 'return sum(1 for r in self.orders if h(r, self.nb) == h(ref, self.nb) and self.orders[r][0] == 0) >= self.k'),
]
def one(j):
    f, label, old, new = j
    d = tempfile.mkdtemp(prefix="mut20_")
    for sub in ("rtl", "tb", "out", "model", "tools"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub), ignore=shutil.ignore_patterns("*.json", "*_synth.log", "*.hex", "__pycache__", "ex*_*", "t1[0-9]_*"))
    p = os.path.join(d, f); s = open(p).read()
    if old not in s: shutil.rmtree(d, ignore_errors=True); return label, "BAD ANCHOR (0 occurrences)"
    i = s.index(old); open(p, "w").write(s[:i] + new + s[i + len(old):])
    try: q = subprocess.run([sys.executable, "tools/ch20_run.py", "--battery" if f == RTL else "--battery-model"], cwd=d, capture_output=True, text=True, timeout=900); out = q.stdout.strip().splitlines()[-1] if q.stdout.strip() else "RESULT crash: " + (q.stderr.strip().splitlines() or ["?"])[-1][:70]
    except subprocess.TimeoutExpired: out = "RESULT hang (timeout)"
    shutil.rmtree(d, ignore_errors=True); r = out.replace("RESULT ", "")
    return label, ("NOT CAUGHT" if r == "None" else "caught by: " + r[:110])
if __name__ == "__main__":
    print("NOTE: this script deliberately breaks copies of the RTL and of the model. 'caught' lines are EXPECTED: they show the battery notices the mistake.")
    q1 = subprocess.run([sys.executable, "tools/ch20_run.py", "--battery"], cwd=flow.ROOT, capture_output=True, text=True); q2 = subprocess.run([sys.executable, "tools/ch20_run.py", "--battery-model"], cwd=flow.ROOT, capture_output=True, text=True)
    base = q1.stdout.strip().endswith("None") and q2.stdout.strip().endswith("None"); print("unmutated design and model pass their batteries:", base)
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(one, MUT))
    cnt = {RTL: [0, 0], MOD: [0, 0]}
    for (f, *_), (label, st) in zip(MUT, res): print(f"  {label}: {st}"); cnt[f][1] += 1; cnt[f][0] += st.startswith("caught")
    for f, (c, n) in cnt.items(): print(f"  {f}: caught {c} of {n}")
    print(f"mutants caught: {sum(c for c, n in cnt.values())} of {len(MUT)}")
