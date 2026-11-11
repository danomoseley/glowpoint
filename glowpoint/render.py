"""Render a project:  python3 -m glowpoint.render projects/lobby [--check] [--labels]

Reads   <project>/model.json   the 3D model behind the drawing
        <project>/design.json  the lighting design (layers of features, positions as relationships)
Writes  <project>/out/concept.png    the drawing with the lighting
        <project>/out/check.png      the model on the drawing, with a grid (with --check)
        <project>/out/positions.csv  every light, with its surface and X/Y/Z in feet

Other views:  --camera view.json   use a different camera (see model.json "camera"); the model is drawn
                                   as linework because the architect's drawing only fits its own camera
              --linework           draw the model as linework with the original camera (no drawing needed)
"""
import argparse, csv, json, os
import numpy as np
import cv2
from . import pngmark
from .model import Model
from .expr import namespace, ev
from . import features as F
from . import plugins
from . import linework as LW

GEOMETRY = {"waffle": (F.waffle_prepare, F.waffle_draw)}


def evaluate(f, ns):
    return {k: (ev(v, ns) if k not in ("layer", "type", "name", "note", "plane", "slot", "fixture", "surface_name", "shape", "align") else v) for k, v in f.items()}


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


POINT_TYPES = ("downlight", "pendant", "sconce", "uplight")


def warn_overlaps(report, tol=0.5):
    """Warn when two fixtures from different features are at (almost) the same place."""
    pts = [(i, r) for i, r in enumerate(report) if r["type"] in POINT_TYPES]
    seen = set()
    for a in range(len(pts)):
        for b in range(a+1, len(pts)):
            (i, r1), (j, r2) = pts[a], pts[b]
            if r1["layer"] == r2["layer"] and r1["type"] == r2["type"]: continue
            if abs(r1["x"]-r2["x"]) < tol and abs(r1["z"]-r2["z"]) < tol and \
               (r1["type"] in ("downlight", "pendant")) == (r2["type"] in ("downlight", "pendant")):
                key = (r1["layer"], r1["type"], r2["layer"], r2["type"])
                if key in seen: continue
                seen.add(key)
                print(f"warning: {r1['type']} ({r1['layer']}) and {r2['type']} ({r2['layer']}) are at the same place, "
                      f"x {r1['x']}, z {r1['z']} (and maybe more)")


def render(project, check=False, out_name="concept.png", design_file="design.json", camera=None, linework=False,
           size=None):
    m = Model(project)
    dpath = os.path.join(project, design_file)
    if os.path.exists(dpath):
        design = json.load(open(dpath))
    elif design_file == "design.json":
        design = {"layers": [], "legend": False}          # new project: check the model before any design
        print(f"note: {dpath} not found; rendering the model with no lights")
    else:
        raise FileNotFoundError(dpath)
    has_drawing = os.path.exists(m.drawing)
    if has_drawing and pngmark.is_marked(m.drawing):
        raise ValueError(f"{m.drawing} is an image that glowpoint made (it already has lights or coffers drawn on it). "
                         "Use the architect's original drawing as drawing.png. Outputs are in out/.")
    base = None if (camera or linework or not has_drawing) else cv2.imread(m.drawing)
    if base is None and not (camera or linework):
        raise FileNotFoundError(f"{m.drawing} not found. Add the drawing, or use --linework to draw the model.")
    # "visible" in the design always means visible in the architect's drawing, whatever view is rendered
    ref = cv2.imread(m.drawing) if has_drawing else None; ref_shape = ref.shape[:2] if ref is not None else (700, 1050)
    ref_ids = m.raycast(ref_shape)[0]
    if camera:
        m.set_camera(camera)
    if base is None:
        shape = tuple(size) if size else ref_shape
        base = LW.draw(m, shape)
    os.makedirs(os.path.join(project, "out"), exist_ok=True)
    stem = os.path.splitext(out_name)[0]
    suffix = "" if out_name == "concept.png" else "_" + stem       # each view keeps its own check and positions files
    if check:
        pngmark.write(os.path.join(project, "out", f"check{suffix}.png"), check_image(m, base))

    layers = design["layers"]
    lights, geometry, helper_factories, loaded = plugins.load(project, F.LIGHTS, GEOMETRY)
    for path in loaded: print(f"loaded plugin {path}")
    extra = lambda: {k: v for h in helper_factories for k, v in h(m).items()}
    ns = namespace(m); ns.update(extra())
    # 1. architecture that changes the model (waffle ceilings): evaluate and cut holes before ray casting
    geo = []
    for L in layers:
        for f in L["features"]:
            if f["type"] in geometry:
                fe = evaluate(f, ns); fe["layer"] = L["name"]; geometry[f["type"]][0](m, fe); geo.append(fe)
    cv = F.Canvas(m, base); cv.raycast()
    cv.fixtures = {}
    fx_file = os.path.join(project, "fixtures.json")
    if os.path.exists(fx_file): cv.fixtures.update(json.load(open(fx_file)))
    cv.fixtures.update(design.get("fixtures", {}))
    cv.fixtures = {k: v for k, v in cv.fixtures.items() if not k.startswith("_")}
    for fe in geo:
        base = geometry[fe["type"]][1](cv, fe, base)
    cv.img = base.copy(); cv.over = base.copy()
    # 2. lights: may refer to what is visible
    vis = [(s, int((ref_ids == i).sum())) if i < ref_ids.max()+1 else (s, 0) for i, s in enumerate(m.surfaces)]
    ns = namespace(m, visible=vis); ns.update(extra())
    waffles = {fe.get("name", "Waffle"): fe for fe in geo if fe["type"] == "waffle"}

    def coffers(name="Waffle", axis="x"):
        """Centres of the full coffers of a waffle: axis 'x' or 'z' gives a list, 'y' the coffer top height."""
        if name not in waffles: raise KeyError(f"No waffle named '{name}'. Known: {sorted(waffles)}")
        w = waffles[name]; (x0, x1), (z0, z1) = w["X"], w["Z"]; mod = w["module"]
        nx, nz = int((x1-x0)/mod + 0.01), int((z1-z0)/mod + 0.01)
        ox = ((x1-x0) - nx*mod)/2 if w.get("align", "start") == "centre" else 0.0
        oz = ((z1-z0) - nz*mod)/2 if w.get("align", "start") == "centre" else 0.0
        if axis == "x": return [x0 + ox + (i+0.5)*mod for i in range(nx)]
        if axis == "z": return [z1 - oz - (j+0.5)*mod for j in range(nz)]
        if axis == "y": return m.surface(w.get("plane", "Ceiling"))["at"] + w["depth"]
        raise ValueError("axis must be 'x', 'z' or 'y'")
    ns["coffers"] = coffers
    for L in layers:
        for f in L["features"]:
            if f["type"] in geometry: continue
            fe = evaluate(f, ns); fe["layer"] = L["name"]
            if f["type"] not in lights:
                raise ValueError(f"Unknown type '{f['type']}'. Known: {sorted(lights) + sorted(geometry)}. "
                                 f"Add new types in {project}/types/ or a GLOWPOINT_TYPES folder.")
            lights[f["type"]](cv, fe)
    warn_overlaps(cv.report)
    img = cv.finish()
    if design.get("legend", True):
        img = legend(img, design.get("title", "LIGHTING CONCEPT"), [(L["name"], L.get("description", "")) for L in layers])
    pngmark.write(os.path.join(project, "out", out_name), img)
    with open(os.path.join(project, "out", f"positions{suffix}.csv"), "w", newline="") as fh:
        keys = ["layer", "type", "surface", "x", "y", "z", "visible", "note"]
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore"); w.writeheader()
        for r in cv.report: w.writerow(r)
    return cv.report


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project"); ap.add_argument("--check", action="store_true", help="also write out/check.png")
    ap.add_argument("--design", default="design.json"); ap.add_argument("--out", default="concept.png")
    ap.add_argument("--camera", help="JSON file with a camera, for a new view (path from the current folder). "
                    "Outputs are named after --out: check_<out>.png, positions_<out>.csv")
    ap.add_argument("--linework", action="store_true", help="draw the model as linework, not on the drawing")
    a = ap.parse_args()
    cam = json.load(open(a.camera)) if a.camera else None
    rep = render(a.project, a.check, a.out, a.design, cam, a.linework)
    print(f"{len(rep)} items -> {os.path.join(a.project, 'out', a.out)}")
