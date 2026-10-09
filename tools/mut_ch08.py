#!/usr/bin/env python3
"""Chapter 8: test the tests. Mutants of rtl/mac.sv (receive MAC, transmit MAC, frame buffer, the loss handling of the receive path). The battery: mac_rx against the specification on two fault-heavy seeds; mac_rx_path with a fast core (all good frames delivered exactly) and a slow core (integrity: nothing corrupt) and a small buffer (overflow drops); the transmit wire format (frames of every interesting size, source at two speeds); the loopback. Usage: mut_ch08.py"""
import concurrent.futures as cf, os, re, shutil, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, hw, mac_gold as g
M = "rtl/mac.sv"
F = ["rtl/crc32_stream.sv", "rtl/cdc_sync.sv", "rtl/cdc.sv", "rtl/mac.sv"]
MUTANTS = [
 ("rx: the SFD value is 0xD4", "else if (rxd == 8'hD5) begin st <= DATA;", "else if (rxd == 8'hD4) begin st <= DATA;"),
 ("rx: a start needs no preamble byte (IDLE goes straight to PRE on any byte)", "IDLE: if (rx_dv) st <= (rxd == 8'h55) ? PRE : IGN;", "IDLE: if (rx_dv) st <= PRE;"),
 ("rx: a frame with a bad first byte is not ignored", "else st <= IGN;\n            IGN:", "else st <= PRE;\n            IGN:"),
 ("rx: the FCS delay line is three bytes, not four", "if (cnt >= 12'd4) begin", "if (cnt >= 12'd3) begin"),
 ("rx: the minimum length is 63", "(cnt < 12'd64)", "(cnt < 12'd63)"),
 ("rx: the minimum length is 65", "(cnt < 12'd64)", "(cnt < 12'd65)"),
 ("rx: the maximum length is 1523", "(cnt > 12'd1522)", "(cnt > 12'd1523)"),
 ("rx: the maximum length is not checked", "|| (cnt > 12'd1522)", ""),
 ("rx: rx_er is not remembered", "ersn <= ersn | rx_er;", "ersn <= rx_er;"),
 ("rx: the residue constant is wrong", "(crc != 32'hDEBB20E3)", "(crc != 32'hDEBB20E2)"),
 ("rx: the CRC register is not restarted at the SFD", "cnt <= '0; ersn <= 1'b0; crc <= 32'hFFFFFFFF; held_v <= 1'b0; end", "cnt <= '0; ersn <= 1'b0; held_v <= 1'b0; end"),
 ("rx: the end of the frame does not mark last", "m_data <= held_d; m_last <= 1'b1; m_bad <= bad_now; end", "m_data <= held_d; m_last <= 1'b0; m_bad <= bad_now; end"),
 ("rx: bad is never raised", "m_last <= 1'b1; m_bad <= bad_now; end", "m_last <= 1'b1; m_bad <= 1'b0; end"),
 ("rx: the held byte is dropped at the end of the frame", "if (held_v) begin m_valid <= 1'b1; m_data <= held_d; m_last <= 1'b1;", "if (1'b0) begin m_valid <= 1'b1; m_data <= held_d; m_last <= 1'b1;"),
 ("fifo: a bad frame is committed", "if (in_bad) begin wptr <= cptr; n_bad <= n_bad + 1'b1; end", "if (1'b0) begin wptr <= cptr; n_bad <= n_bad + 1'b1; end"),
 ("fifo: a committed frame is visible at once (no cptr_r delay)", "assign out_valid = (rptr != cptr_r);", "assign out_valid = (rptr != cptr);"),
 ("fifo: full is detected one byte late", "assign full = (wptr + 1'b1) == rptr;", "assign full = (wptr + 2'd2) == rptr;"),
 ("fifo: an overflowing frame is not rolled back at its last byte", "if (in_last) begin wptr <= cptr; dropping <= 1'b0; if (in_bad", "if (in_last) begin dropping <= 1'b0; if (in_bad"),
 ("fifo: the read address does not advance with out_ready", "assign ra = (out_valid && out_ready) ? rptr + 1'b1 : rptr;", "assign ra = rptr;"),
 ("fifo: the last flag is dropped from the stored word", "mem[wptr] <= {in_last, in_data};", "mem[wptr] <= {1'b0, in_data};"),
 ("tx: preamble is six bytes", "if (k == 3'd6) st <= SFD;", "if (k == 3'd5) st <= SFD;"),
 ("tx: padding stops at 59 bytes", "if (len + 12'd1 >= 12'd60) begin st <= FCS;", "if (len + 12'd1 >= 12'd59) begin st <= FCS;"),
 ("tx: padding threshold is 61 (a 60-byte frame is padded)", "st <= (len + 12'd1 < 12'd60) ? PAD : FCS;", "st <= (len + 12'd1 < 12'd61) ? PAD : FCS;"),
 ("tx: the FCS is not inverted", "txd <= (k == 3'd0) ? ~crc[7:0] : (k == 3'd1) ? ~crc[15:8] : (k == 3'd2) ? ~crc[23:16] : ~crc[31:24];", "txd <= (k == 3'd0) ? crc[7:0] : (k == 3'd1) ? crc[15:8] : (k == 3'd2) ? crc[23:16] : crc[31:24];"),
 ("tx: the FCS is sent high byte first", "txd <= (k == 3'd0) ? ~crc[7:0] : (k == 3'd1) ? ~crc[15:8] : (k == 3'd2) ? ~crc[23:16] : ~crc[31:24];", "txd <= (k == 3'd0) ? ~crc[31:24] : (k == 3'd1) ? ~crc[23:16] : (k == 3'd2) ? ~crc[15:8] : ~crc[7:0];"),
 ("tx: the gap is 11 cycles", "st <= IDLE; gap <= 4'd11; end", "st <= IDLE; gap <= 4'd10; end"),
 ("tx: the gap is 13 cycles", "st <= IDLE; gap <= 4'd11; end", "st <= IDLE; gap <= 4'd12; end"),
 ("tx: the padding bytes are not included in the CRC", "PAD: begin tx_en <= 1'b1; txd <= 8'd0; crc <= nx;", "PAD: begin tx_en <= 1'b1; txd <= 8'd0;"),
 ("tx: the CRC is not restarted for each frame", "SFD: begin tx_en <= 1'b1; txd <= 8'hD5; st <= DATA; crc <= 32'hFFFFFFFF; len <= '0; end", "SFD: begin tx_en <= 1'b1; txd <= 8'hD5; st <= DATA; len <= '0; end"),
 ("path: a lost byte does not mark the frame bad", "wd = {m_bad | lost, m_last, m_data};", "wd = {m_bad, m_last, m_data};"),
 ("path: a lost last byte gets no terminator", "if (m_last) fix <= 1'b1; end", "end"),
 ("path: the loss flag is not cleared at the end of a frame", "else if (m_valid && !af_full && !fix && m_last) lost <= 1'b0;", ""),
]
def battery(root):
    def sim(files, top, defines): rc, o = hw.sim_icarus(files, top, root=root, defines=defines); return o
    for seed in (3, 5):
        it = g.make_items(seed, 70, {"good": 30, "badfcs": 20, "runt": 15, "giant": 8, "er": 12, "shortpre": 8, "nosfd": 7, "nopre": 6}); st = g.phy_stream(it, seed); g.write_stream(os.path.join(root, "out", "mac_stream.hex"), st)
        if g.parse_frames(sim(["rtl/crc32_stream.sv", "rtl/mac.sv", "tb/mac_rx_tb.sv"], "mac_rx_tb", (f"NC={len(st)}",))) != g.spec_rx(st): return f"mac_rx seed {seed}"
    import random
    it = g.make_items(1, 60); st = g.phy_stream(it); g.write_stream(os.path.join(root, "out", "mac_stream.hex"), st); good = [p for p, b in g.spec_rx(st) if not b]
    def subseq(a, b): i = iter(b); return all(any(x == y for y in i) for x in a)
    o = sim(F + ["tb/mac_path_tb.sv"], "mac_path_tb", (f"NC={len(st)}", "COREP=6400"))
    if [p for p, _ in g.parse_frames(o)] != good: return "rx path, fast core: not all good frames delivered exactly"
    o = sim(F + ["tb/mac_path_tb.sv"], "mac_path_tb", (f"NC={len(st)}", "COREP=8200"))
    got = [p for p, _ in g.parse_frames(o)]
    if not subseq(got, good): return "rx path, slow core: a corrupt frame was delivered"
    if len(got) == len(good): return "rx path, slow core: nothing was lost (the test lost its teeth)"
    o = sim(F + ["tb/mac_path_tb.sv"], "mac_path_tb", (f"NC={len(st)}", "COREP=6400", "AW=8"))
    got = [p for p, _ in g.parse_frames(o)]
    if not subseq(got, good): return "rx path, small buffer: a corrupt frame was delivered"
    it = g.recovery_items(); st2 = g.phy_stream(it); g.write_stream(os.path.join(root, "out", "mac_stream.hex"), st2); good2 = [p for p, b in g.spec_rx(st2) if not b]
    o = sim(F + ["tb/mac_path_tb.sv"], "mac_path_tb", (f"NC={len(st2)}", "COREP=8600")); got2 = [p for p, _ in g.parse_frames(o)]
    if [x for x in got2 if len(x) < 200] != [x for x in good2 if len(x) < 200]: return "rx path, recovery after a loss"
    for aw, spaced, rdy in ((4, True, 100), (4, False, 50)):
        d = 2 ** aw; fr_, cyc = g.ff_stimulus(1, d - 1, spaced=spaced); g.write_ff(os.path.join(root, "out", "ff_stim.hex"), cyc)
        o = sim(["rtl/crc32_stream.sv", "rtl/mac.sv", "tb/ff_tb.sv"], "ff_tb", (f"NC={len(cyc)}", f"AW={aw}", f"RDY={rdy}")); got3 = [p for p, _ in g.parse_frames(o)]; m_ = re.search(r"STATS (.*)", o)
        if not m_: return "frame_fifo unit: no result"
        st3 = [int(x) for x in m_.group(1).split()]
        if spaced:
            exp3 = [f for f, b in fr_ if not b and len(f) <= d - 1]
            if got3 != exp3 or st3 != [len(exp3), sum(1 for f, b in fr_ if b and len(f) <= d - 1), sum(1 for f, b in fr_ if len(f) > d - 1)]: return "frame_fifo unit, spaced"
        elif not subseq(got3, [f for f, b in fr_ if not b]) or sum(st3) != len(fr_): return "frame_fifo unit, back to back"
    fr = g.tx_frames(2, 14); g.write_tx(fr, os.path.join(root, "out", "tx_bytes.hex"), os.path.join(root, "out", "tx_lens.hex")); exp = [g.spec_tx(b) for b in fr]
    for src in (100, 30):
        o = sim(F + ["tb/mac_tx_tb.sv"], "mac_tx_tb", (f"NF={len(fr)}", f"SRC={src}", "LOOP=1"))
        wire = [w for w, _ in g.parse_frames(o, "WIRE")]; gaps = [int(x) for x in re.findall(r"GAP (\d+)", o)]
        if wire != exp: return f"tx wire format, source {src}%"
        if gaps and min(gaps) != 12: return f"tx gap (min {min(gaps)})"
        if [p for p, _ in g.parse_frames(o)] != [g.pad(b) for b in fr]: return f"loopback, source {src}%"
    return None
def one(m):
    label, old, new = m; d = tempfile.mkdtemp(prefix="mut8_")
    for sub in ("rtl", "tb", "out", "model"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub), ignore=shutil.ignore_patterns("*.json", "*_synth.log", "*.hex"))
    p = os.path.join(d, M); s = open(p).read()
    if s.count(old) != 1: shutil.rmtree(d, ignore_errors=True); return label, f"BAD ANCHOR ({s.count(old)} occurrences)"
    open(p, "w").write(s.replace(old, new)); r = battery(d); shutil.rmtree(d, ignore_errors=True); return label, ("NOT CAUGHT" if r is None else "caught by: " + r)
if __name__ == "__main__":
    print("NOTE: this script deliberately breaks copies of the RTL. 'caught' lines are EXPECTED: they show the battery notices the mistake.")
    base = battery(flow.ROOT); print("unmutated design passes the whole battery:", base is None, "" if base is None else base)
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(one, MUTANTS))
    caught = 0
    for label, st in res: print(f"  {label}: {st}"); caught += st.startswith("caught")
    print(f"mutants caught: {caught} of {len(MUTANTS)}")
    sys.exit(0 if base is None and caught == len(MUTANTS) else 1)
