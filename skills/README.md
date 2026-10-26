# Skills

Packaged workflows for an agent working with or on Janim.py. Each is a
`SKILL.md` with YAML frontmatter (`name`, `description`); the description is
what decides whether a skill gets loaded, so it names the task, not the topic.

They are the operational sibling of [`../llms.txt`](../llms.txt): `llms.txt`
is the API in one file, these are the procedures — what to run, in what
order, and which traps have already been paid for. Every number and every
behaviour they state was measured on Janim.py (and, where it says so, on
ManimCE 0.22 and ManimGL 1.7.2) on the date given, not remembered.

## Using Janim.py

| Skill | For |
|---|---|
| [`janim-scene`](janim-scene/SKILL.md) | write a new scene: the `class X(Scene)` contract, the template, the CLI, relative layout, the traps |
| [`janim-verify`](janim-verify/SKILL.md) | verify a render by looking at pixels; debug a scene that "does not show up" |
| [`janim-text`](janim-text/SKILL.md) | `Text` through FreeType, `Tex` through LaTeX, parts by key, `TransformMatchingTex`, numbers, `Code` |
| [`janim-compositor`](janim-compositor/SKILL.md) | layers, masks, effects, a second camera, and the glow and magnifier recipes |
| [`janim-from-manim`](janim-from-manim/SKILL.md) | translate a ManimCE/GL scene: the knobs that moved, the measured defaults, what has no equivalent |

## Working on Janim.py

| Skill | For |
|---|---|
| [`janim-stage`](janim-stage/SKILL.md) | run a stage end to end: measure, implement, lock, teach, document, prove, close |
| [`janim-tests`](janim-tests/SKILL.md) | the suites, the frame-hash harness ([`skills/janim-tests/scripts/frame_hashes.py`](janim-tests/scripts/frame_hashes.py)), GPU hygiene, reading a red |
| [`janim-layer-effect`](janim-layer-effect/SKILL.md) | add a compositor effect: dataclass + shader + one handler, and the noise contract |

## How an agent loads them

Claude Code reads project skills from `.claude/skills/<name>/SKILL.md`. In
this checkout `.claude/skills/` holds relative symlinks to the folders here,
so the ONE copy lives in `skills/`, is versioned with the code, and is still
picked up automatically when the agent starts in the checkout. Editing a skill
means editing the file here; never create a second copy under `.claude/`, or
the two drift apart in silence. (On Windows, `git clone` needs
`core.symlinks=true`, or copy the folders instead.)

## Where else the knowledge lives

- [`../llms.txt`](../llms.txt) — the whole API, for agents (`../llms.es.txt` in Spanish)
- [`../examples/tutorial/`](../examples/tutorial/README.md) — 93 runnable lessons in four courses; the best few-shot corpus in the repo
- [`../docs/`](../docs/) — the CLI, the compositor and 3D, as manuals
- [`../TODO.md`](../TODO.md) — what is open, and why
- [`../history/`](../history/) — the record of the platform ports

## A note on staleness

These files name real identifiers, real paths, real CLI verbs and real
environment variables, so a rename can turn them into confident lies without
touching a line of them. `check_skills.py` guards against that by asking the
library instead of trusting the prose: every call and CamelCase type the
skills claim must be a public name of `janim`, an attribute of one of its core
classes, or a declared internal or foreign name; every path must exist; every
`bin/janim <verb>` must be a verb the CLI has; every `JANIM_*` variable must
be read somewhere under `janim/`. Run it after any rename, and after editing
a skill:

```bash
.venv/bin/python skills/check_skills.py
```

It is written to be failable — drop a name that does not exist into a skill
and it goes red — and its lists of excused names are explicit, so every
exception is auditable.
