#!/usr/bin/env python3
"""Chapter 5: test the tests. Each mutant breaks one line of rtl/fxp.sv, rtl/fir.sv or rtl/ram_style.sv. The battery: rounding/saturation exhaustively (12 -> 6 bits in all four modes, 14 -> 8 bits rounded and saturated), the multiply-accumulate in six traffic/mode combinations, both FIR forms in two modes, the memory in four style/depth combinations. Changes no test can see are listed apart. Usage: mut_ch05.py"""
import concurrent.futures as cf, os, random, shutil, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, hw, fx_gold as g
X = "rtl/fxp.sv"; F = "rtl/fir.sv"; M = "rtl/ram_style.sv"
COHEX = "".join(f"{g.COEF[i] & 0xFFFF:04x}" for i in reversed(range(8)))
MUTANTS = [
 (X, "round: the half constant is one place too high", "(EW'(1) <<< (SH - 1)) : EW'(0);", "(EW'(1) <<< SH) : EW'(0);"),
 (X, "round: truncation mode also rounds", "(RND != 0 && SH > 0) ?", "(SH > 0) ?"),
 (X, "round: the largest value is one too high", "MAXV = (EW'(1) <<< (OW - 1)) - EW'(1);", "MAXV = (EW'(1) <<< (OW - 1));"),
 (X, "round: the smallest value is one too high", "MINV = -(EW'(1) <<< (OW - 1));", "MINV = -(EW'(1) <<< (OW - 1)) + EW'(1);"),
 (X, "round: logical shift instead of arithmetic", "s = r >>> SH;", "s = r >> SH;"),
 (X, "round: saturation is always on", "if (SAT != 0) begin", "if (1'b1) begin"),
 (X, "mac: the product is subtracted", "else if (pen) acc <= acc + 40'(p);", "else if (pen) acc <= acc - 40'(p);"),
 (X, "mac: a clear without an enable loads the product", "if (pclr) acc <= pen ? 40'(p) : 40'sd0;", "if (pclr) acc <= 40'(p);"),
 (X, "mac: the accumulator adds even when not enabled", "else if (pen) acc <= acc + 40'(p);", "else acc <= acc + 40'(p);"),
 (X, "mac: the operand register is skipped", "p <= ra * rb; pen <= ren; pclr <= rclr;", "p <= a * b; pen <= ren; pclr <= rclr;"),
 (X, "mac: the enable is not delayed with the data", "p <= ra * rb; pen <= ren;", "p <= ra * rb; pen <= en;"),
 (X, "mac: reset does not clear the accumulator", "pen <= 1'b0; pclr <= 1'b0; acc <= '0; end", "pen <= 1'b0; pclr <= 1'b0; end"),
 (X, "mac: the product is zero-extended, not sign-extended", "acc <= acc + 40'(p);", "acc <= acc + {8'd0, p};"),
 (F, "fir direct: coefficients shifted by one", "sum = sum + 40'(tap[i] * $signed(CO[i*16 +: 16]));", "sum = sum + 40'(tap[i] * $signed(CO[((i + 1) % 8)*16 +: 16]));"),
 (F, "fir direct: the sum is never registered", "acc <= sum;", "acc <= acc;"),
 (F, "fir direct: reset does not clear the taps", "if (rst) begin acc <= '0; for (int i = 0; i < 8; i++) tap[i] <= '0; end", "if (rst) begin acc <= '0; end"),
 (F, "fir transposed: the last coefficient is the wrong one", "t[7] <= 40'(xr * $signed(CO[7*16 +: 16]));", "t[7] <= 40'(xr * $signed(CO[6*16 +: 16]));"),
 (F, "fir transposed: a stage adds its own old value", "t[i] <= t[i + 1] + 40'(xr * $signed(CO[i*16 +: 16]));", "t[i] <= t[i] + 40'(xr * $signed(CO[i*16 +: 16]));"),
 (M, "ram: the write goes to the read address", "if (we) mem[waddr] <= wdata;", "if (we) mem[raddr] <= wdata;"),
 (M, "ram: styles 1 and 2 are swapped", "((STYLE == 1) ? r1 : r2)", "((STYLE == 1) ? r2 : r1)"),
 (M, "ram: the output register takes the array directly", "r2 <= r1;", "r2 <= mem[raddr];"),
 (M, "ram: the memory has no initial contents", "    initial for (int i = 0; i < D; i++) mem[i] = '0;", ""),
 (M, "ram: a synchronous read of the written address returns the new data", "r1 <= mem[raddr];", "r1 <= (we && waddr == raddr) ? wdata : mem[raddr];"),
]
EQUIV = [
 (X, "round: saturate when the value EQUALS the maximum (the result is the same value either way)", "if (s > MAXV) y = MAXV[OW-1:0];", "if (s >= MAXV) y = MAXV[OW-1:0];"),
 (X, "round: saturate when the value EQUALS the minimum (the result is the same value either way)", "else if (s < MINV) y = MINV[OW-1:0];", "else if (s <= MINV) y = MINV[OW-1:0];"),
]
def battery(root):
    V = lambda n: os.path.join(root, "out", n)
    def sim(files, top, d): rc, o = hw.sim_icarus(files, top, root=root, defines=d); return rc == 0 and "PASS" in o
    for iw, ow, sh, rnd, sat in ((12, 6, 4, 0, 0), (12, 6, 4, 1, 0), (12, 6, 4, 0, 1), (12, 6, 4, 1, 1), (14, 8, 5, 1, 1)):
        g.rs_vectors(V("rs_vec.hex"), iw, ow, sh, rnd, sat)
        if not sim([X, "tb/rs_tb.sv"], "rs_tb", (f"IW={iw}", f"OW={ow}", f"SH={sh}", f"RND={rnd}", f"SAT={sat}")): return f"round/saturate {iw}->{ow} rnd={rnd} sat={sat}"
    for mode, rnd, sat in (("random", 1, 1), ("random", 0, 1), ("random", 1, 0), ("random", 0, 0), ("overflow", 1, 1), ("overflow", 1, 0)):
        st = g.mac_stim(1, 1500, mode); g.write_mac(V("mac_vec.hex"), st, g.mac_run(st, rnd, sat))
        if not sim([X, "tb/mac_tb.sv"], "mac_tb", (f"RND={rnd}", f"SAT={sat}", "NC=1500")): return f"mac {mode} rnd={rnd} sat={sat}"
    rng = random.Random(3); xs = [rng.randint(-32768, 32767) if k % 50 < 40 else rng.choice([32767, -32768]) for k in range(1500)]
    for form in (0, 1):
        for rnd in (1, 0):
            g.write_fir(V("fir_vec.hex"), xs, g.fir_run(xs, rnd, 1))
            if not sim([X, F, "tb/fir_tb.sv"], "fir_tb", (f"FORM={form}", f"COHEX={COHEX}", "NC=1500", f"RND={rnd}", "SAT=1")): return f"fir form {form} rnd={rnd}"
    for D, s in ((64, 0), (64, 1), (64, 2), (256, 1)):
        ops = g.ram_ops(2, 1500, D, 16); g.write_ram(V("ram_vec.hex"), ops, g.ram_run(s, ops, D), 16)
        if not sim([M, "tb/ram_tb.sv"], "ram_tb", (f"D={D}", f"STYLE={s}", "NC=1500")): return f"ram depth {D} style {s}"
    return None
def one(m):
    fn, label, old, new = m; d = tempfile.mkdtemp(prefix="mut5_")
    for sub in ("rtl", "tb", "out", "model"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub), ignore=shutil.ignore_patterns("*.json", "*_synth.log"))
    p = os.path.join(d, fn); s = open(p).read()
    if s.count(old) != 1: shutil.rmtree(d, ignore_errors=True); return label, f"BAD ANCHOR ({s.count(old)} occurrences)"
    open(p, "w").write(s.replace(old, new)); r = battery(d); shutil.rmtree(d, ignore_errors=True); return label, ("NOT CAUGHT" if r is None else "caught by: " + r)
if __name__ == "__main__":
    print("NOTE: this script deliberately breaks copies of the RTL. 'caught' lines are EXPECTED: they show the battery notices the mistake.")
    base = battery(flow.ROOT); print("unmutated design passes the whole battery:", base is None, "" if base is None else base)
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(one, MUTANTS)); eq = list(ex.map(one, EQUIV))
    caught = 0
    for label, st in res: print(f"  {label}: {st}"); caught += st.startswith("caught")
    print(f"mutants caught: {caught} of {len(MUTANTS)}")
    print("equivalent changes (no test can tell them apart; listed apart, see the page):")
    for label, st in eq: print(f"  {label}: {st}")
    sys.exit(0 if base is None and caught == len(MUTANTS) and all(s == "NOT CAUGHT" for _, s in eq) else 1)
