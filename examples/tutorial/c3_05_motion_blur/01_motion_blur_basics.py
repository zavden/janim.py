"""Course 3 · 5.1 — Motion blur

    render_frame_motion(SceneClass, t, n=8, shutter=0.5, fps=30, resolution=(854, 480))

Each frame becomes the average of `n` EXPOSURES inside the shutter, with the
scene state ADVANCED between them. So it is not a directional smear applied
to a picture: it is the real thing a camera does, and it smears every object
along its own path — curves, rotations and updater-driven motion included.

  n             sub-exposures per frame. `n ≤ 1` is an exact no-op: the
                frame loop takes exactly the branch it always took, so a
                scene without blur costs nothing.
  shutter       the fraction of the frame interval the shutter is open.
                0.5 is cinema's 180° shutter (lesson 5.2).

HONEST NOTE ON WHAT RENDERS. A per-video accumulator inside the frame loop
(`Scene(..., motion_blur=8, shutter=0.5)`, or a CLI flag `--motion-blur 8,0.5`)
is not part of Janim: `Scene(...)` takes no `motion_blur`/`shutter` and the
CLI rejects the flag. What exists is the still: `render_frame_motion`
averages `n` sub-exposures on the CPU in linear light. A lesson declares
`PREVIEW_MOTION` for it, because a single instantaneous frame cannot show the
point.

USE IT for animations, text, graphs and camera moves. Do NOT use it over
integrated physics — lesson 5.5 measures why.

    python examples/tutorial/c3_05_motion_blur/01_motion_blur_basics.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.2
PREVIEW_MOTION = 12          # ← the runner uses render_frame_motion


class MotionBlurBasics(Scene):
    def construct(self):
        title = Text("each frame is the average of n exposures", size=0.42, color=GREY_A)
        title.to_edge(UP, buff=0.35)
        self.add(title)

        # Fast linear motion: the classic case.
        slider = Square(side_length=0.9)
        slider.set_fill("#39D0FF", 1.0)
        slider.set_stroke(opacity=0)
        slider.move_to((-5.2, 1.6, 0))

        # Rotation: a directional blur could not do this one.
        spinner = VGroup()
        for k in range(3):
            r = Rectangle(width=2.2, height=0.22)
            r.set_fill("#FFD25E", 1.0)
            r.set_stroke(opacity=0)
            r.rotate(k * PI / 3)
            spinner.add(r)
        spinner.move_to((-2.5, -1.3, 0))

        # A curved path: every point follows its own arc.
        orbiter = Dot(ORIGIN, radius=0.24)
        orbiter.set_fill("#FF3D8B")
        ring = Circle(radius=1.5)
        ring.move_to((3.2, -1.0, 0))
        ring.set_stroke("#25405C", width=2.0)

        self.add(slider, spinner, ring, orbiter)

        self.play(
            AnimationGroup(
                slider.animate(rate_func=linear).move_to((5.2, 1.6, 0)),
                Rotating(spinner, 3 * TAU, run_time=2.0),
                MoveAlongPath(orbiter, ring, rate_func=linear),
            ),
            run_time=2.0,
        )
        self.wait(0.4)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    # There is no per-video motion blur (see the header). The video renders sharp;
    # the blurred STILL is
    # render_frame_motion(MotionBlurBasics, PREVIEW_T, n=PREVIEW_MOTION, shutter=0.5).
    MotionBlurBasics(output=str(out), fps=30, resolution=(1920, 1080)).render()
    print("→", out)
