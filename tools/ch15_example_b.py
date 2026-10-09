#!/usr/bin/env python3
"""Chapter 15, example B: the split under load (model level, cycle for cycle as tcp_split is). 8 connections are established through software, then carry in-order data and pure ACKs with a fraction p of OBLIGING exceptions (an old duplicate, a gap, an ACK for data never sent) that the hot path cannot take. Software takes `L` cycles per punted event. Three questions: (1) how much of the traffic ends up in software, and how much of that only because an earlier event of the same connection was pending; (2) how long do HOT events wait when the punt FIFO is full (head-of-line blocking), under POLICY 0 (stall) and POLICY 1 (drop); (3) how long does a RECONNECT take (SYN-ACK arrival to the connection being hot again) when software is busy."""
import os, random, statistics as st, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import split_gold as S, tcp_gold as G
M = 0xFFFFFFFF
def steady(seed, ncid, n, p, L=16, phi=0.25, wnd=65535, reconnect=0, rcyc=12, burst=0):
    """phi = (one connection's event rate) x L: the fraction of the time a connection spends pending if every one of its events were punted. Arrivals are Poisson with mean spacing L / (ncid x phi)."""
    gm = L / (ncid * phi)
    rng = random.Random(seed); ref = [G.TCB() for _ in range(ncid + reconnect)]; evs = []; arr = []; t = 0
    def add(c, at, tag=None, **k):
        v = dict(cid=c, wnd=wnd, **k)
        if tag: v["tag"] = tag
        evs.append(v); arr.append(at); ref[c].event(v["e"], v.get("f", 0), v.get("seq", 0), v.get("ack", 0), v.get("ln", 0), wnd, v.get("iss", 0))
    for c in range(ncid):
        add(c, t, e=G.E_OPEN_P, iss=1000 * c + 7); add(c, t + 1, e=G.E_SEG, f=G.SYN, seq=5000 * c + 9, ack=0); add(c, t + 2, e=G.E_SEG, f=G.ACK, seq=5000 * c + 10, ack=ref[c].nxt); t += 3
    t += 4 * ncid * L + 500; tb0 = t; nhs = len(evs); body = []
    for _ in range(n):
        t += int(rng.expovariate(1 / gm)); c = rng.randrange(ncid); r = ref[c]
        if rng.random() < p:
            k = rng.randrange(3)
            if k == 0: body.append((c, t, dict(e=G.E_SEG, f=G.ACK, seq=(r.rcv - 100) & M, ack=r.nxt, ln=100)))
            elif k == 1: body.append((c, t, dict(e=G.E_SEG, f=G.ACK, seq=(r.rcv + 700) & M, ack=r.nxt, ln=100)))
            else: body.append((c, t, dict(e=G.E_SEG, f=G.ACK, seq=r.rcv, ack=(r.nxt + 50) & M)))
        else:
            ln = rng.choice([0, 100]); body.append((c, t, dict(e=G.E_SEG, f=G.ACK, seq=r.rcv, ack=r.nxt, ln=ln)))
            r.rcv = (r.rcv + ln) & M                                                                              # the generator's own bookkeeping of in-order data
    # the generator advanced rcv itself; the real reference must be fed the same events in order, so rebuild it from the start
    ref2 = [G.TCB() for _ in range(ncid + reconnect)]
    for i in range(nhs): v = evs[i]; ref2[v["cid"]].event(v["e"], v.get("f", 0), v.get("seq", 0), v.get("ack", 0), v.get("ln", 0), wnd, v.get("iss", 0))
    for c, at, v in body: evs.append(dict(cid=c, wnd=wnd, **v)); arr.append(at)
    if burst:                                                                                                     # `burst` exceptional events, one per cycle, for random connections, in the middle of the run
        t0 = arr[nhs] + (arr[-1] - arr[nhs]) // 3
        for k in range(burst): c = rng.randrange(ncid); evs.append(dict(cid=c, wnd=wnd, e=G.E_SEG, f=G.ACK, seq=(ref2[c].rcv - 100) & M, ack=ref2[c].nxt, ln=100, tag=("burst", k))); arr.append(t0 + k)
    if reconnect:
        for j in range(reconnect):
            c = ncid + j; tt = tb0 + 200 + 97 * j
            for k in range(rcyc):
                iss = 77 * (k + 1) + j; peer = 100000 * (j + 1) + k
                evs.append(dict(cid=c, wnd=wnd, e=G.E_OPEN_A, iss=iss)); arr.append(tt)
                evs.append(dict(cid=c, wnd=wnd, e=G.E_SEG, f=G.SYN | G.ACK, seq=peer, ack=(iss + 1) & M, tag=("synack", c, k))); arr.append(tt + 300)
                evs.append(dict(cid=c, wnd=wnd, e=G.E_ABORT)); arr.append(tt + 1100); tt += 1500 + 40 * k
    order = sorted(range(len(evs)), key=lambda i: (arr[i], i)); return [evs[i] for i in order], [arr[i] for i in order], nhs
def pct(xs, q): xs = sorted(xs); return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else 0
if __name__ == "__main__":
    print("== 1. how much traffic is punted, and how much only because an earlier event of the same connection was pending. 8 connections, L = 16, 4,000 events after the handshakes, exceptions p = 2%, FIFO of 8, POLICY 0. phi = the connection's own event rate x L")
    print(f"  {'phi':>5s} | {'punted':>7s} {'collateral':>11s} {'collateral per exception':>25s} {'derived phi/(1-phi)':>20s} | {'mean wait':>9s} {'p99':>5s} {'max':>6s} {'max FIFO':>9s} {'cycles stalled':>15s}")
    for phi in (0.02, 0.05, 0.1, 0.25, 0.5, 0.75):
        ev, arr, nhs = steady(1, 8, 4000, 0.02, 16, phi); r = S.run(ev, 8, 8, 0, lat=16, arrivals=arr); assert S.reference_check(r) is None
        body = range(nhs, len(ev)); punted = sum(1 for i in body if r["path"][i] == 1); nex = max(1, sum(1 for i in body if ev[i]["e"] == G.E_SEG and (ev[i].get("seq", 0) != ev[i].get("seq", 0)))) ; wait = [r["ctime"][i] - arr[i] for i in body]
        nex = round(0.02 * len(body))
        print(f"  {phi:5.2f} | {punted / len(body) * 100:6.1f}% {r['collateral']:11d} {r['collateral'] / nex:25.2f} {phi / (1 - phi):20.2f} | {st.mean(wait):9.1f} {pct(wait, .99):5d} {max(wait):6d} {r['max_fifo']:9d} {r['stall']:15d}")
    print("  (collateral per exception: how many other events of the same connection software had to take because of one exception. Derived: each pending event keeps the connection pending for L more cycles, in which phi more events of the connection are expected, each of which does the same: phi + phi^2 + ... = phi / (1 - phi), as long as software has time to spare)")
    print("\n== 2. head-of-line blocking. A burst of B exceptional events (one per cycle, any connection) arrives in the middle of light traffic (8 connections, L = 16, phi = 0.05, no other exceptions). How long do the OTHER events, arriving while the burst is being served, wait before they are consumed?")
    print(f"  {'policy':>6s} {'FIFO depth':>10s} {'burst B':>8s} | {'others':>7s} {'mean wait':>9s} {'max wait':>9s} {'derived max (B-D) x L':>22s} | {'burst events dropped':>21s}")
    for policy in (0, 1):
        for depth in (2, 8, 32):
            for B in (8, 32, 128):
                ev, arr, nhs = steady(2, 8, 3000, 0.0, 16, 0.05, burst=B); r = S.run(ev, 8, depth, policy, lat=16, arrivals=arr); assert S.reference_check(r) is None
                bi = [i for i, e in enumerate(ev) if e.get("tag") and e["tag"][0] == "burst"]; t0 = arr[bi[0]]; t1 = t0 + B * 16 + 200
                oth = [r["ctime"][i] - arr[i] for i in range(nhs, len(ev)) if t0 <= arr[i] <= t1 and i not in set(bi)]
                dr = sum(1 for i in bi if r["path"][i] == 2)
                print(f"  {policy:6d} {depth:10d} {B:8d} | {len(oth):7d} {st.mean(oth):9.1f} {max(oth):9d} {max(0, B - depth) * 16:22d} | {dr:21d}")
    print("  (derived: with POLICY 0 the event at the head of the queue waits for room in the FIFO; room appears once per L cycles, so the last burst event is consumed about (B - D) x L cycles after it arrived, and every event behind it waits at least that long. With POLICY 1 nobody waits and the burst events beyond the FIFO's room are dropped: TCP's retransmission has to supply them again)")
    print("\n== 3. reconnects: 4 connections open actively, are answered 300 cycles later (SYN-ACK), and are aborted, 12 times each, while 12 others carry traffic (phi = 0.05). Time from the SYN-ACK's ARRIVAL to the write-back that leaves the connection ESTABLISHED in the table (software time + queueing); FIFO of 8, POLICY 0")
    print(f"  {'L':>3s} {'background exception p':>23s} | {'reconnects':>10s} {'mean':>7s} {'p99':>6s} {'max':>7s} | {'ideal (L)':>9s}")
    for L in (4, 16, 64):
        for p in (0.0, 0.05, 0.2):
            ev, arr, nhs = steady(3, 12, 3000, p, L, 0.05, reconnect=4); r = S.run(ev, 16, 8, 0, lat=L, arrivals=arr); assert S.reference_check(r) is None
            arrt = {}
            for e, a in zip(ev, arr):
                if e.get("tag"): arrt[e["tag"]] = a
            lat = [t - arrt[tag] for t, c, tag, stt in r["sw"].tags if tag in arrt and stt == G.ESTAB]
            print(f"  {L:3d} {p * 100:22.1f}% | {len(lat):10d} {st.mean(lat):7.1f} {pct(lat, .99):6d} {max(lat):7d} | {L:9d}")
