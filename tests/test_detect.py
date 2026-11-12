"""Coffer detection test with known answers.

Draws the lobby test fixture as linework with known coffers (unlit, no lights), saves it as the drawing,
runs glowpoint.detect, and compares the result with the truth. Cases: square coffers in the original
one-point view, round coffers, and square coffers in a two-point view.

  python3 tests/test_detect.py
"""
import json, os, shutil, sys, tempfile
import numpy as np
import cv2
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from glowpoint.render import render
from glowpoint.model import Model
from glowpoint.detect import detect_coffers

W = {"type": "waffle", "plane": "Ceiling", "X": "inset(gap('Column L1', 'Column R1'), 3)",
     "Z": "(surf('Ceiling').Z[0], centre_line('Column L1', 'Column R1', 'Z'))", "depth": "inch(6)", "lit": False}
CASES = [
    ("square, one-point view", dict(module="inch(20)", rib="inch(4)"), None),
    ("round, one-point view", dict(shape="round", module="inch(24)", d="inch(18)", align="centre"), None),
    ("square, two-point view", dict(module="inch(24)", rib="inch(6)"),
     {"f": 620, "principal": [525, 350], "position": [-14, 5.5, 14], "yaw": 30, "pitch": 18, "roll": 0}),
]


def make_case(tmp, name, extra, camera):
    proj = os.path.join(tmp, name.replace(" ", "_").replace(",", ""))
    shutil.copytree(os.path.join(ROOT, "tests", "fixtures", "lobby"), proj, ignore=shutil.ignore_patterns("out", "drawing.*"))
    if camera:
        mj = json.load(open(os.path.join(proj, "model.json"))); mj["camera"] = camera
        json.dump(mj, open(os.path.join(proj, "model.json"), "w"))
    w = dict(W); w.update(extra)
    json.dump({"legend": False, "layers": [{"name": "W", "features": [w]}]}, open(os.path.join(proj, "design.json"), "w"))
    rep = render(proj, linework=True, out_name="truth.png")
    truth = next(r for r in rep if r["type"] == "waffle")
    cv2.imwrite(os.path.join(proj, "drawing.png"), cv2.imread(os.path.join(proj, "out", "truth.png")))   # an unmarked copy
    os.remove(os.path.join(proj, "design.json"))
    return proj, w, truth


def main():
    ok = True; tmp = tempfile.mkdtemp(prefix="glowpoint_detect_")
    for name, extra, camera in CASES:
        proj, w, truth = make_case(tmp, name, extra, camera)
        m = Model(proj); img = cv2.imread(m.drawing)
        try:
            got = detect_coffers(m, img)
        except Exception as e:
            print(f"FAIL  {name}: {e}"); ok = False; continue
        tmod = {"inch(20)": 20, "inch(24)": 24}[extra["module"]]/12
        shape = extra.get("shape", "square")
        # true area of full coffers, from the render note ("X a..b, Z c..d, ...")
        note = truth["note"]; tx = [float(v) for v in note.split("X ")[1].split(",")[0].split("..")]
        tz = [float(v) for v in note.split("Z ")[1].split(",")[0].split("..")]
        nx_t = int(note.split(", ")[2].split(" x ")[0]); nz_t = int(note.split(" x ")[1].split(" ")[0])
        if shape == "square":                                  # only full coffers can be detected
            tx = [tx[0], tx[0] + nx_t*tmod]
        if shape == "round" and extra.get("align") == "centre":
            ox = ((tx[1]-tx[0]) - nx_t*tmod)/2; oz = ((tz[1]-tz[0]) - nz_t*tmod)/2
            tx = [tx[0]+ox, tx[1]-ox]; tz = [tz[0]+oz, tz[1]-oz]
        nx = int(round((got["X"][1]-got["X"][0])/got["module"])); nz = int(round((got["Z"][1]-got["Z"][0])/got["module"]))
        size_ok = (abs(got.get("rib", 0) - {"inch(4)": 4, "inch(6)": 6}.get(extra.get("rib"), 0)/12) < 2/12) if shape == "square" \
            else abs(got["d"] - 1.5) < 2/12
        # the visible part must match; parts out of view may be extended
        x_ok = abs(got["X"][0]-tx[0]) < 0.3*tmod and abs(got["X"][1]-tx[1]) < 0.3*tmod
        z_ok = abs(got["Z"][1]-tz[1]) < 0.3*tmod
        good = got["shape"] == shape and abs(got["module"]-tmod)/tmod < 0.02 and size_ok and x_ok and z_ok and nx == nx_t
        ok &= good
        size = f"rib {got['rib']*12:.1f} in" if got["shape"] == "square" else f"d {got['d']*12:.1f} in"
        print(f"{'PASS' if good else 'FAIL'}  {name}: {got['shape']} (true {shape}), module {got['module']*12:.2f} in "
              f"(true {tmod*12:.0f}), {size}, {nx} x {nz} coffers (true {nx_t} x {nz_t}), "
              f"X {got['X'][0]:.2f}..{got['X'][1]:.2f} (true {tx[0]:.2f}..{tx[1]:.2f}), far Z {got['Z'][1]:.2f} (true {tz[1]:.2f})")
    print(f"test projects in {tmp}")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
