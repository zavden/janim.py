"""Course 2 · 6.1 — Writing a layer effect (basic shaders)

ManimGL's shaders are per MOBJECT. Janim's are per LAYER: the compositor has
already rendered the layer into a texture, so an effect is one fullscreen
pass over an image — which is what an editor's effect actually is, and what
makes "blur THIS group and not that one" possible at all.

A layer effect is exactly three things:

  1. a MUTABLE object (mutable so it can be animated from an updater, and so
     the frame clock can be handed to it — lesson 6.2): a dataclass will do;
  2. a fragment shader in WGSL, registered once with `effect_shader`;
  3. ONE handler registered with `@apply_effect.register(MyEffect)`, called as
     `handler(effect, compositor, source)`, that writes a scratch slot and
     RETURNS it.

Four conventions worth copying from the built-ins:

  · THE ZERO IS AN EXACT NO-OP. Return `source` untouched when the dial is at
     identity so the pass is skipped and the layer comes out bit for bit as
     it went in.
  · SIZES IN SCENE UNITS, converted with `compositor.ppu` (pixels per scene
     unit), so the effect looks the same at 480p and at 1080p.
  · THE TEXTURE IS PREMULTIPLIED. Divide by alpha before touching colour and
     multiply back afterwards (`unpremult` is spliced in for you), or the
     effect eats the edges.
  · NEVER WRITE `source`. A frame is ONE command buffer and a pass already
     recorded may still read that slot: write `compositor._scratch(source)`
     and hand the new slot on. There is no copy back — the layer's CURRENT
     texture travels as a slot index.

The fragment is `fn fs_<entry>(in: QuadOut) -> @location(0) vec4<f32>` over
the compositor's shared quad: it reads the layer through `sample_a(in.uv)`,
its dials from `P.f0` / `P.f1` (four floats each) and `P.i0` (four ints),
which `quad_params(f0=…, f1=…, i0=…)` fills on the Python side. The engine
splices the inserts every built-in effect sees (quad_common, noise,
straight), so nothing has to be pasted into the string.

`RadialBlur` in janim/backend/wgpu/effects.py is the smallest complete
example in the library; this is the same shape.

    python examples/tutorial/c2_06_shaders/01_write_a_layer_effect.py
"""

from dataclasses import dataclass
from pathlib import Path

from janim import *
from janim.backend.wgpu.uniforms import quad_params
from janim.math import sin

# ── 1 · the struct ─────────────────────────────────────────────────────────


@dataclass
class Posterize:
    """Posterize(levels=6, tint=0.0)

    Quantise each channel to `levels` steps — the poster look. `levels ≤ 1` is an
    exact no-op. `tint` pushes the result towards a warm/cool split, to show what
    a second dial costs (nothing).
    """

    levels: float = 6.0
    tint: float = 0.0

    def __post_init__(self):
        self.levels = float(self.levels)
        self.tint = float(self.tint)


# ── 2 · the shader ─────────────────────────────────────────────────────────

POSTERIZE_WGSL = """
@fragment
fn fs_posterize(in: QuadOut) -> @location(0) vec4<f32> {
    let c = sample_a(in.uv);
    let levels = P.f0.x;
    let tint = P.f0.y;
    // PREMULTIPLIED in, premultiplied out: unpremultiply before touching the
    // colour or the quantisation eats the antialiased edges.
    var s = unpremult(c);
    s = floor(s * levels + 0.5) / levels;
    // a cheap grade: warm the highlights, cool the shadows
    let l = dot(s, vec3<f32>(0.2126, 0.7152, 0.0722));
    s = clamp(s + tint * (l - 0.5) * vec3<f32>(0.9, 0.2, -0.7), vec3<f32>(0.0), vec3<f32>(1.0));
    return vec4<f32>(s * c.a, c.a);
}
"""
effect_shader("posterize", POSTERIZE_WGSL)

# ── 3 · the handler ────────────────────────────────────────────────────────


@apply_effect.register(Posterize)
def _apply_posterize(effect, compositor, source):
    if effect.levels <= 1:
        return source                                    # the zero is an exact no-op
    return compositor._quad(
        "posterize",
        compositor._scratch(source),
        source,
        params=quad_params(f0=(effect.levels, effect.tint)),
    )


PREVIEW_T = 2.4


class WriteALayerEffect(Scene):
    def construct(self):
        title = Text("a layer effect is a struct, a shader and one method", size=0.42, color=GREY_A)
        title.to_edge(UP, buff=0.3)

        def art(x):
            """The same content, built twice so each side owns its copy."""
            g = VGroup()
            for k in range(7):
                c = Circle(radius=0.5 + 0.32 * k)
                c.set_stroke(opacity=0)
                c.set_fill(color_gradient(["#0B0E14", "#2C5F8A", "#FFD25E"], 7)[k], 1.0)
                g.add(c)
            # smallest on top, so the rings read as rings
            for k, c in enumerate(reversed(g.submobjects), 1):
                c.set_z_index(k)
            g.move_to((x, -0.3, 0))
            return g

        plain = art(-3.4)
        posted = art(3.4)
        poster = Posterize(3, tint=0.0)

        left = Text("as rendered", size=0.34, color=GREY_B)
        right = Text("Posterize(3)", size=0.34, color=GREY_B)
        left.move_to((-3.4, -3.1, 0))
        right.move_to((3.4, -3.1, 0))

        self.use_composition(
            Composition(
                Layer(plain),
                Layer(posted, effects=[poster]),
                Layer(title, left, right),
                background=(0.02, 0.03, 0.05, 1),
            ),
        )

        # The object is mutable, so the effect is animatable from an updater —
        # no new mechanism, just a field changing over time.
        clock = VGroup()

        def dial(m, dt):
            if dt <= 0:
                return
            poster.levels = 2 + 6 * (0.5 + 0.5 * sin(1.2 * self.t))
            poster.tint = 0.6 * (0.5 + 0.5 * sin(0.7 * self.t))

        clock.add_updater(dial)
        self.add(clock)

        self.wait(4.0)
        print("levels at the end:", round(poster.levels, 2))


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    WriteALayerEffect(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
