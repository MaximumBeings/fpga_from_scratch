#!/usr/bin/env python3
"""Chapter 1: test the tests of the registered adder. Each mutant breaks one line of rtl/radd.v; the testbench (golden vectors, 16 bits) must notice. Equivalent changes are listed apart."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, radd_gold
V = "rtl/radd.v"
MUT = [
 (V, "radd: subtracts instead of adding", "s <= ra + rb;", "s <= ra - rb;"),
 (V, "radd: ORs the operands", "s <= ra + rb;", "s <= ra | rb;"),
 (V, "radd: drops the carry out", "s <= ra + rb; end\nendmodule\nmodule radd_lut", "s <= {1'b0, ra + rb}; end\nendmodule\nmodule radd_lut"),
 (V, "radd: one register stage too few", "ra <= a; rb <= b; s <= ra + rb;", "ra <= a; rb <= b; s <= a + b;"),
 (V, "radd: the second operand register takes a", "ra <= a; rb <= b; s <= ra + rb;", "ra <= a; rb <= a; s <= ra + rb;"),
 (V, "radd_lut: the sum bit ignores the carry in", "assign sum[i] = ra[i] ^ rb[i] ^ c[i];", "assign sum[i] = ra[i] ^ rb[i];"),
 (V, "radd_lut: the carry forgets the propagate term", "assign c[i+1] = (ra[i] & rb[i]) | (c[i] & (ra[i] ^ rb[i]));", "assign c[i+1] = (ra[i] & rb[i]) | c[i];"),
 (V, "radd_lut: the carry-in of bit 0 is 1", "assign c[0] = 1'b0;\n    genvar", "assign c[0] = 1'b1;\n    genvar"),
 (V, "radd_lut: the carry out is not connected", "assign sum[W] = c[W];", "assign sum[W] = 1'b0;"),
 (V, "radd_lut: the second operand register takes a", "ra <= a; rb <= b; s <= sum;", "ra <= a; rb <= a; s <= sum;"),
]
EQUIV = [(V, "EQUIVALENT: the carry uses OR instead of XOR as its propagate signal (a + b with a OR b is also correct: the generate term covers the case where both are 1)", "assign c[i+1] = (ra[i] & rb[i]) | (c[i] & (ra[i] ^ rb[i]));", "assign c[i+1] = (ra[i] & rb[i]) | (c[i] & (ra[i] | rb[i]));")]
n = radd_gold.write(16, 200, 1, os.path.join(flow.ROOT, "out", "radd_vec.hex")); D = ("WIDTH=16", f"NVEC={n}"); F = [V]; TB = ["tb/radd_tb.v"]
print("NOTE: this script deliberately breaks copies of the RTL. 'caught' lines are EXPECTED: they show the testbench notices the mistake.")
c, t, l = flow.mutate(MUT, F, "radd_tb", TB, workers=4, defines=D); print("\n".join(l)); print(f"\nregistered adder: {c} of {t} broken circuits caught")
c2, t2, l2 = flow.mutate(EQUIV, F, "radd_tb", TB, workers=1, defines=D); print("\nChanges that look like bugs and are not:"); print("\n".join(l2))
sys.exit(0 if c == t else 1)
