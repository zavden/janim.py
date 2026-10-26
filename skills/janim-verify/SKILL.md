---
name: janim-verify
description: Verify a Janim.py render by looking at pixels — `render_frame`, `describe`, `animation_map`, `count_frames`, `render_frame_motion`, `bin/janim frame`, cutting frames out of an mp4 — and debug a Janim.py scene that renders but "does not show up" or looks wrong. Use before calling any Janim.py scene, lesson, port or effect done, whenever a frame looks wrong, and to check that two runs give the same bytes.
---

# Verify a render (Janim.py)

House rule: **nothing is called done without looking at pixels.** Scene bugs
— an invisible mobject, an ugly morph, a label on top of a square, a 0.3-pixel
stroke — throw no exception. They are only visible.

## 1 · The headless probes

```python
from janim import *
from scene import Demo

# the exact frame at t: the same simulation as the mp4, deterministic, no window
render_frame(Demo, 1.7, fps=30, resolution=(854, 480), png="f.png")   # → RGB uint8, shape (480, 854, 3)
render_frame([square, label], png="static.png")                         # a static list, no scene
render_frame(Demo, 1.7, transparent=True)                               # RGBA

# the numbered play/wait map, without a GPU: which frame each act starts at
starts, total = animation_map(Demo, fps=30)      # e.g. ([1, 16, 46], 60)
frames, animations = count_frames(Demo, fps=30)

# the state at t, as text, taken where render_frame takes its pixels
print(describe(Demo, 1.7))

# a motion-blurred still, when the subject is invisible in an instantaneous frame
render_frame_motion(Demo, 1.7, n=8, shutter=0.5, png="mb.png")
```

`describe` prints one line per mobject on stage — points, bounding box, stroke
and fill with their opacities — and, with a composition mounted, the layer and
mask tree:

```text
Scene 854×480 · t=1.033 s · 31 frames · 2 mobjects
  - Circle · 33 points · bbox [-1.000, 1.000]×[-1.000, 1.000] · stroke #eca39d α1.00 w4.0 · fill #c0c048 α0.47
```

Reach for it FIRST when something "does not appear": `α0.00`, `0 points` or a
bbox outside ±7.1 × ±4 names the cause without spending a render.
`describe(self)` inside `construct` needs no second simulation.

Frame K (from 1) is the instant `t = (K − ½)/fps`, and the αs are midpoints:
no frame ever sees α = 0 or 1. Use `animation_map` instead of guessing times —
it tells you where act 4 actually begins. A lesson marks its own moment in
`PREVIEW_T` (and `PREVIEW_MOTION` for the blurred ones).

The first `render_frame` in a process opens the device (about half a second);
later ones in the same process are fast. Rendering to a file opens no window.

## 2 · From the shell

```bash
bin/janim frame scene.py 45 f.png -ql          # ONE frame; re-simulated from t = 0 (no daemon, no cache)
bin/janim render scene.py -s --to 1.5s         # the same, by time
bin/janim render scene.py -qs -o out.mp4       # the whole video, small and fast
ffmpeg -i out.mp4 -vf "select='eq(n,44)'" -vframes 1 f45.png    # frame 45 of an mp4 (ffmpeg counts from 0)
JANIM_HEADLESS=1 bin/janim frame scene.py 45 f.png             # the CPU route
```

`frame` is the single-frame verb; `render` renders the WHOLE video (or one
frame with `-s`). A late frame costs its whole prefix, because every call
re-simulates from t = 0: for many frames of a long scene, render the mp4 once
at `-qs` and cut the frames out of it.

## 3 · Then actually LOOK

Open the PNG (the Read tool shows images). A render that ran is not a render
that is right — exit code 0 says nothing about what is on screen.

Frames worth looking at, in order of how often they catch something:

1. **the middle of every `Transform`** — morphs fail here and never at the
   ends (exploding glyphs, blobs, cancelled fill). The highest-yield frame in
   any scene.
2. **`t = 0 + ε`** — is the opening state clean, or is something already wrong?
3. **just after every `FadeOut`** — leftovers, ghosts, half-faded children.
4. **the last frame** — does the composition settle? Does anything overlap?
5. **a layout check at a size a human would use** — labels over shapes, text
   wider than the frame, a title under the camera's new position.

## 4 · When it renders but looks wrong

- **Nothing of a mobject you added** while a `Composition` is mounted: the
  layers decide what is DRAWN. A root that is in no `Layer` is updated and
  never drawn (measured). Put it in a layer.
- **A fade that does nothing**: the mobject's points are rebuilt in an
  updater, so new points re-stamp the factory style. Freeze the updater first,
  or build the mobject with its final style.
- **A `Dot` that stays white, an `Arrow` that stays grey**: `color=` painted
  the stroke; both are fills → `fill_color=` or `.set_fill(c)`.
- **A default that "should" be visible and is not**: pixels per scene unit are
  `width / 14.22` — 45 at 640×360, 60 at 854×480, 135 at 1080p — so a
  0.01-unit width is under one pixel at every preview size. A sub-pixel effect
  satisfies every closed-form test and fails the only question that matters:
  can you see it?
- **A morph with flying blobs** on text: morph the `Tex`/`Text` parent (one
  child per glyph pairs glyph to glyph), not a flattened single path.
- **A title that moved when the camera zoomed**: `to_edge`/`to_corner` use the
  NOMINAL frame; a HUD that must ignore the camera is `m.fix_in_frame()`.
- **An updater one frame behind**: `bring_to_back` moved it before the thing
  it follows in the update order; use `set_z_index` for drawing order.
- **A `TypeError` from `VGroup`**: mixed content wants `Group`.

## 5 · Determinism checks

Same code → same bytes, in any process. To prove it, hash the FRAMES, never
the mp4 (x264 is threaded unless `encoder_threads=1`):

```python
import hashlib

hashes = []
Demo(
    output="x.mp4",
    fps=10,
    resolution=(640, 360),
    frame_tap=lambda index, pixels: hashes.append(hashlib.sha256(pixels.tobytes()).hexdigest()),
).render()
```

Run it twice, in two processes, and compare. Parity is WITHIN a route: RADV,
lavapipe (`JANIM_HEADLESS=1`), Metal, DX12 and WARP each give their own
reproducible picture, differing from one another by a pixel at some edges.
`driver_header(gpu_info())` names the route that ran; write it next to any
hash you keep. The whole-corpus version of this is `janim-tests`.

## 6 · If you touched the engine

Anything under `janim/` → the frame harness and the suites of `janim-tests`,
before and after. An expected hash that moves is a fact to EXPLAIN, not a
number to regenerate.
