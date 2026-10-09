#!/usr/bin/env python3
"""Chapter 7: independent models of the Ethernet CRC-32 and the frame stream. Three implementations of the same function that must agree: a bit-serial reference written from the definition, zlib.crc32 (a library nobody here wrote), and a table-driven version.
Ethernet CRC-32: polynomial x^32 + x^26 + x^23 + x^22 + x^16 + x^12 + x^11 + x^10 + x^8 + x^7 + x^5 + x^4 + x^2 + x + 1 (0x04C11DB7), bits sent least-significant first (so the working form is the reflected polynomial 0xEDB88320), register initialised to all ones, result inverted, sent least-significant byte first. A frame followed by its own FCS leaves a fixed value (the 'residue'): zlib.crc32(frame + fcs_little_endian) == 0x2144DF1C."""
import random, zlib
POLY_R = 0xEDB88320; RESIDUE = 0x2144DF1C
def crc_bitwise(data, init=0xFFFFFFFF, final=True):
    c = init
    for byte in data:
        for i in range(8):
            fb = (c ^ (byte >> i)) & 1; c >>= 1
            if fb: c ^= POLY_R
    return c ^ 0xFFFFFFFF if final else c
_T = []
for n in range(256):
    c = n
    for _ in range(8): c = (c >> 1) ^ POLY_R if c & 1 else c >> 1
    _T.append(c)
def crc_table(data):
    c = 0xFFFFFFFF
    for b in data: c = _T[(c ^ b) & 0xFF] ^ (c >> 8)
    return c ^ 0xFFFFFFFF
def fcs(frame): return zlib.crc32(frame).to_bytes(4, "little")
def with_fcs(frame): return frame + fcs(frame)
def beats(data, w):
    """Splits bytes into beats of w//8 bytes (byte 0 in bits 7:0). Returns [(value, nbytes, last)]."""
    k = w // 8; out = []
    for i in range(0, len(data), k):
        chunk = data[i:i + k]; out.append((int.from_bytes(chunk, "little"), len(chunk), int(i + k >= len(data))))
    return out
def make_frames(seed, n, lo=5, hi=200, bad_fraction=0.3):
    """n byte strings WITH an FCS appended; a fraction have a corrupted FCS (one bit flipped). Returns [(bytes, good)]."""
    rng = random.Random(seed); out = []
    for _ in range(n):
        body = bytes(rng.getrandbits(8) for _ in range(rng.randint(lo, hi))); f = with_fcs(body); good = True
        if rng.random() < bad_fraction:
            k = rng.randrange(len(f)); f = f[:k] + bytes([f[k] ^ (1 << rng.randrange(8))]) + f[k + 1:]; good = False
        out.append((f, good))
    return out
def schedule(frames, w, seed):
    """Per-cycle input list (valid, data, nbytes, last), gaps of 0..3 idle cycles between beats and frames. IDLE cycles carry random junk on data, nbytes and last: the interface says they are don't-cares when valid = 0, and a design that reads them is wrong."""
    rng = random.Random(seed ^ 0x5bd1)
    def idle(): return (0, rng.getrandbits(w), rng.randint(0, 8), rng.getrandbits(1))
    ins = [idle() for _ in range(3)]
    for f, _ in frames:
        for v, nb, last in beats(f, w):
            while rng.random() < 0.15: ins.append(idle())
            ins.append((1, v, nb, last))
        ins += [idle() for _ in range(rng.randint(0, 3))]
    return ins + [idle() for _ in range(6)]
def expected(ins, w, latency=1):
    """Per cycle (out_valid, out_good, out_crc) as seen BEFORE the clock edge: the result of a frame appears `latency` cycles after the cycle of its last beat (1 for the single-stage design, 4 for the pipelined one). The CRC is zlib's, computed over all the bytes of the frame (FCS included): out_crc == 0x2144DF1C exactly when the frame is good."""
    res = [(0, 0, 0)] * (len(ins) + latency + 1); cur = bytearray()
    for k, (v, d, nb, last) in enumerate(ins):
        if v:
            cur += d.to_bytes(w // 8, "little")[:nb]
            if last: c = zlib.crc32(bytes(cur)); res[k + latency] = (1, int(c == RESIDUE), c); cur = bytearray()
    return res[:len(ins)]
def write_vectors(path, ins, res, w):
    """One line per cycle: valid last nbytes(hex digit) data (w/4 hex digits) | out_valid out_good out_crc(8 hex)."""
    with open(path, "w") as f:
        for (v, d, nb, last), (ov, og, oc) in zip(ins, res): f.write(f"{v}{last}{nb:x}{d:0{w // 4}x}{ov}{og}{oc:08x}\n")
if __name__ == "__main__":
    rng = random.Random(1); ok = 0
    for _ in range(2000):
        d = bytes(rng.getrandbits(8) for _ in range(rng.randint(0, 300))); ok += crc_bitwise(d) == zlib.crc32(d) == crc_table(d)
    print("bitwise = zlib = table on 2000 random messages:", ok, "of 2000;  residue check:", zlib.crc32(with_fcs(b"hello world")) == RESIDUE)
def frames_all_lengths(lo, hi, seed=1):
    """One good and one bad frame (with FCS) for every body length lo..hi: every length modulo the beat width, so every partial-last-beat case is exercised at every width."""
    rng = random.Random(seed); out = []
    for n in range(lo, hi + 1):
        body = bytes(rng.getrandbits(8) for _ in range(n)); f = with_fcs(body); out.append((f, True))
        k = rng.randrange(len(f)); out.append((f[:k] + bytes([f[k] ^ (1 << rng.randrange(8))]) + f[k + 1:], False))
    return out
