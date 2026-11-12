# Office library

Light types and fixtures here are available in **every project, for every user**, and appear in the menu
(`python3 -m glowpoint.plugins list <project>`).

- `types/*.py`: plugins (see the README, "Adding your own types"). Every type needs `INFO` with a plain
  `name`, a `description`, and an `example` request.
- `fixtures.json`: specific fixtures for the `fixture` type. Give each one a `description`.

How things get here: a session makes a plugin or a fixture for one project. When it is useful again, the
agent asks the user, and makes a patch that adds it here (AGENTS.md, "Custom types"). The maintainer adds the
patch, and everybody gets it with the next zip.

**Changes affect every project, and that is intended.** A project uses the library version at each render,
so a fix or an improvement here reaches every project with the next zip. Only a deliberately different
design (not a fix) gets a new name, so that existing designs keep their intent. The project file's render
check (`project restore`) shows when a project's lights changed.
