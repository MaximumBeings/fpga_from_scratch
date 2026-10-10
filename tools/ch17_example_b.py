#!/usr/bin/env python3
"""Chapter 17, example B: the two prices of a wide beat. (1) The tail: a packet of B bytes needs ceil(B / W) beats, so the last beat is partly empty. Measured on the RTL (W = 8, back-to-back packets, no idle cycles): cycles per packet and the fraction of the bus used, against the derived ceil(B / W). (2) The framing rule: a block that is shorter than a beat can complete in the same beat as the block before it, which the parser does not allow (error 3, the packet is abandoned). Measured by the model on random alignments (the RTL is compared on a sample): the probability that a block of L bytes of body trips the rule, against the derived max(0, W - L - 2) / W."""
import os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import itch_gold as I, wide_gold as WG, ch17_run as C
if __name__ == "__main__":
    W = 8; rng = random.Random(9); lat = {1: 1}.get(C.VERSION, 2)
    print(f"== 1. the tail of a packet (W = {W}, 30 identical packets back to back, no idle cycles, version {C.VERSION}: output latency {lat} cycle(s))")
    print(f"  {'messages':>8s} {'bytes':>6s} | {'beats':>6s} {'cycles per packet (measured)':>29s} {'bus used':>9s} | {'derived beats':>13s} {'derived bus used':>17s}")
    for nmsg in (1, 2, 3, 5, 12, 40):
        msgs = [I.build_msg(rng, "D") for _ in range(nmsg)]; pk = I.build_packet(rng, msgs); lines, packets = WG.schedule(rng, [dict(data=pk, eop=True)] * 30, W, gap=0, stray=0, between=(0, 0))
        got = C.parse_out(C.sim(lines, W, rtl="rtl/mold_wide.sv")); ends = [e[1] for e in got if e[0] == "P"]; first = packets[0]["bytes"][0][0]
        cyc = (ends[-1] - first - (lat - 1)) / len(packets) if len(ends) == len(packets) else float("nan"); beats = -(-len(pk) // W)
        print(f"  {nmsg:8d} {len(pk):6d} | {beats:6d} {cyc:29.2f} {len(pk) / (cyc * W) * 100:8.1f}% | {beats:13d} {len(pk) / (beats * W) * 100:16.1f}%")
    print("\n== 2. the framing rule: a packet of random-length messages, then ONE erroneous block (unknown type) of L bytes (body, type byte included), at a random alignment (a random number of random messages before it); 2,000 packets per cell")
    print(f"  {'W':>2s} {'L (bytes)':>10s} | {'measured P(framing error)':>26s} {'derived max(0, W - L - 2) / W':>31s}")
    for Wd in (2, 4, 8, 16):
        for L in (0, 1, 2, 3, 4, 6, 8, 14):
            n = 0; T = 2000
            for _ in range(T):
                msgs = [I.build_msg(rng, rng.choice("ADESXUPF")) for _ in range(rng.randint(1, 4))] + [bytes([ord("Z")]) + bytes(rng.getrandbits(8) for _ in range(L - 1)) if L else b""]
                pk = I.build_packet(rng, msgs); _, packets = WG.schedule(rng, [dict(data=pk, eop=True)], Wd, gap=0, stray=0, between=(0, 0)); n += any(e[0] == "X" for e in WG.decode(packets))
            print(f"  {Wd:2d} {L:10d} | {n / T * 100:25.1f}% {max(0, Wd - L - 2) / Wd * 100:30.1f}%")
    print("  (a block of L bytes of body is L + 2 bytes on the wire; it ends in the same beat as the block before it when that block's last byte is early enough in its beat. For W = 8 only blocks of up to 5 bytes can; a valid ITCH message has at least 12, so no valid traffic trips the rule at W <= 14; at W = 16 two short valid messages (a 14-byte System Event after another block) can, which is the 3.1% in the last row. The measured values are a few points above the derived ones because the derivation assumes the previous block ends at a uniformly random lane; the header (20 bytes) and the message lengths (all 14 to 46 bytes on the wire) make the alignment slightly non-uniform)")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    print("\n== 3. the same on the RTL: 40 packets of that kind (W = 8, L = 0 to 5) through the parser against the model")
    pks = []
    for _ in range(40):
        L = rng.randint(0, 5); msgs = [I.build_msg(rng, rng.choice("ADESXUPF")) for _ in range(rng.randint(1, 4))] + [bytes([ord("Z")]) + bytes(rng.getrandbits(8) for _ in range(L - 1)) if L else b""]; pks.append(dict(data=I.build_packet(rng, msgs), eop=True))
    lines, packets = WG.schedule(rng, pks, W, gap=0.1); err = C.compare(C.parse_out(C.sim(lines, W, rtl="rtl/mold_wide.sv")), WG.decode(packets, lat)); print(f"  {len(packets)} packets, {sum(1 for e in WG.decode(packets, lat) if e[0] == 'X')} framing errors: " + ("RTL equals the model" if err is None else "DIFFERENT: " + err))
