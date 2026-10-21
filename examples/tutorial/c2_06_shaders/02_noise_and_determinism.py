"""Course 2 · 6.2 — Randomness in a shader, without breaking determinism

The engine's determinism rule: same code → same frames. That is what buys scrubbing,
the frame cache, parallel segment rendering, and previews that really are
the final film. `random()` in a shader would break all four at once, and so
would a wall clock.

So an effect that needs randomness uses the shared piece:

  · `janim_noise_px(position, frame, seed)` — spliced into every effect's
    module (`shaders/inserts/noise.wgsl`): a hash of (PIXEL, frame, seed).
    Indexed by `in.position.xy`, never by uv, so it does not stretch with
    the aspect ratio.
  · a field `current_frame`. THAT FIELD IS THE DECLARATION — the
    compositor's `tick_effects` fills it in before compositing, and an effect
    without it is not touched. The index is the SCENE's frame counter, so a
    video rendered in segments across processes has no seam.
  · `_noise_seed(effect, effect.seed)` — the user's seed mixed with the
    effect's TYPE NAME. That is why a `Sparkle(seed=1)` and a `Grain(seed=1)`
    on the same layer do not draw the same pattern, without either of them
    having to think about it. It travels to the shader in `P.i0` as an
    `i32`, negative half the time: the shader `bitcast`s it, never `u32()`s
    it, and `seed_plus(seed, k)` is how to derive a second stream.

The hash is Wellons' lowbias32, and its output has 24 significant bits —
exactly what a Float32 holds without rounding. So the CPU and the GPU do not
agree "to some tolerance": they return THE SAME Float32, which holds
on the GPU pixel by pixel.

    python examples/tutorial/c2_06_shaders/02_noise_and_determinism.py
"""

from dataclasses import dataclass, field
from pathlib import Path

from janim import *
from janim.backend.wgpu.uniforms import quad_params
from janim.core.effects_types import _noise_hash, _noise_seed


@dataclass(kw_only=True)
class Sparkle:
    """Sparkle(amount=0.6, density=0.002, seed=1, rate=4)

    Bright specks at random pixels, re-rolled every `rate` frames. `amount = 0`
    is an exact no-op.
    """

    amount: float = 0.6
    density: float = 0.002
    seed: int = 1
    rate: int = 4
    current_frame: int = field(default=0, init=False)      # ← the declaration: tick_effects fills this in


SPARKLE_WGSL = """
@fragment
fn fs_sparkle(in: QuadOut) -> @location(0) vec4<f32> {
    let c = sample_a(in.uv);
    let frame = P.i0.x;
    let seed = P.i0.y;
    let rate = P.i0.z;
    let amount = P.f0.x;
    let density = P.f0.y;
    // the pattern is held for `rate` frames: dividing the frame index is the
    // whole mechanism, and it costs nothing
    let held = janim_frame_step(frame, rate);
    let n = janim_noise_px(in.position.xy, held, seed);
    let hit = step(1.0 - density, n);
    // STAY INSIDE THE LAYER. The pass covers the whole frame, including the
    // parts where this layer is empty (alpha 0) — adding a speck there paints
    // over everything below it. Multiplying by c.a keeps the effect where the
    // layer actually is, and leaves the alpha channel alone.
    return vec4<f32>(min(c.rgb + hit * amount * c.a, vec3<f32>(1.0)), c.a);
}
"""
effect_shader("sparkle", SPARKLE_WGSL)


@apply_effect.register(Sparkle)
def _apply_sparkle(effect, compositor, source):
    if effect.amount <= 0:
        return source
    return compositor._quad(
        "sparkle",
        compositor._scratch(source),
        source,
        params=quad_params(
            i0=(effect.current_frame, _noise_seed(effect, effect.seed), effect.rate),
            f0=(effect.amount, effect.density),
        ),
    )


PREVIEW_T = 1.5


class NoiseAndDeterminism(Scene):
    def construct(self):
        title = Text("deterministic randomness: hash(pixel, frame, seed)", size=0.42, color=GREY_A)
        title.to_edge(UP, buff=0.3)

        def panel(x, label):
            """A dark panel to sparkle over."""
            p = RoundedRectangle(width=5.2, height=3.4, corner_radius=0.2)
            p.set_fill("#101A26", 1.0)
            p.set_stroke("#25405C", width=2.0)
            p.move_to((x, -0.2, 0))
            t = Text(label, size=0.34, color=GREY_B)
            t.move_to((x, -2.4, 0))
            return p, t

        left, lab_l = panel(-3.1, "Sparkle(seed = 1)")
        right, lab_r = panel(3.1, "Sparkle(seed = 2)")

        self.use_composition(
            Composition(
                Layer(left, effects=[Sparkle(seed=1, density=0.004, rate=3)]),
                Layer(right, effects=[Sparkle(seed=2, density=0.004, rate=3)]),
                Layer(title, lab_l, lab_r),
                background=(0.02, 0.03, 0.05, 1),
            ),
        )

        self.wait(2.5)

        # The CPU version of the shader's hash. Same numbers, exactly — which is what
        # lets a test check a shader without a GPU in the loop.
        vals = [_noise_hash(px, 7, 3, 1) for px in range(1, 5)]
        print("janim_noise(px, 7, frame 3, seed 1) =", vals)
        print("…and the same call again:", [_noise_hash(px, 7, 3, 1) for px in range(1, 5)])
        print(
            "seed domains differ: Sparkle →",
            _noise_seed(Sparkle(), 1),
            "· Grain →",
            _noise_seed(Grain(), 1),
        )


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    NoiseAndDeterminism(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
