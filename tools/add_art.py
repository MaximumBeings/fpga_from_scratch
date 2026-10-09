#!/usr/bin/env python3
"""Insert each page's picture and its species/world background under the page's title. Idempotent: pages that already have one are left alone. Usage: add_art.py"""
import os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); DOCS = os.path.join(ROOT, "docs")
def pid_for(rel):
    if rel == "index.md": return "index"
    if rel == "contents.md": return "contents"
    m = re.match(r"part(\d+)/(\d+)-", rel)
    if m: return "ch-%02d" % int(m.group(2))
    m = re.match(r"appendix/([a-l])-", rel)
    if m: return "appx-" + m.group(1)
    return None
n = 0
for dp, _, files in os.walk(DOCS):
    for f in sorted(files):
        if not f.endswith(".md") or "assets" in dp: continue
        rel = os.path.relpath(os.path.join(dp, f), DOCS); pid = pid_for(rel)
        if not pid or not os.path.exists(os.path.join(DOCS, "assets", "art", pid + ".svg")): continue
        path = os.path.join(dp, f); text = open(path).read()
        if "assets/art/" + pid in text: continue
        up = "../" * rel.count("/"); lines = text.split("\n"); i = next(k for k, l in enumerate(lines) if l.startswith("# "))
        block = ["", f"![{pid}]({up}assets/art/{pid}.svg)", "", f'--8<-- "docs/assets/art/{pid}.md"', ""]
        open(path, "w").write("\n".join(lines[:i + 1] + block + lines[i + 1:])); n += 1
print(n, "pages updated")
