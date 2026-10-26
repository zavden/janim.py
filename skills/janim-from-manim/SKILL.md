---
name: janim-from-manim
description: Translate a ManimCE or ManimGL scene into Janim.py, or say what a Manim construct becomes there — what survives verbatim (most of it), the measured defaults that differ (CE's shape colours, Pango's text height, CE's `smooth`, `YELLOW`), the renamed knobs (`config`→kwargs, `-pql`→`-ql`, `self.camera.frame`→`self.frame`, `x_length`→`width`), and what has no equivalent (`MarkupText`, `Union`, `Graph`, `BarChart`, `ZoomedScene`…). Use when porting a `.py` written for `manim` or `manimlib`, when a user pastes Manim code into a Janim checkout, or when comparing Janim.py with Manim.
---

# Translating Manim → Janim.py

Janim.py speaks ManimGL's language, so most of a scene translates by changing
one import. This skill is about the rest: the knobs that moved, the defaults
that differ (measured, not remembered), and what does not exist.

## 1 · What changes, and what does not

| Manim CE / GL | Janim.py |
|---|---|
| `from manim import *` / `from manimlib import *` | `from janim import *` |
| `class S(Scene): def construct(self):`, `self.play`, `self.wait`, `self.add`, `self.remove` | identical |
| `m.set_fill(BLUE, opacity=0.5)`, `next_to`, `to_edge`, `arrange`, `VGroup(*mobs)`, `always_redraw`, `ValueTracker` | identical |
| `Create` / `ShowCreation` | both names, one class |
| `m.animate.shift(RIGHT).set_color(YELLOW)` | identical — GL's EAGER builder: the target is built when the line runs (§3) |
| `Text("hi", font_size=48)` | works; `size=0.6` is Janim's own unit (scene units) |
| `MathTex`, `Tex`, `TexText` through LaTeX | identical names; `isolate=` and `t2c=` give the keys (`janim-text`) |
| `MarkupText` (Pango markup) | none — `Text` with `t2c`/`t2w` |
| `config.frame_rate = 60`, `manim.cfg`, `with tempconfig({…})` | `Scene` kwargs: `Demo(fps=60, resolution=(1920, 1080)).render()`; a dict splatted in is the config dict |
| `manim -pql file.py Demo` | `bin/janim render file.py:Demo -ql -p` |
| `self.camera.frame` (CE), `self.frame` (GL) | `self.frame`, a `CameraFrame`: `set_frame_height(6)`, `scale_frame(0.5)`, `move_to`, `reorient` |
| `MovingCameraScene`, `ThreeDScene` | exist; `MovingCameraScene` IS `Scene` (every camera animates); `ThreeDScene` starts at θ = −30°, φ = 70° with the depth test on |
| `self.set_camera_orientation(phi=70 * DEGREES, theta=-30 * DEGREES)` | `self.frame.reorient(-30, 70)` — THETA FIRST, in DEGREES |
| `self.move_camera(phi=…, theta=…)` | `self.play(self.frame.animate.reorient(theta_deg, phi_deg))` |
| `self.begin_ambient_camera_rotation(rate=0.1)` | `self.frame.add_updater(lambda f, dt: f.increment_theta(0.1 * dt))` (radians) |
| `self.add_fixed_in_frame_mobjects(hud)` | `hud.fix_in_frame()` |
| `Axes(x_range=[-3, 3, 1], y_range=[-2, 2, 1], x_length=6, y_length=4)` | `Axes((-3.0, 3.0, 1.0), (-2.0, 2.0, 1.0), width=6, height=4)`; `plot`, `c2p`, `p2c`, `get_area`, `get_graph_label` as in CE |
| `ZoomedScene` | `Layer(*world, camera=CameraFrame(), window=rect)` in a `Composition` — a real second render (`janim-compositor`) |
| `self.embed()` (GL) | `bin/janim scene.py`, the live window that re-runs the file on save |
| `checkpoint_paste()` (GL) | `self.checkpoint("label")` + `bin/janim render scene.py --from label` |
| `Code(code_string=…, language="python")` | CE's signature and geometry, through pygments |
| `Union`, `Intersection`, `Difference`, `Exclusion` | none; `Cutout(shape, *holes)` covers "shape minus shapes" |
| `Graph`, `DiGraph`, `BarChart` | none (the layouts would need networkx) |
| CE's `ArrowTriangleTip`, `StealthTip`… | none: an `Arrow` is ONE contour with its tip inside (GL's) |
| `Add`, `ChangeSpeed`, `ClockwiseTransform` | `self.add`, a `rate_func`, `Transform(a, b, path_arc=-PI)` |
| `PointCloudDot`, `Point`, `ParametricFunction`, `ArrowVectorField` | `DotCloud`, `VectorizedPoint`, `ParametricCurve`, `VectorField` |
| motion blur, `--motion-blur` | not in the loop; `render_frame_motion` is the blurred still |

## 2 · The defaults, measured (CE 0.22.0 · GL 1.7.2 · Janim.py 1.0, 2026-10-26)

| | CE | GL | Janim.py |
|---|---|---|---|
| `Square()`, `Rectangle()` stroke | `#FFFFFF` | `#DDDDDD` | `#DDDDDD` |
| `Circle()` stroke | `#FC6255` | `#FC6255` | `#FC6255` |
| `Triangle()` stroke | **`#58C4DD`** (blue) | `#DDDDDD` | `#DDDDDD` |
| `Dot(color=BLUE)` | blue fill | **white** fill | **white** → `fill_color=BLUE` |
| `Arrow(a, b, color=RED)` | red, the tip is a child | **grey** fill, zero-width stroke | **grey** → `fill_color=RED` |
| `Text("hi")` height at font_size 48 | 0.506 (Pango) | 0.345 | 0.345 |
| `MathTex("x")` height | 0.226 | 0.219 | 0.220 |
| `smooth(0.25)` | 0.0701 (sigmoid) | 0.1035 (quintic) | 0.1035 |
| `YELLOW` | `#F7D96F` | `#FFFF00` | `#FFFF00` (`ManimCE.YELLOW` is CE's) |
| frame | 14.222 × 8, edge buff 0.5 | same | same |

GL and Janim agree on every row; CE departs from GL. So **when CE disagrees
with Janim, ask GL before calling it a divergence**: Janim ports GL, and the
difference is usually CE's. Geometry (`Square(side_length=2)`,
`Circle(radius=1)`, `Rectangle(width=4, height=2)`, `Triangle` 1.73 × 1.5
pointing up, the four `to_corner` positions) agrees to six decimals across
all three.

## 3 · Five things that are NOT a literal translation

1. **`.animate` is eager.** Touching `m.animate` calls `generate_target()`
   NOW and each chained call mutates `m.target` immediately; `play` turns it
   into a `MoveToTarget`. A CE scene that reads `m.get_center()` between
   building the builder and playing it reads the OLD position (as in GL, not
   as in CE's lazy builder). Two `.animate` on one mobject in one `play` share
   the target: the last wins.
2. **Text is FreeType, formulas are LaTeX.** No Pango (`MarkupText`, weights
   as free text, complex scripts), and a `Tex` glyph answers only to the
   `isolate`/`t2c` keys you gave — `tex[0:3]` by position still works.
3. **There is no config.** `config.*`, `tempconfig`, `manim.cfg` and the long
   cousins of `-pql` are `Scene` kwargs and CLI flags; precedence is
   `CLI flag > kwargs > defaults`, resolved by building the scene.
4. **A render is one process.** No daemon, no partial-movie cache, no
   `disable_caching`: every call re-simulates. `--from label` skips drawing,
   not simulating.
5. **Nested comprehensions and `*` splats are the same Python** — the only
   thing to port there is nothing.

## 4 · Run the reference instead of remembering it

If Manim is installed, probe it. Three claims written from memory about
defaults were false the last time this was tried, and a five-line probe
caught all three:

```bash
python -c "from manim import *; m = Triangle(); print(m.get_stroke_color().to_hex(), m.width, Text('hi').height)"
manim -ql --media_dir /tmp/manim_media file.py Demo        # keep its output out of the repo
```

Then render the Janim side (`bin/janim render file.py -ql`), look at BOTH,
and compare hues and geometry — not bytes: identical colours still differ on
the antialiased edge pixels between renderers.

## 5 · The annotated format for a translation

When the port is meant to teach, as `examples/tutorial/c2_05_from_manim/01_from_manim_ce.py`
and `02_from_manimgl.py` do: keep the original line in a comment above its
translation, give the most space to the lines that translate to NOTHING (that
is where the design difference lives), invent no animation the original did
not have, and state what was actually verified — "described from the
documentation" is not a footnote this repository accepts.

## 6 · Verify

Render it and look (`janim-verify`). A translation that runs is not a
translation that matches, and the divergences of §2 are exactly the kind no
exception reports.
