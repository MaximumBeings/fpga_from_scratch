#!/usr/bin/env python3
"""Chapter 9: the specification of the header filter, written from RFC 791 (IPv4), RFC 768 (UDP), RFC 1071 (the checksum) and IEEE 802.1Q (VLAN), not from the RTL.
A frame body arrives as bytes (the MAC has already removed the FCS). The filter decides a CAUSE for each frame:
  0 forward   1 mac_bad (the MAC marked it)   2 trunc (the frame ends inside the headers)   3 not_ip   4 ip_bad   5 not_udp   6 udp_bad   7 not_ours
and reports the fields it saw. `spec()` returns them; `frames()` makes the stimulus. Run it for a self-test of the model against known checksums."""
import random
FWD, MACBAD, TRUNC, NOTIP, IPBAD, NOTUDP, UDPBAD, NOTOURS = range(8)
NAMES = ["forward", "mac_bad", "trunc", "not_ip", "ip_bad", "not_udp", "udp_bad", "not_ours"]
VLAN_TYPES = (0x8100, 0x88A8)
def csum(b):
    """RFC 1071: the ones' complement sum of the 16-bit big-endian words (an odd last byte is padded with a zero byte), folded to 16 bits. NOT inverted."""
    if len(b) % 2: b = b + b"\x00"
    s = sum((b[i] << 8) | b[i + 1] for i in range(0, len(b), 2))
    while s >> 16: s = (s & 0xFFFF) + (s >> 16)
    return s
def inet_csum(b): return (~csum(b)) & 0xFFFF            # the value a sender puts in the checksum field
def ip4(a, b_, c, d): return (a << 24) | (b_ << 16) | (c << 8) | d
DEFAULT_CFG = {"ip_en": 1, "ip": ip4(192, 168, 1, 10), "vid_en": 0, "vid": 100, "plo": 5000, "phi": 5999}
def spec(body, bad, cfg=DEFAULT_CFG):
    """-> dict(cause, ntags, vid, sip, dip, sport, dport, ulen). Fields are zero unless the byte that carries them was seen."""
    L = len(body); r = dict(cause=FWD, ntags=0, vid=0, sip=0, dip=0, sport=0, dport=0, ulen=0)
    def b(i): return body[i] if 0 <= i < L else 0
    def w(i): return (b(i) << 8) | b(i + 1)
    def done(c): r["cause"] = MACBAD if bad else c; return r
    if L < 14: return done(TRUNC)
    off = 12; typ = w(12)
    while True:
        if typ in VLAN_TYPES and r["ntags"] < 2:
            r["ntags"] += 1
            if r["ntags"] == 1: r["vid"] = ((b(off + 2) & 0xF) << 8) | b(off + 3)
            if L < off + 6: return done(TRUNC)
            off += 4; typ = w(off)
        elif typ == 0x0800: break
        else: return done(NOTIP)
    ip0 = off + 2; n = L - ip0
    if n < 1: return done(TRUNC)
    ihl = b(ip0) & 15; hl = 4 * max(ihl, 5)
    r["sip"] = (w(ip0 + 12) << 16) | w(ip0 + 14); r["dip"] = (w(ip0 + 16) << 16) | w(ip0 + 18)       # captured byte by byte, so zero for bytes never seen
    if n < hl: return done(TRUNC)
    tot = w(ip0 + 2); frag = w(ip0 + 6); proto = b(ip0 + 9)
    if proto == 17:
        u0 = ip0 + hl; r["sport"] = w(u0); r["dport"] = w(u0 + 2); r["ulen"] = w(u0 + 4)
    ok = (b(ip0) >> 4) == 4 and ihl >= 5 and csum(bytes(body[ip0:ip0 + hl])) == 0xFFFF and tot >= hl and tot <= n
    if not ok: return done(IPBAD)
    if proto != 17 or (frag & 0x3FFF): return done(NOTUDP)
    u0 = ip0 + hl; ulen = r["ulen"]; ucs = w(u0 + 6)
    if ulen < 8 or ulen > tot - hl: return done(UDPBAD)
    if ucs != 0:
        pseudo = bytes(body[ip0 + 12:ip0 + 20]) + b"\x00\x11" + ulen.to_bytes(2, "big")
        if csum(pseudo + bytes(body[u0:u0 + ulen])) != 0xFFFF: return done(UDPBAD)
    if cfg["vid_en"] and (r["ntags"] == 0 or r["vid"] != cfg["vid"]): return done(NOTOURS)
    if cfg["ip_en"] and r["dip"] != cfg["ip"]: return done(NOTOURS)
    if not (cfg["plo"] <= r["dport"] <= cfg["phi"]): return done(NOTOURS)
    return done(FWD)
# ---------------------------------------------------------------- building frames
KINDS = ["good", "good_vlan", "good_qinq", "good_opts", "csum_zero", "no_csum", "odd_len", "carry_heavy", "ip_csum", "udp_csum", "ver6", "ihl4", "tot_big", "tot_small", "ulen_small", "ulen_big", "frag_mf", "frag_off", "tcp", "trailer", "arp", "three_tags", "truncated", "mac_bad", "wrong_ip", "wrong_port", "wrong_vid", "bits"]
def build(kind, rng, cfg=DEFAULT_CFG):
    """-> (body, bad_in). Starts from a valid UDP frame for the filter's configuration and breaks one thing."""
    ntags = {"good_vlan": 1, "good_qinq": 2, "three_tags": 3}.get(kind, 1 if (cfg["vid_en"] and kind not in ("wrong_vid",) and rng.random() < 0.8) else rng.choice([0, 0, 0, 1]))
    vid = cfg["vid"] if (kind != "wrong_vid") else (cfg["vid"] + 1 + rng.randrange(50)) & 0xFFF
    if kind == "wrong_vid" and cfg["vid_en"] and rng.random() < 0.3: ntags = 0
    ihl = 5 + (rng.randint(1, 5) if kind == "good_opts" else rng.choice([0, 0, 0, 1]))
    plen = rng.choice([0, 1, 2, 7, 18, 19, 22, 100, rng.randint(0, 200)])
    if kind == "odd_len": plen = rng.choice([1, 3, 17, 101, 199])
    if kind in ("carry_heavy", "csum_zero"): plen = rng.choice([16, 32, 33, 64])
    if kind == "carry_heavy": payload = bytes(rng.choice([0xFF, 0xFF, 0xFF, 0x00, rng.getrandbits(8)]) for _ in range(plen))
    else: payload = bytes(rng.getrandbits(8) for _ in range(plen))
    dip = cfg["ip"] if (cfg["ip_en"] and kind != "wrong_ip") else rng.choice([cfg["ip"], rng.getrandbits(32)])
    if kind == "wrong_ip" and dip == cfg["ip"]: dip ^= 0x100
    if kind == "wrong_port": dport = (cfg["phi"] + 1 + rng.randrange(40)) & 0xFFFF if rng.random() < 0.5 else (cfg["plo"] - 1 - rng.randrange(40)) & 0xFFFF
    else: dport = rng.choice([cfg["plo"], cfg["phi"], rng.randint(cfg["plo"], cfg["phi"])])
    if kind == "wrong_port" and cfg["plo"] <= dport <= cfg["phi"]: dport = (cfg["phi"] + 1) & 0xFFFF
    sip = rng.getrandbits(32); sport = rng.getrandbits(16)
    ulen = 8 + len(payload)
    def udp(ulen_field=None, force_csum=None):
        ul = ulen if ulen_field is None else ulen_field
        hdr = sport.to_bytes(2, "big") + dport.to_bytes(2, "big") + ul.to_bytes(2, "big") + b"\x00\x00"
        pseudo = sip.to_bytes(4, "big") + dip.to_bytes(4, "big") + b"\x00\x11" + ul.to_bytes(2, "big")
        c = inet_csum(pseudo + hdr + payload)
        if kind == "csum_zero":
            # make the sum of everything but the last payload word equal to what turns the checksum into zero: the sender then transmits 0xFFFF
            body_ = bytearray(payload); wd = len(body_) // 2 * 2 - 2; body_[wd:wd + 2] = b"\x00\x00"
            s = csum(pseudo + hdr + bytes(body_)); want = (0xFFFF - s) & 0xFFFF if s != 0xFFFF else 0xFFFF
            body_[wd:wd + 2] = want.to_bytes(2, "big"); payload_ = bytes(body_); c = inet_csum(pseudo + hdr + payload_); return hdr[:6] + (0xFFFF if c == 0 else c).to_bytes(2, "big") + payload_
        if c == 0: c = 0xFFFF
        if kind == "no_csum" or (kind == "ulen_small" and rng.random() < 0.5): c = 0        # (a too-short length must be refused even when there is no checksum to refuse it)
        if kind == "udp_csum": c ^= 1 << rng.randrange(16)
        if force_csum is not None: c = force_csum
        return hdr[:6] + c.to_bytes(2, "big") + payload
    if kind == "ulen_small": ulen_f = rng.choice([0, 1, 7, rng.randint(0, 7)])
    elif kind == "ulen_big": ulen_f = ulen + rng.choice([1, 2, 9, 400])
    else: ulen_f = None
    seg = udp(ulen_f)
    proto = rng.choice([6, 1, 2, 47, 0, 16, 18, 255, 6]) if kind == "tcp" else 17
    if kind == "trailer": seg = seg + bytes(rng.getrandbits(8) for _ in range(rng.randint(1, 20)))      # bytes after the UDP datagram, inside the IP packet: not part of the checksum
    tot = ihl * 4 + len(seg)
    if kind == "tot_big": tot += rng.choice([1, 2, 100, 1000]) + max(0, 60 - 14 - tot)        # always past the end of even a padded frame
    if kind == "tot_small": tot = rng.choice([ihl * 4 - 1, ihl * 4 - 4, ihl * 4, 0, 20 if ihl > 5 else 19, ihl * 4 + 7 if len(seg) >= 8 else 0])
    frag = 0x4000 if rng.random() < 0.3 else 0
    if kind == "frag_mf": frag |= 0x2000
    if kind == "frag_off": frag |= rng.randint(1, 0x1FFF)
    ver = rng.choice([5, 3, 6, 7, 0, 12, 15, 5]) if kind == "ver6" else 4        # versions other than 4, the near misses first
    ih = 4 if kind == "ihl4" else ihl
    opts = bytes(rng.getrandbits(8) for _ in range((ihl - 5) * 4))
    ip = bytes([(ver << 4) | ih, rng.getrandbits(8)]) + tot.to_bytes(2, "big") + rng.getrandbits(16).to_bytes(2, "big") + frag.to_bytes(2, "big") + bytes([rng.randint(1, 255), proto, 0, 0]) + sip.to_bytes(4, "big") + dip.to_bytes(4, "big") + opts
    hl = 4 * max(ihl, 5) if kind != "ihl4" else 20
    c = inet_csum(ip[:hl]) if True else 0
    if kind == "ip_csum": c ^= 1 << rng.randrange(16)
    ip = ip[:10] + c.to_bytes(2, "big") + ip[12:]
    pkt = ip + seg
    dst = bytes(rng.getrandbits(8) for _ in range(6)); src = bytes(rng.getrandbits(8) for _ in range(6))
    eth = dst + src
    for t in range(ntags): eth += (0x8100 if (t == 0 or rng.random() < 0.5) else 0x88A8).to_bytes(2, "big") + ((rng.getrandbits(3) << 13) | (vid if t == 0 else rng.getrandbits(12))).to_bytes(2, "big")
    if kind == "arp": body = eth + (0x0806).to_bytes(2, "big") + bytes(rng.getrandbits(8) for _ in range(28))
    else: body = eth + (0x0800).to_bytes(2, "big") + pkt
    if kind == "bits": body = bytes(rng.getrandbits(8) for _ in range(rng.randint(1, 120)))
    bad = 0
    if kind == "mac_bad": bad = 1
    if kind == "truncated": body = body[:rng.randint(1, len(body) - 1)] if len(body) > 1 else body
    elif len(body) < 60: body = body + bytes(60 - len(body))
    if kind == "truncated" and rng.random() < 0.5:
        body = body[:rng.choice([12, 13, 14, 15, 16, 17, 18, 20, 33, 34, 35, 36, 37, 41, 42, 43, 49])]      # cuts at the interesting offsets
    return body, bad
def frames(seed, n, cfg=DEFAULT_CFG, weights=None):
    """n frames of mixed kinds; `weights` is a dict kind -> weight (default: about 1/3 good, the rest each fault)."""
    rng = random.Random(seed); w = weights or {k: (6 if k.startswith("good") or k in ("no_csum", "odd_len") else 2) for k in KINDS}
    ks = list(w); ws = [w[k] for k in ks]; out = []
    for _ in range(n):
        k = rng.choices(ks, ws)[0]; body, bad = build(k, rng, cfg); out.append((k, body, bad))
    return out
def write_stimulus(path, fr, seed=1, gap=(0, 0), bubble=0):
    """One line per cycle: valid last bad data (5 hex digits). `gap` = idle cycles between frames (min, max); `bubble` = percent chance of an idle cycle before each byte inside a frame. Idle cycles carry random junk on data, last and bad: a don't-care must be ignored."""
    rng = random.Random(seed ^ 0x9E37); lines = []
    def idle(): lines.append("%x%x%x%02x" % (0, rng.getrandbits(1), rng.getrandbits(1), rng.getrandbits(8)))
    for k, body, bad in fr:
        for _ in range(rng.randint(*gap)): idle()
        for i, x in enumerate(body):
            while bubble and rng.randrange(100) < bubble: idle()
            last = i == len(body) - 1
            lines.append("%x%x%x%02x" % (1, int(last), bad if last else 0, x))
    with open(path, "w") as f: f.write("\n".join(lines) + "\n")
    return len(lines)
def csum_messages(seed, n=300):
    """Messages for the checksum accumulators: the edge cases first (all 0xFF, alternating, zero, the RFC 1071 example, one byte, odd lengths), then random ones heavy in 0xFF so that carries occur on almost every word."""
    rng = random.Random(seed); m = [bytes.fromhex("0001f203f4f5f6f7"), b"\xff", b"\x00", b"\xff\xff", b"\xff\xff\xff", b"\x01"]
    m += [b"\xff" * k for k in range(1, 41)] + [b"\x00" * k for k in (2, 3, 9)] + [b"\xff\x00" * k for k in (1, 2, 17)] + [b"\x80\x00" * k for k in (2, 3)]
    while len(m) < n:
        k = rng.choice([rng.randint(1, 12), rng.randint(1, 100), rng.randint(1, 1600)]); style = rng.randrange(3)
        m.append(bytes(rng.getrandbits(8) if style == 0 else rng.choice([0xFF, 0xFF, 0xFF, 0xFE, 0x00, rng.getrandbits(8)]) for _ in range(k)))
    return m
def write_csum_stimulus(path, msgs, seed=1, idle=15):
    rng = random.Random(seed ^ 0x51); lines = []
    for m in msgs:
        for i, x in enumerate(m):
            while rng.randrange(100) < idle: lines.append("%x%x%x%02x" % (0, rng.getrandbits(1), rng.getrandbits(1), rng.getrandbits(8)))
            lines.append("%x%x%x%02x" % (1, int(i == len(m) - 1), int(i == 0), x))
    with open(path, "w") as f: f.write("\n".join(lines) + "\n")
    return len(lines)
def parse_results(text):
    """The testbench prints `FRAME <hex> <bad>` then `RES cause ntags vid sip dip sport dport ulen` per frame."""
    fr = []; res = []
    for line in text.splitlines():
        p = line.split()
        if line.startswith("FRAME "):
            try: fr.append((bytes.fromhex(p[1]), int(p[2])))
            except ValueError: fr.append((b"<x>", 9))
        elif line.startswith("RES "):
            try: res.append(tuple(int(x) for x in p[1:]))
            except ValueError: res.append(("x",))
    return fr, res
def expected(fr, cfg=DEFAULT_CFG):
    out_f = []; out_r = []
    for k, body, bad in fr:
        s = spec(body, bad, cfg); out_f.append((body, 1 if s["cause"] else 0)); out_r.append((s["cause"], s["ntags"], s["vid"], s["sip"], s["dip"], s["sport"], s["dport"], s["ulen"]))
    return out_f, out_r
if __name__ == "__main__":
    # RFC 1071 example: 00 01 f2 03 f4 f5 f6 f7 sums to ddf2
    assert csum(bytes.fromhex("0001f203f4f5f6f7")) == 0xDDF2
    # a textbook IPv4 header (Wikipedia): checksum field 0xB861 over 4500 0073 0000 4000 4011 .... c0a8 0001 c0a8 00c7
    h = bytes.fromhex("450000730000400040110000c0a80001c0a800c7"); assert inet_csum(h) == 0xB861, hex(inet_csum(h))
    assert csum(h[:10] + b"\xb8\x61" + h[12:]) == 0xFFFF
    from collections import Counter
    c = Counter(); n_ok = 0
    for seed in range(40):
        for k, body, bad in frames(seed, 60):
            s = spec(body, bad); c[(k, NAMES[s["cause"]])] += 1
    want = {"good": "forward", "trailer": "forward", "ip_csum": "ip_bad", "udp_csum": "udp_bad", "ver6": "ip_bad", "ihl4": "ip_bad", "tot_big": "ip_bad", "frag_mf": "not_udp", "frag_off": "not_udp", "tcp": "not_udp", "arp": "not_ip", "mac_bad": "mac_bad", "no_csum": "forward", "csum_zero": "forward", "ulen_small": "udp_bad", "ulen_big": "udp_bad", "three_tags": "not_ip", "odd_len": "forward", "carry_heavy": "forward", "good_opts": "forward"}
    cfgd = DEFAULT_CFG; bad = []
    for (k, cause), v in sorted(c.items()):
        if k in want and cause != want[k] and not (k in ("good", "trailer", "good_opts", "odd_len", "carry_heavy", "no_csum", "csum_zero") and cause == "not_ours"): bad.append((k, cause, v))
    print("model self-test: known checksums OK;", "construction and specification agree" if not bad else f"DISAGREE: {bad}")
    for k in ("good", "good_vlan", "good_qinq", "good_opts", "csum_zero", "no_csum", "odd_len", "carry_heavy", "tot_small", "truncated", "wrong_ip", "wrong_port", "wrong_vid", "bits"):
        print(f"  {k:12s} " + ", ".join(f"{cause} {v}" for (kk, cause), v in sorted(c.items()) if kk == k))
