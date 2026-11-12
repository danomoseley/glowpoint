"""Draw the section (profile) of a 3D fixture, with its dimensions and its light.

  python3 -m glowpoint.profile <project> <fixture name> [--out NAME.png] [--rays N] [--no-dimensions] [--half]

The fixture comes from the project's fixture lists (library/fixtures.json, <project>/fixtures.json, or
"fixtures" in design.json) and must have a "body" (see glowpoint/body.py). The drawing is a line drawing to
scale: the section through the axis (revolved parts are cut, so both halves of each profile are drawn), the
axis as a dash-dot line, the overall width and height, each light point, and rays from each light: up or down
in its direction, and, when the light is aimed onto a part, reflected off that part. Output:
out/profile_<fixture>.png (or --out).
"""
import argparse, json, math, os, sys

import cv2
import numpy as np

from glowpoint import pngmark
from glowpoint.plugins import load_fixtures
from glowpoint import features as F
from glowpoint.body import profile_points

INK, GREY, PAPER = (20, 20, 20), (140, 140, 140), (255, 255, 255)
FONT = cv2.FONT_HERSHEY_SIMPLEX


def feet_inches(v):
    i = round(v * 12 * 4) / 4
    ft, inch = int(i // 12), i - 12 * int(i // 12)
    s = f"{inch:g}\""
    return f"{ft}'-{s}" if ft else s


def _segments(spec, half=False):
    """Section lines (x, y) in the fixture's own axes, each with the index of its part."""
    out = []
    for i, p in enumerate(spec["body"]):
        if p.get("kind", "revolve") == "revolve":
            prof = [(float(r), float(y)) for r, y in profile_points(p)]
            for side in ((1,) if half else (1, -1)):
                out.append((i, [(side * r, y) for r, y in prof]))
        else:
            (x0, x1), (y0, y1) = p["X"], p["Y"]
            out.append((i, [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]))
    return out


def _hit(o, d, segs, skip=None):
    """First intersection of the ray o + t d (t > 0) with the section lines: (t, point, unit normal, part)."""
    best = None
    for i, pts in segs:
        for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
            ex, ey = bx - ax, by - ay
            den = d[0] * ey - d[1] * ex
            if abs(den) < 1e-12: continue
            t = ((ax - o[0]) * ey - (ay - o[1]) * ex) / den
            u = ((ax - o[0]) * d[1] - (ay - o[1]) * d[0]) / den
            if t > 1e-6 and -1e-9 <= u <= 1 + 1e-9 and (best is None or t < best[0]):
                n = np.array([-ey, ex]); n /= np.linalg.norm(n)
                if n @ d > 0: n = -n
                best = (t, o + t * d, n, i)
    return best


def profile(project, name, out=None, size=900, rays=7, dimensions=True, half=False):
    dp = os.path.join(project, "design.json")
    design = json.load(open(dp)) if os.path.exists(dp) else {}
    fx = load_fixtures(project, design)
    if name not in fx: raise SystemExit(f"No fixture named '{name}'. Known: {sorted(fx)}")
    spec = fx[name]
    if "body" not in spec: raise SystemExit(f"fixture '{name}' has no 'body' (3D parts)")
    segs = _segments(spec, half)
    xs = [x for _, pts in segs for x, _ in pts]; ys = [y for _, pts in segs for _, y in pts]
    for L in spec.get("lights", []): xs.append(L["at"][0]); ys.append(L["at"][1])
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    span = max(x1 - x0, y1 - y0, 1e-3)
    reach_y0 = y0
    s = (size - 300) / span
    W, H = size, int((y1 - y0) * s + 0.45 * span * s + 330)
    img = np.full((H, W, 3), PAPER, np.uint8)
    ox, oy = W / 2 - (x0 + x1) / 2 * s, H - 110 - 0.45 * span * s + y0 * s
    P = lambda x, y: (int(round(ox + x * s)), int(round(oy - y * s)))
    # light rays first, under the linework
    col = F.cct_bgr(spec.get("cct", 2700))
    reach = span * 0.9
    for L in spec.get("lights", []):
        o = np.array([L["at"][0], L["at"][1]], float)
        up = L.get("direction", "down") == "up"
        half_a = math.radians(L.get("beam", 100) / 2)
        target = [sg for sg in segs if sg[0] == L.get("onto")]       # rays meet only the part they are aimed at
        for a in (np.linspace(-half_a, half_a, rays) if rays > 1 else ([0.0] if rays == 1 else [])):
            d = np.array([math.sin(a), math.cos(a) if up else -math.cos(a)])
            h = _hit(o, d, target) if target else None
            if h is None:
                end = o + d * reach; cv2.arrowedLine(img, P(*o), P(*end), col, 2, cv2.LINE_AA, tipLength=0.04); continue
            t, q, n, part = h
            cv2.line(img, P(*o), P(*q), col, 2, cv2.LINE_AA)
            if L.get("onto") is not None and part == L["onto"]:
                r = d - 2 * (d @ n) * n                       # reflect off the part
                y_end = y0 - 0.4 * span                       # the reflected rays end a little below the fixture
                t2 = (q[1] - y_end) / -r[1] if r[1] < -1e-6 else reach * 0.5
                end = q + r * min(t2, reach)
                cv2.arrowedLine(img, P(*q), P(*end), col, 2, cv2.LINE_AA, tipLength=0.05)
        c = P(*o); cv2.circle(img, c, 7, col, -1, cv2.LINE_AA); cv2.circle(img, c, 7, INK, 1, cv2.LINE_AA)
    # section lines
    for i, pts in segs:
        role = spec["body"][i].get("role", "housing")
        th = 3 if role in ("reflector", "housing") else 2
        cv2.polylines(img, [np.int32([P(x, y) for x, y in pts])], False, INK, th, cv2.LINE_AA)
    # axis
    ax_top, ax_bot = P(0, y1 + span * 0.08), P(0, y0 - span * 0.08)
    n = int(math.hypot(ax_top[0] - ax_bot[0], ax_top[1] - ax_bot[1]) / 14)
    for k in range(n):
        if k % 3 == 2: continue
        a = ax_bot[1] - (ax_bot[1] - ax_top[1]) * k / n; b = ax_bot[1] - (ax_bot[1] - ax_top[1]) * (k + .7) / n
        cv2.line(img, (ax_top[0], int(a)), (ax_top[0], int(b)), GREY, 1, cv2.LINE_AA)
    # dimensions: overall width (above) and height (right)
    def dim(a, b, text, horizontal):
        cv2.line(img, a, b, INK, 1, cv2.LINE_AA)
        for p_ in (a, b):
            d = 6
            cv2.line(img, (p_[0] - d, p_[1] + d), (p_[0] + d, p_[1] - d), INK, 1, cv2.LINE_AA)
        (tw, th_), _ = cv2.getTextSize(text, FONT, 0.55, 1)
        if horizontal: cv2.putText(img, text, ((a[0] + b[0]) // 2 - tw // 2, a[1] - 8), FONT, 0.55, INK, 1, cv2.LINE_AA)
        else: cv2.putText(img, text, (a[0] + 10, (a[1] + b[1]) // 2 + th_ // 2), FONT, 0.55, INK, 1, cv2.LINE_AA)
    yt = P(0, y1)[1] - 40
    if dimensions: dim((P(x0, 0)[0], yt), (P(x1, 0)[0], yt), feet_inches(x1 - x0), True)
    xr = P(x1, 0)[0] + 40
    if dimensions:
        for xx in (x0, x1): cv2.line(img, (P(xx, 0)[0], yt - 6), (P(xx, 0)[0], P(xx, y1)[1] - 4), GREY, 1)
        dim((xr, P(0, y1)[1]), (xr, P(0, y0)[1]), feet_inches(y1 - y0), False)
        for yy in (y0, y1): cv2.line(img, (P(x1, 0)[0] + 4, P(0, yy)[1]), (xr + 6, P(0, yy)[1]), GREY, 1)
    cv2.putText(img, f"{name.upper()}  -  SECTION", (30, 40), FONT, 0.75, INK, 2, cv2.LINE_AA)
    if spec.get("description"):
        cv2.putText(img, spec["description"][:90], (30, 68), FONT, 0.5, GREY, 1, cv2.LINE_AA)
    os.makedirs(os.path.join(project, "out"), exist_ok=True)
    path = os.path.join(project, "out", out or f"profile_{name}.png")
    pngmark.write(path, img)
    print(f"wrote {path}")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project"); ap.add_argument("fixture"); ap.add_argument("--out")
    ap.add_argument("--rays", type=int, default=7, help="light rays from each light point (0 = none)")
    ap.add_argument("--no-dimensions", action="store_true", help="leave out the width and height")
    ap.add_argument("--half", action="store_true", help="draw only the right half of revolved parts")
    a = ap.parse_args(argv)
    profile(a.project, a.fixture, a.out, rays=a.rays, dimensions=not a.no_dimensions, half=a.half)
    return 0


if __name__ == "__main__":
    sys.exit(main())
