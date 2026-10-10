#!/usr/bin/env python3
"""Chapter 25, example B (model level, checked against the RTL by ch25_sys.py): (1) LATENCY: the cycles from an order being taken to its answer, for each way an order can end. (2) FAULT STUDY: one report the books cannot explain is injected at a random cycle of ordinary traffic; how many orders are refused afterwards, how many orders that were already in flight are still sent, how long until the first refusal, and whether the books still agree. (3) TABLE SIZE: the share of orders that the gate accepts but the tracker has no room for (the give-back), against NT, for the same traffic."""
import os, random, statistics as st, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model")); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sys_gold as SG, life_gold as LG, risk_gold as RG, ch25_sys as C
U = dict(maxlong=100, maxshort=100, maxqty=50, maxonot=10000, maxnot=100000, cap=5)
SETUP = [dict(cfg=(0, U)), dict(cfg=(1, U)), dict(cfg=(2, U)), dict(cfg=(3, U)), dict(band=(0, 1, 100)), dict(band=(1, 1, 100)), dict(band=(2, 1, 100)), dict(band=(3, 1, 100)), dict(arm=1), {}, {}]
def order(t, q=10, px=20, a=0, s=0, sd=0): return dict(tok=t, acct=a, sym=s, side=sd, px=px, qty=q)
def latency(extra, nt=2, ordkw=None):
    cyc = SETUP + extra; cyc[len(SETUP)].setdefault("ord", order(1)) if not any("ord" in c for c in extra) else None
    r = SG.run(cyc + [{}] * 14, nt); rows = r["rows"]; t0 = next(c for c, row in enumerate(rows) if row[0] and any("ord" in cc for cc in cyc[c:c + 1])); t1 = next(c for c in range(t0, len(rows)) if rows[c][2])
    return t0, t1, rows[t1][3]
if __name__ == "__main__":
    print("== 1. cycles from the cycle an order is offered to the cycle its answer is visible (the order is offered at cycle 0 of each case)")
    cases = [
        ("accepted by gate and tracker (OK)", [dict(ord=order(1))], 2),
        ("refused by the gate (QTY)", [dict(ord=order(1, 99))], 2),
        ("refused by the gate (KILL)", [dict(ord=order(1), kill=1)], 2),
        ("tracker refuses, token open (DUPTOK): charge given back", [dict(ord=order(1)), {}, {}, {}, {}, {}, dict(ord=order(1))], 2),
        ("tracker refuses, table full (FULL): charge given back", [dict(ord=order(1)), {}, {}, {}, {}, {}, dict(ord=order(2)), {}, {}, {}, {}, {}, dict(ord=order(3))], 2),
        ("OK, but a report from the exchange wins the tracker's cycle", [dict(ord=order(1)), {}, {}, {}, {}, {}, dict(ord=order(2)), {}, {}, dict(rep=(LG.ACK, dict(tok=1))), dict(rep=(LG.ACK, dict(tok=1)))], 4),
    ]
    for name, ex, nt in cases:
        cyc = SETUP + ex; r = SG.run(cyc + [{}] * 20, nt); rows = r["rows"]
        offered = [len(SETUP) + i for i, c in enumerate(ex) if "ord" in c]; ans = [c for c, row in enumerate(rows) if row[2]]
        last = offered[-1]; a = [c for c in ans if c > last][0] if [c for c in ans if c > last] else None
        print(f"  {name:62s} {a - last if a else '-':>3} cycles (answer {RG.RN[rows[a][3]] if a is not None and rows[a][3] < 16 else 'TRK_' + LG.RN[rows[a][3] - 16] if a is not None else '-'})")
    print("\n== 2. fault study: one anomalous report (a fill of 1 for a token that does not exist) at a random cycle of ordinary traffic; 300 trials, NT 4, 400 cycles each")
    rng = random.Random(25); refused = []; sent_after = []; first = []; bad = 0
    for trial in range(300):
        cy = C.make("flow", 1000 + trial, 4); t = rng.randrange(40, 340); cy[t] = dict(cy[t]); cy[t]["rep"] = (LG.FILL, dict(tok=999999, qty=1))
        r = SG.run(cy, 4); rows = r["rows"]; bad += r["sys"].bad
        fault_c = next((c for c, row in enumerate(rows) if row[16]), None)
        ds = [(c, row) for c, row in enumerate(rows) if row[2] and c > t]; kills = [c for c, row in ds if row[3] == RG.KILL]; refused.append(len(kills)); first.append((kills[0] - t) if kills else None)
        sent_after.append(sum(1 for c, row in ds if row[3] == 0 and (fault_c is None or c <= fault_c + 6)))
    ok = [x for x in first if x is not None]
    print(f"  orders refused (KILL) after the fault, per trial: mean {st.mean(refused):.1f}, min {min(refused)}, max {max(refused)}")
    print(f"  cycles from the bad report to the first KILL answer: mean {st.mean(ok):.1f}, min {min(ok)}, max {max(ok)} (an order is answered 3 cycles after it is offered)")
    print(f"  orders in flight at the fault that are still sent (answered OK within 6 cycles of the fault becoming visible): mean {st.mean(sent_after):.2f}, max {max(sent_after)}")
    print(f"  quiet cycles in which the gate's books and the tracker's books differ, over all trials: {bad}")
    print("\n== 3. the share of orders the tracker has no room for, against the table size (each table size has its own traffic from the generator, which reports only on orders the table holds: 'flow', 6 seeds of 400 cycles)")
    print(f"  {'NT':>3s} | {'orders':>6s} {'sent':>5s} {'FULL give-backs':>16s} {'share':>6s}")
    for nt in (1, 2, 4, 8, 16):
        n = s = f = 0
        for seed in range(6):
            r = SG.run(C.make("flow", 50 + seed, nt), nt); ds = [row for row in r["rows"] if row[2]]; n += len(ds); s += sum(row[3] == 0 for row in ds); f += sum(row[3] == 16 + LG.FULL for row in ds)
        print(f"  {nt:3d} | {n:6d} {s:5d} {f:16d} {100 * f / n:5.1f}%")
