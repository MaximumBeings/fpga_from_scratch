#!/usr/bin/env python3
"""Chapter 10: test the tests. Mutants of rtl/match.sv. The battery: the three CAM engines (8 and 16 slots) against the specification on several seeds; the hash engines with one and two tables (exact, and a 12-bit fingerprint) on random and stride keys; one-per-cycle queries. Usage: mut_ch10.py"""
import concurrent.futures as cf, os, random, re, shutil, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, hw, match_gold as g
M = "rtl/match.sv"; F = ["rtl/match.sv", "tb/match_tb.sv"]
MUTANTS = [
 ("cam: exact compares only the low 31 bits", "0: hv[i] = vld[i] && (k[i] == q_key);", "0: hv[i] = vld[i] && (k[i][30:0] == q_key[30:0]);"),
 ("cam: a deleted slot still matches", "0: hv[i] = vld[i] && (k[i] == q_key);", "0: hv[i] = (k[i] == q_key);"),
 ("cam: ternary treats mask bits as 'don't care' where set", "1: hv[i] = vld[i] && (((k[i] ^ q_key) & a[i]) == 32'd0);", "1: hv[i] = vld[i] && (((k[i] ^ q_key) & ~a[i]) == 32'd0);"),
 ("cam: ternary ignores the mask", "1: hv[i] = vld[i] && (((k[i] ^ q_key) & a[i]) == 32'd0);", "1: hv[i] = vld[i] && (k[i] == q_key);"),
 ("cam: ternary compares one bit less (bit 0 never compared)", "1: hv[i] = vld[i] && (((k[i] ^ q_key) & a[i]) == 32'd0);", "1: hv[i] = vld[i] && (((k[i] ^ q_key) & a[i] & 32'hFFFFFFFE) == 32'd0);"),
 ("cam: ternary does not need the key cleared outside the mask (it uses the key masked on one side only)", "1: hv[i] = vld[i] && (((k[i] ^ q_key) & a[i]) == 32'd0);", "1: hv[i] = vld[i] && ((k[i] & a[i]) == q_key);"),
 ("cam: the range's low end is exclusive", "(q_key[15:0] >= a[i][15:0])", "(q_key[15:0] > a[i][15:0])"),
 ("cam: the range's high end is exclusive", "(q_key[15:0] <= a[i][31:16])", "(q_key[15:0] < a[i][31:16])"),
 ("cam: the range uses 15 bits of the key", "(q_key[15:0] >= a[i][15:0]) && (q_key[15:0] <= a[i][31:16])", "(q_key[14:0] >= a[i][14:0]) && (q_key[14:0] <= a[i][30:16])"),
 ("cam: the range compares the whole key", "(q_key[15:0] >= a[i][15:0]) && (q_key[15:0] <= a[i][31:16])", "(q_key >= {16'd0, a[i][15:0]}) && (q_key <= {16'd0, a[i][31:16]})"),
 ("cam: the HIGHEST matching slot wins", "if (hv_r[i]) begin found = 1'b1; idx = IW'(i); end", "if (hv_r[N-1-i]) begin found = 1'b1; idx = IW'(N-1-i); end"),
 ("cam: the first matching slot above slot 0 wins (slot 0 never)", "for (int i = N - 1; i >= 0; i--)", "for (int i = N - 1; i >= 1; i--)"),
 ("cam: the value is taken from slot 0", "r_val <= found ? v[idx] : 8'd0;", "r_val <= found ? v[0] : 8'd0;"),
 ("cam: the value is not cleared on a miss", "r_val <= found ? v[idx] : 8'd0;", "r_val <= v[idx];"),
 ("cam: a write does not store the value", "v[w_addr[IW-1:0]] <= w_val; end", "end"),
 ("cam: a write does not store the mask or range", "a[w_addr[IW-1:0]] <= w_aux;", ""),
 ("cam: reset does not clear the valid bits", "if (rst) vld <= '0; else if (w_en)", "if (w_en)"),
 ("cam: a query during reset is answered", "qv_r <= q_valid && !rst;", "qv_r <= q_valid;"),
 ("cam: results are valid one cycle early (skip stage 2's register of qv)", "r_valid <= qv_r;", "r_valid <= q_valid;"),
 ("cam: the valid bit is written even when the write is not enabled", "else if (w_en) vld[w_addr[IW-1:0]] <= w_vld;", "else vld[w_addr[IW-1:0]] <= w_vld;"),
 ("cam: the valid bit is written as 1", "vld[w_addr[IW-1:0]] <= w_vld;", "vld[w_addr[IW-1:0]] <= 1'b1;"),
 ("hash: the first hash drops its top chunk", "for (int i = 0; i < 32; i += AW) s = s ^ AW'(x >> i);", "for (int i = 0; i < 24; i += AW) s = s ^ AW'(x >> i);"),
 ("hash: the second hash is rotated by 12", "assign h2 = fold({q_key[18:0], q_key[31:19]} ^ {5'd0, q_key[31:5]});", "assign h2 = fold({q_key[19:0], q_key[31:20]} ^ {5'd0, q_key[31:5]});"),
 ("hash: the second table is read with the first hash", "r1 <= m1[h2];", "r1 <= m1[h1];"),
 ("hash: the first table is written with table select inverted", "if (w_en && !w_sel) m0", "if (w_en && w_sel) m0"),
 ("hash: both tables are written on every write", "if (w_en && w_sel) m1[w_addr[AW-1:0]]", "if (w_en) m1[w_addr[AW-1:0]]"),
 ("hash: the valid bit is not stored (always 1 once written)", "<= {w_vld, w_key[KW-1:0], w_val};\n        r0", "<= {1'b1, w_key[KW-1:0], w_val};\n        r0"),
 ("hash: the key compare ignores the top stored bit", "(r0[EW-2:8] == qk[KW-1:0])", "(r0[EW-3:8] == qk[KW-2:0])"),
 ("hash: table 1 hit is ignored", "assign hit1 = (CH == 2) && r1[EW-1] && (r1[EW-2:8] == qk[KW-1:0]);", "assign hit1 = 1'b0;"),
 ("hash: table 0 hit is ignored", "assign hit0 = r0[EW-1] && (r0[EW-2:8] == qk[KW-1:0]);", "assign hit0 = 1'b0;"),
 ("hash: the value of table 0 is taken even on a table-1 hit", "r_val <= hit0 ? r0[7:0] : hit1 ? r1[7:0] : 8'd0;", "r_val <= (hit0 || hit1) ? r0[7:0] : 8'd0;"),
 ("hash: the key is not held for the compare stage", "qk <= q_key; qv <= q_valid && !rst;", "qv <= q_valid && !rst;"),
 ("hash: a query during reset is answered", "qv <= q_valid && !rst;", "qv <= q_valid;"),
 ("hash: the value is not cleared on a miss", "r_val <= hit0 ? r0[7:0] : hit1 ? r1[7:0] : 8'd0;", "r_val <= hit0 ? r0[7:0] : r1[7:0];"),
 ("hash: the address of a write uses one bit less", "m0[w_addr[AW-1:0]] <= {w_vld", "m0[{1'b0, w_addr[AW-2:0]}] <= {w_vld"),
]
def res(o): return [(int(a), int(b)) for a, b in re.findall(r"RES (\d+) (\d+)", o)]
def battery(root):
    def sim(eng, lines, **kw):
        n = g.write_stim(os.path.join(root, "out", "match_stim.hex"), lines); d = (f"NC={n}", f"ENG={eng}") + tuple(f"{k}={v}" for k, v in kw.items()); return hw.sim_icarus(F, "match_tb", root=root, defines=d)[1]
    for mode in (0, 1, 2):
        for n in (8, 16):
            for seed in range(3):
                lines, exp = g.cam_ops(seed, mode, n, clear=seed % 2 == 0)
                if res(sim(mode, lines, N=n)) != exp: return f"cam mode {mode}, {n} slots, seed {seed}"
    for ch, aw, kw in ((1, 5, 32), (2, 5, 32), (2, 5, 12), (2, 6, 32)):
        for kind in ("random", "stride", "mcast"):
            for seed in range(2):
                lines, exp, st = g.hash_ops(seed, aw, ch, kw, int(0.8 * ch * (1 << aw)), kind, 160)
                if res(sim(2 + ch, lines, AW=aw, KW=kw)) != exp: return f"hash {ch} x {1 << aw}, {kw} bits, {kind}, seed {seed}"
    return None
def one(m):
    label, old, new = m; d = tempfile.mkdtemp(prefix="mut10_")
    for sub in ("rtl", "tb", "out", "model"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub), ignore=shutil.ignore_patterns("*.json", "*_synth.log", "*.hex"))
    p = os.path.join(d, M); s = open(p).read()
    if s.count(old) != 1: shutil.rmtree(d, ignore_errors=True); return label, f"BAD ANCHOR ({s.count(old)} occurrences)"
    open(p, "w").write(s.replace(old, new)); r = battery(d); shutil.rmtree(d, ignore_errors=True); return label, ("NOT CAUGHT" if r is None else "caught by: " + r)
if __name__ == "__main__":
    print("NOTE: this script deliberately breaks copies of the RTL. 'caught' lines are EXPECTED: they show the battery notices the mistake.")
    base = battery(flow.ROOT); print("unmutated design passes the whole battery:", base is None, "" if base is None else base)
    with cf.ThreadPoolExecutor(4) as ex: res_ = list(ex.map(one, MUTANTS))
    caught = 0
    for label, st in res_: print(f"  {label}: {st}"); caught += st.startswith("caught")
    print(f"mutants caught: {caught} of {len(MUTANTS)}")
    sys.exit(0 if base is None and caught == len(MUTANTS) else 1)
