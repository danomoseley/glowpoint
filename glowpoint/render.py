"""Render a project:  python3 -m glowpoint.render projects/lobby [--check] [--labels]

Reads   <project>/model.json   the 3D model behind the drawing
        <project>/design.json  the lighting design (layers of features, positions as relationships)
Writes  <project>/out/concept.png    the drawing with the lighting
        <project>/out/check.png      the model on the drawing, with a grid (with --check)
        <project>/out/positions.csv  every light, with its surface and X/Y/Z in feet
"""
import argparse, csv, json, os
import numpy as np
import cv2
from .model import Model
from .expr import namespace, ev
from . import features as F

GEOMETRY = {"waffle": (F.waffle_prepare, F.waffle_draw)}


def evaluate(f, ns):
    return {k: (ev(v, ns) if k not in ("layer", "type", "name", "note", "plane", "slot") else v) for k, v in f.items()}


def legend(img, title, layers, at="bottom-left"):
    lines = [title] + [f"{i+1}  {name} - {desc}" if desc else f"{i+1}  {name}" for i, (name, desc) in enumerate(layers)]
    w = max(cv2.getTextSize(t, 0, 0.42, 1)[0][0] for t in lines) + 16
    h = 18*len(lines) + 12
    H, W = img.shape[:2]; x0, y0 = 12, H - h - 12
    ov = img.copy(); cv2.rectangle(ov, (x0, y0), (x0+w, y0+h), (255, 255, 255), -1)
    img = cv2.addWeighted(ov, 0.88, img, 0.12, 0)
    cv2.rectangle(img, (x0, y0), (x0+w, y0+h), (0, 0, 0), 1)
    for i, t in enumerate(lines):
        cv2.putText(img, t, (x0+8, y0+18+18*i), 0, 0.42 if i else 0.47, (0, 0, 0), 1, cv2.LINE_AA)
    return img


def check_image(m, base, step=4.0):
    ids, P, _ = m.raycast(base.shape[:2])
    pal = [(66, 135, 245), (245, 135, 66), (60, 180, 75), (200, 80, 200), (230, 50, 50), (0, 170, 200), (150, 120, 40), (120, 120, 120)]
    out = base.astype(float); groups = {}
    for i, s in enumerate(m.surfaces):
        if (ids == i).any(): groups.setdefault(s.get("box", s["name"]), []).append(i)
    tint = np.zeros_like(out); grid = np.zeros(ids.shape, bool)
    for gi, (key, lst) in enumerate(groups.items()):
        col = np.array(pal[gi % len(pal)], float)
        for i in lst:
            msk = ids == i; tint[msk] = col; a = m.surfaces[i]["axis"]
            for k in range(3):
                if k == a: continue
                u = P[..., k]; gy, gx = np.gradient(u); g = np.hypot(gx, gy)
                grid |= msk & (np.abs(u-np.round(u/step)*step) < 0.75*g) & (g < step/2)
    msk = ids >= 0
    out[msk] = out[msk]*0.78 + tint[msk]*0.22
    out[grid] = tint[grid]*0.85
    out[cv2.Canny((ids+1).astype(np.uint8)*7, 1, 1) > 0] = (40, 40, 40)
    out = out.clip(0, 255).astype(np.uint8)
    for key, lst in groups.items():
        k = np.isin(ids, lst[:1]);  k = k if k.sum() >= 300 else np.isin(ids, lst)
        if k.sum() < 300: continue
        ys, xs = np.nonzero(k); cy, cx = int(np.median(ys)), int(np.median(xs))
        if not k[cy, cx]:
            j = np.argmin((ys-cy)**2+(xs-cx)**2); cy, cx = ys[j], xs[j]
        (tw, th), _ = cv2.getTextSize(key, 0, 0.5, 1)
        cv2.rectangle(out, (cx-tw//2-4, cy-th-6), (cx+tw//2+4, cy+4), (255, 255, 255), -1)
        cv2.putText(out, key, (cx-tw//2, cy), 0, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(out, f"Grid = {step:g} ft   Eye height {m.h:.1f} ft", (10, out.shape[0]-10), 0, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    return out


def render(project, check=False, out_name="concept.png", design_file="design.json"):
    m = Model(project)
    design = json.load(open(os.path.join(project, design_file)))
    base = cv2.imread(m.drawing)
    if base is None: raise FileNotFoundError(m.drawing)
    os.makedirs(os.path.join(project, "out"), exist_ok=True)
    if check:
        cv2.imwrite(os.path.join(project, "out", "check.png"), check_image(m, base))

    layers = design["layers"]
    ns = namespace(m)
    # 1. architecture that changes the model (waffle ceilings): evaluate and cut holes before ray casting
    geo = []
    for L in layers:
        for f in L["features"]:
            if f["type"] in GEOMETRY:
                fe = evaluate(f, ns); fe["layer"] = L["name"]; GEOMETRY[f["type"]][0](m, fe); geo.append(fe)
    cv = F.Canvas(m, base); cv.raycast()
    for fe in geo:
        base = GEOMETRY[fe["type"]][1](cv, fe, base)
    cv.img = base.copy(); cv.over = base.copy()
    # 2. lights: may refer to what is visible
    vis = [(s, int((cv.ids == i).sum())) for i, s in enumerate(m.surfaces)]
    ns = namespace(m, visible=vis)
    for L in layers:
        for f in L["features"]:
            if f["type"] in GEOMETRY: continue
            fe = evaluate(f, ns); fe["layer"] = L["name"]
            if f["type"] not in F.LIGHTS: raise ValueError(f"Unknown type '{f['type']}'. Known: {sorted(F.LIGHTS)}")
            F.LIGHTS[f["type"]](cv, fe)
    img = cv.finish()
    if design.get("legend", True):
        img = legend(img, design.get("title", "LIGHTING CONCEPT"), [(L["name"], L.get("description", "")) for L in layers])
    cv2.imwrite(os.path.join(project, "out", out_name), img)
    with open(os.path.join(project, "out", "positions.csv"), "w", newline="") as fh:
        keys = ["layer", "type", "surface", "x", "y", "z", "visible", "note"]
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore"); w.writeheader()
        for r in cv.report: w.writerow(r)
    return cv.report


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project"); ap.add_argument("--check", action="store_true", help="also write out/check.png")
    ap.add_argument("--design", default="design.json"); ap.add_argument("--out", default="concept.png")
    a = ap.parse_args()
    rep = render(a.project, a.check, a.out, a.design)
    print(f"{len(rep)} items -> {os.path.join(a.project, 'out', a.out)}")
