#!/usr/bin/env python3
"""Chapter 4: independent models. (1) pipe_f: the pipelined function, from its definition. (2) Packet-filter models: the SPECIFICATION of what a packet filter must output (classify), and cycle-exact models of the cut-through and store-and-forward designs, written as state machines from the description, not from the Verilog. (3) Stimulus and vector files.
A packet is a list of 32-bit beats. Rules: the packet is DROPPED unless its first beat has 0xA5 in the low byte; a kept packet is BAD if the sum of the low 16 bits of all its beats (including the first) is not 0 mod 65536, otherwise GOOD."""
import random
M16 = 0xFFFF
def rnd(x, w):
    y = 0
    for j in range(w): y |= ((x >> j & 1) ^ ((x >> ((j + 1) % w) & 1) & (x >> ((j + 3) % w) & 1)) ^ (x >> ((j + 7) % w) & 1)) << j
    return y
def pipe_f(x, w=16, r=12):
    for _ in range(r): x = rnd(x, w)
    return x
def pipe_cycles(inputs, s, w=16, r=12):
    """inputs: per cycle (valid, data). Returns per cycle (out_valid, out_data) as seen before the clock edge: the input of cycle k appears s + 1 cycles later (an input register plus s stages)."""
    out = []
    for k in range(len(inputs)):
        j = k - s - 1; out.append((1, pipe_f(inputs[j][1], w, r)) if j >= 0 and inputs[j][0] else (0, 0))
    return out
def classify(pkt):
    """The specification: 'drop', 'bad' or 'good'."""
    if pkt[0] & 0xFF != 0xA5: return "drop"
    return "good" if sum(b & M16 for b in pkt) & M16 == 0 else "bad"
def make_packet(rng, n, kind):
    """kind: 'good', 'bad' or 'drop'; n beats (n >= 1). A one-beat 'good' packet cannot exist (its low byte is 0xA5, so its low 16 bits cannot sum to 0): callers ask for 'bad' instead."""
    pkt = [rng.getrandbits(32) for _ in range(n)]
    if kind == "drop":
        while pkt[0] & 0xFF == 0xA5: pkt[0] = rng.getrandbits(32)
        return pkt
    pkt[0] = (pkt[0] & ~0xFF & 0xFFFFFFFF) | 0xA5
    if kind == "good":
        assert n >= 2
        s = sum(b & M16 for b in pkt[:-1]) & M16; pkt[-1] = (pkt[-1] & ~M16 & 0xFFFFFFFF) | ((-s) & M16)
    else:
        while classify(pkt) != "bad": pkt[-1] = rng.getrandbits(32)
    return pkt
class CT:
    """Cut-through filter: one register stage; the drop decision is made on the first beat, the bad flag is raised on the last beat of a kept packet."""
    def __init__(s): s.ov = s.od = s.ol = s.ob = 0; s.inpkt = 0; s.keep = 0; s.acc = 0
    def out(s): return (s.ov, s.od, s.ol, s.ob)
    def step(s, v, d, l):
        if not v: s.ov = 0; s.ol = 0; s.ob = 0; return
        first = not s.inpkt; keep = (d & 0xFF) == 0xA5 if first else s.keep; acc = ((0 if first else s.acc) + (d & M16)) & M16
        s.ov, s.od, s.ol = int(keep), d, l; s.ob = int(bool(l and keep and acc != 0))
        s.inpkt = 0 if l else 1; s.keep = int(keep); s.acc = acc
class SF:
    """Store-and-forward filter: stores the whole packet; at the last beat decides; a good packet is then streamed out one beat per cycle, a bad or dropped one is discarded. in_ready is low while a packet is draining."""
    def __init__(s): s.ov = s.od = s.ol = 0; s.buf = []; s.acc = 0; s.drain = 0; s.rd = 0; s.total = 0
    def ready(s): return int(not s.drain)
    def out(s): return (s.ov, s.od, s.ol, 0)
    def step(s, v, d, l):
        ov = od = ol = 0
        if s.drain:
            ov, od, ol = 1, s.buf[s.rd], int(s.rd == s.total - 1)
            if s.rd == s.total - 1: s.drain = 0; s.buf = []; s.acc = 0
            s.rd += 1
        elif v:
            s.buf.append(d); s.acc = (s.acc + (d & M16)) & M16
            if l:
                if (s.buf[0] & 0xFF) == 0xA5 and s.acc == 0: s.drain = 1; s.rd = 0; s.total = len(s.buf)
                else: s.buf = []; s.acc = 0
        s.ov, s.od, s.ol = ov, od, ol
def schedule(packets, gaps):
    """Per-cycle input list (valid, data, last): packet i's beats back to back, then gaps[i] idle cycles; two idle cycles first."""
    ins = [(0, 0, 0)] * 2
    for pkt, g in zip(packets, gaps):
        for k, b in enumerate(pkt): ins.append((1, b, int(k == len(pkt) - 1)))
        ins += [(0, 0, 0)] * g
    return ins + [(0, 0, 0)] * 80
def run(model, ins):
    """Returns per cycle (in_ready, out_valid, out_data, out_last, out_bad) as seen before the clock edge."""
    m = model(); res = []
    for v, d, l in ins:
        r = m.ready() if hasattr(m, "ready") else 1; ov, od, ol, ob = m.out(); res.append((r, ov, od, ol, ob)); m.step(v, d, l)
    return res
def gen(seed, kind_mix, count, maxlen, dense):
    """Packets and gaps. kind_mix: weights for (good, bad, drop). dense: gaps 0..2 (for the cut-through filter); otherwise gaps are long enough for the store-and-forward filter to drain (gap >= length + 2)."""
    rng = random.Random(seed); pk = []; gp = []
    for _ in range(count):
        n = rng.randint(1, maxlen); kind = rng.choices(["good", "bad", "drop"], kind_mix)[0]
        if kind == "good" and n == 1: kind = "bad"
        pk.append(make_packet(rng, n, kind)); gp.append(rng.randint(0, 2) if dense else n + 2 + rng.randint(0, 3))
    return pk, gp
def write_vectors(path, ins, res):
    """One line per cycle: in_valid in_last in_data(hex) | expected in_ready out_valid out_last out_bad out_data(hex)."""
    with open(path, "w") as f:
        for (v, d, l), (r, ov, od, ol, ob) in zip(ins, res): f.write(f"{v}{l}{r}{ov}{ol}{ob}{d:08x}{od:08x}\n")
def pipe_vectors(path, s, cycles, seed, w=16, r=12, p_valid=0.7):
    """Random valid/data stream; one line per cycle: in_valid in_data(4 hex) out_valid out_data(4 hex), the outputs as the golden model says. Returns the number of valid outputs."""
    rng = random.Random(seed); ins = [(int(rng.random() < p_valid), rng.getrandbits(w)) for _ in range(cycles)]; out = pipe_cycles(ins, s, w, r); n = 0
    with open(path, "w") as f:
        for (v, d), (ov, od) in zip(ins, out): f.write(f"{v}{d:04x}{ov}{od:04x}\n"); n += ov
    return n
