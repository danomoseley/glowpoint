"""3D fixtures: a fixture body made of simple parts with real dimensions, drawn in the perspective in the same
diagrammatic style as the rest of the drawing, hidden correctly behind the architecture.

A body is described in a fixture list (fixtures.json, library/fixtures.json, or "fixtures" in design.json):

  "reflector-pendant": {
    "description": "indirect pendant: uplight under a curved reflector",
    "body": [
      {"kind": "revolve", "role": "reflector", "profile": [[0, 1.1], [0.6, 1.02], [1.0, 0.85], [1.25, 0.62]]},
      {"kind": "revolve", "role": "housing",   "profile": [[0.02, 0.25], [0.02, 1.1]]},
      {"kind": "revolve", "role": "housing",   "profile": [[0, 0], [0.16, 0], [0.16, 0.25], [0, 0.25]]}
    ],
    "lights": [{"at": [0, 0.25, 0], "direction": "up", "onto": 0}],
    "pool_r": 4
  }

Sizes are in feet. The fixture's own axes: x to the right, y up, z away; y = 0 is the bottom of the fixture,
and the axis of revolution is x = z = 0.

Parts:
  revolve   "profile": [[r, y], ...], a line turned around the vertical axis (domes, cones, cylinders, bowls,
            reflectors, discs: use r = 0 at an end to close it)
  box       "X": [x0, x1], "Y": [y0, y1], "Z": [z0, z1] (linear housings, channels, arms)
  "role":   housing (white, the default), reflector (lit on the side that faces its light), lens (lit), dark
  "smooth": true rounds a revolved profile (a few points give a smooth curve): good for reflectors and domes

A 3D fixture is a diagram, not a product model: a few profile points that give the right shape and the main
dimensions are enough.

Lights inside the fixture ("lights"):
  "at"         the light point, in the fixture's own axes
  "direction"  up or down
  "onto"       the index of the part that it lights (a reflector); that part glows on the side that faces it
  The fixture's light reaches the room as a pool of radius "pool_r" (ft) on the floor below (or on "beam_to"),
  and an up light with nothing above it lights the ceiling ("ceiling_r").

In design.json:
  {"type": "fixture3d", "fixture": "reflector-pendant", "plane": "Ceiling", "x": [...], "z": [...],
   "y": 9}            the bottom of the fixture above the floor, or "drop": from the ceiling to the fixture top
   "rotate": 0        turn about the vertical axis, degrees (for boxes)
   "cord": true       a line from the ceiling (or "from_y") to the top of the fixture
   "scale": 1         make the whole fixture larger or smaller

Look (in the design feature, or as "style" in the fixture definition; the feature wins):
   "fill": "white"    white body that hides what is behind it; "none" draws only the lines
   "detail": "rings"  lines at each break of the profile and the box edges; "outline" only the outlines
   "glow": true       lit reflectors and lenses in the light colour; false for plain lines
   "line": 1          line width in pixels

python3 -m glowpoint.profile <project> <fixture> draws the same body as a section with dimensions.
"""
import itertools

import cv2
import numpy as np

from glowpoint import features as F

SEG = 48                               # segments around a revolved part
FILL = {"housing": (252, 252, 252), "reflector": (246, 246, 246), "lens": (250, 250, 250), "dark": (70, 70, 70)}


def body_of(cv, f):
    name = f["fixture"]
    spec = cv.fixtures.get(name) if isinstance(name, str) else name
    if spec is None:
        raise KeyError(f"No fixture named '{name}'. Known: {sorted(cv.fixtures)}")
    if "body" not in spec:
        raise ValueError(f"fixture '{name}' has no 'body' (3D parts); use the 'fixture' type for flat fixtures")
    return spec


def profile_points(p):
    """The profile of a revolved part; "smooth": true rounds its corners (for curved reflectors and domes)."""
    pts = np.asarray(p["profile"], float)
    if p.get("smooth"):
        for _ in range(3):                                         # Chaikin corner cutting, ends kept
            q = [pts[0]]
            for a, b in zip(pts[:-1], pts[1:]):
                q += [0.75 * a + 0.25 * b, 0.25 * a + 0.75 * b]
            q.append(pts[-1]); pts = np.asarray(q)
    return pts


def part_mesh(p, seg=SEG):
    """Triangles (n, 3, 3) and outward normals (n, 3) of one part, in the fixture's own axes."""
    tris = []
    if p.get("kind", "revolve") == "revolve":
        prof = profile_points(p)
        th = np.linspace(0, 2 * np.pi, seg + 1)
        ring = lambda r, y: np.stack([r * np.cos(th), np.full_like(th, y), r * np.sin(th)], 1)
        for (r0, y0), (r1, y1) in zip(prof[:-1], prof[1:]):
            a, b = ring(r0, y0), ring(r1, y1)
            for k in range(seg):
                tris.append([a[k], a[k + 1], b[k + 1]]); tris.append([a[k], b[k + 1], b[k]])
    elif p["kind"] == "box":
        (x0, x1), (y0, y1), (z0, z1) = p["X"], p["Y"], p["Z"]
        c = np.array([[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)])
        for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            tris.append([c[q[0]], c[q[1]], c[q[2]]]); tris.append([c[q[0]], c[q[2]], c[q[3]]])
    else:
        raise ValueError(f"unknown part kind {p.get('kind')}: use revolve or box")
    T = np.asarray(tris, float)
    N = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    ln = np.linalg.norm(N, axis=1); keep = ln > 1e-12
    T, N = T[keep], N[keep] / ln[keep, None]
    centre = T.mean(1)
    if p.get("kind", "revolve") == "revolve":                    # outward = away from the axis (or up/down)
        radial = centre * np.array([1, 0, 1]); radial[np.linalg.norm(radial, axis=1) < 1e-9] = [0, 1, 0]
        flip = (N * radial).sum(1) < 0
    else:
        mid = np.array([sum(p["X"]) / 2, sum(p["Y"]) / 2, sum(p["Z"]) / 2])
        flip = (N * (centre - mid)).sum(1) < 0
    N[flip] *= -1
    return T, N


def height(spec):
    ys = []
    for p in spec["body"]:
        ys += [q[1] for q in p["profile"]] if p.get("kind", "revolve") == "revolve" else list(p["Y"])
    return max(ys), min(ys)


def radius(spec):
    rs = []
    for p in spec["body"]:
        if p.get("kind", "revolve") == "revolve": rs += [abs(q[0]) for q in p["profile"]]
        else: rs += [abs(v) for v in p["X"] + p["Z"]]
    return max(rs) if rs else 0.5


STYLE = {"fill": "white", "detail": "rings", "glow": True, "line": 1}


def draw_one(cv, spec, origin, rot_deg=0.0, scale=1.0, style=None):
    """Draw one body at origin (the bottom of its axis). Returns True if any of it is visible."""
    st = dict(STYLE, **(spec.get("style") or {}), **(style or {}))
    lw = int(st["line"])
    m = cv.m; H, W = cv.dep.shape
    c, s = np.cos(np.radians(rot_deg)), np.sin(np.radians(rot_deg))
    Rf = np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]])
    zbuf = cv.dep.copy(); pid = np.full((H, W), -1, np.int32); back = np.zeros((H, W), bool)
    lit_parts = {L.get("onto") for L in spec.get("lights", []) if L.get("onto") is not None}
    for i, p in enumerate(spec["body"]):
        T, N = part_mesh(p)
        T = (T * scale) @ Rf.T + origin; N = N @ Rf.T
        flat = T.reshape(-1, 3); q = m.cam(flat); z = q[:, 2].reshape(-1, 3)
        pix = m.project(flat).reshape(-1, 3, 2)
        view = T.mean(1) - m.C                                     # from the camera to the triangle
        facing_away = (N * view).sum(1) > 0                        # we see its inner (back) side
        for t in range(len(T)):
            if (z[t] <= 0.05).any(): continue
            P = pix[t]
            x0, y0 = np.floor(P.min(0)).astype(int); x1, y1 = np.ceil(P.max(0)).astype(int)
            x0, y0 = max(x0, 0), max(y0, 0); x1, y1 = min(x1, W - 1), min(y1, H - 1)
            if x0 > x1 or y0 > y1: continue
            ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
            (ax, ay), (bx, by), (cx, cy) = P
            d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(d) < 1e-9:
                continue
            w0 = ((by - cy) * (xs + .5 - cx) + (cx - bx) * (ys + .5 - cy)) / d
            w1 = ((cy - ay) * (xs + .5 - cx) + (ax - cx) * (ys + .5 - cy)) / d
            w2 = 1 - w0 - w1
            inside = (w0 >= -1e-3) & (w1 >= -1e-3) & (w2 >= -1e-3)
            if not inside.any(): continue
            # perspective-correct depth: interpolate 1/z
            zz = 1.0 / (w0 / z[t, 0] + w1 / z[t, 1] + w2 / z[t, 2])
            sub = zbuf[y0:y1 + 1, x0:x1 + 1]
            win = inside & (zz < sub - 0.005)
            if not win.any(): continue
            sub[win] = zz[win]
            pid[y0:y1 + 1, x0:x1 + 1][win] = i
            back[y0:y1 + 1, x0:x1 + 1][win] = facing_away[t]
    vis = pid >= 0
    if not vis.any(): return False
    # fill: white body (it hides the light behind it), glow where a part is lit
    for i, p in enumerate(spec["body"]):
        k = pid == i
        if not k.any(): continue
        role = p.get("role", "housing"); col = FILL.get(role, FILL["housing"])
        if st["fill"] != "none" or role == "dark":
            cv.img[k] = col; cv.over[k] = col
        lit = st["glow"] and (role == "lens" or (role == "reflector" and i in lit_parts and back[k].any()))
        if lit:
            kk = k & back if role == "reflector" else k
            g = np.zeros((H, W), float); g[kk] = 0.85
            cv.over[kk] = F.LENS if role == "lens" else F.GLOW
    # detail lines: a line at each break of a revolved profile (rims, steps), and the edges of boxes
    def visible_poly(pts, th=1):
        q = m.cam(pts); z = q[:, 2]; px = m.project(pts)
        ok = np.zeros(len(pts), bool)
        for j, ((u, v), zz) in enumerate(zip(px, z)):
            if zz <= 0.05 or not (np.isfinite(u) and np.isfinite(v)): continue
            ui, vi = int(u), int(v)
            if 0 <= ui < W and 0 <= vi < H:
                ok[j] = zz <= zbuf[vi, ui] + max(0.02, 0.004 * zz)
        for j in range(len(pts) - 1):
            if ok[j] and ok[j + 1]:
                cv2.line(cv.img, tuple(np.int32(px[j])), tuple(np.int32(px[j + 1])), (0, 0, 0), th, cv2.LINE_AA)
    th_ = np.linspace(0, 2 * np.pi, 97)
    for p in (spec["body"] if st["detail"] != "outline" else []):
        if p.get("kind", "revolve") == "revolve":
            for r, y in p["profile"]:
                if r * scale * m.f / max(np.linalg.norm(origin - m.C), 1e-6) < 1.5: continue   # too small to see
                ring = np.stack([r * np.cos(th_), np.full_like(th_, y), r * np.sin(th_)], 1) * scale
                visible_poly(ring @ Rf.T + origin)
        else:
            (x0, x1), (y0, y1), (z0, z1) = p["X"], p["Y"], p["Z"]
            cn = [np.array([x, y, z]) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
            for a, b in itertools.combinations(range(8), 2):
                if sum(cn[a] != cn[b]) == 1:                      # an edge of the box
                    pts = np.linspace(cn[a], cn[b], 24) * scale
                    visible_poly(pts @ Rf.T + origin)
    # outlines: the edge of each part, and of the whole body
    for i in range(len(spec["body"])):
        k = (pid == i).astype(np.uint8)
        if k.any():
            cs, _ = cv2.findContours(k, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            cv2.drawContours(cv.img, cs, -1, (0, 0, 0), lw, cv2.LINE_AA)
            if spec["body"][i].get("role") == "reflector":     # the rim between the inner and outer side
                kb = (k.astype(bool) & back).astype(np.uint8)
                if kb.any() and kb.sum() < k.sum():
                    cs2, _ = cv2.findContours(kb, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
                    cv2.drawContours(cv.img, cs2, -1, (0, 0, 0), lw, cv2.LINE_AA)
    return True


def _pool(cv, x, z, y_to, r):
    """Soft pool of light of radius r on the horizontal surface at height y_to."""
    if r <= 0: return
    P = cv.P; on = np.abs(P[..., 1] - y_to) < 0.05
    d = np.hypot(P[..., 0] - x, P[..., 2] - z)
    g = np.clip(1 - d / r, 0, 1) ** 1.5 * 0.75
    cv.glow(on, g)


def _ceiling_glow(cv, x, z, y_from, r):
    if r <= 0: return
    P = cv.P; above = (cv.ids >= 0) & (P[..., 1] > y_from + 0.3)
    horiz = np.array([s["axis"] == 1 for s in cv.m.surfaces] + [False])[np.clip(cv.ids, -1, None)]
    d = np.hypot(P[..., 0] - x, P[..., 2] - z)
    cv.glow(above & horiz, np.clip(1 - d / r, 0, 1) ** 1.5 * 0.7)


def fixture3d(cv, f):
    m = cv.m; spec = body_of(cv, f)
    scale = f.get("scale", 1.0); top_y, bottom_y = height(spec)
    s = m.surface(f["plane"]) if "plane" in f else None
    for x, z in itertools.product(F.as_list(f["x"]), F.as_list(f["z"])):
        hang = f.get("from_y", s["at"] if s is not None and s["axis"] == 1 else None)
        if "y" in f: y = f["y"]
        elif hang is not None: y = hang - f.get("drop", 2.0) - top_y * scale
        else: raise ValueError("fixture3d needs 'y', or 'plane' / 'from_y' with 'drop'")
        origin = np.array([x, y - bottom_y * scale, z])
        # light into the room first, so the body is drawn over it
        lights = spec.get("lights", [])
        if any(L.get("onto") is not None or L.get("direction", "down") == "down" for L in lights):
            _pool(cv, x, z, f.get("beam_to", 0.0), f.get("pool_r", spec.get("pool_r", 0.0)))
        if any(L.get("direction") == "up" and L.get("onto") is None for L in lights):
            _ceiling_glow(cv, x, z, y + top_y * scale, f.get("ceiling_r", spec.get("ceiling_r", 4.0)))
        if f.get("cord", True) and hang is not None and hang > y + top_y * scale + 0.05:
            cv.seg([x, hang, z], [x, y + top_y * scale, z], 1)
        vis = draw_one(cv, spec, origin, f.get("rotate", 0.0), scale,
                       {k: f[k] for k in ("fill", "detail", "glow", "line") if k in f})
        cv.add(f, "fixture3d", f.get("plane", "point"), [x, y, z], visible=bool(vis),
               note=f["fixture"] if isinstance(f["fixture"], str) else "", size=round(2 * radius(spec) * scale, 2))


F.LIGHTS["fixture3d"] = fixture3d
