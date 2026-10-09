#!/usr/bin/env python3
"""Chapter 2: golden model of the frame recognizer and its stimulus. The model is a direct transcription of the specification (a frame is SOF 0xA5, LEN 1..16, LEN payload bytes, END 0x5A; a bad LEN or END aborts), written as a Python function of the byte stream, not as a state machine copied from the RTL: it walks the stream and keeps a position within the current frame.
Outputs per cycle (as seen before the clock edge): busy, pay_v, done, err (pay_v, done, err report the byte consumed in the previous cycle). Vector word: {err, done, pay_v, busy, rst, in_valid, in_byte}. Usage: frame_gold.py CYCLES SEED OUTFILE"""
import random, sys
def golden(inputs):
    """inputs: list of (rst, in_valid, byte). Returns per cycle (busy, pay_v, done, err) before the edge."""
    pos = 0; remaining = 0; busy = 0; pay = done = err = 0; out = []
    for rst, v, b in inputs:
        out.append((busy, pay, done, err)); pay = done = err = 0
        if rst: pos = 0; remaining = 0; busy = 0; continue
        if not v: continue
        if pos == 0:
            if b == 0xA5: pos = 1
        elif pos == 1:
            if 1 <= b <= 16: remaining = b; pos = 2
            else: err = 1; pos = 0
        elif pos == 2:
            pay = 1; remaining -= 1
            if remaining == 0: pos = 3
        else:
            if b == 0x5A: done = 1
            else: err = 1
            pos = 0
        busy = int(pos != 0)
    return out
def stimulus(cycles, seed):
    R = random.Random(seed); ins = [(1, 0, 0), (1, 1, 0xA5)]
    def byte_stream():
        kind = R.random()
        if kind < 0.55: n = R.randrange(1, 17); return [0xA5, n] + [R.randrange(256) for _ in range(n)] + [0x5A]
        if kind < 0.7: return [0xA5, R.choice([0, 17, 18, 255])] + [R.randrange(256) for _ in range(R.randrange(3))]       # bad length
        if kind < 0.85: n = R.randrange(1, 17); return [0xA5, n] + [R.randrange(256) for _ in range(n)] + [R.choice([0x00, 0xA5, 0x5B])]  # bad end
        if kind < 0.93: return [R.randrange(256) for _ in range(R.randrange(1, 6))]                                        # noise outside frames (may contain SOF)
        return [0xA5, 0xA5, 3, 1, 2, 3, 0x5A]                                                                              # a SOF byte where a length belongs
    while len(ins) < cycles:
        for b in byte_stream():
            while R.random() < 0.25: ins.append((0, 0, R.randrange(256)))            # idle cycles: valid low, garbage on the bus
            ins.append((int(R.random() < 0.004), 1, b))
    return ins[:cycles]
def write(cycles, seed, path):
    ins = stimulus(cycles, seed); exp = golden(ins)
    with open(path, "w") as f:
        for (rst, v, b), (bu, pv, dn, er) in zip(ins, exp): f.write("%x\n" % ((((((er << 1 | dn) << 1 | pv) << 1 | bu) << 1 | rst) << 1 | v) << 8 | b))
    return len(ins), exp
if __name__ == "__main__":
    n, e = write(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]); print(n, "cycles;", "frames done", sum(x[2] for x in e), "errors", sum(x[3] for x in e), "payload bytes", sum(x[1] for x in e))
