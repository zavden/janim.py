---
name: janim-tests
description: Run and read Janim.py's checks without lying to yourself — the `tests/test_*.py` suites (as scripts, or with pytest), the per-frame SHA-256 regression harness over every example scene (`skills/janim-tests/scripts/frame_hashes.py seal | compare`), GPU hygiene (one GPU job at a time, `JANIM_HEADLESS=1`, per-route hashes), timing claims, and how to tell a driver flake from a regression. Use before and after any change under `janim/`, when a hash or a test goes red, before claiming "frames identical" or "N× faster", and when planning a long render sweep.
---

# Suites, frames and not lying to yourself (Janim.py)

Janim.py has no daemon and no hidden cache: every check is an ordinary process
you start yourself. What can still lie to you is the reading — a flake called
a regression, a regression called a flake, a timing taken while the GPU was
busy with something else.

## 1 · The unit suites

```bash
cd <checkout>                                   # ALWAYS from the root (§4)
for t in tests/test_*.py; do .venv/bin/python "$t" || echo "FAIL $t"; done
.venv/bin/python -m pytest tests               # if pytest is installed; the venv does not ship it
```

Each `tests/test_*.py` runs as a script (a `main()` that calls every `test_*`
and prints `OK`/`BAD`/`SKIP`) and under pytest. `test_math.py` and
`test_surface.py` need no GPU; `test_code.py` needs a monospace font and
pygments; the `Variable` and `SampleSpace` labels need `latex` + `dvisvgm`
and SKIP without them, they do not fail. About 20 s in all.

A new feature is born with its suite (`janim-stage` §3). A tolerance in a
test is MEASURED on the reference, never inherited from a similar test.

## 2 · The frame harness: every example, every frame, hashed

The regression instrument is the SHA-256 of every frame of every `Scene` in
`examples/tutorial`, `examples/gallery`, `examples/scenes` and `examples/demo`
at 640×360 and 10 fps, one process per scene, through `Scene(frame_tap=…)` —
the raw RGB bytes before the encoder, so the mp4 container never enters it.

```bash
H=skills/janim-tests/scripts/frame_hashes.py
.venv/bin/python $H seal output/frames/before                  # ~3 min for 139 scenes on a discrete GPU
# … edit …
.venv/bin/python $H seal output/frames/after
.venv/bin/python $H compare output/frames/before output/frames/after
.venv/bin/python $H seal output/frames/x --only c1_03 --only gallery          # a subset while iterating
.venv/bin/python $H one examples/gallery/01_square_to_circle.py SquareToCircle /tmp/one.tsv   # one scene
```

`seal` writes one `<path with __>__<Class>.tsv` per scene (frame index, hash),
a `summary.tsv` (scene, class, frames, seconds, or `ERR …`) and `driver.txt`
(`driver_header(gpu_info())`, the Python, the git HEAD): the manifest knows
what produced it. `compare` prints `SAME`, `DIFFER n/N (first frame k)` or
`MISSING` per scene, then the totals, and exits 1 if anything differs.
`output/` is ignored by git, so manifests can live there.

The procedure, in this order:

1. **Seal BEFORE touching anything.** The before-manifest is the reference;
   the repository stores none yet (`TODO.md`).
2. **Write the prediction before sealing after**: which scenes SHOULD change.
   A new lesson appears as `MISSING` in before; a change to `Text` moves every
   scene with text; a renderer change moves everything. "I expect 0
   differences" is a prediction too.
3. Seal after, compare, and **explain every line that disagrees with the
   prediction** before anything else.

## 3 · Reading a red honestly

- **A regression differs ALWAYS; a flake differs sometimes.** A scene that
  differs in ONE frame once and gives the before-hash on six consecutive
  re-runs alone is a driver flake (measured on RADV, 2026-10-26: `Plots3D`,
  1 frame of 45, 6/6 re-runs equal). Re-run that scene alone with `one`
  several times and compare the MODAL hash of your tree with the modal hash of
  the clean tree.
- **5 runs are not samples.** A 10 % intermittent failure hides in 5 runs
  59 % of the time; ask how many runs it would take to SEE it before declaring
  it gone.
- **Parity is WITHIN a route.** RADV, lavapipe (`JANIM_HEADLESS=1`), Metal,
  DX12 and WARP each give their own reproducible frames, differing by a pixel
  at some edges. Never compare a manifest from one route with another:
  `driver.txt` says which one ran.
- **A red right after a system update is the driver's until proven
  otherwise.** Mesa releases have moved hashes on RADV and on lavapipe with
  zero lines changed in the engine. Compare the driver lines of the two
  `driver.txt` (on Fedora, `rpm -q --last mesa-vulkan-drivers`), and re-seal
  the untouched tree first.
- **An expected hash that moves is a fact to EXPLAIN, not a number to
  regenerate.** `compare` names the first differing frame: render it from both
  trees (`janim-verify`) and look at the difference before accepting it.
- Never pipe a long run through `| tail`: the only line that explains a
  failure is the one you threw away. Write to a log and grep afterwards.

## 4 · Hygiene

- **One GPU job at a time.** Two concurrent renders are a flake factory and
  ruin every timing; a sweep in the background plus a probe in the foreground
  is the shape that bites. `JANIM_HEADLESS=1` (lavapipe) is slower but free of
  GPU contention — and has its own hashes.
- **Run from the checkout root.** Inside `janim/`, `janim/math.py` shadows
  the standard library's `math` and the errors look like anything but that.
- **One process per render**, which is how the harness works: an aborted
  device (a `wgpu` panic aborts the process) takes one scene with it, not the
  sweep, and no state leaks between scenes.
- Long sweeps run detached with a log (`nohup … > sweep.log 2>&1 &`); the
  harness's `summary.tsv` grows as it goes, so progress is `wc -l`.
- Kill by PID, never by pattern: `pgrep -f` matches its own shell.
- Do not edit anything under `janim/` while a seal is running: the children
  import the tree as it is when they start.

## 5 · Timing claims

Time the WHOLE process (`time .venv/bin/python …` or `time bin/janim render …`),
one render at a time, with the TeX cache in the state you say it is in (cold:
`JANIM_TEX_CACHE=$(mktemp -d)`), and report resolution, fps and route. Noise
to expect: a browser or an IDE indexing in bursts hits ONE run and leaves the
others flat — that is not thermal throttling, which climbs monotonically.
Compare medians of three, never a single run. The farm (`-j N`) does not
speed up simulation-bound scenes: every process re-simulates its prefix
(`docs/cli.md`).

## 6 · What is not here yet

Stored per-route reference hashes and a `tests/` entry point that runs the
harness are open items in `TODO.md`; until then the reference is the
before-manifest you seal yourself.
