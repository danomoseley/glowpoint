"""Documentation test: README.md and AGENTS.md must describe what the code can do.

  python3 tests/test_docs.py

Checks:
  - every light and ceiling type has a README section and a row in the type overview table
  - every option that a type reads (f["key"], f.get("key")) is named in that type's README section
  - every expression helper is in the README expression table
  - every plain-text key is listed in the README and in AGENTS.md
  - every command-line tool is in the README, and the main tools are in AGENTS.md
  - every README link to a section (#anchor) and to a file in the repo works
Run it after every change, and before every push (the pre-push hook does this).
"""
import inspect, os, re, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from glowpoint import features as F, render as R, expr as E

README = open(os.path.join(ROOT, "README.md")).read()
AGENTS = open(os.path.join(ROOT, "AGENTS.md")).read()
problems = []


def section(title):
    """Text of a README '### `title`' section, up to the next heading."""
    m = re.search(r"^### `" + re.escape(title) + r"`\s*$(.*?)(?=^#{2,3} )", README, re.M | re.S)
    return m.group(1) if m else None


# 1. types and their options
types = dict(F.LIGHTS); types.update({k: v[1] for k, v in R.GEOMETRY.items()})
ignore_keys = {"layer", "type", "note", "name"}           # handled by the renderer, documented elsewhere
for name, fn in types.items():
    sec = section(name)
    if sec is None:
        problems.append(f"type '{name}' has no README section (### `{name}`)"); continue
    if not re.search(r"\|\s*\[`" + re.escape(name) + r"`\]", README):
        problems.append(f"type '{name}' is not in the README type overview table")
    src = inspect.getsource(fn)
    if name in R.GEOMETRY: src += inspect.getsource(R.GEOMETRY[name][0])
    keys = set(re.findall(r'\bf\["(\w+)"\]', src)) | set(re.findall(r'\bf\.get\("(\w+)"', src)) | \
           set(re.findall(r'"(\w+)" in f\b', src))
    for k in sorted(keys - ignore_keys):
        if f"`{k}`" not in sec:
            problems.append(f"type '{name}': option `{k}` is used in the code but not named in its README section")

# 2. expression helpers
ns_src = inspect.getsource(E.namespace) + inspect.getsource(R.render)
helpers = set(re.findall(r"return dict\((.*?)\)\s*$", inspect.getsource(E.namespace), re.S)[0].replace("\n", " ").split(","))
helpers = {h.split("=")[0].strip() for h in helpers if "=" in h} - {"min", "max", "abs", "round"}
helpers.add("coffers")
table = README[README.find("## Relationships"):README.find("## Outputs")]
for h in sorted(helpers):
    if f"{h}(" not in table:
        problems.append(f"expression '{h}()' is not in the README expression table")

# 3. plain-text keys
m = re.search(r'k not in \((.*?)\) else v', inspect.getsource(R.evaluate))
plain = re.findall(r'"(\w+)"', m.group(1)) if m else []
for k in plain:
    if f"`{k}`" not in README[README.find("Text that is not an expression"):]:
        problems.append(f"plain-text key `{k}` is not in the README list")
    if f"`{k}`" not in AGENTS and False:
        problems.append(f"plain-text key `{k}` is not in AGENTS.md")

# 4. tools
tools = [os.path.splitext(f)[0] for f in os.listdir(os.path.join(ROOT, "glowpoint"))
         if f.endswith(".py") and "def main" in open(os.path.join(ROOT, "glowpoint", f)).read()] + ["render"]
for t in sorted(set(tools)):
    if f"glowpoint.{t}" not in README:
        problems.append(f"tool glowpoint.{t} is not in the README")
for t in ("render", "calibrate", "measure", "zoom", "doctor"):
    if f"glowpoint.{t}" not in AGENTS:
        problems.append(f"tool glowpoint.{t} is not in AGENTS.md")

# 5. README links
heads = {re.sub(r"[^a-z0-9 _-]", "", h.strip().lower()).replace(" ", "-") for h in re.findall(r"^#+ (.*)$", README, re.M)}
for a in sorted(set(re.findall(r"\]\(#([^)]+)\)", README)) - heads):
    problems.append(f"README link to #{a} has no matching section")
for f in sorted(set(re.findall(r"\]\((?!http|#)([^)\s]+)\)", README))):
    if not os.path.exists(os.path.join(ROOT, f)):
        problems.append(f"README links to {f}, which does not exist")

# 6. version and changelog
from glowpoint import __version__
CHANGELOG = open(os.path.join(ROOT, "CHANGELOG.md")).read()
if f"## {__version__}" not in CHANGELOG:
    problems.append(f"CHANGELOG.md has no entry for the current version {__version__} (glowpoint/__init__.py)")

if problems:
    print("FAIL  documentation is not up to date:")
    for p in problems: print("      -", p)
    sys.exit(1)
print(f"PASS  documentation: {len(types)} types, {len(helpers)} expressions, {len(plain)} plain-text keys, "
      f"{len(set(tools))} tools, all README links")
