"""Draw a plan of the project: a reflected ceiling plan or a floor plan, with a symbol for each light.

  python3 -m glowpoint.plan <project> [--rcp] [--all] [--design design.json] [--out NAME.png] [--title TEXT]

  (default)  floor plan: lights below 7 ft (uplights, sconces, furniture and lamp light, floor patterns)
  --rcp      reflected ceiling plan: lights at 7 ft and above (downlights, slots, track, pendants, wallwashers,
             coves) and the ceiling elements (coffers, coves, slats, light wells, luminous areas, ceiling heights)
  --all      every light, in either plan

The plan is drawn straight down (orthographic), to scale, with X to the right and Z (away from the drawing's
viewer) up the page. A reflected ceiling plan uses the same orientation as the floor plan. The marker at the
bottom shows where the drawing's viewer stands and which way they look. Columns are solid; furniture is
dashed in the reflected ceiling plan. Each layer of the design gets its own symbol colour and a line in the
legend, with its light count. Output: out/plan.png or out/rcp.png (or --out), and the light list in
out/positions_plan.csv or out/positions_rcp.csv.
"""
import argparse, csv, math, os, sys

import cv2, numpy as np

from glowpoint import pngmark
from glowpoint.model import Model

CEILING_MIN = 7.0                      # ft: lights at or above this height are in the reflected ceiling plan
INK, GREY, LIGHT_GREY, PAPER = (30, 30, 30), (120, 120, 120), (215, 215, 215), (255, 255, 255)
LAYER_COLOURS = [(0, 110, 230), (190, 90, 0), (40, 150, 40), (160, 40, 160), (0, 140, 170), (40, 40, 200),
                 (130, 100, 0), (90, 90, 200), (0, 90, 140), (150, 0, 90)]          # BGR, readable on white
FONT = cv2.FONT_HERSHEY_SIMPLEX
GEOMETRY_TYPES = {"waffle", "cove", "slats", "lightwell"}


class Sheet:
    def __init__(self, x0, x1, z0, z1, width=1500, margin=70, legend_w=380):
        self.s = (width - 2 * margin - legend_w) / max(x1 - x0, 1e-6)
        self.s = min(self.s, 1100 / max(z1 - z0, 1e-6))
        self.x0, self.z1, self.m = x0, z1, margin
        self.W = int((x1 - x0) * self.s + 2 * margin + legend_w)
        self.H = int((z1 - z0) * self.s + 2 * margin + 120)
        self.img = np.full((self.H, self.W, 3), PAPER, np.uint8)
        self.plan_right = int((x1 - x0) * self.s + 2 * margin)

    def p(self, x, z):
        return (int(round(self.m + (x - self.x0) * self.s)), int(round(self.m + 50 + (self.z1 - z) * self.s)))

    def ft(self, d):
        return max(1, int(round(d * self.s)))

    def line(self, a, b, col=INK, w=1, dashed=False):
        A, B = self.p(*a), self.p(*b)
        if not dashed:
            cv2.line(self.img, A, B, col, w, cv2.LINE_AA); return
        L = math.hypot(B[0] - A[0], B[1] - A[1]); n = max(1, int(L / 8))
        for i in range(0, n, 2):
            t0, t1 = i / n, min(1, (i + 1) / n)
            cv2.line(self.img, (int(A[0] + (B[0] - A[0]) * t0), int(A[1] + (B[1] - A[1]) * t0)),
                     (int(A[0] + (B[0] - A[0]) * t1), int(A[1] + (B[1] - A[1]) * t1)), col, w, cv2.LINE_AA)

    def rect(self, X, Z, col=INK, w=1, fill=None, dashed=False):
        if fill is not None:
            cv2.rectangle(self.img, self.p(X[0], Z[1]), self.p(X[1], Z[0]), fill, -1)
        for a, b in (((X[0], Z[0]), (X[1], Z[0])), ((X[1], Z[0]), (X[1], Z[1])),
                     ((X[1], Z[1]), (X[0], Z[1])), ((X[0], Z[1]), (X[0], Z[0]))):
            self.line(a, b, col, w, dashed)

    def circle(self, x, z, r_ft, col=INK, w=1, fill=None, min_px=4):
        c = self.p(x, z); r = max(min_px, self.ft(r_ft))
        if fill is not None: cv2.circle(self.img, c, r, fill, -1, cv2.LINE_AA)
        cv2.circle(self.img, c, r, col, w, cv2.LINE_AA)
        return c, r

    def text(self, s, x, z=None, size=0.45, col=INK, w=1, px=None):
        pos = px if px is not None else self.p(x, z)
        cv2.putText(self.img, s, pos, FONT, size, col, w, cv2.LINE_AA)


def feet_inches(v):
    i = int(round(v * 12)); return f"{i // 12}'-{i % 12}\""


def bounds(m):
    xs, zs = [], []
    for s in m.surfaces:
        if "X" in s: xs += s["X"]
        if "Z" in s: zs += s["Z"]
        if s["axis"] == 0: xs.append(s["at"])
        if s["axis"] == 2: zs.append(s["at"])
    for b in m.boxes.values():
        xs += [b.x0, b.x1]; zs += [b.z0, b.z1]
    return min(xs), max(xs), min(zs), max(zs)


def draw_architecture(sh, m, rcp):
    surfs = [s for s in m.surfaces if "box" not in s]          # box faces are drawn with their boxes
    floor = [s for s in surfs if s["axis"] == 1 and s["at"] <= 0.01]
    for s in floor:
        if not rcp: sh.rect(s["X"], s["Z"], LIGHT_GREY, 1, fill=(247, 247, 247))
    labels = []
    if rcp:                                   # ceiling areas, with their heights
        for s in surfs:
            if s["axis"] == 1 and s["at"] > 0.01:
                sh.rect(s["X"], s["Z"], GREY, 1)
                for h in s.get("holes", []):
                    sh.rect(h["X"], h["Z"], GREY, 1)
                labels.append(((s["X"][0] + s["X"][1]) / 2, s["Z"][1] - 0.04 * (s["Z"][1] - s["Z"][0]),
                               f"CLG {feet_inches(s['at'])}"))
    for s in surfs:                           # walls to the floor; steps in the ceiling are thin
        full = s["axis"] != 1 and s.get("Y", [0, 0])[0] <= 0.5
        if s["axis"] == 1 or (not full and not rcp): continue
        w, col = (3, INK) if full else (1, GREY)
        if s["axis"] == 0: sh.line((s["at"], s["Z"][0]), (s["at"], s["Z"][1]), col, w)
        if s["axis"] == 2: sh.line((s["X"][0], s["at"]), (s["X"][1], s["at"]), col, w)
    sh.labels = labels
    for b in m.boxes.values():
        if b.kind == "column":
            sh.rect((b.x0, b.x1), (b.z0, b.z1), INK, 1, fill=(90, 90, 90))
        else:
            sh.rect((b.x0, b.x1), (b.z0, b.z1), GREY if rcp else INK, 1, dashed=rcp)
            if not rcp:
                (tw, _), _ = cv2.getTextSize(b.name, FONT, 0.38, 1)
                x, y = sh.p(b.xc, b.zc)
                if sh.ft(b.x1 - b.x0) > tw + 4 or sh.ft(b.z1 - b.z0) > 14:
                    sh.text(b.name, 0, px=(x - tw // 2, y + 4), size=0.38, col=GREY)


def draw_geometry(sh, m, fe, col):
    t = fe["type"]
    if t == "waffle":
        (x0, x1), (z0, z1) = fe["X"], fe["Z"]; mod = fe["module"]
        nx, nz = int((x1 - x0) / mod + 0.01), int((z1 - z0) / mod + 0.01)
        ox = ((x1 - x0) - nx * mod) / 2 if fe.get("align", "start") == "centre" else 0.0
        oz = ((z1 - z0) - nz * mod) / 2 if fe.get("align", "start") == "centre" else 0.0
        sh.rect((x0, x1), (z0, z1), col, 2)
        for i in range(nx):
            for j in range(nz):
                cx, cz = x0 + ox + (i + .5) * mod, z1 - oz - (j + .5) * mod
                if fe.get("shape", "square") == "round":
                    sh.circle(cx, cz, fe.get("d", mod * .8) / 2, GREY, 1, min_px=1)
                else:
                    h = (mod - fe.get("rib", mod * .2)) / 2
                    sh.rect((cx - h, cx + h), (cz - h, cz + h), GREY, 1)
        return f"coffers {nx} x {nz}"
    if t == "cove":
        k = fe.get("kind", "recess")
        if k in ("recess", "perimeter") and "X" in fe:
            (x0, x1), (z0, z1) = fe["X"], fe["Z"]
            sh.rect((x0, x1), (z0, z1), col, 2)
            b = fe.get("border", 1.0) if k == "perimeter" else 0.5
            sh.rect((x0 + b, x1 - b), (z0 + b, z1 - b), col, 1, dashed=True)
            return "cove"
        if k == "wall" and "plane" in fe:
            s = m.surface(fe["plane"]); u0, u1 = fe["range"]; d = fe.get("depth", 1.0)
            side = 1.0 if m.C_drawing[s["axis"]] > s["at"] else -1.0
            if s["axis"] == 0: sh.rect(sorted([s["at"], s["at"] + side * d]), (u0, u1), col, 2)
            else: sh.rect((u0, u1), sorted([s["at"], s["at"] + side * d]), col, 2)
            return "wall cove"
    if t == "slats":
        (x0, x1), (z0, z1) = fe["X"], fe["Z"]; pitch = fe.get("pitch", 1.0)
        sh.rect((x0, x1), (z0, z1), col, 2)
        if fe.get("direction", "x") == "x":
            z = z0
            while z <= z1 + 1e-6: sh.line((x0, z), (x1, z), GREY, 1); z += pitch
        else:
            x = x0
            while x <= x1 + 1e-6: sh.line((x, z0), (x, z1), GREY, 1); x += pitch
        return "slats"
    if t == "lightwell":
        if fe.get("shape") == "round":
            sh.circle(fe["x"], fe["z"], fe["d"] / 2, col, 2)
            r = fe["d"] / 2 * .707
            sh.line((fe["x"] - r, fe["z"] - r), (fe["x"] + r, fe["z"] + r), col, 1)
            sh.line((fe["x"] - r, fe["z"] + r), (fe["x"] + r, fe["z"] - r), col, 1)
        else:
            (x0, x1), (z0, z1) = fe["X"], fe["Z"]
            sh.rect((x0, x1), (z0, z1), col, 2)
            sh.line((x0, z0), (x1, z1), col, 1); sh.line((x0, z1), (x1, z0), col, 1)
        return "light well"
    return None


def symbol(sh, t, x, z, col, r, note="", fe=None, m=None):
    """One light symbol at (x, z)."""
    if t in ("downlight", "fixture"):
        sh.circle(x, z, 0.5, col, 2, min_px=5); cv2.circle(sh.img, sh.p(x, z), 2, col, -1)
    elif t == "pendant":
        c, rr = sh.circle(x, z, 0.75, col, 2, min_px=6)
        d = int(rr * .7); cv2.line(sh.img, (c[0] - d, c[1] - d), (c[0] + d, c[1] + d), col, 1, cv2.LINE_AA)
        cv2.line(sh.img, (c[0] - d, c[1] + d), (c[0] + d, c[1] - d), col, 1, cv2.LINE_AA)
    elif t == "track head":
        c = sh.p(x, z); cv2.rectangle(sh.img, (c[0] - 4, c[1] - 4), (c[0] + 4, c[1] + 4), col, -1)
    elif t == "uplight":
        c, rr = sh.circle(x, z, 0.4, col, 2, min_px=5)
        cv2.ellipse(sh.img, c, (rr, rr), 0, 180, 360, col, -1, cv2.LINE_AA)
    elif t == "wallwasher":
        c, rr = sh.circle(x, z, 0.5, col, 2, min_px=5)
        cv2.circle(sh.img, c, rr + 4, col, 1, cv2.LINE_AA)
    elif t == "sconce":
        c = sh.p(x, z); cv2.circle(sh.img, c, 6, col, -1, cv2.LINE_AA); cv2.circle(sh.img, c, 9, col, 1, cv2.LINE_AA)
    elif t == "glow":
        c = sh.p(x, z)
        for a in range(0, 360, 30):
            cv2.ellipse(sh.img, c, (8, 8), 0, a, a + 15, col, 2, cv2.LINE_AA)
    elif t == "fixture3d":
        sh.circle(x, z, max(0.25, float(r) / 2), col, 2, min_px=5)
        c = sh.p(x, z); cv2.drawMarker(sh.img, c, col, cv2.MARKER_CROSS, 8, 1, cv2.LINE_AA)
    elif t == "linear_pendant":
        L = float(note.split()[0]) if note[:1].isdigit() else 4.0
        if "along X" in note: sh.rect((x - L / 2, x + L / 2), (z - .25, z + .25), col, 2)
        else: sh.rect((x - .25, x + .25), (z - L / 2, z + L / 2), col, 2)
    else:
        c = sh.p(x, z); cv2.rectangle(sh.img, (c[0] - 5, c[1] - 5), (c[0] + 5, c[1] + 5), col, 2)


def draw_light_feature(sh, m, fe, rows, col):
    """Lines and areas that a point symbol does not show (slots, track runs, washes, luminous areas)."""
    t = fe["type"]
    if t == "slots" and "X" in fe:
        (x0, x1), (z0, z1) = fe["X"], fe["Z"]; p = fe.get("pitch", 4.0); off = fe.get("offset", p / 2)
        d = fe.get("direction", "x")
        if d in ("x", "grid"):
            z = z0 + off
            while z < z1: sh.line((x0, z), (x1, z), col, 3); z += p
        if d in ("z", "grid"):
            x = x0 + off
            while x < x1: sh.line((x, z0), (x, z1), col, 3); x += p
    elif t == "luminous" and "X" in fe and "Z" in fe:
        (x0, x1), (z0, z1) = fe["X"], fe["Z"]
        ov = sh.img.copy(); cv2.rectangle(ov, sh.p(x0, z1), sh.p(x1, z0), (150, 225, 255), -1)
        sh.img[:] = cv2.addWeighted(ov, .6, sh.img, .4, 0); sh.rect((x0, x1), (z0, z1), col, 2)
        g = fe.get("grid")
        if g:
            x = x0 + g
            while x < x1 - 1e-6: sh.line((x, z0), (x, z1), col, 1); x += g
            z = z0 + g
            while z < z1 - 1e-6: sh.line((x0, z), (x1, z), col, 1); z += g
    elif t == "wash" and "plane" in fe:
        s = m.surface(fe["plane"]); u0, u1 = fe["range"]
        side = 1.0 if m.C_drawing[s["axis"]] > s["at"] else -1.0
        off = abs(fe["slot"]["offset"]) if fe.get("slot") else 1.0
        w = s["at"] + side * off
        a, b = ((w, u0), (w, u1)) if s["axis"] == 0 else ((u0, w), (u1, w))
        sh.line(a, b, col, 4 if fe.get("slot") else 2, dashed=not fe.get("slot"))
        n = max(2, int(abs(u1 - u0) / 4))
        for i in range(n + 1):                                    # arrows toward the wall
            u = u0 + (u1 - u0) * i / n
            P = (w, u) if s["axis"] == 0 else (u, w); Q = (s["at"], u) if s["axis"] == 0 else (u, s["at"])
            cv2.arrowedLine(sh.img, sh.p(*P), sh.p(*Q), col, 1, cv2.LINE_AA, tipLength=0.35)
    elif t == "track":
        heads = [r for r in rows if r["type"] == "track head"]
        for key, other in (("x", "z"), ("z", "x")):
            groups = {}
            for r in heads: groups.setdefault(round(float(r[key]), 2), []).append(float(r[other]))
            for k, vals in groups.items():
                if len(vals) < 2: continue
                vals.sort(); ext = (vals[1] - vals[0]) / 2
                a, b = vals[0] - ext, vals[-1] + ext
                sh.line((k, a), (k, b), INK, 2) if key == "x" else sh.line((a, k), (b, k), INK, 2)
    elif t == "object_light" and "box" in fe and fe["box"] in m.boxes:
        b = m.boxes[fe["box"]]
        sh.rect((b.x0 - .3, b.x1 + .3), (b.z0 - .3, b.z1 + .3), col, 2, dashed=True)
    elif t == "projection" and "at" in fe and m.surface(fe["plane"])["axis"] == 1:
        (x, z), (w, d) = fe["at"], fe.get("size", [6, 6])
        sh.rect((x - w / 2, x + w / 2), (z - d / 2, z + d / 2), col, 1, dashed=True)
        sh.text(fe.get("pattern", "pattern"), x - w / 2 + .3, z - d / 2 + .5, 0.38, col)


def viewer(sh, m, z_min):
    """Where the drawing's viewer stands, and which way they look."""
    C = m.C_drawing; R = getattr(m, "R", None)
    x, z = float(C[0]), float(C[2])
    try:
        fwd = m.R[2] if R is not None else np.array([0, 0, 1.0])
    except Exception:
        fwd = np.array([0, 0, 1.0])
    d = np.array([fwd[0], fwd[2]]); n = np.linalg.norm(d); d = d / n if n > 1e-6 else np.array([0, 1.0])
    p = sh.p(x, max(z, z_min - 1e9))
    tip = (int(p[0] + d[0] * 40), int(p[1] - d[1] * 40))
    cv2.circle(sh.img, p, 6, INK, -1, cv2.LINE_AA)
    cv2.arrowedLine(sh.img, p, tip, INK, 2, cv2.LINE_AA, tipLength=0.3)
    sh.text("VIEWER", 0, px=(p[0] + 10, p[1] + 18), size=0.4, col=INK)


def scale_bar(sh):
    step = next(s for s in (1, 2, 4, 5, 10, 20, 25, 50) if s * sh.s >= 30)
    x0, y = sh.m, sh.H - 40
    for i in range(4):
        a, b = x0 + int(i * step * sh.s), x0 + int((i + 1) * step * sh.s)
        cv2.rectangle(sh.img, (a, y), (b, y + 8), INK, -1 if i % 2 == 0 else 1)
        cv2.putText(sh.img, f"{i * step}'", (a - 4, y - 6), FONT, 0.38, INK, 1, cv2.LINE_AA)
    cv2.putText(sh.img, f"{4 * step}'", (x0 + int(4 * step * sh.s) - 6, y - 6), FONT, 0.38, INK, 1, cv2.LINE_AA)


def plan(project, rcp=False, show_all=False, design_file="design.json", out=None, title=None):
    from glowpoint import render as R
    R.render(project, design_file=design_file, linework=True, size=(240, 360), write=False)
    m_arch = Model(project)                   # the model before ceiling elements cut it
    m, feats, rows, design = R.LAST["model"], R.LAST["features"], R.LAST["report"], R.LAST["design"]
    keep = lambda y: show_all or ((y >= CEILING_MIN) if rcp else (y < CEILING_MIN))
    x0, x1, z0, z1 = bounds(m_arch)
    sh = Sheet(x0, x1, z0, z1)
    draw_architecture(sh, m_arch, rcp)
    layers = [L["name"] for L in design["layers"]]
    colour = {name: LAYER_COLOURS[i % len(LAYER_COLOURS)] for i, name in enumerate(layers)}
    legend, out_rows = [], []
    for fe in feats:
        col = colour.get(fe["layer"], INK)
        if fe["type"] in GEOMETRY_TYPES:
            if rcp or show_all:
                what = draw_geometry(sh, m, fe, col)
                if what: legend.append((fe["layer"], fe["type"], what, col))
            continue
        lrows = [r for r in rows if r.get("layer") == fe["layer"] and keep(float(r["y"]))]
        if not lrows: continue
        draw_light_feature(sh, m, fe, lrows, col)
    for name in layers:                       # point symbols on top
        lrows = [r for r in rows if r.get("layer") == name and r["type"] not in GEOMETRY_TYPES and keep(float(r["y"]))]
        if not lrows: continue
        col = colour[name]; types = sorted({r["type"] for r in lrows})
        for r in lrows:
            if r["type"] in ("wash", "slots", "luminous", "projection", "object_light", "cove"): continue
            symbol(sh, r["type"], float(r["x"]), float(r["z"]), col, r.get("size", 0.5) or 0.5, r.get("note") or "")
        legend.append((name, types[0], f"{len(lrows)} x {', '.join(types)}", col))
        out_rows += lrows
    for x, z, label in getattr(sh, "labels", []):        # ceiling heights, on a white box, last
        (tw, th), _ = cv2.getTextSize(label, FONT, 0.42, 1)
        px, py = sh.p(x, z); px -= tw // 2
        cv2.rectangle(sh.img, (px - 3, py - th - 3), (px + tw + 3, py + 4), PAPER, -1)
        sh.text(label, 0, px=(px, py), size=0.42, col=GREY)
    viewer(sh, m_arch, z0)
    scale_bar(sh)
    kind = "REFLECTED CEILING PLAN" if rcp else "FLOOR PLAN"
    sh.text((title or design.get("title") or "LIGHTING CONCEPT").upper() + "  -  " + kind, 0, px=(sh.m, 34), size=0.75, w=2)
    # legend
    lx, ly = sh.plan_right + 10, 90
    cv2.putText(sh.img, "LEGEND", (lx, ly), FONT, 0.55, INK, 2, cv2.LINE_AA); ly += 30
    seen = set()
    for name, t, what, col in legend:
        if (name, what) in seen: continue
        seen.add((name, what))
        cx, cy = lx + 12, ly - 5
        tmp = Sheet.__new__(Sheet); tmp.__dict__.update(sh.__dict__)
        tmp.p = lambda x, z, cx=cx, cy=cy: (cx, cy); tmp.ft = lambda d: 6
        if t in GEOMETRY_TYPES: cv2.rectangle(sh.img, (cx - 7, cy - 7), (cx + 7, cy + 7), col, 2)
        elif t in ("wash", "slots", "luminous", "projection", "object_light", "linear_pendant"):
            cv2.line(sh.img, (cx - 9, cy), (cx + 9, cy), col, 3)
        else: symbol(tmp, t, 0, 0, col, 0.5, "4 ft along X" if t == "linear_pendant" else "")
        cv2.putText(sh.img, name[:34], (lx + 30, ly), FONT, 0.45, INK, 1, cv2.LINE_AA)
        cv2.putText(sh.img, what[:44], (lx + 30, ly + 16), FONT, 0.38, GREY, 1, cv2.LINE_AA)
        ly += 40
    if not legend:
        cv2.putText(sh.img, "no lights in this plan", (lx, ly), FONT, 0.45, GREY, 1, cv2.LINE_AA)
    note = ("lights at 7 ft and above" if rcp else "lights below 7 ft") if not show_all else "all lights"
    cv2.putText(sh.img, note, (lx, sh.H - 40), FONT, 0.4, GREY, 1, cv2.LINE_AA)
    name = out or ("rcp.png" if rcp else "plan.png")
    os.makedirs(os.path.join(project, "out"), exist_ok=True)
    path = os.path.join(project, "out", name)
    pngmark.write(path, sh.img)
    stem = os.path.splitext(name)[0]
    with open(os.path.join(project, "out", f"positions_{stem}.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["layer", "type", "surface", "x", "y", "z", "visible", "note"], extrasaction="ignore")
        w.writeheader(); [w.writerow(r) for r in out_rows]
    print(f"{len(out_rows)} lights -> {path}")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project"); ap.add_argument("--rcp", action="store_true", help="reflected ceiling plan")
    ap.add_argument("--all", action="store_true", help="every light, at any height")
    ap.add_argument("--design", default="design.json"); ap.add_argument("--out"); ap.add_argument("--title")
    a = ap.parse_args(argv)
    plan(a.project, a.rcp, a.all, a.design, a.out, a.title)
    return 0


if __name__ == "__main__":
    sys.exit(main())
