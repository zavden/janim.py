# Layers and effects

A `Composition` defines what is drawn. Scene roots still receive their
updaters, but drawing comes from the layers, from bottom to top.
Within a layer, objects are drawn as in the direct path; between layers,
composition and effects work in premultiplied linear light.
The three fill shaders discard the Loop–Blinn triangle of a straight edge
thinner than 2⁻⁹ window pixels: lavapipe produced a NaN texel there that
the composited path propagated through any effect. Setting
`_FILL_THIN_PX = 0` in `janim/backend/wgpu/pipelines.py` disables that
discard.

```python
from janim import *


class LayerExample(Scene):
    def construct(self):
        square = Square(fill_color=BLUE, fill_opacity=1)
        disc = Circle(fill_color=RED, fill_opacity=0.7).shift(RIGHT)
        blur = Blur(0.12)
        self.use_composition(
            Composition(
                Layer(square, effects=[blur]),
                Layer(disc, blend="screen"),
                background=(0.03, 0.04, 0.05, 1),
            ),
        )
        self.play(disc.animate.shift(LEFT))
        self.wait()
```

Blend modes are `normal`, `add`, `multiply`, `screen` and `overlay`.
Layer opacity multiplies its finished image. `Layer(composition)` nests a
composition with its own accumulators; `Layer(effects=[...])` applies its
effects to the composite below. An adjustment layer only carries effects:
mask, opacity, blend, matte, camera and window are errors.

`Mask(*mobjects, invert=False, feather=0, hard=False, luma=False)` clips
the content. `crop(*mobjects, inside=shape)` and `crop(*mobjects, minus=shape)`
build those cutouts. The mask is drawn in the parent's space, after placing
the window. Its feather is also measured in that space.
A `matte="alpha"`, `"luma"`, `"alpha_inv"` or `"luma_inv"` consumes the
next layer: it uses its content and camera, skipping its effects and mask.

`Layer(*world, camera=view, window=rectangle)` creates a view of the world
in a window. `view` is a `CameraFrame`; the rectangle is projected with the
parent's camera and its aspect ratio crops the center of the view. Its
effects are computed before scaling it down to the window, at its camera's
scale. Inner cameras override the view inherited from a precomposition.

Shared objects update once. Scene roots run first, followed by content and
masks, and finally cameras and windows that were not already in those lists.
`remove` and animation replacements also traverse nested layers. `clear`
only empties roots. `describe(scene)` shows the layer and mask tree alongside
the roots.

| Effect | Main parameters | Unit |
|---|---|---|
| `Blur(sigma, in_pixels=False)` | sigma | Scene units, or explicit pixels |
| `BoxBlur(radius)` | radius | Scene units |
| `DirectionalBlur(sigma, angle)` | sigma, angle | Scene units and radians |
| `RadialBlur(strength, center_point=(0, 0))` | strength, center_point | Fraction and scene units |
| `Dof(focus=None, aperture=0.4, max_sigma=4)` | Distance to the focal plane | Scene units |
| `Bloom(threshold=0.6, intensity=1, sigma=0.15)` | Threshold, gain, sigma | Linear light and scene units |
| `Glitch()` | intensity, seed, rate, rgb_shift, slices, block | Scene units and frames |
| `CRT()` | intensity, scanlines, scan_depth, mask, curvature, vignette, roll | Counts and fractions |
| `VHS()` | intensity, seed, rate, chroma_bleed, jitter, noise, head_switch | Scene units, frames and fractions |
| `ColorAdjust()` | brightness, contrast, saturation, hue | Factors and radians |
| `Pixelate(size=0.2)` | size | Scene units |
| `Vignette()` | amount, radius, feather | Fractions of the half-diagonal |
| `Grain()` | amount, seed, rate, levels=8 | Factors and frames |
| `ChromaticAberration(amount=0.1)` | amount | Scene units |
| `Sharpen(amount=0.6, sigma=0.05)` | amount, sigma | Factor and scene units |
| `Wave()` | amplitude, wavelength, angle, phase | Scene units and radians |
| `EdgeDetect()` | amount, color, thickness | Factor, color and pixels |

Fields are mutable and can change from an updater. `rate` counts frames.
Noise mixes the seed with the type name and the scene's frame index; it
does not consult an external clock. A `current_frame` field receives that
index automatically and requires a mutable object.

An effect with its controls at identity skips the pass, with three exceptions:
`BoxBlur(0)` uses at least a one-pixel radius, `RadialBlur(0)` runs its 32
samples, and `Bloom(intensity=0)` runs the pyramid and its saturating sum.
Gaussian and box kernels warn when the requested radius exceeds the
supported 63 pixels.

Register a custom shader with `effect_shader`. The handler is registered
by type and receives the source slot; it returns that same slot for
identity, or a scratch slot containing the result. Minimal example:

```python
from dataclasses import dataclass
from janim import apply_effect, effect_shader
from janim.backend.wgpu.uniforms import quad_params


@dataclass
class Posterize:
    levels: float = 6


effect_shader(
    "posterize",
    """
    @fragment
    fn fs_posterize(in: QuadOut) -> @location(0) vec4<f32> {
        let c = sample_a(in.uv);
        let s = floor(unpremult(c) * P.f0.x + 0.5) / P.f0.x;
        return vec4<f32>(s * c.a, c.a);
    }
    """,
)


@apply_effect.register(Posterize)
def posterize(effect, compositor, source):
    if effect.levels <= 1:
        return source
    return compositor._quad(
        "posterize",
        compositor._scratch(source),
        source,
        params=quad_params(f0=(effect.levels,)),
    )
```

Registration adds `sample_a`, `sample_b`, `P`, the noise functions and
`unpremult`/`luma`. Registering the same name again recompiles it on the
next use. Built-in names are reserved. Color effects must divide by alpha
before operating and multiply by it afterward.

For use outside `Scene`, `render_composition(comp, camera, rv=rv, cg=cg)`
returns top-down RGB. `read_layer_rgba(layer, camera, rv=rv, cg=cg)`
returns straight RGBA, with the bottom row first. The direct path's `flip_y`
differs from video for vertically asymmetric effects such as VHS; each
function maintains its own contract.
