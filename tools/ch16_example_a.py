#!/usr/bin/env python3
"""Chapter 16, example A: what a message type costs. The generator is run on subsets of the ITCH grammar (1, 2, 4, 8 message types) and on larger grammars made by copying the 8 layouts under other type bytes (16, 32, 64 types: the same layouts, so the same 12 field names, which isolates the cost of the type table and of the field selects). Each parser behind its pin wrapper (11 input bits shifted in serially, all outputs registered, then folded into one registered 16-bit word) is synthesised and placed for iCE40 and ECP5 (nextpnr seed 1, asked for 300 MHz)."""
import os, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import re, flow, grammar, gen_parser as GP
def crit(log):
    i = log.rfind("Critical path report for clock"); j = log.find("Setup", i); sec = log[i:j + 300]; src = re.findall(r"Source (\S+)", sec); snk = re.findall(r"Sink (\S+)", sec); tl = re.search(r"([\d.]+) ns logic, ([\d.]+) ns routing", sec)
    nm = lambda x: re.sub(r"_(SB_|TRELLIS_|LUT4|CCU2C|PFUMX|L6MUX|RAM)\S*", "", re.sub(r"\.\d+\.\d+(_RAM)?", "", x)); return nm(src[0]), nm(snk[-1]), tl.groups() if tl else ("?", "?")
def grammar_of(n):
    base = list(grammar.ITCH.items()); g = {}
    letters = "SAFEXDUP" + "".join(chr(0x80 + i) for i in range(56))                      # type bytes 0x80 and up
    for i in range(n): t, m = base[i % 8]; g[letters[i]] = m
    return g
SIZES = (1, 2, 4, 8, 16, 32, 64)
def job(a):
    n, fam = a; g = grammar_of(n); f = f"out/ex_mold_{n}.sv"; open(os.path.join(flow.ROOT, f), "w").write(GP.gen(g, f"mold_{n}"))
    return a, flow.run([f], f"mold_{n}_syn", fam, 300, tag=f"t16_{n}_{fam}")
if __name__ == "__main__":
    with cf.ThreadPoolExecutor(4) as ex: res = dict(ex.map(job, [(n, f) for n in SIZES for f in ("ice40", "ecp5")]))
    print("== cost of the generated parser against the number of message types (the layouts of the first 8 are ITCH's; beyond that they are copies under other type bytes), behind the pin wrapper")
    print(f"  {'types':>5s} {'lines of SV':>11s} | {'iCE40 LUT':>9s} {'FF':>5s} {'Fmax':>6s} | {'ECP5 LUT':>8s} {'FF':>5s} {'Fmax':>6s} | {'iCE40 LUT/type':>14s}")
    for n in SIZES:
        i, e = res[(n, "ice40")], res[(n, "ecp5")]; lines = len(GP.gen(grammar_of(n), "m").splitlines())
        print(f"  {n:5d} {lines:11d} | {i['luts']:9d} {i['ffs']:5d} {i['fmax']:6.1f} | {e['luts']:8d} {e['ffs']:5d} {e['fmax']:6.1f} | {(i['luts'] - res[(1, 'ice40')]['luts']) / max(1, n - 1):14.1f}")
    print("\n== throughput: one byte per clock, so bytes per second = Fmax; messages per second follow from the length of a message (derived, not measured)")
    i8 = res[(8, "ice40")]["fmax"]; e8 = res[(8, "ecp5")]["fmax"]
    print(f"  8 types: iCE40 {i8:.1f} MHz = {i8 * 8:.0f} Mbit/s of payload; ECP5 {e8:.1f} MHz = {e8 * 8:.0f} Mbit/s; at 125 MHz (a byte per clock on gigabit Ethernet) the parser would have to reach 125 MHz: it does not on iCE40")
    print(f"  per message the parser spends (length + 2) cycles (the two length bytes): for a 36-byte Add Order that is 38 cycles, {i8 / 38:.2f} million messages/s on iCE40, {e8 / 38:.2f} on ECP5")
    print("\n== the end points of the critical path (nextpnr's last report for the clock), 8 types")
    for fam in ("ice40", "ecp5"):
        a, b, (lg, rt) = crit(res[(8, fam)]["pnr_log"]); print(f"  {fam:6s} {a:24s} -> {b:24s} {lg} ns logic, {rt} ns routing")
