#!/usr/bin/env python3
"""Chapter 19: test the tests. Two families. (1) mutants of rtl/book.sv, battery `ch19_run.py --battery`: the book against the cycle model, results, top of book and readiness in every cycle, five sizes, flow with faults and random events. (2) mutants of model/book_gold.py, battery `--battery-model`: the model's own hand-checked scenarios (the model is the oracle; what checks IT is a handful of cases worked by hand, so this family measures how complete they are)."""
import concurrent.futures as cf, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flow
RTL = "rtl/book.sv"; MOD = "model/book_gold.py"
MUT = [
 (RTL, "the level search counts the wrong side as better", "if (lop_li[0] ? (lpx[lop_li][i] < lop_px) : (lpx[lop_li][i] > lop_px)) p = p + 1'b1;", "if (lop_li[0] ? (lpx[lop_li][i] > lop_px) : (lpx[lop_li][i] < lop_px)) p = p + 1'b1;"),
 (RTL, "an equal price counts as better", "if (lop_li[0] ? (lpx[lop_li][i] < lop_px) : (lpx[lop_li][i] > lop_px)) p = p + 1'b1;", "if (lop_li[0] ? (lpx[lop_li][i] <= lop_px) : (lpx[lop_li][i] >= lop_px)) p = p + 1'b1;"),
 (RTL, "a level is a hit whatever its price", "&& lpx[lop_li][i] == lop_px) begin hit = 1'b1;", ") begin hit = 1'b1;"),
 (RTL, "a side is full one level early", "lfull = !hit && (cnt == DW'(D));", "lfull = !hit && (cnt >= DW'(D - 1));"),
 (RTL, "a side is never full", "lfull = !hit && (cnt == DW'(D));", "lfull = 1'b0;"),
 (RTL, "a duplicate is checked before zero shares", "if (a_sh == 32'd0) res = 3'd6; else if (dup) res = 3'd5;", "if (dup) res = 3'd5; else if (a_sh == 32'd0) res = 3'd6;"),
 (RTL, "a full order table is not noticed", "else if (!free_any) res = 3'd2;", "else if (1'b0) res = 3'd2;"),
 (RTL, "full levels are checked before the order table", "else if (!free_any) res = 3'd2; else if (lfull) res = 3'd3;", "else if (lfull) res = 3'd3; else if (!free_any) res = 3'd2;"),
 (RTL, "a duplicate reference is not noticed", "if (ov[i] && oref[i] == a_ref) dup = 1'b1;", ""),
 (RTL, "the duplicate check of an add after a replace uses the old reference", "if (ov[i] && oref[i] == a_ref) dup = 1'b1;", "if (ov[i] && oref[i] == in_ref) dup = 1'b1;"),
 (RTL, "a reduction by the whole order is an over-reduction", "else if (is_red && in_sh > f_sh) res = 3'd4;", "else if (is_red && in_sh >= f_sh) res = 3'd4;"),
 (RTL, "a reduction by zero is accepted", "else if (is_red && in_sh == 32'd0) res = 3'd6;", ""),
 (RTL, "an over-reduction is accepted", "else if (is_red && in_sh > f_sh) res = 3'd4;", ""),
 (RTL, "a replace reduces by the new shares", "tk = (is_del || is_rep) ? f_sh : in_sh;", "tk = is_del ? f_sh : in_sh;"),
 (RTL, "a full reduction does not free the order", "if (tk == f_sh) ord_free = 1'b1; else ord_red = 1'b1;", "ord_red = 1'b1;"),
 (RTL, "a level whose shares reach 1 is removed", "remove_lv = ((hit_sh - tk) == 32'd0); if (tk == f_sh)", "remove_lv = ((hit_sh - tk) == 32'd1); if (tk == f_sh)"),
 (RTL, "an emptied level is not removed after a delete", "else begin res = 3'd0; lop = 1'b1; remove_lv = ((hit_sh - tk) == 32'd0);", "else begin res = 3'd0; lop = 1'b1; remove_lv = 1'b0;"),
 (RTL, "a replace does not remove the old order", "begin rep_go = 1'b1; lop = 1'b1; remove_lv = ((hit_sh - tk) == 32'd0); ord_free = 1'b1; end", "begin rep_go = 1'b1; lop = 1'b1; remove_lv = ((hit_sh - tk) == 32'd0); end"),
 (RTL, "a replace adds the new order at the input's symbol", "b_sym <= f_sym; b_side <= f_side;", "b_sym <= in_sym; b_side <= f_side;"),
 (RTL, "a replace adds the new order at the input's side", "b_sym <= f_sym; b_side <= f_side;", "b_sym <= f_sym; b_side <= in_side;"),
 (RTL, "a replace gives the new order the old reference", "b_ref <= in_ref2;", "b_ref <= in_ref;"),
 (RTL, "a replace keeps the old price", "b_px <= in_px;", "b_px <= f_px;"),
 (RTL, "the second phase of a replace is not remembered", "if (busy) busy <= 1'b0;", ""),
 (RTL, "the engine is always ready", "in_ready = !busy;", "in_ready = 1'b1;"),
 (RTL, "an unknown reference is reported with the input's symbol", "rsym = found ? f_sym : '0;", "rsym = in_sym;"),
 (RTL, "adding to a level replaces its shares", "lsh[s][i] <= lsh[s][i] + lop_sh; end", "lsh[s][i] <= lop_sh; end"),
 (RTL, "the removal leaves the level in place", "if (DW'(i) >= p) begin", "if (DW'(i) > p) begin"),
 (RTL, "a reduction subtracts one", "lsh[s][i] <= lsh[s][i] - lop_sh; end", "lsh[s][i] <= lsh[s][i] - 32'd1; end"),
 (RTL, "the best bid is shown when the side is empty", "o_bpx = lv[{o_sym, 1'b0}][0] ? lpx[{o_sym, 1'b0}][0] : 32'd0;", "o_bpx = lpx[{o_sym, 1'b0}][0];"),
 (RTL, "the ask count is wrong", "if (lv[{o_sym, 1'b1}][i]) na = na + 8'd1;", "if (lv[{o_sym, 1'b1}][i]) na = na + 8'd2;"),
 (RTL, "the order count ignores one entry", "for (int i = 0; i < NO; i++) if (ov[i]) no_ = no_ + 8'd1;", "for (int i = 1; i < NO; i++) if (ov[i]) no_ = no_ + 8'd1;"),
 (RTL, "reset does not clear the order table", "for (int i = 0; i < NO; i++) ov[i] <= 1'b0;", ""),
 (RTL, "reset does not clear the levels", "for (int s = 0; s < NS * 2; s++) for (int i = 0; i < D; i++) lv[s][i] <= 1'b0;", ""),
 (RTL, "reset does not clear the second phase", "busy <= 1'b0; for (int i = 0; i < NO; i++)", "for (int i = 0; i < NO; i++)"),
 (RTL, "a reduction does not update the order", "if (ord_red) osh[f_idx] <= f_sh - tk;", ""),
 (RTL, "a reduction sets the shares to the reduction", "if (ord_red) osh[f_idx] <= f_sh - tk;", "if (ord_red) osh[f_idx] <= tk;"),
 (RTL, "an add stores the wrong side", "osd[free_idx] <= a_side;", "osd[free_idx] <= 1'b0;"),
 (RTL, "an add stores the wrong price", "opx[free_idx] <= a_px;", "opx[free_idx] <= a_sh;"),
 (RTL, "the symbol and the side are swapped in the level index", "lop_li = {a_sym, a_side};", "lop_li = {a_side, a_sym[0]};"),
 (RTL, "a reduction names the level by the input's side", "lop_li = {f_sym, f_side};", "lop_li = {f_sym, in_side};"),
 (RTL, "a delete is taken for a reduction", "is_del = accept && in_type == 3'd3;", "is_del = accept && in_type == 3'd9;"),
 (MOD, "model: a reduction by zero is accepted", "if sh == 0: return ZERO, sym", "if False: return ZERO, sym"),
 (MOD, "model: an over-reduction is accepted", "if sh > osh: return OVER, sym", "if False: return OVER, sym"),
 (MOD, "model: levels are checked before the table", "if len(self.orders) >= self.no: return FULL\n        L = self.lv[sym][side]\n        if px not in L and len(L) >= self.d: return LVL", "L = self.lv[sym][side]\n        if px not in L and len(L) >= self.d: return LVL\n        if len(self.orders) >= self.no: return FULL"),
 (MOD, "model: a duplicate is checked after the table", "if ref in self.orders: return DUPREF\n        if len(self.orders) >= self.no: return FULL", "if len(self.orders) >= self.no: return FULL\n        if ref in self.orders: return DUPREF"),
 (MOD, "model: an emptied level stays", "if L[px] == 0: del L[px]", "pass"),
 (MOD, "model: a replace takes one phase", "return 2, r, sym", "return 1, r, sym"),
 (MOD, "model: a replace keeps the old order on failure", "self._take(ref, osh); r = self._add(", "r = self._add("),
 (MOD, "model: an unknown reference is reported with symbol 1", "if ref not in self.orders: return 1, UNK, 0                                                                  # REPLACE", "if ref not in self.orders: return 1, UNK, 1                                                                  # REPLACE"),
 (MOD, "model: the table is counted wrongly in the top of book", "len(self.orders))", "len(self.orders) + 1)"),
]
def one(j):
    f, label, old, new = j
    d = tempfile.mkdtemp(prefix="mut19_")
    for sub in ("rtl", "tb", "out", "model", "tools"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub), ignore=shutil.ignore_patterns("*.json", "*_synth.log", "*.hex", "__pycache__", "ex*_*", "t1[0-9]_*"))
    p = os.path.join(d, f); s = open(p).read()
    if old not in s: shutil.rmtree(d, ignore_errors=True); return label, "BAD ANCHOR (0 occurrences)"
    i = s.index(old); open(p, "w").write(s[:i] + new + s[i + len(old):])
    try: q = subprocess.run([sys.executable, "tools/ch19_run.py", "--battery" if f == RTL else "--battery-model"], cwd=d, capture_output=True, text=True, timeout=900); out = q.stdout.strip().splitlines()[-1] if q.stdout.strip() else "RESULT crash: " + (q.stderr.strip().splitlines() or ["?"])[-1][:70]
    except subprocess.TimeoutExpired: out = "RESULT hang (timeout)"
    shutil.rmtree(d, ignore_errors=True); r = out.replace("RESULT ", "")
    return label, ("NOT CAUGHT" if r == "None" else "caught by: " + r[:110])
if __name__ == "__main__":
    print("NOTE: this script deliberately breaks copies of the RTL and of the model. 'caught' lines are EXPECTED: they show the battery notices the mistake.")
    q1 = subprocess.run([sys.executable, "tools/ch19_run.py", "--battery"], cwd=flow.ROOT, capture_output=True, text=True); q2 = subprocess.run([sys.executable, "tools/ch19_run.py", "--battery-model"], cwd=flow.ROOT, capture_output=True, text=True)
    base = q1.stdout.strip().endswith("None") and q2.stdout.strip().endswith("None"); print("unmutated design and model pass their batteries:", base)
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(one, MUT))
    cnt = {RTL: [0, 0], MOD: [0, 0]}
    for (f, *_), (label, st) in zip(MUT, res): print(f"  {label}: {st}"); cnt[f][1] += 1; cnt[f][0] += st.startswith("caught")
    for f, (c, n) in cnt.items(): print(f"  {f}: caught {c} of {n}")
    print(f"mutants caught: {sum(c for c, n in cnt.values())} of {len(MUT)}")
