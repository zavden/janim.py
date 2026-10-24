"""Demo 10 · MOTION BLUR — a wheel, four orbits and a camera sweep

This scene was written for motion blur that is not a directional smear
painted over the image: advance the scene's STATE between sub-exposures
and average (in linear light). Each object then blurs along ITS trajectory —
straight lines, arcs, rotations, camera movement — and with `shutter = 0.5`
(cinema's 180° shutter), a fast wheel's spokes merge into a disc,
as in a real camera.

Janim does not apply that motion blur inside the render loop: `Scene`
has no `motion_blur` kwarg (and the CLI rejects `--motion-blur` by name),
so video uses single exposures. What exists is the still image
`render_frame_motion(MotionBlur, t, n=8, shutter=0.5)` (see
`examples/tutorial/c3_05_motion_blur/04_render_frame_motion.py`), with its
limitation: it takes the frame containing each sub-exposure, and because
the shutter window (`shutter / fps`) is shorter than a frame, it averages
at most TWO distinct frames — two copies, not a trail (see this folder's README).

Three things in one shot: a title whipping in, an accelerating wheel,
four orbiting particles, and finally a camera sweep. The bottom caption
describes that sub-exposure motion blur, although the video does not
apply it. Manim has no motion blur.

    bin/janim render examples/demo/10_motion_blur.py -ql
"""

from pathlib import Path

import numpy as np

from janim import *
from janim.math import cos, sin


class MotionBlur(Scene):
    def construct(self):
        title = Text("motion blur", size=0.95, color=WHITE)
        title.move_to((-10.0, 2.4, 0))       # off screen, to the left

        # a spoked wheel: when spinning fast, its spokes merge into a disc
        wheel = VGroup()
        for k in range(6):
            spoke = Rectangle(width=3.0, height=0.16)
            spoke.set_fill("#FFD25E", opacity=1.0)
            spoke.set_stroke(opacity=0)
            spoke.rotate(k * TAU / 12)
            wheel.add(spoke)
        rim = Circle(radius=1.55)
        rim.set_stroke("#FFD25E", width=8.0)
        wheel.add(rim)
        hub = Circle(radius=0.22, fill_opacity=1.0)
        hub.set_fill("#FF3D8B", opacity=1.0)
        hub.set_stroke(opacity=0)
        wheel_center = np.array((-3.4, -0.9, 0), dtype=np.float32)
        wheel.move_to(wheel_center)
        hub.move_to(wheel_center)

        # rotation is a CLOSED-FORM function of time: accelerates for 3 s, then runs at 3 rev/s
        omega_max, t_acc = 3.0 * TAU, 3.0

        def angle(t):
            return omega_max * (t * t) / (2 * t_acc) if t < t_acc else omega_max * (t - t_acc / 2)

        theta_prev = [0.0]

        def spin(m, dt):
            theta = angle(self.t)
            m.rotate(theta - theta_prev[0], about_point=wheel_center)
            theta_prev[0] = theta

        wheel.add_updater(spin)

        # four particles in fast orbits: each follows its own arc
        orbit_center = np.array((3.4, -0.9, 0), dtype=np.float32)
        ring = Circle(radius=1.8)
        ring.move_to(orbit_center)
        ring.set_stroke("#25405C", width=2.0)
        orbiters = VGroup()
        for c in ("#FF3D8B", "#39D0FF", "#7FDD58", "#FFFFFF"):
            d = Dot(ORIGIN, radius=0.18)
            d.set_fill(c)
            orbiters.add(d)

        def orbit(m, dt):
            t = self.t
            for k, d in enumerate(m.submobjects):
                phi = 1.3 * TAU * t + k * TAU / 4
                d.move_to(orbit_center + np.array((1.8 * cos(phi), 1.8 * sin(phi), 0), dtype=np.float32))

        orbiters.add_updater(orbit)

        caption = Text(
            "motion_blur = 8, shutter = 0.5: the state advances between sub-exposures",
            size=0.32,
            color=GREY_C,
        )
        caption.to_edge(DOWN, buff=0.35)

        self.add(wheel, hub, ring, orbiters, title, caption)

        # 1 · the title whips in
        self.play(
            title.animate(rate_func=ease_out_quint).move_to((0, 2.4, 0)),
            run_time=0.6,
        )
        # 2 · the wheel accelerates and the particles orbit
        self.wait(5.0)
        # 3 · camera sweep: everything moves at once, including stationary objects
        self.play(
            self.frame.animate.move_to((3.2, -0.6, 0)).scale_frame(0.6),
            run_time=0.7,
        )
        self.wait(0.8)
        self.play(
            self.frame.animate.move_to(ORIGIN).scale_frame(1 / 0.6),
            run_time=0.7,
        )
        self.wait(1.2)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    # The video has no motion blur (see the docstring).
    MotionBlur(output=str(here.with_suffix(".mp4")), fps=30, resolution=(1280, 720)).render()
