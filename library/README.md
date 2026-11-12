# Office library

Light types and fixtures here are available in **every project, for every user**, and appear in the menu
(`python3 -m glowpoint.plugins list <project>`).

- `types/*.py`: plugins (see the README, "Adding your own types"). Every type needs `INFO` with a plain
  `name`, a `description`, and an `example` request.
- `fixtures.json`: specific fixtures for the `fixture` type. Give each one a `description`.

How things get here: a session makes a plugin or a fixture for one project. When it is useful again, the
agent asks the user, and makes a patch that adds it here (AGENTS.md, rule 20). The maintainer adds the
patch, and everybody gets it with the next zip.

**Changes affect every project.** A project uses the library version at each render, so a change here
changes every project that uses the type. Keep changes compatible: add options with defaults that draw as
before. For a different look, add a new type or fixture with a new name. A project that must not change
keeps its own copy in its `types/` folder (or `fixtures.json`); the project copy is used first. The project
file's render check (`project restore`) shows when a project's lights changed.
