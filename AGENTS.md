# Instructions for AI agents

glowpoint places lighting concepts on a perspective image of a space. The full reference is [README.md](README.md). This file gives the rules and the work sequence.

## Start of a conversation

When a user gives you this repository (often only a zip, with no other instructions), do this:

1. If it is a zip, unzip it. Work in the folder that has `AGENTS.md`, and run all commands from there.
2. Run `python3 -m glowpoint.doctor`. If it says NOT READY, tell the user what is missing and stop.
3. Show the user Part A of the how-to (section "How-to for the user"). Do not show the other parts yet.
4. If the user has not sent a sketch or render yet, ask for it, and for one or two real dimensions. If they sent one, start "Task: set up a new image" (and still ask for a real dimension if they gave none).
5. If the user only wants to try the tool, use the lobby example: copy `projects/lobby` to `local/lobby` and render it with `--linework` (its drawing is not in the repository).

## When the user sends an updated zip

The user may send a newer version of glowpoint in the middle of a session. A zip from GitHub does **not** contain the user's projects (`local/` is not in the repository), so never replace or delete the old folder.

1. Unzip the new zip into a **new** folder (for example `glowpoint-new/`), not over the old one. The zip from GitHub always unzips to `glowpoint-main/`, so rename one of them first.
2. Run `python3 -m glowpoint.doctor` in the new folder. Compare its version with the old one (`glowpoint/__init__.py`).
3. Copy the user's projects from the old `local/` folder into the new `local/` folder (the whole project folders, with the drawings, model.json, design.json, and any `types/` and `fixtures.json`), and `local/patches/` if it exists. Do **not** copy `local/.baseline/`: the new folder has its own.
4. Read the new `AGENTS.md` again: the rules can change. Read the new entries in `CHANGELOG.md`, and tell the user in two or three lines what is new that matters to them.
5. Render the current project again in the new folder (with `--check` if the project is being set up). Compare the light counts in `positions.csv` with the last render in the old folder. If something changed, tell the user and send the new image.
6. If you made core code changes in the old folder (rule 18), first check that each one has a patch: run `python3 -m glowpoint.patch status` in the old folder, and if it shows changes that are not in a patch yet, run `patch make` there now. Then look in `CHANGELOG.md` to see if the new version already has the changes. If not, apply each patch in the new folder: `python3 -m glowpoint.patch apply local/patches/<file>.patch`, then run the tests. If a patch does not apply, nothing in the new folder changes: tell the user, still give them the patch file to send to the maintainer, and make the change again in the new folder only if it is still necessary.
7. Continue only in the new folder. Keep the old folder until the user confirms that the new version works.

If the new version stops with an error on the user's project, tell the user, continue in the old folder, and send the error so the code can be fixed.

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
12. **Before every commit and push, update README.md, AGENTS.md, and CHANGELOG.md** (raise the version in `glowpoint/__init__.py` for a change in behaviour; a session that cannot push does not, see rule 18) so they describe every change: new types, options, expressions, tools, and behaviour. `python3 tests/test_docs.py` checks this. Turn on the pre-push hook once in each clone with `git config core.hooksPath .githooks`: it runs the documentation test and all tests, and stops a push that fails.
13. **After a code change, run the tests:** `python3 tests/test_docs.py`, `python3 tests/test_render.py`, `python3 tests/test_calibrate.py`, `python3 tests/test_detect.py`, and `python3 tests/test_patch.py`.

14. **Draw only with glowpoint.** Never edit or draw on the user's image yourself, and never make an image with an image-generation tool. Show the user only files that glowpoint wrote in the project's `out/` folder (and the example picture `docs/menu.png`), and give the path of each one.
15. **Stop after the model setup.** Send the user `out/check.png` as an image (rule 16), give the main numbers of the calibration report in plain words, and list what you modelled and what you assumed. Ask the short question of Part B of the how-to (the full checklist only if the user is unsure), and **point out the parts you are least sure of** (for example a hidden end of an object, or a scale from an assumed dimension), so the user looks there first. Design lighting only after the user confirms the model: if the model is wrong, every light is wrong.
16. **Send the image after every render.** After each render, put the image file itself into the conversation, so the user sees the picture: `out/concept.png` after a lighting change (or the `--out` name you used), `out/check.png` after a model setup. Display it or attach it as a file, with its path. A file name, a description, or a link to a folder is not enough. Then give a short plain-text list of the lights (type, count, spacing, heights) from `out/positions.csv`, and at most one tip about an option the user has not used yet (rule 17).
    **Do not paste JSON** (design.json, model.json, positions.csv) as your answer. The user wants the picture. Show JSON only when the user asks for it.
17. **Give the how-to in small parts** (section "How-to for the user"): Part A at the start, Part B with the first check image, Part C when the model is confirmed, the menu when the user asks what is available, and at most one tip after each render. The user must feel that glowpoint is simple, and still learn every option. Show the parts as they are written; shorten them if the user already knows glowpoint.

Run all commands from the repository root (`python3 -m glowpoint.<tool>`). In a new environment, run `python3 -m glowpoint.doctor` first. If you cannot clone from GitHub (no internet), ask the user to upload the repository as a zip (GitHub: Code → Download ZIP).

18. **Core code changes when you cannot push (for example in ChatGPT or another sandbox).** You may change the code in `glowpoint/` when a project needs a fix or a feature that a plugin (rule 4) cannot give. **First tell the user, in plain words, and ask before you start.** Most users are designers, not programmers: do not say "patch", "core", "commit", or "repository" to them. Say something like:

    > "This needs a change to the glowpoint program itself, not only to your project. I can make the change here, and it will work in this conversation. At the end I will give you a small text file that lists the changes. Please send it to the person who looks after glowpoint, so they can add it for everybody. It does not contain your drawings. Until they add it, a new conversation will not have this change. Do you want me to try?"

    For a large change (for example sloped ceilings or light-level calculations), say that it can take a long time and may not work well, and offer a second choice: write a short description of what is needed, for the user to send to the person who looks after glowpoint. Then:
    1. Make the change for everybody, not only for this project. Update README.md and AGENTS.md, and run the tests (rule 13). **Do not change the version number or CHANGELOG.md.** Only the maintainer sets them, when the patch goes in; two sessions would otherwise both choose the same next number.
    2. Make a patch: `python3 -m glowpoint.patch make "short title" --why "what was wrong and what you changed" --changelog "the line for the changelog"`. If you changed the version or CHANGELOG.md by mistake, the tool leaves them out and moves the new changelog lines into the patch header. It compares with the original files that `doctor` saved at the start (or give `--base` with the uploaded zip, for example `--base /mnt/data/glowpoint-main.zip`), runs the tests, and writes `local/patches/<date>-<title>.patch`.
    3. Send the patch file to the user as a file they can download (not pasted text), and tell them: "Here is the file with the changes to the glowpoint program. Please send it (for example by email) to the person who looks after glowpoint, or attach it to a new issue at https://github.com/danomoseley/glowpoint/issues. It does not contain your drawings. Until it is added, a new conversation will not have this change, so keep this conversation if you need the change again soon."
    4. Never say that the change is in glowpoint or on GitHub. It is only in this session until the maintainer applies it. `python3 -m glowpoint.patch status` shows what you changed.
    5. Make one patch for each separate change when you can, so the maintainer can accept them one at a time. Never put the user's drawings or projects in a patch (the tool leaves out `local/` and drawings).

    For the maintainer, or an agent that can push: `python3 -m glowpoint.patch apply FILE.patch`, read the change, and run all tests. Then raise the version in `glowpoint/__init__.py` to the next number after the current one (not the number in the patch header, which is the version the session started from), add the changelog lines from the header under it, and commit and push (the pre-push hook runs the tests). Apply several patches one at a time, each with its own version, or together under one version.

## Menu for the user: lights, ceilings, and plugins

Send the picture `docs/menu.png` (one labelled example of each type) with this list. Show this list when the user asks what glowpoint can draw, what fixture types or options there are, or seems unsure what to ask for (rule 17). The names in brackets are the types in `design.json`; you can leave them out for the user. When the user asks about one type, give its options from that type's section in the README, in plain words, with the default values.

> **Lights**
> - Downlights: round symbols in the ceiling, with a beam and a pool of light (`downlight`)
> - Wallwashers: a row, recessed in the ceiling or on arms, with scallops on the wall (`wallwasher`)
> - Wall wash from the top of a wall, optionally from a slot in the ceiling (`wash`)
> - Sconces: light up, down, or both, optionally onto the ceiling (`sconce`)
> - In-floor uplights that graze a wall or a column face (`uplight`)
> - Track: surface, recessed, trimless, or suspended, with aimable heads in real aperture sizes (ERCO XS–L, Solais 2–4 in), tilt and aim, and stitch patterns (`track`)
> - Ceiling slots: lit lines or track channels with spot heads, as lines or a grid (`slots`)
> - Pendants: on a cord from the ceiling or from inside coffers, with a pool of light (`pendant`)
> - Linear pendants: direct light down and indirect light up onto the ceiling (`linear_pendant`)
> - A specific fixture from a photo or spec sheet, drawn from its parts: trim, lens, rings, slots (`fixture`)
> - Light from furniture or architecture: up onto the ceiling, down onto the floor, an LED edge, under a shelf (`object_light`)
> - Projected patterns: dappled light through leaves, a window shape, stripes (`projection`)
> - A glow at a lamp that is in the drawing: a table lamp, floor lamp, or candle (`glow`)
>
> **Ceilings and architecture with light**
> - Coffers: square or round, any size and depth, lit or with a fixture or pendant in each (`waffle`); I can also find coffers that are already in your drawing
> - Coves: a recessed ceiling tray, or a lit ledge on a wall (`cove`)
> - Slats or baffles below a ceiling, optionally lit from above (`slats`)
> - Light wells and skylights: round or rectangular, with a glowing top and light on their walls (`lightwell`)
> - Luminous ceilings or walls: a glowing area, with panel joints or bands (`luminous`)
>
> **For every light:** colour temperature (for example 2700 K, 3000 K, 4000 K; diagrammatic colours, good for warm and cool options), counts and spacing tied to the architecture ("centred on the desk", "every 4 ft", "in every second coffer"), other views of the same design, design options side by side, and a legend.
>
> **Plugins: things you can add.** If you need something that is not on this list, I can write a plugin, a small file in your project, without changing glowpoint:
> - **a new kind of light**, for example an LED strip between two columns, a fixture family your office uses often, or a special symbol;
> - **a new ceiling or architectural element** that changes the 3D model, for example a beam grid, a bulkhead, or a stepped soffit made of flat surfaces;
> - **new placement words**, for example "between column A and column B" or "on every second window".
> A fixture from a spec sheet usually needs no plugin: I describe it with the fixture type, and I can save it in a fixture list for the project so you can reuse it by name.
> A plugin cannot change how glowpoint reads the drawing or the camera, cannot make sloped or curved surfaces, and cannot calculate light levels. Those need a change to the glowpoint program itself. I tell you before I try one, and afterwards I give you a small file to send to the person who looks after glowpoint, so that everybody gets the change.

## How-to for the user

**Goal: the user must feel that glowpoint is simple, and still learn every option.** So give the information in small parts, at the moment it is useful, never all at once:

| When | Show |
|---|---|
| Start of a conversation | Part A (short), with the picture `docs/menu.png` |
| With the first check image | Part B |
| When the user confirms the model | Part C |
| The user asks what is available, or seems unsure | "Menu for the user", with `docs/menu.png` |
| The user asks about one kind of light | That type's options from the README, in plain words, with defaults |
| After each render | The image, a short list of the lights, and **at most one** short tip about an option that fits this design and that the user has not used yet (for example "A recessed track version can go next to this one as option B" or "I can find the coffers that are in your drawing"). Do not repeat a tip. |

**Who the users are:** professional lighting designers, highly skilled at their craft. They know lighting terms, fixtures, and products better than you. Never explain lighting to them, and never coach them on how to describe a design. Use their terms (aiming, beam spread, scallop, aperture, CCT, grazing, cut-off). They are usually not programmers, so do not explain the software either.

Keep your own messages short and plain. Do not show JSON, file names, commands, or type names unless the user asks for them. When they ask for something that glowpoint cannot draw exactly (a product, a beam angle, an optic), say so in one line and say what you drew instead.

### Part A: welcome (start of a conversation)

> **glowpoint** draws lighting concepts on your perspective sketch, placed accurately in 3D.
>
> 1. Send me the **original** sketch or render, and **one real dimension** (for example "the ceiling is 10 ft").
> 2. I send back a **check image** of the 3D model. You confirm it or tell me what is wrong.
> 3. Then describe the lighting in plain words, for example "wash the back wall and put pendants over the desk". I send the drawing with the lights.
>
> The picture shows the lights and ceilings that I can draw. Ask "what can you draw?" at any time for the list with options.

Send `docs/menu.png` as an image with Part A (it is the picture that Part A refers to).

### Part B: checking the model (with the check image)

Send the check image with only this short question:

> Here is the 3D model over your drawing: each surface tinted, with its name, and a 4 ft grid. **Do the coloured areas line up with your drawing, and do the 4 ft squares look the right size?** Reply "yes", or tell me what is wrong in plain words ("the ceiling is too low", "the desk is longer", "a column is missing at the back").

Then name the one or two parts you are least sure of (rule 15). Show the full checklist below only if the user is unsure what to look for, or confirms a model that looks wrong to you:

> - **Edges:** each coloured area covers exactly its part of the drawing, with its edges on the drawn lines.
> - **Grid:** the grid lines run in the same directions as the lines in your drawing, and get smaller into the distance at the same rate.
> - **Size:** the squares are 4 ft. A door (about 7 ft) is a little less than two squares high. If sizes look wrong, give me another real dimension.
> - **Missing objects:** everything that you want to light, or that lights refer to, has its own coloured box.

### Part C: lighting (when the user confirms the model)

> The model is ready. Describe the lighting as you would mark up a sketch for a colleague: what is lit, from where, the fixture type, counts and spacing, mounting heights, apertures, beam spreads, aiming, and CCT. Give positions relative to the architecture ("centred on the desk", "18 in off the wall", "every second coffer"), and the lights follow when the model changes. Ask for changes, other views, or options at any time; I keep the rest. If you leave out a value, I use a usual one and tell you which.
>
> It draws a diagrammatic concept, not a photometric render: no sloped or curved ceilings yet, and no illuminance calculations.

## Task: show a specific fixture

When the user gives a fixture (a photo, a product page, a spec sheet), reproduce it with the `fixture` type: describe its parts in the fixture list (trim, lens, rings, slots) with the real dimensions, then place it. Do not paste the picture and do not draw it by hand. For "one in every coffer", use `coffers('Waffle', 'x')`, `coffers('Waffle', 'z')`, and `y = coffers('Waffle', 'y')`. Check the count in `positions.csv`, and look at a close view (for example a camera that looks up into the ceiling) to compare the drawn fixture with the user's fixture.

## Task: coffered ceilings

**When to use the coffer detector (`glowpoint.detect coffers`):** when the original drawing shows a grid of coffers on the ceiling (look at the drawing during the setup; setup step 5), or when the user asks to change or light coffers that are in the drawing. Do not use it to add coffers to a flat ceiling: then write a `waffle` feature yourself (below). Never draw new coffers over drawn ones without `"replace": true`.

1. **First the model:** the camera and the `Ceiling` surface must match the drawing, and the user should have confirmed `out/check.png`. The detector looks only inside that surface, so a wrong ceiling gives a wrong result.
2. **Ask for the depth** (a line drawing seldom shows it). If the user does not know, use 6 in and say so.
3. **Run:** `python3 -m glowpoint.detect coffers <project> --depth FT --add`. It prints the waffle feature (module, rib or diameter, area) and puts it in `design.json` as the layer "Coffers (detected)", with `"replace": true` (the drawn coffers are erased and redrawn) and `"lit": false`.
4. **Check `out/detect_coffers.png`:** the red lines must lie on the drawn coffer edges across the whole grid, not only near the middle. Send this image to the user (rule 16) with the module, rib or diameter, and the number of coffers across × deep, and ask them to confirm.
5. **If the red lines are off, or it says "no coffers detected":** (a) check the `Ceiling` surface first (the usual cause); (b) run again with `--area X0 X1 Z0 Z1` on a clear part of the ceiling (for example without a light fixture or a beam in it). Running again replaces the earlier detected layer. (c) If it still fails, measure it yourself: get the pixels of two rib lines several coffers apart with `glowpoint.zoom`, convert them with `python3 -m glowpoint.measure <project> plane PX PY Y <ceiling height>`, divide by the number of modules, and write the `waffle` feature by hand with `"replace": true`. Tell the user which way you used.
6. **Then do what the user asked:** change the depth or shape, or add fixtures with `coffers()` (below). Render and send the image.

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
