"""Multicamera views and a chase camera, as Manim scenes."""

import numpy as np

from janim import *
from janim.math import atan2, cos, sin
from janim.core.surface import _cross


class MulticamScene(Scene):
    def construct(self):
        torus = Torus(r1=2.0, r2=0.55, resolution=(81, 41))
        torus.set_color("#3F6FB0")
        torus.apply_depth_test()
        axes = VGroup()
        for direction, color in (((3.2, 0, 0), "#E4573D"), ((0, 3.2, 0), "#63B463"), ((0, 0, 2.4), "#5AA8D8")):
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
            m.move_to(np.array((2.0 + 1.1 * cos(phase[0]), 0, 1.1 * sin(phase[0])), dtype=np.float32))

        sat.add_updater(orbit)
        world = [torus, axes, sat]
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

        def window(x, y):
            rectangle = Rectangle(width=6.91, height=6.91 * 9 / 16)
            rectangle.set_stroke(GREY_B, width=3.0)
            rectangle.set_fill(opacity=0)
            rectangle.move_to((x, y, 0))
            return rectangle

        w_tl = window(-3.555, 2.0)
        w_tr = window(3.555, 2.0)
        w_bl = window(-3.555, -2.0)
        w_br = window(3.555, -2.0)

        def tag(text, w):
            label = Text(text, size=0.26, color=GREY_B)
            label.align_to(w, UL)
            label.shift((0.18, -0.28, 0))
            return label

        tags = [tag("TOP", w_tl), tag("PERSPECTIVA", w_tr), tag("ALZADO", w_bl), tag("PERFIL", w_br)]
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
        self.wait(14.0)


def knot(t):
    return np.array(
        (0.85 * (sin(t) + 2 * sin(2 * t)), 0.85 * (cos(t) - 2 * cos(2 * t)), -0.85 * sin(3 * t)),
        dtype=np.float32,
    )


def _f32_normalize(vector):
    """Normalise a float32 vector by multiplying by the reciprocal float32 norm."""
    x, y, z = vector
    length = np.float32(np.sqrt((x * x + y * y) + z * z))
    return (np.float32(1) / length) * vector


class ChaseScene(Scene):
    def construct(self):
        self.frame.reorient(-30.0, 66.0, height=9.5)
        floor = NumberPlane(
            (-4.0, 4.0, 1.0),
            (-4.0, 4.0, 1.0),
            width=8.0,
            height=8.0,
            background_line_color="#1E3350",
            faded_opacity=0.10,
        )

        def gate(t0):
            g = Torus(r1=0.42, r2=0.055, resolution=(49, 25))
            g.set_color("#8AE08A")
            g.apply_depth_test()
            p = knot(t0)
            v = _f32_normalize(knot(t0 + 1e-3) - p)
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
        trail = TracedPath(lambda: comet.get_center(), stroke_color="#FFD25E", stroke_width=2.5, time_traced=4.0)
        world = [floor, *gates, trail, comet]
        cam_chase = CameraFrame()
        cam_chase.reorient(-30.0, 66.0)
        cam_chase.set_frame_height(2.4)
        cam_chase.add_updater(lambda frame: frame.move_to(comet.get_center()))
        cam_map = CameraFrame()
        cam_map.set_frame_height(7.5)             # top-down: phi = 0 is the plan view
        w_chase = Rectangle(width=4.2, height=4.2 * 9 / 16)
        w_chase.set_stroke(GREY_B, width=3.0)
        w_chase.set_fill(opacity=0)
        w_chase.to_corner(UR, buff=0.35)
        w_map = Square(side_length=2.9)
        w_map.set_stroke(GREY_B, width=3.0)
        w_map.set_fill(opacity=0)
        w_map.to_corner(DR, buff=0.35)

        def tag(text, w):
            label = Text(text, size=0.24, color=GREY_B)
            label.align_to(w, UL)
            label.shift((0.14, -0.26, 0))
            return label

        caption = Text("three cameras, one world — the HUD does not drift: fix_in_frame", size=0.34, color=GREY_C)
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
        self.wait(0.5)
        self.play(self.frame.animate.reorient(25.0, 58.0), run_time=11.0)
        self.wait(0.5)
