"""Demo 11 · CHASE AND MINIMAP — three cameras and a fixed HUD

A comet travels along a trefoil knot through three gates. On screen,
three views of the SAME world at once:

  · the main view, with the scene camera orbiting through `animate` in
    two segments: 11 s and another 10 continuing around the orbit,
    so the comet makes two passes through the gates;
  · CHASE: a layer whose camera follows the comet with an updater
    (`move_to` the comet's center, every frame) — the idiom that requires
    a `ZoomedScene` in CE is an updater on a `CameraFrame` here;
  · TOP: an overhead minimap in a SQUARE window — the window crops its
    camera view to the largest central section with its aspect ratio,
    so a square window on a 16:9 camera shows the central square.

The entire HUD (frames, labels, caption) uses `fix_in_frame()`: a layer's
window is projected by the PARENT's camera, and a screen-fixed mobject
stays still even when the main camera orbits — this is why the boxes
do not drift during the camera flight.

The trail is ONE `TracedPath` shared by all three layers: the updater
list is deduplicated by identity, so it records one point per frame,
not three.

The same scene, with ten fewer seconds of flight, lives in
`examples/scenes/multicam_scenes.py:ChaseScene`.

`NumberPlane` already IS the mobject (the layer receives it directly);
`normalize` on a Float32 point and `cross` / `norm` on Float64 vectors
are written by hand (multiply by the Float32 reciprocal of the norm;
`_cross`), and `atan(s, v[3])` is `scalar_atan2`, the two-argument `atan`.

    bin/janim render examples/demo/11_chase_camera.py -ql
"""

from pathlib import Path

import numpy as np

from janim import *
from janim.math import atan2, cos, sin
from janim.core.surface import _cross


def knot(t):
    return np.array(
        (
            0.85 * (sin(t) + 2 * sin(2 * t)),
            0.85 * (cos(t) - 2 * cos(2 * t)),
            -0.85 * sin(3 * t),
        ),
        dtype=np.float32,
    )


def normalize32(vector):
    """StaticArrays' `normalize` on a Point3f: multiply by the Float32 reciprocal of the norm."""
    x, y, z = vector
    length = np.float32(np.sqrt((x * x + y * y) + z * z))
    return (np.float32(1) / length) * vector


class ChaseCamera(Scene):
    def construct(self):
        self.frame.reorient(-30.0, 66.0, height=9.5)

        # ── the world: floor, gates, comet and its trail ─────────────────
        floor = NumberPlane(
            (-4.0, 4.0, 1.0),
            (-4.0, 4.0, 1.0),
            width=8.0,
            height=8.0,
            background_line_color="#1E3350",
            faded_opacity=0.10,
        )

        def gate(t0):
            g = Torus(
                r1=0.42,
                r2=0.055,
                resolution=(49, 25),
            )
            g.set_color("#8AE08A")
            g.apply_depth_test()
            p = knot(t0)
            v = normalize32(knot(t0 + 1e-3) - p)
            axis = _cross(np.array((0.0, 0.0, 1.0)), v.astype(np.float64))
            s = float(np.sqrt((axis[0] * axis[0] + axis[1] * axis[1]) + axis[2] * axis[2]))
            if s > 1e-6:
                g.rotate(atan2(s, float(v[2])), axis=axis)
            g.move_to(p)
            return g

        gates = [gate(0.8), gate(2.9), gate(5.0)]

        comet = Sphere(radius=0.14)
        comet.set_color("#FFD25E")
        comet.apply_depth_test()
        tau = [0.0]

        def fly(m, dt):
            tau[0] += 0.55 * dt
            m.move_to(knot(tau[0]))

        comet.add_updater(fly)
        trail = TracedPath(
            lambda: comet.get_center(),
            stroke_color="#FFD25E",
            stroke_width=2.5,
            time_traced=4.0,
        )

        world = [floor, *gates, trail, comet]

        # ── the other two cameras ────────────────────────────────────────
        cam_chase = CameraFrame()
        cam_chase.reorient(-30.0, 66.0)
        cam_chase.set_frame_height(2.4)
        cam_chase.add_updater(lambda f: f.move_to(comet.get_center()))

        cam_map = CameraFrame()
        cam_map.set_frame_height(7.5)             # overhead: φ = 0 is the top view

        # ── the HUD, fixed to the screen ────────────────────────────────────
        w_chase = Rectangle(
            width=4.2,
            height=4.2 * 9 / 16,
        )
        w_chase.set_stroke(GREY_B, width=3.0)
        w_chase.set_fill(opacity=0)
        w_chase.to_corner(UR, buff=0.35)

        w_map = Square(side_length=2.9)
        w_map.set_stroke(GREY_B, width=3.0)
        w_map.set_fill(opacity=0)
        w_map.to_corner(DR, buff=0.35)

        def tag(txt, w):
            t = Text(txt, size=0.24, color=GREY_B)
            t.align_to(w, UL)
            t.shift((0.14, -0.26, 0))
            return t

        caption = Text(
            "three cameras, one world — the HUD does not drift: fix_in_frame",
            size=0.34,
            color=GREY_C,
        )
        caption.to_corner(DL, buff=0.4)
        hud = [w_chase, w_map, tag("CHASE", w_chase), tag("TOP", w_map), caption]
        for mob in hud:
            mob.fix_in_frame()

        self.use_composition(
            Composition(
                Layer(*world),
                Layer(*world, camera=cam_chase, window=w_chase),
                Layer(*world, camera=cam_map, window=w_map),
                Layer(*hud),
                background=(0.015, 0.02, 0.04, 1),
            ),
        )

        # two flight segments: the original and ten more seconds continuing around the orbit
        self.wait(0.5)
        self.play(self.frame.animate.reorient(25.0, 58.0), run_time=11.0)
        self.play(self.frame.animate.reorient(85.0, 64.0), run_time=10.0)
        self.wait(0.5)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    ChaseCamera(output=str(here.with_suffix(".mp4")), fps=30, resolution=(1280, 720)).render()
