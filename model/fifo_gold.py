#!/usr/bin/env python3
"""Chapter 6: the FIFO's golden model, the three kinds of stimulus (directed, uniform random, constrained random), and the functional coverage bins, all independent of the RTL.
The model is the specification: a deque. Per cycle, the outputs seen BEFORE the clock edge are (rd_data, full, empty, count); then the inputs are applied: a write is accepted if not full, a read if not empty."""
import random
from collections import deque
DEPTH = 6; W = 8
class Fifo:
    def __init__(s, depth=DEPTH): s.d = deque(); s.depth = depth
    def out(s): return (s.d[0] if s.d else 0, int(len(s.d) == s.depth), int(not s.d), len(s.d))
    def step(s, wr, rd, data):
        full, empty = len(s.d) == s.depth, not s.d
        if rd and not empty: s.d.popleft()
        if wr and not full: s.d.append(data)
def run(stim, depth=DEPTH):
    m = Fifo(depth); res = []
    for wr, rd, data in stim: res.append(m.out()); m.step(wr, rd, data)
    return res
def write_vectors(path, stim, res):
    """One line per cycle: wr rd data(2 hex) | rd_data(2 hex) full empty count."""
    with open(path, "w") as f:
        for (wr, rd, data), (q, full, empty, cnt) in zip(stim, res): f.write(f"{wr}{rd}{data:02x}{q:02x}{full}{empty}{cnt}\n")
# ---- stimulus
def directed():
    """What an engineer writes by hand: a few words in and out, fill to full and drain to empty, alternate write and read."""
    s = []
    for k in range(3): s.append((1, 0, 0x10 + k))
    for k in range(3): s.append((0, 1, 0))
    for k in range(DEPTH): s.append((1, 0, 0x20 + k))
    s.append((1, 0, 0x99))                                                # a write when full
    for k in range(DEPTH): s.append((0, 1, 0))
    s.append((0, 1, 0))                                                   # a read when empty
    for k in range(20): s.append((1, 1, 0x30 + k)) if k else s.append((1, 0, 0x30))
    for k in range(4): s.append((0, 1, 0))
    return s
def uniform(seed, n, pw=0.5, pr=0.5):
    rng = random.Random(seed); return [(int(rng.random() < pw), int(rng.random() < pr), rng.getrandbits(W)) for _ in range(n)]
PHASES = [(0.9, 0.1), (0.1, 0.9), (0.5, 0.5), (0.7, 0.7), (0.95, 0.95), (0.6, 0.55), (0.3, 0.3)]
SPECIAL = [0x00, 0xFF, 0xA5, 0x5A, 0x01, 0x80]
def constrained(seed, n):
    """Constrained random: phases of 20 to 80 cycles with biased write/read probabilities (so the FIFO is driven to full and to empty and held near both), and data drawn half the time from a list of special values."""
    rng = random.Random(seed); s = []
    while len(s) < n:
        pw, pr = rng.choice(PHASES)
        for _ in range(rng.randint(20, 80)): s.append((int(rng.random() < pw), int(rng.random() < pr), rng.choice(SPECIAL) if rng.random() < 0.5 else rng.getrandbits(W)))
    return s[:n]
# ---- functional coverage
BINS = [f"occupancy {k}" for k in range(DEPTH + 1)] + ["write when full", "read when empty", "read+write when empty", "read+write when full", "read+write with one word", "write wraps (2 laps)", "write of 0xA5 at depth-1", "write of 0x00 at depth-1", "full for 3 cycles running", "empty for 3 cycles running", "read+write with 3 words"]
def coverage(stim, depth=DEPTH):
    """Returns the set of bins hit by the stimulus, computed on the golden model's state."""
    m = Fifo(depth); hit = set(); writes = 0; fullrun = emptyrun = 0
    for wr, rd, data in stim:
        n = len(m.d); full, empty = n == depth, n == 0; hit.add(f"occupancy {n}")
        if wr and full: hit.add("write when full")
        if rd and empty: hit.add("read when empty")
        if wr and rd and empty: hit.add("read+write when empty")
        if wr and rd and full: hit.add("read+write when full")
        if wr and rd and n == 1: hit.add("read+write with one word")
        if wr and rd and n == 3: hit.add("read+write with 3 words")
        if wr and not full:
            writes += 1
            if writes >= 2 * depth: hit.add("write wraps (2 laps)")
            if n == depth - 1 and data == 0xA5: hit.add("write of 0xA5 at depth-1")
            if n == depth - 1 and data == 0x00: hit.add("write of 0x00 at depth-1")
        fullrun = fullrun + 1 if full else 0; emptyrun = emptyrun + 1 if empty else 0
        if fullrun >= 3: hit.add("full for 3 cycles running")
        if emptyrun >= 3: hit.add("empty for 3 cycles running")
        m.step(wr, rd, data)
    return hit
if __name__ == "__main__":
    for name, st in (("directed", directed()), ("uniform 2000", uniform(1, 2000)), ("constrained 2000", constrained(1, 2000))):
        print(f"{name:18s} {len(st):5d} cycles, coverage {len(coverage(st))} of {len(BINS)} bins")
