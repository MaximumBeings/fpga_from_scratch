#!/usr/bin/env python3
"""Chapter 8: the running designs. (1) lint; (2) mac_rx against the specification model on 8 seeds x 2 mixes (Icarus; Verilator on one); (3) mac_rx_path across two unrelated clocks, consumer speeds and buffer sizes: delivered frames against the good frames of the specification, with the INTEGRITY property (every frame delivered is byte-exact and in order, nothing corrupt); (4) mac_tx_path: the exact wire format, the gaps, with the source at three speeds; (5) transmit-to-receive loopback. Usage: ch08_run.py"""
import os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, mac_gold as g
R = flow.ROOT
F = ["rtl/crc32_stream.sv", "rtl/cdc_sync.sv", "rtl/cdc.sv", "rtl/mac.sv"]
def subseq(got, exp):
    it = iter(exp); return all(any(x == y for y in it) for x in got)
if __name__ == "__main__":
    print("== 1. lint gate (Verilator -Wall --lint-only, Yosys 'check')")
    for top, fs in (("mac_rx", ["rtl/crc32_stream.sv", "rtl/mac.sv"]), ("frame_fifo", ["rtl/crc32_stream.sv", "rtl/mac.sv"]), ("mac_tx", ["rtl/crc32_stream.sv", "rtl/mac.sv"]), ("mac_rx_path", F), ("mac_tx_path", ["rtl/crc32_stream.sv", "rtl/mac.sv"])):
        p = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", top] + fs, cwd=R, capture_output=True, text=True); w = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%Warning")]
        y = subprocess.run(["yosys", "-p", f"read_verilog -sv {' '.join(F)}; hierarchy -top {top}; proc; opt_clean; check"], cwd=R, capture_output=True, text=True).stdout
        print(f"  {top:12s} Verilator warnings: {len(w)}   Yosys check problems: {len([l for l in y.splitlines() if 'Found and reported' in l and ' 0 problems' not in l])}")
    print("\n== 2. mac_rx against the specification: every frame reported (bytes without FCS, bad flag) must equal the model's, in order")
    print(f"  {'mix':32s} {'seeds':>5s} {'frames (good/bad)':>20s} {'Icarus':>8s} {'Verilator':>10s}")
    for name, mix in (("default (60% good, faults)", None), ("fault-heavy (30% good)", {"good": 30, "badfcs": 20, "runt": 15, "giant": 8, "er": 12, "shortpre": 8, "nosfd": 7, "nopre": 6})):
        ok = 0; tot = 0; ng = nb = 0; v = "-"
        for seed in range(8):
            it = g.make_items(seed, 100, mix); st = g.phy_stream(it, seed); g.write_stream(os.path.join(R, "out", "mac_stream.hex"), st); exp = g.spec_rx(st)
            o = flow.sim_icarus(["rtl/crc32_stream.sv", "rtl/mac.sv", "tb/mac_rx_tb.sv"], "mac_rx_tb", defines=(f"NC={len(st)}",))[1]; tot += 1; ok += g.parse_frames(o) == exp; ng += sum(1 for _, b in exp if not b); nb += sum(1 for _, b in exp if b)
            if seed == 0: ov = flow.sim_verilator(["rtl/crc32_stream.sv", "rtl/mac.sv", "tb/mac_rx_tb.sv"], "mac_rx_tb", defines=(f"NC={len(st)}",))[1]; v = "PASS" if g.parse_frames(ov) == exp else "FAIL"
        print(f"  {name:32s} {tot:5d} {ng:10d} / {nb:<8d} {ok:4d} of {tot:<2d} {v:>10s}")
    it = g.make_items(1, 120); st = g.phy_stream(it); g.write_stream(os.path.join(R, "out", "mac_stream.hex"), st); good = [p for p, b in g.spec_rx(st) if not b]; nrec = len(g.spec_rx(st))
    print(f"\n== 3. mac_rx_path across clocks (PHY clock 8,000 ps = 125 MHz; core clock and consumer speed as shown; 120 frames offered, {nrec} recognised by the specification, {len(good)} of them good): delivered against the spec's good frames")
    print(f"  {'core period':>11s} {'consumer':>9s} {'buffer':>8s} | {'delivered':>9s} of {len(good)} {'exact+ordered':>14s} {'ok bad ovf lost':>20s}")
    for core, rdy, aw in ((6400, 100, 11), (6400, 60, 11), (8000, 100, 11), (8200, 100, 11), (9000, 100, 11), (6400, 100, 8), (6400, 100, 9)):
        o = flow.sim_icarus(F + ["tb/mac_path_tb.sv"], "mac_path_tb", defines=(f"NC={len(st)}", f"COREP={core}", f"RDY={rdy}", f"AW={aw}"))[1]; got = [p for p, _ in g.parse_frames(o)]; s = re.search(r"STATS (.*)", o).group(1)
        print(f"  {core:8d} ps {rdy:8d}% {2 ** aw:6d} B | {len(got):9d}        {'YES' if subseq(got, good) else 'NO: corrupt':>14s} {s:>20s}")
    it = g.recovery_items(); st2 = g.phy_stream(it); g.write_stream(os.path.join(R, "out", "mac_stream.hex"), st2); good2 = [p for p, b in g.spec_rx(st2) if not b]
    o = flow.sim_icarus(F + ["tb/mac_path_tb.sv"], "mac_path_tb", defines=(f"NC={len(st2)}", "COREP=8600"))[1]; got2 = [p for p, _ in g.parse_frames(o)]
    print(f"  recovery: 40 pairs of (a maximum frame, a gap, a small good frame), core 8,600 ps (the big ones overflow the crossing FIFO, the small ones fit): delivered {len(got2)} frames; all 40 small frames delivered exactly: {[x for x in got2 if len(x) < 200] == [x for x in good2 if len(x) < 200]}; nothing corrupt: {subseq(got2, good2)}")
    print("  'exact+ordered' = every delivered frame is byte-exact and the frames are a subsequence of the good frames: nothing corrupt, only whole frames missing")
    print("\n== 3b. frame_fifo alone (buffer of 16 and 32 bytes, so 15 and 31 can be held): frames of 1 byte to twice the buffer, 20% marked bad, with the source spaced so that the buffer is empty at each start (exact) and back to back with a slow reader (property)")
    def ffrun(aw, rdy, spaced, seed=1):
        d = 2 ** aw; fr, cyc = g.ff_stimulus(seed, d - 1, spaced=spaced); g.write_ff(os.path.join(R, "out", "ff_stim.hex"), cyc)
        o = flow.sim_icarus(["rtl/crc32_stream.sv", "rtl/mac.sv", "tb/ff_tb.sv"], "ff_tb", defines=(f"NC={len(cyc)}", f"AW={aw}", f"RDY={rdy}"))[1]
        return d, fr, [p for p, _ in g.parse_frames(o)], [int(x) for x in re.search(r"STATS (.*)", o).group(1).split()]
    for aw in (4, 5):
        d, fr, got, st = ffrun(aw, 100, True); exp = [f for f, b in fr if not b and len(f) <= d - 1]; want = [len(exp), sum(1 for f, b in fr if b and len(f) <= d - 1), sum(1 for f, b in fr if len(f) > d - 1)]
        print(f"  {d:3d} B, reader 100%, spaced: delivered {len(got)} frames = exactly the good frames that fit, in order: {got == exp};  counters ok/bad/ovf {st} expected {want}: {st == want}")
    for aw, rdy in ((4, 50), (5, 30)):
        d, fr, got, st = ffrun(aw, rdy, False); good = [f for f, b in fr if not b]
        print(f"  {d:3d} B, reader {rdy}%, back to back: delivered {len(got)} frames, all byte-exact and in order: {subseq(got, good)};  ok + bad + ovf = {sum(st)} of {len(fr)} offered")
    print("\n== 4. mac_tx_path: the wire format and the gaps (24 frames of 14 to 1,518 bytes, including the padding boundary; source at three speeds)")
    fr = g.tx_frames(1, 24); g.write_tx(fr, os.path.join(R, "out", "tx_bytes.hex"), os.path.join(R, "out", "tx_lens.hex")); exp = [g.spec_tx(b) for b in fr]
    print(f"  {'source speed':>12s} {'wire frames exact':>18s} {'min gap':>8s} {'underruns':>10s}")
    for src in (100, 40, 10):
        o = flow.sim_icarus(["rtl/crc32_stream.sv", "rtl/mac.sv", "tb/mac_tx_tb.sv"], "mac_tx_tb", defines=(f"NF={len(fr)}", f"SRC={src}", "LOOP=0"))[1]
        wire = [w for w, _ in g.parse_frames(o, "WIRE")]; gaps = [int(x) for x in re.findall(r"GAP (\d+)", o)]; s = re.search(r"STATS (\d+) (\d+) (\d+)", o)
        print(f"  {src:11d}% {'YES' if wire == exp else 'NO':>18s} {min(gaps):8d} {s.group(3):>10s}")
    print("  the wire format is the specification's byte sequence: 7 x 0x55, 0xD5, the body padded with zeros to 60 bytes, the FCS (zlib.crc32, low byte first); min gap 12 cycles = the inter-frame gap")
    print("\n== 5. loopback: transmitter output into the receive path (equal PHY clocks, core clock 6,400 ps): the frames delivered must equal the padded bodies")
    for src in (100, 40):
        o = flow.sim_icarus(F + ["tb/mac_tx_tb.sv"], "mac_tx_tb", defines=(f"NF={len(fr)}", f"SRC={src}", "LOOP=1"))[1]; got = [p for p, _ in g.parse_frames(o)]
        print(f"  source {src:3d}%: {len(got)} of {len(fr)} frames delivered, all equal to the padded bodies in order: {got == [g.pad(b) for b in fr]}")
