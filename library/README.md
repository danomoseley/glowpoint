# Office library

Light types and fixtures here are available in **every project, for every user**, and appear in the menu
(`python3 -m glowpoint.plugins list <project>`).

- `types/*.py`: plugins (see the README, "Adding your own types"). Every type needs `INFO` with a plain
  `name`, a `description`, and an `example` request.
- `fixtures.json`: specific fixtures for the `fixture` type. Give each one a `description`.

How things get here: a session makes a plugin or a fixture for one project. When it is useful again, the
agent asks the user, and makes a patch that adds it here (AGENTS.md, rule 20). The maintainer adds the
patch, and everybody gets it with the next zip.
