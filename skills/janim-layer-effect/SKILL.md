---
name: janim-layer-effect
description: Write a new layer effect for Janim.py's compositor — a mutable dataclass, a WGSL fragment registered with `effect_shader`, one `@apply_effect.register` handler — with the premultiplied-alpha, scene-units, exact-no-op and deterministic-noise contracts (`current_frame`, `_noise_seed`, `janim_noise_px`). Use when adding a compositor effect, writing or editing WGSL for Janim.py, or touching `janim/backend/wgpu/effects.py`, `compositor.py` or the `shaders/` folder.
---

# Writing a layer effect (Janim.py)

ManimGL's shaders are per MOBJECT. Janim's are per LAYER: the compositor has
already rendered the layer into a texture, so an effect is one fullscreen
pass over an image — an editor's effect. `RadialBlur` in
`janim/backend/wgpu/effects.py` is the smallest complete built-in; the
annotated walkthroughs are `examples/tutorial/c2_06_shaders/01_write_a_layer_effect.py`
and `02_noise_and_determinism.py`, and both run.

## 1 · Exactly three things

```python
from dataclasses import dataclass, field

from janim import *
from janim.backend.wgpu.uniforms import quad_params


@dataclass                      # 1 · a MUTABLE object: animatable from an updater, tickable by the frame clock
class Posterize:
    levels: float = 6.0
    tint: float = 0.0


effect_shader(                  # 2 · a WGSL fragment over the compositor's shared quad, registered ONCE
    "posterize",
    """
    @fragment
    fn fs_posterize(in: QuadOut) -> @location(0) vec4<f32> {
        let c = sample_a(in.uv);
        var s = unpremult(c);                              // UNPREMULTIPLY before touching colour
        s = floor(s * P.f0.x + 0.5) / P.f0.x;
        return vec4<f32>(s * c.a, c.a);                    // premultiply back
    }
    """,
)


@apply_effect.register(Posterize)   # 3 · ONE handler: write a scratch slot, return it
def _apply_posterize(effect, compositor, source):
    if effect.levels <= 1:
        return source                                      # the zero is an EXACT no-op
    return compositor._quad(
        "posterize",
        compositor._scratch(source),
        source,
        params=quad_params(f0=(effect.levels, effect.tint)),
    )
```

Use it like a built-in: `Layer(content, effects=[Posterize(3)])`.

The fragment is `fn fs_<entry>(in: QuadOut) -> @location(0) vec4<f32>`. It
reads the layer through `sample_a(in.uv)` (a second texture through
`sample_b`), the pixel through `in.position.xy`, and its dials from
`P.f0`/`P.f1` (four floats each), `P.i0` (four ints) and `P.w` (64 floats as
sixteen `vec4`), which `quad_params(f0=…, f1=…, i0=…, w=…)` fills on the
Python side. The registry splices
`janim/backend/wgpu/shaders/inserts/quad_common.wgsl` (the bind group,
`QuadOut`, `sample_a`/`sample_b`), `noise.wgsl` and `straight.wgsl`
(`unpremult`, `luma`) in front of your source, so nothing is pasted by hand.
Registering the same entry again recompiles it on the next use; a built-in
entry name is refused with a `ValueError`.

## 2 · The four conventions, all load-bearing

- **The zero is an EXACT no-op.** Return `source` at identity so the pass is
  skipped and the layer comes out bit for bit. Every built-in obeys this and
  users rely on it (the three documented exceptions are `BoxBlur(0)`,
  `RadialBlur(0)` and `Bloom(intensity=0)`).
- **The texture is PREMULTIPLIED.** Divide by alpha before touching colour and
  multiply back (`unpremult` is spliced in), or the effect eats the
  antialiased edges. And STAY INSIDE THE LAYER: the pass covers the whole
  frame, including where the layer is empty (α = 0); anything you add there
  paints over every layer below. Multiply additions by `c.a`.
- **Geometric sizes are in SCENE UNITS**, converted with `compositor.ppu`
  (pixels per scene unit = width / 14.22), so a 480p preview tells the truth
  about the 1080p film.
- **Never write `source`.** A frame is ONE command buffer and a pass already
  recorded may still read that slot: write `compositor._scratch(source)` and
  return the slot you wrote. The layer's current texture travels as a slot
  index; there is no copy back.

And one with its own units: **`rate` counts FRAMES**, not seconds.

## 3 · Randomness, and why `random()` is forbidden

Same code → same frames is what scrubbing, `render_frame`'s agreement with
the video, and the render farm (segments across processes) are built on. The
contract instead:

```python
@dataclass(kw_only=True)
class Sparkle:
    amount: float = 0.6
    seed: int = 1
    rate: int = 4
    current_frame: int = field(default=0, init=False)      # THE DECLARATION: tick_effects fills it in
```

```wgsl
let held = janim_frame_step(P.i0.x, P.i0.z);                    // hold the pattern for `rate` frames
let n = janim_noise_px(in.position.xy, held, P.i0.y);           // hash(PIXEL, frame, seed) in [0, 1)
```

with `i0=(effect.current_frame, _noise_seed(effect, effect.seed), effect.rate)`
in the handler (`from janim.core.effects_types import _noise_seed`).

- Declaring `current_frame` is what makes the compositor's `tick_effects`
  fill it in before compositing; an effect without the field is not touched,
  and a frozen dataclass raises
  `TypeError: … declares current_frame but is not mutable`.
- The index is the SCENE's frame counter, so a video rendered in segments has
  no seam, and `render_frame(Demo, t)` agrees with the video it inspects.
- `_noise_seed(effect, seed)` mixes the seed with the effect's TYPE NAME:
  `Sparkle(seed=1)` and `Grain(seed=1)` on the same layer draw uncorrelated
  patterns. It is an `i32`, negative half the time: the shader `bitcast`s it
  (never `u32()`), and `seed_plus(seed, k)` derives a second stream.
- Index noise by PIXEL (`in.position.xy`), never by uv, so it does not
  stretch with the aspect ratio. Quantise with `janim_noise_steps` when the
  noise multiplies a colour: a continuous factor leaves pixels on an 8-bit
  rounding edge that flip between runs.
- The hash is Wellons' lowbias32 with 24 significant bits: the CPU twin
  `_noise_hash(x, y, frame, seed)` in `janim/core/effects_types.py` returns
  THE SAME float as the GPU, so a test can check a shader's numbers without a
  GPU in the loop.

## 4 · The trap no test catches

**Render your geometric default before you write it down.** `rgb_shift =
0.01` is 0.6 px at 854×480; `block = 0.004` is a quarter of a pixel. A
sub-pixel effect satisfies every closed-form check and fails the only
question that matters: can you see it? Render one frame at `-ql` AND at
1080p and look at both (`janim-verify`).

## 5 · If the bug looks like the compositor's

Measure before touching shared code. Adding a shader must leave every
existing frame byte-identical: run the frame harness of `janim-tests` before
and after, and if a hash of an existing scene moves, the design is wrong, not
the hash. Two measured subtleties are already paid for and explained in their
comments — `_FILL_THIN_PX` in `janim/backend/wgpu/pipelines.py` (the thin
Loop–Blinn triangle lavapipe turned into a NaN) and the row flip on the
GEOMETRY in `quad_common.wgsl` — so read them before "fixing" an edge.

## 6 · Close it like a stage

A new effect ships with its handler and shader (built-ins live in
`janim/backend/wgpu/effects.py` plus `janim/backend/wgpu/shaders/effects.wgsl`;
a user effect in its own module), its name in `janim/_exports_effects.py` if
it is public, a test (CPU side: identity returns `source`; noise through
`_noise_hash`), a mention in `docs/compositor.md` and `llms.txt`, and the
harness pass. See `janim-stage`.
