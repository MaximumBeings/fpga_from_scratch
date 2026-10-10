#!/usr/bin/env python3
"""Chapter 17: the specification of the W-bytes-per-beat MoldUDP64 + ITCH parser, and its stimulus. Same protocol model as Chapter 16 (itch_gold.py), with the two things a beat adds:
  * the CYCLE of an event is that of the BEAT that contains the last byte of the block (+ lat, the latency of the design: 1 for version 1, 2 for version 2), not of the byte;
  * at most one block may COMPLETE in a beat. A second block completing in the same beat is a FRAMING ERROR (err 3): an event ("X", cycle, idx) is produced, the rest of the packet is ignored, and its packet end reports trunc. (Valid messages are 12 bytes or more plus 2 of length, so for W <= 8 only erroneous blocks can do this.)
decode(packets, lat) -> events ("M", cycle, type, err, idx, seq, fields), ("X", cycle, idx), ("P", cycle, trunc, cntbad, session, count). A packet is dict(bytes=[(cycle, byte)], eop). Bytes of one beat share a cycle."""
import os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import itch_gold as I
def decode(packets, lat=1):
    ev = []
    for pk in packets:
        b = [x for _, x in pk["bytes"]]; cy = [c for c, _ in pk["bytes"]]; eop = pk["eop"]; n = len(b); trunc = False; nblk = 0; dead = False; last = None
        if n < 20: trunc = True; pos = n
        else:
            session = int.from_bytes(bytes(b[0:10]), "big"); seq = int.from_bytes(bytes(b[10:18]), "big"); count = int.from_bytes(bytes(b[18:20]), "big"); pos = 20; idx = 0
            while pos < n:
                if pos + 2 > n: trunc = True; break
                L = b[pos] * 256 + b[pos + 1]
                if L == 0: end = cy[pos + 1] + lat; last_byte = pos + 1; nxt = pos + 2
                else:
                    if pos + 2 + L > n: trunc = True; break
                    end = cy[pos + 1 + L] + lat; last_byte = pos + 1 + L; nxt = pos + 2 + L
                if last == end:                                                                   # a second completion in this beat
                    ev.append(("X", end, idx)); dead = True; break
                last = end
                if L == 0: ev.append(("M", end, 0, 2, idx, seq, {}))
                else:
                    body = bytes(b[pos + 2: pos + 2 + L]); t = body[0]
                    if chr(t) not in I.FMT: ev.append(("M", end, t, 1, idx, seq, {}))
                    elif len(body) != 1 + sum(I.WIDTH[nm] for nm in I.NAMES[chr(t)]): ev.append(("M", end, t, 2, idx, seq, {}))
                    else: ev.append(("M", end, t, 0, idx, seq, I.body_fields(t, body)))
                idx += 1; nblk += 1; pos = nxt
        if eop:
            if n >= 20: ev.append(("P", cy[-1] + lat, int(trunc or dead), int((not trunc) and (not dead) and nblk != count and count != 0xFFFF), session, count))
            else: ev.append(("P", cy[-1] + lat, 1, 0, None, None))
    return ev
def schedule(rng, pkts, W, gap=0.1, stray=0.05, between=(0, 3)):
    """pkts: list of dict(data, eop, reset_at). -> (lines, packets). A line is (valid, sop, eop, rst, nb, bytes). A packet is cut into beats of W bytes (the last may be shorter, and has the eop; a packet without eop is cut to whole beats, so that only a last beat is ever short). Idle cycles between beats (probability `gap`), stray beats between packets, and a reset before the beat in which `reset_at` falls (the rest of the packet then arrives as stray beats)."""
    lines = []; out = []; open_ = False
    def idle(): lines.append((0, rng.getrandbits(1), rng.getrandbits(1), 0, rng.getrandbits(4), [rng.getrandbits(8) for _ in range(W)]))
    for pk in pkts:
        for _ in range(rng.randint(*between)):
            if rng.random() < stray and not open_: lines.append((1, 0, 1 if rng.random() < .3 else 0, 0, rng.randint(1, W), [rng.getrandbits(8) for _ in range(W)]))
            else: idle()
        data = pk["data"]; eop = pk["eop"]; ra = pk.get("reset_at")
        if not eop and ra is None: data = data[: max(W, len(data) // W * W)]
        by = []; i = 0; first = True
        if ra is not None: ra = ra // W * W
        while i < len(data):
            while rng.random() < gap: idle()
            chunk = data[i:i + W]; last = i + W >= len(data)
            if ra is not None and i == ra: lines.append((0, 0, 0, 1, 0, [0] * W))
            if ra is not None and i >= ra: lines.append((1, 0, 1 if (eop and last) else 0, 0, len(chunk), list(chunk) + [rng.getrandbits(8) for _ in range(W - len(chunk))]))
            else:
                for k, x in enumerate(chunk): by.append((len(lines), x))
                lines.append((1, 1 if first else 0, 1 if (eop and last) else 0, 0, len(chunk), list(chunk) + [rng.getrandbits(8) for _ in range(W - len(chunk))]))
            first = False; i += W
        out.append(dict(bytes=by, eop=eop and ra is None)); open_ = (not eop) and ra is None
    for _ in range(4): idle()
    return lines, out
def write_stim(path, lines, W):
    with open(path, "w") as f:
        for v, s, e, r, nb, by in lines:
            d = 0
            for j, x in enumerate(by): d |= x << (8 * j)
            f.write("%0*x\n" % (2 * W + 2, (((((v << 3) | (s << 2) | (e << 1) | r) << 4) | nb) << (8 * W)) | d))
    return len(lines)
def alignment_packets(rng, n):
    """Packets that put ONE short or odd block at every alignment in the beat: 1 to 5 random valid messages, then one of: a zero-length block, a block of one byte, an unknown type of 3 or 4 bytes, a wrong-length block; then 1 or 2 valid messages."""
    pk = []
    for _ in range(n):
        pre = [I.build_msg(rng, rng.choice(I.TYPES)) for _ in range(rng.randint(1, 5))]; post = [I.build_msg(rng, rng.choice(I.TYPES)) for _ in range(rng.randint(1, 2))]
        odd = rng.choice([b"", bytes([rng.choice(b"ASDZ")]), b"Z" + bytes(rng.getrandbits(8) for _ in range(rng.choice([2, 3]))), I.build_msg(rng, "A")[:-rng.randint(1, 3)]])
        pk.append(dict(data=I.build_packet(rng, pre + [odd] + post), eop=True))
    return pk
if __name__ == "__main__":
    rng = random.Random(3); ms = [I.build_msg(rng, t) for t in "AD"]; pk = I.build_packet(rng, ms, seq=9)
    for W in (4, 8):
        lines, pks = schedule(rng, [dict(data=pk, eop=True)], W, gap=0, between=(0, 0)); ev = decode(pks)
        assert [e[0] for e in ev] == ["M", "M", "P"] and ev[0][1] == pks[0]["bytes"][20 + 2 + 35][0] + 1 and sum(1 for l in lines if l[3] == 0 and l[0]) == (len(pk) + W - 1) // W
    z = I.build_packet(rng, [b"", b"", ms[1]]); lines, pks = schedule(rng, [dict(data=z, eop=True)], 8, gap=0, between=(0, 0)); ev = decode(pks)
    assert [e[0] for e in ev] == ["M", "X", "P"] and ev[1][2] == 1 and ev[2][2] == 1                                  # two zero-length blocks complete in the same beat: framing error, packet abandoned
    print("wide_gold hand-checked scenarios passed")
