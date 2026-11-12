"""Save a project to one file, and restore it, so it survives the end of a chat session.

  python3 -m glowpoint.project save <project folder>       writes local/backups/<name>-<date>.zip
  python3 -m glowpoint.project restore <file.zip>          puts the project back in local/<name>/

A chat sandbox (ChatGPT and others) deletes its files after some time. The project file has everything
that is needed to continue in a new conversation: the drawing, model.json, design.json (and other design
files), camera.json, fixtures.json, types/ (plugins), and the last images from out/. Give it to the user to
keep. In a new conversation, the user uploads the glowpoint zip and the project file, and you restore it.
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
    out = out or os.path.join(ROOT, "local", "backups", f"{name}-{now:%Y%m%d-%H%M}.zip")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    files = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for d, dirs, fns in os.walk(project):
            rel_d = os.path.relpath(d, project)
            dirs[:] = [x for x in dirs if x != "__pycache__"]
            for fn in fns:
                rel = os.path.normpath(os.path.join(rel_d, fn)).replace(os.sep, "/")
                if rel.startswith("out/") and not fn.lower().endswith(".png"): continue   # images only from out/
                if fn.endswith(".pyc"): continue
                z.write(os.path.join(d, fn), f"{name}/{rel}"); files.append(rel)
        z.writestr(f"{name}/{MANIFEST}", json.dumps({"project": name, "glowpoint": _version(),
                                                      "saved": f"{now:%Y-%m-%d %H:%M}", "files": files}, indent=1))
    print(f"saved {name} ({len(files)} files) to {os.path.relpath(out, ROOT)}")
    return out


def restore(path, dest=None):
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
    if info: msg += f" (saved {info.get('saved')} with glowpoint {info.get('glowpoint')}; this is {_version()})"
    if os.path.basename(target) != top: msg += f". A project named {top} already existed, so this one is {os.path.basename(target)}"
    print(msg)
    return target


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("save"); s.add_argument("project"); s.add_argument("--out")
    r = sub.add_parser("restore"); r.add_argument("file"); r.add_argument("--dest")
    a = ap.parse_args(argv)
    if a.cmd == "save": save(a.project, a.out)
    else: restore(a.file, a.dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
