#!/usr/bin/env python3
"""Chapter 10: the specification of the match engines and the control plane that fills the hash tables.
CAM-like engines (exact, ternary, range): a list of N slots; a query returns the LOWEST valid slot that matches. Hash engines: the specification is a SET of keys with values; the control plane (HashPlane below) decides which slot each key goes to (it knows the hash), and a key it could not place is simply absent from the set: the hardware must say "miss" for it. With a stored fingerprint (KW < 32) the structure may also answer "hit" for keys never inserted; `HashPlane.lookup` emulates the structure for that case and the measured false-positive rate is reported against the set.
Stimulus lines (see tb/match_tb.sv): type(0 idle,1 write,2 query) sel addr key aux val vld."""
import random
M32 = 0xFFFFFFFF
def rotl13(k): return ((k << 13) | (k >> 19)) & M32
def fold(x, aw):
    s = 0
    for i in range(0, 32, aw): s ^= (x >> i) & ((1 << aw) - 1)
    return s
def h1(k, aw): return fold(k, aw)
def h2(k, aw): return fold(rotl13(k) ^ (k >> 5), aw)
EXACT, TERNARY, RANGE = 0, 1, 2
def cam_match(mode, e, q):
    key, aux, val, vld = e
    if not vld: return False
    if mode == EXACT: return key == q
    if mode == TERNARY: return ((key ^ q) & aux) == 0
    return (aux & 0xFFFF) <= (q & 0xFFFF) <= (aux >> 16)
def cam_lookup(mode, entries, q):
    for e in entries:
        if e and cam_match(mode, e, q): return (1, e[2])
    return (0, 0)
def line(t, sel=0, addr=0, key=0, aux=0, val=0, vld=0): return f"{t:x}{sel:x}{addr:04x}{key:08x}{aux:08x}{val:02x}{vld:x}"
def junk(rng): return line(0, rng.getrandbits(1), rng.getrandbits(12), rng.getrandbits(32), rng.getrandbits(32), rng.getrandbits(8), rng.getrandbits(1))
def write_stim(path, lines):
    with open(path, "w") as f: f.write("\n".join(lines) + "\n")
    return len(lines)
def cam_ops(seed, mode, n, nops=700, idle=15, clear=True):
    """-> (lines, expected). Writes, deletes and queries interleaved; every query's expected result is computed against the slots as they are at that point of the sequence. Overlapping entries (ternary, range) test the priority. Queries also use keys of entries that have been deleted or overwritten (they must miss). With clear=False the slots are not cleared by writes and the engine must come out of reset empty."""
    rng = random.Random(seed * 7919 + mode); ent = [None] * n; lines = []; exp = []; dead = []
    pool = [rng.getrandbits(32) for _ in range(6)]                   # a small pool of keys so that exact entries collide, and queries hit more than one slot
    def mk():
        val = rng.getrandbits(8)
        if mode == EXACT: return (rng.choice(pool) if rng.random() < .4 else rng.getrandbits(32), rng.getrandbits(32), val, 1)
        if mode == TERNARY:
            p = rng.choice([0, 1, 8, 16, 24, 31, 32, rng.randint(0, 32)]); mask = (M32 << (32 - p)) & M32 if rng.random() < .7 else rng.getrandbits(32)
            return (rng.getrandbits(32), mask, val, 1)               # key bits outside the mask are random: the hardware must not need them cleared
        lo = rng.choice([0, 1, 80, 443, 1024, 65535, rng.getrandbits(16)]); hi = rng.choice([lo, lo + 1, lo + rng.randint(0, 3000), 65535, rng.getrandbits(16)]) & 0xFFFF
        if rng.random() < .85 and hi < lo: lo, hi = hi, lo           # a few empty ranges are left in
        return (rng.getrandbits(32), lo | (hi << 16), val, 1)
    def query():
        live = [e for e in ent if e and e[3]]
        if dead and rng.random() < .2: e = rng.choice(dead); return (e[0] if mode != RANGE else (rng.getrandbits(16) << 16) | (e[1] & 0xFFFF)) if mode != TERNARY else ((e[0] & e[1]) | (rng.getrandbits(32) & ~e[1] & M32))
        if live and rng.random() < .65:
            e = rng.choice(live); key, aux = e[0], e[1]
            if mode == EXACT: q = key if rng.random() < .8 else key ^ (1 << rng.choice([0, 31, rng.randrange(32)]))
            elif mode == TERNARY:
                q = (key & aux) | (rng.getrandbits(32) & ~aux & M32)       # any bits where the mask does not care
                care = [i for i in range(32) if (aux >> i) & 1]
                if care and rng.random() < .3: q ^= 1 << rng.choice([min(care), max(care), rng.choice(care)])      # a near miss on a bit the mask cares about, the extreme ones included
            else:
                lo, hi = aux & 0xFFFF, aux >> 16; q = (rng.getrandbits(16) << 16) | (rng.choice([lo, hi, (lo - 1) & 0xFFFF, (hi + 1) & 0xFFFF, (lo + hi) // 2, rng.getrandbits(16)]))
            return q & M32
        return rng.getrandbits(32) if mode != RANGE else rng.getrandbits(32)
    if not clear:
        for q in (0, 0, M32): lines.append(line(2, 0, 0, q, 0, 0, 0)); exp.append((0, 0))     # straight after reset every slot must be empty (the testbench powers the registers up with garbage)
    if clear:
        for a in range(n): lines.append(line(1, 0, a, 0, 0, 0, 0))          # clear every slot (the CAM also clears itself in reset; the hash tables need this)
    for _ in range(nops):
        while rng.randrange(100) < idle: lines.append(junk(rng))
        r = rng.random()
        if r < .30:
            a = rng.randrange(n); e = mk()
            if ent[a]: dead.append(ent[a])
            ent[a] = e; lines.append(line(1, 0, a, e[0], e[1], e[2], 1))
        elif r < .38:
            a = rng.randrange(n); old = ent[a]
            if old: dead.append(old)
            ent[a] = None                                               # deleting clears the valid bit only; half the time the old key stays in the slot, as when software just flips the flag
            lines.append(line(1, 0, a, old[0], old[1], old[2], 0) if (old and rng.random() < .5) else line(1, 0, a, rng.getrandbits(32), rng.getrandbits(32), rng.getrandbits(8), 0))
        else:
            q = query(); lines.append(line(2, 0, 0, q, rng.getrandbits(32), rng.getrandbits(8), rng.getrandbits(1))); exp.append(cam_lookup(mode, ent, q))
    return lines, exp
class HashPlane:
    """The control plane of a hash engine: knows both hashes, places keys, remembers where they are. insert() returns the write lines to issue and whether it succeeded."""
    def __init__(self, aw, ch, kw=32):
        self.aw, self.ch, self.kw = aw, ch, kw; self.slot = [dict() for _ in range(ch)]; self.where = {}; self.val = {}
    def idx(self, sel, k): return h1(k, self.aw) if sel == 0 else h2(k, self.aw)
    def clear_lines(self): return [line(1, s, a, 0, 0, 0, 0) for s in range(self.ch) for a in range(1 << self.aw)]
    def insert(self, k, v):
        if k in self.where: s, a = self.where[k]; self.val[k] = v; return [line(1, s, a, k, 0, v, 1)], True      # update in place
        for s in range(self.ch):
            a = self.idx(s, k)
            if a not in self.slot[s]: self.slot[s][a] = k; self.where[k] = (s, a); self.val[k] = v; return [line(1, s, a, k, 0, v, 1)], True
        return [], False
    def delete(self, k):
        s, a = self.where.pop(k); del self.slot[s][a]; del self.val[k]; return [line(1, s, a, 0, 0, 0, 0)]
    def lookup(self, q):
        """The structure's answer for key q (a fingerprint compare when kw < 32)."""
        m = (1 << self.kw) - 1
        for s in range(self.ch):
            a = self.idx(s, q)
            if a in self.slot[s] and (self.slot[s][a] & m) == (q & m): return (1, self.val[self.slot[s][a]])
        return (0, 0)
    def load(self): return len(self.where) / (self.ch << self.aw)
def keys_of(kind, rng, n):
    """kind: random 32-bit keys; seq (consecutive, a subnet); mcast (IPv4 multicast group addresses 224.0.0.0/4); stride (multiples of 2**12: a typical aligned allocation)."""
    out = set()
    base = rng.getrandbits(32) & ~0xFF
    while len(out) < n:
        i = len(out)
        if kind == "random": out.add(rng.getrandbits(32))
        elif kind == "seq": out.add((base + i) & M32)
        elif kind == "mcast": out.add(0xE0000000 | rng.getrandbits(28))
        elif kind == "stride": out.add((i << 12) & M32)
        else: raise ValueError(kind)
    return sorted(out) if kind in ("seq", "stride") else list(out)
def hash_ops(seed, aw, ch, kw, nmem, kind="random", nq=500, churn=True, idle=15):
    """-> (lines, expected, stats). Clear, insert nmem keys, query, delete 25% and insert new ones, query again. Expected results come from the structure's emulation (== the key set when kw = 32: asserted)."""
    rng = random.Random(seed * 104729 + aw * 7 + ch); hp = HashPlane(aw, ch, kw); lines = hp.clear_lines(); exp = []; fails = 0; mem = keys_of(kind, rng, nmem + nmem // 3 + 4); first, extra = mem[:nmem], mem[nmem:]
    vals = {}
    for k in first:
        v = rng.getrandbits(8); w, ok = hp.insert(k, v); lines += w; fails += not ok
    def queries(n):
        nonlocal lines
        pool_in = list(hp.where); pool_all = first + extra
        for _ in range(n):
            while rng.randrange(100) < idle: lines.append(junk(rng))
            r = rng.random(); q = rng.choice(pool_in) if (r < .4 and pool_in) else (rng.choice(pool_all) if r < .6 else rng.getrandbits(32))
            if r >= .8 and pool_in:                                # a key that hashes to the same bucket of table 0 as a member (two bits that fold onto each other differ) but is not the member
                i = rng.randrange(32 - aw); q = rng.choice(pool_in) ^ (1 << i) ^ (1 << (i + aw))
            lines.append(line(2, 0, 0, q, rng.getrandbits(32), rng.getrandbits(8), rng.getrandbits(1))); e = hp.lookup(q); exp.append(e)
            if kw == 32: assert e == ((1, hp.val[q]) if q in hp.where else (0, 0))
    queries(nq)
    if churn:
        for k in rng.sample(list(hp.where), max(1, len(hp.where) // 4)): lines += hp.delete(k)
        for k in extra:
            v = rng.getrandbits(8); w, ok = hp.insert(k, v); lines += w; fails += not ok
        queries(nq)
    return lines, exp, dict(placed=len(hp.where), failed=fails, load=hp.load())
if __name__ == "__main__":
    # a hand-checked case: ternary 10.0.0.0/8 then 10.1.0.0/16 at a LATER slot: the lowest slot wins even if the later one is more specific
    e = [(0x0A000000, 0xFF000000, 1, 1), (0x0A010000, 0xFFFF0000, 2, 1), None]
    assert cam_lookup(TERNARY, e, 0x0A010203) == (1, 1) and cam_lookup(TERNARY, e, 0x0B000000) == (0, 0)
    assert cam_lookup(RANGE, [(0, 80 | (90 << 16), 7, 1)], 80) == (1, 7) and cam_lookup(RANGE, [(0, 80 | (90 << 16), 7, 1)], 91) == (0, 0) and cam_lookup(RANGE, [(0, 90 | (80 << 16), 7, 1)], 85) == (0, 0)
    assert fold(0x12345678, 8) == 0x12 ^ 0x34 ^ 0x56 ^ 0x78 and fold(0xFFFFFFFF, 12) == (0xFFF ^ 0xFFF ^ 0xFF)
    for m in (0, 1, 2): lines, exp = cam_ops(1, m, 16); print("cam mode", m, len(lines), "cycles", len(exp), "queries,", sum(h for h, _ in exp), "hits")
    for kind in ("random", "seq", "mcast", "stride"):
        lines, exp, st = hash_ops(1, 6, 2, 32, 90, kind, 200); print("hash", kind, st, sum(h for h, _ in exp), "hits of", len(exp))
    print("model self-test passed")
