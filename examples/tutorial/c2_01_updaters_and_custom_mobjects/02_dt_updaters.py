"""Course 2 · 1.2 — dt updaters

    m.add_updater(lambda m, dt: …)   time-based: dt is the frame interval
    m.add_updater(lambda m: …)       state-based: no clock at all

WHICH ONE YOU GET IS DECIDED BY ARITY. The engine asks whether the function
takes a second argument — the same question ManimGL asks `inspect`.

Four things that bite, in the order they bite:

  1. REGISTRATION CALLS THE UPDATER ONCE WITH dt = 0. So anything that
     integrates must start with `if dt > 0`, or the first call advances a
     solver by nothing and, worse, `TracedPath` would record a sample before
     the scene has started.
  2. dt IS THE FRAME INTERVAL, not wall-clock time. At 30 fps it is exactly
     1/30 in production. That is what makes an updater deterministic.
  3. A mobject whose POINTS are built inside an updater must be born with
     its final style: new points re-stamp the factory style, so styling it
     afterwards is undone on the next frame.
  4. FREEZE an updater before fading its mobject out (a flag the closure
     reads is enough). Otherwise the updater keeps re-stamping the default
     style and the fade has no visible effect.

`suspend_updating` / `resume_updating` do the same job for a whole subtree.

    python examples/tutorial/c2_01_updaters_and_custom_mobjects/02_dt_updaters.py
"""

from pathlib import Path

import numpy as np

from janim import *

PREVIEW_T = 2.5


class DtUpdaters(Scene):
    def construct(self):
        title = Text(
            "dt is the frame interval, not the wall clock",
            size=0.44,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.35)
        self.add(title)

        # A hand-rolled integrator: position += velocity·dt, with a wall bounce.
        ball = Dot((-5.0, 1.2, 0), radius=0.22)
        ball.set_fill(color="#58C4DD")
        vel = np.array((3.4, 0.0, 0), dtype=np.float32)
        live = True                              # trap 4: the freeze switch

        def bounce(m, dt):
            nonlocal vel
            if not (live and dt > 0):            # trap 1: the dt = 0 registration call
                return
            p = m.get_center() + np.float32(dt) * vel
            if abs(p[0]) > 5.0:
                vel = np.array((-vel[0], vel[1], 0), dtype=np.float32)
                p = m.get_center() + np.float32(dt) * vel
            m.move_to(p)

        ball.add_updater(bounce)

        # Trap 3, made visible: this mobject's POINTS are rebuilt every frame, so
        # it is born with its final style and never restyled afterwards.
        ruler = VMobject()
        ruler.set_stroke(color="#FFD25E", width=3.0)

        def measure(m, dt):
            m.set_points_as_corners(
                [
                    (-5.6, -1.4, 0),
                    (ball.get_center()[0], -1.4, 0),
                ],
            )

        ruler.add_updater(measure)

        # A clock that counts frames, to show dt is exactly 1/fps in production.
        frames = 0
        seconds = DecimalNumber(
            0.0,
            num_decimal_places=2,
            size=0.6,
            color=GREY_A,
        )
        seconds.move_to((4.6, -2.4, 0))

        def count(m, dt):
            nonlocal frames
            if not dt > 0:
                return
            frames += 1

        seconds.add_updater(count)
        seconds.add_updater(lambda d: d.set_value(frames / 30))

        self.add(ball, ruler, seconds)
        self.wait(3.0)

        # Trap 4: freeze first, THEN fade. Comment out the `live = False` and
        # the ball goes on moving as it fades, which is rarely what you meant.
        live = False
        self.play(FadeOut(ball), run_time=0.8)
        print(
            "frames counted by the updater: ",
            frames,
            " · scene frames: ",
            self.frames,
            sep="",
        )


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    DtUpdaters(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
