"""Course 2 · 3.2 — The magnifier: a second camera on its own layer

CE's `ZoomedScene` renders the scene TWICE: a second camera draws an inset
"display". Janim has the real thing — a `Layer` can carry its own
`CameraFrame` and a `window`:

    Layer(*world, camera=zoom, window=display)

  · `camera` says what the layer SEES: a real second render through a real
    camera, so stroke widths do not grow with the zoom and nothing needs to
    re-adopt geometry with `become` every frame.
  · `window` says where the finished picture SHOWS: the mobject's bounding
    box on screen. The layer does not draw the mobject itself — give it a
    stroke and put it in a layer on top, and that is the border. Animate
    it and the window follows.

What the window shows is the largest CENTRED cut of the camera's view that
matches the window's aspect. Make the window the same shape as the camera
frame — 16:9 here — and it shows exactly the camera's view, which is why
the on-screen region indicator below is just a rectangle of the camera's
own `get_width` × `get_height`, glued to its centre with an updater.

Course 3 owns layers properly; this lesson borrows the one it needs.

    python examples/tutorial/c2_03_camera/02_zoomed_camera.py
"""

from pathlib import Path

import numpy as np

from janim import *
from janim.math import cos, linear_range, sin, step_range

PREVIEW_T = 2.4


class ZoomedCamera(Scene):
    def construct(self):
        # ── the world, with detail worth magnifying ──────────────────────────
        world = VGroup()
        plane = NumberPlane(
            (-7.0, 7.0, 1.0),
            (-4.0, 4.0, 1.0),
            width=14.0,
            height=8.0,
            background_line_color="#25405C",
            faded_opacity=0.12,
        )
        world.add(plane)
        spiral = VMobject()
        spiral.set_points_as_corners(
            [(-2.5 + 0.13 * t * cos(t), 0.35 * t * sin(t) - 0.6, 0) for t in step_range(0, 9, 0.05)],
        )
        spiral.set_stroke(color="#58C4DD", width=3.0)
        world.add(spiral)
        for theta in linear_range(0, TAU, 9)[:8]:
            d = Dot((-2.5 + 0.22 * cos(theta), -0.6 + 0.22 * sin(theta), 0), radius=0.03)
            d.set_fill(color="#FFD25E")
            world.add(d)
        fine = Text("fine print", size=0.09, color="#7FDD58")
        fine.move_to((-2.5, -1.1, 0))
        world.add(fine)

        # ── the second camera, and where its picture lands ───────────────────
        focus = np.array((-2.5, -0.6, 0), dtype=np.float32)
        zoom = CameraFrame()
        zoom.set_frame_height(1.2)                 # capture 1.2 scene units tall
        zoom.add_updater(lambda f: f.move_to(focus))

        display = Rectangle(
            width=4.5,
            height=4.5 * 9 / 16,                   # 16:9, the camera frame's shape
        )
        display.set_stroke(color=GREY_A, width=4.0)
        display.set_fill(opacity=0)                # it must not cover its window
        display.to_corner(UR, buff=0.4)

        reticle = Rectangle(
            width=zoom.get_width(),                # the captured region, exactly
            height=zoom.get_height(),
        )
        reticle.set_stroke(color=GREY_A, width=2.0)
        reticle.set_fill(opacity=0)

        def track(m):
            m.set_width(zoom.get_width())          # …even while the zoom animates
            m.move_to(focus)

        reticle.add_updater(track)

        caption = Text(
            "a second camera on its own layer — a render, not a copy",
            size=0.36,
            color=GREY_C,
        )
        caption.to_edge(DOWN, buff=0.35)

        self.use_composition(
            Composition(
                Layer(world),
                Layer(reticle, caption),
                Layer(world, camera=zoom, window=display),
                Layer(display),
                background=(0.02, 0.03, 0.05, 1),
            ),
        )

        self.wait(0.8)

        # The focus moves; the camera's own updater keeps it centred, so the
        # inset follows: the camera shows whatever it is aimed at, like any camera.
        def orbit(m, a):
            nonlocal focus
            focus = np.array(
                (-2.5 + 0.45 * cos(TAU * a), -0.75 + 0.35 * sin(TAU * a), 0),
                dtype=np.float32,
            )

        self.play(UpdateFromAlphaFunc(reticle, orbit), run_time=3.0)

        # A CameraFrame is a mobject: animating the zoom is animating it — while
        # the focus drifts back to the ring's centre and the reticle's updater
        # keeps the indicator matched with the tightening frame.
        p0 = focus
        ring = np.array((-2.5, -0.6, 0), dtype=np.float32)
        step = (ring - p0).astype(np.float64)      # a Float32 difference

        def home(m, a):
            nonlocal focus
            focus = (p0 + a * step).astype(np.float32)   # the lerp in Float64, rounded once

        self.play(
            zoom.animate.set_frame_height(0.7),
            UpdateFromAlphaFunc(reticle, home),
            run_time=1.2,
        )
        self.wait(0.6)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    ZoomedCamera(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
