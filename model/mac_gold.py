#!/usr/bin/env python3
"""Chapter 8: the golden model of the Ethernet MAC at the byte interface (GMII-style: one byte per clock, rx_dv, rx_er), written from the standard, not from the RTL.
 spec_rx(stream)      what a receiver must make of a stream of PHY cycles: the list of (frame bytes without FCS, bad) for every frame whose start (preamble + SFD) it recognises
 spec_tx(frame)       the exact byte sequence a transmitter puts on the wire for one frame (preamble, SFD, data padded to 60 bytes, FCS) and the minimum gap after it
 phy_stream(items)    the cycle-by-cycle PHY signals (dv, er, byte) for a list of frames, with the faults a real PHY produces: bad FCS, runts, giants, rx_er, short preambles, missing SFD, short gaps
A frame of four bytes or fewer after the SFD is not reported at all (there is no data byte left to carry the end mark once the FCS is removed).
Rules used: minimum frame 64 bytes counting the FCS (60 without), maximum 1518 (1522 with one VLAN tag: the limit here is MAXLEN = 1522 bytes including FCS), preamble = at least one 0x55 before the SFD 0xD5, inter-frame gap 12 byte times."""
import random, zlib
MINLEN = 64; MAXLEN = 1522; IFG = 12; PRE = 0x55; SFD = 0xD5
def fcs(b): return zlib.crc32(b).to_bytes(4, "little")
def good_frame(body):
    """body: destination..payload (>= 60 bytes after padding). Returns body + FCS."""
    return body + fcs(body)
def pad(body): return body + bytes(max(0, 60 - len(body)))
def classify(frame, er):
    """frame: bytes after the SFD up to the end of rx_dv (FCS included). Returns bad flag."""
    if er: return True
    if len(frame) < MINLEN or len(frame) > MAXLEN: return True
    return zlib.crc32(frame) != 0x2144DF1C
def spec_rx(stream):
    """stream: list of (dv, er, byte) per cycle. Returns [(payload_without_fcs, bad)]. A frame starts at an SFD preceded by at least one 0x55 in the same rx_dv run; bytes before that that are not 0x55 make the whole run ignored."""
    out = []; i = 0; n = len(stream)
    while i < n:
        dv, er, b = stream[i]
        if not dv: i += 1; continue
        j = i; ok = False; seen55 = False
        while j < n and stream[j][0]:
            d = stream[j][2]
            if d == PRE: seen55 = True; j += 1; continue
            if d == SFD and seen55: ok = True; j += 1
            break
        if not ok:
            while j < n and stream[j][0]: j += 1
            i = j; continue
        k = j; data = bytearray(); e = False
        while k < n and stream[k][0]: data.append(stream[k][2]); e |= bool(stream[k][1]); k += 1
        if len(data) > 4: out.append((bytes(data[:-4]), classify(bytes(data), e)))      # a run of 4 bytes or fewer after the SFD has no byte to carry the end-of-frame mark: nothing is reported
        i = k
    return out
def spec_tx(body):
    """The byte sequence on the wire for one frame body (without FCS): preamble, SFD, padded body, FCS."""
    p = pad(body); return bytes([PRE] * 7 + [SFD]) + p + fcs(p)
def phy_stream(items, seed=1):
    """items: list of dicts {kind, body, gap}. kind in good | badfcs | runt | giant | er | shortpre | nosfd. Returns (stream, expected) where expected = spec_rx(stream) computed independently by construction (see tests)."""
    rng = random.Random(seed); s = [(0, 0, 0)] * 4
    for it in items:
        kind = it["kind"]; body = it["body"]; frame = good_frame(body)
        if kind == "badfcs": k = rng.randrange(len(frame)); frame = frame[:k] + bytes([frame[k] ^ (1 << rng.randrange(8))]) + frame[k + 1:]
        pre = [PRE] * 7 + [SFD]
        if kind == "shortpre": pre = [PRE] + [SFD]
        if kind == "nosfd": pre = [PRE] * 8
        if kind == "nopre": pre = [rng.choice([0x00, 0xAA, 0x01, 0xD5]), SFD]   # a SFD preceded by something that is not a preamble byte: not a frame start
        cyc = [(1, 0, b) for b in pre + list(frame)]
        if kind == "er": k = rng.randrange(len(pre) + 10, len(cyc)); cyc[k] = (1, 1, cyc[k][2])
        s += cyc + [(0, 0, 0)] * it["gap"]
    return s + [(0, 0, 0)] * 40
def make_items(seed, n, mix=None, maxbody=400):
    rng = random.Random(seed); mix = mix or {"good": 60, "badfcs": 10, "runt": 8, "giant": 4, "er": 6, "shortpre": 6, "nosfd": 6, "nopre": 5}; kinds = list(mix); w = [mix[k] for k in kinds]; items = []
    for _ in range(n):
        kind = rng.choices(kinds, w)[0]
        if kind == "runt": body = bytes(rng.getrandbits(8) for _ in range(rng.choice([59, 58, rng.randint(14, 57)])))        # frame = body + FCS < 64 bytes; 63 and 62 are the boundary cases
        elif kind == "giant": body = bytes(rng.getrandbits(8) for _ in range(rng.choice([1519, 1519, rng.randint(1519, 1530)])))   # frame = body + FCS > 1522; 1523 is the boundary case
        else: body = bytes(rng.getrandbits(8) for _ in range(rng.choice([60, 60, 61, 64, 100, rng.randint(60, maxbody), 1514, 1518])))
        if kind in ("good", "badfcs", "er", "shortpre") and len(body) < 60: body = body + bytes(60 - len(body))
        items.append({"kind": kind, "body": body, "gap": rng.choice([IFG, IFG, IFG, IFG + 1, IFG + 3, 20, 40])})
    return items
def write_stream(path, stream):
    with open(path, "w") as f:
        for dv, er, b in stream: f.write(f"{dv}{er}{b:02x}\n")
def parse_frames(text, tag="FRAME"):
    """Parses lines `FRAME <hex bytes> <bad>` printed by the testbenches."""
    out = []
    for line in text.splitlines():
        if line.startswith(tag + " "):
            p = line.split()
            try: out.append((bytes.fromhex(p[1]) if p[1] != "-" else b"", int(p[2])))
            except ValueError: out.append((b"<unknown bits in the output>", 9))               # an x or z in the output is never equal to a good frame
    return out
if __name__ == "__main__":
    it = make_items(1, 200); st = phy_stream(it); ex = spec_rx(st)
    from collections import Counter
    print(len(st), "cycles;", Counter(i["kind"] for i in it)); print(len(ex), "frames recognised,", sum(b for _, b in ex), "bad,", len(ex) - sum(b for _, b in ex), "good")
    # spec_rx must agree with what the construction says for every item
    k = 0; ok = True
    for i in it:
        if i["kind"] in ("nosfd", "nopre"): continue
        p, b = ex[k]; k += 1
        exp_bad = i["kind"] in ("badfcs", "runt", "giant", "er")
        if b != exp_bad: ok = False; print("mismatch", i["kind"], b)
        if i["kind"] in ("good", "shortpre"): ok &= p == i["body"]
    print("construction and spec agree:", ok)
def tx_frames(seed, n, sizes=None):
    """n frame bodies (destination..payload, no FCS) of assorted sizes, including the pad boundary (59, 60, 61), the maximum (1514 + 4 = 1518 and 1518 + 4 = 1522 with FCS), and short ones that need padding."""
    rng = random.Random(seed); sizes = sizes or [14, 20, 46, 59, 60, 61, 64, 100, 512, 1000, 1514, 1518]
    return [bytes(rng.getrandbits(8) for _ in range(rng.choice(sizes + [rng.randint(14, 300)]))) for _ in range(n)]
def write_tx(frames, pb="out/tx_bytes.hex", pl="out/tx_lens.hex"):
    with open(pb, "w") as f:
        for fr in frames:
            for b in fr: f.write(f"{b:02x}\n")
    with open(pl, "w") as f:
        for fr in frames: f.write(f"{len(fr):04x}\n")
def recovery_items(seed=2, pairs=40):
    """Pairs of (a maximum-size frame, a long gap, a small good frame, a gap): with a core clock a little slower than the PHY the big frames overflow the crossing FIFO, the small ones always fit. EVERY small frame must be delivered, however the big one before it was damaged (liveness after a loss), and nothing may be corrupt."""
    rng = random.Random(seed); it = []
    for _ in range(pairs):
        it.append({"kind": "good", "body": bytes(rng.getrandbits(8) for _ in range(1514)), "gap": 600})
        it.append({"kind": "good", "body": bytes(rng.getrandbits(8) for _ in range(rng.randint(60, 100))), "gap": 100})
    return it
def ff_stimulus(seed, depth, n=120, maxlen=None, spaced=False):
    """Frames for the frame buffer alone: lengths 1 to 2 x depth, some marked bad. Returns (list of (bytes, bad), cycles list of (valid, last, bad, data))."""
    rng = random.Random(seed); maxlen = maxlen or 2 * depth; frames = []; cyc = []
    for _ in range(n):
        L = rng.choice([1, 1, 2, depth - 2, depth - 1, depth, depth + 1, rng.randint(1, maxlen)]); fr = bytes(rng.getrandbits(8) for _ in range(L)); bad = int(rng.random() < 0.2); frames.append((fr, bad))
        for k, b in enumerate(fr):
            while rng.random() < 0.1: cyc.append((0, 0, 0, 0))
            cyc.append((1, int(k == L - 1), bad if k == L - 1 else 0, b))
        cyc += [(0, 0, 0, 0)] * (L + 8 if spaced else rng.randint(0, 3))          # spaced: the buffer is empty again before the next frame starts
    return frames, cyc + [(0, 0, 0, 0)] * 60
def write_ff(path, cyc):
    with open(path, "w") as f:
        for v, l, b, d in cyc: f.write(f"{v}{l}{b}{d:02x}\n")
