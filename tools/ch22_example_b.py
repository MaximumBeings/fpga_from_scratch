#!/usr/bin/env python3
"""Chapter 22, example B (model level): how many fraction bits, and what the shared divider costs in waiting. (1) ERROR against F: for random books (prices around a mid with a spread of 0 to 20 ticks, shares long-tailed up to 2^20) the largest and the mean error of the imbalance (in units of 2^-F and in absolute terms) and of the microprice (in ticks, and as a share of the spread), for F = 4 to 20, against the exact rational values. (2) The smallest F for which the microprice error stays below 1/100 and 1/1000 of a tick on every book seen. (3) WAITING: the shared divider accepts one book every F + 4 cycles; for books arriving at random (probability p per cycle, a message held until accepted) the mean wait before acceptance and the largest, for F = 12, against p, and the pipelined divider's (none). 50,000 books, one seed."""
import os, random, statistics as st, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import sig_gold as G
if __name__ == "__main__":
    rng = random.Random(3); books = [b for b in G.random_books(rng, 50000, 24, 20) if b[1] and b[3]]
    print(f"== 1. error against F: {len(books)} books with both sides present; errors against the exact rational values")
    print(f"  {'F':>3s} | {'imbalance: max err':>18s} {'mean err':>10s} | {'microprice: max err (ticks)':>27s} {'mean (ticks)':>13s} {'max / spread':>13s}")
    small = {}
    for F in range(4, 21, 2):
        ei = []; em = []; er = []
        for (b, bs, a, as_) in books:
            _, _, s, _, _, w, imb, mic = G.compute(b, bs, a, as_, F); i_id, m_id, _ = G.ideal(b, bs, a, as_)
            ei.append(abs(imb / (1 << F) - float(i_id))); em.append(abs(mic / (1 << F) - float(m_id)))
            if s: er.append(em[-1] / abs(s))
        small[F] = max(em)
        print(f"  {F:3d} | {max(ei):18.6f} {st.mean(ei):10.6f} | {max(em):27.6f} {st.mean(em):13.6f} {max(er):13.6f}")
    print("\n== 2. the smallest F (even values) that keeps the microprice error on every book seen below a threshold, in ticks")
    for thr in (1 / 16, 1 / 100, 1 / 1000):
        ok = [F for F in small if small[F] < thr]; print(f"  below {thr:8.5f} tick: F = {min(ok) if ok else '> 20'}")
    print("\n== 3. waiting for the shared divider (F = 12, accepts every 16 cycles): books arrive with probability p per cycle, one is held until accepted; 20,000 books")
    print(f"  {'p':>6s} {'offered per 16 cycles':>22s} | {'mean wait':>10s} {'max wait':>9s} {'share waiting':>14s} | pipelined divider")
    for p in (0.01, 0.03, 0.05, 0.06, 0.0625, 0.07):
        r = random.Random(5); n = 20000; gaps = []; t = 0
        arr = []
        for _ in range(n):
            g = 1
            while r.random() > p: g += 1
            t += g; arr.append(t)
        free = 0; waits = []
        for a in arr: acc = max(a, free); waits.append(acc - a); free = acc + 12 + 4
        print(f"  {p:6.4f} {p * 16:22.2f} | {st.mean(waits):10.1f} {max(waits):9d} {sum(1 for w in waits if w) / n * 100:13.1f}% | wait 0")
