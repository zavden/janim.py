# The Janim course

Four courses, 90 runnable lessons, written in Manim syntax. Every lesson is a
real scene you can render, preview, edit and break; the explanation lives in
its docstring, next to the code it is about.

| Course | What it covers | Lessons |
|---|---|---|
| 1 — Foundations | mobjects, animations, configuration, assets, groups, text and formulas, rate functions, the utility belt, plots, updaters, fields and particles, source code listings | 34 |
| 2 — Going deeper | alpha and dt updaters, custom mobjects, custom animations, the camera, simulations, coming from Manim, writing shaders | 14 |
| 3 — Only in Janim | the layer compositor, blur and glow, masks, glitch and the editor effects, motion blur, and a capstone | 40 |
| 4 — The complete reference | the shape zoo: every flat constructor, groups and the base types — in progress | 2 |

Courses 1 and 2 follow the shape of a ManimCE/ManimGL course, so a Manim user
recognises the syllabus; where Janim does something differently, the
lesson says so. Course 3 has no Manim equivalent at all: a compositor of
layers is a consequence of Janim's architecture, not a feature that could be
bolted onto Manim's.

## Running a lesson

Every lesson defines a `Scene` subclass — the contract the CLI, the farm and
the live window all look up — and renders itself when run directly. From the
repository root, inside the project's virtual environment:

```bash
bin/janim render examples/tutorial/c1_01_basics/02_mobjects_and_animations.py -ql
# → examples/tutorial/c1_01_basics/02_mobjects_and_animations.mp4 (beside the lesson;
#   -ql is 854x480 at 15 fps — add --fps 30 for the lessons' own rate, --out_dir DIR to move it)
python examples/tutorial/c1_01_basics/02_mobjects_and_animations.py
# → examples/tutorial/output/c1_01_basics/02_mobjects_and_animations.mp4,
#   at the lesson's own settings (most are 854x480 at 30 fps)
```

The same file works with the rest of the CLI (`docs/cli.md`):

```bash
bin/janim examples/tutorial/c1_01_basics/06_layers.py                   # the live window; Esc/q quits
bin/janim frame examples/tutorial/c1_01_basics/06_layers.py 40 f.png    # one frame (re-simulated from t = 0)
bin/janim render examples/tutorial/c1_02_config_and_assets/07_multiscene.py:Intro -ql   # one scene of several
```

`JANIM_HEADLESS=1` renders on the CPU adapter (lavapipe) instead of the GPU
(Linux only: macOS has no CPU adapter).

A lesson marks the moment worth looking at in two constants: `PREVIEW_T` (the
second worth looking at, default 1.0) and `PREVIEW_MOTION` (sub-exposures, for
the motion-blur lessons whose subject is invisible in an instantaneous frame).
Pass them to `render_frame(Class, PREVIEW_T)` or
`render_frame_motion(Class, PREVIEW_T, n=PREVIEW_MOTION)` to get that one frame
as a PNG. A file with several scenes names the lesson's with `SCENE = <class>`.
**A lesson that renders is not a lesson that is right** — look at the frames.

## Course 1 — Foundations

### 1 · `c1_01_basics` — the elements

| Lesson | Class | What it teaches |
|---|---|---|
| `01_how_janim_works.py` | `HowJanimWorks` | `construct(self)` as a contract; frames as steps of a fixed clock — the αs are the midpoints `(k + ½)/n` |
| `02_mobjects_and_animations.py` | `MobjectsAndAnimations` | `self.add` vs `self.play`, the four basic animations; `play` adds the mobject, a remover takes it out |
| `03_setters_and_getters.py` | `SettersAndGetters` | style, placement, size and the bounding-box getters; `set_fill(opacity=…)` without a colour keeps each point's colour |
| `04_animation_properties.py` | `AnimationProperties` | `run_time`, `rate_func`, `lag_ratio`, `remover`; `lag_ratio` staggers a family on one animation and animations in a group |
| `05_copies.py` | `Copies` | `copy()` is deep; where copies appear whether you ask or not (`Transform`, `TransformFromCopy`, `.animate`) |
| `06_layers.py` | `Layers` | draw order, `set_z_index`, `bring_to_front`/`bring_to_back` — which also moves the update order |

### 2 · `c1_02_config_and_assets` — configuration and files

| Lesson | Class | What it teaches |
|---|---|---|
| `01_configuration.py` | `Configuration` | there is no config file: `CLI flag > Scene kwargs > defaults`, resolved by building the scene |
| `02_cli.py` | `Cli` | `bin/janim`: render, frame, preview, states, the farm — one process per call |
| `03_config_dict.py` | `ConfigDict` | Manim's config dict as a plain dict splatted into the scene; `encoder_threads=1` for a byte-reproducible mp4 |
| `04_svg_import.py` | `SVGImport` | `SVGMobject` from a file or a string; ids become keys |
| `05_image_import.py` | `ImageImport` | `ImageMobject` from an array computed in Python, and `TexturedSurface` |
| `06_audio_import.py` | `AudioImport` | `add_sound`, with a wav synthesised in the lesson; the audio is muxed at close, so the video stays deterministic |
| `07_multiscene.py` | `Intro`, `Orbit`, `Multiscene` (`SCENE`) | several scenes in one file: `file.py:Class` on every verb, and mixing scenes by plain calls |

### 3 · `c1_03_groups_and_text` — groups, text and formulas

| Lesson | Class | What it teaches |
|---|---|---|
| `01_groups_vs_vgroups.py` | `GroupsVsVGroups` | `VGroup` (vector geometry) vs `Group` (anything); `AnimationGroup` picks for you |
| `02_comprehensions.py` | `Comprehensions` | building many mobjects with comprehensions and the `*` splat; `step_range` for float ranges |
| `03_text.py` | `TextLesson` | `Text` through FreeType, fonts, `t2c`, `t2w`; a missing weight is an error, not a fallback |
| `04_latex.py` | `Formulas` | `Tex` through LaTeX, Janim's one route: a parent plus one child per glyph |
| `05_latex_config.py` | `LatexConfig` | the typesetting route: Janim has one, LaTeX |
| `06_tex_transformations.py` | `TexTransformations` | `TransformMatchingTex`: when it ends the scene holds the target |
| `07_symbol_by_symbol.py` | `SymbolBySymbol` | `tex[2]`, `tex["x^2"]`, `isolate`; through LaTeX a glyph answers only to `isolate`/`t2c` |
| `08_code.py` | `CodeLesson` | ManimCE's `Code`: pygments styles, line numbers, the window background; a listing is a parent of glyphs |

### 4 · `c1_04_animations` — animations

| Lesson | Class | What it teaches |
|---|---|---|
| `01_rate_functions.py` | `RateFunctions` | the whole rate-function family, drawn and raced; `rate_func` belongs to the animation |
| `02_class_animations.py` | `ClassAnimations` | an animation is a value with a three-act life; `Rotating` (arcs) is not a `Transform` (chords) |
| `03_method_animations.py` | `MethodAnimations` | `.animate`, the chainable proxy — with an eager target |
| `04_animation_group.py` | `AnimationGroupLesson` | `AnimationGroup`, `LaggedStart`, `Succession` — which begins each animation late, and why it is a type |

### 5 · `c1_05_utilities` — the utility belt

| Lesson | Class | What it teaches |
|---|---|---|
| `01_useful_methods.py` | `UsefulMethods` | `next_to`, `align_to`, `arrange`, `arrange_in_grid`, `surround`; `to_edge` uses the nominal frame |
| `02_useful_mobjects.py` | `UsefulMobjects` | the shape zoo, annotations, `Angle`, matrices; `Brace` is a native path, not LaTeX |
| `03_useful_animations.py` | `UsefulAnimations` | `Indicate`, `Flash`, `Circumscribe`, `Wiggle`, `FocusOn`, the growers, `UpdateFromAlphaFunc` |
| `04_extending_janim.py` | `ExtendingJanim` | the extension seams — Manim's "plugins": a function, and a `VMobject` subclass |

### 6 · `c1_06_plots_and_updaters` — plots and updaters

| Lesson | Class | What it teaches |
|---|---|---|
| `01_plots_2d.py` | `Plots2D` | `Axes`, `c2p`/`p2c`, `plot`, `get_area`, `PolarPlane`; the map is read off the live geometry |
| `02_plots_3d.py` | `Plots3D` | `ThreeDAxes`, `Surface`, `reorient`, `apply_depth_test`; `fix_in_frame` is how a HUD ignores the camera |
| `03_basic_updaters.py` | `BasicUpdaters` | `add_updater`, `always_redraw`, `ValueTracker`, `DecimalNumber`, `TracedPath`; born styled |
| `04_vector_fields.py` | `VectorFields` | `TimeVaryingVectorField`, `StreamLines`, `AnimatedStreamLines`; a field is one mobject with hashed seeds |
| `05_particles.py` | `Particles` | `GlowDots`, `DotCloud`, `make_3d`, the in-place updater idiom; glow vs Bloom |

## Course 2 — Going deeper

### 1 · `c2_01_updaters_and_custom_mobjects`

| Lesson | Class | What it teaches |
|---|---|---|
| `01_alpha_updaters.py` | `AlphaUpdaters` | `UpdateFromAlphaFunc`, `UpdateFromFunc`: no snapshot, so it drives a `Surface` |
| `02_dt_updaters.py` | `DtUpdaters` | the dt form and its four traps; registration calls the updater with `dt = 0` |
| `03_custom_mobjects.py` | `CustomMobjects` | seam A, a shape (`VMobject` subclass), and seam B, a `Mobject` with the interpolation contract |

### 2 · `c2_02_custom_animations`

| Lesson | Class | What it teaches |
|---|---|---|
| `01_anatomy.py` | `Anatomy` | `begin` / `interpolate` / `finish`; snapshot in `begin`, apply the rate function yourself |
| `02_a_real_one.py` | `ARealOne` | one animation driving three mobjects: make its mobject a `Group` of all of them |

### 3 · `c2_03_camera`

| Lesson | Class | What it teaches |
|---|---|---|
| `01_moving_camera.py` | `MovingCamera` | `self.frame` is a mobject: zoom, pan, `reset_frame`; `to_edge` stays nominal |
| `02_zoomed_camera.py` | `ZoomedCamera` | the magnifier: a `Layer` with its own `camera=` and `window=` — a real second render |
| `03_camera_3d.py` | `Camera3D` | `reorient`, `apply_depth_test`, `fix_in_frame`; 2D mobjects stay out of the z-buffer by default |

### 4 · `c2_04_simulations`

| Lesson | Class | What it teaches |
|---|---|---|
| `01_ode_pendulum.py` | `OdePendulum` | `janim.ode`'s Tsit5 inside an updater: integrator outside, `dt > 0`, one for everything |
| `02_gradient_descent.py` | `GradientDescent` | forward-mode duals (`janim.ode.dual.gradient`) through the whole drawing |

### 5 · `c2_05_from_manim`

| Lesson | Class | What it teaches |
|---|---|---|
| `01_from_manim_ce.py` | `FromManimCE` | a CE scene line by line, with the original in the comments, and where CE and Janim still disagree |
| `02_from_manimgl.py` | `FromManimGL` | a ManimGL scene, and what `embed()` / `checkpoint_paste()` become |

### 6 · `c2_06_shaders`

| Lesson | Class | What it teaches |
|---|---|---|
| `01_write_a_layer_effect.py` | `WriteALayerEffect` | a mutable dataclass, a WGSL fragment (`effect_shader`), one `apply_effect` handler; premultiplied, exact no-op at zero |
| `02_noise_and_determinism.py` | `NoiseAndDeterminism` | `janim_noise_px`, `current_frame`, `_noise_seed`: randomness without breaking determinism |

## Course 3 — Only in Janim

### 1 · `c3_01_layers` — the compositor

| Lesson | Class | What it teaches |
|---|---|---|
| `01_one_layer.py` | `OneLayer` | `Layer`, `Composition`, `use_composition` — a mounted composition replaces `self.mobjects` as what is drawn |
| `02_blend_modes.py` | `BlendModes` | `"normal"`, `"add"`, `"multiply"`, `"screen"`, `"overlay"`, and the W3C equation behind them |
| `03_layer_opacity.py` | `LayerOpacity` | layer opacity vs mobject opacity: the seams |
| `04_adjustment_layer.py` | `AdjustmentLayer` | a layer with NO content grades everything below it |
| `05_precomp.py` | `Precomp` | a `Composition` as a layer's content: blurring the RESULT of a blend |
| `06_track_matte.py` | `TrackMatte` | `matte="alpha"` / `"luma"` / … consumes the next layer as coverage |
| `07_layers_vs_zindex.py` | `LayersVsZIndex` | z-index for ORDER, a layer for TREATMENT |
| `08_animated_composition.py` | `AnimatedComposition` | every layer parameter and effect dial is a mutable field |

### 2 · `c3_02_blur_and_glow` — blur and glow

| Lesson | Class | What it teaches |
|---|---|---|
| `01_blur_basics.py` | `BlurBasics` | `Blur(sigma)`; sigma in scene units so the look survives the resolution |
| `02_blur_animated.py` | `BlurAnimated` | the dream transition: blur up, swap, blur down |
| `03_box_blur.py` | `BoxBlurLesson` | `BoxBlur`, its hard cut-off, and why three chained ≈ a Gaussian |
| `04_directional_blur.py` | `DirectionalBlurLesson` | `DirectionalBlur`, and why it is not motion blur |
| `05_radial_blur.py` | `RadialBlurLesson` | `RadialBlur`: the centre stays sharp |
| `06_bloom.py` | `BloomLesson` | `Bloom` as bright pass → pyramid → add, and how to tune each dial |
| `07_depth_of_field.py` | `DepthOfField` | `Dof`: sigma from the layer's distance to the focal plane; rack focus |
| `08_glow_pipeline.py` | `GlowPipeline` | the neon recipe: `blend="add"` + `Bloom` + a dark background + a dim tube |

### 3 · `c3_03_masks` — clipping masks

| Lesson | Class | What it teaches |
|---|---|---|
| `01_mask_basics.py` | `MaskBasics` | `Mask(*shapes)`: coverage per pixel, and the shapes are never drawn |
| `02_crop_inside_minus.py` | `CropInsideMinus` | `crop(base, inside=…)` vs `crop(base, minus=…)` |
| `03_feather.py` | `Feather` | feather blurs the MASK, not the layer — and the difference is visible |
| `04_invert_and_hard.py` | `InvertAndHard` | `invert`, and `hard` as a threshold over a feathered stencil |
| `05_luma_mask.py` | `LumaMask` | brightness as coverage: gradients and wipes |
| `06_animated_spotlight.py` | `AnimatedSpotlight` | a mask that FOLLOWS; parking it off screen to start |
| `07_text_as_mask.py` | `TextAsMask` | the world seen through the letters, and punched out of them |
| `08_svg_clip_layers.py` | `SVGClipLayers` | `clip_layers(svg)`: an SVG's own `clipPath`s, honoured per pixel |

### 4 · `c3_04_glitch` — glitch and the editor family

| Lesson | Class | What it teaches |
|---|---|---|
| `01_glitch_basics.py` | `GlitchBasics` | `Glitch`: bands, blocks, RGB split; `rate` in frames; 0 is an exact no-op |
| `02_glitch_animated.py` | `GlitchAnimated` | a spike, not a swell — and deterministic irregularity |
| `03_crt.py` | `CRTLesson` | `CRT`: scanlines as a count, curvature as a fraction of the frame |
| `04_crt_roll.py` | `CrtRoll` | `roll`: a television losing sync, with no internal clock |
| `05_vhs.py` | `VHSLesson` | `VHS`: the chroma smear takes colour and never luma |
| `06_cheap_family.py` | `CheapFamily` | `ColorAdjust`, `Pixelate`, `Vignette`, `Grain` |
| `07_chromatic_and_sharpen.py` | `ChromaticAndSharpen` | a radial split, and the unsharp mask that is exactly identity on flats |
| `08_wave.py` | `WaveLesson` | `Wave`: animate the phase, and why it is reduced mod 2π |
| `09_edge_detect.py` | `EdgeDetectLesson` | Sobel over luma: a line drawing, or outlines added over the solid |

### 5 · `c3_05_motion_blur` — motion blur

Janim has no motion blur inside the render loop (`Scene` takes no
`motion_blur`); what it has is the blurred still, `render_frame_motion`, which
the lessons that need it declare through `PREVIEW_MOTION`.

| Lesson | Class | What it teaches |
|---|---|---|
| `01_motion_blur_basics.py` | `MotionBlurBasics` | n exposures with the state ADVANCED between them, not a smear of a picture |
| `02_shutter_angle.py` | `ShutterAngle` | `shutter` as the 180° convention, and strobing vs mush |
| `03_updater_motion.py` | `UpdaterMotion` | updaters and `always_redraw` smear too — that is the difference |
| `04_render_frame_motion.py` | `RenderFrameMotion` | check a blurred still before committing to n× the render |
| `05_physics_warning.py` | `PhysicsWarning` | measured: sub-stepping a chaotic system, 7.5e-11 at 2 s → 6.7e-2 at 20 s |
| `06_cli_and_farm.py` | `CliAndFarm` | the `--motion-blur` flag the CLI rejects, and the combination the farm refuses |

### 6 · `c3_06_capstone` — the capstone

| Lesson | Class | What it teaches |
|---|---|---|
| `01_pendulum_smooth_masked.py` | `PendulumSmoothMasked` | the field and the chaos with no word on screen; with a composition mounted, put the simulation in a scene-level mobject |

## Course 4 — The complete reference

Courses 1 to 3 choose what to teach. Course 4 is the reference course: it is
meant to cover every public name of Janim in a lesson that runs. So far it has
the shape zoo.

| Lesson | Class | What it teaches |
|---|---|---|
| `c4_01_shape_zoo/01_every_flat_shape.py` | `EveryFlatShape` | every flat constructor, in one frame |
| `c4_01_shape_zoo/02_groups_and_the_base.py` | `GroupsAndTheBase` | `VMobject`, `VGroup`, `Group`, and a path built by hand |

## Conventions used throughout

- **Manim syntax**: `class X(Scene)`, `def construct(self)`, `self.play(…)`,
  `m.animate…`; code, comments and docstrings in English, in the expanded
  format (one argument per line when a call spans several).
- **Sizes are in scene units**: the nominal frame is 8 units tall and 8·16/9 ≈
  14.22 wide, whatever the pixel resolution.
- **Reproducible arithmetic where it matters**: a lesson that evaluates `sin`,
  `cos`, `hypot`… in its own code takes them from `janim.math` (Julia's libm,
  bit for bit, for floats and for whole arrays), and float ranges from the
  same module, so its samples are the same on every run and every machine.
- **Numbers in the docstrings were measured**, not remembered; where a lesson
  claims a figure it usually prints it too.

## Where the rest of the documentation is

- `../../llms.txt` — the operational summary of the whole API, for agents.
- `../../README.md` — the overview of the project (`../../README.es.md` in Spanish).
- `../../docs/` — the compositor, 3D and the CLI.
- `../gallery/`, `../scenes/` — complete scenes written as Manim classes.
- `../demo/` — twelve short demonstrations of what only Janim does, with English comments and the Spanish originals in `*.es.py`.
