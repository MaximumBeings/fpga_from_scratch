#!/usr/bin/env python3
"""Chapter 2: the golden model of the valid/ready stages and their chain, cycle by cycle, and the stimulus.
Each stage is a state machine written from the specification, not from the Verilog: a stage holds up to one item (two for the skid stage). Per cycle, from the outside: ready_in is a function of the stage's state (and, for the 'comb' stage, of ready_out); an item moves in when valid_in && ready_in; the output holds while valid_out && !ready_out.
A chain of N stages is evaluated back to front (ready flows from the output towards the input; valid and data flow forward from registered outputs). The vector file has one word per cycle: {expected out_data, expected out_valid, expected in_ready, out_ready, in_valid, in_data}. Usage: vr_gold.py STYLE N W CYCLES SEED PROFILE OUTFILE"""
import random, sys
class Slow:
    def __init__(s): s.v = 0; s.d = 0
    def ready_in(s, ro): return int(not s.v)
    def step(s, vi, di, ro):
        if vi and s.ready_in(ro): s.v, s.d = 1, di
        elif ro: s.v = 0
class Comb:
    def __init__(s): s.v = 0; s.d = 0
    def ready_in(s, ro): return int(bool(ro) or not s.v)
    def step(s, vi, di, ro):
        if s.ready_in(ro): s.v, s.d = int(bool(vi)), di
class Skid:
    def __init__(s): s.v = 0; s.d = 0; s.sv = 0; s.sd = 0
    def ready_in(s, ro): return int(not s.sv)
    def step(s, vi, di, ro):
        ri = s.ready_in(ro)
        if ro or not s.v:
            if s.sv: s.d, s.v, s.sv = s.sd, 1, 0
            else: s.d, s.v = di, int(bool(vi))
        elif vi and ri: s.sd, s.sv = di, 1
KINDS = [Slow, Comb, Skid]
def run_chain(style, n, inputs):
    """inputs: list of (in_valid, in_data, out_ready) per cycle. Returns per cycle (in_ready, out_valid, out_data) as seen before the clock edge."""
    st = [KINDS[style]() for _ in range(n)]; out = []
    for vi, di, ro in inputs:
        rdy = [0] * (n + 1); rdy[n] = int(bool(ro))
        for k in range(n - 1, -1, -1): rdy[k] = st[k].ready_in(rdy[k + 1])
        vlink = [int(bool(vi))] + [s.v for s in st]; dlink = [di] + [s.d for s in st]
        out.append((rdy[0], st[-1].v, st[-1].d))
        for k in range(n): st[k].step(vlink[k], dlink[k], rdy[k + 1])
    return out
PROFILES = {"free": (1.0, 1.0), "bursty": (0.6, 0.5), "slow_sink": (0.9, 0.25), "slow_source": (0.25, 0.9), "random": (0.5, 0.5)}
def stimulus(w, cycles, seed, profile):
    if profile == "mixed":                                   # consecutive segments of 100 cycles in four different traffic profiles
        out = []; names = ["random", "bursty", "slow_sink", "slow_source", "free"]; k = 0
        while len(out) < cycles: out += stimulus(w, 100, seed + k, names[k % len(names)]); k += 1
        return out[:cycles]
    R = random.Random(seed); pv, pr = PROFILES[profile]; ins = []; cnt = 1
    for t in range(cycles):
        if profile == "bursty": ro = int((t // 7) % 2 == 0 or R.random() < 0.15); vi = int(R.random() < pv + 0.4 * ((t // 11) % 2))     # bursts of ready and of not-ready
        else: ro = int(R.random() < pr); vi = int(R.random() < pv)
        ins.append((vi, (cnt * 2654435761) & ((1 << w) - 1) if vi else R.getrandbits(w), ro)); cnt += vi
    return ins
def pack(w, vi, di, ro, ri, ov, od): return (((((od << 1 | ov) << 1 | ri) << 1 | ro) << 1 | vi) << w) | di
def write(style, n, w, cycles, seed, profile, path):
    ins = stimulus(w, cycles, seed, profile); exp = run_chain(style, n, ins)
    with open(path, "w") as f:
        for (vi, di, ro), (ri, ov, od) in zip(ins, exp): f.write("%x\n" % pack(w, vi, di, ro, ri, ov, od))
    return len(ins), exp, ins
if __name__ == "__main__":
    st, n, w, cyc, seed, prof, out = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), sys.argv[6], sys.argv[7]; print(write(st, n, w, cyc, seed, prof, out)[0], "cycles written")
