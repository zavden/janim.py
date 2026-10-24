"""Demo 06 · THE BROADCAST — glitch, cathode-ray tube and VHS tape over a
formula that keeps morphing underneath

Editor effects (`Glitch`, `CRT`, `VHS`, `ColorAdjust`) go in ONE layer's
`effects` list, and each is a mutable dataclass: animating them means
writing their fields from an updater. Three properties make this usable
rather than a trick:

  · each dial's ZERO is an EXACT no-op: the pass is skipped, and the image
    returns clean, byte for byte, when the interference ends;
  · randomness is a hash of (pixel, frame, seed), never `random()`:
    the same glitch appears on the same frame in every render, and you
    can rewind to it;
  · `CRT.roll` has no internal clock: the television loses sync because
    YOU write its offset every frame.

Manim has no post-processing of any kind — not even blur.

The noise hash is `janim.core.effects_types._noise_hash`. The class is
named `BroadcastScene`, not `Broadcast`, because `Broadcast` is already
a janim animation (ManimGL's), imported by `from janim import *`:
the name would shadow it.

    bin/janim render examples/demo/06_broadcast.py -ql
"""

from pathlib import Path

from janim import *
from janim.math import sin
from janim.core.effects_types import _noise_hash


def ramp(t, t0, t1):
    """0 before t0, 1 after t1, and a straight line in between."""
    return min(max((t - t0) / (t1 - t0), 0.0), 1.0)


class BroadcastScene(Scene):
    def construct(self):
        # ── the monitor: color bars, the formula and channel labels ─
        bars = VGroup()
        for k, c in enumerate(("#FFFFFF", "#FFFF00", "#00FFFF", "#00FF00", "#FF00FF", "#FF0000", "#0000FF")):
            r = Rectangle(width=1.6, height=0.8)
            r.set_fill(c, opacity=1.0)
            r.set_stroke(opacity=0)
            r.move_to((-4.8 + 1.6 * k, -2.95, 0))
            bars.add(r)

        def make_formula(s, color):
            t = Tex(s, color=color, size=1.25)
            if t.get_width() > 10.5:
                t.set_width(10.5)
            t.move_to(0.35 * UP)
            return t

        formula = make_formula(r"\nabla \times B = \mu_0 J + \mu_0 \varepsilon_0 \, \partial_t E", WHITE)

        channel = Text("JANIM · CHANNEL 7", size=0.36, color="#7FDD58")
        channel.to_corner(UL, buff=0.5)

        def make_status(s, color):
            t = Text(s, size=0.36, color=color)
            t.to_corner(UR, buff=0.5)
            return t

        status = make_status("SIGNAL", GREY_B)

        # ── the effects, all off: zero = skipped pass ──────────────
        glitch = Glitch(
            intensity=0.0,
            seed=7,
            rate=2,
            slices=18,
        )
        tube = CRT(
            intensity=0.0,
            scanlines=220,
            scan_depth=0.4,
            curvature=0.12,
            vignette=0.4,
        )
        tape = VHS(
            intensity=0.0,
            seed=3,
            rate=2,
        )
        grade = ColorAdjust()

        self.use_composition(
            Composition(
                Layer(bars, formula, channel, status, effects=[glitch, tube, tape, grade]),
                background=(0.02, 0.02, 0.03, 1),
            ),
        )

        # ── the interference script, as a function of self.t ────────────
        def script(m, dt):
            if not dt > 0:
                return
            t = self.t

            # 1 · bursts (3–7 s): a spike, not a ramp, then back to exact
            # zero. Irregular but deterministic: the engine's own hash
            # applied to the frame.
            if 3.0 <= t < 7.0:
                window = self.frames // 6
                fire = float(_noise_hash(1, 1, window, 4)) > 0.5
                phase = (self.frames % 6) / 6
                glitch.intensity = 0.95 * ((1 - phase) * (1 - phase)) if fire else 0.0
            else:
                glitch.intensity = 0.0

            # 2 · the tube (7–12.5 s): turns on in half a second, loses sync
            # between 8 and 11 s, and recovers on its own.
            tube.intensity = ramp(t, 7.0, 7.5) * (1 - ramp(t, 12.5, 13.0))
            if 8.0 <= t < 11.0:
                speed = 0.2 + 0.9 * max(0.0, sin(TAU * (t - 8.0) / 3.0))
                tube.roll = (tube.roll + speed * dt) % 1.0
            elif tube.roll > 0.0:
                # back to the frame: along the shortest path, and 1.0 ≡ 0.0
                if tube.roll < 0.5:
                    tube.roll = max(tube.roll - 1.2 * dt, 0.0)
                else:
                    tube.roll = min(tube.roll + 1.2 * dt, 1.0)
                if tube.roll >= 1.0:
                    tube.roll = 0.0

            # 3 · the tape (13–17 s), with increased color saturation and contrast
            tape.intensity = 0.8 * ramp(t, 13.0, 13.4) * (1 - ramp(t, 17.0, 17.6))
            grade.saturation = 1.0 + 0.35 * tape.intensity / 0.8
            grade.contrast = 1.0 + 0.15 * tape.intensity / 0.8

        clock = VGroup()
        clock.add_updater(script)
        self.add(clock)

        # ── the formula continues underneath everything ────────────────────────
        self.play(Write(formula), run_time=2.0)
        self.wait(1.2)
        self.play(Transform(status, make_status("INTERFERENCE", "#FF3D8B")), run_time=0.4)
        self.wait(1.4)
        self.play(Transform(formula, make_formula(r"\nabla \cdot B = 0", "#58C4DD")), run_time=1.2)
        self.wait(1.0)
        self.play(Transform(status, make_status("NO SYNC", "#FFD25E")), run_time=0.4)
        self.wait(2.2)
        self.play(
            Transform(formula, make_formula(r"\nabla \times E = - \partial_t B", "#FFD25E")),
            run_time=1.2,
        )
        self.wait(2.0)
        self.play(Transform(status, make_status("TAPE", "#F0A045")), run_time=0.4)
        self.wait(1.2)
        self.play(
            Transform(formula, make_formula(r"\nabla \cdot E = \rho / \varepsilon_0", "#7FDD58")),
            run_time=1.2,
        )
        self.wait(2.0)
        self.play(Transform(status, make_status("SIGNAL", GREY_B)), run_time=0.4)
        self.wait(1.6)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    BroadcastScene(
        output=str(here.with_suffix(".mp4")),
        fps=30,
        resolution=(1280, 720),
        encoder_threads=1,      # high-frequency noise: byte-reproducible mp4
    ).render()
