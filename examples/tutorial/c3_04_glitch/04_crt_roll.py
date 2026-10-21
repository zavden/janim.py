"""Course 3 · 4.4 — A television losing sync

`CRT`'s `roll` is a vertical offset with a dark sync bar at the seam.
Animate it and the picture rolls — the thing an old set does when the
vertical hold slips.

Note what is NOT there: `CRT` declares no `current_frame` field, so the
frame clock never touches it. It has no internal notion of time at all —
the motion comes entirely from you writing to `roll`. That is a good
illustration of the contract: the frame clock fills in only what asks for
it, and an effect that does not ask stays a pure function of its fields.

The consequence worth having: a rolling television is still deterministic
and still scrub-able, because `roll` is a function of `self.t`, which
advances by exactly 1/fps.

    python examples/tutorial/c3_04_glitch/04_crt_roll.py
"""

import math
from pathlib import Path

from janim import *

PREVIEW_T = 2.6


class CrtRoll(Scene):
    def construct(self):
        bars = VGroup()
        for k, c in enumerate(
            ("#FFFFFF", "#FFFF00", "#00FFFF", "#00FF00", "#FF00FF", "#FF0000", "#0000FF"),
            start=1,
        ):
            rect = Rectangle(width=1.3, height=4.4)
            rect.set_fill(c, 1.0)
            rect.set_stroke(opacity=0)
            rect.move_to((-3.9 + 1.3 * (k - 1), 0.3, 0))
            bars.add(rect)
        label = Text("VERTICAL HOLD", size=0.42, color=BLACK)
        label.move_to((0, -1.6, 0))
        plate = Rectangle(width=4.4, height=0.7)
        plate.set_fill("#DDDDDD", 1.0)
        plate.set_stroke(opacity=0)
        plate.move_to((0, -1.6, 0))

        tube = CRT(
            scanlines=200,
            scan_depth=0.4,
            curvature=0.2,
            roll=0.0,
        )

        self.use_composition(
            Composition(
                Layer(bars, plate, label, effects=[tube]),
                background=(0.02, 0.02, 0.03, 1.0),
            ),
        )

        # Losing sync: the roll accelerates, then settles. `%` keeps the
        # number small so a long scene does not lose precision.
        def slip(m, dt):
            if not dt > 0:
                return
            speed = 0.15 + 0.5 * max(0.0, math.sin(0.7 * self.t))
            tube.roll = (tube.roll + speed * dt) % 1.0

        clock = VGroup()
        clock.add_updater(slip)
        self.add(clock)

        self.wait(4.0)
        print(f"roll at the end: {round(tube.roll, 3)} — a plain field, no internal clock")


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    CrtRoll(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
