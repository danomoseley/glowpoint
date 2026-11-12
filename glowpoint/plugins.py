"""Load extra light types, ceiling types, and expression helpers without changing glowpoint itself.

Search order (a later file can replace a type of the same name):
  1. the built-in types in glowpoint/features.py
  2. library/types/ in this repository: the office library, in every project and for every user
  3. every folder in the GLOWPOINT_TYPES environment variable (paths separated by ':' on Linux/macOS, ';' on Windows)
     -> use this for types that a whole office shares
  4. <project>/types/
     -> use this for types that only one project needs

A plugin is a .py file. It can define any of:

  LIGHTS   = {"pendant": pendant}               # function(canvas, feature)
  GEOMETRY = {"vault": (prepare, draw)}         # prepare(model, feature) before ray casting,
                                                # draw(canvas, feature, base_image) -> new base image
  def helpers(model):                           # extra names for design.json expressions
      return {"halfway": lambda a, b: (a + b) / 2}

  INFO = {"pendant": {"name": "Cone pendant",                       # how users ask for it, in plain words
                      "description": "a cone pendant with a pool below",
                      "example": "three cone pendants over the table, 30 in above it"}}

INFO is required for every type in LIGHTS and GEOMETRY: without it, users cannot find or ask for the type.
Files that start with '_' are skipped.

Fixture lists (specific fixtures for the "fixture" type) load in this order: library/fixtures.json,
<project>/fixtures.json, then a "fixtures" block in design.json. Give each fixture a "description".

  python3 -m glowpoint.plugins list [project]     the custom types and fixtures that a project can use
"""
import glob, importlib.util, json, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LIBRARY = os.path.join(ROOT, "library")


def plugin_dirs(project):
    dirs = [os.path.join(LIBRARY, "types")]
    dirs += [d for d in os.environ.get("GLOWPOINT_TYPES", "").split(os.pathsep) if d]
    dirs.append(os.path.join(project, "types"))
    return [d for d in dirs if os.path.isdir(d)]


def source_of(path, project):
    path = os.path.abspath(path)
    if path.startswith(os.path.abspath(LIBRARY) + os.sep): return "office library"
    if path.startswith(os.path.abspath(project) + os.sep): return "this project"
    return "office folder"


INFO = {}          # type -> {"name", "description", "example", "file", "source"} for the last load()


def load(project, lights, geometry):
    """Returns (lights, geometry, helper_factories, loaded_files). The input dicts are not changed."""
    lights, geometry, helpers, loaded = dict(lights), dict(geometry), [], []
    INFO.clear()
    for d in plugin_dirs(project):
        for path in sorted(glob.glob(os.path.join(d, "*.py"))):
            if os.path.basename(path).startswith("_"):
                continue
            name = "glowpoint_plugin_" + os.path.splitext(os.path.basename(path))[0] + "_" + str(abs(hash(path)))
            spec = importlib.util.spec_from_file_location(name, path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
            for k, fn in getattr(mod, "LIGHTS", {}).items():
                if k in lights: print(f"note: {path} replaces light type '{k}'")
                lights[k] = fn
            for k, pair in getattr(mod, "GEOMETRY", {}).items():
                if k in geometry: print(f"note: {path} replaces geometry type '{k}'")
                geometry[k] = pair
            info = getattr(mod, "INFO", {})
            for k in list(getattr(mod, "LIGHTS", {})) + list(getattr(mod, "GEOMETRY", {})):
                if not all(info.get(k, {}).get(x) for x in ("name", "description", "example")):
                    print(f"warning: {path}: type '{k}' has no complete INFO (name, description, example). "
                          "Add it, so users can find the type and ask for it by name.")
                INFO[k] = dict(info.get(k, {}), type=k, file=path, source=source_of(path, project))
            if hasattr(mod, "helpers"):
                helpers.append(mod.helpers)
            loaded.append(path)
    return lights, geometry, helpers, loaded


def load_fixtures(project, design=None):
    """All fixtures a project can use, as {name: definition}; later lists replace earlier ones."""
    out = {}
    for f in (os.path.join(LIBRARY, "fixtures.json"), os.path.join(project, "fixtures.json")):
        if os.path.exists(f): out.update(json.load(open(f)))
    out.update((design or {}).get("fixtures", {}))
    return {k: v for k, v in out.items() if not k.startswith("_")}


def fixture_sources(project, design=None):
    src = {}
    for f, label in ((os.path.join(LIBRARY, "fixtures.json"), "office library"), (os.path.join(project, "fixtures.json"), "this project")):
        if os.path.exists(f):
            src.update({k: label for k in json.load(open(f)) if not k.startswith("_")})
    src.update({k: "this project" for k in (design or {}).get("fixtures", {}) if not k.startswith("_")})
    return src


def catalog(project, only=None):
    """Lines that describe the custom types and fixtures a project can use (only: a source label to keep)."""
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        load(project, {}, {})
    dp = os.path.join(project, "design.json")
    design = json.load(open(dp)) if os.path.exists(dp) else {}
    fx, fsrc = load_fixtures(project, design), fixture_sources(project, design)
    lines = []
    types = [i for i in INFO.values() if not only or i["source"] == only]
    if types:
        lines.append("Custom types:")
        for i in sorted(types, key=lambda i: (i["source"], i["type"])):
            lines.append(f"  {i.get('name', i['type'])} [{i['type']}, {i['source']}]: {i.get('description', '(no description)')}"
                         + (f'. Ask: "{i["example"]}"' if i.get("example") else ""))
    fixtures = [k for k in fx if not only or fsrc.get(k) == only]
    if fixtures:
        lines.append("Fixtures (for the fixture type):")
        for k in sorted(fixtures, key=lambda k: (fsrc.get(k, ""), k)):
            lines.append(f"  {k} [{fsrc.get(k)}]: {fx[k].get('description', '(no description)')}")
    return lines


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="List the custom types and fixtures that a project can use.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("list"); l.add_argument("project", nargs="?", default=os.path.join(ROOT, "projects", "lobby"))
    a = ap.parse_args(argv)
    lines = catalog(a.project)
    print("\n".join(lines) if lines else "no custom types or fixtures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
