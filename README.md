# glowpoint

> **AI assistants:** if a user gave you this repository (a clone or a zip), read [AGENTS.md](AGENTS.md) now and follow it. It tells you how to start, what to ask the user, and how to work. The user does not need to give you any other instructions.

Put lighting concepts on an architect's perspective drawing, placed accurately in 3D.

You start with a perspective image of a space: a render from 3D software or a hand sketch, in one-, two- or three-point perspective. glowpoint builds a simple 3D model behind the drawing (the camera, the floor, the walls, the ceiling, the columns). Then you describe the lighting in a design file, for example "three downlights equally spaced above the desk" or "an uplight on every visible column face". glowpoint calculates the exact positions and draws the light on the original drawing, in the correct perspective.

The output is diagrammatic, not photorealistic. It shows **what is lit and where the light comes from**, for a design review with the architect.

![The lobby example, drawn as linework from its model](docs/lobby-linework.png)

*The lobby example from `projects/lobby`, drawn as linework from its model. With the architect's drawing in the project folder, the same lights are drawn on the drawing.*

---

## Contents

- [Install](#install)
- [Changes](CHANGELOG.md)
- [Quick start](#quick-start)
- [Sandboxes without internet (ChatGPT and others)](#sandboxes-without-internet-chatgpt-and-others)
- [How it works](#how-it-works)
- [Project folder](#project-folder)
- [model.json: the 3D model](#modeljson-the-3d-model)
- [design.json: the lighting design](#designjson-the-lighting-design)
- [Light and ceiling types](#light-and-ceiling-types)
- [Relationships (expressions)](#relationships-expressions)
- [Outputs](#outputs)
- [Setting up a new drawing](#setting-up-a-new-drawing)
- [Adding your own types (plugins)](#adding-your-own-types-plugins)
- [Working without merge conflicts](#working-without-merge-conflicts)
- [Notes for AI agents](#notes-for-ai-agents)
- [Limits](#limits)
- [Roadmap](#roadmap)

---

## Install

Python 3.10 or newer.

```bash
git clone https://github.com/danomoseley/glowpoint.git
cd glowpoint
pip install -r requirements.txt
```

The only dependencies are `numpy` and `opencv-python`. It runs on Linux, macOS, and Windows.

## Quick start

The lobby example runs without its drawing (the drawing is not in this repository). `--linework` draws the model itself:

```bash
python3 -m glowpoint.render projects/lobby --linework
```

With your own drawing in the project folder, draw the lights on the drawing, and make the check image too:

```bash
python3 -m glowpoint.render projects/lobby --check
```

This writes:

| File | What it is |
|---|---|
| `projects/lobby/out/concept.png` | The drawing (or linework) with the lighting and a legend |
| `projects/lobby/out/check.png` | The 3D model on the drawing, with a 4 ft grid on each surface |
| `projects/lobby/out/positions.csv` | Every light: layer, type, surface, X/Y/Z in feet |

To change the lighting, edit `design.json` and run the same command again.

| Option | Use |
|---|---|
| `--check` | Also write `out/check.png` |
| `--linework` | Draw the model as linework instead of using the drawing |
| `--camera view.json` | Render from another camera (see below). The path is from the current folder |
| `--design file.json` | Use another design file, for example an option B |
| `--out name.png` | Name of the output image in `out/`. With any name other than `concept.png`, the other outputs get the same name: `check_name.png`, `positions_name.csv` |

A project without `design.json` renders the model with no lights. Use this to check a new model before you design.

To see the same design from another position, give a camera. The model is drawn as linework, because the architect's image only fits its own camera. This camera stands in the lobby's left doorway, at eye height, and looks toward the far end of the hall:

```bash
python3 -m glowpoint.render projects/lobby --camera door.json --out door.png
```

```json
{"f": 626, "principal": [525, 350], "position": [-24.4, 5.5, 31.0], "yaw": 20, "pitch": 0, "roll": 0}
```

`position` is in model feet. `yaw` 0 looks along +Z (into the original drawing), 90 looks along +X (to the right). `f` is the lens in pixels: for an image 1050 px wide, 626 px is an 80° field of view.

## Sandboxes without internet (ChatGPT and others)

Some chat assistants run code in a sandbox that cannot reach GitHub or install packages. Use glowpoint there like this:

1. On GitHub, click **Code → Download ZIP**, and upload `glowpoint-main.zip` to the chat.
2. Ask the assistant to unzip it and run `python3 -m glowpoint.doctor` from the `glowpoint-main` folder. It prints the Python, numpy, and OpenCV versions and `READY` or `NOT READY`. glowpoint needs only numpy and OpenCV, which most sandboxes already have.
3. Then ask it to follow `AGENTS.md`.

If the sandbox can run Python but not shell commands, use the functions directly:

```python
import sys; sys.path.insert(0, "glowpoint-main")
from glowpoint.render import render
render("glowpoint-main/projects/lobby", linework=True)          # same as: python3 -m glowpoint.render ... --linework

from glowpoint import calibrate, measure, zoom                  # each tool has a main(); for example:
measure.main(["glowpoint-main/projects/lobby", "floor", "302", "444"])
```

**Keep your work.** A chat sandbox deletes its files after some time. The assistant gives you a project file at important steps (`python3 -m glowpoint.project save <project>`): the drawing, model, design, plugins, fixture list, and the last images in one zip. To continue later, start a new chat, upload the glowpoint zip and the project file, and the assistant restores it (`python3 -m glowpoint.project restore <file>`). A restore never overwrites a project with the same name; it uses a new name (`lobby-2`). A restore also checks the version: the file records the glowpoint version that saved it. A project from an older version is usually fine; a project from a newer version prints a warning (use the newest glowpoint zip). Then it renders the project and compares the lights with the light list saved in the file, and says if they differ.

**Updating a session that already has glowpoint.** Download the new zip, upload it to the same conversation, and send this message with it. It works also when the old version in the session is older than these instructions:

```text
Here is a newer version of glowpoint. Update without losing my work:
1. First make a zip of each project in local/ (with python3 -m glowpoint.project save local/<project> if this version has it, otherwise a zip of the project folder: drawing, model.json, design.json, types/, fixtures.json) and give it to me to download as a backup. If the files from earlier in this conversation are gone, tell me, and do not continue.
2. Tell me if you changed any glowpoint files outside local/ earlier in this conversation. Do not copy them to the new version.
3. Rename the old folder, unzip the new zip into a new folder, and run python3 -m glowpoint.doctor there.
4. Read the new AGENTS.md completely and follow it from now on, starting at "When the user sends an updated zip", step 3.
5. If you changed glowpoint code in the old folder, make a file of those changes with the new version (from the new folder: python3 -c "from glowpoint.patch import make; make('OLD_FOLDER', 'changes from an older session', base='THE_OLD_ZIP')"), and give it to me.
6. Render my current project with the new version, send me the image, and tell me what changed compared with the last image.
```

If the backup in step 1 is all that is left (for example after the sandbox was reset), start a new conversation, upload the new zip and the backup zip, and ask the assistant to put the backup projects into `local/`.

**Code changes in a sandbox.** A sandbox cannot push to GitHub. If the assistant changes the glowpoint code there (for example to fix a bug), it runs `python3 -m glowpoint.patch make "title" --why "..."` and gives you a `.patch` file. Send that file to the person who looks after glowpoint, or attach it to a GitHub issue. See [Patches from sessions that cannot push](#patches-from-sessions-that-cannot-push).

If OpenCV has no LSD line detector (some versions), the camera setup uses a Hough line detector instead. It is a little less accurate (lens within about 1 % on the test images, instead of 0.3 %). `glowpoint.doctor` tells you which one you have.

## How it works

1. **Camera.** The setup tool finds the camera from the vanishing points in the image: the lens, the turn, the tilt, and the roll. One known dimension sets the scale.
2. **Model.** The space is a set of flat rectangles (floor, walls, ceiling, soffits) and boxes (columns, desks). All sizes are in feet.
3. **Ray casting.** For each pixel of the drawing, glowpoint finds which surface the pixel shows and the 3D point on it. This gives exact perspective and correct hiding: a light behind a column does not show.
4. **Design.** Each light is placed on a named surface. Its position is a relationship to the model ("centered between Column L1 and Column R1"), not a fixed number. When the model changes, the lights follow.
5. **Drawing.** Light is drawn as a soft warm glow over the original linework, so the architect's drawing stays readable.

Coordinates: **X** to the right, **Y** up (floor = 0), **Z** into the image, in feet. The drawing's camera usually stands at X = 0, Z = 0.

## Project folder

```
projects/lobby/
  drawing.png    the architect's perspective drawing (PNG or JPG)
  model.json     the 3D model behind the drawing
  design.json    the lighting design
  out/           output images and positions.csv (made by the render command)
```

One folder for each drawing. To start a new project, make a new folder with the drawing, then follow [Setting up a new drawing](#setting-up-a-new-drawing). Keep your projects outside this repository or in `local/` (see [Working without merge conflicts](#working-without-merge-conflicts)).

To experiment with the lobby example, copy it first: `cp -r projects/lobby local/lobby`. The tests use their own copy in `tests/fixtures/`, so the example can change without breaking them, but a copy keeps the repository clean.

> **Use the original drawing.** glowpoint marks every PNG that it writes (a hidden text field, the pixels do not change) and refuses a marked image as `drawing.png`, so an output with lights already drawn on it is not used again by mistake. Screenshots and JPEG copies lose the mark, so keep the original file.

> **Drawings are not in this repository.** The architects' drawings belong to the architects or their clients. `.gitignore` excludes `projects/*/drawing.*` and `projects/*/out/`. The lobby example runs with `--linework`.

## model.json: the 3D model

```json
{
  "drawing": "drawing.png",
  "units": "ft",
  "camera": {"vp": [543, 345], "f": 550, "eye_height": 9.388},
  "calibration": "One-point perspective. Scale from people at 5 ft 8 in.",
  "surfaces": [
    {"name": "Floor",     "axis": "Y", "at": 0,     "X": [-25.37, 38.57], "Z": [5.07, 111.64]},
    {"name": "Left wall", "axis": "X", "at": -25.37, "Y": [0, 20.81],    "Z": [5.07, 111.64]}
  ],
  "boxes": [
    {"name": "Column L1", "kind": "column", "X": [-14.82, -8.32], "Y": [0, 24.36], "Z": [50.65, 57.14]},
    {"name": "Desk",      "kind": "object", "X": [-24.8, -22.3],  "Y": [0, 3.26],  "Z": [35.13, 52.16]}
  ]
}
```

The camera has two forms.

**General** (two- and three-point images; what `glowpoint.calibrate` writes):

```json
"camera": {"f": 651.3, "principal": [526.8, 350.3], "position": [0, 5.5, 0], "yaw": 25.1, "pitch": 12.0, "roll": 0.0}
```

**One-point** (the camera looks straight along +Z):

```json
"camera": {"vp": [543, 345], "f": 550, "eye_height": 9.388}
```

| Field | Meaning |
|---|---|
| `camera.f` | Lens, in pixels (distance from the eye to the picture plane) |
| `camera.principal` | The point in the image straight in front of the camera, in pixels (usually the image centre) |
| `camera.position` | Eye position in feet. Usually `[0, eye height, 0]` |
| `camera.yaw`, `pitch`, `roll` | Turn to the right, tilt up, and roll, in degrees |
| `camera.vp` | One-point form: the vanishing point in pixels |
| `camera.eye_height` | One-point form: height of the eye above the floor, in feet |
| `surfaces[].axis` | The axis the surface is perpendicular to. `Y` = floor, ceiling, soffit. `X` = left or right wall. `Z` = back wall |
| `surfaces[].at` | Position of the surface on that axis |
| `surfaces[].X/Y/Z` | Size of the surface on the other two axes |
| `boxes[]` | Columns and objects. `kind` is `column` or `object` |

Each box makes five surfaces, named `"<name> front"`, `"back"`, `"left"`, `"right"`, and `"top"`. Front is the side at the low Z end (toward the drawing's camera), left is the low X side. On the drawing, objects (like the desk) are not drawn, because the drawing already shows them. In linework, check images, and other camera views they are drawn as boxes. They always hide light that is behind them, and lights can refer to them.

Surfaces and boxes can have a `"note"` field. Use it to record how a value was found or what was assumed, for example a hidden end of an object.

## design.json: the lighting design

A design is a list of **layers**. Each layer has a name, a short description (for the legend), and **features** (lights or ceiling elements).

```json
{
  "title": "LIGHTING CONCEPT",
  "layers": [
    {
      "name": "Reception",
      "description": "3 downlights on the desk, 4 wall sconces",
      "features": [
        {"type": "downlight", "plane": "Left soffit",
         "x": "box('Desk').xc",
         "z": "spaced(box('Desk').z0, box('Desk').z1, 3)",
         "d": "inch(8)", "beam_to": "box('Desk').top", "pool_r": 1.4},
        {"type": "sconce", "plane": "Left wall",
         "along": "spaced(box('Desk').z0, box('Desk').z1, 4)", "y": 6.5}
      ]
    }
  ]
}
```

Any value can be a number or a text expression (see [Relationships](#relationships-expressions)). If a position is a list, glowpoint makes one light for each value. If two positions are lists, it makes one light for each combination (a grid).

Set `"legend": false` at the top level to leave out the legend. Set `"legend_at"` to choose where it goes: `bottom-left` (default), `bottom-right`, `top-left`, `top-right`, or `below` (a white band under the drawing, so the legend covers nothing).

glowpoint warns when two fixtures from different layers are at the same place (for example a pendant and a downlight above the same point).

## Light and ceiling types

![One example of each type](docs/menu.png)

[`docs/menu.png`](docs/menu.png) shows one example of each type on the lobby model. Rebuild it with `python3 docs/make_menu.py` (the designs are in `docs/menu_tiles.json`; add a tile when you add a type).

| Type | What it is |
|---|---|
| [`glow`](#glow) | A soft glow around a point: a table lamp, floor lamp, or candle in the drawing |
| [`wallwasher`](#wallwasher) | A row of wallwashers with scallops on the wall: recessed in the ceiling, or on arms out from the wall |
| [`object_light`](#object_light) | Light from a piece of furniture or architecture: up onto the ceiling, down onto the floor, an LED edge |
| [`projection`](#projection) | A projected light pattern on a surface: dappled light through leaves, a window shape, stripes |
| [`downlight`](#downlight) | Round downlight symbol in a ceiling, with a beam and a pool |
| [`sconce`](#sconce) | Wall light with a wash up and down |
| [`uplight`](#uplight) | In-floor uplight that grazes a column face or wall |
| [`wash`](#wash) | Wall wash from the top of a wall, optionally from a ceiling slot |
| [`pendant`](#pendant) | Pendant on a cord, from a ceiling or from inside coffers |
| [`fixture`](#fixture) | A specific fixture, drawn from its parts (trim, lens, rings, slots) |
| [`track`](#track) | Track lighting: surface, recessed (with trim), trimless, or suspended track, with aimable heads in set aperture sizes |
| [`slots`](#slots) | Narrow recessed lines in a ceiling: lit slots or track channels with spot heads, as lines or a grid |
| [`linear_pendant`](#linear_pendant) | Suspended linear fixture with direct light down and indirect light up onto the ceiling |
| [`luminous`](#luminous) | A glowing ceiling or wall area (luminous ceiling, backlit stretch ceiling), with optional panel joints |
| [`waffle`](#waffle) | Square or round coffers cut into a ceiling |
| [`cove`](#cove) | A recessed ceiling cove (tray), or a wall cove (a lit ledge on a wall) |
| [`slats`](#slats) | Parallel slats or baffles below a ceiling, optionally lit from above |
| [`lightwell`](#lightwell) | A deep opening in a ceiling (round or rectangular) with a glowing top: a skylight or laylight, with concealed light on its walls |

More types can be added as plugins (see [Adding your own types](#adding-your-own-types-plugins)).

**Light colour (all types).** Every feature accepts `"cct"` (colour temperature in kelvin, for example `2700`, `3000`, `4000`) or `"light_color"` (`[R, G, B]`). Put `"cct"` at the top level of `design.json` to set the default for the whole design. Without either, the light is about 2700 K. The colours are diagrammatic: warm amber at 2200 K, pale yellow at 3000 K, near white at 4000 K, and cool blue at 6500 K. Use them to compare warm and cool options with the architect.

```json
{"title": "OPTION B", "cct": 3000, "layers": [ ... {"type": "wallwasher", "cct": 4000, ...} ... ]}
```

Positions on a surface:

| Surface | Position keys |
|---|---|
| Horizontal (floor, ceiling, soffit, box top) | `x`, `z` |
| Wall at constant X (left wall, right wall, box left/right) | `along` (= Z), `y` |
| Wall at constant Z (back wall, box front/back) | `along` (= X), `y` |

### `glow`
A soft glow around a point: lights the surfaces nearby and shows a halo around the source. Use it to switch on the table lamps, floor lamps, or candles that are already in the drawing.

```json
{"type": "glow", "x": -12.5, "y": 2.3, "z": 5.9, "r": 1.6, "halo": 0.7}
```

| Key | Default | Meaning |
|---|---|---|
| `x`, `y`, `z` | | Position of the source, ft (lists make several) |
| `r` | 2.0 | How far the light reaches on nearby surfaces, ft |
| `strength` | 0.7 | Brightness on the surfaces, 0 to 1 |
| `halo` | 0.6 | Size of the halo around the source, ft (0 = none) |

### `wallwasher`
A row of wallwashers that light a wall with the typical scallops, brightest a little below the source and fading down the wall.

```json
{"type": "wallwasher", "wall": "Back wall", "plane": "Ceiling", "range": "surf('Back wall').X", "spacing": 4, "offset": 3}
{"type": "wallwasher", "wall": "Right wall", "mounting": "arm", "y": 15, "range": [62, 108], "spacing": 6, "offset": 1.5}
```

| Key | Default | Meaning |
|---|---|---|
| `wall` | | The wall that is lit |
| `mounting` | `recessed` | `recessed` (in the ceiling, near the wall) or `arm` (on arms out from the wall) |
| `plane` | `Ceiling` | Recessed: the ceiling the fixtures are in |
| `y` | | Arm: height of the fixtures, ft |
| `range` | | (start, end) along the wall |
| `spacing` | 3.0 | Distance between fixtures, ft (or `count`) |
| `count` | | Number of fixtures, equally spaced |
| `offset` | 2.5 | Distance from the wall to the fixtures, ft. Always on the room side |
| `d` | 4 in | Recessed: aperture diameter, ft |
| `length` | 2.0 | Arm: length of the lamp housing along the wall, ft |
| `reach` | 8.0 | How far down the wall the light goes, ft |
| `strength` | 0.95 | Brightness, 0 to 1 |

### `object_light`
Light that comes from a box in the model: up from its top onto the ceiling (a lit vitrine or cabinet), down from its underside onto the floor (a floating stair, a bench or desk with a light below), and an optional LED line along its edges.

```json
{"type": "object_light", "box": "Desk", "down": 0.8, "under_y": 0.6, "spread": 1.5, "edge": "bottom"}
```

| Key | Default | Meaning |
|---|---|---|
| `box` | | Name of the box in `model.json` |
| `up` | 0 | Brightness of the light up onto the surfaces above the box, 0 to 1 |
| `down` | 0 | Brightness of the light down onto the floor around the box, 0 to 1 |
| `under_y` | bottom of the box | Height where the down light comes out (for example the underside of a desk top) |
| `spread` | 2.0 | How far the light spreads past the outline of the box, ft |
| `edge` | none | `bottom` or `top`: draw a lit line along those edges |

### `projection`
A light pattern projected on a surface, as with a gobo projector or daylight through leaves or a window.

```json
{"type": "projection", "plane": "Floor", "at": [8, 78], "size": [14, 16], "pattern": "dapple"}
{"type": "projection", "plane": "Left wall", "at": [80, 8], "size": [8, 6], "pattern": "window", "panes": [3, 2], "cct": 2200}
```

| Key | Default | Meaning |
|---|---|---|
| `plane` | | Surface |
| `at` | | Centre: `[x, z]` on floors and ceilings, `[along, y]` on walls |
| `size` | [6, 4] | Width and height of the pattern on the surface, ft |
| `pattern` | `dapple` | `dapple` (light through leaves), `window` (panes), or `stripes` |
| `rotate` | 0 | Turn the pattern on the surface, degrees |
| `soft` | 0.4 | Width of the soft edge, ft |
| `strength` | 0.8 | Brightness, 0 to 1 |
| `density`, `scale`, `seed` | 1.0, 1.0, 1 | Dapple: amount of light, size of the leaf pattern, and a number for a different random pattern |
| `panes`, `mullion` | [3, 2], 0.25 | Window: number of panes across and up, and the width of the bars, ft |
| `pitch`, `duty` | 1.0, 0.5 | Stripes: spacing, ft, and the lit part of each stripe, 0 to 1 |

### `downlight`
A round downlight in a horizontal surface.

| Key | Default | Meaning |
|---|---|---|
| `plane` | | Surface name |
| `x`, `z` | | Position(s) |
| `d` | 8 in | Aperture diameter, ft |
| `beam_to` | 0 | Height where the beam lands (0 = floor; use `box('Desk').top` for a desk) |
| `pool_r` | 1.5 | Radius of the light pool, ft |
| `cone` | true | Draw the beam |
| `pool_a` | 0.5 | Strength of the pool, 0 to 1 |

### `sconce`
A wall light with a soft wash up and down.

| Key | Default | Meaning |
|---|---|---|
| `plane` | | Wall name |
| `along`, `y` | | Position(s) along the wall and height to the center |
| `w`, `h` | 0.4, 1.0 | Size of the fixture, ft |
| `spread`, `reach` | 0.9, 2.6 | Width and height of the wash, ft |
| `direction` | `both` | `up`, `down`, or `both` |
| `ceiling` | none | Name of a ceiling or soffit that gets light above an up-light |
| `ceiling_spread` | 4.0 | How far that light spreads on the ceiling, ft |

### `uplight`
An in-floor uplight that grazes a vertical face. Usually for columns.

| Key | Default | Meaning |
|---|---|---|
| `faces` | | One face name, a list, or `visible_faces('column')` |
| `at` | center | Position across the face |
| `offset` | 0.5 | Distance from the face, ft |
| `fade` | 12 | Height over which the wash fades, ft |

### `wash`
A wall wash from the top of a wall, optionally from a slot in the ceiling.

| Key | Default | Meaning |
|---|---|---|
| `plane` | | Wall name |
| `range` | | (start, end) along the wall |
| `y_top` | top of the wall | Height where the wash starts |
| `fade`, `strength` | 10, 0.8 | How fast the wash fades down, and how bright it is |
| `slot` | none | `{"plane": "Left soffit", "offset": 2}` draws the slot in that ceiling, `offset` ft from the wall. The slot is always on the room side of the wall (the side of the drawing's camera), so the sign of `offset` does not matter |

### `pendant`
A pendant hanging from a horizontal surface, with a glow around the shade and an optional pool.

| Key | Default | Meaning |
|---|---|---|
| `plane` | | Surface it hangs from |
| `from_y` | | Instead of `plane`: the height where the cord starts. For pendants in coffers: `"coffers('Waffle', 'y')"` |
| `x`, `z` | | Position(s) |
| `y` | | Height of the bottom of the shade above the floor, ft. Use this for "3 ft above the desk": `"box('Desk').top + 3"` |
| `drop` | 10 | Distance from the cord start (the `plane` or `from_y`) to the bottom of the shade, ft. This sets the pendant length |
| `d`, `h` | 1.5, 0.6 | Shade diameter and height, ft |
| `pool_r` | 0 | Radius of a light pool, ft (0 = none) |
| `beam_to` | 0 | Height of the pool (0 = floor) |

Give the length with `drop` or the height with `y`. If both are given, `y` is used. For pendants of different lengths, use one feature for each length.

### `fixture`
A specific fixture, drawn from its parts (trim, lens, rings, slots), flush on a surface. Use it to show the real fixture of the design, not a generic symbol. The fixture is defined one time in a **fixture list** and used in many places.

```json
{"type": "fixture", "fixture": "round-12in-downlight",
 "x": "coffers('Waffle', 'x')", "z": "coffers('Waffle', 'z')", "y": "coffers('Waffle', 'y')"}
```

| Key | Meaning |
|---|---|
| `fixture` | Name in the fixture list |
| `plane` | Surface the fixture is on (or give `y` for a horizontal level, for example the top of the coffers) |
| `x`, `z` or `along`, `y` | Position(s), as for the other types |
| `rotate` | Turn the fixture on its surface, degrees |

**Fixture list.** Put it in `<project>/fixtures.json`, or in a `"fixtures"` block in `design.json` (that one wins). [`examples/fixtures.json`](examples/fixtures.json) has a round downlight, a 2×2 troffer, and a linear slot.

```json
"round-12in-downlight": {
  "parts": [
    {"kind": "fill", "shape": "round", "d": 1.0, "color": "trim"},
    {"kind": "line", "shape": "round", "d": 1.0, "width": 0.03},
    {"kind": "fill", "shape": "round", "d": 0.7, "color": "lit"}
  ],
  "glow": {"r": 0.9, "strength": 0.55}
}
```

Parts are drawn in order, so later parts are on top. All sizes in feet.

| Part key | Meaning |
|---|---|
| `kind` | `fill` (a filled shape), `line` (the outline of a shape), `slots` (parallel lines inside a shape: louvers, blades) |
| `shape` | `round` (`d`), `square` (`w`), or `rect` (`w` across, `l` along) |
| `width` | Line width, ft. Thin lines stay at least about one pixel wide |
| `n`, `angle` | `slots`: number of lines, and their direction in degrees |
| `color` | `lit`, `trim`, `metal`, `dark`, `black`, `white`, or `[R, G, B]` |
| `glow` | For the fixture: `r` (ft) and `strength` (0 to 1) of the light around it |

![A 12 in round fixture in every coffer, seen from below](docs/coffer-fixtures.png)

To describe a fixture from a photo or a spec sheet: start with the outer trim (`fill` + `line`), then the lens or aperture (`fill`, `lit`), then details (`line` rings, `slots`). Use the real dimensions from the spec sheet.

### `track`
Track lighting: a track profile along a line, with heads that you can aim. Four mounting types, as offered by architectural track makers (for example ERCO, Stucchi, Flos, iGuzzini):

| `mounting` | What it is |
|---|---|
| `surface` | The profile is fixed below the ceiling |
| `recessed` | The profile is set into the ceiling, flush, with a visible trim flange |
| `trimless` | The profile is plastered into the ceiling, flush, with no trim: only a dark slot shows |
| `suspended` | The profile hangs below the ceiling on cables |

```json
{"type": "track", "plane": "Ceiling", "mounting": "surface", "direction": "z", "at": 34, "range": [30, 105],
 "aperture": "M", "spacing": 6, "tilt": 30, "pan": 0, "beam": 25, "color": "white"}
```

**Aperture sizes.** `aperture` is a size name or a diameter in feet (for example `"inch(3)"`). The names come from manufacturers' specifications:

| Name | Diameter | Source |
|---|---|---|
| `XS` | 32 mm (1¼ in) | ERCO Parscan XS |
| `S` | 60 mm (2⅜ in) | ERCO Parscan S |
| `M` | 92 mm (3⅝ in) | ERCO Parscan M |
| `L` | 129 mm (5⅛ in) | ERCO Parscan L |
| `2.5in`, `3in`, `3.75in` | 2.5, 3, 3.75 in | Solais Xd20, Xd24, Xd30 |
| `2in`, `4in` | 2, 4 in | Common track head sizes |

Add more sizes in `APERTURES` in `glowpoint/features.py`, or give the diameter directly.

| Key | Default | Meaning |
|---|---|---|
| `plane` | | Surface the track is on (or `from_y` for a height, for example `coffers('Waffle', 'y')`; only `surface` and `suspended` tracks) |
| `from_y` | | Instead of `plane`: the height of the track's top |
| `mounting` | `surface` | `surface`, `recessed`, `trimless`, or `suspended` |
| `direction` | `z` | The direction the track runs: `z` or `x` |
| `at` | | Position across the track, ft. A list makes several parallel runs |
| `range` | | (start, end) along the track, ft |
| `profile_w`, `profile_h` | 36 mm, 30 mm | Width and height of the track profile, ft |
| `flange` | 12 mm | `recessed`: width of the trim flange on each side, ft |
| `drop` | 3.0 | `suspended`: distance from the ceiling to the top of the track, ft |
| `cable_spacing` | 8.0 | `suspended`: distance between cables, ft |
| `piece` | 1.0 | `surface`/`suspended`: the profile is drawn in pieces of this length, ft, so a run partly behind a column or the camera still shows |
| `spacing` | 4.0 | Distance between heads, ft (or use `count`) |
| `count` | | Number of heads, equally spaced, half a space at each end |
| `aperture` | `S` | Head size: a name from the table above, or a diameter in ft |
| `head` | `cylinder` | `cylinder` (adjustable spotlight) or `flush` (a low head that sits in the track, like ERCO InTrack) |
| `head_l` | 1.6 × diameter | Length of a cylinder head, ft |
| `stem` | 0.12 | Length of the adapter between the track and a cylinder head, ft |
| `tilt` | 0 | Aim: degrees from straight down |
| `pattern` | none | Stitch track: short staggered runs instead of one continuous track. `{"run": 5, "gap": 3, "stagger": 3}`: runs of 5 ft with 3 ft gaps, moved 3 ft across, alternating left and right |
| `pan` | 0 | Aim direction for the tilt, degrees: 0 = across the track toward +X (or +Z for tracks along X), 180 = the other way, 90 = along the track |
| `beam` | 25 | Beam angle, degrees. Sets the size of the light pool where the aim lands |
| `pool` | 0.5 | Brightness of the light pool, 0 to 1 (0 = none) |
| `color` | `white` | Housing: `white`, `black`, `silver`, or `[R, G, B]` |

`positions.csv` has one row for each head (`track head`, with its size in inches) and one row for each track.

![Suspended track with L heads (left), surface track with M heads aimed at the wall (right), and a recessed track](docs/track-lighting.png)

### `slots`
Narrow recessed lines in a surface: lit slots (a lens flush with the ceiling) or track channels with spot heads, as single lines, parallel lines, or a grid.

```json
{"type": "slots", "plane": "Ceiling", "X": "(box('Column R1').x1 + 1, surf('Right wall').at - 1)", "Z": [20, 105],
 "direction": "grid", "pitch": 4, "w": "inch(2)", "style": "track", "spot_spacing": 2}
```

| Key | Default | Meaning |
|---|---|---|
| `plane` | | Surface |
| `X`, `Y`, `Z` | | (start, end) of the area, on the two axes of the surface (as for `luminous`) |
| `direction` | `grid` | `z`: lines that run along Z; `x`: lines that run along X; `grid`: both |
| `pitch` | 4.0 | Spacing between lines, ft |
| `offset` | pitch / 2 | Distance from the start of the area to the first line, ft. For one line, use a large `pitch` and set `offset` |
| `w` | 0.25 | Slot or track width, ft |
| `style` | `lens` | `lens`: lit slot. `track`: dark track channel |
| `strength` | 0.7 | Lens slots: brightness of the light next to the slot |
| `spot_spacing` | none | Track: distance between spot heads along each track, ft |
| `spot_size` | 0.35 | Track: size of a spot head, ft |

### `linear_pendant`
A suspended linear fixture (direct/indirect): a lit lens below, light up onto the ceiling, and light down onto the floor. Two cables hold it.

```json
{"type": "linear_pendant", "plane": "Ceiling", "x": ["0", "12.7"], "z": "every(65, 105, 10)",
 "drop": 8, "length": 6, "direction": "z"}
```

| Key | Default | Meaning |
|---|---|---|
| `plane` | | Ceiling it hangs from (or `from_y`) |
| `from_y` | | Instead of `plane`: the height where the cables start (for example `coffers('Waffle', 'y')`) |
| `x`, `z` | | Centre position(s). Lists make a row or a grid |
| `y` | | Height of the bottom of the fixture, ft (or use `drop`) |
| `drop` | 4.0 | Distance from the cable start to the bottom of the fixture, ft |
| `length`, `w`, `h` | 4.0, 0.3, 0.25 | Fixture size, ft |
| `direction` | `z` | The direction the fixture runs: `z` or `x` |
| `up`, `down` | 0.6, 0.5 | Strength of the light up (on the ceiling) and down (on the floor), 0 to 1 |
| `spread_up`, `spread_down` | 3.0, 2.5 | How far the light spreads on the ceiling and on the floor, ft |

### `luminous`
A glowing area on a surface: a luminous ceiling, a backlit stretch ceiling, or a light wall.

```json
{"type": "luminous", "plane": "Ceiling", "X": "(box('Column R1').x1 + 1, surf('Right wall').at - 1)", "Z": [62, 100], "grid": 2.0}
```

| Key | Default | Meaning |
|---|---|---|
| `plane` | | Surface |
| `X`, `Y`, `Z` | | (start, end) of the area on the two axes of the surface: `X` and `Z` on a ceiling, `Z` and `Y` on a wall at constant X, `X` and `Y` on a wall at constant Z |
| `strength` | 0.9 | Brightness, 0 to 1 |
| `soft` | 0.5 | Width of the softer border, ft |
| `grid` | none | Panel size, ft: draws the joints between panels |
| `bands` | none | Spacing of the lamps behind a fabric or glass ceiling, ft: draws faint brighter lines |
| `bands_along` | `z` | Direction of the lamp lines: `z` or `x` |

**Laylights and fabric ceilings.** A laylight (a glass ceiling with lamps or daylight above it) is a `luminous` area with `grid` for the glass panels and `bands` for the lamps above it; add a `track` below it for accent lights. A backlit fabric ceiling is a `luminous` area with `bands` and no `grid`.
| `joint` | 0.03 | Joint width, ft |

### `waffle`
A waffle-slab ceiling of square coffers. It changes the model, so lights hide correctly inside the coffers.

| Key | Default | Meaning |
|---|---|---|
| `plane` | | The ceiling it is cut into |
| `X`, `Z` | | (start, end) of the waffle area |
| `shape` | `square` | `square` (coffers separated by ribs) or `round` (round recesses in a flat ceiling) |
| `module` | | Grid spacing, centre to centre, ft |
| `rib` | | Square coffers: rib width, ft (the coffer opening is `module − rib`) |
| `d` | | Round coffers: diameter, ft. Must be smaller than `module` |
| `depth` | | Coffer depth, ft |
| `align` | `start` | `start`: the grid starts at the far end (`Z` end) and the left edge (`X` start); a cut coffer can remain at the other edges. `centre`: only full coffers, centred in the area, with equal solid borders |
| `lit` | true | true: coffers glow. false: coffers are plain (use this when fixtures in the coffers give the light) |
| `replace` | false | true: erase what the drawing shows in the waffle area first, then draw the coffers. Use it for coffers that are already in the drawing (see [Coffers that are in the drawing](#coffers-that-are-in-the-drawing)) |

Pendants in coffers: a pendant in every second coffer across and every third in depth, hanging from the coffer tops (Python slices select from the lists):

```json
{"type": "pendant", "from_y": "coffers('Waffle', 'y')", "x": "coffers('Waffle', 'x')[1::2]",
 "z": "coffers('Waffle', 'z')[::3]", "y": 14, "d": 1.2}
```

Round coffers, 24 in on centre, 18 in diameter, 6 in deep, centred:

```json
{"type": "waffle", "plane": "Ceiling", "X": "inset(gap('Column L1', 'Column R1'), 3)",
 "Z": "(surf('Ceiling').Z[0], centre_line('Column L1', 'Column R1', 'Z'))",
 "shape": "round", "module": "inch(24)", "d": "inch(18)", "depth": "inch(6)", "align": "centre", "lit": false}
```

![Round coffers with an 8 in fixture in each, seen from below](docs/round-coffers.png)

### `cove`
Two kinds of cove. Both change the model, so the cove hides what is behind it.

**Recessed cove** (`"kind": "recess"`): a tray recessed into the ceiling. The light comes from a hidden ledge at its edges, so the top of the tray is brightest near the edges.

```json
{"type": "cove", "kind": "recess", "plane": "Ceiling", "X": "inset(gap('Column L1', 'Column R1'), 3)",
 "Z": "(surf('Ceiling').Z[0], centre_line('Column L1', 'Column R1', 'Z'))", "depth": 1.0}
```

**Perimeter cove** (`"kind": "perimeter"`): a lowered border (soffit) around a ceiling area. A hidden light on the border's ledge grazes the ceiling in the centre, brightest near the edges.

```json
{"type": "cove", "kind": "perimeter", "plane": "Ceiling", "X": "inset(gap('Column L1', 'Column R1'), 1)",
 "Z": "(surf('Ceiling').Z[0], centre_line('Column L1', 'Column R1', 'Z'))", "border": 2.0, "drop": 1.0}
```

**Wall cove** (`"kind": "wall"`): a ledge along a wall with a hidden light on top. It lights the wall above it and, if you name the ceiling, the ceiling near the wall.

```json
{"type": "cove", "kind": "wall", "name": "Right cove", "plane": "Right wall", "range": [40, 105],
 "y": 14, "depth": 1.0, "ceiling": "Ceiling"}
```

| Key | Default | Meaning |
|---|---|---|
| `kind` | `recess` | `recess`, `perimeter`, or `wall` |
| `name` | `Cove` | Name of the cove. Give each cove a different name |
| `plane` | `Ceiling` | Recess: the ceiling it is cut into. Wall: the wall |
| `X`, `Z` | | Recess: (start, end) of the tray. Perimeter: (start, end) of the whole area, border included |
| `border` | 2.0 | Perimeter: width of the lowered border, ft |
| `drop` | 1.0 | Perimeter: how far the border hangs below the ceiling, ft |
| `gap` | 0.5 | Perimeter: height of the open gap between the fascia and the ceiling, where the light comes out, ft |
| `depth` | 1.0 (wall) | Recess: depth of the tray, ft. Wall: how far the ledge projects from the wall, ft |
| `range` | | Wall: (start, end) along the wall |
| `y` | | Wall: height of the top of the ledge, ft |
| `h` | 0.5 | Wall: height of the ledge fascia, ft |
| `fade` | 4.0 / 3.0 | Wall: how far up the wall the light goes, ft. Perimeter: how far the light grazes into the ceiling, ft (default 3.0) |
| `ceiling` | none | Wall: name of the ceiling that gets light near the wall |
| `spread` | 4.0 | Wall: how far onto the ceiling the light goes, ft |
| `strength` | 0.85 | Brightness, 0 to 1 |

### `slats`
Parallel slats (or baffles) hanging below a ceiling, ray-traced so that you see between them in perspective. Lights and surfaces behind the slats show through the gaps and are hidden by the slats.

```json
{"type": "slats", "X": "(surf('Soffit step').at, -5.32)", "Z": "(surf('Ceiling').Z[0], surf('Back wall').at)",
 "y": 20, "h": "inch(6)", "w": "inch(3)", "pitch": 1.0, "direction": "x", "color": "wood", "backlit": true}
```

| Key | Default | Meaning |
|---|---|---|
| `name` | `Slats` | Name. Give each slat field a different name |
| `X`, `Z` | | (start, end) of the slat area |
| `y` | | Height of the bottom of the slats, ft |
| `h`, `w` | | Height and width of each slat, ft |
| `pitch` | | Spacing, centre to centre, ft |
| `direction` | `z` | The direction the slats run: `z` (away from the viewer) or `x` (across) |
| `color` | `wood` | `wood`, `white`, `dark`, or `[R, G, B]` |
| `backlit` | false | true: light between the slats (a lit ceiling above them) |

![A recessed cove, backlit wood slats, a wall cove, and a luminous ceiling with 2 ft panels](docs/coves-slats-luminous.png)

### `lightwell`
A deep opening in a ceiling with a glowing top (a skylight or a laylight) and concealed light on its walls, brightest near the top. The opening changes the model, so you see into it correctly from any view, and it lights the floor below.

```json
{"type": "lightwell", "name": "Well 1", "shape": "round", "x": 6.34, "z": 75, "d": 6, "depth": 4}
```

| Key | Default | Meaning |
|---|---|---|
| `name` | `Light well` | Name. Give each well a different name |
| `plane` | `Ceiling` | The ceiling it is cut into |
| `shape` | `rect` | `rect` or `round` |
| `X`, `Z` | | Rectangular: (start, end) of the opening |
| `x`, `z`, `d` | | Round: centre and diameter, ft |
| `depth` | | Depth of the well, ft |
| `top` | `sky` | Colour of the top: `sky` (daylight), `warm`, or `white` |
| `wall_light` | 0.6 | Brightness of the light on the walls, 0 to 1 |
| `pool` | 0.4 | Brightness of the light on the floor below, 0 to 1 (0 = none) |

![A light well, linear direct/indirect pendants, a track grid with spot heads, and a perimeter cove, seen from below](docs/slots-wells-linear.png)

![Stitch track, recessed wallwashers on the back wall, arm wallwashers on the right wall, dappled light on the floor](docs/renfro-additions.png)

## Relationships (expressions)

Expressions refer to the model by name. Use them for all positions that depend on the architecture, so lights move when the model is corrected.

| Expression | Result |
|---|---|
| `box('Desk').x0`, `.x1`, `.xc`, `.z0`, `.z1`, `.zc`, `.y0`, `.top` | Edges and centre of a box |
| `surf('Left soffit').at`, `.X`, `.Y`, `.Z` | Position and ranges of a surface |
| `gap('Column L1', 'Column R1')` | (lo, hi) between the inner faces of two boxes, on X |
| `gap('Column L1', 'Column L2', 'Z')` | The same, on Z |
| `centre_line('Column L1', 'Column R1', 'Z')` | Average of the two box centres on an axis |
| `inset((lo, hi), d)` | (lo + d, hi − d) |
| `mid((lo, hi))` | Centre of a range |
| `spaced(lo, hi, n)` | n positions, equal spaces, half a space at each end |
| `spaced_ends(lo, hi, n)` | n positions, the first at lo and the last at hi |
| `every(start, stop, step)` | start, start + step, … up to stop |
| `list[a:b:c]` | Part of a list, as in Python: `coffers('Waffle', 'x')[1::2]` is every second item, starting with the second |
| `inch(n)` | n inches in feet |
| `visible_faces('column')` | Every face of every column that is visible in the drawing |
| `coffers('Waffle', 'x')`, `coffers('Waffle', 'z')` | Centres of all full coffers of a waffle (square or round, with its `align`), across and in depth. Use both for one item in every coffer |
| `coffers('Waffle', 'y')` | Height of the coffer tops (ceiling + depth), for fixtures inside the coffers |

Examples:

```text
"X": "inset(gap('Column L1', 'Column R1'), 3)"          waffle 3 ft from the inner column faces
"x": "mid((box('Column R1').x1, surf('Right wall').at))" halfway between a column and the wall
"z": "every(centre_line('Column L1', 'Column R1', 'Z') + 9, surf('Back wall').at - 6, 10)"
```

Expressions run in a restricted Python evaluator with only these names (and Python arithmetic, lists, and slices).

**Text that is not an expression.** These keys always hold plain text and are never evaluated: `layer`, `type`, `name`, `note`, `plane`, `slot`, `fixture`, `shape`, `align`, `kind`, `direction`, `color`, `ceiling`, `style`, `top`, `mounting`, `head`, `wall`, `box`, `edge`, `pattern`, `bands_along`. `aperture` is plain text when it is a size name (`S`), and an expression otherwise (`inch(3)`). Every other text value is an expression, so a new text option in a plugin must be added to that list in `glowpoint/render.py`, or a word such as `round` is read as a Python name.

## Outputs

- **concept.png** — the drawing with the lighting and a legend made from the layer names and descriptions.
- **check.png** (with `--check`) — every surface tinted and named, with a 4 ft grid. If the grid follows the lines of the drawing, the model is correct.
- **positions.csv** — one row for each light: layer, type, surface, X/Y/Z (ft), and `visible`. Use it to check the design and to give positions to others. `visible` is about the fixture point itself: an uplight hidden behind a bench is `False`, although the column face that it lights can be in view.

`visible_faces()` always means visible in the drawing's own camera, also when you render another view. Thus a design is the same in all views.

## Setting up a new drawing

### 1. Find the camera

```bash
python3 -m glowpoint.calibrate projects/new/drawing.png --known 640,520,640,388,10
```

The tool finds the straight lines, groups them by vanishing point, and calculates the camera. `--known x1,y1,x2,y2,H` gives the scale (give it two or three times to check it, see below): pixel (x1, y1) is on the floor, pixel (x2, y2) is on the same vertical edge, and they are H feet apart (a door frame, a column edge from floor to ceiling, a person). In a three-point image vertical edges lean; follow the edge. Or give `--eye-height`.

It prints a report and writes `camera.json` (paste it into `model.json` as `"camera"`) and `calibration.png` (each group of lines in one color):

```
282 line segments, 3 vanishing points, three-point perspective
  VP1: 146 lines, fit 0.26 deg rms, at (1947, 488) px, horizontal
  VP2: 82 lines, fit 0.39 deg rms, at (215, 489) px, horizontal
  VP3: 23 lines, fit 0.12 deg rms, at (526, -2708) px, vertical
  lens f = 651.3 px  (horizontal field of view 77.7 deg)
  turn (yaw) 25.13 deg, tilt (pitch) 12.02 deg, roll 0.02 deg
  angles between the found directions (90 = perfect): 90.00, 90.00, 90.00
```

Options:

| Option | Use |
|---|---|
| `--known x1,y1,x2,y2,H` | Scale from a known vertical. Give it several times: the tool prints the eye height from each, how much they disagree, and uses the median |
| `--eye-height FT` | Scale from a known eye height |
| `--f PX` | Lens in pixels, if known (necessary for one-point images) |
| `--tol DEG` | How far a line can be from its vanishing point (default 1; hand drawings 2) |
| `--out FILE` | Camera file to write (default `camera.json`) |
| `--overlay FILE` | Line-group image to write (default `calibration.png`) |

How to read it:

- **fit** — how well the lines meet at each vanishing point. Renders: below 0.5°. Hand drawings: 1° to 3° (use `--tol 2`).
- **angles between the found directions** — the room's main directions must be 90° apart. More than 1° from 90 means a wrong line group or a non-square room. Look at `calibration.png`.
- **known dimensions disagree by** — with several `--known`, more than 10% means a wrong pixel, a wrong dimension, or an inexact drawing. The line for each one shows which is the odd one out. Hand sketches often disagree by 10–25%: choose the dimension you trust most, for example the ceiling height.
- **one-point** images: the lens cannot be found from lines alone. Give `--f`, or calculate it from something square (see below).

The world frame: the origin is on the floor below the camera, Y is up, Z is the room direction most in front of the camera, and X is to its right.

### 2. Start model.json

Make `model.json` in the project folder with the camera from step 1:

```json
{
  "drawing": "drawing.png",
  "units": "ft",
  "camera": {"f": 651.3, "principal": [526.8, 350.3], "position": [0, 5.5, 0], "yaw": 25.1, "pitch": 12.0, "roll": 0.0},
  "calibration": "Scale from the door frame at 7 ft.",
  "surfaces": [],
  "boxes": []
}
```

### 3. Build the surfaces

To find exact pixel positions, use the zoom tool. It makes an enlarged image with the original pixel coordinates on a grid, and writes it to `out/zoom.png` next to the image (or `--out`):

```bash
python3 -m glowpoint.zoom projects/new/drawing.png                       # whole image, coarse grid
python3 -m glowpoint.zoom projects/new/drawing.png 150 390 330 500       # zoom on a box (X0 Y0 X1 Y1)
python3 -m glowpoint.zoom projects/new/drawing.png 150 390 330 500 --mark 302,444   # confirm a point
python3 -m glowpoint.zoom projects/new/drawing.png 650 160 860 460 --model projects/new  # model edges in red
```

Pixels: a whole number is the centre of a pixel, and the grid lines go through pixel centres. Fractions such as 302.5 are allowed in all tools. Far from the camera one pixel can be more than half a foot, so use fractions there.

Then measure the room in feet with the measure tool, then add the surfaces and boxes to `model.json`. The tool reads the camera from `model.json` (or give it `camera.json` instead of the project folder):

```bash
python3 -m glowpoint.measure projects/new floor 302 444          # floor point:  X -22.85  Z 52.16
python3 -m glowpoint.measure projects/new height 203 492 203 441 # height above a floor point: 3.26 ft
python3 -m glowpoint.measure projects/new plane 760 182 Y 24.36  # point on the plane Y = 24.36 (a ceiling)
python3 -m glowpoint.measure projects/new plane 120 300 X -25.37 # point on the wall X = -25.37
python3 -m glowpoint.measure projects/new project -22.85 0 52.16 # the pixel of a 3D point: check a corner
```

`height` measures along the true vertical, also when vertical edges lean in a three-point image.

**Boxes in one step.** `box` makes a model box from the base corners that you can see and one top pixel straight above the first corner, and prints a line for `model.json`:

```bash
python3 -m glowpoint.measure projects/new box 161 417 234 397 132 400 --top 161 348 --name "Nightstand L" --snap "Left wall"
# {"name": "Nightstand L", "kind": "object", "X": [-13.05, -10.71], "Y": [0, 1.61], "Z": [5.04, 7.05]}
```

| Option | Use |
|---|---|
| `--top X Y` | A top pixel straight above the first corner (necessary) |
| `--name`, `--kind` | Name and kind of the box (`object` or `column`) |
| `--depth FT`, `--toward wall\|camera` | With only 2 corners (one side visible): the size and direction of the hidden side |
| `--snap "Left wall"` | Move the box's nearest side onto that wall (for furniture against a wall) |

Typical steps:

1. **Floor:** `floor` on the far corners that you can see. Make the floor surface a little larger than the room.
2. **Walls:** `floor` on two points of each wall's base line. A wall along Z has the same X at both points; that X is its `at`.
3. **Ceiling:** `height` from a floor point to the ceiling line straight above it.
4. **Columns and objects:** `floor` on the base corners, `height` for the top. Add each one as a box.

Name surfaces and boxes clearly (`Left wall`, `Column L1`, `Desk`). The design refers to these names.

**Hidden parts.** When part of an object is hidden (for example one end of a bench behind a column), find its limits from what you can see: the hidden end must be behind the edge that hides it (use `plane` at that edge). Then choose a value inside the limits, usually by symmetry, and write the assumption in the box's `note`. Do not model objects that are fully hidden.

### Coffers that are in the drawing

If the architect's drawing already shows a coffered ceiling, let glowpoint find it:

```bash
python3 -m glowpoint.detect coffers projects/new --depth 0.75 --add
```

It finds square or round coffers on the ceiling and writes a `waffle` feature with the module, the rib width (square) or the diameter (round), and the area. `out/detect_coffers.png` shows the detected coffers in red over the drawing: check that the red lines lie on the drawn coffers. With `--add`, the feature goes into `design.json` as the first layer, with `"replace": true` (the drawn coffers are erased and redrawn) and `"lit": false`. Then you can change the depth or the shape, and use `coffers()` to put a fixture or pendant in every coffer.

| Option | Use |
|---|---|
| `--plane` | The surface with the coffers (default `Ceiling`) |
| `--area X0 X1 Z0 Z1` | Search only in this rectangle on the surface, ft |
| `--depth FT` | Coffer depth. A line drawing seldom shows it clearly, so give the real one (default 6 in) |
| `--add` | Add the feature to `design.json` |

Notes: the camera and the ceiling must be set up first (the detection uses them). Running it again with `--add` replaces the earlier "Coffers (detected)" layer. If it finds nothing, it says what to check; see AGENTS.md, "Task: coffered ceilings", for the steps when the detection fails. Only full coffers are reported. If the coffers continue past the edge of the image, the area is extended to the edge of the ceiling surface, in whole modules, and the note says so. On renders the module and area are usually within an inch; the rib width within about an inch.

`python3 tests/test_detect.py` tests the detection on drawings with known coffers (square and round, one-point and two-point).

### 4. Check

Run `python3 -m glowpoint.render projects/new --check` and look at `out/check.png`. Each surface must follow the lines of the image. For a close check, zoom with `--model projects/new`: every red model edge must lie on a line of the image. Use `measure ... project X Y Z` to compare corners in numbers. If a surface is off, measure it again.

### One-point images and hand drawings

For a one-point image, set the lens from something square in plan, for example a column: if its front corner is at pixel x1 and its back corner (same side) at x2, and the front face is w pixels wide, then `f = w / ((x1 − vp_x)/(x2 − vp_x) − 1)`. Average several measurements on a hand drawing.

Hand drawings are not exact. Match the model to the drawing, not to an ideal grid.

### Tests

`python3 tests/test_detect.py` tests the coffer detection on drawings with known coffers.

`python3 tests/test_docs.py` checks that this README and AGENTS.md describe the code: every type and each option that it reads, every expression, every tool, every plain-text key, and every link.

To contribute: run `git config core.hooksPath .githooks` once in your clone. Then every `git push` first runs the documentation test and all tests, and stops if one fails. Update README.md and AGENTS.md in the same commit as the code change.

`python3 tests/test_render.py` draws the lobby test fixture (`tests/fixtures/lobby`) and checks it three ways: the light positions (within 0.01 ft), the surface that each pixel shows (exact, the same on every OpenCV version), and the image (loosely, because OpenCV versions draw text and soft edges a little differently). `--update` accepts an intended change.

`python3 tests/test_calibrate.py` renders the lobby model from known cameras (two- and three-point, with tilt and roll), runs the setup on each image, and compares the result with the true camera. Current results: lens within 0.3 %, angles within 0.15°, scale within 1 %.

## Adding your own types (plugins)

You can add light types, ceiling types, and expression helpers **without changing glowpoint's files**. A plugin is one Python file. glowpoint loads plugins from:

1. Each folder in the `GLOWPOINT_TYPES` environment variable (separate several folders with `:` on Linux and macOS, `;` on Windows). Use this for types that a whole office shares, for example a folder on a shared drive.
2. `<project>/types/`. Use this for a type that only one project needs.

A later file can replace a type with the same name, so a project can change an office type for itself. glowpoint prints each plugin that it loads. Files that start with `_` are skipped.

A plugin can define any of these:

```python
LIGHTS = {"linear_strip": linear_strip}  # function(canvas, feature)
GEOMETRY = {"vault": (prepare, draw)}    # prepare(model, feature) before ray casting,
                                         # draw(canvas, feature, base_image) -> new base image
def helpers(model):                      # extra names for design.json expressions
    return {"between": lambda a, b: ...}
```

[`examples/types/linear_strip.py`](examples/types/linear_strip.py) is a complete example: a linear LED strip on any surface, and a `between('Column L1', 'Column R1')` helper. Copy it to start a new type.

Inside a light function, the canvas gives you:

| Name | Use |
|---|---|
| `cv.m` | The model: `surface(name)`, `to3d(surface, u, v)`, `project(points)`, `depth(points)`, `boxes` |
| `cv.ids`, `cv.P`, `cv.dep` | For each pixel: surface index, 3D point, depth along the camera's forward direction |
| `cv.glow(mask, strength)` | Add warm light to pixels (strength 0 to 1 per pixel) |
| `cv.seg(A, B, width)` | Draw a 3D line, hidden where something is in front |
| `cv.visible(points, pixels)` | True for each 3D point that is not hidden |
| `cv.sid(name)` | Index of a surface in `cv.ids` |
| `cv.img`, `cv.over` | The linework image and the light image (OpenCV BGR arrays) |
| `cv.add(feature, type, surface, point, ...)` | Add a row to positions.csv |

When a plugin type is useful for everybody, move it into `glowpoint/features.py` in a pull request.

## Working without merge conflicts

glowpoint keeps your work separate from the code, so you can update glowpoint with `git pull` at any time.

| Your work | Where to keep it | In git? |
|---|---|---|
| Projects (drawing, model, design) | Any folder outside the clone, or `local/` inside it | No (`local/` is ignored) |
| Office light types | A shared folder in `GLOWPOINT_TYPES` | Your choice, in your own repo |
| Project light types | `<project>/types/` | With the project |
| Drawings and renders | In the project folder | No (`drawing.*` and `out/` are ignored) |

Run any project from anywhere:

```bash
python3 -m glowpoint.render ~/work/smith-lobby --check
GLOWPOINT_TYPES=~/office/glowpoint-types python3 -m glowpoint.render ~/work/smith-lobby
```

To try a different design without changing `design.json`, give another file:

```bash
python3 -m glowpoint.render projects/lobby --design design.option-b.json --out option-b.png
```

Only change the files in `glowpoint/` to fix a bug or add a feature for everybody.

### Patches from sessions that cannot push

A chat sandbox (ChatGPT, or any session with a zip and no GitHub access) can change the code but cannot push. `glowpoint.patch` turns those changes into one standard patch file:

```bash
python3 -m glowpoint.doctor                       # at the start: saves the original files in local/.baseline/ (when there is no .git)
python3 -m glowpoint.patch status                 # which core files changed
python3 -m glowpoint.patch make "Fix round coffer size" --why "diameter was read as radius" \
    --changelog "waffle: round d is the diameter"
                                                  # writes local/patches/<date>-fix-round-coffer-size.patch and runs the tests
python3 -m glowpoint.patch make "..." --base glowpoint-main.zip   # compare with the uploaded zip instead
python3 -m glowpoint.patch apply FILE.patch       # apply a patch (git apply, patch -p1, or a built-in applier)
```

The patch file starts with a header (title, reason, glowpoint version, base, changed files, test results), then a normal unified diff. `local/`, drawings, `out/`, and zips are never in a patch. Binary files are listed in the header but not included.

**Version numbers.** A patch never changes the version or `CHANGELOG.md`: if two sessions both raised 0.11.0 to 0.12.0, there would be two different 0.12.0s. The session gives its changelog line with `--changelog`, and the line goes in the patch header. The header also says which version the session started from. If the session changed the version or the changelog anyway, `make` leaves those files out and moves the new changelog lines into the header.

To accept a patch: `python3 -m glowpoint.patch apply FILE.patch` (or `git apply`), read the change, and run the tests. Then raise the version to the next number after the current one, add the changelog lines from the header, commit, and push. `apply` prints these steps and the lines. When a new zip is used in a session that has old patches, the agent applies them again with `patch apply` (they fail cleanly if the change is already in the new version).

`python3 tests/test_patch.py` tests this: it makes a patch in a copy without git and applies it to a clean copy.

**Versions.** The version is in `glowpoint/__init__.py` (and `doctor` prints it). [CHANGELOG.md](CHANGELOG.md) lists what changed. When you change behaviour, raise the version and add a line to the changelog in the same commit.

## Notes for AI agents

**Design goal:** the user must feel that glowpoint is simple, and still learn every option. AGENTS.md gives the user information in small parts at the moment it is useful (a short welcome, then how to check the model, then how to ask for lighting, a menu on request, and one tip after each render). Keep this in mind when you add a feature: add it to the menu in AGENTS.md, and keep the welcome short.

glowpoint is designed so that an agent can take a request in plain words and place lights reliably. [AGENTS.md](AGENTS.md) has the rules and the work sequence (Claude Code reads it through `CLAUDE.md`).

- **Always use relationships.** Write `"spaced(box('Desk').z0, box('Desk').z1, 3)"`, not three numbers. If the model is corrected later, the lights follow.
- **Add the objects you refer to.** If a request mentions an object (a desk, a bench, a stair), add it as a box in `model.json` first. Then refer to it.
- **Check the model before you place lights.** Run with `--check` and look at `check.png`. Fix surfaces that do not follow the drawing. When a user says that a light looks off-centre, check the model first: the error is usually the surface or box under it, not the light.
- **Verify with positions.csv.** After a render, read the CSV and confirm the numbers that the user asked for (spacing, distances, counts). Look at `concept.png` too.
- **State your assumptions.** When a request leaves out a size (aperture, rib width, height), choose a normal value and tell the user which value you chose.
- **Only edit `design.json` for design changes** and `model.json` for geometry changes. Keep the code generic.
- **For a new kind of light, write a plugin** in `<project>/types/` (start from `examples/types/linear_strip.py`). Do not change `glowpoint/` for one project.
- **Keep user projects out of the repo.** Put them in `local/` or outside the clone.
- **Set up a new image with the tools:** `glowpoint.calibrate` for the camera, `glowpoint.zoom` to read pixels, `glowpoint.measure` for every surface. Do not estimate positions by eye.
- **Coordinates:** X right, Y up, Z into the image, feet. Horizontal surfaces use (x, z). Walls use (along, y).
- **Update README.md and AGENTS.md before every commit and push**, and run the tests after a code change: `python3 tests/test_docs.py`, `python3 tests/test_render.py`, `python3 tests/test_calibrate.py`. The pre-push hook (`git config core.hooksPath .githooks`) runs them for you.

Typical request to design file:

> "A downlight on each column line, halfway between the first and the second columns."

```json
{"type": "downlight", "plane": "Ceiling",
 "x": ["box('Column L1').xc", "box('Column R1').xc"],
 "z": "centre_line('Column L1', 'Column L2', 'Z')"}
```

Two values for `x` and one for `z` make two lights.

## Limits

- The room must have mostly square corners (two main horizontal directions at 90°). Angled walls can be added as boxes or surfaces, but they cannot set the camera.
- Surfaces are flat rectangles that line up with the axes. No curved or sloped surfaces yet.
- The model only knows what the drawing shows. Areas outside the drawing are guesses.
- After the camera setup, the surfaces are measured by hand with the measure tool.

## Roadmap

- Automatic surfaces: find the floor, wall, and ceiling planes from the line groups.
- Design options (A, B, C) in one design file, and a style file for colors, line weights, and labels.
- A review PDF, and 3D export (OBJ, DXF) for SketchUp, Rhino, and Revit.
