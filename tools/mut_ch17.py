#!/usr/bin/env python3
"""Chapter 17: test the tests. Two families of mutants, one battery (`python3 tools/ch17_run.py --battery`: the parser against the independent model, W = 8 and W = 4, on four kinds of stream, every message, framing error and packet end at its cycle):
  (1) the GENERATED RTL (rtl/mold_wide.sv, W = 8, version 2), mutated as text, no regeneration. Most anchors occur once per lane: `all` replaces every occurrence, `first` and `last` only lane 0 or lane 7's (a mistake in one lane only);
  (2) the GENERATOR (tools/gen_parser_wide.py), mutated, the RTL regenerated for W = 4 and 8."""
import concurrent.futures as cf, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flow
RTL = "rtl/mold_wide.sv"; GEN = "tools/gen_parser_wide.py"
MUT = [
 (RTL, "a new packet does not clear the block counter", "c_nblk = 16'd0; c_ses", "c_ses", "all"),
 (RTL, "the session is 9 bytes", "if (c_pos <= 5'd10) c_ses", "if (c_pos <= 5'd9) c_ses", "all"),
 (RTL, "the sequence number takes one byte too few", "else if (c_pos <= 5'd18) c_seq", "else if (c_pos <= 5'd17) c_seq", "all"),
 (RTL, "the header ends a byte early", "if (c_pos == 5'd20) c_st = LENH;", "if (c_pos == 5'd19) c_st = LENH;", "all"),
 (RTL, "the length is little-endian", "c_len = {c_lenh, b};", "c_len = {b, c_lenh};", "all"),
 (RTL, "a zero-length block is not recognised", "if (c_len == 16'd0) begin", "if (c_len == 16'd9999) begin", "all"),
 (RTL, "a second completion is not an error", "if (c_done) begin x_v = 1'b1; x_i = c_nblk; c_st = DEAD; end", "if (1'b0) begin x_v = 1'b1; x_i = c_nblk; c_st = DEAD; end", "all"),
 (RTL, "a framing error does not abandon the packet", "x_i = c_nblk; c_st = DEAD; end", "x_i = c_nblk; end", "all"),
 (RTL, "the framing error reports the wrong index", "x_i = c_nblk;", "x_i = c_nblk + 16'd1;", "all"),
 (RTL, "the first completion does not mark the beat", "else begin c_done = 1'b1; m_v = 1'b1;", "else begin m_v = 1'b1;", "all"),
 (RTL, "a completed block is not counted", "c_nblk = c_nblk + 16'd1; c_st = LENH;", "c_st = LENH;", "all"),
 (RTL, "a zero-length block is reported as a message of type 0 with error 1", "m_e = 2'd2; m_i = c_nblk;", "m_e = 2'd1; m_i = c_nblk;", "first"),
 (RTL, "an unknown type is a bad length", "er_d = (e_len == 8'd0) ? 2'd1 :", "er_d = (e_len == 8'd0) ? 2'd2 :", "all"),
 (RTL, "the length is not checked against the type's", "(({8'd0, e_len} == c_rem) ? 2'd0 : 2'd2)", "2'd0", "all"),
 (RTL, "the body ends a byte late", "lastb = (c_rem == 16'd1);", "lastb = (c_rem == 16'd2);", "all"),
 (RTL, "the offset counter does not saturate", "if (c_off != 8'hff) c_off = c_off + 8'd1;", "c_off = c_off + 8'd1;", "all"),
 (RTL, "the offset is not reset for a new block", "c_rem = c_len; c_off = 8'd0;", "c_rem = c_len;", "all"),
 (RTL, "a one-byte block takes the previous type", "t_ty = (c_off == 8'd0) ? b : c_ty;", "t_ty = c_ty;", "all"),
 (RTL, "a one-byte block takes the previous error", "t_er = (c_off == 8'd0) ? er_d : c_er;", "t_er = c_er;", "all"),
 (RTL, "the tagged offset is one too high", "= c_off; tg_ty", "= c_off + 8'd1; tg_ty", "all"),
 (RTL, "the tagged type is stale for lane 7", "tg_ty[7] = c_ty;", "tg_ty[7] = ty;", "all"),
 (RTL, "the snapshot is never taken in lane 3", "tg_comp[3] = 1'b1;", "", "all"),
 (RTL, "the packet end needs no packet", "p_v = eop && (c_st != IDLE);", "p_v = eop;", "all"),
 (RTL, "an abandoned packet is not truncated", "p_t = (c_st != LENH);", "p_t = (c_st != LENH) && (c_st != DEAD);", "all"),
 (RTL, "the count 0xFFFF is checked", "&& (c_cnt != 16'hffff);", ";", "all"),
 (RTL, "the count is not compared", "(c_nblk != c_cnt) &&", "1'b0 &&", "all"),
 (RTL, "a truncated packet also reports a bad count", "p_c = (c_st == LENH) &&", "p_c =", "all"),
 (RTL, "a packet end does not return to idle", "st <= eop ? IDLE : c_st;", "st <= c_st;", "all"),
 (RTL, "valid is not looked at", "else if (valid) begin", "else begin", "first"),
 (RTL, "the beat is one lane short", "< nb) begin", "< nb - 1) begin", "all"),
 (RTL, "the beat is one lane long", "< nb) begin", "<= nb) begin", "all"),
 (RTL, "stage 2 processes a beat that is not there", "if (v1) begin\n            m_valid", "if (1'b1) begin\n            m_valid", "all"),
 (RTL, "the data of the beat is not registered", "v1 <= 1'b1; d1 <= data;", "v1 <= 1'b1;", "all"),
 (RTL, "the snapshot of a field is never used", "if (tg_comp1[0]) begin o_locate = n_locate;", "if (1'b0) begin o_locate = n_locate;", "all"),
 (RTL, "the working field is the output", "w_locate <= n_locate; f_locate <= o_locate;", "w_locate <= n_locate; f_locate <= n_locate;", "all"),
 (RTL, "a field is shifted in the wrong direction", "n_ref = {n_ref[55:0], b2};", "n_ref = {b2, n_ref[63:8]};", "all"),
 (RTL, "a lane of the beat is read from the wrong byte", "b2 = d1[8 +: 8];", "b2 = d1[0 +: 8];", "all"),
 (RTL, "the framing error is not passed to stage 2", "x_v1 <= x_v;", "x_v1 <= 1'b0;", "all"),
 (GEN, "generator: lanes read the bytes in the wrong order", 'b = data[{8 * j} +: 8];', 'b = data[{8 * (W - 1 - j)} +: 8];', "all"),
 (GEN, "generator: the second stage reads the wrong lane", 'b2 = d1[{8 * j} +: 8];', 'b2 = d1[{8 * ((j + 1) % W)} +: 8];', "all"),
 (GEN, "generator: the tagged type is not registered", 'tg_ty1[q] <= tg_ty[q];', '', "all"),
 (GEN, "generator: the snapshot is taken before the lane's push", 'A(f"        if (tg_comp1[{j}]) begin " + " ".join(f"o_{nm} = n_{nm};" for nm in F) + " end")', 'A(f"        if (tg_comp1[{j}]) begin " + " ".join(f"o_{nm} = w_{nm};" for nm in F) + " end")', "all"),
]
def apply(s, old, new, mode):
    if old not in s: return None
    if mode == "all": return s.replace(old, new)
    idx = s.index(old) if mode == "first" else s.rindex(old); return s[:idx] + new + s[idx + len(old):]
def one(j):
    f, label, old, new, mode = j
    d = tempfile.mkdtemp(prefix="mut17_")
    for sub in ("rtl", "tb", "out", "model", "tools"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub), ignore=shutil.ignore_patterns("*.json", "*_synth.log", "*.hex", "__pycache__", "ex17_*", "t17_*"))
    p = os.path.join(d, f); s = open(p).read(); t = apply(s, old, new, mode)
    if t is None: shutil.rmtree(d, ignore_errors=True); return label, "BAD ANCHOR (0 occurrences)"
    open(p, "w").write(t)
    args = [sys.executable, "tools/ch17_run.py", "--battery"] + (["--no-regen"] if f == RTL else [])
    try: q = subprocess.run(args, cwd=d, capture_output=True, text=True, timeout=900, env=dict(os.environ, MOLD_VERSION="2")); out = q.stdout.strip().splitlines()[-1] if q.stdout.strip() else "RESULT crash: " + (q.stderr.strip().splitlines() or ["?"])[-1][:70]
    except subprocess.TimeoutExpired: out = "RESULT hang (timeout)"
    shutil.rmtree(d, ignore_errors=True); r = out.replace("RESULT ", "")
    return label, ("NOT CAUGHT" if r == "None" else "caught by: " + r[:110])
if __name__ == "__main__":
    print("NOTE: this script deliberately breaks copies of the generated RTL and of the generator. 'caught' lines are EXPECTED: they show the battery notices the mistake.")
    q = subprocess.run([sys.executable, "tools/ch17_run.py", "--battery", "--no-regen"], cwd=flow.ROOT, capture_output=True, text=True, env=dict(os.environ, MOLD_VERSION="2")); base = q.stdout.strip().endswith("None"); print("unmutated design passes the battery:", base)
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(one, MUT))
    cnt = {RTL: [0, 0], GEN: [0, 0]}
    for (f, *_), (label, st) in zip(MUT, res): print(f"  {label}: {st}"); cnt[f][1] += 1; cnt[f][0] += st.startswith("caught")
    for f, (c, n) in cnt.items(): print(f"  {f}: caught {c} of {n}")
    print(f"mutants caught: {sum(c for c, n in cnt.values())} of {len(MUT)}")
