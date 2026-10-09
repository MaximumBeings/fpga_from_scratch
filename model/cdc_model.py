#!/usr/bin/env python3
"""Independent models for Chapter 3 (clock-domain crossing). Nothing here reads the RTL.
  pulses_naive / pulses_toggle   how many of NP one-cycle pulses cross, from the clock edges alone (an ideal-sampling event model)
  reset_release_edges            clock edges between the release of an asynchronous reset and rst_n going high
  pointer_capture                every way a pointer step can be captured when each bit independently takes its old or new value
  mtbf                           the standard synchronizer MTBF formula (constants are ASSUMED, not measured)
"""
import math
def _edges(period, first, upto):   # clock rising edges: first, first+period, ... below `upto` (ps)
    t = first; out = []
    while t < upto: out.append(t); t += period
    return out
def _pulse_schedule(AP, GAP, NP):
    # testbench: 4 edges of aclk, then pulse k asserted 200 ps after edge 4+k*GAP (aclk edges are at AP/2 + n*AP, the first being edge 1); a_q / tog change at the NEXT aclk edge
    ae = lambda n: AP // 2 + (n - 1) * AP
    return [ae(5 + k * GAP) for k in range(NP)], ae          # the aclk edge at which a_q first shows pulse k
def _bsamples(BP, OFF, tmax):
    return _edges(BP, OFF + BP // 2, tmax)                       # the b clock starts low at OFF; its first rising edge is BP/2 later
def pulses_naive(AP, BP, OFF, GAP, NP):
    starts, ae = _pulse_schedule(AP, GAP, NP); tmax = starts[-1] + 10 * AP + 20 * BP + GAP * AP
    def a_q(t): return any(s < t <= s + AP for s in starts)       # a_q is high for one aclk period after the capturing edge; a b edge at the very same instant still sees the old value (the register updates after the edge)
    prev = 0; n = 0
    for tb in _bsamples(BP, OFF, tmax):
        v = 1 if a_q(tb) else 0
        if v and not prev: n += 1
        prev = v
    return n
def pulses_toggle(AP, BP, OFF, GAP, NP):
    starts, ae = _pulse_schedule(AP, GAP, NP); tmax = starts[-1] + 10 * AP + 20 * BP + GAP * AP
    def tog(t): return sum(1 for s in starts if s < t) & 1       # the toggle flips at each capturing edge (a b edge at that same instant still sees the old value)
    prev = 0; n = 0
    for tb in _bsamples(BP, OFF, tmax):
        v = tog(tb)
        if v != prev: n += 1
        prev = v
    return n
def reset_release_edges(offset_ps, P=10000):
    """Release `offset_ps` after a clock edge (0 < offset < P): the first edge after the release moves the 1 into q1, the second moves it into rst_n. Two edges whatever the offset."""
    assert 0 < offset_ps < P
    return 2
def _outcomes(old, new, width):
    """All values a `width`-bit register can capture when every bit that differs between old and new independently takes its old or its new value."""
    diff = [i for i in range(width) if (old ^ new) >> i & 1]; out = set()
    for m in range(1 << len(diff)):
        v = new
        for j, i in enumerate(diff):
            if m >> j & 1: v = (v & ~(1 << i)) | (old & (1 << i))
        out.add(v)
    return out
def pointer_capture(width, gray):
    """For each pointer step b -> b+1 (mod 2**width): the set of values that can be captured, and which of them are neither the old nor the new pointer. Returns (steps, steps_with_a_wrong_value, wrong_values_total)."""
    enc = (lambda b: b ^ (b >> 1)) if gray else (lambda b: b); N = 1 << width; bad_steps = 0; bad_vals = 0
    for b in range(N):
        o, n = enc(b), enc((b + 1) % N); got = _outcomes(o, n, width); wrong = got - {o, n}
        if wrong: bad_steps += 1; bad_vals += len(wrong)
    return N, bad_steps, bad_vals
def mtbf(tr_ps, tau_ps, t0_ps, fclk_hz, fdata_hz):
    """MTBF = exp(tr / tau) / (T0 * fclk * fdata), seconds. tr: time allowed for resolution; tau, T0: device constants (ASSUMED here)."""
    x = tr_ps / tau_ps
    return math.exp(x) / (t0_ps * 1e-12 * fclk_hz * fdata_hz) if x < 700 else float("inf")
if __name__ == "__main__":
    print(pointer_capture(4, True), pointer_capture(4, False))
