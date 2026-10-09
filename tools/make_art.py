#!/usr/bin/env python3
"""Write the book's pictures: docs/assets/art/<id>.svg (kestrels over a landscape, a different scene for each page) and <id>.md (a short note on the species shown, included on the page). The scenes are stylised drawings. Usage: make_art.py"""
import os, random, sys, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import kestrel
HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "assets", "art")
SPECIES = {
 "common": ("Common kestrel", "Falco tinnunculus", "ranges across Europe, Asia and Africa. It is famous for hovering: it faces the wind and holds its head almost still while its body adjusts, searching the ground below before it drops onto prey. A much-cited study reported that voles' scent trails reflect ultraviolet light, which kestrels may be able to see."),
 "american": ("American kestrel", "Falco sparverius", "is the smallest falcon in North America and is found from Alaska to South America. The sexes differ in plumage: males have blue-grey wings, females are barred rufous. It hunts insects and small vertebrates from perches and by hovering."),
 "lesser": ("Lesser kestrel", "Falco naumanni", "breeds in colonies in Mediterranean Europe and Central Asia and migrates to Africa for the winter. It feeds largely on large insects and nests in cavities in old buildings and cliffs."),
 "mauritius": ("Mauritius kestrel", "Falco punctatus", "lives only on the island of Mauritius. By the mid-1970s only a handful of wild birds were known (the figure usually quoted is four); captive breeding and release programmes brought the population back to hundreds."),
 "nankeen": ("Nankeen kestrel", "Falco cenchroides", "is found across Australia and nearby islands. It hovers over open country and grassland, and often hunts along roadsides and fields."),
 "seychelles": ("Seychelles kestrel", "Falco araeus", "is found on the granitic islands of the Seychelles. It is a small kestrel that hunts lizards and insects in forest and around villages."),
}
SKY = {"dawn": ("#fde68a", "#fb923c", "#7c3aed"), "day": ("#bae6fd", "#7dd3fc", "#0ea5e9"), "dusk": ("#fcd34d", "#f472b6", "#4338ca"), "night": ("#312e81", "#1e1b4b", "#0f172a"), "storm": ("#cbd5e1", "#94a3b8", "#475569")}
TERRAIN = ["hills", "city", "canyon", "coast", "mesa", "field"]
def terrain(kind, w, h, R, dark):
    col = ["#14532d", "#166534", "#15803d"] if not dark else ["#0f172a", "#111827", "#1f2937"]; o = ""
    if kind == "hills":
        for k, c in enumerate(col): pts = " ".join(f"{x},{h - 30 - k * 24 - 18 * (1 + __import__('math').sin(x / 70 + k * 2 + R.random()))}" for x in range(0, w + 40, 40)); o += f'<polygon points="0,{h} {pts} {w},{h}" fill="{c}"/>'
    elif kind == "city":
        x = 0
        while x < w:
            bw = R.randrange(24, 52); bh = R.randrange(40, 130); o += f'<rect x="{x}" y="{h - bh}" width="{bw}" height="{bh}" fill="{"#1e293b" if not dark else "#020617"}"/>'
            for wy in range(h - bh + 8, h - 6, 14):
                for wx in range(x + 5, x + bw - 6, 11):
                    if R.random() < 0.35: o += f'<rect x="{wx}" y="{wy}" width="5" height="7" fill="#fde047" opacity="0.8"/>'
            x += bw + R.randrange(0, 8)
    elif kind == "canyon":
        o += f'<polygon points="0,{h} 0,{h - 120} 90,{h - 150} 150,{h - 90} 210,{h - 40} {w - 210},{h - 40} {w - 150},{h - 100} {w - 80},{h - 160} {w},{h - 110} {w},{h}" fill="#9a3412"/><polygon points="0,{h} 0,{h - 60} 120,{h - 30} {w // 2},{h - 14} {w - 120},{h - 30} {w},{h - 60} {w},{h}" fill="#7c2d12"/>'
    elif kind == "coast":
        o += f'<rect x="0" y="{h - 70}" width="{w}" height="70" fill="#0369a1"/><polygon points="0,{h} 0,{h - 60} 160,{h - 52} 300,{h - 26} {w // 2 + 40},{h - 10} {w // 2 + 60},{h}" fill="#a16207"/>' + "".join(f'<path d="M{x},{h - 50 + (k % 3) * 8} q12,-6 24,0" stroke="#e0f2fe" fill="none" stroke-width="1.6"/>' for k, x in enumerate(range(w // 2 + 80, w - 20, 46)))
    elif kind == "mesa":
        o += f'<polygon points="{w//2-200},{h} {w//2-170},{h-110} {w//2+50},{h-110} {w//2+90},{h}" fill="#b45309"/><polygon points="0,{h} 0,{h-40} 140,{h-24} {w},{h-36} {w},{h}" fill="#92400e"/>'
    else:
        for k in range(6): o += f'<rect x="0" y="{h - 70 + k * 12}" width="{w}" height="14" fill="{"#ca8a04" if k % 2 == 0 else "#a16207"}" opacity="{0.9 - k * 0.05}"/>'
    return o
def scene(pid, count=2):
    R = random.Random(pid); w, h = 900, 300; tod = R.choice(list(SKY)); dark = tod == "night"; c0, c1, c2 = SKY[tod]
    s = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-label="kestrels over a landscape"><defs><linearGradient id="g{zlib.crc32(pid.encode()) % 9999}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c2}"/><stop offset="0.6" stop-color="{c1}"/><stop offset="1" stop-color="{c0}"/></linearGradient></defs>'
    gid = f"g{zlib.crc32(pid.encode()) % 9999}"; s = s.replace(f'id="g{zlib.crc32(pid.encode()) % 9999}"', f'id="{gid}"')
    s += f'<rect width="{w}" height="{h}" fill="url(#{gid})"/>'
    if dark: s += "".join(f'<circle cx="{R.randrange(w)}" cy="{R.randrange(160)}" r="{R.choice([1, 1, 1.6])}" fill="#f8fafc" opacity="0.8"/>' for _ in range(70))
    else: s += f'<circle cx="{R.randrange(120, w - 120)}" cy="{R.randrange(50, 110)}" r="{R.randrange(22, 34)}" fill="{"#fff7ed" if tod != "dusk" else "#fed7aa"}" opacity="0.9"/>'
    if tod in ("day", "storm", "dawn"): s += "".join(f'<ellipse cx="{R.randrange(w)}" cy="{R.randrange(30, 120)}" rx="{R.randrange(40, 90)}" ry="{R.randrange(8, 16)}" fill="#ffffff" opacity="{0.5 if tod != "storm" else 0.7}"/>' for _ in range(4))
    s += terrain(R.choice(TERRAIN), w, h, R, dark)
    names = list(SPECIES); R.shuffle(names); cast = names[:count]
    for k, nm in enumerate(cast):
        pose = R.choice(["hover", "glide", "dive"]) if k else "hover"; x = R.randrange(120, w - 120) if k == 0 else (R.randrange(80, 300) if R.random() < .5 else R.randrange(w - 300, w - 80)); y = R.randrange(95, 150) if pose != "dive" else R.randrange(110, 170)
        s += kestrel.bird(x, y, R.choice([0.7, 0.85, 1.0]) if k == 0 else R.choice([0.45, 0.55]), pose, R.random() < .5, *(("#b5651d", "#8a4b12", "#f3e3c8", "#2d2a26") if nm not in ("american", "lesser") else ("#c2410c", "#64748b", "#fde68a", "#1f2937")))
    return s + "</svg>", cast
def caption(cast, pid):
    items = "\n".join(f"    - **{SPECIES[c][0]}** (*{SPECIES[c][1]}*) {SPECIES[c][3] if False else SPECIES[c][2]}" for c in cast)
    return f'??? info "About the kestrels in this picture"\n{items}\n\n    The scene is imaginary and the birds are stylised drawings.\n'
PLAN = ["index", "contents"] + [f"ch-{i:02d}" for i in range(1, 50)] + [f"appx-{c}" for c in "abcdefghijkl"]
if __name__ == "__main__":
    os.makedirs(HERE, exist_ok=True)
    for pid in PLAN:
        svg, cast = scene(pid); open(os.path.join(HERE, pid + ".svg"), "w").write(svg); open(os.path.join(HERE, pid + ".md"), "w").write(caption(cast, pid))
    print(len(PLAN), "pictures and captions written")
