# Changes

Newest first. Each version says what a user or an agent will notice. The version is in
`glowpoint/__init__.py`, and `python3 -m glowpoint.doctor` prints it.

## 0.10.0 — 2026-11-12
- Agents: start sequence, how-to for the user, how to read the check image, send the image after every render (not JSON), how to handle an updated zip.
- `glowpoint.detect coffers`: finds square or round coffers in the drawing; waffle `replace` redraws them.

## 0.9.0 — 2026-11-11
- Light colour (`cct`, `light_color`) on every type; new types `wallwasher`, `object_light`, `projection`; stitch track (`pattern`); sconce `direction`; luminous `bands`.
- `calibrate` accepts several `--known` dimensions; `measure box`; `legend_at`; `glow` type; slots and ledges always on the room side.
- Track lighting (`track`): surface, recessed, trimless, suspended, with ERCO and Solais aperture sizes.
- Ceiling types `slots`, `lightwell`, `linear_pendant`, perimeter `cove`, `cove`, `slats`, `luminous`; round coffers; pendants in coffers; drawn `fixture` type and `coffers()`.

## 0.1.0 – 0.8.0 — 2026-11-11
- First versions: model, design file with relationships, render, check image, positions.csv; plugins; two- and three-point cameras (`calibrate`, `measure`, `zoom`); `doctor`; tests and the pre-push hook.
