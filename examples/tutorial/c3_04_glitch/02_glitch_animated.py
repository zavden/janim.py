"""Course 3 · 4.2 — A glitch that comes and goes

`intensity` is a field of a mutable dataclass, so the whole technique is one
updater. What makes it read as an ACCIDENT rather than as an animation is
the SHAPE of that function of time:

  · a glitch is short and violent — a spike, not a swell;
  · it repeats irregularly;
  · and it must return to EXACTLY zero, because zero is an exact no-op and
    the picture has to come back clean.

Irregular but deterministic: use the library's own noise (`_noise_hash`, in
`janim.core.effects_types`) keyed on the frame index, never `random()`.
Determinism is what lets you scrub back to a glitch and see the same one.

    python examples/tutorial/c3_04_glitch/02_glitch_animated.py
"""

from pathlib import Path

from janim import *
from janim.core.effects_types import _noise_hash

PREVIEW_T = 2.4


class GlitchAnimated(Scene):
    def construct(self):
        title = Text(
            "a spike, not a swell — and it returns to exact zero",
            size=0.4,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.3)

        photo = VGroup()
        for k in range(7):
            rect = Rectangle(width=1.5, height=3.4 - 0.3 * k)
            rect.set_fill(color_gradient(["#39D0FF", "#FF3D8B"], 7)[k], 1.0)
            rect.set_stroke(opacity=0)
            rect.move_to((-4.6 + 1.55 * k, 0.1, 0))
            photo.add(rect)
        caption = Text("BROADCAST", size=0.8, color=WHITE)
        caption.move_to(0.1 * UP)

        glitch = Glitch(
            intensity=0.0,
            seed=11,
            rate=2,
            slices=22,
        )
        meter = DecimalNumber(
            0.0,
            num_decimal_places=2,
            size=0.5,
            color="#FF3D8B",
        )
        meter.move_to((5.2, -2.7, 0))

        self.use_composition(
            Composition(
                Layer(photo, caption, effects=[glitch]),
                Layer(title, meter),
                background=(0.02, 0.03, 0.05, 1.0),
            ),
        )

        # The driver. `burst` is 1 for a few frames at irregular moments,
        # decided by a hash of the frame index — deterministic, so scrubbing
        # shows the same glitches.
        def drive(m, dt):
            if not dt > 0:
                return
            window = self.frames // 7                          # a decision every 7 frames
            fire = float(_noise_hash(1, 1, window, 4)) > 0.72
            phase = (self.frames % 7) / 7
            glitch.intensity = 0.9 * ((1 - phase) * (1 - phase)) if fire else 0.0   # spike, then exact 0
            meter.set_value(glitch.intensity)

        clock = VGroup()
        clock.add_updater(drive)
        self.add(clock, meter)

        self.wait(4.0)
        print(f"intensity at the end: {glitch.intensity} (0.0 exactly means the pass was skipped)")


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    GlitchAnimated(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
