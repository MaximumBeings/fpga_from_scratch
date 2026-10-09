#!/usr/bin/env python3
"""Chapter 7, example B: what the CRC detects, by experiment. Every error pattern is applied to a real frame (with a correct FCS) and the frame is checked the way the receiver does (zlib.crc32 of frame + FCS == 0x2144DF1C). (1) every single-bit error, every double-bit error (exhaustive on a 64-byte frame, sampled on a 1,518-byte frame), every three-bit error on a 16-byte frame; (2) burst errors of every length up to 40 bits; (3) random corruption, with the full 32-bit check and with only its low 16 bits (to measure the 2^-n miss rate that 32 bits makes too small to see). Usage: ch07_example_b.py"""
import os, random, sys, zlib, itertools, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import crc_gold as g
def mk(n, seed): rng = random.Random(seed); return g.with_fcs(bytes(rng.getrandbits(8) for _ in range(n)))
def flipped(f, bits):
    b = bytearray(f)
    for k in bits: b[k >> 3] ^= 1 << (k & 7)
    return bytes(b)
def undetected(f, bits): return zlib.crc32(flipped(f, bits)) == g.RESIDUE
if __name__ == "__main__":
    t0 = time.time()
    print("== 1. few-bit errors in a frame with a correct FCS (a frame is 'detected' when its CRC no longer equals the residue)")
    print(f"  {'case':52s} {'patterns tried':>15s} {'undetected':>11s}")
    for n in (60, 508, 1514):
        f = mk(n, n); nb = len(f) * 8; bad = sum(undetected(f, (k,)) for k in range(nb)); print(f"  {'every single-bit error, frame of %d bytes + FCS' % n:52s} {nb:15d} {bad:11d}")
    f = mk(60, 1); nb = len(f) * 8; bad = sum(undetected(f, p) for p in itertools.combinations(range(nb), 2)); print(f"  {'every two-bit error, frame of 60 bytes + FCS':52s} {nb * (nb - 1) // 2:15d} {bad:11d}")
    f = mk(1514, 2); nb = len(f) * 8; rng = random.Random(3); bad = sum(undetected(f, tuple(rng.sample(range(nb), 2))) for _ in range(300000)); print(f"  {'300,000 random two-bit errors, 1,514 bytes + FCS':52s} {300000:15d} {bad:11d}")
    f = mk(12, 4); nb = len(f) * 8; bad = sum(undetected(f, p) for p in itertools.combinations(range(nb), 3)); print(f"  {'every three-bit error, frame of 12 bytes + FCS':52s} {nb * (nb - 1) * (nb - 2) // 6:15d} {bad:11d}")
    f = mk(60, 5); nb = len(f) * 8; rng = random.Random(6); bad = sum(undetected(f, tuple(rng.sample(range(nb), 4))) for _ in range(1000000)); print(f"  {'1,000,000 random four-bit errors, 60 bytes + FCS':52s} {1000000:15d} {bad:11d}")
    print("\n== 2. burst errors: a burst of length L is a run of L bits whose first and last bit are flipped and whose middle bits are anything (a 64-byte frame with FCS)")
    print(f"  {'burst length L':>14s} {'patterns tried':>15s} {'undetected':>11s}   how")
    f = mk(60, 7); nb = len(f) * 8; rng = random.Random(8)
    for L in (1, 2, 3, 8, 12, 16, 24, 31, 32, 33, 40):
        tried = 0; bad = 0
        if L <= 12:
            for start in range(nb - L + 1):
                for mid in range(1 << max(L - 2, 0)):
                    bits = [start] + ([start + L - 1] if L > 1 else []) + [start + 1 + i for i in range(L - 2) if mid >> i & 1]; tried += 1; bad += undetected(f, bits)
            how = "exhaustive"
        else:
            for _ in range(200000):
                start = rng.randrange(nb - L + 1); bits = [start, start + L - 1] + [start + 1 + i for i in range(L - 2) if rng.random() < 0.5]; tried += 1; bad += undetected(f, bits)
            how = "200,000 random bursts"
        print(f"  {L:14d} {tried:15d} {bad:11d}   {how}")
    print("  every burst of up to 32 bits is detected, by construction of the code (a CRC of degree 32 detects all bursts of length <= 32); a burst of 33 or more is missed with probability about 2^-32, too small to measure here")
    print("\n== 3. random corruption: replace a random byte range with random bytes (a frame of 60 bytes + FCS); detected when the check differs from the residue")
    rng = random.Random(9); f = mk(60, 10); N = 4000000; miss32 = miss16 = 0
    for _ in range(N):
        b = bytearray(f); i = rng.randrange(len(b) - 3); 
        for j in range(4): b[i + j] ^= rng.getrandbits(8)
        c = zlib.crc32(bytes(b)); 
        if b != f:
            miss32 += c == g.RESIDUE; miss16 += (c & 0xFFFF) == (g.RESIDUE & 0xFFFF)
    print(f"  {N:,} random corruptions: undetected with the full 32-bit CRC: {miss32}   undetected if only the low 16 bits were checked: {miss16}   (expected for 16 bits: about {N / 65536:.0f}; for 32 bits: {N / 2 ** 32:.4f})")
    print(f"\n  run time {time.time() - t0:.0f} s")
