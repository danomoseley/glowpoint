# glowpoint

Put lighting concepts on an architect's perspective drawing, placed accurately in 3D.

You start with a black-and-white perspective sketch of a space. glowpoint builds a simple 3D model behind the drawing (the camera, the floor, the walls, the ceiling, the columns). Then you describe the lighting in a design file, for example "three downlights equally spaced above the desk" or "an uplight on every visible column face". glowpoint calculates the exact positions and draws the light on the original drawing, in the correct perspective.

The output is diagrammatic, not photorealistic. It shows **what is lit and where the light comes from**, for a design review with the architect.

---

## Contents

- [Install](#install)
- [Quick start](#quick-start)
- [How it works](#how-it-works)
- [Project folder](#project-folder)
- [model.json: the 3D model](#modeljson-the-3d-model)
- [design.json: the lighting design](#designjson-the-lighting-design)
- [Light and ceiling types](#light-and-ceiling-types)
- [Relationships (expressions)](#relationships-expressions)
- [Outputs](#outputs)
- [Setting up a new drawing](#setting-up-a-new-drawing)
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

```bash
# put the architect's drawing in the project folder first (see "Project folder")
python3 -m glowpoint.render projects/lobby --check
```

This writes:

| File | What it is |
|---|---|
| `projects/lobby/out/concept.png` | The drawing with the lighting and a legend |
| `projects/lobby/out/check.png` | The 3D model on the drawing, with a 4 ft grid on each surface |
| `projects/lobby/out/positions.csv` | Every light: layer, type, surface, X/Y/Z in feet |

To change the lighting, edit `design.json` and run the same command again.

## How it works

1. **Camera.** The drawing is a one-point perspective. The vanishing point, the lens (in pixels), and the eye height define the camera.
2. **Model.** The space is a set of flat rectangles (floor, walls, ceiling, soffits) and boxes (columns, desks). All sizes are in feet.
3. **Ray casting.** For each pixel of the drawing, glowpoint finds which surface the pixel shows and the 3D point on it. This gives exact perspective and correct hiding: a light behind a column does not show.
4. **Design.** Each light is placed on a named surface. Its position is a relationship to the model ("centered between Column L1 and Column R1"), not a fixed number. When the model changes, the lights follow.
5. **Drawing.** Light is drawn as a soft warm glow over the original linework, so the architect's drawing stays readable.

Coordinates: **X** to the right, **Y** up (floor = 0), **Z** away from the viewer. The camera is at X = 0, Z = 0.

## Project folder

```
projects/lobby/
  drawing.png    the architect's perspective drawing (PNG or JPG)
  model.json     the 3D model behind the drawing
  design.json    the lighting design
  out/           output images and positions.csv (made by the render command)
```

One folder for each drawing. To start a new project, copy a folder, replace the drawing, and set up the model (see [Setting up a new drawing](#setting-up-a-new-drawing)).

> **Drawings are not in this repository.** The architects' drawings belong to the architects or their clients. `.gitignore` excludes `projects/*/drawing.*` and `projects/*/out/`. Add your own drawing to the project folder to run the example.

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

| Field | Meaning |
|---|---|
| `camera.vp` | Vanishing point in drawing pixels |
| `camera.f` | Lens, in pixels (distance from the eye to the picture plane) |
| `camera.eye_height` | Height of the eye above the floor, in feet |
| `surfaces[].axis` | The axis the surface is perpendicular to. `Y` = floor, ceiling, soffit. `X` = left or right wall. `Z` = back wall |
| `surfaces[].at` | Position of the surface on that axis |
| `surfaces[].X/Y/Z` | Size of the surface on the other two axes |
| `boxes[]` | Columns and objects. `kind` is `column` or `object` |

Each box makes five surfaces, named `"<name> front"`, `"back"`, `"left"`, `"right"`, and `"top"`. The front faces the viewer. Objects (like the desk) are not drawn, because the drawing already shows them. They hide light that is behind them, and lights can refer to them.

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

Set `"legend": false` at the top level to leave out the legend.

## Light and ceiling types

Positions on a surface:

| Surface | Position keys |
|---|---|
| Horizontal (floor, ceiling, soffit, box top) | `x`, `z` |
| Wall at constant X (left wall, right wall, box left/right) | `along` (= Z), `y` |
| Wall at constant Z (back wall, box front/back) | `along` (= X), `y` |

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
| `slot` | none | `{"plane": "Left soffit", "offset": 2}` draws the slot in that ceiling, `offset` ft from the wall |

### `waffle`
A waffle-slab ceiling of square coffers. It changes the model, so lights hide correctly inside the coffers.

| Key | Meaning |
|---|---|
| `plane` | The ceiling it is cut into |
| `X`, `Z` | (start, end) of the waffle area. The grid starts at the far end (`Z` end) and the left edge (`X` start) |
| `module`, `rib`, `depth` | Grid spacing, rib width, coffer depth, ft |
| `lit` | true: coffers glow. false: coffers are plain |

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
| `inch(n)` | n inches in feet |
| `visible_faces('column')` | Every face of every column that is visible in the drawing |

Examples:

```text
"X": "inset(gap('Column L1', 'Column R1'), 3)"          waffle 3 ft from the inner column faces
"x": "mid((box('Column R1').x1, surf('Right wall').at))" halfway between a column and the wall
"z": "every(centre_line('Column L1', 'Column R1', 'Z') + 9, surf('Back wall').at - 6, 10)"
```

Expressions run in a restricted Python evaluator with only these names. Plain names such as `"plane": "Ceiling"` are not evaluated.

## Outputs

- **concept.png** — the drawing with the lighting and a legend made from the layer names and descriptions.
- **check.png** (with `--check`) — every surface tinted and named, with a 4 ft grid. If the grid follows the lines of the drawing, the model is correct.
- **positions.csv** — one row for each light: layer, type, surface, X/Y/Z (ft), and whether it is visible. Use it to check the design and to give positions to others.

## Setting up a new drawing

The setup is partly manual for now. It takes about 15 minutes for a clean drawing.

1. **Vanishing point.** Find where the lines that go away from the viewer meet (floor joints, wall bases, ceiling lines). An OpenCV line detector (`cv2.createLineSegmentDetector`) and a RANSAC fit find it well on clean line drawings.
2. **Eye height.** For a person standing on the floor, `eye_height / person_height = (y_feet − y_vp) / (y_feet − y_head)` in pixels. Use the known height of the people in the drawing (or any known vertical dimension).
3. **Lens.** Use something square in plan (a column, a floor tile) or two known depths. For hand drawings, average several measurements.
4. **Surfaces.** A point on the floor at pixel (x, y) is at `Z = f·h/(y − y_vp)`, `X = (x − x_vp)·h/(y − y_vp)`. Measure wall bases, column bases, and the far end. For heights, `Y = h + (y_vp − y)·Z/f`.
5. **Check.** Run with `--check`. If a grid does not follow the drawing, correct that surface and run again.
6. **Ask for one real dimension** (for example the ceiling height) when you can, and scale the model to it.

Hand drawings are not exact. Match the model to the drawing, not to an ideal grid.

## Notes for AI agents

glowpoint is designed so that an agent can take a request in plain words and place lights reliably.

- **Always use relationships.** Write `"spaced(box('Desk').z0, box('Desk').z1, 3)"`, not three numbers. If the model is corrected later, the lights follow.
- **Add the objects you refer to.** If a request mentions an object (a desk, a bench, a stair), add it as a box in `model.json` first. Then refer to it.
- **Check the model before you place lights.** Run with `--check` and look at `check.png`. Fix surfaces that do not follow the drawing. When a user says that a light looks off-centre, check the model first: the error is usually the surface or box under it, not the light.
- **Verify with positions.csv.** After a render, read the CSV and confirm the numbers that the user asked for (spacing, distances, counts). Look at `concept.png` too.
- **State your assumptions.** When a request leaves out a size (aperture, rib width, height), choose a normal value and tell the user which value you chose.
- **Only edit `design.json` for design changes** and `model.json` for geometry changes. Keep the code generic.
- **Coordinates:** X right, Y up, Z away from the viewer, feet. Horizontal surfaces use (x, z). Walls use (along, y).

Typical request to design file:

> "Two rows of downlights along the column lines, one between each pair of columns."

```json
{"type": "downlight", "plane": "Ceiling",
 "x": ["box('Column L1').xc", "box('Column R1').xc"],
 "z": ["centre_line('Column L1', 'Column L2', 'Z')"]}
```

## Limits

- One-point perspective only. Verticals must be vertical and the main lines must meet at one vanishing point.
- Surfaces are flat rectangles that line up with the axes. No curved or sloped surfaces yet.
- The model only knows what the drawing shows. Areas outside the drawing are guesses.
- The camera setup is manual (see above).

## Roadmap

- A setup tool that calculates the camera from measured points and reports how well they agree.
- One renderer for the original view and for new camera positions (the lights in new views too).
- Design options (A, B, C) in one design file, and a style file for colors, line weights, and labels.
- A review PDF, and 3D export (OBJ, DXF) for SketchUp, Rhino, and Revit.
