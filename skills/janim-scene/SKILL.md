---
name: janim-scene
description: Write a new scene with Janim.py (the Python package `janim`, `from janim import *`, Manim's syntax on a WebGPU renderer) — the `class X(Scene)` / `construct(self)` contract, the file template and its `__main__` block, rendering and previewing with `bin/janim`, relative layout, the camera and 3D, simulations, and the traps that cost hours (eager `.animate`, updaters born styled, `Dot(color=)`, `VGroup` vs `Group`). Use whenever asked to create, build, extend or fix an animation or scene inside a Janim checkout, even when the request just says "manim".
---

# A new Janim.py scene

Janim.py is a Manim-style animation engine in Python: ManimGL's vocabulary
(`class X(Scene)`, `self.play`, `.animate`, `next_to`, `Text`, `Tex`) on its
own WebGPU renderer, with deterministic frames and a layer compositor Manim
does not have. No daemon and no config file: one ordinary Python process per
call.

## 0 · Before you touch anything

```bash
cd <checkout>                                   # the directory with pyproject.toml, janim/ and bin/
ls .venv/bin/python || scripts/bootstrap.sh     # the pinned venv behind bin/janim
.venv/bin/python -c "from janim.backend.wgpu.context import gpu_info; print(gpu_info())"
```

- Work from the checkout root. Running Python from inside `janim/` puts
  `janim/math.py` in front of the standard library's `math`, and everything
  breaks in ways that look like anything but that.
- `import janim` opens no device; the first render does. `JANIM_HEADLESS=1`
  picks the CPU adapter (lavapipe on Linux, WARP on Windows; macOS has none):
  slower, but free of GPU contention.
- `bin/janim` uses `.venv/bin/python` when it exists, else `python3`. Python
  3.14 is required.

## 1 · The template

```python
"""What the scene shows, in a paragraph: the explanation lives next to the code."""

from pathlib import Path

from janim import *

PREVIEW_T = 1.2          # the second worth looking at (janim-verify)


class Demo(Scene):
    def construct(self):
        title = Text("a frame is one step of a fixed clock", size=0.5, color=GREY_A)
        title.to_edge(UP, buff=0.4)
        c = Circle(radius=1.0)
        c.set_fill(YELLOW, opacity=1.0)
        c.set_stroke(WHITE, width=3.0)

        self.add(title)
        self.play(FadeIn(c, shift=0.5 * UP), run_time=0.8)
        self.play(Transform(c, Square()), run_time=1.2)
        self.wait(0.5)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.with_suffix(".mp4")
    Demo(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
```

The class is a CONTRACT, not a convention: the CLI, the render farm and the
live window look up the `Scene` subclass in your file (the only one, or the
one you name as `file.py:Demo`) and call its `construct`. There is nothing to
register.

Three facts behind everything else:

- A frame is one step of a FIXED clock: `run_time=2` at 30 fps is exactly 60
  steps of `dt = 1/30`. Nothing reads the wall clock, which is why two renders
  give identical frames.
- The αs an animation sees are the MIDPOINTS `(k + ½)/n`, never 0 or 1; the
  exact end pose belongs to `finish`, the frame after.
- Defaults differ by door: a `Scene(...)` built by hand is 1920×1080 at 60 fps;
  the CLI is 1280×720 at 30 (`-qm`); `render_frame` is 854×480 at 30. The
  tutorial renders itself at 854×480@30.

## 2 · Render it

```bash
bin/janim render scene.py -ql              # the video, beside the scene (-ql = 854×480 at 15 fps)
bin/janim render scene.py:Demo -qm -o out.mp4
bin/janim frame scene.py 20 f.png -ql      # ONE frame: K ↔ t = (K − ½)/fps, re-simulated from t = 0
bin/janim scene.py                         # the live window: Esc/q quit, space pause, ,/. step, [ ] jump an animation
bin/janim render scene.py -s --to 1.5s     # one frame as a PNG, by time
.venv/bin/python scene.py                  # the __main__ block above
```

Presets set BOTH resolution and fps: `-qs` 640×360@10 · `-ql` 854×480@15 ·
`-qm` 1280×720@30 · `-qh` 1920×1080@60. `-r WxH` and `--fps N` override the
part they name, and the last flag wins. `-n 3,5` is a range of ANIMATIONS
(play/wait numbered from 1), not of frames; `--from label` draws from a
`self.checkpoint("label")`; `-j 4` is the render farm. No flag is ignored in
silence, and `render` (the whole video) and `frame` (one frame) are different
verbs. `docs/cli.md` is the full manual.

A scene with no `play`/`wait` writes a PNG instead of an empty video and says
so in a `RuntimeWarning`.

Then LOOK at a frame before calling it done: `janim-verify`.

## 3 · Placement: never write coordinates by hand

Sizes are SCENE UNITS: the frame is 8 tall and 8·16/9 ≈ 14.22 wide whatever
the resolution (`FRAME_WIDTH`, `FRAME_HEIGHT`, `FRAME_X_RADIUS`). Hand-written
coordinates are the first thing to break when a label grows, so place
everything relative to something:

```python
label.next_to(box, UP, buff=0.3, aligned_edge=LEFT)   # the reference may be a mobject or a point
title.to_edge(UP, buff=0.5)                             # the NOMINAL frame: a camera zoom does not move it
logo.to_corner(UR)
a.align_to(b, LEFT)
group.arrange(DOWN, buff=0.4, aligned_edge=LEFT)
grid.arrange_in_grid(n_rows=3, buff=0.3)
m.center();  m.set_x(2.0);  a.match_width(b);  box.surround(content, buff=0.2)
if g.get_width() > FRAME_WIDTH - 1:
    g.set_width(FRAME_WIDTH - 1)
```

`Line(a, b)`, `Arrow(a, b)` and `Dot(p)` accept MOBJECTS as endpoints and use
their facing edges. `get_center()` is the bounding-box centre (what `move_to`
and `rotate` use); `get_center_of_mass()` is Manim's mean of the control
points.

## 4 · Style, and the two colour traps

```python
m.set_fill(BLUE, opacity=0.5).set_stroke(WHITE, width=3.0)     # setters chain
m.set_color(c)                 # fill AND stroke
m.set_fill(opacity=0.5)        # no colour given: each point keeps its own
Square(fill_color=BLUE, fill_opacity=1, stroke_width=0)       # most constructors take the style keywords
```

Measured on Janim.py — both are ManimGL's behaviour, not ManimCE's:

- `Dot(p, color=BLUE)` stays WHITE: a `Dot` is a fill. Write
  `Dot(p, fill_color=BLUE)` or `.set_fill(BLUE)`.
- An `Arrow` is drawn by its FILL (one contour, the tip inside), so
  `Arrow(a, b, color=RED)` paints a zero-width stroke and the arrow stays
  grey. Use `fill_color=RED` or `.set_fill(RED)`.

The defaults are GL's: `Square`, `Triangle` and `Rectangle` stroke `#DDDDDD`,
`Circle` `#FC6255`, `YELLOW` is `#FFFF00` (CE's palette lives under
`ManimCE.YELLOW` and friends).

## 5 · Animations

```python
self.play(FadeIn(c), Write(t), run_time=1.5, rate_func=linear)   # the dials go into EVERY animation given
self.play(AnimationGroup(a, b, lag_ratio=0.2, run_time=2.0))     # the group's T is shared
self.play(LaggedStart(*(GrowFromCenter(d) for d in dots), lag_ratio=0.2))
self.play(Succession(a, b))           # begins each animation when its turn comes (and snapshots then)
self.wait(0.5)
```

- `.animate` is ManimGL's builder and it is EAGER (measured): touching
  `m.animate` calls `m.generate_target()`, every chained call mutates that
  target NOW, and the result is a `MoveToTarget`. The dials go in the call:
  `m.animate(run_time=2, rate_func=linear).shift(RIGHT).rotate(PI)`. Two
  `.animate` on the same mobject in one `play` share `m.target`: the last
  wins. It works on `vt.animate.set_value(10)` and on `self.frame`.
- `rate_func` belongs to the animation; `smooth` is GL's quintic, not CE's
  sigmoid. `play` adds the animation's mobject for you.
- `Transform(a, b)` never mutates `b`, and the scene keeps `a` wearing b's
  shape; `ReplacementTransform(a, b)` leaves the scene holding `b`. Removers
  (`FadeOut`, `Uncreate`, `Unwrite`) hand the mobject back INTACT.
- `ShowCreation` and `Create` are one class. `Rotating` moves along arcs,
  `Transform` along chords.
- An animation of your own subclasses `Animation`: snapshot in `begin` (never
  in `__init__`, a `Succession` may begin it much later) and apply
  `self.rate_func` yourself in `interpolate(alpha)`. Worked examples:
  `examples/tutorial/c2_02_custom_animations/`.

## 6 · Updaters and trackers

```python
t = ValueTracker(0.3)
dot = Dot(ORIGIN, radius=0.1).set_fill(RED)
dot.add_updater(lambda m: m.move_to((t.get_value(), 0, 0)))           # no dt: the arity decides
chord = always_redraw(lambda: Line(LEFT, (t.get_value(), 1, 0)).set_stroke(YELLOW, width=3))
trail = TracedPath(dot.get_center, stroke_color=RED, time_traced=3.0)
self.add(dot, chord, trail)
self.play(t.animate.set_value(2.0), run_time=2)
```

Traps, each paid for:

- **The arity decides** whether an updater gets `dt`: `lambda m, dt:` is
  time-based, `lambda m:` is not, whatever the second parameter is called. A
  DEFAULTED second parameter receives `dt` too (`lambda m, n=n:` gets `dt` in
  `n`): capture with a closure or `functools.partial`.
- Registration calls the updater once with `dt = 0`: an integrator guards
  with `if dt > 0`.
- **A mobject whose points are made inside an updater must be BORN with its
  final style**: new points re-stamp the factory style, so a later `set_fill`
  or a fade writes on water. `always_redraw` and `TracedPath` handle it.
- **Freeze an updater before fading its mobject out** (a flag its closure
  reads), or it keeps re-stamping the style and the fade does nothing.
- Update order is `self.mobjects` in order, and `bring_to_back` also moves the
  UPDATE order: a trail sent to the back samples one frame late. Layer with
  `set_z_index` instead.
- Arrays written in place (`cloud.get_points()[:] = …`) are seen by the
  renderer; a `Group` above a mesh caches its box, so tell it:
  `m.note_changed_data()`.

## 7 · Groups

`VGroup(*mobs)` holds VMobjects only and REFUSES anything else
(`TypeError: VMobject children must be VMobjects; use Group for mixed objects`).
`Group(*mobs)` holds any mobject — a `ValueTracker`, a `Surface`, an
`ImageMobject` — and moves and animates like a VGroup.
`VGroup(*[Dot() for _ in range(5)])` is the same Python as in Manim.

## 8 · Beyond flat 2D

- **Camera**: `self.frame` is a `CameraFrame`, a mobject on stage from the
  start. `self.frame.set_frame_height(6)`, `.scale_frame(0.5)` (< 1 zooms in),
  `.move_to(p)`, `.reorient(theta_deg, phi_deg)`, `.reset_frame()`, all
  animatable (`self.frame.animate.reorient(25, 55)`).
  `self.frame.add_updater(lambda f: f.move_to(dot))` is a chase camera.
  `to_edge` stays nominal under a zoom; a HUD that must ignore the camera is
  `m.fix_in_frame()`.
- **3D**: `ThreeDScene` is a `Scene` born at θ = −30°, φ = 70° with the depth
  test on. Otherwise `m.apply_depth_test()` joins the z-buffer (OFF by
  default: in 2D, order is the answer) and `m.set_shading(...)` lights a mesh.
  Meshes: `Surface`, `Sphere`, `Torus`, `Cube`, `Dot3D`, `ThreeDAxes`…
  `docs/3d.md`.
- **Compositor** (no Manim equivalent): layers, masks, blur, glow, a second
  camera → `janim-compositor`.
- **Text and formulas** → `janim-text`.
- **Simulations**: `janim.ode` is a Tsit5 integrator (`ODEProblem`, `init`,
  `step`). Four rules: the integrator lives OUTSIDE the updater and is stepped
  by `dt`; guard `if dt > 0`; ONE integrator drives everything; do not
  motion-blur integrated physics. `examples/tutorial/c2_04_simulations/`.
- **Your own trig**: `from janim.math import sin, cos, hypot` — Julia's libm
  bit for bit, for floats and for whole arrays — so frames match on every
  machine. `math.sin` and `np.sin` differ in the last bit on ~3 % of inputs.

## 9 · Determinism

Same code → same frames, byte for byte, in any process. No wall clock in a
scene and no unseeded randomness (`np.random.default_rng(seed)` is fine). The
mp4 CONTAINER is x264's: `encoder_threads=1` makes the file itself
reproducible; the frames always are.

## 10 · Then verify, by looking

Never call a scene done without looking at pixels. Load `janim-verify`.

## 11 · The few-shot corpus in this repo

- `examples/tutorial/` — 93 runnable lessons in four courses;
  `examples/tutorial/README.md` is the index. Each lesson is a `Scene` with the
  explanation in its docstring and the `__main__` block above.
- `examples/gallery/`, `examples/scenes/`, `examples/demo/` — classics,
  complete scenes, and the compositor and camera demos (`*.es.py` are the
  Spanish originals).
- `llms.txt` — the whole API in one file. `docs/cli.md`, `docs/compositor.md`,
  `docs/3d.md` — the manuals.
