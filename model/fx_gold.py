#!/usr/bin/env python3
"""Chapter 5: independent models of the fixed-point and memory designs. Nothing here reads the RTL; everything is integer arithmetic.
  round_sat   a signed IW-bit value scaled down by 2**SH into an OW-bit signed result: truncate (floor) or round half up, saturate or wrap
  MAC         the three-stage multiply-accumulate, cycle by cycle
  fir         the 8-tap filter: y[k] = sum C[i] * x[k - 2 - i] (two cycles of latency), the accumulator rounded and saturated
  ram         the three read styles: asynchronous (latency 0), synchronous (1), synchronous with an output register (2)
Q notation: Qm.n is a signed number of m + n bits with n fractional bits; Q1.15 (16 bits) is the number x / 2**15 in [-1, 1)."""
import random
def sx(v, w): v &= (1 << w) - 1; return v - (1 << w) if v >> (w - 1) else v
def round_sat(x, iw, ow, sh, rnd, sat):
    assert -(1 << (iw - 1)) <= x < (1 << (iw - 1))
    r = x + ((1 << (sh - 1)) if rnd and sh > 0 else 0); s = r >> sh                  # Python's >> on negative integers floors, like an arithmetic shift
    lo, hi = -(1 << (ow - 1)), (1 << (ow - 1)) - 1
    return max(lo, min(hi, s)) if sat else sx(s, ow)
COEF = [-1243, 2115, 6410, 11870, 11870, 6410, 2115, -1243]                            # a symmetric 8-tap low-pass in Q1.15 (sum = 38304 = 1.169 in Q1.15: not unity gain, on purpose, so that overflow is possible)
class MAC:
    """Stage 1 registers the operands, stage 2 the product, stage 3 the accumulator. clr starts a new sum (acc := product if en else 0); en adds the product."""
    def __init__(s, rnd=1, sat=1, aw=40): s.ra = s.rb = 0; s.ren = s.rclr = 0; s.p = 0; s.pen = s.pclr = 0; s.acc = 0; s.rnd, s.sat, s.aw = rnd, sat, aw
    def out(s): return (s.acc, round_sat(s.acc, s.aw, 16, 15, s.rnd, s.sat))
    def step(s, en, clr, a, b):
        nacc = s.acc
        if s.pclr: nacc = s.p if s.pen else 0
        elif s.pen: nacc = sx(s.acc + s.p, s.aw)
        s.acc = nacc
        s.pen, s.pclr = s.ren, s.rclr; s.p = s.ra * s.rb
        s.ra, s.rb, s.ren, s.rclr = a, b, en, clr
def mac_run(stim, rnd=1, sat=1):
    m = MAC(rnd, sat); res = []
    for en, clr, a, b in stim: res.append(m.out()); m.step(en, clr, a, b)
    return res
def fir_run(xs, rnd=1, sat=1, coef=COEF):
    out = []
    for k in range(len(xs)):
        acc = sum(c * (xs[k - 2 - i] if k - 2 - i >= 0 else 0) for i, c in enumerate(coef)); out.append((acc, round_sat(acc, 40, 16, 15, rnd, sat)))
    return out
def ram_run(style, ops, depth):
    """ops: per cycle (we, waddr, wdata, raddr). Returns the rdata seen before each clock edge. A synchronous read returns the OLD contents when it reads the address being written (read-first)."""
    mem = [0] * depth; r1 = 0; r2 = 0; res = []
    for we, wa, wd, ra in ops:
        res.append(mem[ra] if style == 0 else (r1 if style == 1 else r2)); nr1 = mem[ra]
        if we: mem[wa] = wd
        r2 = r1; r1 = nr1
    return res
def rs_vectors(path, iw, ow, sh, rnd, sat):
    """Every input of an IW-bit signed value, one line each: x (hex, IW bits) y (hex, OW bits)."""
    n = 0
    with open(path, "w") as f:
        for x in range(-(1 << (iw - 1)), 1 << (iw - 1)):
            f.write(f"{x & ((1 << iw) - 1):0{(iw + 3) // 4}x}{round_sat(x, iw, ow, sh, rnd, sat) & ((1 << ow) - 1):0{(ow + 3) // 4}x}\n"); n += 1
    return n
def mac_stim(seed, n, mode="random"):
    rng = random.Random(seed); out = []
    for k in range(n):
        if mode == "overflow": a, b = rng.choice([32767, -32768, 30000, -30000]), rng.choice([32767, -32768, 30000, -30000])
        else: a, b = rng.randint(-32768, 32767), rng.randint(-32768, 32767)
        out.append((int(rng.random() < 0.8), int(rng.random() < (0.02 if mode == "overflow" else 0.12)), a, b))
    return out
def write_mac(path, stim, res):
    """One line per cycle: en clr a(4 hex) b(4 hex) | acc (10 hex, 40 bits) y (4 hex)."""
    with open(path, "w") as f:
        for (en, clr, a, b), (acc, y) in zip(stim, res): f.write(f"{en}{clr}{a & 0xFFFF:04x}{b & 0xFFFF:04x}{acc & ((1 << 40) - 1):010x}{y & 0xFFFF:04x}\n")
def write_fir(path, xs, res):
    with open(path, "w") as f:
        for x, (acc, y) in zip(xs, res): f.write(f"{x & 0xFFFF:04x}{y & 0xFFFF:04x}\n")
def write_ram(path, ops, res, w):
    with open(path, "w") as f:
        for (we, wa, wd, ra), r in zip(ops, res): f.write(f"{we}{wa:04x}{wd:0{(w + 3) // 4}x}{ra:04x}{r:0{(w + 3) // 4}x}\n")
def ram_ops(seed, n, depth, w):
    rng = random.Random(seed); ops = []
    for _ in range(n):
        wa = rng.randrange(depth); ra = wa if rng.random() < 0.2 else rng.randrange(depth); ops.append((int(rng.random() < 0.5), wa, rng.getrandbits(w), ra))
    return ops
