"""Course 2 · 3.1 — Moving the camera

CE has a `MovingCameraScene` you must inherit from. Here every scene's
camera is already animatable: `self.frame` is a `CameraFrame`, a mobject
that is a live VIEW onto the camera the scene renders with.

    self.frame.animate.scale_frame(0.5)        zoom IN (factor < 1)
    self.frame.animate.move_to(2 * RIGHT)      pan
    self.frame.animate.set_frame_height(3.0)   "show me 3 units tall"
    self.frame.animate.reorient(-40.0, 70.0)   the 3D angles (lesson 3.3)
    self.frame.reset_frame()

It works because `CameraFrame` implements the interpolation contract —
nothing in `Transform` knows a camera exists. The orientation is
interpolated with a quaternion slerp, so a rotating camera takes the short
arc at constant angular speed instead of the wobble a component-wise lerp
gives.

ONE THING THAT DOES NOT MOVE WITH IT: `to_edge` and `FRAME_X_RADIUS` speak
about the NOMINAL frame (8 units tall), not about the current camera. Zoom
in and a title placed with `to_edge` does not follow — same as Manim. If
you want it pinned to the screen, that is `fix_in_frame`.

    python examples/tutorial/c2_03_camera/01_moving_camera.py
"""

from pathlib import Path

from janim import *
from janim.core._julia_math import cos, sin

PREVIEW_T = 3.0


class MovingCamera(Scene):
    def construct(self):
        # A world with detail at two scales, so zooming has something to find.
        grid = NumberPlane(
            (-8.0, 8.0, 1.0),
            (-5.0, 5.0, 1.0),
            width=16.0,
            height=10.0,
            background_line_color="#25405C",
            faded_opacity=0.15,
        )
        self.add(grid)

        big = Circle(radius=2.2)
        big.set_stroke(color="#58C4DD", width=4.0)
        big.set_fill(opacity=0)
        big.move_to(1.5 * LEFT)

        tiny = VGroup()
        for k in range(12):
            theta = k * TAU / 12
            d = Dot((2.6 + 0.28 * cos(theta), 0.9 + 0.28 * sin(theta), 0), radius=0.035)
            d.set_fill(color="#FFD25E")
            tiny.add(d)
        label = Text("detail", size=0.12, color="#FFD25E")
        label.move_to((2.6, 0.45, 0))

        pinned = Text("fix_in_frame!: stays put", size=0.4, color=GREY_A)
        pinned.to_corner(UL, buff=0.4)
        pinned.fix_in_frame()

        floating = Text(
            "to_edge! is nominal: it does not follow",
            size=0.4,
            color=GREY_C,
        )
        floating.to_edge(DOWN, buff=0.4)

        self.add(big, tiny, label, pinned, floating)
        self.wait(0.5)

        # Zoom IN: a factor below 1 shrinks the frame, so the world grows.
        self.play(
            self.frame.animate.scale_frame(0.22).move_to((2.6, 0.9, 0)),
            run_time=2.2,
        )
        self.wait(0.8)
        print(
            "frame height now: ",
            round(self.frame.get_height(), 3),
            " scene units (nominal is ",
            FRAME_HEIGHT,
            ")",
            sep="",
        )

        # Pan while zoomed, then back. `reset_frame` is the way home.
        self.play(self.frame.animate.shift((-0.9, -0.4, 0)), run_time=1.2)
        self.play(self.frame.animate.reset_frame(), run_time=1.4)
        self.wait(0.4)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    MovingCamera(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
