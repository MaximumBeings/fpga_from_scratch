#!/usr/bin/env python3
"""The book's mascot: a kestrel (a small falcon that hovers motionless in the wind, then dives). Draws the bird as an SVG group, in several poses, for the logo and the chapter pictures. Usage: import kestrel; kestrel.bird(x, y, scale, pose, flip, colors)"""
import math
def bird(x, y, s=1.0, pose="hover", flip=False, body="#b5651d", wing="#8a4b12", light="#f3e3c8", dark="#2d2a26"):
    """Return SVG for a kestrel centred at (x, y). pose: 'hover' (wings raised, tail fanned down), 'glide' (wings level), 'dive' (wings swept back, head down)."""
    f = -1 if flip else 1; P = lambda px, py: f"{f * px:.1f},{py:.1f}"
    if pose == "hover":
        wings = f"M{P(-6,-4)} C{P(-30,-34)} {P(-62,-44)} {P(-84,-30)} C{P(-60,-26)} {P(-42,-16)} {P(-30,-4)} Z M{P(6,-4)} C{P(30,-34)} {P(62,-44)} {P(84,-30)} C{P(60,-26)} {P(42,-16)} {P(30,-4)} Z"
        tail = f"M{P(-8,20)} L{P(-18,62)} L{P(-6,58)} L{P(0,66)} L{P(6,58)} L{P(18,62)} L{P(8,20)} Z"; head_y = -22
    elif pose == "glide":
        wings = f"M{P(-6,-2)} C{P(-30,-10)} {P(-64,-12)} {P(-92,2)} C{P(-64,8)} {P(-40,8)} {P(-26,10)} Z M{P(6,-2)} C{P(30,-10)} {P(64,-12)} {P(92,2)} C{P(64,8)} {P(40,8)} {P(26,10)} Z"
        tail = f"M{P(-8,22)} L{P(-14,58)} L{P(-4,54)} L{P(0,62)} L{P(4,54)} L{P(14,58)} L{P(8,22)} Z"; head_y = -22
    else:
        wings = f"M{P(-6,0)} C{P(-26,10)} {P(-44,30)} {P(-52,60)} C{P(-34,44)} {P(-22,30)} {P(-12,16)} Z M{P(6,0)} C{P(26,10)} {P(44,30)} {P(52,60)} C{P(34,44)} {P(22,30)} {P(12,16)} Z"
        tail = f"M{P(-6,26)} L{P(-10,52)} L{P(0,48)} L{P(10,52)} L{P(6,26)} Z"; head_y = -20
    g = f'<g transform="translate({x:.1f},{y:.1f}) scale({s:.3f})">'
    g += f'<path d="{tail}" fill="{wing}" stroke="{dark}" stroke-width="1.5" stroke-linejoin="round"/>'
    g += f'<path d="{wings}" fill="{wing}" stroke="{dark}" stroke-width="1.6" stroke-linejoin="round"/>'
    g += f'<ellipse cx="0" cy="6" rx="15" ry="26" fill="{body}" stroke="{dark}" stroke-width="1.6"/>'
    g += f'<ellipse cx="0" cy="12" rx="9" ry="16" fill="{light}" opacity="0.85"/>'
    g += "".join(f'<circle cx="{f*dx}" cy="{dy}" r="1.3" fill="{dark}"/>' for dx, dy in ((-4, 6), (4, 10), (-3, 16), (5, 20), (-5, 24)))
    g += f'<circle cx="0" cy="{head_y}" r="11" fill="#9aa5ad" stroke="{dark}" stroke-width="1.6"/>'
    g += f'<path d="M{P(-1,head_y-4)} L{P(10,head_y+3)} L{P(1,head_y+3)} Z" fill="#e8b923" stroke="{dark}" stroke-width="1"/>'
    g += f'<circle cx="{f*-3.5}" cy="{head_y-2}" r="2.4" fill="{dark}"/><path d="M{P(-6,head_y+3)} L{P(-7,head_y+10)}" stroke="{dark}" stroke-width="1.6"/>'
    return g + "</g>"
def logo(path):
    """A square logo: a kestrel hovering over a grid of logic cells (the FPGA fabric), one of them lit."""
    s = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 240"><rect width="240" height="240" rx="40" fill="#0f766e"/>'
    for i in range(6):
        for j in range(3): s += f'<rect x="{30 + i * 31}" y="{150 + j * 25}" width="24" height="19" rx="3" fill="{"#fbbf24" if (i, j) == (3, 1) else "#115e59"}" stroke="#5eead4" stroke-width="1.3"/>'
    s += '<path d="M42,142 H198" stroke="#5eead4" stroke-width="1.5" stroke-dasharray="4 4"/>' + bird(120, 78, 0.95, "hover") + "</svg>"
    open(path, "w").write(s)
if __name__ == "__main__":
    import os; root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); pass  # the header logo (docs/assets/kestrel-logo.svg) is now a hand-drawn white mark on a transparent background, like the Capra one; logo() is kept for the favicon style
    fav = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 240"><rect width="240" height="240" rx="40" fill="#0f766e"/>' + bird(120, 100, 1.3, "hover") + "</svg>"; open(os.path.join(root, "docs", "assets", "kestrel-favicon.svg"), "w").write(fav); print("logo written")
