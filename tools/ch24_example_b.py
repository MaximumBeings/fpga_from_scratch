#!/usr/bin/env python3
"""Chapter 24, example B (model level): the time to put an order on the wire, and how long a session takes to notice a dead server. (1) WIRE TIME: for each packet, the cycles from the cycle it is accepted to the cycle its last byte is on the wire (the model: ceil(bytes / W)), against the beat width W (W = 16 is the arithmetic only: the RTL is built for up to 8 bytes). (2) THE LIVENESS RULE: the client calls the server dead after K x HB quiet cycles (K = 3 in the unit); the server sends a heartbeat every HB cycles with a delay that varies and, with probability p, loses one. For K from 2 to 5, the share of 20,000 server heartbeats that is wrongly given up on (the session declared dead while the server is alive) and, when the server really falls silent, how many cycles pass between the last heartbeat and DEAD. (3) DETECTION TIME: the cycles from the last heartbeat heard to DEAD in the cycle model. (4) HEARTBEATS SENT: the client's heartbeat traffic against the order rate, for HB = 20. One seed."""
import math, os, random, statistics as st, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import sess_gold as G
PK = [("ORDER", 31), ("CANCEL", 12), ("REPLACE", 25), ("LOGIN", 15), ("HEARTBEAT", 3), ("LOGOUT", 3)]
if __name__ == "__main__":
    print("== 1. cycles from acceptance to the last byte on the wire: ceil(bytes / W)")
    print(f"  {'packet':10s} {'bytes':>5s} | " + " ".join(f"{'W = ' + str(w):>6s}" for w in (1, 2, 4, 8, 16)))
    for n, b in PK: print(f"  {n:10s} {b:5d} | " + " ".join(f"{math.ceil(b / w):6d}" for w in (1, 2, 4, 8, 16)))
    print("  (the first byte is on the wire in the cycle after acceptance for every W: one cycle to patch the template)")
    print("\n== 2. liveness: false give-ups against the multiple K (the server's heartbeat period HB = 20 cycles, delay uniform in 0 .. J, loss probability p)")
    print(f"  {'J':>4s} {'p':>6s} | " + " ".join(f"{'K = ' + str(k):>8s}" for k in (2, 3, 4, 5)))
    for J in (0, 10, 30):
        for p in (0.0, 0.05, 0.2):
            row = []
            for K in (2, 3, 4, 5):
                rng = random.Random(7); last = 0; t = 0; bad = 0; n = 20000; times = []
                for i in range(n):
                    t_next = (i + 1) * 20 + rng.randint(0, J)
                    if rng.random() >= p: times.append(t_next)
                prev = 0
                for x in times:
                    if x - prev >= K * 20: bad += 1
                    prev = x
                row.append(f"{bad / n * 100:7.2f}%")
            print(f"  {J:4d} {p:6.2f} | " + " ".join(row))
    print("\n== 3. dead-server detection time, from the model (the unit): the cycles between the last heartbeat heard and DEAD, for HB = 20 and K = 3; checked against the cycle model")
    base = [dict(cfg=(0, 0, 0x41424344)), dict(req=(G.LOGINQ, {})), dict(), dict(), dict(), dict(rx=("A", 1))]
    for hb in (7, 20, 50):
        cy = base + [dict() for _ in range(8 * hb + 20)]
        for k in range(4): cy[6 + k * hb]["rx"] = ("H", 0)
        r = G.run(cy, 8, 4, hb, 100)["rows"]; last = 6 + 3 * hb; dead = [c for c, x in enumerate(r) if x[5] == G.DEAD][0]
        print(f"  HB {hb:3d}: last heartbeat heard in cycle {last}, DEAD from cycle {dead}: {dead - last} cycles = {(dead - last) / hb:.2f} HB")
    print("\n== 4. the client's heartbeats against the order rate (HB = 20): the share of packets sent that are heartbeats, for orders offered at rate r per cycle (one 31-byte order is 4 beats at W = 8)")
    for rate in (0.0, 0.01, 0.02, 0.05, 0.1):
        rng = random.Random(3); n = 20000; cy = [dict() for _ in range(n)]
        cy[0]["req"] = (G.LOGINQ, {}); cy[5]["rx"] = ("A", 1)
        for c in range(20, n):
            if rng.random() < rate and "req" not in cy[c]: cy[c]["req"] = (G.ORDER, dict(tok=c, sym=0, side=0, shares=1, px=1, tif=0))
            if c % 25 == 0: cy[c]["rx"] = ("H", 0)
        r = G.run(cy, 8, 4, 20, 100); hbs = sum(1 for _, k, _ in r["packets"] if k == G.HEARTBEAT); orders = sum(1 for _, k, _ in r["packets"] if k == G.ORDER)
        print(f"  rate {rate:5.2f}: {orders:5d} orders, {hbs:5d} heartbeats ({hbs / max(1, hbs + orders) * 100:5.1f}% of the packets)")
