"""Save a project to one file, and restore it, so it survives the end of a chat session.

  python3 -m glowpoint.project save <project folder>       writes local/backups/<name>-<date>.zip
  python3 -m glowpoint.project restore <file.zip>          puts the project back in local/<name>/

A chat sandbox (ChatGPT and others) deletes its files after some time. The project file has everything
that is needed to continue in a new conversation: the drawing, model.json, design.json (and other design
files), camera.json, fixtures.json, types/ (plugins), and the last images from out/. Give it to the user to
keep. In a new conversation, the user uploads the glowpoint zip and the project file, and you restore it.

restore checks the version: the project file records the glowpoint version that saved it. A project from an
older version is usually fine; a project from a newer version needs the newer glowpoint zip. Then it renders
the project and compares the lights with the light list saved in the file, and says if they differ.
"""
import argparse, datetime, json, os, sys, zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MANIFEST = "glowpoint-project.json"


def _version():
    try:
        from glowpoint import __version__
        return __version__
    except Exception:
        return "unknown"


def save(project, out=None):
    project = os.path.abspath(project)
    name = os.path.basename(project.rstrip(os.sep))
    if not os.path.exists(os.path.join(project, "model.json")):
        raise SystemExit(f"{project} has no model.json: it is not a glowpoint project")
    now = datetime.datetime.now()
    if not out:
        base = os.path.join(ROOT, "local", "backups", f"{name}-{now:%Y%m%d-%H%M}")
        out, k = base + ".zip", 1
        while os.path.exists(out):                  # two saves in one minute: never overwrite
            k += 1; out = f"{base}-{k}.zip"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    files = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for d, dirs, fns in os.walk(project):
            rel_d = os.path.relpath(d, project)
            dirs[:] = [x for x in dirs if x != "__pycache__"]
            for fn in fns:
                rel = os.path.normpath(os.path.join(rel_d, fn)).replace(os.sep, "/")
                if rel.startswith("out/") and not fn.lower().endswith((".png", ".csv")): continue   # images and light lists
                if fn.endswith(".pyc"): continue
                z.write(os.path.join(d, fn), f"{name}/{rel}"); files.append(rel)
        z.writestr(f"{name}/{MANIFEST}", json.dumps({"project": name, "glowpoint": _version(),
                                                      "saved": f"{now:%Y-%m-%d %H:%M}", "files": files}, indent=1))
    print(f"saved {name} ({len(files)} files) to {os.path.relpath(out, ROOT)}")
    return out


def _vt(v):
    try: return tuple(int(x) for x in v.split("."))
    except Exception: return None


def version_status(saved):
    """same, older (project from an older glowpoint: usually fine, check the render), newer (get the newer glowpoint)."""
    a, b = _vt(saved or ""), _vt(_version())
    if a is None or b is None: return "unknown"
    return "same" if a == b else ("older" if a < b else "newer")


def _rows(path):
    import csv
    with open(path, newline="") as fh:
        return sorted((r["layer"], r["type"], round(float(r["x"]), 2), round(float(r["y"]), 2), round(float(r["z"]), 2))
                      for r in csv.DictReader(fh))


def compare_render(target):
    """Render the restored project and compare its lights with the light list saved with it."""
    saved = os.path.join(target, "out", "positions.csv")
    if not os.path.exists(saved): return "no saved light list to compare with"
    keep = os.path.join(target, "out", "positions_saved.csv"); os.replace(saved, keep)
    from glowpoint.model import Model
    from glowpoint.render import render
    try:
        render(target, linework=not os.path.exists(Model(target).drawing))
    except Exception as e:
        return f"the project does not render with this version: {e}"
    a, b = _rows(keep), _rows(saved)
    if a == b: return f"same lights as when it was saved ({len(a)} rows)"
    from collections import Counter
    ca, cb = Counter((r[0], r[1]) for r in a), Counter((r[0], r[1]) for r in b)
    diff = [f"{l} ({t}): {ca[(l, t)]} then, {cb[(l, t)]} now" for l, t in sorted(set(ca) | set(cb)) if ca[(l, t)] != cb[(l, t)]]
    moved = sum(1 for x, y in zip(a, b) if x != y) if not diff else 0
    return "the lights differ from when it was saved: " + ("; ".join(diff) if diff else f"{moved} positions moved")


def restore(path, dest=None, check=True):
    dest = dest or os.path.join(ROOT, "local")
    z = zipfile.ZipFile(path)
    names = [n for n in z.namelist() if not n.endswith("/")]
    man = [n for n in names if n.endswith("/" + MANIFEST) and n.count("/") == 1]
    if man:
        top = man[0].split("/")[0]; info = json.loads(z.read(man[0]))
    else:                                   # a plain zip of a project folder
        mj = [n for n in names if n.endswith("model.json") and n.count("/") == 1]
        if not mj: raise SystemExit(f"{path} has no glowpoint project (no model.json)")
        top = mj[0].split("/")[0]; info = {}
    target = os.path.join(dest, top); k = 1
    while os.path.exists(target):
        k += 1; target = os.path.join(dest, f"{top}-{k}")
    for n in names:
        if not n.startswith(top + "/") or n.endswith("/" + MANIFEST): continue
        rel = n[len(top) + 1:]
        if ".." in rel.split("/"): continue
        p = os.path.join(target, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh: fh.write(z.read(n))
    msg = f"restored {top} to {os.path.relpath(target, ROOT)}"
    if os.path.basename(target) != top: msg += f" (a project named {top} already existed)"
    print(msg)
    st = version_status(info.get("glowpoint"))
    saved_v = info.get("glowpoint", "unknown")
    print({"same": f"version: same as when it was saved ({saved_v})",
           "older": f"version: saved with glowpoint {saved_v}, this is {_version()} (newer). Usually fine; check the render",
           "newer": f"WARNING version: saved with glowpoint {saved_v}, but this is only {_version()}. Ask the user for the "
                    f"newest glowpoint zip; this older version may not know all of the project's features",
           "unknown": f"version: unknown (saved with {saved_v}, this is {_version()}); check the render"}[st])
    if check:
        print("render check: " + compare_render(target))
    try:
        from glowpoint.plugins import catalog
        lines = catalog(target, only="this project")
        if lines: print("This project has its own types or fixtures (tell the user their names):\n" + "\n".join(lines))
    except Exception as e:
        print(f"note: could not list the project's types ({e})")
    return target


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("save"); s.add_argument("project"); s.add_argument("--out")
    r = sub.add_parser("restore"); r.add_argument("file"); r.add_argument("--dest")
    r.add_argument("--no-check", action="store_true", help="do not render and compare the lights")
    a = ap.parse_args(argv)
    if a.cmd == "save": save(a.project, a.out)
    else: restore(a.file, a.dest, not a.no_check)
    return 0


if __name__ == "__main__":
    sys.exit(main())
