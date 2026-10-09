#!/usr/bin/env python3
"""Chapter 16: test the tests. Three families of mutants, one battery (`python3 tools/ch16_run.py --battery`: the parser against the independent model on four kinds of stream, every message and packet end at its cycle):
  (1) the GENERATED RTL (rtl/mold_itch.sv), mutated as text, no regeneration;
  (2) the GENERATOR (tools/gen_parser.py), mutated, the RTL regenerated from the unmutated grammar: a bug in the generator is a bug in every parser it will ever make;
  (3) the GRAMMAR (model/grammar.py), mutated, the RTL regenerated: a wrong layout must disagree with the model, which has its own copy of the layouts."""
import concurrent.futures as cf, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flow
RTL = "rtl/mold_itch.sv"; GEN = "tools/gen_parser.py"; GRA = "model/grammar.py"
MUT = [
 (RTL, "the header ends one byte late", "hdr_last = (pos == 5'd19)", "hdr_last = (pos == 5'd20)"),
 (RTL, "the sequence number is taken from the wrong header bytes", "else if (pos < 5'd18) h_seq", "else if (pos < 5'd17) h_seq"),
 (RTL, "the session is 9 bytes", "if (pos < 5'd10) h_session", "if (pos < 5'd9) h_session"),
 (RTL, "the count is taken from the wrong byte", "else h_count <= {h_count[7:0], data}", "else h_count <= {data, h_count[15:8]}"),
 (RTL, "the length is little-endian", "len_now = {lenh, data}", "len_now = {data, lenh}"),
 (RTL, "a zero-length block is not reported", "if (len_now == 16'd0) begin m_valid <= 1'b1; m_type <= 8'd0; m_err <= 2'd2; m_idx <= nblk; end end", "end"),
 (RTL, "a zero-length block is not counted", "LENL: if (len_now == 16'd0) begin st_n = LENH; nblk_n = nblk + 16'd1; end", "LENL: if (len_now == 16'd0) begin st_n = LENH; end"),
 (RTL, "a zero-length block is reported as an unknown type", "m_type <= 8'd0; m_err <= 2'd2;", "m_type <= 8'd0; m_err <= 2'd1;"),
 (RTL, "the length of type A is wrong", "8'h41: exp_len = 8'd36;", "8'h41: exp_len = 8'd35;"),
 (RTL, "the last type of the table is missing", "8'h50: exp_len = 8'd44;   // P", "8'h50: exp_len = 8'd0;   // P"),
 (RTL, "the length is not compared with the type's", "(({8'd0, exp_len} == rem) ? 2'd0 : 2'd2)", "2'd0"),
 (RTL, "an unknown type is reported as a bad length", "er_d = (exp_len == 8'd0) ? 2'd1 :", "er_d = (exp_len == 8'd0) ? 2'd2 :"),
 (RTL, "the error is taken from the wrong place on a one-byte block", "m_err <= (off == 8'd0) ? er_d : er;", "m_err <= er;"),
 (RTL, "the type of a one-byte block is stale", "m_type <= (off == 8'd0) ? data : ty;", "m_type <= ty;"),
 (RTL, "the body ends one byte late", "last_byte = (rem == 16'd1)", "last_byte = (rem == 16'd2)"),
 (RTL, "the offset counter does not saturate", "if (off != 8'hff) off <= off + 8'd1;", "off <= off + 8'd1;"),
 (RTL, "the offset is not reset for each block", "rem <= len_now; off <= 8'd0;", "rem <= len_now;"),
 (RTL, "a field of type A starts one byte early", "(ty == 8'h41 && off >= 8'd24 && off < 8'd32)", "(ty == 8'h41 && off >= 8'd23 && off < 8'd31)"),
 (RTL, "a field of type U is one byte too short", "(ty == 8'h55 && off >= 8'd19 && off < 8'd27)", "(ty == 8'h55 && off >= 8'd19 && off < 8'd26)"),
 (RTL, "a field of type P is not selected", "(ty == 8'h50 && off >= 8'd36 && off < 8'd44)", "(1'b0)"),
 (RTL, "the shared field takes type E's offset for type X", "(ty == 8'h58 && off >= 8'd19 && off < 8'd23)", "(ty == 8'h58 && off >= 8'd20 && off < 8'd24)"),
 (RTL, "a field is shifted in the wrong order", "f_ref <= {f_ref[55:0], data}", "f_ref <= {data, f_ref[63:8]}"),
 (RTL, "the message index is the next one", "m_idx <= nblk; end end", "m_idx <= nblk + 16'd1; end end"),
 (RTL, "the block counter is not cleared by a new packet", "nblk <= 16'd0; h_session", "h_session"),
 (RTL, "the block counter does not count the last block", "BODY: if (last_byte) begin st_n = LENH; nblk_n = nblk + 16'd1; end", "BODY: if (last_byte) begin st_n = LENH; end"),
 (RTL, "the end of the packet inside a block is not a truncation", "p_trunc <= (st_n != LENH);", "p_trunc <= (st_n == IDLE);"),
 (RTL, "the end of the packet inside the header is not a truncation", "(st_n != LENH)", "(st_n != LENH && st != HDR)"),
 (RTL, "the count is not compared", "(nblk_n != count_now) &&", "1'b0 &&"),
 (RTL, "the count 0xFFFF is checked", "&& (count_now != 16'hffff)", ""),
 (RTL, "the count is read before its last byte arrives", "count_now = (st == HDR) ? {h_count[7:0], data} : h_count;", "count_now = h_count;"),
 (RTL, "a truncated packet also reports a bad count", "p_cntbad <= (st_n == LENH) && ", "p_cntbad <= "),
 (RTL, "a stray eop outside a packet reports a packet end", "if (eop && !sop && st != IDLE)", "if (eop && !sop)"),
 (RTL, "a packet end does not return to idle", "p_cntbad <= (st_n == LENH) && (nblk_n != count_now) && (count_now != 16'hffff); st <= IDLE; end", "p_cntbad <= (st_n == LENH) && (nblk_n != count_now) && (count_now != 16'hffff); end"),
 (RTL, "bytes outside a packet start a packet", "else begin\n                st <= st_n;", "else begin\n                if (st == IDLE) st <= HDR; else\n                st <= st_n;"),
 (RTL, "a one-byte packet is not reported", "if (eop && sop) begin p_valid <= 1'b1;", "if (eop && sop) begin p_valid <= 1'b0;"),
 (RTL, "a new sop does not restart the header", "if (sop) begin st <= HDR; pos <= 5'd1;", "if (sop) begin st <= HDR;"),
 (RTL, "the first header byte is lost", "h_session <= {72'd0, data}; end", "end"),
 (RTL, "valid is not looked at", "else if (valid) begin", "else begin"),
 (RTL, "the fields are captured on invalid cycles", "always_ff @(posedge clk) if (valid && !sop && !rst) begin", "always_ff @(posedge clk) if (!sop && !rst) begin"),
 (RTL, "reset does not stop a packet", "if (rst) st <= IDLE;", "if (rst) ;"),
 (GEN, "generator: the offset of a field starts at 0", "o = 1\n        for nm, n in m: sel[nm].append((t, o, n)); o += n", "o = 0\n        for nm, n in m: sel[nm].append((t, o, n)); o += n"),
 (GEN, "generator: the offset does not advance", "sel[nm].append((t, o, n)); o += n", "sel[nm].append((t, o, n)); o += 0"),
 (GEN, "generator: a field's end is inclusive", "off < 8'd{o + n})", "off <= 8'd{o + n})"),
 (GEN, "generator: the type code is the type's position", "8'h{ord(t):02x}: exp_len", "8'h{types.index(t):02x}: exp_len"),
 (GEN, "generator: a one-byte field is shifted like a wide one", "if (s_{nm}) f_{nm} <= data;", "if (s_{nm}) f_{nm} <= {f_{nm}[0], data};"),
 (GRA, "grammar: the length of a type leaves out the type byte", "return 1 + sum", "return 0 + sum"),
 (GRA, "grammar: two fields of A swapped", '("ref", 8), ("side", 1), ("shares", 4), ("stock", 8), ("price", 4)],\n    "F"', '("side", 1), ("ref", 8), ("shares", 4), ("stock", 8), ("price", 4)],\n    "F"'),
 (GRA, "grammar: the timestamp of S is 4 bytes", '"S": [("locate", 2), ("tracking", 2), ("ts", 6)', '"S": [("locate", 2), ("tracking", 2), ("ts", 4)'),
 (GRA, "grammar: type D has a stray byte", '"D": [("locate", 2), ("tracking", 2), ("ts", 6), ("ref", 8)]', '"D": [("locate", 2), ("tracking", 2), ("ts", 6), ("ref", 8), ("tracking", 2)]'),
 (GRA, "grammar: a message type is missing", '    "X": [("locate", 2), ("tracking", 2), ("ts", 6), ("ref", 8), ("shares", 4)],\n', ""),
 (GRA, "grammar: the price is 8 bytes everywhere", '("price", 4)', '("price", 8)'),
]
def one(j):
    f, label, old, new = j
    d = tempfile.mkdtemp(prefix="mut16_")
    for sub in ("rtl", "tb", "out", "model", "tools"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub), ignore=shutil.ignore_patterns("*.json", "*_synth.log", "*.hex", "__pycache__"))
    p = os.path.join(d, f); s = open(p).read()
    if old not in s: shutil.rmtree(d, ignore_errors=True); return label, "BAD ANCHOR (0 occurrences)"
    i = s.index(old); open(p, "w").write(s[:i] + new + s[i + len(old):])
    args = [sys.executable, "tools/ch16_run.py", "--battery"] + (["--no-regen"] if f == RTL else [])
    try: q = subprocess.run(args, cwd=d, capture_output=True, text=True, timeout=600); out = q.stdout.strip().splitlines()[-1] if q.stdout.strip() else "RESULT crash: " + (q.stderr.strip().splitlines() or ["?"])[-1][:70]
    except subprocess.TimeoutExpired: out = "RESULT hang (timeout)"
    shutil.rmtree(d, ignore_errors=True); r = out.replace("RESULT ", "")
    return label, ("NOT CAUGHT" if r == "None" else "caught by: " + r[:110])
if __name__ == "__main__":
    print("NOTE: this script deliberately breaks copies of the generated RTL, of the generator and of the grammar. 'caught' lines are EXPECTED: they show the battery notices the mistake.")
    q = subprocess.run([sys.executable, "tools/ch16_run.py", "--battery"], cwd=flow.ROOT, capture_output=True, text=True); base = q.stdout.strip().endswith("None"); print("unmutated design passes the battery:", base)
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(one, MUT))
    cnt = {RTL: [0, 0], GEN: [0, 0], GRA: [0, 0]}
    for (f, *_), (label, st) in zip(MUT, res): print(f"  {label}: {st}"); cnt[f][1] += 1; cnt[f][0] += st.startswith("caught")
    for f, (c, n) in cnt.items(): print(f"  {f}: caught {c} of {n}")
    print(f"mutants caught: {sum(c for c, n in cnt.values())} of {len(MUT)}")
