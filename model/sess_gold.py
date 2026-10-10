#!/usr/bin/env python3
"""Chapter 24: the specification of the order-entry transmitter: a binary order protocol, pre-built message templates, and the client side of a session (login, heartbeats, liveness, sequence checking). THE PROTOCOL IS A SIMPLIFIED, OUCH- AND SOUPBINTCP-LIKE ONE WRITTEN FOR THIS BOOK FROM MEMORY; it is NOT any exchange's specification and has not been checked against one.
PACKETS (client to server), all numbers big endian: a 2-byte length (of everything after it), a 1-byte type, a payload.
  LOGIN 'L':       user(4) password(4) requested sequence number(4)                    15 bytes on the wire
  HEARTBEAT 'R':   (nothing)                                                            3
  LOGOUT 'O':      (nothing)                                                            3
  DATA 'U':        a message: ENTER 'O' token(4) side('B'/'S') shares(4) stock(4) price(4) tif(4) firm(4) display(1) capacity(1)   31 bytes on the wire
                   CANCEL 'X' token(4) shares(4)                                                                                   12
                   REPLACE 'N' old token(4) new token(4) shares(4) price(4) tif(4) display(1)                                      25
PACKETS FROM THE SERVER the unit sees, as events (type, sequence number): 'A' login accepted (the sequence number the session continues from), 'J' login rejected, 'H' heartbeat, 'S' sequenced data (its number must be the next expected), 'Z' end of session.
TEMPLATES. The stock name of each symbol index (4 bytes), the user, the password, the requested sequence number, the firm and the display and capacity bytes are CONFIGURATION (writes, any time); an order is a template whose fixed bytes are already there and whose token, side, shares, price and tif are patched in: one cycle, whatever the packet. The packet then leaves W bytes per beat, first byte in the high byte of the beat; the last beat has nbytes <= W valid bytes (the rest 0).
REQUESTS (one offered at a time, held until accepted; accepted in a cycle in which `ready`): ORDER(token, sym, side, shares, price, tif), CANCEL(token, shares), REPLACE(old, new, shares, price, tif), LOGIN, LOGOUT. The answer (the cycle after acceptance): OK (the packet is on its way), REFUSED (the session is not in the state that allows it) or BADSYM (an ORDER for a symbol index of NS or more). A refused request sends nothing. LOGIN is allowed in IDLE; ORDER, CANCEL, REPLACE and LOGOUT in ACTIVE.
SESSION STATES: IDLE (after reset) -> LOGIN (a LOGIN request was accepted) -> ACTIVE ('A') | REJECTED ('J') | DEAD (no answer within TL cycles); ACTIVE -> CLOSED (LOGOUT accepted, or 'Z') | GAP ('S' with a number other than the expected one: the stream lost or repeated a message) | DEAD (nothing heard from the server for 3 HB cycles). No state leaves REJECTED, CLOSED, GAP or DEAD but reset: orders are refused until the session is built again, which is FAILING CLOSED.
HEARTBEATS. In ACTIVE, if HB cycles pass since a packet was last started (any packet), a HEARTBEAT is sent in the first cycle the transmitter is free, ahead of any request (the request waits: ready is low in that cycle).
TIME. ready(c) = the transmitter has at most W bytes left (the last beat is leaving, or nothing) and no heartbeat is due. A packet accepted in cycle a is on the wire in cycles a + 1 to a + ceil(bytes / W), one beat per cycle, and the next packet's first beat can follow in the very next cycle. hb counts cycles in ACTIVE since the last packet was loaded; rx counts cycles since the server was last heard ('H', 'A', or an in-order 'S'); a login timer counts cycles in LOGIN."""
import random
IDLE, LOGIN, ACTIVE, REJECTED, DEAD, CLOSED, GAP = range(7)
SN = ["IDLE", "LOGIN", "ACTIVE", "REJECTED", "DEAD", "CLOSED", "GAP"]
ORDER, CANCEL, REPLACE, LOGINQ, LOGOUT = range(5)
KN = ["ORDER", "CANCEL", "REPLACE", "LOGIN", "LOGOUT"]
OK, REFUSED, BADSYM = range(3)
RN = ["OK", "REFUSED", "BADSYM"]
M = 0xFFFFFFFF
def be(x, n): return (x & ((1 << (8 * n)) - 1)).to_bytes(n, "big")
def packet(kind, r, cfg, ns):
    """The bytes of the packet for request r (a dict) with configuration cfg: the specification of the encoder, written with bytes and not with the hardware's concatenation."""
    if kind == ORDER:
        body = b"U" + b"O" + be(r["tok"], 4) + (b"S" if r["side"] else b"B") + be(r["shares"], 4) + cfg["stock"][r["sym"]] + be(r["px"], 4) + be(r["tif"], 4) + cfg["firm"] + be(cfg["display"], 1) + be(cfg["capacity"], 1)
    elif kind == CANCEL: body = b"U" + b"X" + be(r["tok"], 4) + be(r["shares"], 4)
    elif kind == REPLACE: body = b"U" + b"N" + be(r["tok"], 4) + be(r["tok2"], 4) + be(r["shares"], 4) + be(r["px"], 4) + be(r["tif"], 4) + be(cfg["display"], 1)
    elif kind == LOGINQ: body = b"L" + cfg["user"] + cfg["pw"] + be(cfg["seq"], 4)
    elif kind == LOGOUT: body = b"O"
    else: body = b"R"                                                                              # a heartbeat
    return be(len(body), 2) + body
HEARTBEAT = -1
def new_cfg(ns): return dict(stock=[b"\0\0\0\0"] * ns, user=b"\0\0\0\0", pw=b"\0\0\0\0", seq=0, firm=b"\0\0\0\0", display=0, capacity=0)
def apply_cfg(cfg, c):
    what, sym, data = c
    if what == 0:
        if sym < len(cfg["stock"]): cfg["stock"][sym] = be(data, 4)                                 # a write for a symbol index that does not exist is ignored
    elif what == 1: cfg["user"] = be(data, 4)
    elif what == 2: cfg["pw"] = be(data, 4)
    elif what == 3: cfg["firm"] = be(data, 4)
    elif what == 4: cfg["display"] = (data >> 8) & 0xFF; cfg["capacity"] = data & 0xFF
    elif what == 5: cfg["seq"] = data & M
def run(cycles, w=8, ns=4, hb=20, tl=60):
    """Closed loop. cycles[c] = dict(req=(kind, dict), rx=(type, seq), cfg=(what, sym, data)), any subset; a req is offered from the cycle it appears in until it is accepted (the next only after); cycle 0 is the first cycle after reset. -> dict(rows, packets, lines) with lines[c] = (the request on the pins in cycle c or None, rx, cfg) and rows[c] = (ready, beat valid, beat (int), last, nbytes, state, expected seq, answer valid, answer) as visible in cycle c, and packets = [(cycle accepted, kind, bytes)]."""
    cfg = new_cfg(ns); st = IDLE; exp = 0; tx = b""; hbc = 0; rxc = 0; ltc = 0; ans = None; rows = []; lines = []; packets = []; qi = 0; reqs = [cy["req"] for cy in cycles if "req" in cy]; at = [c for c, cy in enumerate(cycles) if "req" in cy]; held = None; n = len(cycles)
    for c in range(n + 40):
        cy = cycles[c] if c < n else {}
        hb_due = st == ACTIVE and hbc >= hb
        ready = 1 if (len(tx) <= w and not hb_due) else 0
        if held is None and qi < len(reqs) and at[qi] <= c: held = reqs[qi]; qi += 1
        lines.append((held, cy.get("rx"), cy.get("cfg")))
        data = int.from_bytes(tx[:w] + b"\0" * (w - len(tx[:w])), "big") if tx else 0
        rows.append((ready, 1 if tx else 0, data, 1 if (tx and len(tx) <= w) else 0, min(len(tx), w), st, exp, 1 if ans is not None else 0, ans if ans is not None else 0))
        # the end of the cycle: the transmitter advances and may load; the server's packet and the timers move the state; an accepted request's transition comes last
        tx = tx[w:]; loaded = False; new_ans = None; acc = None
        if hb_due and len(tx) == 0: tx = packet(HEARTBEAT, None, cfg, ns); loaded = True; packets.append((c, HEARTBEAT, tx))
        elif held is not None and ready:
            kind, r = held; held = None
            allowed = (st == IDLE) if kind == LOGINQ else (st == ACTIVE)
            if not allowed: new_ans = REFUSED
            elif kind == ORDER and r["sym"] >= ns: new_ans = BADSYM
            else: new_ans = OK; tx = packet(kind, r, cfg, ns); loaded = True; acc = kind; packets.append((c, kind, tx))
        nst = st; heard = False; rx = cy.get("rx")
        if rx is not None:
            t, sq = rx
            if st == LOGIN and t == "A": nst = ACTIVE; exp = sq
            elif st == LOGIN and t == "J": nst = REJECTED
            elif t == "Z" and st in (LOGIN, ACTIVE): nst = CLOSED
            elif st == ACTIVE and t == "H": heard = True
            elif st == ACTIVE and t == "S":
                if sq == exp: exp = (exp + 1) & M; heard = True
                else: nst = GAP
        if st == LOGIN and nst == LOGIN:
            ltc += 1
            if ltc >= tl: nst = DEAD
        if st == ACTIVE and nst == ACTIVE:
            rxc = 0 if heard else rxc + 1
            if rxc >= 3 * hb: nst = DEAD
        if nst == ACTIVE: hbc = 0 if (loaded or st != ACTIVE) else hbc + 1
        else: hbc = 0
        if acc == LOGINQ: nst = LOGIN; ltc = 0
        elif acc == LOGOUT: nst = CLOSED
        if "cfg" in cy: apply_cfg(cfg, cy["cfg"])
        st = nst; ans = new_ans
    return dict(rows=rows, packets=packets, lines=lines)
def expected_rows(res): return [(c,) + tuple(r) for c, r in enumerate(res["rows"])]
def write_stim(path, lines, seed=1):
    """One line per cycle, the layout of tb/sess_tb.sv: request (held) bits 0..168, server packet 169..209, configuration write 210..249; junk where not valid. 64 hex digits."""
    rng = random.Random(seed)
    with open(path, "w") as f:
        for q, rx, c in lines:
            kind, r = q if q else (rng.randrange(5), dict(tok=rng.getrandbits(32), tok2=rng.getrandbits(32), sym=rng.randrange(16), side=rng.randrange(2), shares=rng.getrandbits(32), px=rng.getrandbits(32), tif=rng.getrandbits(32)))
            r = {**dict(tok=0, tok2=0, sym=0, side=0, shares=0, px=0, tif=0), **r}
            v = (1 if q else 0) | (kind << 1) | (r["tok"] << 4) | (r["tok2"] << 36) | (r["sym"] << 68) | (r["side"] << 72) | (r["shares"] << 73) | (r["px"] << 105) | (r["tif"] << 137)
            t, sq = rx if rx else (rng.choice("AJHSZ"), rng.getrandbits(32))
            v |= ((1 if rx else 0) << 169) | (ord(t) << 170) | (sq << 178)
            what, sym, data = c if c else (rng.randrange(6), rng.randrange(16), rng.getrandbits(32))
            v |= ((1 if c else 0) << 210) | (what << 211) | (sym << 214) | (data << 218)
            f.write("%064x\n" % v)
    return len(lines)
if __name__ == "__main__":
    # 1. the encoder, byte by byte, worked out by hand (stock "ABCD", firm "FIR0", display 'Y' = 0x59, capacity 0x43 'C', user "USER", password "PASS")
    cfg = new_cfg(2); cfg["stock"][0] = b"ABCD"; cfg["firm"] = b"FIR0"; cfg["display"] = 0x59; cfg["capacity"] = 0x43; cfg["user"] = b"USER"; cfg["pw"] = b"PASS"; cfg["seq"] = 7
    o = packet(ORDER, dict(tok=1, sym=0, side=1, shares=100, px=0x1234, tif=0, tok2=0), cfg, 2)
    assert o == bytes.fromhex("001d" "55" "4f" "00000001" "53" "00000064" "41424344" "00001234" "00000000" "46495230" "59" "43") and len(o) == 31
    assert packet(CANCEL, dict(tok=2, shares=0), cfg, 2) == bytes.fromhex("000a" "55" "58" "00000002" "00000000") and packet(REPLACE, dict(tok=2, tok2=3, shares=5, px=6, tif=7), cfg, 2) == bytes.fromhex("0017" "55" "4e" "00000002" "00000003" "00000005" "00000006" "00000007" "59")
    assert packet(LOGINQ, {}, cfg, 2) == bytes.fromhex("000d" "4c" "55534552" "50415353" "00000007") and packet(HEARTBEAT, None, cfg, 2) == bytes.fromhex("000152") and packet(LOGOUT, {}, cfg, 2) == bytes.fromhex("00014f")
    assert packet(ORDER, dict(tok=1, sym=0, side=0, shares=1, px=1, tif=1, tok2=0), cfg, 2)[8:9] == b"B"                                  # side 0 is a buy
    # 2. time, hand-simulated: W = 8, NS = 2, HB = 4 (so the server is given up after 12 quiet cycles), TL = 6
    L = lambda c, k, v: dict(c, **{k: v})
    base = [dict(cfg=(0, 0, 0x41424344)), dict(cfg=(3, 0, 0x46495230)), dict(cfg=(4, 0, 0x5943)), dict(cfg=(1, 0, 0x55534552)), dict(cfg=(2, 0, 0x50415353)), dict(cfg=(5, 0, 7)), dict(), dict(req=(LOGINQ, {})), dict(), dict(), dict()]     # LOGIN offered in cycle 7
    r = run(base + [dict(rx=("A", 50))] + [dict() for _ in range(30)], 8, 2, 4, 6)["rows"]                                           # row fields: ready, beat valid, beat, last, nbytes, state, expected, answer valid, answer
    assert [r[c][1] for c in range(7, 12)] == [0, 1, 1, 0, 0] and r[8][3] == 0 and r[8][4] == 8 and r[9][3] == 1 and r[9][4] == 7           # accepted in cycle 7: beats in 8 (8 bytes) and 9 (the last 7); ready is low in cycle 8 (15 bytes left), high in 9 (7 <= 8)
    assert r[8][7:] == (1, OK) and r[7][5] == IDLE and r[8][5] == LOGIN                                                               # the answer and the new state are visible in cycle 8
    assert r[10][5] == LOGIN and r[11][5] == LOGIN and r[12][5] == ACTIVE and r[12][6] == 50                                         # 'A' offered in cycle 11 takes effect for cycle 12; the expected number is the one given
    rr = run(base[:7] + [dict(req=(LOGINQ, {}))] + [dict() for _ in range(12)], 8, 2, 4, 6)["rows"]
    assert [rr[c][5] for c in range(8, 16)] == [LOGIN] * 6 + [DEAD, DEAD]                                                             # the login timer: the request is accepted in cycle 7, LOGIN from cycle 8, six quiet cycles (8..13) and DEAD from cycle 14
    act = run(base + [dict(rx=("A", 50))] + [dict() for _ in range(40)], 8, 2, 4, 6)                                                  # ACTIVE from cycle 12: hb counts 0 in 12, 1 in 13, 2, 3, 4 in cycle 16 -> due: a heartbeat is loaded at the end of 16 and its beat is in cycle 17
    a = act["rows"]; assert a[16][0] == 0 and a[17][1] == 1 and a[17][3] == 1 and a[17][4] == 3 and a[17][2] == 0x0001520000000000 and (16, HEARTBEAT, bytes.fromhex("000152")) in act["packets"]
    assert [a[c][5] for c in range(12, 26)] == [ACTIVE] * 12 + [DEAD, DEAD]                                                           # nothing heard from the server: the quiet counter is 0 in cycle 12 and 11 in cycle 23, the end of cycle 23 makes it 12 = 3 HB: DEAD from cycle 24
    hb2 = run(base + [dict(rx=("A", 50)), dict(), dict(), dict(rx=("H", 0))] + [dict() for _ in range(40)], 8, 2, 4, 6)["rows"]
    assert [hb2[c][5] for c in range(12, 40)].index(DEAD) + 12 == 27 and hb2[26][5] == ACTIVE                                        # a server heartbeat in cycle 14 restarts the quiet count: 0 in cycle 15, 11 in cycle 26, so DEAD from cycle 27
    sq = run(base + [dict(rx=("A", 50)), dict(), dict(rx=("S", 50)), dict(rx=("S", 51)), dict(rx=("S", 53)), dict(), dict()], 8, 2, 4, 6)["rows"]
    assert [sq[c][6] for c in range(12, 19)] == [50, 50, 51, 52, 52, 52, 52] and [sq[c][5] for c in range(12, 19)] == [ACTIVE] * 4 + [GAP] * 3    # S 50 (cycle 13) and S 51 (14) are in order (expected 51 from cycle 14, 52 from 15); S 53 (15) is not 52: GAP from cycle 16, the number stays
    # 3. requests: refused before ACTIVE, a symbol that does not exist, a packet of 31 bytes in 4 beats
    ra = run(base[:6] + [dict(req=(ORDER, dict(tok=1, sym=0, side=0, shares=1, px=1, tif=0)))] + base[7:] + [dict(rx=("A", 50)), dict(), dict(req=(ORDER, dict(tok=1, sym=2, side=0, shares=1, px=1, tif=0))), dict(req=(ORDER, dict(tok=2, sym=1, side=1, shares=1, px=1, tif=0))), dict(), dict(), dict(), dict()], 8, 2, 4, 6)
    r2 = ra["rows"]
    assert r2[7][7:] == (1, REFUSED) and r2[8][7:] == (1, OK) and [p[1] for p in ra["packets"]][:3] == [LOGINQ, ORDER, HEARTBEAT]                      # the order offered in cycle 6 (IDLE) is refused and sends nothing; the login offered in 7 is accepted
    assert r2[14][7:] == (1, BADSYM) and r2[15][7:] == (1, OK) and [r2[c][1] for c in range(14, 20)] == [0, 1, 1, 1, 1, 0] and [r2[c][4] for c in range(15, 19)] == [8, 8, 8, 7] and r2[18][3] == 1   # sym 2 does not exist (NS = 2): nothing sent; the next order is on the wire in cycles 15 to 18: 8 + 8 + 8 + 7 bytes
    # 4. more states and requests, each worked by hand on the same timeline (ACTIVE from cycle 12, the count 0 in 12)
    tail = [dict() for _ in range(30)]
    def at(c, **kw): x = [dict(d) for d in base + [dict(rx=("A", 50))] + [dict() for _ in range(40)]]; x[c].update(kw); return x
    g1 = run(at(13, req=(LOGINQ, {})), 8, 2, 4, 6); assert g1["rows"][14][7:] == (1, REFUSED) and g1["rows"][14][5] == ACTIVE and all(k != LOGINQ for _, k, _ in g1["packets"][1:])       # a second login while ACTIVE is refused and sends nothing
    g2 = run(at(13, rx=("S", 99))[:15] + [dict(req=(ORDER, dict(tok=1, sym=0, side=0, shares=1, px=1, tif=0)))] + [dict() for _ in range(5)], 8, 2, 4, 6)
    assert g2["rows"][14][5] == GAP and g2["rows"][16][7:] == (1, REFUSED)                                                            # a wrong number in cycle 13: GAP from 14; an order offered in cycle 15 is refused
    g3 = run(base[:9] + [dict(rx=("Z", 0))] + base[10:] + [dict(rx=("A", 50))] + tail, 8, 2, 4, 6); assert g3["rows"][10][5] == CLOSED and g3["rows"][13][5] == CLOSED   # an end of session in LOGIN (cycle 9): CLOSED from cycle 10, and a later 'A' changes nothing
    g4 = run(at(13, req=(LOGOUT, {})), 8, 2, 4, 6); assert g4["rows"][14][5] == CLOSED and g4["rows"][14][7:] == (1, OK) and g4["rows"][14][1:5] == (1, 0x00014F0000000000, 1, 3)    # LOGOUT accepted in cycle 13: its 3 bytes are on the wire in cycle 14, with the answer and the state CLOSED
    g5 = run(at(14, req=(CANCEL, dict(tok=1, shares=0))), 8, 2, 4, 6); assert [p[:2] for p in g5["packets"]][1:3] == [(14, CANCEL), (19, HEARTBEAT)]                      # a packet restarts the heartbeat count: the cancel loaded at the end of 14 gives the count 0 in 15 and 4 in 19, the heartbeat goes in 19 (not in 16)
    cf = at(6, cfg=(0, 2, 0x5A5A5A5A)); cf[16]["req"] = (ORDER, dict(tok=1, sym=0, side=0, shares=1, px=1, tif=0)); g6 = run(cf, 8, 2, 4, 6); o6 = [p for p in g6["packets"] if p[1] == ORDER][0][2]; assert o6[13:17] == b"ABCD"      # a stock write for symbol 2 (NS = 2) is ignored: symbol 0 keeps its name
    assert r[8][0] == 0 and r[9][0] == 1 and r[7][0] == 1                                                                              # ready: 1 when idle, 0 in cycle 8 (15 bytes in the transmitter), 1 in 9 (7 left)
    print("sess_gold: hand-checked scenarios passed")
