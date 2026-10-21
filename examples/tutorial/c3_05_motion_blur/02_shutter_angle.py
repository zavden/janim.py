"""Course 3 · 5.2 — Shutter angle

    shutter=0.5      the 180° shutter — cinema's default

`shutter` is the FRACTION OF THE FRAME INTERVAL during which the shutter is
open. Film cameras spell the same number as an angle on a rotating disc, so
the two vocabularies map like this:

    shutter 0.25 →  90°   crisp, staccato (Saving Private Ryan)
    shutter 0.5  → 180°   the standard look
    shutter 1.0  → 360°   maximum smear, one exposure touching the next

The trade is between STROBING and MUSH. Too short and fast motion strobes
(the eye sees discrete copies); too long and everything is soft. 180° is the
default because it is the compromise a century of cinema settled on.

Cost: `n` sub-exposures means the frame is DRAWN n times, so the render is
roughly n× slower. The scene is simulated once either way.

There is no per-video shutter setting (`Scene(...)` takes no `motion_blur`
or `shutter`); the three renders to compare are three blurred STILLS through
`render_frame_motion(..., shutter=s)` — a single frame cannot show three
shutters at once, and pretending otherwise would be a lie.

    python examples/tutorial/c3_05_motion_blur/02_shutter_angle.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.0
PREVIEW_MOTION = 12


class ShutterAngle(Scene):
    def construct(self):
        title = Text("shutter is how long the exposure lasts", size=0.42, color=GREY_A)
        title.to_edge(UP, buff=0.35)
        self.add(title)

        # Three identical bars at different heights, all moving fast. The
        # scene renders once per shutter value (see the footer), so the three
        # renders are what you compare.
        bars = VGroup()
        for k, colour in enumerate(("#39D0FF", "#FFD25E", "#FF3D8B"), 1):
            r = Rectangle(width=1.1, height=0.7)
            r.set_fill(colour, 1.0)
            r.set_stroke(opacity=0)
            r.move_to((-5.0, 1.7 - 1.5 * (k - 1), 0))
            bars.add(r)
        self.add(bars)

        labels = VGroup()
        for k, s in enumerate(("slow", "medium", "fast"), 1):
            t = Text(s, size=0.32, color=GREY_B)
            t.move_to((-6.2, 1.7 - 1.5 * (k - 1), 0))
            labels.add(t)
        self.add(labels)

        # ease_in_out_cubic and ease_in_expo are the easings.net rate functions.
        self.play(
            AnimationGroup(
                bars[0].animate(rate_func=linear).move_to((5.0, 1.7, 0)),
                bars[1].animate(rate_func=ease_in_out_cubic).move_to((5.0, 0.2, 0)),
                bars[2].animate(rate_func=ease_in_expo).move_to((5.0, -1.3, 0)),
            ),
            run_time=1.6,
        )
        self.wait(0.4)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    base = here.parents[1] / "output" / here.parent.name
    base.mkdir(parents=True, exist_ok=True)
    for shutter in (0.25, 0.5, 1.0):
        out = base / ("02_shutter_" + str(shutter).replace(".", "p") + ".png")
        render_frame_motion(
            ShutterAngle,
            PREVIEW_T,
            n=12,
            shutter=shutter,
            fps=30,
            resolution=(854, 480),
            png=str(out),
        )
        print("→", out)
