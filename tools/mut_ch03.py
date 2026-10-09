#!/usr/bin/env python3
"""Chapter 3: test the tests of the crossing circuits. Each mutant breaks one line of rtl/cdc_sync.sv, rtl/cdc.sv or rtl/gray_prop.sv; the whole battery then runs on the mutant: FIFO scoreboard with the ideal and the metastability synchronizer (five traffic/clock mixes), pulse counts against the event model, the reset synchronizer, a structural check that the synchronizer is two flip-flops, and the SAT proof of the Gray property. Usage: mut_ch03.py"""
import concurrent.futures as cf, os, re, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, hw, cdc_model
C = "rtl/cdc.sv"; S = "rtl/cdc_sync.sv"; G = "rtl/gray_prop.sv"
MUTANTS = [
 (S, "sync: one flip-flop instead of two (q takes d directly)", "q_r <= m;", "q_r <= d;"),
 (S, "sync: the first flip-flop starts at 1", "logic [W-1:0] m = '0;", "logic [W-1:0] m = '1;"),
 (C, "naive pulse: b_pulse is the level, not the edge", "assign b_pulse = b_sync && !b_prev;", "assign b_pulse = b_sync;"),
 (C, "toggle pulse: the source stores the pulse instead of toggling", "tog <= tog ^ a_pulse;", "tog <= a_pulse;"),
 (C, "toggle pulse: only rising changes are reported", "assign b_pulse = b_sync ^ b_prev;", "assign b_pulse = b_sync & !b_prev;"),
 (C, "reset synchronizer: reset no longer asserts asynchronously", "always_ff @(posedge clk or negedge arst_n) begin", "always_ff @(posedge clk) begin"),
 (C, "reset synchronizer: released after one edge", "else begin q1 <= 1'b1; rst_n <= q1; end", "else begin q1 <= 1'b1; rst_n <= 1'b1; end"),
 (C, "fifo: full compares only the top pointer bit flipped", "(wptr == {~rptr_s[AW:AW-1], rptr_s[AW-2:0]})", "(wptr == {~rptr_s[AW], rptr_s[AW-1:0]})"),
 (C, "fifo: empty ignores the wrap bit", "assign empty = (rptr == wptr_s);", "assign empty = (rptr[AW-1:0] == wptr_s[AW-1:0]);"),
 (C, "fifo: writes ignore full", "assign do_wr = wr_en && !full;", "assign do_wr = wr_en;"),
 (C, "fifo: reads ignore empty", "assign do_rd = rd_en && !empty;", "assign do_rd = rd_en;"),
 (C, "fifo: a word is written one slot ahead", "if (do_wr) mem[wbin[AW-1:0]] <= wr_data;", "if (do_wr) mem[wbin_n[AW-1:0]] <= wr_data;"),
 (C, "fifo: read data addressed by the Gray pointer", "assign rd_data = mem[rbin[AW-1:0]];", "assign rd_data = mem[rptr[AW-1:0]];"),
 (C, "fifo: the write pointer is not a Gray code (shifted by two)", "wptr_r <= GRAY ? (wbin_n ^ (wbin_n >> 1)) : wbin_n;", "wptr_r <= GRAY ? (wbin_n ^ (wbin_n >> 2)) : wbin_n;"),
 (C, "fifo: the read pointer is not a Gray code (shifted by two)", "rptr_r <= GRAY ? (rbin_n ^ (rbin_n >> 1)) : rbin_n;", "rptr_r <= GRAY ? (rbin_n ^ (rbin_n >> 2)) : rbin_n;"),
 (C, "fifo: gray2bin forgets the XOR with the bits above", "b[i] = b[i + 1] ^ g[i];", "b[i] = g[i];"),
 (C, "fifo: the write side forgets to reset its sent pointer", "if (!wrst_n) begin wbin <= '0; wptr_r <= '0; end", "if (!wrst_n) begin wbin <= '0; end"),
 (C, "fifo: the write pointer that crosses is one step older (full compares a stale pointer)", "wptr_r <= GRAY ? (wbin_n ^ (wbin_n >> 1)) : wbin_n;", "wptr_r <= GRAY ? (wbin ^ (wbin >> 1)) : wbin;"),
 (G, "gray_prop: the encoder shifts by two", "(b ^ (b >> 1))", "(b ^ (b >> 2))"),
]
EQUIV = [
 (C, "fifo: the reader's count is taken after this edge's read (rbin_n instead of rbin)", "assign rlevel = (GRAY ? wptr_b : wptr_s) - rbin;", "assign rlevel = (GRAY ? wptr_b : wptr_s) - rbin_n;"),
]
def battery(root):
    """Returns the name of the first check that fails, or None."""
    def fifo(sync, gray, wp, rp, pw, pr):
        fs = [("tb/cdc_sync_meta.sv" if sync == "meta" else S), C, "tb/cdc_fifo_tb.sv"]; rc, o = hw.sim_icarus(fs, "cdc_fifo_tb", root=root, defines=(f"GRAY={gray}", f"WP={wp}", f"RP={rp}", f"PW={pw}", f"PR={pr}"))
        return rc == 0 and any(l.startswith("PASS") for l in o.splitlines())
    for sync, args in (("ideal", (10000, 7300, 70, 60)), ("ideal", (7300, 10000, 100, 100)), ("ideal", (10000, 7300, 100, 30)), ("ideal", (10000, 7300, 30, 90)), ("meta", (10000, 7300, 70, 60)), ("meta", (7300, 10000, 100, 100))):
        if not fifo(sync, 1, *args): return f"FIFO {sync} {args}"
    for t in (0, 1):
        for bp, gap in ((2000, 6), (13000, 6), (41300, 4)):
            rc, o = hw.sim_icarus([S, C, "tb/cdc_pulse_tb.sv"], "cdc_pulse_tb", root=root, defines=(f"TOGGLE={t}", "AP=10000", f"BP={bp}", "OFF=1234", f"GAP={gap}", "NP=200")); m = re.search(r"got (\d+)", o)
            if not m or int(m.group(1)) != (cdc_model.pulses_toggle if t else cdc_model.pulses_naive)(10000, bp, 1234, gap, 200): return f"pulse {'toggle' if t else 'naive'} BP={bp} gap={gap}"
    rc, o = hw.sim_icarus([S, C, "tb/rst_sync_tb.sv"], "rst_sync_tb", root=root); rel = re.findall(r"REL (\d+) (\d+)", o); chk = re.search(r"bad_assert (\d+) bad_hold (\d+)", o)
    if len(rel) != 40 or any(int(e) != 2 for _, e in rel) or not chk or chk.group(1) != "0" or chk.group(2) != "0": return "reset synchronizer"
    y = subprocess.run(["yosys", "-p", f"read_verilog -sv {S}; hierarchy -top cdc_sync; chparam -set W 1 cdc_sync; synth_ice40 -top cdc_sync; select -count t:SB_DFF*"], cwd=root, capture_output=True, text=True).stdout
    ff = int(re.findall(r"(\d+) objects\.", y)[-1])
    if ff != 2: return f"structure: {ff} flip-flops in the synchronizer, expected 2"
    o = subprocess.run(["yosys", "-p", f"read_verilog -formal -sv {G}; chparam -set MODE 1 gray_prop; hierarchy -top gray_prop; proc; opt_clean; sat -prove-asserts"], cwd=root, capture_output=True, text=True).stdout
    if "no model found: SUCCESS" not in o: return "SAT: Gray property"
    return None
def one(m):
    fn, label, old, new = m; d = tempfile.mkdtemp(prefix="mut3_")
    for sub in ("rtl", "tb", "out", "model"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub))
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
    print("equivalent changes (no property in the testbench's reach can tell them apart; listed apart, see the page):")
    for label, st in eq: print(f"  {label}: {st}")
    sys.exit(0 if base is None and caught == len(MUTANTS)  else 1)
