"""Course 3 · 5.4 — Blurring a single frame

    render_frame_motion(SceneClass, t, n=8, shutter=0.5, fps=30,
                        resolution=(854, 480), png="f.png")

The still-image sibling of a blurred render: it renders `n` sub-frames centred
on `t` and averages them. Same picture as the video's frame at `t` would be
with that shutter, without encoding a video to look at one frame.

It is the honest way to CHECK a blurred render before committing to it, and
it is what this tutorial's runner uses when a lesson declares
`PREVIEW_MOTION` — an instantaneous frame simply cannot show the subject.

The sampling is symmetric about `t` (`t − dtf/2 + dtf(k+½)/n`), the same
midpoint rule the animation timeline uses, so the average is centred rather
than lagging half a shutter behind.

Cost: n full renders. At n = 8 that is 8× one frame — which is nothing for a
still and is exactly why you check a still first.

    python examples/tutorial/c3_05_motion_blur/04_render_frame_motion.py
"""

from pathlib import Path

from janim import *
from janim.math import cos, sin

PREVIEW_T = 1.0
PREVIEW_MOTION = 16


class RenderFrameMotion(Scene):
    def construct(self):
        title = Text("render_frame_motion: check the still, then render", size=0.4, color=GREY_A)
        title.to_edge(UP, buff=0.35)
        self.add(title)

        wheel = VGroup()
        for k in range(12):
            spoke = Line(ORIGIN, (1.9 * cos(k * TAU / 12), 1.9 * sin(k * TAU / 12), 0))
            spoke.set_stroke(color_gradient(["#39D0FF", "#FFD25E"], 12)[k], width=5.0)
            wheel.add(spoke)
        rim = Circle(radius=1.95)
        rim.set_stroke(GREY_A, width=4.0)
        rim.set_fill(opacity=0)
        wheel.add(rim)
        wheel.move_to(0.3 * DOWN)
        self.add(wheel)

        self.play(Rotating(wheel, 2 * TAU, run_time=2.0, rate_func=linear), run_time=2.0)
        self.wait(0.3)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    base = here.parents[1] / "output" / here.parent.name
    base.mkdir(parents=True, exist_ok=True)
    # The instantaneous frame…
    render_frame(RenderFrameMotion, 1.0, fps=30, resolution=(854, 480), png=str(base / "04_still_sharp.png"))
    # …and the same instant, exposed for half a frame.
    render_frame_motion(
        RenderFrameMotion,
        1.0,
        n=16,
        shutter=0.5,
        fps=30,
        resolution=(854, 480),
        png=str(base / "04_still_blurred.png"),
    )
    print("→", base, "/04_still_{sharp,blurred}.png — look at both")
