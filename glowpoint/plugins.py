"""Load extra light types, ceiling types, and expression helpers without changing glowpoint itself.

Search order (a later file can replace a type of the same name):
  1. the built-in types in glowpoint/features.py
  2. every folder in the GLOWPOINT_TYPES environment variable (paths separated by ':' on Linux/macOS, ';' on Windows)
     -> use this for types that a whole office shares
  3. <project>/types/
     -> use this for types that only one project needs

A plugin is a .py file. It can define any of:

  LIGHTS   = {"pendant": pendant}               # function(canvas, feature)
  GEOMETRY = {"vault": (prepare, draw)}         # prepare(model, feature) before ray casting,
                                                # draw(canvas, feature, base_image) -> new base image
  def helpers(model):                           # extra names for design.json expressions
      return {"halfway": lambda a, b: (a + b) / 2}

Files that start with '_' are skipped.
"""
import glob, importlib.util, os, sys


def plugin_dirs(project):
    dirs = [d for d in os.environ.get("GLOWPOINT_TYPES", "").split(os.pathsep) if d]
    dirs.append(os.path.join(project, "types"))
    return [d for d in dirs if os.path.isdir(d)]


def load(project, lights, geometry):
    """Returns (lights, geometry, helper_factories, loaded_files). The input dicts are not changed."""
    lights, geometry, helpers, loaded = dict(lights), dict(geometry), [], []
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
            if hasattr(mod, "helpers"):
                helpers.append(mod.helpers)
            loaded.append(path)
    return lights, geometry, helpers, loaded
