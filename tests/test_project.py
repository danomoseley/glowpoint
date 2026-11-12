"""Test glowpoint.project: save a project with a plugin and a drawing, restore it twice, render the copy.

  python3 tests/test_project.py
"""
import os, shutil, sys, tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from glowpoint import project as P
from glowpoint.render import render

fails = 0
def check(ok, msg):
    global fails
    print(("PASS " if ok else "FAIL ") + msg); fails += 0 if ok else 1


with tempfile.TemporaryDirectory() as t:
    proj = os.path.join(t, "lobby"); shutil.copytree(os.path.join(ROOT, "tests/fixtures/lobby"), proj)
    os.makedirs(os.path.join(proj, "types")); shutil.copy(os.path.join(ROOT, "examples/types/linear_strip.py"), os.path.join(proj, "types"))
    shutil.copy(os.path.join(ROOT, "examples/fixtures.json"), proj)
    render(proj, linework=True)
    z = P.save(proj, os.path.join(t, "lobby-backup.zip"))
    dest = os.path.join(t, "local"); os.makedirs(dest)
    a = P.restore(z, dest)
    want = ["model.json", "design.json", "fixtures.json", "types/linear_strip.py", "out/concept.png"]
    check(all(os.path.exists(os.path.join(a, w)) for w in want), "restore has the model, design, fixtures, plugin and last image")
    check(not os.path.exists(os.path.join(a, "out", "positions.csv")) and not os.path.exists(os.path.join(a, "glowpoint-project.json")),
          "only images from out/, and no manifest in the project")
    b = P.restore(z, dest)
    check(os.path.basename(b) == "lobby-2" and os.path.exists(os.path.join(a, "model.json")), "a second restore does not overwrite the first")
    render(a, linework=True)
    check(open(os.path.join(a, "out", "positions.csv")).read() == open(os.path.join(proj, "out", "positions.csv")).read(),
          "the restored project renders the same lights")

sys.exit(1 if fails else 0)
