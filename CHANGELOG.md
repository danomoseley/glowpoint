# Changes

Newest first. Each version says what a user or an agent will notice. The version is in
`glowpoint/__init__.py`, and `python3 -m glowpoint.doctor` prints it.

## 0.13.4 — 2026-11-12
- From a cold test with a fresh agent: `calibrate` warns for nearly one-point images (the lens from lines is not reliable); `project save` never overwrites a save from the same minute; a clearer note when there is no design.json yet. AGENTS: read sections 1–2 before the first reply; do not ask about the original with one image; what to do when measurements disagree, and what to model.

## 0.13.3 — 2026-11-12
- AGENTS.md reorganized: everyday rules first (12 rules), rare situations (restore, updated zip, program changes, shared types, push) in a last section that agents read only when needed. The rules are the same; the everyday part is about 30 % shorter.

## 0.13.2 — 2026-11-12
- `plugins list` also shows the custom types in the user's other projects in the session, with how to ask for one ("use the LED strip from the Smith lobby"); the menu says so.

## 0.13.1 — 2026-11-12
- Library changes reach every project (intended); a deliberately different design gets a new name. Custom types in the user's projects are copies: a change stays in the current project, and the agent asks before it changes the same type in another project.

## 0.13.0 — 2026-11-12
- Plugins need `INFO` (plain name, description, example request); render warns without it. Fixtures take a `description`.
- `library/`: the office library of types and fixtures, loaded in every project. Sessions add to it with a patch.
- `python3 -m glowpoint.plugins list <project>`: the custom types and fixtures a project can use. `project restore` lists the project's own ones.
- Agents: rule 20 (tell the user about new types, show them in the menu, reuse from an earlier project file, offer to add them to the library).

## 0.12.1 — 2026-11-12
- `project restore`: checks the version that saved the project (warns when the project is from a newer glowpoint), renders it, and compares the lights with the saved light list.

## 0.12.0 — 2026-11-12
- `glowpoint.project save` / `restore`: one file with the whole project (drawing, model, design, plugins, fixtures, last images), so work survives the end of a chat session. Agents give it to the user at important steps (rule 19) and restore it in a new chat.

## 0.11.7 — 2026-11-12
- `docs/menu.png`: one labelled example of each light and ceiling type (`docs/make_menu.py` rebuilds it); agents send it with the welcome and the menu.
- Agents: the model check is one short question; the full checklist only when the user is unsure.

## 0.11.6 — 2026-11-12
- Agents: the users are professional lighting designers: no lighting explanations or coaching; Part C is a short brief in their terms; say plainly when a product or optic cannot be drawn exactly.

## 0.11.5 — 2026-11-12
- Agents: the how-to comes in small parts (a short welcome, how to check the model with the first check image, how to ask for lighting when the model is confirmed), plus the menu on request and at most one tip after each render.

## 0.11.4 — 2026-11-12
- Agents: before a change to the program, tell the user in plain words and ask; no "patch" jargon; for large changes, offer a written request instead.

## 0.11.3 — 2026-11-12
- Agents: a menu for the user with every light and ceiling type, the options for all lights, and what plugins can add (the docs test checks that every type is in it).

## 0.11.2 — 2026-11-12
- `detect coffers`: when it finds nothing, it says what to check instead of a Python error; `--add` again replaces the earlier detected layer.
- Agents: when to use the coffer detector, and the steps when it fails.

## 0.11.1 — 2026-11-12
- `glowpoint.patch make`: patches never change the version number or CHANGELOG.md; the changelog line goes in the header (`--changelog`), and the maintainer sets the version when the patch goes in. `apply` prints these steps.

## 0.11.0 — 2026-11-12
- `glowpoint.patch`: a session that cannot push (ChatGPT, a zip) can change the code and send the change back as a `.patch` file; `apply` re-applies a patch, also without git. `doctor` saves the original files as the base.
- Agents: rule 18 (core code changes and patches); the updated-zip steps re-apply patches.

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
