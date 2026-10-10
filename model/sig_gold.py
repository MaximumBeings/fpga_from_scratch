#!/usr/bin/env python3
"""Chapter 22: the specification of the signal unit: from the top of book (best bid price and shares, best ask price and shares) to four numbers, in fixed point, bit for bit.
FORMATS. Prices are unsigned integers of PW bits (ticks), shares unsigned of QW bits. F is the number of fraction bits. Both sides must be present (shares > 0 on both) for the signals to exist: ok = (bid shares > 0 and ask shares > 0); when ok = 0 every output is 0.
  mid2   = Pa + Pb                              unsigned, PW + 1 bits, in HALF ticks: exact, no rounding
  spread = Pa - Pb                              signed, PW + 1 bits, in ticks; cross = (spread < 0) and lock = (spread == 0)
  w      = round_half_up(Qb * 2^F / (Qa + Qb))  unsigned, F + 1 bits, 0 <= w <= 2^F: the bid's share of the quantity at the touch, in units of 2^-F
  imb    = 2 w - 2^F                            signed, F + 2 bits, in units of 2^-F: the imbalance (Qb - Qa) / (Qb + Qa) in [-1, 1] (resolution 2^-(F-1): only even values)
  micro  = Pb 2^F + spread w                    unsigned, PW + F bits, in ticks x 2^F: the microprice, Pb + spread Qb / (Qa + Qb) = (Pa Qb + Pb Qa) / (Qa + Qb), from the ROUNDED w
w is the only division, done once; imb and micro use it. ROUNDING: round half up (floor(x + 1/2)); the unit is NOT antisymmetric by one unit of w at exact halves (swap the sides and the half rounds up on both).
TIME. A message offered in cycle a is answered in cycle a + L, L = F + 4 (F restoring-division steps, one rounding stage, one multiplication stage, one addition stage). DIV = 1 (pipelined divider) accepts one message per cycle; DIV = 0 (one shared divider step) is busy from the cycle after it accepts until the cycle the answer is visible (L - 1 cycles in which it does not accept): the engine accepts again in cycle a + L."""
import random
from fractions import Fraction
def compute(bpx, bsh, apx, ash, F):
    """-> (ok, mid2, spread, cross, lock, w, imb, micro): the specification, in integers."""
    if bsh == 0 or ash == 0: return (0, 0, 0, 0, 0, 0, 0, 0)
    d = bsh + ash; w = (2 * bsh * (1 << F) + d) // (2 * d); s = apx - bpx
    return (1, apx + bpx, s, int(s < 0), int(s == 0), w, 2 * w - (1 << F), bpx * (1 << F) + s * w)
def ideal(bpx, bsh, apx, ash):
    """The same quantities in exact rationals (what the fixed point approximates): -> (imbalance, microprice in ticks, mid in ticks) or None."""
    if bsh == 0 or ash == 0: return None
    d = Fraction(bsh + ash); return Fraction(bsh - ash) / d, (Fraction(apx) * bsh + Fraction(bpx) * ash) / d, Fraction(apx + bpx, 2)
def division(bsh, ash, F):
    """The division as the hardware does it: F restoring steps on the remainder, starting from Qb (< D), then the rounding: -> (t, r) and w = t + (2 r >= D)."""
    d = bsh + ash; r = bsh; t = 0
    for _ in range(F):
        r *= 2
        if r >= d: r -= d; t = 2 * t + 1
        else: t = 2 * t
    return t, r
def run(msgs, pw, qw, f, div=1, gaps=None):
    """Closed loop: msgs[i] = (bpx, bsh, apx, ash) is offered no earlier than cycle sum(gaps[:i + 1]) and held until accepted. DIV 1 accepts every cycle; DIV 0 accepts when idle (L cycles after it last accepted). -> dict(rows, lines, accepted) with rows[c] = (ready, answer visible this cycle or None)."""
    L = f + 4; n = len(msgs); arr = []; t = 0
    for i in range(n): t += (gaps[i] if gaps else 0); arr.append(t)
    qi = 0; t = 0; busy_until = 0; pend = {}; rows = []; lines = []; acc = []
    while qi < n or pend or t < busy_until + 2:
        offered = msgs[qi] if qi < n and arr[qi] <= t else None
        ready = 1 if (div == 1 or t >= busy_until) else 0
        rows.append((ready, pend.pop(t, None))); lines.append(offered)
        if offered is not None and ready:
            pend[t + L] = compute(*offered, f); busy_until = t + L; qi += 1; acc.append(t)
        t += 1
        if t > 10 * (n + 4) * (L + 2) + sum(gaps or [0]) + 100: break
    return dict(rows=rows, lines=lines, accepted=acc)
def expected_rows(res):
    """(cycle, ready, valid, ok, mid2, spread, cross, lock, w, imb, micro) as the testbench prints them."""
    out = []
    for c, (ready, r) in enumerate(res["rows"]): out.append((c, ready, 0) + (0,) * 8 if r is None else (c, ready, 1) + tuple(r))
    return out
def write_stim(path, lines, seed=1):
    """One line per cycle: valid(1), then bid price, bid shares, ask price, ask shares as 32-bit fields (junk when valid = 0), 129 bits as 34 hex digits."""
    rng = random.Random(seed)
    with open(path, "w") as fh:
        for e in lines:
            v, b, bs, a, as_ = (1,) + tuple(e) if e else (0, rng.getrandbits(32), rng.getrandbits(32), rng.getrandbits(32), rng.getrandbits(32))
            fh.write("%034x\n" % ((v << 128) | (b << 96) | (bs << 64) | (a << 32) | as_))
    return len(lines)
def half_books(pw, qw, f):
    """Directed: books whose division lands EXACTLY on a half unit of w (x = Qb 2^F / D = j + 1/2), where the rounding rule decides: D = m 2^(F+1) and Qb = m (1/2), or Qb odd < 2^(F+1) with D = 2^(F+1), for the first few odd Qb and the last few, on both sides."""
    out = []; d0 = 1 << (f + 1)
    for m in (1, 3):
        if m * d0 < (1 << qw):
            for qb in (m, m * d0 - m): out += [(100, qb, 102, m * d0 - qb), (102, qb, 100, m * d0 - qb)]
    if d0 < (1 << qw):
        for qb in (1, 3, 5, d0 // 2 - 1, d0 // 2 + 1, d0 - 3, d0 - 1): out += [(100, qb, 102, d0 - qb), (100, d0 - qb, 102, qb)]
    return out
def edge_books(pw, qw):
    """Directed: every combination of prices and shares from sets that hold the boundaries (0, 1, the maximum, a half, the exact-half rounding cases, crossed, locked, equal sides, one side empty)."""
    P = [0, 1, 2, 1000, (1 << pw) - 2, (1 << pw) - 1]; Q = [0, 1, 2, 3, 7, 100, (1 << (qw - 1)), (1 << qw) - 2, (1 << qw) - 1]
    return [(b, bs, a, as_) for b in P for a in P for bs in Q for as_ in Q]
def random_books(rng, n, pw, qw):
    """Random tops of book: prices around a mid with a spread of 0 to 20 ticks (sometimes crossed), shares from a long-tailed distribution (sometimes 0, sometimes equal)."""
    out = []; mid = rng.randrange(100, (1 << pw) - 100)
    for _ in range(n):
        mid = max(30, min((1 << pw) - 30, mid + rng.randint(-2, 2))); s = rng.choice([0, 1, 1, 2, 3, 5, 8, 20, -1, -3]); b = mid - s // 2; a = b + s
        q = lambda: 0 if rng.random() < .05 else min((1 << qw) - 1, int(rng.paretovariate(1.1) * rng.choice([1, 10, 100])))
        bs = q(); as_ = bs if rng.random() < .1 else q(); out.append((max(0, min((1 << pw) - 1, b)), bs, max(0, min((1 << pw) - 1, a)), as_))
    return out
if __name__ == "__main__":
    F = 4
    assert compute(100, 10, 102, 30, F) == (1, 202, 2, 0, 0, 4, 4 * 2 - 16, 100 * 16 + 2 * 4)          # Qb 10, Qa 30: share 10/40 = 0.25 = 4/16: w = 4, imbalance -0.5 (-8/16), microprice 100 + 2 * 0.25 = 100.5 (1608 / 16)
    assert compute(100, 10, 102, 10, F)[5:] == (8, 0, 100 * 16 + 2 * 8) and compute(100, 30, 102, 10, F)[5:] == (12, 8, 100 * 16 + 2 * 12)  # equal sides: w = 8 (half), imbalance 0, micro at the mid; bid heavy: w 12, imbalance +0.5
    assert compute(100, 0, 102, 10, F) == (0,) * 8 and compute(100, 10, 102, 0, F) == (0,) * 8 and compute(100, 0, 102, 0, F) == (0,) * 8        # a side without shares: no signals
    assert compute(102, 10, 100, 30, F)[1:5] == (202, -2, 1, 0) and compute(100, 10, 100, 30, F)[1:5] == (200, 0, 0, 1)                              # crossed (spread -2, cross) and locked (spread 0, lock)
    assert compute(102, 10, 100, 30, F)[7] == 102 * 16 + (-2) * 4                                                                                      # crossed: micro = 102 - 2 * 0.25 = 101.5, still between the two prices
    assert compute(0, 1, 5, 2, 3)[5] == 3 and compute(0, 1, 5, 7, 3)[5] == 1 and compute(0, 1, 1, 15, 3)[5] == 1                                      # F = 3: Qb/D = 1/3 -> 8/3 = 2.67 -> 3; 1/8 -> 1; 1/16 -> 0.5 -> 1 (round half up)
    assert compute(0, 15, 1, 1, 3)[5] == 8 and compute(0, 1, 1, 1, 3)[5] == 4 and compute(0, 255, 1, 1, 3)[5] == 8                                   # 15/16 * 8 = 7.5 -> 8 (the exact half rounds up on both sides: 0.5 -> 1 above and 7.5 -> 8 here: w(1, 15) + w(15, 1) = 9, not 8); 1/2 -> 4; 255/256 -> 7.97 -> 8
    assert compute(0, 1, 1, 15, 3)[5] + compute(0, 15, 1, 1, 3)[5] == 9
    for bsh, ash in ((1, 1), (3, 5), (1, 15), (15, 1), (7, 9), (1, 2 ** 20 - 2)):                                                                    # the division as the hardware does it equals the specification
        for f in (3, 8, 12): t, r = division(bsh, ash, f); assert t + (2 * r >= bsh + ash) == compute(0, bsh, 1, ash, f)[5], (bsh, ash, f)
    assert expected_rows(run([(100, 10, 102, 30)], 24, 20, 4, 1))[4 + 4][1:3] == (1, 1) and run([(1, 1, 2, 1), (1, 1, 2, 1)], 24, 20, 4, 0, [0, 0])["accepted"] == [0, 8]      # L = F + 4 = 8: the answer in cycle 8; the sequential unit accepts again in cycle 8
    assert run([(1, 1, 2, 1), (1, 1, 2, 1)], 24, 20, 4, 1, [0, 0])["accepted"] == [0, 1]                                                              # the pipelined unit accepts every cycle
    hb = half_books(24, 20, 3)                                                                                                                         # F = 3: D = 16 and Qb = 1, 15, 3, ...: all exact halves (Qb 2^F / D = j + 1/2): division() leaves 2 r == D
    assert hb and all(2 * division(b[1], b[3], 3)[1] == b[1] + b[3] for b in hb), [b for b in hb if 2 * division(b[1], b[3], 3)[1] != b[1] + b[3]]
    print("sig_gold hand-checked scenarios passed")
