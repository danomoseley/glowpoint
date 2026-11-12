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
    check(os.path.exists(os.path.join(a, "out", "positions_saved.csv")) and not os.path.exists(os.path.join(a, "glowpoint-project.json")),
          "the saved light list is kept, and no manifest in the project")
    import io, contextlib, json, zipfile
    out = io.StringIO()
    with contextlib.redirect_stdout(out): b = P.restore(z, dest)
    check("same lights as when it was saved" in out.getvalue() and "version: same" in out.getvalue(), "restore reports the same version and the same lights")
    check("LED strip [linear_strip, this project]" in out.getvalue() and "round-12in-downlight [this project]" in out.getvalue(),
          "restore lists the project's own types and fixtures by name")
    check(os.path.basename(b) == "lobby-2" and os.path.exists(os.path.join(a, "model.json")), "a second restore does not overwrite the first")
    check(open(os.path.join(a, "out", "positions.csv")).read() == open(os.path.join(proj, "out", "positions.csv")).read(),
          "the restored project renders the same lights")
    check([P.version_status(v) for v in ("0.0.1", "99.0.0", P._version(), "x")] == ["older", "newer", "same", "unknown"], "version status")
    # a saved light list that differs (as from another version) is reported
    z2 = os.path.join(t, "changed.zip")
    with zipfile.ZipFile(z, "r") as zi, zipfile.ZipFile(z2, "w") as zo:
        for n in zi.namelist():
            data = zi.read(n)
            if n.endswith("out/positions.csv"): data = b"\n".join(data.split(b"\n")[:-3]) + b"\n"
            if n.endswith("glowpoint-project.json"):
                info = json.loads(data); info["glowpoint"] = "99.0.0"; data = json.dumps(info).encode()
            zo.writestr(n, data)
    out = io.StringIO()
    with contextlib.redirect_stdout(out): P.restore(z2, dest)
    check("WARNING version" in out.getvalue() and "the lights differ" in out.getvalue(), "restore warns about a newer version and changed lights")

    # the menu list shows custom types from the other projects in the session
    other = os.path.join(dest, "jones"); os.makedirs(other)
    shutil.copy(os.path.join(ROOT, "tests/fixtures/lobby/model.json"), other)
    from glowpoint.plugins import catalog
    lines = catalog(other)
    check(any("In your other projects" in l for l in lines) and any("LED strip [linear_strip] in lobby" in l for l in lines),
          "the menu list shows custom types from other projects, with how to ask for them")

sys.exit(1 if fails else 0)
