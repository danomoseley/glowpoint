"""Test glowpoint.patch: make a patch in a copy without git, then apply it to a clean copy three ways.

  python3 tests/test_patch.py
"""
import io, os, re, shutil, subprocess, sys, tempfile, zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from glowpoint import patch as P

fails = 0
def check(ok, msg):
    global fails
    print(("PASS " if ok else "FAIL ") + msg); fails += 0 if ok else 1


def copy(dst):
    for rel, src in P.tracked_files(ROOT).items():
        p = os.path.join(dst, rel); os.makedirs(os.path.dirname(p), exist_ok=True); shutil.copy2(src, p)
    return dst


def edit(root):
    with open(os.path.join(root, "glowpoint/expr.py"), "a") as fh: fh.write("# patch test\n")
    with open(os.path.join(root, "glowpoint/new_helper.py"), "w") as fh: fh.write("X = 1\nY = 2")   # no final newline
    os.remove(os.path.join(root, "examples/fixtures.json"))
    v = os.path.join(root, "glowpoint/__init__.py"); txt = open(v).read()      # a session raises the version
    open(v, "w").write(re.sub(r'"(\d+)\.(\d+)\.(\d+)"', lambda m: f'"{m[1]}.{int(m[2]) + 1}.0"', txt))
    c = os.path.join(root, "CHANGELOG.md"); txt = open(c).read()
    open(c, "w").write(txt.replace("\n## ", "\n## 9.9.9 — test\n- Session change line.\n\n## ", 1))


def same(a, b, rels):
    return all(os.path.exists(os.path.join(a, r)) == os.path.exists(os.path.join(b, r)) and
               (not os.path.exists(os.path.join(a, r)) or open(os.path.join(a, r), "rb").read() == open(os.path.join(b, r), "rb").read())
               for r in rels)


RELS = ["glowpoint/expr.py", "glowpoint/new_helper.py", "examples/fixtures.json"]
with tempfile.TemporaryDirectory() as t:
    a = copy(os.path.join(t, "a"))
    P.save_baseline(a, quiet=True)
    base, desc = P.load_base(a)
    check(desc == "local/.baseline" and P.changes(a, base) == ([], [], []), "baseline: no changes at the start")
    edit(a)
    ch, ad, rm = P.changes(a, P.load_base(a)[0])
    ch = [r for r in ch if r not in ("glowpoint/__init__.py", "CHANGELOG.md")]
    check((ch, ad, rm) == (["glowpoint/expr.py"], ["glowpoint/new_helper.py"], ["examples/fixtures.json"]), "status finds changed, added and removed files")
    path = P.make(a, "Patch test", "because", tests=False)
    text = open(path).read()
    check(text.startswith("Subject: Patch test") and "Why:\nbecause" in text and "diff --git a/glowpoint/expr.py" in text, "patch header and diff")
    body = text.split("\n---\n", 1)[1]
    check("glowpoint/__init__.py" not in body and "CHANGELOG.md" not in body, "the version and CHANGELOG.md are not in the patch")
    check("- Session change line." in text.split("\n---\n")[0], "the changelog line is in the header")
    check("local/" not in text.split("---\n", 1)[1].split("diff --git")[0] and "local/.baseline/" not in "".join(l for l in text.splitlines(True) if l.startswith("diff")), "user files are not in the patch")

    b = copy(os.path.join(t, "b")); check(P.apply(b, path) and same(a, b, RELS), "apply (git apply or patch) gives the same files")
    c = copy(os.path.join(t, "c")); probs = P._py_apply(c, text)
    check(not probs and same(a, c, RELS), "built-in applier gives the same files")
    check(bool(P._py_apply(c, text, check=True)), "built-in applier refuses a patch that is already applied")

    zbuf = os.path.join(t, "glowpoint-main.zip")
    with zipfile.ZipFile(zbuf, "w") as z:
        for rel, src in P.tracked_files(ROOT).items(): z.write(src, "glowpoint-main/" + rel)
    d = copy(os.path.join(t, "d")); edit(d)
    zfiles, zdesc = P.load_base(d, zbuf)
    zc = P.changes(d, zfiles); zc = ([r for r in zc[0] if r in ch], zc[1], zc[2])
    check(zc == (ch, ad, rm), "the original zip works as the base")

sys.exit(1 if fails else 0)
