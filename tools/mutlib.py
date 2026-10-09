#!/usr/bin/env python3
"""Chapter 6: a small mutation-testing library. Instead of a hand-written list of mutants (Chapters 1 to 5), it GENERATES mutants from the source by applying operator-replacement rules to every occurrence in the code, skipping comments and any line that matches `skip` (the injected-bug lines). A mutant is one source text with one change.
  generate(text, skip)         -> list of (line number, description, mutated text)
  score(mutants, fn, workers)  -> for each mutant the name of the first check that fails (a `battery`), or None if it survives
The operator set is deliberately plain: equality and inequality swapped, && and || swapped, + and - swapped (only in `+ 1'b1` / `- 1'b1` forms), 1'b0 and 1'b1 swapped, '0 and '1 swapped, negation removed on a signal, a boundary limit swapped for its neighbour (DEP/DEPM1, LAST/LATE), a guard term (`&& !full`, `&& !empty`, `count != DEP`) removed."""
import re, concurrent.futures as cf
RULES = [
    (r"==", "!=", "== replaced by !="), (r"!=", "==", "!= replaced by =="), (r"&&", "||", "&& replaced by ||"), (r"\|\|", "&&", "|| replaced by &&"),
    (r"\+ 1'b1", "- 1'b1", "+ 1 replaced by - 1"), (r"- 1'b1", "+ 1'b1", "- 1 replaced by + 1"),
    (r"1'b0", "1'b1", "1'b0 replaced by 1'b1"), (r"1'b1", "1'b0", "1'b1 replaced by 1'b0"), (r"'0\b", "'1", "'0 replaced by '1"),
    (r"!(?=[a-z])", "", "negation removed"),
    (r" && !full", "", "term '&& !full' removed"), (r" && !empty", "", "term '&& !empty' removed"), (r"\bDEP\b", "DEPM1", "limit DEP replaced by DEPM1"), (r"\bDEPM1\b", "DEP", "limit DEPM1 replaced by DEP"),
    (r"\bLAST\b", "LATE", "wrap point LAST replaced by LATE"), (r"if \(count != DEP\) ", "", "guard 'count != DEP' removed"),
]
def generate(text, skip=r"BUG|^\s*//|^module|^\s*localparam|^\s*logic"):
    out = []; lines = text.split("\n")
    for ln, line in enumerate(lines):
        code = line.split("//")[0]
        if re.search(skip, code) or not code.strip(): continue
        for pat, rep, desc in RULES:
            if rep is None: continue
            for m in re.finditer(pat, code):
                new = code[:m.start()] + rep + code[m.end():] + (("//" + line.split("//", 1)[1]) if "//" in line else "")
                if new == line: continue
                out.append((ln + 1, f"line {ln + 1}: {desc}: {code.strip()[:60]}", "\n".join(lines[:ln] + [new] + lines[ln + 1:])))
    seen = set(); uniq = []
    for ln, d, t in out:
        if t not in seen: seen.add(t); uniq.append((ln, d, t))
    return uniq
def score(mutants, fn, workers=4):
    with cf.ThreadPoolExecutor(workers) as ex: return list(ex.map(lambda m: fn(m[2]), mutants))
