#!/usr/bin/env python3
"""Chapter 11: the specification of the UDP frame builder and the pacer.
build_body(): the frame (Ethernet header to payload, no FCS) the builder must send for a payload, destination port and address, written from RFC 791/768/1071 with the helper functions of ip_gold; expected_wire() adds mac_gold's preamble, padding and FCS. Pacer: a cycle-exact model of the token bucket. Stimulus: descriptors (dport, dip, len) and payload bytes."""
import os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ip_gold as ip, mac_gold as mg
DMAC = bytes.fromhex("AABBCCDDEEFF"); SMAC = bytes.fromhex("021122334455"); SIP = ip.ip4(10, 0, 0, 1); SPORT = 0x1234; MAXP = 1472
def build_body(payload, dport, dip, pid, ct=False):
    ulen = 8 + len(payload)
    udp0 = SPORT.to_bytes(2, "big") + dport.to_bytes(2, "big") + ulen.to_bytes(2, "big") + b"\0\0" + payload
    if ct: ucs = 0
    else:
        pseudo = SIP.to_bytes(4, "big") + dip.to_bytes(4, "big") + b"\x00\x11" + ulen.to_bytes(2, "big")
        ucs = ip.inet_csum(pseudo + udp0); ucs = ucs or 0xFFFF
    udp = udp0[:6] + ucs.to_bytes(2, "big") + udp0[8:]
    h = bytes([0x45, 0]) + (20 + ulen).to_bytes(2, "big") + pid.to_bytes(2, "big") + b"\x40\x00" + bytes([64, 17, 0, 0]) + SIP.to_bytes(4, "big") + dip.to_bytes(4, "big")
    h = h[:10] + ip.inet_csum(h).to_bytes(2, "big") + h[12:]
    return DMAC + SMAC + b"\x08\x00" + h + udp
def expected_wire(payload, dport, dip, pid, ct=False): return mg.spec_tx(build_body(payload, dport, dip, pid, ct))
def wire_cost(payload_len): return max(60, 42 + payload_len) + 24            # preamble 8 + frame (padded) + FCS 4 + gap 12
def csum_zero_payload(rng, n, dport, dip):
    """A payload of n >= 2 bytes (even) whose UDP checksum computes to 0, so the sender must transmit 0xFFFF."""
    p = bytearray(rng.getrandbits(8) for _ in range(n)); p[-2:] = b"\0\0"
    ulen = 8 + n; pseudo = SIP.to_bytes(4, "big") + dip.to_bytes(4, "big") + b"\x00\x11" + ulen.to_bytes(2, "big")
    s = ip.csum(pseudo + SPORT.to_bytes(2, "big") + dport.to_bytes(2, "big") + ulen.to_bytes(2, "big") + b"\0\0" + bytes(p))
    w = (0xFFFF - s) & 0xFFFF; p[-2:] = w.to_bytes(2, "big"); return bytes(p)
def make_packets(seed, n, maxp=MAXP, oversize=False, sizes=None):
    rng = random.Random(seed); out = []
    sizes = sizes or [1, 2, 3, 4, 17, 18, 19, 20, 100, 1000, 1471, 1472]
    for i in range(n):
        kind = rng.choice(["rand", "rand", "ff", "zero", "csz", "odd"] + (["big"] if oversize else []))
        L = rng.choice(sizes + [rng.randint(1, 300)]); dport = rng.choice([0, 1, 5000, 0xFFFF, rng.getrandbits(16)]); dip = rng.choice([ip.ip4(192, 168, 1, 10), rng.getrandbits(32), 0xFFFFFFFF, 0])
        if kind == "big": L = maxp + rng.choice([1, 2, 7])
        if kind == "odd" and L % 2 == 0: L += 1 if L < maxp else -1
        if kind == "ff": p = bytes(rng.choice([0xFF, 0xFF, 0xFE, rng.getrandbits(8)]) for _ in range(L))
        elif kind == "zero": p = bytes(L)
        elif kind == "csz": L = max(2, L + L % 2); L = min(L, maxp - maxp % 2); p = csum_zero_payload(rng, L, dport, dip)
        else: p = bytes(rng.getrandbits(8) for _ in range(L))
        out.append(dict(payload=p, dport=dport, dip=dip))
    if oversize:                                                   # the boundary of the store-and-forward builder, exactly: the largest payload it takes and the smallest it drops
        for L in (maxp, maxp + 1, maxp):
            out.insert(rng.randrange(len(out) + 1), dict(payload=bytes(rng.getrandbits(8) for _ in range(L)), dport=5000, dip=ip.ip4(192, 168, 1, 10)))
    return out
def write_pkts(pk, desc="out/udp_desc.hex", byt="out/udp_bytes.hex"):
    with open(desc, "w") as f:
        for q in pk: f.write(f"{q['dport']:04x}{q['dip']:08x}{len(q['payload']):04x}\n")
    with open(byt, "w") as f:
        for q in pk:
            for b in q["payload"]: f.write(f"{b:02x}\n")
def expected_frames(pk, maxp=MAXP, ct=False):
    """-> (wire frames for the packets that are not dropped, number dropped, ids): the frame id counts emitted packets."""
    out = []; drop = 0
    for q in pk:
        if len(q["payload"]) > maxp: drop += 1; continue
        out.append(expected_wire(q["payload"], q["dport"], q["dip"], len(out) & 0xFFFF, ct))
    return out, drop
class PacerModelComb:
    """The first pacer: grant when the credit covers the cost, in the same cycle."""
    def __init__(self, burst=4096): self.cap = burst << 8; self.credit = self.cap
    def step(self, req, ln, rate):
        cost = ln << 8; go = bool(req) and self.credit >= cost; after = self.credit - cost if go else self.credit
        self.credit = min(self.cap, after + rate); return go
class PacerModel:
    """The final pacer, register for register. The first cycle after reset sees the registers as the last cycle of reset left them (the testbench holds req = 1 and len = 1538 in reset)."""
    def __init__(self, burst=4096, rate=0):
        self.cap = burst << 8; self.credit = self.cap; self.cost_r = 1538 << 8; self.d_r = rate - (1538 << 8); self.ok_r = False; self.r1 = False; self.r2 = False
    def step(self, req, ln, rate):
        go = bool(req) and self.r2 and self.ok_r
        nxt = min(self.cap, self.credit + (self.d_r if go else rate)); assert nxt >= 0 or not go
        self.d_r, self.cost_r, self.ok_r = rate - self.cost_r, ln << 8, (self.credit >= self.cost_r) and not go
        self.r2, self.r1 = self.r1, bool(req); self.credit = nxt; return go
def pacer_stim(seed, ncyc, maxlen=1538):
    """Requests that hold their length for at least 4 cycles (the precondition of the pipelined pacer) and change it at random after that."""
    rng = random.Random(seed); out = []
    while len(out) < ncyc:
        hold = (1 if rng.random() < .7 else 0, rng.choice([84, 84, 1538, 1000, 84, rng.randint(1, maxlen)])); out += [hold] * rng.choice([4, 4, 5, 8, 30, 200, 2000])
    return out[:ncyc]
def write_pacer(path, st):
    with open(path, "w") as f:
        for r, ln in st: f.write(f"{r:x}{ln:03x}\n")
if __name__ == "__main__":
    # RFC-independent sanity: a known UDP frame has a header checksum that sums to 0xFFFF and the filter of Chapter 9 accepts it
    pk = make_packets(1, 60); bad = 0
    cfg = ip.DEFAULT_CFG | {"ip_en": 0, "plo": 0, "phi": 65535}
    for i, q in enumerate(pk):
        b = build_body(q["payload"], q["dport"], q["dip"], i); b = b + bytes(max(0, 60 - len(b))); s = ip.spec(b, 0, cfg)
        if s["cause"] != 0 or s["dport"] != q["dport"] or s["dip"] != q["dip"]: bad += 1
    print("builder output accepted by the Chapter 9 filter:", len(pk) - bad, "of", len(pk))
    c = sum(1 for q in pk if q["payload"] and build_body(q["payload"], q["dport"], q["dip"], 0)[40:42] == b"\xff\xff"); print("frames with a UDP checksum of 0xFFFF:", c)
    m = PacerModel(rate=64); n = 0
    for _ in range(100000): n += m.step(1, 1000, 64)
    print("pacer model: 100,000 cycles at 64/256 byte per cycle with 1000-byte requests ->", n, "grants (derived about", 100000 * 64 // 256 // 1000 + 4, ")")
