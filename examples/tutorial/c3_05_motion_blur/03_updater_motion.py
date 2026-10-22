"""Course 3 · 5.3 — Motion blur smears updaters too

This is the difference between real motion blur and a directional smear.
The scene STATE is advanced between sub-exposures, so anything that moves —
`self.play` animations, updaters, `always_redraw`, a camera move — is smeared
along its own path.

`render_frame_motion` does exactly this: it advances the scene to the start
of the shutter, then takes one exposure per sub-step

    for sub_dt in subs:                 # one exposure per step
        update everything by sub_dt
        draw and accumulate

so `dt` reaches your updater in `n` pieces instead of one. Which is fine for
anything that computes a position from time, and NOT fine for an integrator
— that is lesson 5.5.

One consequence worth naming: a `TracedPath` under motion blur samples once
per SUB-EXPOSURE, so its trail gets n times as many points per frame. That
is more accurate, and it is also n times the memory.

(The same loop inside the video frame loop, `Scene(..., motion_blur=10)`, does
not exist in Janim. The still is the mechanism that remains.)

    python examples/tutorial/c3_05_motion_blur/03_updater_motion.py
"""

from pathlib import Path

import numpy as np

from janim import *
from janim.math import cos, sin

PREVIEW_T = 1.6
PREVIEW_MOTION = 10

HUB = np.array((0, -0.3, 0), dtype=np.float32)      # a float32 point, like every mobject coordinate


class UpdaterMotion(Scene):
    def construct(self):
        title = Text("the state advances between exposures", size=0.42, color=GREY_A)
        title.to_edge(UP, buff=0.35)
        self.add(title)

        # Nothing here is a `self.play`: every motion comes from an updater.
        arms = VGroup()
        for k in range(6):
            d = Dot(HUB, radius=0.2)
            d.set_fill(color_gradient(["#39D0FF", "#FF3D8B"], 6)[k])
            arms.add(d)
        self.add(arms)

        def orbit(m, dt):
            if dt <= 0:
                return
            for k, d in enumerate(m.submobjects, 1):
                theta = 2.2 * self.t + (k - 1) * TAU / 6
                r = 1.5 + 0.6 * sin(1.7 * self.t + k)
                # Point3f arithmetic: the offset is rounded to Float32, then added in Float32
                d.move_to(HUB + np.array((r * cos(theta), r * sin(theta), 0), dtype=np.float32))

        arms.add_updater(orbit)

        # An always_redraw whose GEOMETRY changes every frame — it smears too.
        def ripple_now():
            r = 2.6 + 0.5 * sin(3.1 * self.t)
            c = Circle(radius=r)
            c.set_stroke("#FFD25E", width=3.0)
            c.set_fill(opacity=0)
            c.move_to(HUB)
            return c

        ripple = always_redraw(ripple_now)
        self.add(ripple)

        self.wait(3.0)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    # No per-video motion blur: the blurred STILL is render_frame_motion.
    UpdaterMotion(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
