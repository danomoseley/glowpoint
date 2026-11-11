# Instructions for AI agents

glowpoint places lighting concepts on a perspective image of a space. The full reference is [README.md](README.md). This file gives the rules and the work sequence.

## Rules

1. **Never estimate positions by eye.** Get pixel positions with `glowpoint.zoom`, and turn them into feet with `glowpoint.measure`.
2. **Use relationships in design.json**, not numbers, for anything that depends on the architecture: `"spaced(box('Desk').z0, box('Desk').z1, 3)"`, not three numbers. Then the lights follow when the model is corrected.
3. **Add an object to model.json before you refer to it.** A desk, bench, or stair is a box.
4. **Geometry goes in model.json, lighting goes in design.json.** Do not change code in `glowpoint/` for one project. A new kind of light is a plugin in `<project>/types/` (copy `examples/types/linear_strip.py`).
5. **Verify every result:** read `out/positions.csv` and confirm the numbers the user asked for (counts, spacing, heights), and look at the output image.
6. **When a light looks wrong, check the model first.** The usual cause is a surface or box that does not match the image. Run with `--check`.
7. **State your assumptions.** If the request leaves out a size, choose a normal value and tell the user which one.
8. **Keep user projects and images out of git.** Put projects in `local/` or outside the clone. Architects' drawings and renders are often confidential.
9. **Use the original drawing.** `drawing.png` must be the file that the user gave you, not an output from `out/` and not an image with lights or coffers already drawn on it. glowpoint marks its own PNG outputs and refuses them as a drawing, but screenshots and JPEG copies lose that mark. If a conversation has several images, confirm with the user which one is the original. If the drawing already shows colored lights or coffers, stop and ask.
10. **Edit JSON files by inserting or changing text**, not by writing the whole file again with a JSON library. That keeps the layout and the diffs small. In `design.json`, most text values are expressions; only `layer`, `type`, `name`, `note`, `plane`, `slot`, `fixture`, `shape`, `align`, `kind`, `direction`, `color`, `ceiling`, `style`, `top`, `mounting`, `head`, `wall`, `box`, `edge`, `pattern`, `bands_along` are plain text (and `aperture` when it is a size name such as `S`) (see the README).
11. **Do not edit `projects/lobby` for experiments.** Copy it to `local/` first.
12. **Before every commit and push, update README.md and AGENTS.md** so they describe every change: new types, options, expressions, tools, and behaviour. `python3 tests/test_docs.py` checks this. Turn on the pre-push hook once in each clone with `git config core.hooksPath .githooks`: it runs the documentation test and all tests, and stops a push that fails.
13. **After a code change, run the tests:** `python3 tests/test_docs.py`, `python3 tests/test_render.py`, and `python3 tests/test_calibrate.py`.

Run all commands from the repository root (`python3 -m glowpoint.<tool>`). In a new environment, run `python3 -m glowpoint.doctor` first. If you cannot clone from GitHub (no internet), ask the user to upload the repository as a zip (GitHub: Code → Download ZIP).

## Task: show a specific fixture

When the user gives a fixture (a photo, a product page, a spec sheet), reproduce it with the `fixture` type: describe its parts in the fixture list (trim, lens, rings, slots) with the real dimensions, then place it. Do not paste the picture and do not draw it by hand. For "one in every coffer", use `coffers('Waffle', 'x')`, `coffers('Waffle', 'z')`, and `y = coffers('Waffle', 'y')`. Check the count in `positions.csv`, and look at a close view (for example a camera that looks up into the ceiling) to compare the drawn fixture with the user's fixture.

## Task: coffered ceilings

- A coffered ceiling is a `waffle` feature in `design.json`: `"shape": "square"` (with `rib`) or `"shape": "round"` (with `d`, the diameter), plus `module` and `depth`. Use `"align": "centre"` for only full coffers, centred. Set `"lit": false` when fixtures in the coffers give the light.
- One item in every coffer: `"x": "coffers('Waffle', 'x')"`, `"z": "coffers('Waffle', 'z')"`. Select some with slices: `coffers('Waffle', 'x')[1::2]`.
- Flush fixtures in the coffers: `fixture` type with `"y": "coffers('Waffle', 'y')"` (the coffer top).
- Pendants in the coffers: `pendant` type with `"from_y": "coffers('Waffle', 'y')"`, and the length with `drop` (from the coffer top) or the shade height with `y`.
- The original view often looks along the ceiling, so deep coffers hide their fixtures. Render a second view that looks up (`--camera`) to check them.
- Check the counts in `positions.csv` (across × deep).

## Task: coves, slats, slots, light wells, luminous ceilings, linear pendants

- Ceiling tray lit from its edges: `cove` with `"kind": "recess"` (`X`, `Z`, `depth`).
- Lit ledge on a wall: `cove` with `"kind": "wall"` (`plane` = the wall, `range`, `y` = top of the ledge, `depth`; add `"ceiling"` for light on the ceiling).
- Slatted or baffle ceiling: `slats` (`X`, `Z`, `y` = bottom of the slats, `h`, `w`, `pitch`, `direction`); `"backlit": true` for light above the slats.
- Luminous or backlit ceiling or wall: `luminous` (`plane` and the area on its two axes; `grid` for panel joints).
- Ceiling lowered at its edges with light grazing the centre: `cove` with `"kind": "perimeter"` (`X`, `Z`, `border`, `drop`).
- Lit slots or a recessed track grid: `slots` (`style` `lens` or `track`, `direction` `x`/`z`/`grid`, `pitch`, `w`, `spot_spacing` for track heads).
- Skylight, laylight, or light well: `lightwell` (`shape` `round` with `x`, `z`, `d`, or `rect` with `X`, `Z`; `depth`). From a low view you may see only its far wall; check it from below.
- Suspended linear direct/indirect fixtures: `linear_pendant` (`x`, `z` lists for rows or grids, `length`, `direction`, `drop` or `y`).
- Give each cove and slat field its own `name`. Use relationships for the areas (for example `inset(gap(...), 3)`), as for the waffle.

## Task: light colour and options

- Colour: `"cct"` (kelvin) on any feature, or at the top of `design.json` for the whole design; `"light_color": [R, G, B]` for a colour. To compare warm and cool options, make a second design file with a different `cct` and render it with `--design ... --out ...`.

## Task: walls, furniture and patterns

- Scallops on a wall from ceiling fixtures: `wallwasher` (`wall`, `range`, `spacing`, `offset`); on arms from the wall: `"mounting": "arm"` with `y`.
- Wall lights that only light up or down: `sconce` with `direction`; add `ceiling` for light on the ceiling above.
- Light from furniture or a stair: add it as a box, then `object_light` (`up`, `down`, `under_y`, `edge`).
- Stitch track (short staggered runs): `track` with `pattern`.
- Laylight or fabric ceiling: `luminous` with `grid` and/or `bands`.
- Dappled light, a window shape, stripes: `projection`.

## Task: switch on lamps that are in the drawing

Table lamps, floor lamps, candles: `glow` at the lamp shade (measure the shade with `zoom` and `measure ... plane` at its height). Use `r` about 1.5 ft for a table lamp.

## Task: track lighting

- Use `track` with `mounting`: `surface`, `recessed` (flush with a trim flange), `trimless` (flush, no trim), or `suspended` (on cables).
- Head size: `aperture` with a name from the README table (ERCO `XS`/`S`/`M`/`L`, Solais `2.5in`/`3in`/`3.75in`) or a diameter (`inch(3)`). If the user names a product, use its aperture from the spec sheet.
- Heads: `spacing` or `count`; aim with `tilt` (from straight down) and `pan` (direction); `beam` sets the pool size.
- Several parallel runs: a list in `at`. Check the head count in `positions.csv` (`track head` rows).

## Task: change the lighting in an existing project

1. Read `<project>/model.json` (surface and box names) and `<project>/design.json`. Before you place a light, check for existing lights at the same place; render prints a warning when two overlap.
2. Add or edit features in `design.json`. The light types and expressions are in the README.
3. `python3 -m glowpoint.render <project>` (add `--linework` if there is no drawing; `--camera view.json` for another view).
4. Check `out/positions.csv` and `out/concept.png`. If the legend covers part of the drawing, set `"legend_at"` (for example `"below"`).

## Task: set up a new image

1. **Camera:** `python3 -m glowpoint.calibrate <image> --known x1,y1,x2,y2,H --out <project>/camera.json --overlay <project>/calibration.png`
   - Read the report. Each vanishing point fit should be below 0.5° for renders (1–3° for hand drawings, with `--tol 2`), and the angles between the found directions should be within 1° of 90.
   - Look at the overlay image: each color must be one real direction of the room.
   - Give `--known` two or three times when you can. If the report says they disagree by more than 10%, find the odd one out (its line shows it) and ask the user for a real dimension if none is reliable.
   - For `--known`, use a vertical with a known height: a door frame (often 7 ft), a column edge from floor to ceiling, or a person (about 5 ft 8 in). Both pixels are on the same vertical edge (it may lean in a three-point image). Find them with `zoom`.
   - One-point images: the lens cannot be found from lines; see the README.
2. **model.json:** start it from the skeleton in the README, with the camera from `camera.json`. You do not need a `design.json` yet.
3. **Surfaces and boxes:** for each corner you need:
   - `python3 -m glowpoint.zoom <image>` to see the whole image with a coarse grid,
   - `python3 -m glowpoint.zoom <image> X0 Y0 X1 Y1` on a box about 100–200 px wide around the corner,
   - read the pixel, confirm it with `--mark X,Y`,
   - `python3 -m glowpoint.measure <project> floor X Y` (or `height`, or `plane`).
   Walls: two floor points on the base line. Ceiling: `height` from a floor point to the ceiling line above it.
   Furniture and columns: `measure <project> box X1 Y1 X2 Y2 [X3 Y3] --top X Y --name NAME [--snap "Left wall"]` prints the box line for model.json.
   Pixels: whole numbers are pixel centres; use fractions (302.5) far away, where one pixel can be more than 0.5 ft.
   Hidden parts: find the limits from the edge that hides them, choose a value inside (usually by symmetry), and write it in the box's `"note"`.
4. **Check:** `python3 -m glowpoint.render <project> --check`, look at `out/check.png`, and zoom on the corners with `--model <project>` (red = model edges). Compare corners in numbers with `measure <project> project X Y Z`. Fix and repeat.

## Coordinates

Feet. X right, Y up (floor = 0), Z into the image. Horizontal surfaces use (x, z), walls use (along, y). Box faces: front (low Z), back, left (low X), right, top.
