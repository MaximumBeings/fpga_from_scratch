#!/usr/bin/env python3
"""Chapter 6: mutation testing with the generated mutants of tools/mutlib.py, scored against five levels of verification, each cumulative: (1) the directed test, (2) 500 cycles of uniform random, (3) 500 cycles of constrained random, (4) 5,000 cycles of each random kind, (5) formal bounded model checking (12 cycles, all properties; the longest shortest-counterexample of the six injected bugs is 9 cycles). A mutant that survives all five is then checked for EQUIVALENCE with the original by a SAT miter (14 cycles from reset, outputs compared when the FIFO is not empty). Usage: mut_ch06.py"""
import os, re, shutil, subprocess, sys, tempfile, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, hw, fifo_gold as g, mutlib
R = flow.ROOT
def clean(t):
    t = re.sub(r"^\s*if \(BUG == \d.*\n", "", t, flags=re.M)
    return t.replace("((BUG == 3) ? LATE : LAST)", "LAST").replace("2'b11: if (BUG == 2 && count == CW'(1)) count <= '0;", "2'b11: ;")
LEVELS = [("directed", g.directed()), ("uniform 500", g.uniform(11, 500)), ("constrained 500", g.constrained(11, 500)), ("uniform 5000", g.uniform(12, 5000)), ("constrained 5000", g.constrained(12, 5000))]
def sim_ok(d, stim, tag):
    g.write_vectors(os.path.join(d, "out", f"vec_{tag}.hex"), stim, g.run(stim))
    rc, o = hw.sim_icarus(["rtl/sfifo.sv", "tb/sfifo_tb.sv"], "sfifo_tb", root=d, defines=("BUG=0", f"NC={len(stim)}", f'VEC="out/vec_{tag}.hex"'))
    return rc == 0 and "PASS" in o
def formal_ok(d):
    s = f"read_verilog -formal -sv {d}/rtl/sfifo.sv {R}/formal/sfifo_props.sv; chparam -set BUG 0 sfifo_props; hierarchy -top sfifo_props; proc; flatten; memory_map; opt_clean; sat -seq 12 -prove-asserts -set-init-zero"
    o = subprocess.run(["yosys", "-p", s], capture_output=True, text=True, timeout=300).stdout
    return "no model found: SUCCESS" in o
WRAP = """module obs_a(input logic clk, input logic rst, input logic wr_en, input logic [7:0] wr_data, input logic rd_en, output logic [7:0] q, output logic full, output logic empty, output logic [2:0] count);
    logic [7:0] rd; sfifo #(.W(8), .DEPTH(6), .BUG(0)) u (.clk(clk), .rst(rst), .wr_en(wr_en), .wr_data(wr_data), .rd_en(rd_en), .rd_data(rd), .full(full), .empty(empty), .count(count)); assign q = empty ? 8'd0 : rd; endmodule
module obs_b(input logic clk, input logic rst, input logic wr_en, input logic [7:0] wr_data, input logic rd_en, output logic [7:0] q, output logic full, output logic empty, output logic [2:0] count);
    logic [7:0] rd; sfifo_m #(.W(8), .DEPTH(6), .BUG(0)) u (.clk(clk), .rst(rst), .wr_en(wr_en), .wr_data(wr_data), .rd_en(rd_en), .rd_data(rd), .full(full), .empty(empty), .count(count)); assign q = empty ? 8'd0 : rd; endmodule
"""
def equivalent(d, text):
    open(os.path.join(d, "sfifo_m.sv"), "w").write(text.replace("module sfifo ", "module sfifo_m ")); open(os.path.join(d, "obs.sv"), "w").write(WRAP)
    s = f"read_verilog -sv {R}/rtl/sfifo.sv {d}/sfifo_m.sv {d}/obs.sv; proc; flatten; memory_map; opt_clean; miter -equiv -flatten -make_assert obs_a obs_b m; hierarchy -top m; sat -seq 14 -set-at 1 in_rst 1 -prove-asserts -prove-skip 1 -set-init-zero"
    o = subprocess.run(["yosys", "-p", s], capture_output=True, text=True, timeout=300).stdout
    return "no model found: SUCCESS" in o
def one(m):
    ln, desc, text = m; d = tempfile.mkdtemp(prefix="mut6_")
    for sub in ("rtl", "tb", "out", "model"): shutil.copytree(os.path.join(R, sub), os.path.join(d, sub), ignore=shutil.ignore_patterns("*.json", "*_synth.log", "*.hex"))
    open(os.path.join(d, "rtl", "sfifo.sv"), "w").write(text); killed = None
    for name, st in LEVELS:
        if not sim_ok(d, st, name.replace(" ", "")): killed = name; break
    if killed is None and not formal_ok(d): killed = "formal (12 cycles)"
    eq = None
    if killed is None: eq = equivalent(d, text)
    shutil.rmtree(d, ignore_errors=True); return desc, killed, eq
if __name__ == "__main__":
    print("NOTE: this script deliberately breaks copies of the RTL. 'killed by' lines are EXPECTED: they show a technique notices the mistake.")
    base = clean(open(os.path.join(R, "rtl", "sfifo.sv")).read()); muts = mutlib.generate(base, skip=r"^\s*//|^module|^\s*localparam|^\s*logic|^\s*output|^\s*input")
    d0 = tempfile.mkdtemp(prefix="mut6b_")
    for sub in ("rtl", "tb", "out", "model"): shutil.copytree(os.path.join(R, sub), os.path.join(d0, sub), ignore=shutil.ignore_patterns("*.json", "*_synth.log", "*.hex"))
    open(os.path.join(d0, "rtl", "sfifo.sv"), "w").write(base); ok = all(sim_ok(d0, st, "b" + n.replace(" ", "")) for n, st in LEVELS) and formal_ok(d0); shutil.rmtree(d0, ignore_errors=True)
    print(f"unmutated design (bug-free copy) passes all five levels: {ok};  generated mutants: {len(muts)}")
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(one, muts))
    print(f"  {'mutant':84s} {'killed by'}")
    for desc, k, eq in res: print(f"  {desc[:84]:84s} {k if k else ('SURVIVES; proved equivalent for 14 cycles' if eq else 'SURVIVES; NOT equivalent: a gap')}")
    print("\ncumulative kills (a mutant is counted at the first level that kills it):")
    tot = len(res); cum = 0
    for name in [n for n, _ in LEVELS] + ["formal (12 cycles)"]:
        c = sum(1 for _, k, _ in res if k == name); cum += c; print(f"  {name:20s} kills {c:3d}   cumulative {cum:3d} of {tot}  ({100 * cum / tot:.0f}%)")
    eqs = sum(1 for _, k, e in res if k is None and e); gaps = sum(1 for _, k, e in res if k is None and not e)
    print(f"  survivors proved equivalent: {eqs};  survivors NOT equivalent (gaps in the tests): {gaps}")
    killable = tot - eqs; print(f"  mutation score over the non-equivalent mutants: {cum} of {killable} ({100 * cum / killable:.0f}%)")
    sys.exit(0 if ok and gaps == 0 else 1)
