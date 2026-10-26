---
name: janim-compositor
description: Use Janim.py's layer compositor — `Composition`, `Layer` (blend, opacity, effects, mask, matte, a second `camera=` with a `window=`), `Mask` and `crop`, precomps and adjustment layers, the seventeen effects (`Blur`, `Bloom`, `Dof`, `Glitch`, `CRT`, `VHS`, `Vignette`…) and the recipes for glow, a magnifier, a spotlight or text as a mask. Use whenever a Janim.py scene wants blur, glow, bloom, depth of field, clipping, picture-in-picture, a zoomed inset or any post-processing, and when a composited scene shows nothing or shows the wrong thing.
---

# The compositor (Janim.py)

Manim draws every mobject into one picture. Janim's `Composition` draws
LAYERS, bottom to top, each rendered to its own texture, blended in linear
premultiplied light, with effects that are fullscreen passes over that
texture. That is why "blur THIS group and not that one" exists here and not in
Manim.

## 1 · The model, and the one fact that bites

```python
class Glow(Scene):
    def construct(self):
        tube = Circle(radius=1.5).set_stroke("#58C4DD", width=6).set_fill(opacity=0)
        label = Text("neon", size=0.5).to_edge(UP)
        self.use_composition(
            Composition(
                Layer(tube, blend="add", effects=[Bloom(threshold=0.4, intensity=1.4, sigma=0.25)]),
                Layer(label),
                background=(0.02, 0.03, 0.05, 1),
            ),
        )
        self.play(Rotating(tube, angle=TAU, run_time=4))
```

A mounted composition decides what is DRAWN. The scene's roots (`self.add`,
`self.play`) still receive their updaters, but the picture comes from the
layers only: **a mobject that is in no `Layer` is updated and never drawn**
(measured). `play` on a mobject that lives in a layer works as usual;
`remove` and the replacement animations walk nested layers; `describe(self)`
prints the layer and mask tree beside the roots.

`Scene(composition=…)` mounts one at construction; `use_composition` inside
`construct` is the same thing. The default `background` is transparent black
`(0, 0, 0, 0)`: pass `(r, g, b, 1)` for an opaque one.

## 2 · Layers

`Layer(*mobjects, blend="normal", opacity=1.0, effects=[…], mask=None,
matte=None, camera=None, window=None)`

- Blends: `"normal"`, `"add"`, `"multiply"`, `"screen"`, `"overlay"`. Layer
  opacity multiplies the finished image, unlike a mobject's.
- `Layer(composition)` is a PRECOMP: blur the RESULT of a blend, or give a
  group its own accumulators.
- `Layer(effects=[…])` with no content is an ADJUSTMENT layer that grades
  everything below it. It carries effects ONLY: `mask=`, `opacity=`, `blend=`,
  `matte=`, `camera=`, `window=` on it are `ValueError`s
  ("an adjustment layer cannot carry mask=…").
- `matte="alpha" | "luma" | "alpha_inv" | "luma_inv"` consumes the NEXT layer
  as coverage (its content and camera, skipping its effects and mask).
- Order of work per frame: scene roots update, then layer contents and masks,
  then cameras and windows not already updated. A shared mobject updates once.

## 3 · Masks

```python
Layer(world, mask=Mask(Star(5, fill_opacity=1.0), feather=0.06))       # coverage per pixel
crop(world, inside=Circle(radius=2.0, fill_opacity=1.0))               # keeps a window → a Layer
crop(world, minus=Square(side_length=1.0), feather=0.05, hard=True)    # punches a hole
Mask(gradient_rect, luma=True)
Mask(shape, invert=True)
clip_layers(svg)                 # an SVG's own clipPaths, as layers with masks
```

- The masking mobjects are NEVER drawn, but they still update: a mask can
  follow a dot (`spotlight.add_updater(lambda m: m.move_to(dot))`). Park it
  off screen to start.
- `crop` wants EXACTLY one of `inside`/`minus`
  (`ValueError: crop requires exactly one of minus or inside`).
- `feather` blurs the MASK, not the layer; `hard` thresholds the feathered
  stencil; `luma=True` reads brightness as coverage (gradients, wipes). Masks
  are drawn in the parent's space, after the window is placed, and their
  feather is measured there.

## 4 · A second camera: the magnifier, the inset, the split screen

```python
zoom = CameraFrame().set_frame_height(1.2)          # what to look at: animate it like self.frame
display = Rectangle(width=4.5, height=4.5 * 9 / 16).to_corner(UR, buff=0.4)
Layer(*world, camera=zoom, window=display)         # a REAL second render, placed in display's projected box
```

The window is projected with the parent's camera and its aspect centre-crops
the view; the layer's effects run at the inner camera's scale. This is what
CE's `ZoomedScene` was. A `fix_in_frame()`-ed `PlaneXY` can serve as a
screen. Lesson: `examples/tutorial/c2_03_camera/02_zoomed_camera.py`.

## 5 · The seventeen effects

Sizes are SCENE UNITS (a 480p preview tells the truth about the 1080p film),
`rate` counts FRAMES, every field is mutable so an updater can animate it,
and a dial at identity skips the pass (the layer comes out bit for bit) —
except `BoxBlur(0)` (one pixel), `RadialBlur(0)` (its 32 samples) and
`Bloom(intensity=0)` (its pyramid).

| Effects | Dials |
|---|---|
| `Blur(sigma, in_pixels=False)`, `BoxBlur(radius)`, `DirectionalBlur(sigma, angle)`, `RadialBlur(strength, center_point=(0, 0))` | the blurs |
| `Dof(focus=None, aperture=0.4, max_sigma=4.0)`, `Bloom(threshold=0.6, intensity=1.0, sigma=0.15)` | optics: `focus` is the distance to the focal plane, resolved against the layer's camera each frame |
| `Glitch(intensity, seed, rate, rgb_shift, slices, block)`, `CRT(intensity, scanlines, scan_depth, mask, curvature, vignette, roll)`, `VHS(intensity, seed, rate, chroma_bleed, jitter, noise, head_switch)` | the broken-screen family |
| `ColorAdjust(brightness, contrast, saturation, hue)`, `Pixelate(size)`, `Vignette(amount, radius, feather)`, `Grain(amount, seed, rate, levels)`, `ChromaticAberration(amount)`, `Sharpen(amount, sigma)`, `Wave(amplitude, wavelength, angle, phase)`, `EdgeDetect(amount, color, thickness)` | the editor family |

Noise mixes the seed with the effect's TYPE NAME and the SCENE's frame index —
never a clock — so `Glitch(seed=1)` and `Grain(seed=1)` on one layer are
uncorrelated, and a video rendered in segments across processes has no seam.

## 6 · Recipes that work

- **Neon / glow**: `blend="add"` + `Bloom` + a dark `background` + a DIM tube
  (the bloom supplies the brightness). Sparse points want `GlowDots` or a
  `glow_factor`; dense overlapping dots saturate — put them on a `Bloom`
  layer instead.
- **Dream transition**: an updater raises `blur.sigma`, swap the content,
  lower it. `Blur(0.12)` is already soft at 480p.
- **Rack focus**: two layers at different depths, a `Dof(focus=…)` each,
  animate `focus`.
- **Spotlight**: `Mask(Circle(…, fill_opacity=1), feather=0.3)` with an
  updater on the circle.
- **Text as a mask**: `Mask(Text("WORLD", size=2))` shows the world through
  the letters; `invert=True` punches them out.
- **Picture in picture / split screen**: §4, one layer per view with its own
  `camera=`.
- **A grade over everything**: a final
  `Layer(effects=[Vignette(amount=0.4), Grain(amount=0.1)])`.

## 7 · Traps, each paid for

- **The simulation goes in a scene-level mobject.** Roots update BEFORE layer
  contents, so an integrator in a mobject that lives only inside a layer runs
  after everything that reads it. `self.add(clock)` with the updater on
  `clock`, and the layers read its state.
- **z-index is for ORDER, a layer is for TREATMENT.** Do not make a layer per
  mobject to sort them: `set_z_index` inside one layer is cheaper and does the
  same.
- **Sub-pixel dials**: pixels per scene unit are `width / 14.22` (45 at
  640×360, 60 at 854×480). `Pixelate(0.01)` or `ChromaticAberration(0.005)`
  is invisible at every preview size.
- `describe(self)` first, when a layer "does nothing": it lists
  `layer k · blend=… · effects` and the mobjects each one holds.

## 8 · Outside a scene, and your own effect

`render_composition(comp, camera, rv=rv, cg=cg)` returns top-down RGB;
`read_layer_rgba(layer, camera, rv=rv, cg=cg)` straight RGBA. Writing a NEW
effect (a dataclass, a WGSL fragment, one handler) is `janim-layer-effect`.
The manual is `docs/compositor.md`; the lessons are
`examples/tutorial/c3_01_layers/` through `examples/tutorial/c3_04_glitch/`
(33 of them) and the twelve `examples/demo/` scenes.
