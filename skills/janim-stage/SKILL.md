---
name: janim-stage
description: Run an engineering stage on Janim.py itself — add or change a mobject, animation, effect or renderer path, port something from ManimCE/ManimGL, or do a performance round — end to end: measure the reference first, implement under `janim/` with the lazy export tables, lock it with `tests/test_*.py`, teach it with a tutorial lesson, update `llms.txt`/`llms.es.txt`, the READMEs, `THIRD_PARTY_NOTICES.md` and `TODO.md`, prove "frames identical" with the harness, and close with a commit only when the owner asks. Use for any edit under `janim/` or any new public name.
---

# An engineering stage (Janim.py)

A stage is not "write the feature". It is measure → implement → lock → teach →
document → prove → close, and the repository shows each step: a test, a
lesson, a line in `llms.txt`, a manifest that did not move. The record of how
the last stages went is the git log and `history/`.

## 0 · Open

```bash
cd <checkout>
git status --short                # know what is already modified: the owner may have work in progress
.venv/bin/python -c "import janim; print(janim.__version__)"
```

Read `TODO.md` (what is open and why), the section of `llms.txt` you are
about to change, and the lesson closest to what you are adding. The
references, when installed, are run, not remembered (`janim-from-manim` §4).

## 1 · Measure before designing

The canonical failure is designing against a guess.

- **Geometry comes from the reference.** `Code` matched CE's listing to 2e-3
  units because CE was run and its boxes measured first; `TangentialArc`'s
  four corners are locked at 2e-6 against numbers CE printed on a stated
  date. Write the measured numbers into the test, with the version and the
  date.
- **Ask GL before calling CE's behaviour the truth**: Janim ports ManimGL,
  and CE departs from it in colours, `smooth`, `Text` metrics and more.
- **A reference bug is not copied; it is documented.** Three measured on GL
  1.7.2 and left out: `AddTextWordByWord` shows a whole `Text` at once (GL
  builds one word group), the `…Around` animations re-centre a partial
  outline every frame, `ExponentialValueTracker(5)` reads e⁵. Janim does the
  intended thing and the lesson or `llms.txt` says so.
- **Bit parity when it matters**: a port whose output must equal the
  reference to the last bit keeps the reference's ORDER OF WORK (`polylabel`
  kept CE's heap order; `janim.math` keeps Julia's rounding).
- **Performance is measured on user scenes, as whole processes, at the
  resolution you claim** (`janim-tests` §5). The round that vectorised the
  libm was dismissed once because the benchmark measured the engine alone.

## 2 · Where things go, and how they are written

| What | Where |
|---|---|
| a flat mobject | `janim/core/shapes.py`, `annotations.py`, `decor.py`, `coordinates.py`, `axes.py`, `tables.py`, `probability.py`… |
| text, formulas, numbers, code | `janim/text/` |
| an animation | `janim/animation/<family>.py` — `creation`, `fading`, `indication`, `passing`, `rotation`, `sugar`, `homotopy`, `composition` |
| meshes, clouds, fields, hulls | `janim/core/surface.py`, `dots.py`, `fields.py`, `hull3d.py` |
| trackers and updater helpers | `janim/core/trackers.py` |
| the renderer, compositor, effects, WGSL | `janim/backend/wgpu/` — touch it only when the change IS a rendering change |
| the public name | one of `janim/_exports_basics.py`, `_exports_animation.py`, `_exports_geometry.py`, `_exports_text.py`, `_exports_effects.py`, `_exports_3d.py` |

- **A name is not public until it is in an export table.** `import janim`
  must keep opening no device and importing no geometry: the tables map
  names to module strings, resolved lazily by `janim/__init__.py`. Check with
  `.venv/bin/python -c "import janim; print('Foo' in janim.__all__)"`.
- Code, comments, docstrings and file names in English; the **expanded
  format** when a call spans lines (one argument per line, the closing
  parenthesis on its own line), as the lessons are written.
- Python 3.14; points are `float32` arrays; paths are GL-style quadratics
  (`num_curves = len(points) // 2`); a new subpath starts with
  `start_new_path` or `add_subpath`.
- A constructor calls the base constructor FIRST and lets unknown keywords
  through to it, so a typo raises; setters return `self`.
- Trigonometry on anything that reaches a frame comes from `janim.math` (the
  engine's own modules use `_julia_math`), never `math` or `np` directly, so
  frames match across machines.
- **No new dependency without the owner's decision.** The five pins in
  `pyproject.toml` are the budget; pygments was a decision, with a lazy import
  and an `ImportError` that names the bootstrap.
- Something CE or GL has that you leave out goes to `TODO.md` or to
  `llms.txt` "Deliberately absent", with the reason.

## 3 · Lock it: `tests/test_<name>.py`

The shape every suite here has: plain `test_*` functions, a `main()` that
runs them and prints `OK`/`BAD`/`SKIP`, `if __name__ == "__main__":
sys.exit(main())`, and a `_require_latex()` that SKIPS (not fails) without
`latex`/`dvisvgm` — so it runs as a script AND under pytest, and avoids the
GPU where it can.

- **Numbers measured on the reference**, with the tool and date in the
  docstring: `"""CE 0.22 measured on itself (2026-10-26): same endpoints to 1e-6."""`.
- **A tolerance is measured, never inherited.** A midpoint of an arc differs
  from CE's cubic by 2e-4 for a reason you can name; write that reason next
  to the `atol`.
- **Every equality lock wants a negative control**: the `ValueError` and
  `TypeError` paths (a line is not an arc; `var_type=float` is refused;
  `crop` with both arguments).
- **A test you could not make fail protects nothing.** Before trusting a
  green, break the code once and watch it go red.

## 4 · Teach it: a lesson

Every public name is meant to appear in a lesson that runs (course 4 is the
reference course). A lesson is `examples/tutorial/<course>/<nn>_<name>.py`: a
docstring that explains it with the measured facts, `PREVIEW_T`, one `Scene`
subclass, and the `__main__` block that writes
`examples/tutorial/output/<course>/<name>.mp4` at 854×480@30. Add its row to
`examples/tutorial/README.md` and bump the counts in its header table.

Then **render `render_frame(Lesson, PREVIEW_T)` and look at it**. Overlaps, a
star over a label, an object off screen after a `scale_factor=8` spiral: only
visible.

## 5 · Document

- `llms.txt` AND `llms.es.txt` — the same bullet in both; this is the
  agent-facing API summary and where "deliberately absent" lives.
- `README.md` and `README.es.md` when the requirements change (a font, a
  dependency, a tool on the PATH).
- `THIRD_PARTY_NOTICES.md` when code is PORTED (the CE row lists the files
  and classes); the licence paragraph of the READMEs if a new project
  appears.
- `TODO.md`: remove what the stage settles, add what it leaves open (one
  bullet: what is wrong, where, what settling it takes).
- `docs/cli.md`, `docs/compositor.md`, `docs/3d.md` (and their `.es.md`)
  when a manual area changes. English files keep the original names; the
  Spanish versions are `*.es.*`.

## 6 · Prove it

1. All `tests/test_*.py` green (`janim-tests` §1).
2. The frame harness sealed BEFORE the stage and AFTER, with the prediction
   written first: untouched scenes identical, new lessons `MISSING` in before,
   and nothing else (`janim-tests` §2–3).
3. One GPU job at a time while it runs; nothing under `janim/` edited while a
   seal is running.
4. The new lesson's frames looked at (`janim-verify`).

## 7 · Close

- A commit happens ONLY when the owner asks for it, never on your own
  initiative, and never a push unless asked for in that moment. Stage explicit
  paths (`git add <files>`; `git commit -F msg.txt -- <paths>`), never `-a`
  or `add .`; the owner's own work in progress stays out.
- Commit messages in English for this repository: what changed and WHY (the
  decisions), naming the two or three tests that hold it up; end with the
  trailers the recent commits carry (`git log -3 --format=%B`).
- Only text and SVG enter git (`.gitignore` already refuses PNG, MP4 and
  fonts); render output stays in `output/` folders.
- A stage that leaves a record for the next one (a port, a platform) writes
  it under `history/`, one folder per month (`history/2026-10/` is the
  model).
