"""Render test for the lobby test fixture (tests/fixtures/lobby).

  python3 tests/test_render.py            check
  python3 tests/test_render.py --update   accept the current result as the new reference (after an intended change)

Three checks, from strict to loose:
  1. positions: every light's type, surface and X/Y/Z match tests/reference/lobby_positions.csv (0.01 ft)
  2. geometry:  the surface seen at each pixel matches the reference (pure numpy, same on all OpenCV versions)
  3. image:     the linework image is close to tests/reference/lobby_linework.png. Text and soft edges are drawn
                a little differently by different OpenCV versions, so this check allows small differences.
"""
import csv, json, os, shutil, sys, tempfile
import numpy as np
import cv2
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from glowpoint.render import render
from glowpoint.model import Model

REF_DIR = os.path.join(ROOT, "tests", "reference")
REF_IMG = os.path.join(REF_DIR, "lobby_linework.png")
REF_POS = os.path.join(REF_DIR, "lobby_positions.csv")
REF_IDS = os.path.join(REF_DIR, "lobby_surface_ids.npz")
IMAGE_LIMIT = 3.0        # percent of pixels that may differ after a small blur


def surface_ids(proj):
    m = Model(proj)
    ids = m.raycast((700, 1050))[0]
    names = np.array([s["name"] for s in m.surfaces])
    return np.where(ids >= 0, names[np.clip(ids, 0, None)], "")


def main(update=False):
    tmp = tempfile.mkdtemp(prefix="glowpoint_render_")
    proj = os.path.join(tmp, "lobby")
    shutil.copytree(os.path.join(ROOT, "tests", "fixtures", "lobby"), proj, ignore=shutil.ignore_patterns("out", "drawing.*"))
    render(proj, linework=True, out_name="linework.png")
    img = cv2.imread(os.path.join(proj, "out", "linework.png"))
    pos = list(csv.DictReader(open(os.path.join(proj, "out", "positions_linework.csv"))))
    ids = surface_ids(proj)
    if update:
        cv2.imwrite(REF_IMG, img)
        shutil.copy(os.path.join(proj, "out", "positions_linework.csv"), REF_POS)
        np.savez_compressed(REF_IDS, ids=ids)
        print(f"references updated in {REF_DIR}"); return True
    ok = True
    # 1. positions
    ref = list(csv.DictReader(open(REF_POS)))
    bad = [] if len(ref) == len(pos) else [f"{len(pos)} items, expected {len(ref)}"]
    for a, b in zip(pos, ref):
        if (a["layer"], a["type"], a["surface"]) != (b["layer"], b["type"], b["surface"]) or \
           max(abs(float(a[k]) - float(b[k])) for k in "xyz") > 0.01:
            bad.append(f"{a['type']} on {a['surface']}: {a['x']},{a['y']},{a['z']} (expected {b['x']},{b['y']},{b['z']})")
    print(f"{'PASS' if not bad else 'FAIL'}  positions: {len(pos)} items" + ("" if not bad else "\n      " + "\n      ".join(bad[:5])))
    ok &= not bad
    # 2. geometry
    ref_ids = np.load(REF_IDS)["ids"]
    share = (ids != ref_ids).mean()*100
    good = share < 0.01
    print(f"{'PASS' if good else 'FAIL'}  geometry: {share:.3f}% of pixels see a different surface (limit 0.01%)")
    ok &= good
    # 3. image
    ref_img = cv2.imread(REF_IMG)
    if ref_img is None or ref_img.shape != img.shape:
        print("FAIL  image: reference missing or a different size"); return False
    a = cv2.GaussianBlur(img, (3, 3), 0).astype(int); b = cv2.GaussianBlur(ref_img, (3, 3), 0).astype(int)
    diff = np.abs(a - b).max(2) > 60
    share = diff.mean()*100
    good = share < IMAGE_LIMIT
    print(f"{'PASS' if good else 'FAIL'}  image: {share:.3f}% of pixels differ from the reference (limit {IMAGE_LIMIT}%, "
          f"OpenCV {cv2.__version__})")
    if not good:
        cv2.imwrite(os.path.join(tmp, "diff.png"), diff.astype(np.uint8)*255)
        print(f"      result {os.path.join(proj, 'out', 'linework.png')}, differences {os.path.join(tmp, 'diff.png')}")
    ok &= good
    # 4. coffers() and the fixture type: one fixture in every full coffer (14 x 30 in the lobby)
    d = json.load(open(os.path.join(proj, "design.json")))
    d["fixtures"] = json.load(open(os.path.join(ROOT, "examples", "fixtures.json")))
    d["layers"].append({"name": "Coffer fixtures", "features": [{"type": "fixture", "fixture": "round-12in-downlight",
        "x": "coffers('Waffle', 'x')", "z": "coffers('Waffle', 'z')", "y": "coffers('Waffle', 'y')"}]})
    json.dump(d, open(os.path.join(proj, "design.coffers.json"), "w"))
    rep = render(proj, linework=True, out_name="coffers.png", design_file="design.coffers.json")
    fx = [r for r in rep if r["type"] == "fixture"]
    good = len(fx) == 420 and len({r["x"] for r in fx}) == 14 and sum(bool(r["visible"]) for r in fx) > 50
    print(f"{'PASS' if good else 'FAIL'}  coffer fixtures: {len(fx)} (expected 420 = 14 x 30), "
          f"{sum(bool(r['visible']) for r in fx)} visible")
    ok &= good
    # 5. round coffers, centred: 11 x 25 full coffers of 24 in in the lobby waffle area
    w = d["layers"][0]["features"][0]
    w.update({"shape": "round", "module": "inch(24)", "d": "inch(18)", "depth": "inch(6)", "align": "centre"})
    json.dump(d, open(os.path.join(proj, "design.round.json"), "w"))
    rep = render(proj, linework=True, out_name="round.png", design_file="design.round.json")
    fx = [r for r in rep if r["type"] == "fixture"]
    xs = sorted({r["x"] for r in fx}); (x0, x1) = (-5.32, 18.01)
    centred = abs((xs[0] - x0) - (x1 - xs[-1])) < 0.02
    good = len(fx) == 275 and len(xs) == 11 and centred
    print(f"{'PASS' if good else 'FAIL'}  round coffers: {len(fx)} fixtures (expected 275 = 11 x 25), "
          f"centred: {centred} (left {xs[0]-x0:.2f} ft, right {x1-xs[-1]:.2f} ft)")
    ok &= good
    # 6. pendants hanging from the coffer tops (from_y), with list slices
    d["layers"].append({"name": "Coffer pendants", "features": [{"type": "pendant", "from_y": "coffers('Waffle', 'y')",
        "x": "coffers('Waffle', 'x')[1::2]", "z": "coffers('Waffle', 'z')[::3]", "y": 14}]})
    json.dump(d, open(os.path.join(proj, "design.pendants.json"), "w"))
    rep = render(proj, linework=True, out_name="pendants.png", design_file="design.pendants.json")
    pd = [r for r in rep if r["type"] == "pendant"]
    good = len(pd) == 45 and all(r["surface"] == "y=24.858" and r["y"] == 14 for r in pd)
    print(f"{'PASS' if good else 'FAIL'}  coffer pendants: {len(pd)} (expected 45 = 5 x 9), from the coffer tops at 24.86 ft")
    ok &= good
    # 7. coves, slats and a luminous ceiling
    d2 = json.load(open(os.path.join(proj, "design.json")))
    d2["layers"][0] = {"name": "Cove", "features": [{"type": "cove", "kind": "recess", "plane": "Ceiling",
        "X": "inset(gap('Column L1', 'Column R1'), 3)", "Z": "(surf('Ceiling').Z[0], centre_line('Column L1', 'Column R1', 'Z'))", "depth": 1.0}]}
    d2["layers"] += [
        {"name": "Wall cove", "features": [{"type": "cove", "kind": "wall", "name": "Right cove", "plane": "Right wall",
            "range": [40, 105], "y": 14, "depth": 1.0, "ceiling": "Ceiling"}]},
        {"name": "Slats", "features": [{"type": "slats", "X": "(surf('Soffit step').at, -5.32)", "Z": "(surf('Ceiling').Z[0], surf('Back wall').at)",
            "y": 20, "h": "inch(6)", "w": "inch(3)", "pitch": 1.0, "direction": "x", "backlit": True}]},
        {"name": "Luminous", "features": [{"type": "luminous", "plane": "Ceiling", "X": [29, 37], "Z": [62, 100], "grid": 2.0}]}]
    json.dump(d2, open(os.path.join(proj, "design.arch.json"), "w"))
    rep = render(proj, linework=True, out_name="arch.png", design_file="design.arch.json")
    kinds = {r["type"]: r for r in rep}
    slat = next((r for r in rep if r["type"] == "slats"), None)
    lum = next((r for r in rep if r["type"] == "luminous"), None)
    coves = [r for r in rep if r["type"] == "cove"]
    good = len(coves) == 2 and slat is not None and slat["note"].startswith("107 slats") and lum is not None \
        and lum["note"].startswith("304.0 sq ft")
    print(f"{'PASS' if good else 'FAIL'}  coves, slats, luminous: {len(coves)} coves, "
          f"{slat['note'][:20] if slat else 'no slats'}, {lum['note'] if lum else 'no luminous'}")
    ok &= good
    return ok


if __name__ == "__main__":
    sys.exit(0 if main("--update" in sys.argv) else 1)
