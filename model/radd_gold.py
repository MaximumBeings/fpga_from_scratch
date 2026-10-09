#!/usr/bin/env python3
"""Chapter 1: the golden model of the registered adder, and its test vectors. The circuit adds two W-bit numbers into a (W+1)-bit sum with two register stages: input registers, then the sum register; an input pair applied before clock edge k is visible in the output after edge k+1 (two edges in all).
Vectors: directed ones that exercise the carry chain (all ones plus one, alternating patterns, a single carry running across every bit), and random ones. Each vector line is one hex word {expected, b, a}. Usage: radd_gold.py W N SEED OUTFILE"""
import random, sys
def golden(a, b, w): return (a + b) & ((1 << (w + 1)) - 1)
def vectors(w, n, seed):
    R = random.Random(seed); m = (1 << w) - 1; v = [(0, 0), (m, 1), (1, m), (m, m), (0, m), (m, 0), (0x5555555555555555 & m, 0xAAAAAAAAAAAAAAAA & m), (0xAAAAAAAAAAAAAAAA & m, 0x5555555555555555 & m)]
    v += [((1 << k) - 1 & m, 1) for k in range(1, w + 1)]               # a carry that ripples through k bits
    v += [(1 << k, 1 << k) for k in range(w)]                           # a carry generated at bit k
    v += [(R.getrandbits(w), R.getrandbits(w)) for _ in range(n)]
    return v
def write(w, n, seed, path):
    vs = vectors(w, n, seed)
    with open(path, "w") as f:
        for a, b in vs: f.write("%x\n" % ((golden(a, b, w) << (2 * w)) | (b << w) | a))
    return len(vs)
if __name__ == "__main__":
    w, n, seed, out = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]; print(f"{write(w, n, seed, out)} vectors written to {out}")
