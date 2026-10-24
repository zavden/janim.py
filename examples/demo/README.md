# demo/ — twelve things Janim does that Manim cannot, in Python

Janim demonstration scenes: short scenes (7–23 s, 1280×720), each built
around ONE capability that neither ManimCE nor ManimGL has — the layer
compositor and everything built on it (masks, blend modes, effects, a
camera per layer), plus physics inside an updater and a million-particle cloud.

Comments, identifiers and on-screen text (labels, captions, titles) are in
**English**. The original Spanish-commented files are preserved alongside
them as `*.es.py`; the original guide is [README.es.md](README.es.md).

## How to render them

From the repository root, inside the project's virtual environment,
through the CLI (one process per call):

```bash
bin/janim render examples/demo/03_portals.py -ql     # video, beside the scene
bin/janim examples/demo/09_reflection.py             # live window (preview)
bin/janim frame examples/demo/03_portals.py 90 f.png -ql   # ONE frame (re-simulates from t = 0)
```

Presets set resolution AND fps: `-qs` 640×360@10, `-ql` 854×480@15,
`-qm` 1280×720@30 (the CLI default), `-qh` 1920×1080@60. Each file
contains a single scene, so there is no need to name the class.

Each file is also a complete script with its own entry point:

```bash
python examples/demo/12_motion_blur.py   # 1280×720@30, mp4 beside the .py
```

Prefix any of these commands with `JANIM_HEADLESS=1` to render on the
CPU (lavapipe); without it, the native GPU is used.

A warning that may appear at startup (once for each σ that does not fit)
is not an error: `RuntimeWarning: gaussian-kernel-radius-limit`. The
compositor kernel computes in full up to a radius of 63 px (σ = 21 px);
an effect asking for more warns instead of silently accepting it:
the halo is slightly narrower than requested. Demo 09 at 720p, for
example, warns three times: its Bloom's 2σ and 4σ levels, and the
reflection mask's `feather = 0.7` (63 px of σ).

## Index

| # | file | class | what only Janim can do | duration |
|---|---|---|---|---|
| 01 | `01_multicam.py` | `Multicam` | **One camera per layer**: four views of the SAME 3D world, each with its own z-buffer, with updaters running only once. | 14 s |
| 02 | `02_pendulum_glow.py` | `PendulumGlow` | **Physics (`janim.ode`'s Tsit5) in an updater + an additive layer with Bloom + an animated mask**: a double pendulum with the full grid; the trail is joined with `set_points_smoothly`, the bob has a `GlowDot` behind it (a round per-fragment halo), and the spotlight following the tip is a `crop` with `feather`. | 23 s |
| 03 | `03_portals.py` | `Portals` | **Masked multicamera in 2D**: a rosette in the center (the scene camera) and two IDENTICAL ×3 magnifiers at the sides — a circle and a star that SPINS in place — each with a camera chasing its dot (an updater on the `CameraFrame`); the portal shape is just the mask (`window` + `crop`), so it can rotate while the image stays upright. | 14 s |
| 04 | `04_lorenz_glow.py` | `LorenzGlow` | **10⁶ `GlowDots` particles + `"add"` + Bloom**: the Lorenz attractor with a 15 s camera flight. | 18 s |
| 05 | `05_rack_focus.py` | `RackFocus` | **Per-layer depth of field** (`Dof`): five formulas at five depths; focus travels from nearest to farthest by writing a number, with parallax as a bonus. | 13 s |
| 06 | `06_broadcast.py` | `BroadcastScene` | **Editor effects** (`Glitch`, `CRT` with `roll`, `VHS`, `ColorAdjust`) over a formula that keeps morphing underneath; every dial returns to zero, an exact no-op. | 20 s |
| 07 | `07_text_mask.py` | `TextMask` | **Text masking a lit 3D render**: “JANIM” clips a sea of waves seen through its own camera, ending with an opening-title flight through the “I”. | 14 s |
| 08 | `08_light_vs_pigment.py` | `LightVsPigment` | **Blend modes in linear light**: R+G+B = white with `"add"`, C×M×Y = black with `"multiply"`, each disc in its own layer, light discs in a precomposition with Bloom. | 12 s |
| 09 | `09_reflection.py` | `Reflection` | **A real reflection**: a flipped copy in a layer with `Wave` (animated phase), `Blur`, `opacity` and a feathered `Mask` that fades it with distance; moon and stars with Bloom, adjustment `Vignette`. | 13 s |
| 10 | `10_motion_blur.py` | `MotionBlur` | An accelerating wheel, four orbits and a camera sweep, written for sub-exposure **motion blur** that the render loop does not apply: video uses single exposures (below). | 9 s |
| 11 | `11_chase_camera.py` | `ChaseCamera` | **Chase and minimap**: a comet on a trefoil knot with the main camera orbiting, a CHASE camera driven by an updater (what requires a `ZoomedScene` in CE), and an overhead minimap in a square window; the HUD stays put with `fix_in_frame()`. | 22 s |
| 12 | `12_motion_blur.py` | `MotionBlurWelcome` | A variation on 10: “Welcome / to / JANIM” whipping in, “JANIM” in Fredoka Expanded; also written for sub-exposure motion blur. | 7 s |

## What it takes to make them look right (and why)

- **One disc per layer** (08). Within a layer, mobjects cover one another;
  the blend mode acts between the entire layer and what lies below.
  If all three discs shared one layer, `"add"` would add nothing.
- **The mask is not drawn; the rim is** (03, 07). The clipping shape is
  filled white and belongs to no content layer; the visible border is
  ANOTHER stroke-only mobject in a layer above.
- **A star's bounding-box center is not its center** (03). `rotate`
  pivots around `get_center()` (the box), which on a five-pointed star
  is 0.2 units above the real center: the star orbited instead of
  spinning. Placing and rotating it around `get_real_center_of_mass()`
  (the exact centroid) fixes this. And because `window=` places the
  image in the mobject's BOX, a rotating star would wobble the image by
  ±0.2 units: that layer's window is an invisible fixed square, and the
  star is only the mask.
- **A tail matching the stroke is invisible** (03). A yellow
  `TracingTail` over the gradient rosette disappeared when crossing
  the yellow lobe; a thicker white tail reads clearly in all three views.
- **Two animations on the same mobject overwrite each other** (07).
  Each writes the entire state, so simultaneous `FadeOut` and
  `.animate` on the rim left it stationary. A single `.animate` with
  two chained operations
  (`.scale(90.0, about_point=anchor).set_stroke(opacity=0.0)`) does both.
- **σ has an honest ceiling**: 0.23 units at 720p (21 px). Demo 05's
  `Dof` therefore uses `max_sigma=0.23`; requesting 3.0 only produces
  the warning above and a truncated blur.
- **A truncated Bloom makes SQUARE halos** (02). The pyramid's 4σ level
  with `sigma=0.16` requested 58 px, and the kernel cut it at ±63:
  a truncated Gaussian is almost a box, and a separable H+V box around
  a bright point is a square. It is unnoticeable on a long stroke,
  but obvious on the bob. Two-part fix: `sigma=0.055` (all three
  levels fit) and a `GlowDot` behind the bob, a round per-fragment
  halo independent of the kernel.
- **The initial state already drawn** (02). Rod, bobs and spotlight
  are placed at the initial state's positions BEFORE starting the
  integrator: nothing starts at the origin and jumps a frame later.
- **There is no motion blur in the render loop** (04, 10, 12).
  `Scene` has no `motion_blur` kwarg, and the CLI rejects
  `--motion-blur` by name (exit 2). Scenes render without it;
  the animation is the same.
- **`render_frame_motion` does not show true motion blur**: it renders
  the frame containing each sub-exposure, and because the shutter
  window (`shutter / fps`) is shorter than a frame, it averages at most
  TWO distinct frames — two copies, not a trail. Measured in demo 10
  at t = 4 s:
  `render_frame_motion(MotionBlur, 4.0, n=8, shutter=0.5, fps=30)`
  shows each particle twice. To truly sample a 180° shutter at 30 fps,
  supply a finer clock and open the shutter proportionally:
  `render_frame_motion(MotionBlur, 4.0, n=8, shutter=4.0, fps=240)`
  distributes the eight sub-exposures over four 1/240 s frames and
  produces a trail. This only applies to scenes whose state is a
  function of time (10, 12): an integrator advancing with `dt` (02, 04)
  simulates SOMETHING ELSE at a different fps.
- **Python numerical details** handled carefully so frames always match:
  `sin`/`cos` from `janim.math` (not `math`, which differs in the
  last bit for ~3% of inputs); ranges from `janim.math`
  (`step_range`, `linear_range`); in numpy 2,
  `0.22 * array_float32` remains float32, so values are explicitly
  promoted where Float64 is needed (03, 09: in 03 this does not move
  a pixel at 360p, but it is the exact calculation); `x ** 2` is
  written `x * x`; `enumerate` starts at 1 when the index enters an
  angle (08); and a `lambda` inside a `for` sees only the last
  iteration (05: it is created with a function).
