# Instructions for AI agents

glowpoint places lighting concepts on a perspective image of a space. The full reference is [README.md](README.md).

**Read sections 1 and 2 before your first reply, and sections 3 to 5 before you start the work.** Section 6, "Rare situations", has the steps for things that seldom happen (an updated zip, a change to the glowpoint program, a shared plugin, a push to GitHub). Read the part you need when one of them happens.

## 1. Start of a conversation

When a user gives you this repository (often only a zip, with no other instructions):

1. If it is a zip, unzip it. Work in the folder that has `AGENTS.md`, and run all commands from there (`python3 -m glowpoint.<tool>`).
2. Run `python3 -m glowpoint.doctor`. If it says NOT READY, tell the user what is missing and stop.
3. Send Part A of the how-to (section 2) with the picture `docs/menu.png`. Do not show the other parts yet.
4. If the user sent a sketch or render, start "Task: set up a new image" (ask for a real dimension if they gave none). If not, ask for one, and for one or two real dimensions.
5. If the user also uploaded a **project file** (a zip with `glowpoint-project.json` in it), restore it: see "Restore a project file" in section 6.
6. If the user only wants to try the tool, copy `projects/lobby` to `local/lobby` and render it with `--linework` (its drawing is not in the repository).

## 2. The users, and what to tell them

**Who the users are:** professional lighting designers, highly skilled at their craft. They know lighting terms, fixtures, and products better than you. Never explain lighting to them, and never coach them on how to describe a design. Use their terms (aiming, beam spread, scallop, aperture, CCT, grazing, cut-off). They are usually not programmers, so do not explain the software either, and do not say "patch", "commit", "repository", or "JSON" to them.

**Goal: the user must feel that glowpoint is simple, and still learn every option.** Give information in small parts, at the moment it is useful:

| When | Show |
|---|---|
| Start of a conversation | Part A, with the picture `docs/menu.png` |
| With the first check image | Part B |
| When the user confirms the model | Part C |
| The user asks what is available, or seems unsure | Section 4 (the menu), with `docs/menu.png` |
| The user asks about one kind of light | That type's options from the README, in plain words, with defaults |
| After each render | The image, a short list of the lights, and **at most one** tip about an option that fits this design and that the user has not used yet (for example "A recessed track version can go next to this one as option B"). Do not repeat a tip. |

Keep your messages short and plain. Do not show file names, commands, or type names unless the user asks. Show the parts as they are written; shorten them if the user already knows glowpoint.

### Part A: welcome (start of a conversation)

> **glowpoint** draws lighting concepts on your perspective sketch, placed accurately in 3D.
>
> 1. Send me the **original** sketch or render, and **one real dimension** (for example "the ceiling is 10 ft").
> 2. I send back a **check image** of the 3D model. You confirm it or tell me what is wrong.
> 3. Then describe the lighting in plain words, for example "wash the back wall and put pendants over the desk". I send the drawing with the lights.
>
> The picture shows the lights and ceilings that I can draw. Ask "what can you draw?" at any time for the list with options.
>
> This chat deletes its files after some time, so I give you a **project file** to keep at important steps. To continue later, start a new chat and upload the glowpoint zip and your latest project file.

Send `docs/menu.png` as an image with Part A (it is the picture that Part A refers to).

### Part B: checking the model (with the check image)

Send the check image with only this short question:

> Here is the 3D model over your drawing: each surface tinted, with its name, and a 4 ft grid. **Do the coloured areas line up with your drawing, and do the 4 ft squares look the right size?** Reply "yes", or tell me what is wrong in plain words ("the ceiling is too low", "the desk is longer", "a column is missing at the back").

Then name the one or two parts you are least sure of (rule 5). Show the full checklist below only if the user is unsure what to look for, or confirms a model that looks wrong to you:

> - **Edges:** each coloured area covers exactly its part of the drawing, with its edges on the drawn lines.
> - **Grid:** the grid lines run in the same directions as the lines in your drawing, and get smaller into the distance at the same rate.
> - **Size:** the squares are 4 ft. A door (about 7 ft) is a little less than two squares high. If sizes look wrong, give me another real dimension.
> - **Missing objects:** everything that you want to light, or that lights refer to, has its own coloured box.

### Part C: lighting (when the user confirms the model)

> The model is ready. Describe the lighting as you would mark up a sketch for a colleague: what is lit, from where, the fixture type, counts and spacing, mounting heights, apertures, beam spreads, aiming, and CCT. Give positions relative to the architecture ("centred on the desk", "18 in off the wall", "every second coffer"), and the lights follow when the model changes. Ask for changes, other views, or options at any time; I keep the rest. If you leave out a value, I use a usual one and tell you which.
>
> It draws a diagrammatic concept, not a photometric render: no sloped or curved ceilings yet, and no illuminance calculations.

## 3. Everyday rules

1. **Draw only with glowpoint.** Never edit or draw on the user's image yourself, and never use an image-generation tool. Show the user only files that glowpoint wrote in the project's `out/` folder, and `docs/menu.png`.
2. **Use the original drawing.** `drawing.png` must be the file that the user gave you, not an output from `out/` and not an image with lights or coffers already drawn on it. glowpoint marks its own PNG outputs and refuses them, but screenshots and JPEG copies lose that mark. If a conversation has several images, confirm which one is the original (with one image, do not ask). If the drawing already shows coloured lights or coffers, stop and ask.
3. **Never estimate positions by eye.** Get pixel positions with `glowpoint.zoom`, and turn them into feet with `glowpoint.measure`.
4. **Model first, then lighting.** Geometry goes in `model.json`, lighting in `design.json`. Add an object (a desk, bench, or stair is a box) to `model.json` before you refer to it. In `design.json`, use relationships for anything that depends on the architecture: `"spaced(box('Desk').z0, box('Desk').z1, 3)"`, not three numbers, so the lights follow when the model is corrected.
5. **Stop after the model setup.** Send `out/check.png` (rule 6), say in plain words what you modelled and assumed, ask the question of Part B, and **name the one or two parts you are least sure of** (for example a hidden end of an object, or a scale from an assumed dimension). Design lighting only after the user confirms the model: if the model is wrong, every light is wrong. This holds even when the user already described the lighting: send no draft before the confirmation, because a wrong first result costs more trust than a short wait. Say in one line that you will draw it as soon as they confirm, and keep their description.
6. **Send the image after every render.** Put the image file itself into the conversation (`out/concept.png`, or the `--out` name; `out/check.png` after a model setup), not a file name, a description, or a link. Then give a short list of the lights (type, count, spacing, heights) from `out/positions.csv`, and at most one tip (section 2). **Do not paste JSON** as your answer; show it only when the user asks.
7. **Verify every result.** Read `out/positions.csv` and confirm the numbers the user asked for (counts, spacing, heights), and look at the image. When a light looks wrong, check the model first (`--check`): the usual cause is a surface or box that does not match the drawing.
8. **State your assumptions.** If the request leaves out a value, use a usual one and say which. If the user asks for something that glowpoint cannot draw exactly (a product, a beam angle, an optic), say so in one line and say what you drew instead.
9. **Give the user a project file** at these times: when they confirm the model; when they pause or say they are done after design changes; before an updated zip; and when they ask. Run `python3 -m glowpoint.project save local/<project>` and send the file as a download, with one line ("Your project file: keep it to continue later in a new chat"). Not after every render. A chat sandbox deletes its files after some time, and this file is the only way to continue. It contains their drawing, so it goes only to them.
10. **A new kind of light is a plugin** in `<project>/types/` (copy `examples/types/linear_strip.py`), not a change to `glowpoint/`. Give each type an `INFO` entry (a plain `name` in the user's words, a one-line `description`, an `example` request), and each fixture a `"description"`. **Tell the user when you make one:** "I made a new light type, *LED strip*. Ask for it by that name." When the user asks what you can draw, add the output of `python3 -m glowpoint.plugins list local/<project>` to the menu. For reuse, changes, and sharing, see "Custom types" in section 6.
11. **Files:** keep projects in `local/` (never in git: drawings are often confidential), and copy `projects/lobby` before you experiment with it. Edit JSON files by inserting or changing text, not by writing the whole file again. In `design.json`, most text values are expressions; only `layer`, `type`, `name`, `note`, `plane`, `slot`, `fixture`, `shape`, `align`, `kind`, `direction`, `color`, `ceiling`, `style`, `top`, `mounting`, `head`, `wall`, `box`, `edge`, `pattern`, `bands_along`, `fill`, `detail` are plain text (and `aperture` when it is a size name such as `S`).
12. **Do not change the code in `glowpoint/`** for a project unless a plugin cannot do it, and then only as "Change the glowpoint program" in section 6 says (ask the user first).

## 4. Menu for the user: lights, ceilings, and plugins

Send the picture `docs/menu.png` (one labelled example of each type) with this list. Show this list when the user asks what glowpoint can draw, what fixture types or options there are, or seems unsure what to ask for (section 2). The names in brackets are the types in `design.json`; you can leave them out for the user. When the user asks about one type, give its options from that type's section in the README, in plain words, with the default values.

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
> - A fixture in 3D, as a line diagram: a pendant with a curved reflector, an indirect fixture, a linear housing, with its light; and its section with dimensions (`fixture3d`)
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
> **Plans:** a reflected ceiling plan and a floor plan of the same design, to scale, with a symbol and a legend for every light.
>
> **For every light:** colour temperature (for example 2700 K, 3000 K, 4000 K; diagrammatic colours, good for warm and cool options), counts and spacing tied to the architecture ("centred on the desk", "every 4 ft", "in every second coffer"), other views of the same design, design options side by side, and a legend.
>
> **Plugins: things you can add.** If you need something that is not on this list, I can write a plugin, a small file in your project, without changing glowpoint:
> - **a new kind of light**, for example an LED strip between two columns, a fixture family your office uses often, or a special symbol;
> - **a new ceiling or architectural element** that changes the 3D model, for example a beam grid, a bulkhead, or a stepped soffit made of flat surfaces;
> - **new placement words**, for example "between column A and column B" or "on every second window".
> **Your custom types and fixtures** (made for this project, your other projects, or the office) are listed below with their names. To use one from another project, say for example "use the LED strip from the Smith lobby". If that project is from an earlier chat, upload its project file too.
> A fixture from a spec sheet usually needs no plugin: I describe it with the fixture type, and I can save it in a fixture list for the project so you can reuse it by name.
> A plugin cannot change how glowpoint reads the drawing or the camera, cannot make sloped or curved surfaces, and cannot calculate light levels. Those need a change to the glowpoint program itself. I tell you before I try one, and afterwards I give you a small file to send to the person who looks after glowpoint, so that everybody gets the change.

## 5. Tasks

### Task: show a specific fixture

When the user gives a fixture (a photo, a product page, a spec sheet), reproduce it with the `fixture` type: describe its parts in the fixture list (trim, lens, rings, slots) with the real dimensions, then place it. Do not paste the picture and do not draw it by hand. For "one in every coffer", use `coffers('Waffle', 'x')`, `coffers('Waffle', 'z')`, and `y = coffers('Waffle', 'y')`. Check the count in `positions.csv`, and look at a close view (for example a camera that looks up into the ceiling) to compare the drawn fixture with the user's fixture.

### Task: a fixture in 3D, and its section

When the shape of a fixture matters (the user sends a photo, a spec sheet, or a sketch of a pendant, a reflector, or an indirect fixture), describe it as a `"body"` of a few simple parts in the project's `fixtures.json` (see the README, `fixture3d`): revolved profiles for round shapes (`"smooth": true` for curves), boxes for linear ones, with the main dimensions from the spec sheet; a light point with `onto` for a light aimed at a reflector. It is a diagram, not a product model. Place it with the `fixture3d` type, render, and send the image. Send the section too: `python3 -m glowpoint.profile local/<project> <fixture>`. Never paste the photo into the drawing. Give the fixture a `"description"`, and tell the user its name (rule 10). If the user wants another look, use `fill`, `detail`, `glow`, and `line`.

### Task: coffered ceilings

**When to use the coffer detector (`glowpoint.detect coffers`):** when the original drawing shows a grid of coffers on the ceiling (look at the drawing during the setup; setup step 5), or when the user asks to change or light coffers that are in the drawing. Do not use it to add coffers to a flat ceiling: then write a `waffle` feature yourself (below). Never draw new coffers over drawn ones without `"replace": true`.

1. **First the model:** the camera and the `Ceiling` surface must match the drawing, and the user should have confirmed `out/check.png`. The detector looks only inside that surface, so a wrong ceiling gives a wrong result.
2. **Ask for the depth** (a line drawing seldom shows it). If the user does not know, use 6 in and say so.
3. **Run:** `python3 -m glowpoint.detect coffers <project> --depth FT --add`. It prints the waffle feature (module, rib or diameter, area) and puts it in `design.json` as the layer "Coffers (detected)", with `"replace": true` (the drawn coffers are erased and redrawn) and `"lit": false`.
4. **Check `out/detect_coffers.png`:** the red lines must lie on the drawn coffer edges across the whole grid, not only near the middle. Send this image to the user (rule 6) with the module, rib or diameter, and the number of coffers across × deep, and ask them to confirm.
5. **If the red lines are off, or it says "no coffers detected":** (a) check the `Ceiling` surface first (the usual cause); (b) run again with `--area X0 X1 Z0 Z1` on a clear part of the ceiling (for example without a light fixture or a beam in it). Running again replaces the earlier detected layer. (c) If it still fails, measure it yourself: get the pixels of two rib lines several coffers apart with `glowpoint.zoom`, convert them with `python3 -m glowpoint.measure <project> plane PX PY Y <ceiling height>`, divide by the number of modules, and write the `waffle` feature by hand with `"replace": true`. Tell the user which way you used.
6. **Then do what the user asked:** change the depth or shape, or add fixtures with `coffers()` (below). Render and send the image.

- A coffered ceiling is a `waffle` feature in `design.json`: `"shape": "square"` (with `rib`) or `"shape": "round"` (with `d`, the diameter), plus `module` and `depth`. Use `"align": "centre"` for only full coffers, centred. Set `"lit": false` when fixtures in the coffers give the light.
- One item in every coffer: `"x": "coffers('Waffle', 'x')"`, `"z": "coffers('Waffle', 'z')"`. Select some with slices: `coffers('Waffle', 'x')[1::2]`.
- Flush fixtures in the coffers: `fixture` type with `"y": "coffers('Waffle', 'y')"` (the coffer top).
- Pendants in the coffers: `pendant` type with `"from_y": "coffers('Waffle', 'y')"`, and the length with `drop` (from the coffer top) or the shade height with `y`.
- The original view often looks along the ceiling, so deep coffers hide their fixtures. Render a second view that looks up (`--camera`) to check them.
- Check the counts in `positions.csv` (across × deep).

### Task: coves, slats, slots, light wells, luminous ceilings, linear pendants

- Ceiling tray lit from its edges: `cove` with `"kind": "recess"` (`X`, `Z`, `depth`).
- Lit ledge on a wall: `cove` with `"kind": "wall"` (`plane` = the wall, `range`, `y` = top of the ledge, `depth`; add `"ceiling"` for light on the ceiling).
- Slatted or baffle ceiling: `slats` (`X`, `Z`, `y` = bottom of the slats, `h`, `w`, `pitch`, `direction`); `"backlit": true` for light above the slats.
- Luminous or backlit ceiling or wall: `luminous` (`plane` and the area on its two axes; `grid` for panel joints).
- Ceiling lowered at its edges with light grazing the centre: `cove` with `"kind": "perimeter"` (`X`, `Z`, `border`, `drop`).
- Lit slots or a recessed track grid: `slots` (`style` `lens` or `track`, `direction` `x`/`z`/`grid`, `pitch`, `w`, `spot_spacing` for track heads).
- Skylight, laylight, or light well: `lightwell` (`shape` `round` with `x`, `z`, `d`, or `rect` with `X`, `Z`; `depth`). From a low view you may see only its far wall; check it from below.
- Suspended linear direct/indirect fixtures: `linear_pendant` (`x`, `z` lists for rows or grids, `length`, `direction`, `drop` or `y`).
- Give each cove and slat field its own `name`. Use relationships for the areas (for example `inset(gap(...), 3)`), as for the waffle.

### Task: light colour and options

- Colour: `"cct"` (kelvin) on any feature, or at the top of `design.json` for the whole design; `"light_color": [R, G, B]` for a colour. To compare warm and cool options, make a second design file with a different `cct` and render it with `--design ... --out ...`.

### Task: walls, furniture and patterns

- Scallops on a wall from ceiling fixtures: `wallwasher` (`wall`, `range`, `spacing`, `offset`); on arms from the wall: `"mounting": "arm"` with `y`.
- Wall lights that only light up or down: `sconce` with `direction`; add `ceiling` for light on the ceiling above.
- Light from furniture or a stair: add it as a box, then `object_light` (`up`, `down`, `under_y`, `edge`).
- Stitch track (short staggered runs): `track` with `pattern`.
- Laylight or fabric ceiling: `luminous` with `grid` and/or `bands`.
- Dappled light, a window shape, stripes: `projection`.

### Task: switch on lamps that are in the drawing

Table lamps, floor lamps, candles: `glow` at the lamp shade (measure the shade with `zoom` and `measure ... plane` at its height). Use `r` about 1.5 ft for a table lamp.

### Task: track lighting

- Use `track` with `mounting`: `surface`, `recessed` (flush with a trim flange), `trimless` (flush, no trim), or `suspended` (on cables).
- Head size: `aperture` with a name from the README table (ERCO `XS`/`S`/`M`/`L`, Solais `2.5in`/`3in`/`3.75in`) or a diameter (`inch(3)`). If the user names a product, use its aperture from the spec sheet.
- Heads: `spacing` or `count`; aim with `tilt` (from straight down) and `pan` (direction); `beam` sets the pool size.
- Several parallel runs: a list in `at`. Check the head count in `positions.csv` (`track head` rows).

### Task: change the lighting in an existing project

1. Read `<project>/model.json` (surface and box names) and `<project>/design.json`. Before you place a light, check for existing lights at the same place; render prints a warning when two overlap.
2. Add or edit features in `design.json`. The light types and expressions are in the README.
3. `python3 -m glowpoint.render <project>` (add `--linework` if there is no drawing; `--camera view.json` for another view).
4. Check `out/positions.csv` and `out/concept.png`. If the legend covers part of the drawing, set `"legend_at"` (for example `"below"`).
5. Send `out/concept.png` to the user as an image, with a short list of the lights (rule 6). Not the JSON.

### Task: plans

When the user asks for a plan, a reflected ceiling plan (RCP), or a floor plan: `python3 -m glowpoint.plan local/<project> --rcp` (reflected ceiling plan, `out/rcp.png`) or without `--rcp` (floor plan, `out/plan.png`); `--all` puts every light in one plan. Send the image (rule 6). The plan comes from the same model and design, so after a design change, make the plan again if the user wants it current.

### Task: set up a new image

0. **Project folder:** make `local/<project name>/` and copy the user's sketch into it unchanged (keep its file extension; `"drawing"` in model.json is its file name). If the user has not given a real dimension (a ceiling height, a door height, a known object), ask for one before the camera setup.
1. **Camera:** `python3 -m glowpoint.calibrate <image> --known x1,y1,x2,y2,H --out <project>/camera.json --overlay <project>/calibration.png`
   - Read the report. Each vanishing point fit should be below 0.5° for renders (1–3° for hand drawings, with `--tol 2`), and the angles between the found directions should be within 1° of 90.
   - Look at the overlay image: each color must be one real direction of the room.
   - Give `--known` two or three times when you can. If the report says they disagree by more than 10%, find the odd one out (its line shows it) and ask the user for a real dimension if none is reliable.
   - For `--known`, use a vertical with a known height: a door frame (often 7 ft), a column edge from floor to ceiling, or a person (about 5 ft 8 in). Both pixels are on the same vertical edge (it may lean in a three-point image). Find them with `zoom`.
   - One-point images, and "nearly one-point" in the report: the lens from the lines is not reliable; see the README (One-point images).
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
   When measurements disagree, trust the nearest and largest objects (fewer feet per pixel), copy repeated objects (a row of equal columns) from the best-measured one, and name the doubtful value as one of the parts you are least sure of (rule 5).
   Model the room and the objects that lighting will probably refer to (columns, desks, counters, steps). Leave out far details, and say what you left out.
4. **Check:** `python3 -m glowpoint.render <project> --check`, look at `out/check.png`, and zoom on the corners with `--model <project>` (red = model edges). Compare corners in numbers with `measure <project> project X Y Z`. Fix and repeat.
5. **Coffers in the drawing:** if the ceiling shows coffers, run `python3 -m glowpoint.detect coffers <project> --depth FT --add` and check `out/detect_coffers.png` (see "Task: coffered ceilings").
6. **Stop and send the user** `out/check.png` as an image, with the calibration result and what you modelled and assumed (rules 5 and 6). Wait for confirmation.

## 6. Rare situations

### Restore a project file

Run `python3 -m glowpoint.project restore <file>`. It checks the version, renders the project, and compares the lights with the list saved in the file. Act on what it prints:
- "WARNING version": the project is from a newer glowpoint. Ask the user for the newest glowpoint zip before you continue.
- "the lights differ": this version draws the project differently. Tell the user what changed.
- "does not render": the project needs something this version does not have (often a change from an older session that is not on GitHub yet). Tell the user in plain words, and give them the error to send to the person who looks after glowpoint.
- It lists the project's own types and fixtures: tell the user their names.

Then send the image and continue.

### The user sends an updated zip

A zip from GitHub does **not** contain the user's projects (`local/` is not in the repository), so never replace or delete the old folder.

0. Save each project (rule 9) and send the files to the user.
1. Unzip the new zip into a **new** folder (rename the old `glowpoint-main/` first).
2. Run `python3 -m glowpoint.doctor` in the new folder, and compare the versions.
3. Copy the user's project folders from the old `local/` to the new `local/`, and `local/patches/` if it exists. Do **not** copy `local/.baseline/`.
4. Read the new `AGENTS.md` again: the rules can change. Read the new entries in `CHANGELOG.md`, and tell the user in two or three lines what matters to them.
5. Render the current project in the new folder (with `--check` if it is being set up). Compare the light counts in `positions.csv` with the last render in the old folder. If something changed, tell the user and send the new image.
6. If you changed the glowpoint program in the old folder: run `python3 -m glowpoint.patch status` there, and `patch make` for changes that have no patch yet. If `CHANGELOG.md` shows that the new version does not have them, apply each patch in the new folder (`python3 -m glowpoint.patch apply local/patches/<file>.patch`) and run the tests. If a patch does not apply, nothing changes: tell the user, still give them the patch file, and make the change again only if it is still necessary.
7. Continue only in the new folder. Keep the old folder until the user confirms that the new version works. If the new version fails on the user's project, continue in the old folder and give the user the error to send on.

### Change the glowpoint program (when you cannot push)

You may change the code in `glowpoint/` when a project needs a fix or a feature that a plugin cannot give. **First tell the user in plain words and ask.** Say something like:

> "This needs a change to the glowpoint program itself, not only to your project. I can make the change here, and it will work in this conversation. At the end I will give you a small text file that lists the changes. Please send it to the person who looks after glowpoint, so they can add it for everybody. It does not contain your drawings. Until they add it, a new conversation will not have this change. Do you want me to try?"

For a large change (for example sloped ceilings or light-level calculations), say that it can take a long time and may not work well, and offer a second choice: a short written description of what is needed, for the user to send on. Then:

1. Make the change for everybody, not only for this project. Update README.md and AGENTS.md, and run all tests (see "Push to GitHub"). **Do not change the version number or CHANGELOG.md:** only the maintainer sets them, so two sessions cannot choose the same number.
2. `python3 -m glowpoint.patch make "short title" --why "what was wrong and what you changed" --changelog "the line for the changelog"`. It compares with the original files that `doctor` saved (or use `--base` with the uploaded zip, for example `--base /mnt/data/glowpoint-main.zip`), runs the tests, and writes `local/patches/<date>-<title>.patch`. It leaves out the version and CHANGELOG.md, and the user's projects and drawings.
3. Send the patch file as a download, and tell the user: "Here is the file with the changes to the glowpoint program. Please send it (for example by email) to the person who looks after glowpoint, or attach it to a new issue at https://github.com/danomoseley/glowpoint/issues. It does not contain your drawings. Until it is added, a new conversation will not have this change, so keep this conversation if you need the change again soon."
4. Never say that the change is in glowpoint or on GitHub. Make one patch for each separate change when you can.

**For the maintainer, or an agent that can push:** `python3 -m glowpoint.patch apply FILE.patch`, read the change, and run all tests. Then raise the version in `glowpoint/__init__.py` to the next number after the current one (not the number in the patch header), add the changelog lines from the header under it, and commit and push.

### Custom types: reuse, changes, and sharing

- **From an earlier project:** `plugins list` also shows the types in the user's other projects in this session; the user asks with, for example, "use the LED strip from the Smith lobby". For a project from an earlier chat, ask for its project file and restore it. Copy the plugin file from its `types/` and the fixture entries from its `fixtures.json` into the current project, and tell the user.
- **Changes:** custom types in the user's projects are copies, one in each project. Change one only in the current project. Then check the other projects in this session for the same type (`ls local/*/types/`, and `diff` the files) and ask, for example: "I changed *LED strip* in the Smith lobby. The Jones office also has the old version. Change it there too?" Change another project only when the user says yes, then render it and send its image.
- **For all projects and coworkers:** when a type or fixture will probably be useful again, ask: "Do you want *LED strip* in all future projects, and for your coworkers? I will make a file to send to the person who looks after glowpoint." If yes, copy it to `library/types/` (fixtures: `library/fixtures.json`), run the tests, and make a patch ("Change the glowpoint program", steps 2 to 4). Until it is added, it stays in the project file.
- **Library changes reach every project that uses the type, and that is intended:** fixes and improvements reach everybody with the next zip. Only a deliberately different design (not a fix) gets a new name, so existing designs keep their intent.

### Push to GitHub (agents with push access)

- After a code change, run the tests: `python3 tests/test_docs.py`, `python3 tests/test_render.py`, `python3 tests/test_calibrate.py`, `python3 tests/test_detect.py`, `python3 tests/test_patch.py`, and `python3 tests/test_project.py`.
- Before every commit and push, update README.md, AGENTS.md, and CHANGELOG.md so they describe every change (types, options, expressions, tools, behaviour), and raise the version in `glowpoint/__init__.py` for a change in behaviour. `tests/test_docs.py` checks this. Turn on the pre-push hook once in each clone (`git config core.hooksPath .githooks`); it runs all tests and stops a push that fails.
- If you cannot clone from GitHub (no internet), ask the user to upload the repository as a zip (GitHub: Code → Download ZIP).

## Coordinates

Feet. X right, Y up (floor = 0), Z into the image. Horizontal surfaces use (x, z), walls use (along, y). Box faces: front (low Z), back, left (low X), right, top.
