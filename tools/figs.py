#!/usr/bin/env python3
"""A small SVG drawing library for the book's explanatory figures: boxes, arrows, logic gates, timing diagrams, grids and simple charts. Pure text output, deterministic, no dependencies.
Every figure has its own light background so that it reads the same in the light and dark page themes."""
import math
FONT = "ui-sans-serif,system-ui,'Segoe UI',Helvetica,Arial,sans-serif"; MONO = "ui-monospace,Menlo,Consolas,monospace"
C = dict(bg="#fbfcfe", ink="#1f2a37", line="#51606f", blue="#2b6cb0", blue2="#dbeafe", orange="#dd6b20", orange2="#feebc8", green="#2f855a", green2="#c6f6d5", red="#c53030", red2="#fed7d7", gray="#a0aec0", gray2="#edf2f7", purple="#6b46c1", purple2="#e9d8fd", teal="#2c7a7b", teal2="#b2f5ea", yellow2="#fefcbf")
def esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
class Fig:
    def __init__(self, w, h, title=""): self.w, self.h, self.title, self.o = w, h, title, []
    def add(self, s): self.o.append(s); return self
    def rect(self, x, y, w, h, fill="none", stroke=None, sw=1.5, rx=6, dash=None, op=1):
        return self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}"' + (f' stroke="{stroke}" stroke-width="{sw}"' if stroke else "") + (f' stroke-dasharray="{dash}"' if dash else "") + (f' opacity="{op}"' if op != 1 else "") + "/>")
    def circ(self, x, y, r, fill="none", stroke=None, sw=1.5): return self.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{fill}"' + (f' stroke="{stroke}" stroke-width="{sw}"' if stroke else "") + "/>")
    def line(self, x1, y1, x2, y2, c=None, sw=1.8, dash=None, op=1): return self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{c or C["line"]}" stroke-width="{sw}" stroke-linecap="round"' + (f' stroke-dasharray="{dash}"' if dash else "") + (f' opacity="{op}"' if op != 1 else "") + "/>")
    def path(self, d, fill="none", stroke=None, sw=1.8, dash=None): return self.add(f'<path d="{d}" fill="{fill}"' + (f' stroke="{stroke or C["line"]}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"' if stroke != "" else "") + (f' stroke-dasharray="{dash}"' if dash else "") + "/>")
    def poly(self, pts, fill="none", stroke=None, sw=1.5): return self.add('<polygon points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + f'" fill="{fill}"' + (f' stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"' if stroke else "") + "/>")
    def text(self, x, y, s, size=13, fill=None, anchor="middle", bold=False, mono=False, italic=False, rot=0):
        t = f'<text x="{x:.1f}" y="{y:.1f}" font-family="{MONO if mono else FONT}" font-size="{size}" fill="{fill or C["ink"]}" text-anchor="{anchor}"' + (' font-weight="bold"' if bold else "") + (' font-style="italic"' if italic else "") + (f' transform="rotate({rot} {x:.1f} {y:.1f})"' if rot else "") + f'>{esc(s)}</text>'
        return self.add(t)
    def lines(self, x, y, ss, size=13, fill=None, anchor="middle", lh=None, bold=False, mono=False):
        for k, s in enumerate(ss): self.text(x, y + k * (lh or size * 1.3), s, size, fill, anchor, bold, mono)
        return self
    def arrow(self, x1, y1, x2, y2, c=None, sw=2, head=9, dash=None):
        c = c or C["line"]; a = math.atan2(y2 - y1, x2 - x1); self.line(x1, y1, x2 - head * .6 * math.cos(a), y2 - head * .6 * math.sin(a), c, sw, dash)
        return self.poly([(x2, y2), (x2 - head * math.cos(a - .42), y2 - head * math.sin(a - .42)), (x2 - head * math.cos(a + .42), y2 - head * math.sin(a + .42))], fill=c)
    def box(self, x, y, w, h, label="", fill=None, stroke=None, size=13, bold=False, sub=None, mono=False, rx=8, sw=1.8, tc=None):
        self.rect(x, y, w, h, fill or C["blue2"], stroke or C["blue"], sw, rx); ls = label if isinstance(label, list) else [label]
        ty = y + h / 2 - (len(ls) - 1) * size * .65 + size * .35 - (7 if sub else 0)
        for k, s in enumerate(ls): self.text(x + w / 2, ty + k * size * 1.3, s, size, tc, "middle", bold, mono)
        if sub: self.text(x + w / 2, y + h - 9, sub, size - 3, C["line"], "middle", False, False, True)
        return self
    def pill(self, x, y, w, h, label, fill, stroke, size=12, tc=None): return self.box(x, y, w, h, label, fill, stroke, size, False, rx=h / 2, tc=tc)
    def caption(self, s): self.cap = s; return self
    # ---- logic gates: (x, y) is the top-left; each returns the output point (and input points)
    def gate(self, kind, x, y, label=None, fill="#ffffff", stroke=None, w=44, h=34):
        stroke = stroke or C["ink"]; ins = [(x, y + h * .28), (x, y + h * .72)]
        if kind in ("AND", "NAND"):
            self.path(f"M{x},{y} L{x+w*.5},{y} A{w*.5-(5 if kind=='NAND' else 0)*0},{h/2} 0 0 1 {x+w*.5},{y+h} L{x},{y+h} Z", fill, stroke, 1.8); ox = x + w * 1.0 if kind == "AND" else x + w * 1.0 + 7
        elif kind in ("OR", "NOR", "XOR", "XNOR"):
            self.path(f"M{x},{y} C{x+w*.55},{y} {x+w*.85},{y+h*.2} {x+w},{y+h/2} C{x+w*.85},{y+h*.8} {x+w*.55},{y+h} {x},{y+h} C{x+w*.25},{y+h*.75} {x+w*.25},{y+h*.25} {x},{y} Z", fill, stroke, 1.8); ox = x + w
            if kind in ("XOR", "XNOR"): self.path(f"M{x-7},{y} C{x+w*.18},{y+h*.25} {x+w*.18},{y+h*.75} {x-7},{y+h}", "none", stroke, 1.8); ins = [(x - 3, y + h * .28), (x - 3, y + h * .72)]
        elif kind == "NOT":
            self.poly([(x, y), (x + w * .8, y + h / 2), (x, y + h)], fill, stroke, 1.8); ox = x + w * .8 + 7; ins = [(x, y + h / 2)]
        if kind in ("NAND", "NOR", "XNOR"): self.circ(x + w + 3.5, y + h / 2, 3.5, "#ffffff", stroke, 1.6); ox = x + w + 7
        if kind == "NOT": self.circ(x + w * .8 + 3.5, y + h / 2, 3.5, "#ffffff", stroke, 1.6)
        if label: self.text(x + w * .45, y + h / 2 + 4, label, 10, C["line"], "middle", False, True)
        return {"in": ins, "out": (ox, y + h / 2)}
    # ---- waveforms
    def wave(self, x, y, bits, step=36, h=22, c=None, label=None, lw=2, edge_marks=False, fill=None):
        """A digital waveform from a string like '0011'. Draws the transitions as vertical lines."""
        c = c or C["blue"]
        if label: self.text(x - 8, y + h / 2 + 4, label, 12, C["ink"], "end", False, True)
        pts = []; prev = None
        for k, b in enumerate(bits):
            yy = y if b == "1" else y + h
            if prev is not None and prev != b: pts.append((x + k * step, y if prev == "1" else y + h))
            pts.append((x + k * step, yy)); pts.append((x + (k + 1) * step, yy)); prev = b
        self.path("M" + " L".join(f"{px:.1f},{py:.1f}" for px, py in pts), "none", c, lw)
    def bus(self, x, y, vals, step=36, h=22, c=None, label=None, fills=None):
        c = c or C["purple"]
        if label: self.text(x - 8, y + h / 2 + 4, label, 12, C["ink"], "end", False, True)
        k = 0
        while k < len(vals):
            j = k
            while j + 1 < len(vals) and vals[j + 1] == vals[k]: j += 1
            x0 = x + k * step; x1 = x + (j + 1) * step; self.path(f"M{x0+4:.1f},{y:.1f} L{x1-4:.1f},{y:.1f} L{x1:.1f},{y+h/2:.1f} L{x1-4:.1f},{y+h:.1f} L{x0+4:.1f},{y+h:.1f} L{x0:.1f},{y+h/2:.1f} Z", (fills or {}).get(vals[k], "#ffffff"), c, 1.6)
            self.text((x0 + x1) / 2, y + h / 2 + 4, vals[k], 11, C["ink"], "middle", False, True); k = j + 1
    def render(self):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{esc(self.title)}"><title>{esc(self.title)}</title>'
                f'<rect x="0.5" y="0.5" width="{self.w-1}" height="{self.h-1}" rx="10" fill="{C["bg"]}" stroke="#d5dbe3"/>' + "".join(self.o) + "</svg>")
    def save(self, path): open(path, "w").write(self.render()); return path
# ---- charts
def bar_chart(w, h, labels, series, title="", ylabel="", colors=None, fmt="{:.0f}", maxv=None, legend=None, horizontal=False):
    f = Fig(w, h, title); L, R, T, B = 70, 20, 40, 60; pw, ph = w - L - R, h - T - B; allv = [v for s in series for v in s]; mv = maxv or max(allv) * 1.12 or 1
    f.text(w / 2, 22, title, 15, bold=True)
    for k in range(5): yy = T + ph * (1 - k / 4); f.line(L, yy, L + pw, yy, C["gray2"], 1); f.text(L - 8, yy + 4, fmt.format(mv * k / 4), 11, C["line"], "end")
    f.text(16, T + ph / 2, ylabel, 12, C["line"], rot=-90); ns = len(series); gw = pw / len(labels); bw = gw * .7 / ns; cols = colors or [C["blue"], C["orange"], C["green"], C["purple"], C["red"]]
    for i, lab in enumerate(labels):
        for j, s in enumerate(series):
            x = L + i * gw + gw * .15 + j * bw; bh = ph * s[i] / mv; f.rect(x, T + ph - bh, bw - 2, bh, cols[j % len(cols)], None, 0, 2); f.text(x + bw / 2 - 1, T + ph - bh - 5, fmt.format(s[i]), 10, C["ink"])
        f.text(L + i * gw + gw / 2, T + ph + 18, lab, 11, C["ink"])
    if legend:
        for j, nm in enumerate(legend): f.rect(L + j * 150, h - 22, 12, 12, cols[j % len(cols)], None, 0, 2); f.text(L + j * 150 + 18, h - 12, nm, 11, C["ink"], "start")
    return f
def line_chart(w, h, xs, series, title="", xlabel="", ylabel="", colors=None, legend=None, logx=False, logy=False, xfmt="{:g}", yfmt="{:g}", marks=True, ymin=None, ymax=None):
    f = Fig(w, h, title); L, R, T, B = 70, 24, 40, 64; pw, ph = w - L - R, h - T - B; f.text(w / 2, 22, title, 15, bold=True)
    tx = (lambda v: math.log10(v)) if logx else (lambda v: v); ty = (lambda v: math.log10(v)) if logy else (lambda v: v)
    X = [tx(v) for v in xs]; ally = [ty(v) for s in series for v in s if v is not None]; x0, x1 = min(X), max(X); y0 = ty(ymin) if ymin is not None else min(ally); y1 = ty(ymax) if ymax is not None else max(ally)
    if y1 == y0: y1 = y0 + 1
    px = lambda v: L + pw * (tx(v) - x0) / ((x1 - x0) or 1); py = lambda v: T + ph * (1 - (ty(v) - y0) / (y1 - y0))
    for k in range(5):
        yy = T + ph * (1 - k / 4); val = y0 + (y1 - y0) * k / 4; f.line(L, yy, L + pw, yy, C["gray2"], 1); f.text(L - 8, yy + 4, yfmt.format(10 ** val if logy else val), 11, C["line"], "end")
    for v in xs: f.line(px(v), T + ph, px(v), T + ph + 4, C["line"], 1); f.text(px(v), T + ph + 18, xfmt.format(v), 11, C["ink"])
    f.text(L + pw / 2, h - 28, xlabel, 12, C["line"]); f.text(16, T + ph / 2, ylabel, 12, C["line"], rot=-90); cols = colors or [C["blue"], C["orange"], C["green"], C["purple"], C["red"]]
    for j, s in enumerate(series):
        pts = [(px(x), py(v)) for x, v in zip(xs, s) if v is not None]; f.path("M" + " L".join(f"{a:.1f},{b:.1f}" for a, b in pts), "none", cols[j % len(cols)], 2.4)
        if marks:
            for a, b in pts: f.circ(a, b, 3.4, cols[j % len(cols)], "#fff", 1)
    if legend:
        for j, nm in enumerate(legend): f.line(L + j * 170, h - 12, L + j * 170 + 22, h - 12, cols[j % len(cols)], 3); f.text(L + j * 170 + 28, h - 8, nm, 11, C["ink"], "start")
    return f
