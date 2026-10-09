#!/usr/bin/env python3
"""Chapter 16, example B: what one corrupted byte does. Packets of 12 ITCH messages (a realistic mix) are generated; ONE byte of each is replaced by a random different byte, at a chosen site: the high or low byte of a block's length, a message's type byte, a payload byte, the count in the header, the sequence number. The model (itch_gold.decode, which the RTL equals on every stream of Chapter 16's tests: the last line repeats that on the corrupted packets themselves) says what the parser reports. Measured over 400 packets per site: how often the parser FLAGS the packet (a truncated packet, a wrong count, or a message with an error), how many of the 12 messages come out right, and how many messages come out that were never sent (spurious)."""
import os, random, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import itch_gold as G
MIX = "AAAAAAAADDDDEEXUPSF"
def make(rng, site, n=12):
    msgs = [G.build_msg(rng, rng.choice(MIX)) for _ in range(n)]; data = bytearray(G.build_packet(rng, msgs, seq=rng.getrandbits(64))); starts = []; pos = 20
    for m in msgs: starts.append(pos); pos += 2 + len(m)
    k = rng.randrange(n); s0 = starts[k]
    pos = {"length, high byte": s0, "length, low byte": s0 + 1, "type byte": s0 + 2, "payload byte": s0 + 3 + rng.randrange(len(msgs[k]) - 1), "count": 18 + rng.randrange(2), "sequence number": 10 + rng.randrange(8)}[site]
    old = data[pos]; data[pos] = rng.choice([b for b in range(256) if b != old]); return msgs, bytes(data), k
def run(site, trials, seed):
    rng = random.Random(seed); flagged = 0; right = []; spurious = 0
    for _ in range(trials):
        msgs, data, k = make(rng, site); ev = G.decode([dict(bytes=[(i, x) for i, x in enumerate(data)], eop=True)])
        M = [e for e in ev if e[0] == "M"]; P = [e for e in ev if e[0] == "P"][0]; sent = [(m[0], G.body_fields(m[0], m)) for m in msgs]
        flag = P[2] or P[3] or any(e[3] for e in M); flagged += bool(flag)
        # a sent message is RIGHT if a message with its type and fields comes out (at any index: a swallowed block shifts the later indices); an accepted message (err 0) that was never sent is SPURIOUS
        key = lambda t, f: (t, tuple(sorted(f.items()))); sentset = {key(t, f) for t, f in sent}; outset = [key(e[2], e[6]) for e in M if e[3] == 0]
        right.append(len(sentset & set(outset))); spurious += sum(1 for o in outset if o not in sentset)
    return flagged / trials, st.mean(right), spurious
if __name__ == "__main__":
    T = 400
    print(f"== one random byte of a 12-message packet replaced by another, at each site ({T} packets per site, model decode)")
    print(f"  {'site':18s} | {'flagged':>8s} {'messages right (of 12)':>23s} {'accepted, never sent':>22s} | {'derived right':>13s}")
    der = {"length, high byte": "5.5", "length, low byte": "5.5", "type byte": "11", "payload byte": "11", "count": "12", "sequence number": "12"}
    for site in ("length, high byte", "length, low byte", "type byte", "payload byte", "count", "sequence number"):
        f, r, sp = run(site, T, 7)
        print(f"  {site:18s} | {f * 100:7.1f}% {r:23.2f} {sp:22d} | {der[site]:>13s}")
    print("  (accepted, never sent: messages the parser accepted with err 0 that were not sent. For a payload byte it is the corrupted message itself, which no check at this layer can know. For a length byte it is a block of garbage that happened to frame as a valid message. Derived: a corrupted type byte or payload byte spoils only its own message, so 11 of 12 are right and the parser cannot know for a payload byte (it flags nothing: there is no checksum at this layer; the UDP checksum of Chapter 9 is the guard). A corrupted LENGTH moves every later block boundary: the k messages before it are right and the rest are lost or garbled; with k uniform over the 12 positions the mean is (0 + 1 + ... + 11) / 12 = 5.5 right, a little more when a block is swallowed and the framing happens to recover)")
    print("\\n== the same, on the RTL: 100 corrupted packets (all sites mixed, random gaps) through the generated parser against the model")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import ch16_run as C
    rng = random.Random(11); pks = []
    for i in range(100): _, data, _ = make(rng, rng.choice(["length, high byte", "length, low byte", "type byte", "payload byte", "count", "sequence number"])); pks.append(dict(data=data, eop=True))
    lines, packets = G.schedule(rng, pks, gap=0.1); err = C.compare(C.parse_out(C.sim(lines)), G.decode(packets)); print(f"  {len(packets)} packets, {sum(len(p['bytes']) for p in packets)} bytes: " + ("RTL equals the model" if err is None else "DIFFERENT: " + err))
