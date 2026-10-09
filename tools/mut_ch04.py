#!/usr/bin/env python3
"""Chapter 4: test the tests. Each mutant breaks one line of rtl/pipe.sv or rtl/pktfilt.sv. The battery on each mutant: the pipelined function with S = 1, 3 and 12 (random valid/data against the golden model), and both packet filters against their golden models on three packet mixes. Changes no testbench can see are listed apart. Usage: mut_ch04.py"""
import concurrent.futures as cf, os, shutil, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, hw, lat_gold as g
P = "rtl/pipe.sv"; K = "rtl/pktfilt.sv"
MUTANTS = [
 (P, "pipe: one round too few in each stage", "for (int r = 0; r < G; r++) t = rnd(t);", "for (int r = 0; r < G - 1; r++) t = rnd(t);"),
 (P, "pipe: the round mixes the wrong neighbours", "(x[(j + 1) % W] & x[(j + 3) % W])", "(x[(j + 1) % W] & x[(j + 2) % W])"),
 (P, "pipe: a stage register takes its input, skipping the logic", "q[s] <= t;", "q[s] <= a;"),
 (P, "pipe: the output valid is taken from the first stage", "assign out_data = q[S - 1]; assign out_valid = v[S - 1];", "assign out_data = q[S - 1]; assign out_valid = v[0];"),
 (P, "pipe: the input register is bypassed (one cycle too fast)", "assign a  = (s == 0) ? qi :", "assign a  = (s == 0) ? in_data :"),
 (P, "pipe: the valid chain is not cleared by reset", "v[s] <= rst ? 1'b0 : av;", "v[s] <= av;"),
 (P, "pipe: the input valid register is not cleared by reset", "vi <= rst ? 1'b0 : in_valid;", "vi <= in_valid;"),
 (P, "pipe: the valid bit is delayed one stage too long (extra register in the first stage)", "assign av = (s == 0) ? vi :", "assign av = (s == 0) ? vi & in_valid :"),
 (K, "ct: the header byte is 0xA4", "assign keep_n = first ? (in_data[7:0] == 8'hA5) : keep;", "assign keep_n = first ? (in_data[7:0] == 8'hA4) : keep;"),
 (K, "ct: a dropped packet's later beats are forwarded", ": keep;\n    assign acc_n", ": 1'b1;\n    assign acc_n"),
 (K, "ct: the checksum is not restarted for each packet", "assign acc_n = (first ? 16'd0 : acc) + in_data[15:0];", "assign acc_n = acc + in_data[15:0];"),
 (K, "ct: bad is flagged on dropped packets too", "out_bad <= in_last && keep_n && (acc_n != 16'd0);", "out_bad <= in_last && (acc_n != 16'd0);"),
 (K, "ct: the checksum uses only 15 bits", "(first ? 16'd0 : acc) + in_data[15:0];", "(first ? 16'd0 : acc) + {1'b0, in_data[14:0]};"),
 (K, "ct: no beat is ever the first of a packet after the first packet", "inpkt <= !in_last; keep <= keep_n;", "inpkt <= 1'b1; keep <= keep_n;"),
 (K, "ct: last is never forwarded", "out_last <= in_last; out_bad", "out_last <= 1'b0; out_bad"),
 (K, "ct: reset does not clear the packet state", "inpkt <= 1'b0; keep <= 1'b0; acc <= 16'd0; out_data <= 32'd0; end\n        else if (!in_valid)", "keep <= 1'b0; acc <= 16'd0; out_data <= 32'd0; end\n        else if (!in_valid)"),
 (K, "ct: an idle cycle leaves the output valid", "else if (!in_valid) begin out_valid <= 1'b0; out_last", "else if (!in_valid) begin out_last"),
 (K, "sf: the header byte is 0xA4", "== 8'hA5) && (acc_n == 16'd0);", "== 8'hA4) && (acc_n == 16'd0);"),
 (K, "sf: the checksum leaves out the last beat", "&& (acc_n == 16'd0);", "&& (acc == 16'd0);"),
 (K, "sf: one beat too few is streamed out", "total <= n + 1'b1; n <= n + 1'b1; end", "total <= n; n <= n + 1'b1; end"),
 (K, "sf: last is flagged one beat late", "out_last <= (rd == total - 1'b1);", "out_last <= (rd == total);"),
 (K, "sf: ready stays high while draining", "assign in_ready = !drain;", "assign in_ready = 1'b1;"),
 (K, "sf: a discarded packet leaves its checksum behind", "else begin n <= '0; acc <= 16'd0; end", "else begin n <= '0; end"),
 (K, "sf: a discarded packet leaves its length behind", "else begin n <= '0; acc <= 16'd0; end", "else begin acc <= 16'd0; end"),
 (K, "sf: the first byte is never captured", "if (n == '0) first_lo <= in_data[7:0];", ""),
 (K, "sf: draining never ends", "if (rd == total - 1'b1) begin drain <= 1'b0; n <= '0; acc <= 16'd0; end", "if (rd == total - 1'b1) begin n <= '0; acc <= 16'd0; end"),
 (K, "sf: every beat comes out of buffer slot 0", "out_data <= buffer[rd[AW-1:0]];", "out_data <= buffer[0];"),
]
EQUIV = [
 (P, "pipe: a stage register loads only when its valid is set (data is checked only when valid)", "q[s] <= t;", "if (av) q[s] <= t;"),
 (K, "sf: the write count is not advanced on the last beat of a good packet (it is reset when the drain ends)", "total <= n + 1'b1; n <= n + 1'b1; end", "total <= n + 1'b1; end"),
]
def battery(root):
    def run(sim, files, top, defines): return sim(files, top, root=root, defines=defines)
    for s in (1, 3, 12):
        g.pipe_vectors(os.path.join(root, "out", "pipe_vec.hex"), s, 1500, 5, p_valid=0.7); rc, o = run(hw.sim_icarus, ["rtl/pipe.sv", "tb/pipe_tb.sv"], "pipe_tb", (f"S={s}", "NC=1500"))
        if rc != 0 or "PASS" not in o: return f"pipe S={s}"
    for sf, model, dense, name in ((0, g.CT, True, "cut-through"), (1, g.SF, False, "store-and-forward")):
        for seed, mix in ((1, (5, 3, 2)), (2, (1, 1, 8)), (3, (1, 8, 1))):
            pk, gp = g.gen(seed, mix, 80, 12, dense); ins = g.schedule(pk, gp); g.write_vectors(os.path.join(root, "out", "pkt_vec.hex"), ins, g.run(model, ins))
            rc, o = run(hw.sim_icarus, ["rtl/pktfilt.sv", "tb/pkt_tb.sv"], "pkt_tb", (f"SF={sf}", f"NC={len(ins)}"))
            if rc != 0 or "PASS" not in o: return f"{name} mix {mix}"
    return None
def one(m):
    fn, label, old, new = m; d = tempfile.mkdtemp(prefix="mut4_")
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
    print("equivalent changes (no testbench can tell them apart; listed apart, see the page):")
    for label, st in eq: print(f"  {label}: {st}")
    sys.exit(0 if base is None and caught == len(MUTANTS) and all(s == "NOT CAUGHT" for _, s in eq) else 1)
