#!/usr/bin/env python3
"""A model of FPGA logic: the 4-input lookup table (LUT4) and a small technology mapper.
THE LUT. A LUT4 is a 16-entry memory: its four inputs are the address, its content (16 bits, set by the bitstream) is the truth table. ANY function of up to four inputs is one LUT; a flip-flop beside it makes a 'logic cell'.
THE MAPPER. A function of more than four inputs must be split. This mapper uses Shannon expansion: f = x ? f1 : f0 (the two cofactors on a variable x), each cofactor mapped recursively, joined by a LUT that is a 2-to-1 multiplexer. It drops variables a function does not depend on, shares identical sub-functions (hash-consing), and tries every variable as the split variable, keeping the cheapest by an estimate. It is deliberately simple: Yosys's ABC does much better (Example A measures by how much).
A function is a tuple of 2^n bits: bit i is f at the input whose binary value is i (input 0 is the least significant bit of i)."""
import itertools
def cofactors(tt, n, v):
    """The functions of n-1 variables obtained by fixing variable v to 0 and to 1."""
    c0, c1 = [], []
    for i in range(1 << n):
        if (i >> v) & 1: c1.append(tt[i])
        else: c0.append(tt[i])
    return tuple(c0), tuple(c1)
def depends(tt, n, v): c0, c1 = cofactors(tt, n, v); return c0 != c1
def reduce_support(tt, n, vars_):
    """Remove the variables the function does not depend on. Returns (tt, n, vars)."""
    for v in range(n - 1, -1, -1):
        if not depends(tt, n, v): tt, _ = cofactors(tt, n, v); n -= 1; vars_ = vars_[:v] + vars_[v + 1:]
    return tt, n, vars_
class Net:
    """A network of LUTs. Signals are ('in', i) for primary inputs, ('const', b) and ('lut', k) for LUT outputs."""
    def __init__(self, n_inputs): self.n_inputs = n_inputs; self.luts = []; self.memo = {}
    def lut(self, tt, ins):
        key = (tt, tuple(ins))
        if key not in self.memo: self.luts.append((tt, tuple(ins))); self.memo[key] = ("lut", len(self.luts) - 1)
        return self.memo[key]
    def evaluate(self, x):
        val = {}
        def get(s):
            if s[0] == "in": return (x >> s[1]) & 1
            if s[0] == "const": return s[1]
            if s not in val:
                tt, ins = self.luts[s[1]]; val[s] = tt[sum(get(t) << j for j, t in enumerate(ins))]
            return val[s]
        return get
def estimate(tt, n, memo):
    """Tree-cost estimate of mapping tt (n variables) to LUT4s: 0 for constants and single variables, 1 for up to 4 variables, otherwise the best split."""
    key = (tt, n)
    if key in memo: return memo[key]
    tt2, n2, _ = reduce_support(tt, n, list(range(n)))
    if n2 == 0 or (n2 == 1 and tt2 == (0, 1)): r = 0
    elif n2 <= 4: r = 1
    else: r = min(1 + sum(estimate(c, n2 - 1, memo) for c in cofactors(tt2, n2, v)) for v in range(n2))
    memo[key] = r; return r
def map_function(tt, n):
    """Map the function to a Net of LUT4s. Returns (net, output signal)."""
    net = Net(n); memo = {}
    def build(tt, n, vars_):
        tt, n, vars_ = reduce_support(tt, n, vars_)
        if n == 0: return ("const", tt[0])
        if n == 1 and tt == (0, 1): return vars_[0]
        if n <= 4: return net.lut(tt, vars_)
        best = min(range(n), key=lambda v: sum(estimate(c, n - 1, memo) for c in cofactors(tt, n, v))); c0, c1 = cofactors(tt, n, best); rest = vars_[:best] + vars_[best + 1:]
        s0, s1 = build(c0, n - 1, rest), build(c1, n - 1, rest)
        return net.lut(mux_table(), [vars_[best], s0, s1])
    return net, build(tt, n, [("in", i) for i in range(n)])
def mux_table():
    """LUT3 table of a 2-to-1 multiplexer with inputs (sel, a, b): the output is a if sel = 0, else b. Input 0 (sel) is the least significant address bit."""
    return tuple(((i >> 2) & 1) if (i & 1) else ((i >> 1) & 1) for i in range(8))
def check(net, out, tt, n):
    """Exhaustively compare the network with the truth table."""
    return all(net.evaluate(x)(out) == tt[x] for x in range(1 << n))
def to_verilog(name, n, tt):
    """The function as a Verilog module: a constant truth table indexed by the inputs (what a designer might write for a table lookup)."""
    bits = "".join(str(tt[i]) for i in range(len(tt) - 1, -1, -1))
    return f"module {name}(input [{n-1}:0] x, output y);\n    localparam [{len(tt)-1}:0] T = {len(tt)}'b{bits};\n    assign y = T[x];\nendmodule\n"
def to_verilog_logic(name, n, expr):
    return f"module {name}(input [{n-1}:0] x, output y);\n    assign y = {expr};\nendmodule\n"
def table(n, f): return tuple(int(f([(i >> k) & 1 for k in range(n)])) & 1 for i in range(1 << n))
