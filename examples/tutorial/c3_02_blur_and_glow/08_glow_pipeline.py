"""Course 3 · 2.8 — The neon recipe

Glow is not one effect, it is a PIPELINE, and every piece is doing something
specific:

  1. `blend="add"` on the glowing layer. Additive light is what makes two
     overlapping strokes brighter instead of one hiding the other — and it
     is the only mode where a dark background contributes nothing.
  2. `Bloom` with a LOW threshold on that layer, so the stroke's own colour
     spills. Threshold high → only the brightest core glows; low → the whole
     stroke does.
  3. a dark background. Additive blending over a light background just
     clips to white.
  4. optionally, a second copy of the geometry, thicker and dimmer,
     underneath — the cheap way to fake the tube behind the light.

The pieces are all from this chapter; what this lesson teaches is the ORDER
and why each one is there.

    python examples/tutorial/c3_02_blur_and_glow/08_glow_pipeline.py
"""

from pathlib import Path

from janim import *
from janim.core.effects_types import _noise_hash

PREVIEW_T = 2.6


def sign_parts():
    """The sign: a word and a frame around it, as stroked paths."""
    word = Text("JANIM", size=1.25)
    word.set_fill(opacity=0)                    # a tube, not a solid
    word.set_stroke("#FF3D8B", width=5.0, opacity=1.0)
    word.move_to(0.35 * UP)

    frame = RoundedRectangle(width=6.4, height=2.6, corner_radius=0.4)
    frame.set_fill(opacity=0)
    frame.set_stroke("#39D0FF", width=4.0)
    frame.move_to(0.35 * UP)
    return word, frame


class GlowPipeline(Scene):
    def construct(self):
        word, frame = sign_parts()

        # The "tube": the same geometry, thicker and dim, under the bright one.
        tube_w = word.copy()
        tube_w.set_stroke("#7A1240", width=13.0)
        tube_f = frame.copy()
        tube_f.set_stroke("#0F4A66", width=11.0)

        caption = Text('blend = "add" · Bloom(threshold = 0.2) · dark background', size=0.34, color=GREY_B)
        caption.move_to(2.5 * DOWN)

        flicker = Bloom(threshold=0.2, intensity=1.6, sigma=0.12)

        self.use_composition(
            Composition(
                Layer(tube_w, tube_f),                                   # the glass
                Layer(word, frame, blend="add", effects=[flicker]),      # the light
                Layer(caption),
                background=(0.015, 0.01, 0.03, 1),                       # dark, on purpose
            ),
        )

        # A neon sign flickers: the intensity is a field, so this is one updater.
        # Deterministic on purpose — a hash of the frame index, never random().
        clock = VGroup()

        def buzz(m, dt):
            if dt <= 0:
                return
            n = float(_noise_hash(1, 1, self.frames // 3, 7))
            flicker.intensity = 1.2 + 0.9 * (1.0 if n > 0.22 else 0.15)

        clock.add_updater(buzz)
        self.add(clock)

        self.wait(3.0)
        print("bloom intensity at the end:", round(flicker.intensity, 2))


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    GlowPipeline(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
