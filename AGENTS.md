# Instructions for AI agents

glowpoint places lighting concepts on a perspective image of a space. The full reference is [README.md](README.md). This file gives the rules and the work sequence.

## Rules

1. **Never estimate positions by eye.** Get pixel positions with `glowpoint.zoom`, and turn them into feet with `glowpoint.measure`.
2. **Use relationships in design.json**, not numbers, for anything that depends on the architecture: `"spaced(box('Desk').z0, box('Desk').z1, 3)"`, not three numbers. Then the lights follow when the model is corrected.
3. **Add an object to model.json before you refer to it.** A desk, bench, or stair is a box.
4. **Geometry goes in model.json, lighting goes in design.json.** Do not change code in `glowpoint/` for one project. A new kind of light is a plugin in `<project>/types/` (copy `examples/types/pendant.py`).
5. **Verify every result:** read `out/positions.csv` and confirm the numbers the user asked for (counts, spacing, heights), and look at the output image.
6. **When a light looks wrong, check the model first.** The usual cause is a surface or box that does not match the image. Run with `--check`.
7. **State your assumptions.** If the request leaves out a size, choose a normal value and tell the user which one.
8. **Keep user projects and images out of git.** Put projects in `local/` or outside the clone. Architects' drawings and renders are often confidential.
9. **After a code change, run the tests:** `python3 tests/test_calibrate.py` and `python3 tests/test_render.py`.

Run all commands from the repository root (`python3 -m glowpoint.<tool>`).

## Task: change the lighting in an existing project

1. Read `<project>/model.json` (surface and box names) and `<project>/design.json`.
2. Add or edit features in `design.json`. The light types and expressions are in the README.
3. `python3 -m glowpoint.render <project>` (add `--linework` if there is no drawing; `--camera view.json` for another view).
4. Check `out/positions.csv` and `out/concept.png`.

## Task: set up a new image

1. **Camera:** `python3 -m glowpoint.calibrate <image> --known x1,y1,x2,y2,H --out <project>/camera.json --overlay <project>/calibration.png`
   - Read the report. Each vanishing point fit should be below 0.5° for renders (1–3° for hand drawings, with `--tol 2`), and the angles between the found directions should be within 1° of 90.
   - Look at the overlay image: each color must be one real direction of the room.
   - For `--known`, use a vertical with a known height: a door frame (often 7 ft), a column joint, or a person (about 5 ft 8 in). Find its pixels with `zoom`.
   - One-point images: the lens cannot be found from lines; see the README.
2. **model.json:** start it from the skeleton in the README, with the camera from `camera.json`.
3. **Surfaces and boxes:** for each corner you need:
   - `python3 -m glowpoint.zoom <image>` to see the whole image with a coarse grid,
   - `python3 -m glowpoint.zoom <image> X0 Y0 X1 Y1` on a box about 100–200 px wide around the corner,
   - read the pixel, confirm it with `--mark X,Y`,
   - `python3 -m glowpoint.measure <project> floor X Y` (or `height`, or `plane`).
   Walls: two floor points on the base line. Ceiling: `height` from a floor point to the ceiling line above it. Columns: base corners and top.
4. **Check:** `python3 -m glowpoint.render <project> --check` and look at `out/check.png`. Every surface must follow the lines of the image. Fix and repeat.

## Coordinates

Feet. X right, Y up (floor = 0), Z into the image. Horizontal surfaces use (x, z), walls use (along, y). Box faces: front (low Z), back, left (low X), right, top.
