"""Demo 01 · FOUR CAMERAS, ONE WORLD — 3D multicamera

The classic 3D editor panel, built with the compositor primitive:
FOUR layers sharing the SAME list of mobjects, each with its own
`CameraFrame` (`camera=`) and on-screen rectangle (`window=`). No copies
or fake projections: each view is a real render with its OWN z-buffer —
the satellite threading the torus hides behind the tube in some views
while remaining visible in others, exactly what a scaled copy cannot do.

Why this cannot be done in Manim: it has ONE camera drawing to the final
framebuffer. CE has `ZoomedScene` (a second camera with a fixed display)
and nothing more; GL does not even have that. Here a camera is a layer kwarg.

Two rules this file teaches:
  · the world can be in all four layers at once: updaters run only ONCE
    per frame (the live list is deduplicated by identity);
  · a window with the SAME shape as its camera frame (16:9 here)
    shows that camera's entire view, with no crop to guess.

The same scene lives in `examples/scenes/multicam_scenes.py:MulticamScene`.
Mutable updater state is held in single-element lists.

    bin/janim render examples/demo/01_multicam.py -ql
"""

from pathlib import Path

import numpy as np

from janim import *
from janim.math import cos, sin


class Multicam(Scene):
    def construct(self):
        # ── the world: a torus, its axes, and a satellite threading it ──────
        torus = Torus(
            r1=2.0,
            r2=0.55,
            resolution=(81, 41),
        )
        torus.set_color("#3F6FB0")
        torus.apply_depth_test()

        axes = VGroup()
        for direction, color in (
            ((3.2, 0, 0), "#E4573D"),
            ((0, 3.2, 0), "#63B463"),
            ((0, 0, 2.4), "#5AA8D8"),
        ):
            line = Line((0, 0, 0), direction)
            line.set_stroke(color, width=2.5)
            line.apply_depth_test()
            axes.add(line)

        sat = Sphere(radius=0.22)
        sat.set_color("#FFD25E")
        sat.apply_depth_test()
        phase = [0.0]

        def orbit(m, dt):
            phase[0] += 0.9 * dt
            m.move_to(
                np.array(
                    (2.0 + 1.1 * cos(phase[0]), 0, 1.1 * sin(phase[0])),
                    dtype=np.float32,
                ),
            )

        sat.add_updater(orbit)

        world = [torus, axes, sat]

        # ── four cameras on that world ─────────────────────────────────
        cam_top = CameraFrame()
        cam_top.set_frame_height(7.0)

        cam_front = CameraFrame()
        cam_front.reorient(0.0, 90.0)
        cam_front.set_frame_height(7.0)

        cam_side = CameraFrame()
        cam_side.reorient(90.0, 90.0)
        cam_side.set_frame_height(7.0)

        cam_persp = CameraFrame()
        cam_persp.reorient(-35.0, 62.0)
        cam_persp.set_frame_height(8.5)
        sway = [0.0]

        def swing(frame, dt):
            sway[0] += dt
            frame.reorient(-35.0 + 18.0 * sin(0.35 * sway[0]), 62.0)

        cam_persp.add_updater(swing)

        # ── the panel: four 16:9 windows tiling the frame ─────────────
        def win(x, y):
            r = Rectangle(
                width=6.91,
                height=6.91 * 9 / 16,
            )
            r.set_stroke(GREY_B, width=3.0)
            r.set_fill(opacity=0)
            r.move_to((x, y, 0))
            return r

        w_tl = win(-3.555, 2.0)
        w_tr = win(3.555, 2.0)
        w_bl = win(-3.555, -2.0)
        w_br = win(3.555, -2.0)

        def tag(txt, w):
            t = Text(txt, size=0.26, color=GREY_B)
            t.align_to(w, UL)
            t.shift((0.18, -0.28, 0))
            return t

        tags = [
            tag("TOP", w_tl),
            tag("PERSPECTIVE", w_tr),
            tag("FRONT", w_bl),
            tag("SIDE", w_br),
        ]

        self.use_composition(
            Composition(
                Layer(*world, camera=cam_top, window=w_tl),
                Layer(*world, camera=cam_persp, window=w_tr),
                Layer(*world, camera=cam_front, window=w_bl),
                Layer(*world, camera=cam_side, window=w_br),
                Layer(w_tl, w_tr, w_bl, w_br, *tags),
                background=(0.015, 0.02, 0.04, 1),
            ),
        )

        # All motion comes from updaters: two satellite orbits while the
        # perspective sways. The other three views are unaffected — each
        # has its own camera.
        self.wait(14.0)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    Multicam(output=str(here.with_suffix(".mp4")), fps=30, resolution=(1280, 720)).render()
