#!/usr/bin/env python3
"""Chapter 16: the specification of the MoldUDP64 + ITCH parser, written from the protocol and NOT from the grammar file or the generator: the message layouts are `struct` format strings of their own (the same numbers, written again; if the two copies disagree a test fails, if the author misread the protocol in both, nothing does).
decode(packets) -> the events the parser must produce, with the cycle in which each appears. A packet is a list of (cycle, byte) and a flag `eop` (False: the packet is abandoned by the next sop). Events:
  ("M", cycle, type, err, idx, seq, {field: value})   a message, the cycle after its last byte (a zero-length block: the cycle after the second length byte)
  ("P", cycle, trunc, cntbad, session, count)         the packet ended: the cycle after the eop byte
err: 0 ok, 1 unknown type, 2 the block's length is not the type's (or is 0). Fields are present only for err = 0. A block that is cut off by the end of the packet produces no message and makes the packet `trunc`."""
import random, struct
FMT = {"S": ">HH6sc", "A": ">HH6sQcI8sI", "F": ">HH6sQcI8sII", "E": ">HH6sQIQ", "X": ">HH6sQI", "D": ">HH6sQ", "U": ">HH6sQQII", "P": ">HH6sQcI8sIQ"}
NAMES = {"S": ["locate", "tracking", "ts", "event"], "A": ["locate", "tracking", "ts", "ref", "side", "shares", "stock", "price"], "F": ["locate", "tracking", "ts", "ref", "side", "shares", "stock", "price", "mpid"],
         "E": ["locate", "tracking", "ts", "ref", "shares", "match"], "X": ["locate", "tracking", "ts", "ref", "shares"], "D": ["locate", "tracking", "ts", "ref"], "U": ["locate", "tracking", "ts", "ref", "newref", "shares", "price"],
         "P": ["locate", "tracking", "ts", "ref", "side", "shares", "stock", "price", "match"]}
def _codes(fmt):
    out = []; i = 1
    while i < len(fmt):
        if fmt[i].isdigit(): out.append(fmt[i]); i += 2
        else: out.append(fmt[i]); i += 1
    return out
WIDTH = {n: {"H": 2, "6": 6, "Q": 8, "c": 1, "I": 4, "8": 8}[ch] for t in FMT for n, ch in zip(NAMES[t], _codes(FMT[t]))}    # bytes per field name
def body_fields(t, body):
    vals = struct.unpack(FMT[chr(t)], body[1:]); return {n: (int.from_bytes(v, "big") if isinstance(v, bytes) else v) for n, v in zip(NAMES[chr(t)], vals)}
def decode(packets):
    ev = []
    for pk in packets:
        b = [x for _, x in pk["bytes"]]; cy = [c for c, _ in pk["bytes"]]; eop = pk["eop"]; n = len(b); trunc = False; nblk = 0
        if n < 20: trunc = True; pos = n
        else:
            session = int.from_bytes(bytes(b[0:10]), "big"); seq = int.from_bytes(bytes(b[10:18]), "big"); count = int.from_bytes(bytes(b[18:20]), "big"); pos = 20; idx = 0
            while pos < n:
                if pos + 2 > n: trunc = True; break
                L = b[pos] * 256 + b[pos + 1]
                if L == 0: ev.append(("M", cy[pos + 1] + 1, 0, 2, idx, seq, {})); idx += 1; nblk += 1; pos += 2; continue
                if pos + 2 + L > n: trunc = True; break
                body = bytes(b[pos + 2: pos + 2 + L]); t = body[0]; end = cy[pos + 1 + L] + 1
                if chr(t) not in FMT: ev.append(("M", end, t, 1, idx, seq, {}))
                elif struct.calcsize(FMT[chr(t)]) + 1 != L: ev.append(("M", end, t, 2, idx, seq, {}))
                else: ev.append(("M", end, t, 0, idx, seq, body_fields(t, body)))
                idx += 1; nblk += 1; pos += 2 + L
        if eop:
            if n >= 20: ev.append(("P", cy[-1] + 1, int(trunc), int((not trunc) and nblk != count and count != 0xFFFF), session, count))
            else: ev.append(("P", cy[-1] + 1, 1, 0, None, None))
    return ev
# ------------------------------------------------------------------ building packets
def build_msg(rng, t, **ov):
    f = {"locate": rng.getrandbits(16), "tracking": rng.getrandbits(16), "ts": rng.getrandbits(48), "ref": rng.getrandbits(64), "newref": rng.getrandbits(64), "side": rng.choice(b"BS"), "shares": rng.getrandbits(32), "stock": int.from_bytes(rng.choice([b"AAPL    ", b"MSFT    ", b"ZVZZT   ", b"SPY     "]), "big"),
         "price": rng.getrandbits(32), "match": rng.getrandbits(64), "event": rng.choice(b"OSQMEC"), "mpid": int.from_bytes(rng.choice([b"GSCO", b"MSCO", b"NITE"]), "big")}; f.update(ov); out = bytes([ord(t)]); vals = []
    parts = []
    for n, ch in zip(NAMES[t], _codes(FMT[t])):
        v = f[n]; parts.append(v.to_bytes({"H": 2, "6": 6, "Q": 8, "c": 1, "I": 4, "8": 8}[ch], "big"))
    return out + b"".join(parts)
def build_packet(rng, msgs, seq=None, session=b"NASDAQ0001", count=None, **_):
    seq = rng.getrandbits(64) if seq is None else seq; c = len(msgs) if count is None else count
    return session + seq.to_bytes(8, "big") + c.to_bytes(2, "big") + b"".join(len(m).to_bytes(2, "big") + m for m in msgs)
TYPES = list(FMT)
# ------------------------------------------------------------------ stimulus: one line per cycle
def schedule(rng, pkts, gap=0.1, stray=0.05, between=(0, 3)):
    """pkts: list of dict(data=bytes, eop=bool, reset_at=None or a byte index). -> (lines, packets with the cycle of every byte). A line is (valid, sop, eop, data, rst). Idle cycles (probability `gap` per byte) carry random junk in the unused signals; stray bytes (valid, no sop, sometimes with eop) fall between packets, but not after a packet that was left open (no eop): the parser takes those for its continuation. With reset_at = i the reset is pulled after byte i - 1; the rest of the packet arrives as stray bytes (its eop too) and the packet is the bytes before the reset, without an eop."""
    lines = []; out = []; open_ = False
    def idle(): lines.append((0, rng.getrandbits(1), rng.getrandbits(1), rng.getrandbits(8), 0))
    for pk in pkts:
        for _ in range(rng.randint(*between)):
            if rng.random() < stray and not open_: lines.append((1, 0, 1 if rng.random() < .3 else 0, rng.getrandbits(8), 0))
            else: idle()
        by = []; ra = pk.get("reset_at"); n = len(pk["data"])
        for i, x in enumerate(pk["data"]):
            while rng.random() < gap: idle()
            if ra is not None and i == ra: lines.append((0, 0, 0, 0, 1))
            if ra is not None and i >= ra: lines.append((1, 0, 1 if (pk["eop"] and i == n - 1) else 0, x, 0)); continue
            by.append((len(lines), x)); lines.append((1, 1 if i == 0 else 0, 1 if (pk["eop"] and i == n - 1) else 0, x, 0))
        out.append(dict(bytes=by, eop=pk["eop"] and ra is None)); open_ = (not pk["eop"]) and ra is None                    # a packet without eop stays open until the next sop: stray bytes would be parsed as its continuation
    for _ in range(4): idle()
    return lines, out
def write_stim(path, lines):
    with open(path, "w") as f:
        for v, s_, e, d, r in lines: f.write("%03x\n" % ((v << 11) | (s_ << 10) | (e << 9) | (r << 8) | d))
    return len(lines)
def random_packets(rng, n, maxmsg=6, p_err=0.15):
    """A mix of well-formed packets and packets with every kind of fault: an unknown type, a wrong length, a zero-length block, a one-byte block, a block longer than 255 bytes, a count that is wrong, a packet cut short (with and without eop), a header-only packet, a one-byte packet, a reset in the middle of a packet."""
    pk = []
    for _ in range(n):
        msgs = [build_msg(rng, rng.choice(TYPES)) for _ in range(rng.randint(0, maxmsg))]; r = rng.random(); eop = True; cnt = None; ra = None
        if msgs and r < p_err * .2: i = rng.randrange(len(msgs)); msgs[i] = bytes([rng.choice([ord("Z"), 0, 255, ord("a")])]) + msgs[i][1:]
        elif msgs and r < p_err * .35: i = rng.randrange(len(msgs)); msgs[i] = msgs[i] + bytes([rng.getrandbits(8)]) if rng.random() < .5 else msgs[i][:-1]
        elif msgs and r < p_err * .5: i = rng.randrange(len(msgs)); msgs[i] = rng.choice([b"", bytes([rng.choice(b"ASDZ")]), bytes(rng.getrandbits(8) for _ in range(rng.randint(250, 520)))])
        elif r < p_err * .6: cnt = rng.choice([0, 1, 2, 7, 0xFFFF])
        data = build_packet(rng, msgs, count=cnt)
        if msgs and p_err * .6 <= r < p_err * .75: data = data[:rng.randrange(1, len(data))]
        elif p_err * .75 <= r < p_err * .85: eop = False
        elif p_err * .85 <= r < p_err * .95: ra = rng.randrange(1, len(data))
        elif p_err * .95 <= r < p_err: data = data[:rng.randrange(1, 22)]
        pk.append(dict(data=data, eop=eop, reset_at=ra))
    return pk
if __name__ == "__main__":
    rng = random.Random(1); ms = [build_msg(rng, t) for t in "SAFEXDUP"]
    assert [len(m) for m in ms] == [12, 36, 40, 31, 23, 19, 35, 44]
    pk = build_packet(rng, ms, seq=7); bytes_ = [(i, x) for i, x in enumerate(pk)]
    ev = decode([dict(bytes=bytes_, eop=True)]); assert len(ev) == 9 and ev[-1][:4] == ("P", len(pk), 0, 0) and [e[3] for e in ev[:-1]] == [0] * 8 and ev[1][6]["stock"] > 0
    ev = decode([dict(bytes=bytes_[:-3], eop=True)]); assert ev[-1][2] == 1 and len(ev) == 8                          # cut inside the last block: that message is lost, the packet is truncated
    pk2 = build_packet(rng, ms[:2], count=3); ev = decode([dict(bytes=[(i, x) for i, x in enumerate(pk2)], eop=True)]); assert ev[-1][3] == 1       # count says 3, two blocks
    z = build_packet(rng, [b"", b"A", ms[5]]); ev = decode([dict(bytes=[(i, x) for i, x in enumerate(z)], eop=True)]); assert [e[3] for e in ev[:3]] == [2, 2, 0] and ev[0][2] == 0 and ev[1][2] == ord("A")        # a zero-length block, a block of one byte, a good one
    print("itch_gold hand-checked scenarios passed")
