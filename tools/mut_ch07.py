#!/usr/bin/env python3
"""Chapter 7: test the tests. Mutants of the GENERATED rtl/crc32_stream.sv: (a) hand-written changes to the wrappers (init value, final inversion, residue constant, byte-count handling, frame restart, valid timing, pipeline registers), (b) 'term deletion' mutants: for a sample of XOR terms in the generated equations of step8, step3 and step1, delete that one term (one input of one output bit's XOR). The battery: random frames and every-length frames at W = 8, 32 and 64 for both designs, against zlib. Usage: mut_ch07.py"""
import concurrent.futures as cf, os, random, re, shutil, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, hw, crc_gold as g
F = "rtl/crc32_stream.sv"
HAND = [
 ("stream: register initial value is 0xFFFFFFFE", "if (rst) begin st <= 32'hFFFFFFFF; out_valid <= 1'b0; out_good <= 1'b0; out_crc <= 32'd0; end\n        else begin\n            out_valid <= in_valid && in_last;", "if (rst) begin st <= 32'hFFFFFFFE; out_valid <= 1'b0; out_good <= 1'b0; out_crc <= 32'd0; end\n        else begin\n            out_valid <= in_valid && in_last;"),
 ("stream: the register is not restarted after a frame", "if (in_last) begin st <= 32'hFFFFFFFF; out_crc <= ~nx; out_good <= (~nx == 32'h2144DF1C); end", "if (in_last) begin st <= nx; out_crc <= ~nx; out_good <= (~nx == 32'h2144DF1C); end"),
 ("stream: the output is not inverted", "out_crc <= ~nx; out_good <= (~nx == 32'h2144DF1C);", "out_crc <= nx; out_good <= (~nx == 32'h2144DF1C);"),
 ("stream: the residue constant is wrong", "out_good <= (~nx == 32'h2144DF1C); end\n                else st <= nx;", "out_good <= (~nx == 32'h2144DF1D); end\n                else st <= nx;"),
 ("stream: out_valid ignores in_last", "out_valid <= in_valid && in_last;\n            if (in_valid) begin\n                if (in_last) begin st <= 32'hFFFFFFFF; out_crc <= ~nx", "out_valid <= in_valid;\n            if (in_valid) begin\n                if (in_last) begin st <= 32'hFFFFFFFF; out_crc <= ~nx"),
 ("stream: the register updates when in_valid is low", "if (in_valid) begin\n                if (in_last) begin st <= 32'hFFFFFFFF; out_crc <= ~nx; out_good <= (~nx == 32'h2144DF1C); end\n                else st <= nx;\n            end", "begin\n                if (in_last) begin st <= 32'hFFFFFFFF; out_crc <= ~nx; out_good <= (~nx == 32'h2144DF1C); end\n                else st <= nx;\n            end"),
 ("comb: 4-byte case uses the 3-byte step", "4'd4: n = step4(c, d);", "4'd4: n = step3(c, d);"),
 ("fast: the snapshot is taken one cycle late", "st_s <= st;\n            if (v2)", "st_s <= (v2 && !last2) ? st : st_s;\n            if (v2)"),
 ("fast: the last-beat byte count is not delayed with the data", "v_s <= v2 && last2; nb_s <= nb2;", "v_s <= v2 && last2; nb_s <= nb1;"),
 ("fast: the output valid is one stage early", "out_valid <= v5; out_crc", "out_valid <= v_s; out_crc"),
 ("fast: the state is not restarted after the last beat", "if (v2) begin if (last2) st <= 32'hFFFFFFFF;", "if (v2) begin if (last2) st <= st;"),
 ("fast: reset does not clear the stage-2 valid", "if (rst) begin v1 <= 1'b0; v2 <= 1'b0; v_s <= 1'b0;", "if (rst) begin v1 <= 1'b0; v_s <= 1'b0;"),
]
EQUIV = [
 ("comb: a byte count of zero is treated as 1 (the interface never offers a valid beat with zero bytes)", "default: n = c;", "4'd0: n = step1(c, d);\n            default: n = c;"),
 ("fast: the loop uses B for the beat's own byte count instead of for a full beat (every beat except the last is full by the interface rule)", "else st <= a_loop ^ pf2; end", "else st <= a_loop ^ pl2; end"),
]
def terms_mutants(text, seed=7, per_fn=(("step8", 12), ("step3", 8), ("step1", 6))):
    """Deletes one XOR term from one equation: sample lines of the form `stepK[j] = a ^ b ^ ...;`."""
    rng = random.Random(seed); out = []
    for fn, n in per_fn:
        lines = [(m.start(), m.group(0)) for m in re.finditer(rf"^\s+{fn}\[\d+\] = .*;$", text, re.M)]
        for _ in range(n):
            pos, line = rng.choice(lines); parts = line.strip().rstrip(";").split(" = ")[1].split(" ^ ")
            if len(parts) < 2: continue
            k = rng.randrange(len(parts)); new_rhs = " ^ ".join(parts[:k] + parts[k + 1:]); lhs = line.strip().split(" = ")[0]
            out.append((f"term deleted: {lhs} loses {parts[k]}", line, "            " + lhs + " = " + new_rhs + ";"))
    return out
def battery(root):
    def sim(w, fast, frames, seed):
        ins = g.schedule(frames, w, seed); g.write_vectors(os.path.join(root, "out", "crc_vec.hex"), ins, g.expected(ins, w, 5 if fast else 1), w)
        rc, o = hw.sim_icarus([F, "tb/crc_tb.sv"], "crc_tb", root=root, defines=(f"W={w}", f"NC={len(ins)}", f"FAST={fast}")); return rc == 0 and "PASS" in o
    for fast in (0, 1):
        for w in (64, 32, 8):
            if not sim(w, fast, g.make_frames(1, 40) + g.frames_all_lengths(1, 24, 3), 1): return f"W={w} {'fast' if fast else 'stream'}"
    return None
def one(m):
    label, old, new = m; d = tempfile.mkdtemp(prefix="mut7_")
    for sub in ("rtl", "tb", "out", "model"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub), ignore=shutil.ignore_patterns("*.json", "*_synth.log", "*.hex"))
    p = os.path.join(d, F); s = open(p).read()
    if s.count(old) != 1: shutil.rmtree(d, ignore_errors=True); return label, f"BAD ANCHOR ({s.count(old)} occurrences)"
    open(p, "w").write(s.replace(old, new)); r = battery(d); shutil.rmtree(d, ignore_errors=True); return label, ("NOT CAUGHT" if r is None else "caught by: " + r)
if __name__ == "__main__":
    print("NOTE: this script deliberately breaks copies of the RTL. 'caught' lines are EXPECTED: they show the battery notices the mistake.")
    base = battery(flow.ROOT); print("unmutated design passes the whole battery:", base is None, "" if base is None else base)
    text = open(os.path.join(flow.ROOT, F)).read(); muts = HAND + [(l, o, n) for l, o, n in terms_mutants(text)]
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(one, muts)); eq = list(ex.map(one, EQUIV))
    caught = 0
    for label, st in res: print(f"  {label}: {st}"); caught += st.startswith("caught")
    print(f"mutants caught: {caught} of {len(muts)}  ({len(HAND)} hand-written, {len(muts) - len(HAND)} deleted XOR terms)")
    print("equivalent changes (they differ only on inputs the interface rule forbids: listed apart, see the page):")
    for label, st in eq: print(f"  {label}: {st}")
    sys.exit(0 if base is None and caught == len(muts) and all(s == "NOT CAUGHT" for _, s in eq) else 1)
