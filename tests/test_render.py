"""Render test: draws the lobby test fixture (tests/fixtures/lobby) as linework and compares it with tests/reference/lobby_linework.png.

  python3 tests/test_render.py            check
  python3 tests/test_render.py --update   accept the current result as the new reference (after an intended change)

Also checks that positions.csv has the expected number of lights.
"""
import csv, os, shutil, sys, tempfile
import numpy as np
import cv2
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from glowpoint.render import render

REF = os.path.join(ROOT, "tests", "reference", "lobby_linework.png")
EXPECTED_ITEMS = 29


def main(update=False):
    tmp = tempfile.mkdtemp(prefix="glowpoint_render_")
    proj = os.path.join(tmp, "lobby")
    shutil.copytree(os.path.join(ROOT, "tests", "fixtures", "lobby"), proj, ignore=shutil.ignore_patterns("out", "drawing.*"))
    rep = render(proj, linework=True, out_name="linework.png")
    img = cv2.imread(os.path.join(proj, "out", "linework.png"))
    if update:
        cv2.imwrite(REF, img); print(f"reference updated: {REF}"); return True
    ref = cv2.imread(REF)
    ok = True
    if ref is None or ref.shape != img.shape:
        print("FAIL  reference missing or a different size"); return False
    diff = np.abs(img.astype(int) - ref.astype(int)).max(2) > 40
    share = diff.mean() * 100
    good = share < 0.1
    ok &= good
    print(f"{'PASS' if good else 'FAIL'}  lobby linework: {share:.3f}% of pixels differ from the reference (limit 0.1%)")
    if not good:
        cv2.imwrite(os.path.join(tmp, "diff.png"), diff.astype(np.uint8)*255)
        print(f"      result {os.path.join(proj, 'out', 'linework.png')}, differences {os.path.join(tmp, 'diff.png')}")
    rows = list(csv.DictReader(open(os.path.join(proj, "out", "positions_linework.csv"))))
    good = len(rows) == EXPECTED_ITEMS
    ok &= good
    print(f"{"PASS" if good else "FAIL"}  positions_linework.csv: {len(rows)} items (expected {EXPECTED_ITEMS})")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main("--update" in sys.argv) else 1)
