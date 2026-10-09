#!/usr/bin/env python3
"""Chapter 2, example A: what SystemVerilog can you use? (1) a feature matrix: 22 constructs against three tools; (2) the package finding: what works with Yosys; (3) lint on a module with five mistakes and on its repair. Usage: ch02_example_a.py"""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import flow
R = flow.ROOT
F = {
"logic + always_ff": "module t(input clk, input d, output logic q); always_ff @(posedge clk) q <= d; endmodule",
"always_comb": "module t(input a, input b, output logic y); always_comb y = a & b; endmodule",
"always_latch": "module t(input en, input d, output logic q); always_latch if (en) q = d; endmodule",
"typedef enum": "module t(input clk, input go, output logic y); typedef enum logic [1:0] {A, B, C} st_t; st_t s; always_ff @(posedge clk) case (s) A: if (go) s <= B; B: s <= C; default: s <= A; endcase assign y = (s == C); endmodule",
"packed struct": "module t(input [7:0] x, output logic [3:0] y); typedef struct packed {logic [3:0] hi; logic [3:0] lo;} p_t; p_t p; assign p = x; assign y = p.hi ^ p.lo; endmodule",
"package + import": "package pk; localparam int W = 4; typedef logic [W-1:0] w_t; endpackage\nmodule t(input pk::w_t a, output pk::w_t y); import pk::*; assign y = ~a; endmodule",
"parameter + $clog2": "module t #(parameter int N = 8) (input [N-1:0] a, output logic [$clog2(N):0] y); always_comb begin y = 0; for (int i = 0; i < N; i++) y += a[i]; end endmodule",
"generate for / if": "module t #(parameter int N = 4) (input [N-1:0] a, output [N-1:0] y); genvar i; generate for (i = 0; i < N; i++) begin : g if (i % 2) assign y[i] = ~a[i]; else assign y[i] = a[i]; end endgenerate endmodule",
"function automatic": "module t(input [7:0] a, output [7:0] y); function automatic [7:0] rev(input [7:0] x); for (int i = 0; i < 8; i++) rev[i] = x[7-i]; endfunction assign y = rev(a); endmodule",
"unique case": "module t(input [1:0] s, input [3:0] d, output logic y); always_comb begin unique case (s) 2'd0: y = d[0]; 2'd1: y = d[1]; 2'd2: y = d[2]; 2'd3: y = d[3]; endcase end endmodule",
"case inside": "module t(input [3:0] a, output logic y); always_comb begin case (a) inside 4'b00??: y = 1; default: y = 0; endcase end endmodule",
"assignment pattern '{}": "module t(output logic [3:0] y); typedef struct packed {logic [1:0] a; logic [1:0] b;} s_t; s_t s; always_comb begin s = '{a: 2'd1, b: 2'd2}; y = s; end endmodule",
"2-D packed array": "module t(input [3:0][7:0] a, output [7:0] y); assign y = a[2]; endmodule",
"unpacked array (memory)": "module t(input clk, input [3:0] ad, input [7:0] d, input we, output logic [7:0] q); logic [7:0] m [16]; always_ff @(posedge clk) begin if (we) m[ad] <= d; q <= m[ad]; end endmodule",
"interface + modport": "interface ifc; logic [7:0] d; logic v; modport src(output d, v); modport snk(input d, v); endinterface\nmodule a(ifc.src p); assign p.d = 8'd5; assign p.v = 1; endmodule\nmodule t(output [7:0] y); ifc i(); a u(.p(i)); assign y = i.d; endmodule",
"packed union": "module t(input [7:0] x, output [7:0] y); typedef union packed {logic [7:0] w; logic [1:0][3:0] n;} u_t; u_t u; assign u.w = x; assign y = {u.n[0], u.n[1]}; endmodule",
"assert property": "module t(input clk, input a, input b); assert property (@(posedge clk) a |-> b); endmodule",
"immediate assert": "module t(input clk, input a); always @(posedge clk) assert (a == a); endmodule",
"++ and += operators": "module t(input clk, output logic [3:0] c); always_ff @(posedge clk) c += 1; endmodule",
"int / bit types": "module t(input clk, output bit [3:0] c); int i; always_ff @(posedge clk) begin i <= i + 1; c <= i[3:0]; end endmodule",
"enum methods (.next)": "module t(input clk, output logic y); typedef enum {A, B, C} e_t; e_t s; always_ff @(posedge clk) s <= s.next(); assign y = (s == C); endmodule",
"streaming / dynamic types (queue)": "module t(input clk); int q[$]; always @(posedge clk) q.push_back(1); endmodule",
}

def run3(path, top="t"):
    return [subprocess.run(["iverilog", "-g2012", "-s", top, "-o", "/dev/null", path], capture_output=True, text=True).returncode == 0,
            subprocess.run(["verilator", "--lint-only", "-Wno-fatal", "-Wno-lint", "-Wno-style", "--top-module", top, path], capture_output=True, text=True).returncode == 0,
            subprocess.run(["yosys", "-q", "-p", f"read_verilog -sv {path}; hierarchy -top {top}; proc"], capture_output=True, text=True).returncode == 0]
d = tempfile.mkdtemp(prefix="sv_"); tools = ["Icarus 12", "Verilator 5.020", "Yosys 0.33"]
print("== 1. which constructs do the three tools accept? (each snippet is a tiny module; 'ok' = the tool read it without error)")
print(f"  {'construct':36s} " + " ".join(f"{t:>16s}" for t in tools)); allok = []
for nm, s in F.items():
    p = os.path.join(d, "t.sv"); open(p, "w").write(s + "\n"); r = run3(p); print(f"  {nm:36s} " + " ".join(f"{'ok' if x else 'FAILS':>16s}" for x in r))
    if all(r): allok.append(nm)
print(f"\n  accepted by ALL three: {len(allok)} of {len(F)}. This book's rule: write only what all three accept, because the same file is simulated twice and synthesized once. The constructs that fail somewhere are a list of things to avoid, or to gate behind a simulator-only file")
print("\n== 2. packages: the subtlety (Yosys 0.33 reads packages, but not every way of using them)")
variants = {
 "constant, qualified:  input logic [pk::W-1:0] a": ("package pk; localparam int W = 4; endpackage\nmodule t(input logic [pk::W-1:0] a, output logic [pk::W-1:0] y); assign y = ~a; endmodule", None),
 "type, wildcard import in the header:  module t import pk::*; (input w_t a ...)": ("package pk; localparam int W = 4; typedef logic [W-1:0] w_t; endpackage\nmodule t import pk::*; (input w_t a, output w_t y); assign y = ~a; endmodule", None),
 "packed struct, import inside the module": ("package pk; localparam int W = 4; typedef struct packed {logic [W-1:0] d; logic v;} bus_t; endpackage\nmodule t(input logic [pk::W:0] a, output logic [pk::W-1:0] y); import pk::*; bus_t b; always_comb begin b = a; y = b.d; end endmodule", None),
 "packed struct, qualified type  pk::bus_t b;": ("package pk; localparam int W = 4; typedef struct packed {logic [W-1:0] d; logic v;} bus_t; endpackage\nmodule t(input logic [4:0] a, output logic [3:0] y); pk::bus_t b; always_comb begin b = a; y = b.d; end endmodule", None),
 "typedef in an included header (`include):": ("`include \"hdr.svh\"\nmodule t(input logic [4:0] a, output logic [3:0] y); bus_t b; always_comb begin b = a; y = b.d; end endmodule", "typedef struct packed {logic [3:0] d; logic v;} bus_t;\n"),
}
print(f"  {'way of using a package or a shared type':72s} " + " ".join(f"{t:>10s}" for t in tools))
for nm, (s, hdr) in variants.items():
    p = os.path.join(d, "t.sv"); open(p, "w").write(s + "\n")
    if hdr: open(os.path.join(d, "hdr.svh"), "w").write(hdr)
    r = subprocess.run(["iverilog", "-g2012", "-I", d, "-s", "t", "-o", "/dev/null", p], capture_output=True, text=True).returncode == 0, subprocess.run(["verilator", "--lint-only", "-Wno-fatal", "-Wno-lint", "-Wno-style", "-I" + d, "--top-module", "t", p], capture_output=True, text=True).returncode == 0, subprocess.run(["yosys", "-q", "-p", f"read_verilog -sv -I{d} {p}; hierarchy -top t; proc"], capture_output=True, text=True).returncode == 0
    print(f"  {nm:72s} " + " ".join(f"{'ok' if x else 'FAILS':>10s}" for x in r))
print("  the house rule that follows: QUALIFY names from a package (pk::W, pk::bus_t), never use a wildcard import")
print("\n== 3. lint: a module with five mistakes that all compile (rtl/lint_bad.sv), and the repair (rtl/lint_good.sv)")
for f, top in (("rtl/lint_bad.sv", "lint_bad"), ("rtl/lint_good.sv", "lint_good")):
    p = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", top, f], cwd=R, capture_output=True, text=True); msgs = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("%")]
    print(f"  Verilator -Wall on {f}: {len(msgs)} message(s)")
    for m in msgs: print("    " + m[:200])
y = subprocess.run(["yosys", "-p", "read_verilog -sv rtl/lint_bad.sv; proc; check"], cwd=R, capture_output=True, text=True).stdout
print("  Yosys 'check' on lint_bad.sv: " + "; ".join(l.split("Warning: ")[1][:110] for l in y.splitlines() if "Warning:" in l))
print("  what the codes mean: WIDTHTRUNC = a wider value assigned to a narrower signal (bits lost); LATCH = a combinational block that does not assign its output on every path (a memory element is built); CASEINCOMPLETE = a case with no default and values not covered; BLKSEQ = a blocking assignment (=) in a clocked block; MULTIDRIVEN or the error above = one signal driven from two places")
print("  the discipline: lint is a gate, not a suggestion. Every design file of this book must lint clean under -Wall before its testbench is run, and the run script checks it (Chapter 2, run section 1)")
