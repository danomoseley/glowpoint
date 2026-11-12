"""Send core code changes back as a patch, when you cannot push to GitHub (for example in a chat sandbox).

  python3 -m glowpoint.patch status                       which core files changed, compared with the base
  python3 -m glowpoint.patch make "short title" [--why "what and why"] [--base FOLDER_OR_ZIP] [--no-tests]
  python3 -m glowpoint.patch apply FILE.patch             apply a patch (git apply, or patch -p1)

make writes local/patches/<date>-<title>.patch: a standard unified diff (git apply works with it) with a
header that has the title, the reason, the glowpoint version, and the test results. Send that file to the
maintainer, for example as an attachment to a GitHub issue, or give it to an agent that can push:
    git apply --check FILE.patch && git apply FILE.patch && (run the tests) && commit && push

The base (the original files to compare with) is, in this order: --base (a folder or the original zip),
the git repository (if there is one), or the copy that glowpoint.doctor saves in local/.baseline/ when it
first runs in a folder without git. User projects (local/, drawings, out/) are never in a patch.
"""
import argparse, datetime, difflib, hashlib, io, os, re, shutil, subprocess, sys, zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKIP_DIRS = {".git", "local", "out", "__pycache__", ".githooks_tmp"}
SKIP_EXT = {".pyc", ".zip"}
TEXT_EXT = {".py", ".md", ".json", ".txt", ".cfg", ".toml", ".yml", ".yaml", ""}


def tracked_files(root):
    out = {}
    for d, dirs, files in os.walk(root):
        rel_d = os.path.relpath(d, root)
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for fn in files:
            rel = os.path.normpath(os.path.join(rel_d, fn)).replace(os.sep, "/")
            if rel.startswith("./"): rel = rel[2:]
            if os.path.splitext(fn)[1].lower() in SKIP_EXT: continue
            if re.match(r"projects/[^/]+/drawing\.", rel): continue
            out[rel] = os.path.join(d, fn)
    return out


def _read(path):
    with open(path, "rb") as fh: return fh.read()


def baseline_dir(root=ROOT):
    return os.path.join(root, "local", ".baseline")


def save_baseline(root=ROOT, quiet=False):
    """Copy the current files as the base for later patches (only once per folder)."""
    dst = baseline_dir(root)
    if os.path.isdir(dst): return dst
    for rel, src in tracked_files(root).items():
        p = os.path.join(dst, rel); os.makedirs(os.path.dirname(p), exist_ok=True); shutil.copy2(src, p)
    if not quiet: print(f"saved the original files in {os.path.relpath(dst, root)} (the base for patches)")
    return dst


def load_base(root, base=None):
    """dict rel -> bytes of the original files, and a description of the base."""
    if base:
        if zipfile.is_zipfile(base):
            z = zipfile.ZipFile(base); names = z.namelist()
            top = os.path.commonprefix([n for n in names if not n.endswith("/")]).split("/")[0] + "/"
            files = {}
            for n in names:
                if n.endswith("/") or not n.startswith(top): continue
                rel = n[len(top):]
                if any(part in SKIP_DIRS for part in rel.split("/")) or os.path.splitext(rel)[1] in SKIP_EXT: continue
                files[rel] = z.read(n)
            return files, f"zip {os.path.basename(base)}"
        return {r: _read(p) for r, p in tracked_files(os.path.abspath(base)).items()}, f"folder {base}"
    if os.path.isdir(os.path.join(root, ".git")):
        try:
            names = subprocess.run(["git", "-C", root, "ls-files"], capture_output=True, text=True, check=True).stdout.split()
            files = {}
            for n in names:
                r = subprocess.run(["git", "-C", root, "show", f"HEAD:{n}"], capture_output=True)
                if r.returncode == 0: files[n] = r.stdout
            return files, "git HEAD"
        except Exception:
            pass
    b = baseline_dir(root)
    if os.path.isdir(b):
        return {r: _read(p) for r, p in tracked_files(b).items()}, "local/.baseline"
    raise SystemExit("no base to compare with: give --base (the original zip or folder). "
                     "Next time run python3 -m glowpoint.doctor before changing code; it saves the base.")


def changes(root, base_files):
    cur = tracked_files(root)
    changed, added, removed = [], [], []
    for rel, p in sorted(cur.items()):
        if rel not in base_files: added.append(rel)
        elif hashlib.sha256(_read(p)).digest() != hashlib.sha256(base_files[rel]).digest(): changed.append(rel)
    for rel in sorted(base_files):
        if rel not in cur and not rel.startswith("local/"): removed.append(rel)
    return changed, added, removed


def _is_text(rel, data):
    return os.path.splitext(rel)[1].lower() in TEXT_EXT and b"\0" not in data[:4096]


def unified(rel, old, new):
    """A git-style diff for one file (old or new can be None)."""
    a = old.decode("utf-8").splitlines(keepends=True) if old is not None else []
    b = new.decode("utf-8").splitlines(keepends=True) if new is not None else []
    for lines in (a, b):
        if lines and not lines[-1].endswith("\n"): lines[-1] += "\n\\ No newline at end of file\n"
    head = [f"diff --git a/{rel} b/{rel}\n"]
    if old is None: head.append("new file mode 100644\n")
    if new is None: head.append("deleted file mode 100644\n")
    body = list(difflib.unified_diff(a, b, "/dev/null" if old is None else f"a/{rel}",
                                     "/dev/null" if new is None else f"b/{rel}", n=3))
    return "".join(head + body) if body else ""


def run_tests(root):
    res = []
    for t in ("tests/test_docs.py", "tests/test_render.py", "tests/test_calibrate.py", "tests/test_detect.py", "tests/test_patch.py"):
        if not os.path.exists(os.path.join(root, t)): continue
        r = subprocess.run([sys.executable, "-W", "ignore", t], cwd=root, capture_output=True, text=True)
        lines = [l for l in r.stdout.splitlines() if l.startswith(("PASS", "FAIL"))]
        res.append((t, r.returncode == 0, lines))
    return res


VERSION_FILE, CHANGELOG = "glowpoint/__init__.py", "CHANGELOG.md"


def _version(data):
    m = re.search(rb'__version__\s*=\s*"([^"]+)"', data or b"")
    return m.group(1).decode() if m else "unknown"


def make(root, title, why="", base=None, tests=True, changelog=""):
    base_files, base_desc = load_base(root, base)
    changed, added, removed = changes(root, base_files)
    cur = tracked_files(root)
    # The maintainer chooses the version number and writes CHANGELOG.md when the patch goes in.
    # A session never does: two sessions would both choose the same next number.
    log = [l.strip() for l in changelog.splitlines() if l.strip()]
    held = [r for r in (VERSION_FILE, CHANGELOG) if r in changed]
    if CHANGELOG in held:
        old = base_files[CHANGELOG].decode("utf-8").splitlines(); new = _read(cur[CHANGELOG]).decode("utf-8").splitlines()
        log += [l[1:].strip() for l in difflib.unified_diff(old, new, lineterm="", n=0)
                if l.startswith("+- ") and l[1:].strip() not in log]
    changed = [r for r in changed if r not in held]
    if held:
        print("note: the version number and CHANGELOG.md are not in the patch; the maintainer sets them."
              + (" The changelog lines are in the patch header." if log else ""))
    if not (changed or added or removed):
        print("no core changes compared with the base"); return None
    parts, skipped = [], []
    for rel in changed + added:
        new = _read(cur[rel]); old = base_files.get(rel)
        if not _is_text(rel, new) or (old is not None and not _is_text(rel, old)):
            skipped.append(rel); continue
        parts.append(unified(rel, old, new))
    for rel in removed:
        if _is_text(rel, base_files[rel]): parts.append(unified(rel, base_files[rel], None))
        else: skipped.append(rel)
    ver = _version(base_files.get(VERSION_FILE))
    results = run_tests(root) if tests else []
    now = datetime.datetime.now()
    header = [f"Subject: {title}", "", f"glowpoint version: {ver}", f"base: {base_desc}", f"date: {now:%Y-%m-%d %H:%M}", ""]
    if why: header += ["Why:", why, ""]
    header += ["Changelog (the maintainer adds these lines under the next version number):"] + \
              ([f"  {l if l.startswith('- ') else '- ' + l}" for l in log] or ["  (none given)"]) + [""]
    header += ["Files:"] + [f"  changed  {r}" for r in changed] + [f"  added    {r}" for r in added] + \
              [f"  removed  {r}" for r in removed]
    if skipped:
        header += ["", "Not in this patch (binary files; send them separately):"] + [f"  {r}" for r in skipped]
    if tests:
        header += ["", "Tests:"]
        for t, ok, lines in results:
            header.append(f"  {'PASS' if ok else 'FAIL'}  {t}")
            header += [f"      {l}" for l in lines if l.startswith("FAIL")]
    header += ["", "Apply: git apply --check this.patch && git apply this.patch  (or: patch -p1 < this.patch)", "---", ""]
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40] or "change"
    out_dir = os.path.join(root, "local", "patches"); os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{now:%Y%m%d-%H%M}-{slug}.patch")
    with open(path, "w", newline="\n") as fh:
        fh.write("\n".join(header) + "".join(parts))
    print(f"wrote {os.path.relpath(path, root)}: {len(changed)} changed, {len(added)} added, {len(removed)} removed"
          + (f", {len(skipped)} binary skipped" if skipped else ""))
    if tests and not all(ok for _, ok, _ in results):
        print("warning: some tests fail; the header says which. Fix them, or explain why, before sending the patch.")
    return path


def _py_apply(root, text, check=False):
    """A small applier for unified diffs (for sandboxes without git or patch). Returns a list of problems."""
    problems, edits = [], {}
    blocks = re.split(r"(?m)^diff --git ", text)[1:]
    for blk in blocks:
        lines = blk.splitlines(keepends=True)
        m = re.match(r"a/(\S+) b/(\S+)", lines[0]); rel = m.group(2)
        new_file = any(l.startswith("new file mode") for l in lines[:4])
        deleted = any(l.startswith("deleted file mode") for l in lines[:4])
        path = os.path.join(root, rel)
        if new_file and os.path.exists(path):
            problems.append(f"{rel}: already exists"); continue
        cur = [] if new_file else (open(path, encoding="utf-8").read().splitlines(keepends=True) if os.path.exists(path) else None)
        if cur is None:
            problems.append(f"{rel}: missing"); continue
        out, pos, i = [], 0, 0
        while i < len(lines) and not lines[i].startswith("@@"): i += 1
        ok = True
        while i < len(lines):
            h = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", lines[i]); i += 1
            old_l, new_l, prev = [], [], " "
            while i < len(lines) and not lines[i].startswith("@@"):
                l = lines[i]; i += 1
                if l.startswith("\\"):
                    if prev in ("-", " ") and old_l: old_l[-1] = old_l[-1].rstrip("\n")
                    if prev in ("+", " ") and new_l: new_l[-1] = new_l[-1].rstrip("\n")
                    continue
                prev = l[:1]
                if prev in (" ", "-"): old_l.append(l[1:])
                if prev in (" ", "+"): new_l.append(l[1:])
            start = max(int(h.group(1)) - 1, 0) if old_l else int(h.group(1))
            found = None
            for d in sorted(range(-len(cur), len(cur) + 1), key=abs):
                k = start + d
                if pos <= k <= len(cur) - len(old_l) and cur[k:k + len(old_l)] == old_l:
                    found = k; break
            if found is None:
                problems.append(f"{rel}: a change does not match the current file"); ok = False; break
            out += cur[pos:found] + new_l; pos = found + len(old_l)
        if ok:
            edits[rel] = None if deleted else "".join(out + cur[pos:])
    if not check and not problems:
        for rel, content in edits.items():
            path = os.path.join(root, rel)
            if content is None: os.remove(path); continue
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="") as fh: fh.write(content)
    return problems


def _after_apply(path):
    head = open(path, encoding="utf-8").read().split("\n---\n", 1)[0]
    m = re.search(r"(?ms)^Changelog.*?:\n(.*?)(?:\n\n|\Z)", head)
    print("Next (maintainer): read the change, run the tests, raise __version__ in glowpoint/__init__.py "
          "(the next number after the current one), and add the changelog lines under it:")
    print(m.group(1) if m else "  (the patch has no changelog lines: write one)")


def apply(root, path):
    """Apply a patch: git apply, then patch -p1, then the small built-in applier. All or nothing."""
    ok = _apply(root, path)
    if ok: _after_apply(path)
    return ok


def _apply(root, path):
    try:
        if subprocess.run(["git", "apply", "--check", path], cwd=root, capture_output=True).returncode == 0:
            subprocess.run(["git", "apply", path], cwd=root, check=True); print("applied with git apply"); return True
    except FileNotFoundError:
        pass
    try:
        if subprocess.run(["patch", "-p1", "--forward", "--dry-run", "-i", path], cwd=root, capture_output=True).returncode == 0:
            subprocess.run(["patch", "-p1", "--forward", "-i", path], cwd=root, check=True, capture_output=True)
            print("applied with patch -p1"); return True
    except FileNotFoundError:
        pass
    text = open(path, encoding="utf-8").read()
    problems = _py_apply(root, text, check=True)
    if not problems:
        _py_apply(root, text); print("applied with the built-in applier"); return True
    print("could not apply the patch. Nothing was changed. Problems:")
    for p in problems: print("  " + p)
    print("The files may have changed since the patch was made (it may already be in this version: look in CHANGELOG.md).")
    return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status"); s.add_argument("--base")
    mk = sub.add_parser("make"); mk.add_argument("title"); mk.add_argument("--why", default="")
    mk.add_argument("--base"); mk.add_argument("--no-tests", action="store_true")
    mk.add_argument("--changelog", default="", help="the line for CHANGELOG.md (do not edit CHANGELOG.md or the version)")
    a_ = sub.add_parser("apply"); a_.add_argument("file")
    a = ap.parse_args(argv)
    if a.cmd == "status":
        files, desc = load_base(ROOT, a.base); ch, ad, rm = changes(ROOT, files)
        print(f"base: {desc}")
        for r in ch: print("  changed ", r)
        for r in ad: print("  added   ", r)
        for r in rm: print("  removed ", r)
        if not (ch or ad or rm): print("  no core changes")
    elif a.cmd == "make":
        make(ROOT, a.title, a.why, a.base, not a.no_tests, a.changelog)
    else:
        return 0 if apply(ROOT, os.path.abspath(a.file)) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
