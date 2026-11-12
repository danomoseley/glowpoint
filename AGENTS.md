# Instructions for AI agents

glowpoint places lighting concepts on a perspective image of a space. The full reference is [README.md](README.md). This file gives the rules and the work sequence.

## Start of a conversation

When a user gives you this repository (often only a zip, with no other instructions), do this:

1. If it is a zip, unzip it. Work in the folder that has `AGENTS.md`, and run all commands from there.
2. Run `python3 -m glowpoint.doctor`. If it says NOT READY, tell the user what is missing and stop.
3. Show the user the how-to (section "How-to for the user").
4. If the user has not sent a sketch or render yet, ask for it, and for one or two real dimensions. If they sent one, start "Task: set up a new image" (and still ask for a real dimension if they gave none).
5. If the user only wants to try the tool, use the lobby example: copy `projects/lobby` to `local/lobby` and render it with `--linework` (its drawing is not in the repository).

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
13. **After a code change, run the tests:** `python3 tests/test_docs.py`, `python3 tests/test_render.py`, `python3 tests/test_calibrate.py`, and `python3 tests/test_detect.py`.

14. **Draw only with glowpoint.** Never edit or draw on the user's image yourself, and never make an image with an image-generation tool. Show the user only files that glowpoint wrote in the project's `out/` folder, and give the path of each one.
15. **Stop after the model setup.** Send the user `out/check.png` as an image (rule 16), give the main numbers of the calibration report in plain words, and list what you modelled and what you assumed. Remind the user in one or two lines how to check it (edges on the drawn lines, grid in the drawing's directions, 4 ft squares), and **point out the parts you are least sure of** (for example a hidden end of an object, or a scale from an assumed dimension), so the user looks there first. Design lighting only after the user confirms the model: if the model is wrong, every light is wrong.
16. **Send the image after every render.** After each render, put the image file itself into the conversation, so the user sees the picture: `out/concept.png` after a lighting change (or the `--out` name you used), `out/check.png` after a model setup. Display it or attach it as a file, with its path. A file name, a description, or a link to a folder is not enough. Then give a short plain-text list of the lights (type, count, spacing, heights) from `out/positions.csv`.
    **Do not paste JSON** (design.json, model.json, positions.csv) as your answer. The user wants the picture. Show JSON only when the user asks for it.
17. **Show the user the how-to** (the section "How-to for the user" below) at the start of a new conversation (see "Start of a conversation"), and again when the user seems unsure what to ask. Show it as it is written; you can shorten it if the user already knows glowpoint.

Run all commands from the repository root (`python3 -m glowpoint.<tool>`). In a new environment, run `python3 -m glowpoint.doctor` first. If you cannot clone from GitHub (no internet), ask the user to upload the repository as a zip (GitHub: Code → Download ZIP).

## How-to for the user

Show this to the user (rule 17):

> **How to work with glowpoint**
>
> glowpoint draws lighting concepts on your perspective sketch, placed accurately in 3D. It works in two stages.
>
> **Stage 1 – the model.** Send:
> - the **original** sketch or render (not a copy with anything drawn on it),
> - **one or two real dimensions**, for example "the ceiling is 10 ft high" or "the door is 7 ft",
> - anything I cannot see in the image, for example "the coffers are 6 in deep".
>
> I build a simple 3D model of the space and show you a **check image**: your drawing with each surface of the model tinted in a colour, with its name, and a grid of 4 ft squares drawn on it. **Look at it and confirm it, or tell me what is wrong.** Every light depends on it.
>
> **How to check it:**
> - **Edges:** each coloured area must cover exactly its part of the drawing (the floor, each wall, the ceiling, each column or object), with its edges on the drawn lines.
> - **Grid:** the grid lines must run in the same directions as the lines in your drawing (floor joints, ceiling lines, wall bases), and get smaller into the distance at the same rate.
> - **Size:** the squares are 4 ft. A door (about 7 ft) is a little less than two squares high, a desk top (about 2.5 ft) a little more than half a square. If the sizes look wrong, the scale is wrong: give me a real dimension.
> - **Missing or extra:** every object that you want to light, or that lights must refer to, must have its own coloured box (a desk, a column, a bench).
>
> If something is wrong, tell me in plain words, for example: "the ceiling is too low", "the right wall ends at the window", "the desk is longer than that", "there is a column missing at the back", "the ceiling is 12 ft, not 10". I correct the model and send a new check image.
>
> **Stage 2 – the lighting.** Describe what is lit and where the light comes from. Good requests name:
> - **the surface or object:** "the wall behind the desk", "every column", "the ceiling over the aisle";
> - **the kind of light:** downlights, wall wash, cove, slot, track, pendants, sconces, uplights, a luminous ceiling;
> - **how many and where:** "three, equally spaced along the desk", "4 ft apart", "one in every second coffer", "centered between the first two columns";
> - **heights and sizes, if you know them:** "pendants 3 ft above the table", "4 in apertures", "a 6 in deep cove";
> - **colour, if it matters:** "3000 K", "a warm option and a 4000 K option".
>
> Examples:
> - "Wash the back wall from a slot in the ceiling, and put an uplight on every visible column face."
> - "Add a recessed track along the right aisle with size M heads every 5 ft, aimed at the wall."
> - "Replace the drawn coffers with 24 in round coffers, 8 in deep, with a pendant in every third one."
>
> **Changes:** say what to change, for example "move the downlights 1 ft toward the window" or "make the cove 2 ft wider". I keep the rest.
>
> **Other views and options:** ask for "a view from the doorway, looking at the desk" or "option B with all lights at 4000 K". I render it without changing the first design.
>
> **What I show you:** after every change, the image that glowpoint made, in this chat, and a short list of the lights with their positions in feet. If I assume a size, I tell you. If you want the design file (JSON) too, ask for it.
>
> **Limits:** no sloped or curved ceilings yet, no photo-realistic renders, and no footcandle calculations: the images show the lighting concept, not light levels.

## Task: show a specific fixture

When the user gives a fixture (a photo, a product page, a spec sheet), reproduce it with the `fixture` type: describe its parts in the fixture list (trim, lens, rings, slots) with the real dimensions, then place it. Do not paste the picture and do not draw it by hand. For "one in every coffer", use `coffers('Waffle', 'x')`, `coffers('Waffle', 'z')`, and `y = coffers('Waffle', 'y')`. Check the count in `positions.csv`, and look at a close view (for example a camera that looks up into the ceiling) to compare the drawn fixture with the user's fixture.

## Task: coffered ceilings

- **If the drawing already shows coffers,** do not draw new ones over them. Run `python3 -m glowpoint.detect coffers <project> --depth FT --add` (ask the user for the depth), check `out/detect_coffers.png` (the red lines must lie on the drawn coffers), then change the waffle in `design.json` as asked. The detected feature has `"replace": true`, so the drawn coffers are erased and redrawn.

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
5. Send `out/concept.png` to the user as an image, with a short list of the lights (rule 16). Not the JSON.

## Task: set up a new image

0. **Project folder:** make `local/<project name>/` and copy the user's sketch into it unchanged (keep its file extension; `"drawing"` in model.json is its file name). If the user has not given a real dimension (a ceiling height, a door height, a known object), ask for one before the camera setup.
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
5. **Coffers in the drawing:** if the ceiling shows coffers, run `python3 -m glowpoint.detect coffers <project> --depth FT --add` and check `out/detect_coffers.png` (see "Task: coffered ceilings").
6. **Stop and send the user** `out/check.png` as an image, with the calibration result and what you modelled and assumed (rules 15 and 16). Wait for confirmation.

## Coordinates

Feet. X right, Y up (floor = 0), Z into the image. Horizontal surfaces use (x, z), walls use (along, y). Box faces: front (low Z), back, left (low X), right, top.
