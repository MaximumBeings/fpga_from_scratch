#!/usr/bin/env python3
"""Chapter 11, example B: the token-bucket pacer. Cut-through builder, 1000-byte payloads (wire cost 1066 bytes), 60 packets back to back, source never stalls. (1) the spacing between frame starts against the rate: derived = cost x 256 / rate cycles; (2) the burst: how many frames leave back to back from a full bucket, against the bucket size; derived = the frames whose cost the initial credit covers. Usage: ch11_example_b.py"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import udp_gold as g, ch11_run as r
L = 1000; COST = g.wire_cost(L)
def pk(n): return [dict(payload=bytes((i + j) & 255 for j in range(L)), dport=5000, dip=0x0A000002) for i in range(n)]
if __name__ == "__main__":
    print(f"== 1. spacing between frame starts against the rate (60 packets, wire cost {COST} bytes each, bucket 4,096 bytes): after the burst every frame waits for its credit")
    print(f"  {'rate /256':>9s} {'bytes per cycle':>16s} | {'derived spacing':>16s} {'measured median':>16s} {'measured min':>13s} {'measured max':>13s} | {'achieved rate (last 40 frames)':>31s}")
    for rate in (8, 16, 32, 64, 128, 200, 256):
        o = r.run(pk(60), 1, pace=1, rate=rate); st = r.starts(o); sp = [b - a for a, b in zip(st, st[1:])]; tail = sp[-40:]; der = COST * 256 / rate
        print(f"  {rate:9d} {rate / 256:16.3f} | {der:16.1f} {sorted(tail)[len(tail) // 2]:16d} {min(tail):13d} {max(tail):13d} | {COST * 40 / (st[-1] - st[-41]):20.4f} byte/cycle")
    print("  derived spacing = cost x 256 / rate cycles (the credit needed, over the credit gained per cycle); the measured spacing is an integer number of cycles, so the credit's rounding alternates it between two values")
    print(f"\n== 2. the burst: rate 32/256, frames of cost {COST}; the frames that leave back to back from a full bucket (spacing = one frame's wire time), against the bucket size")
    print(f"  {'bucket (bytes)':>14s} | {'derived frames':>15s} {'measured':>9s}")
    g_ = COST * 32 / 256
    for bl in (11, 12, 13, 14):
        B = 1 << bl; o = r.run(pk(30), 1, pace=1, rate=32, BL=bl); st = r.starts(o); sp = [b - a for a, b in zip(st, st[1:])]; n = 1
        while n - 1 < len(sp) and sp[n - 1] <= COST + 2: n += 1
        der = 1 + int((B - COST) // (COST - g_))
        print(f"  {B:14d} | {der:15d} {n:9d}")
    print("  derived: the k-th frame of the burst can leave at once if the credit still covers it; the credit falls by (cost - credit gained during one frame time = cost x rate/256) per frame, so k <= 1 + (bucket - cost) / (cost - cost x rate/256).")
