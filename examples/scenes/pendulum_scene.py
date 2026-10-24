"""One double pendulum, its trail joined two ways, as a Manim scene."""

import numpy as np

from janim import *
from janim.math import cos, sin
from janim.ode import ODEProblem, Tsit5, init, step

G = 9.8
L = 1.15
OFFSET = np.array((6.0, 0, 0), dtype=np.float32)
PIVOT = np.array((-3.0, 0.95, 0), dtype=np.float32)


def double_pendulum(du, u, p, t):
    theta1, theta2, omega1, omega2 = u
    delta = theta1 - theta2
    den = 3 - cos(2 * delta)
    du[0] = omega1
    du[1] = omega2
    du[2] = (-3 * G * sin(theta1) - G * sin(theta1 - 2 * theta2) - 2 * sin(delta) * (omega2 * omega2 + omega1 * omega1 * cos(delta))) / den
    du[3] = 2 * sin(delta) * (2 * omega1 * omega1 + 2 * G * cos(theta1) + omega2 * omega2 * cos(delta)) / den


class PendulumTrail(Scene):
    def construct(self):
        title = Text("The same trail, joined two ways", size=0.55)
        title.to_edge(UP, buff=0.3)
        left = Text("polygonal", size=0.42, color="#8894A6")
        right = Text("make_smooth!", size=0.42, color="#58C4DD")
        left.move_to((-3.0, -3.15, 0))
        right.move_to((3.0, -3.15, 0))
        self.add(title, left, right)

        integrator = init(ODEProblem(double_pendulum, [2.3, 2.7, 0.0, 0.0], (0.0, 1e4)), Tsit5(), reltol=1e-10, abstol=1e-10)
        state = [(PIVOT, PIVOT)]          # (elbow, tip)

        # ONE integrator: the left rod's. Everything else reads it.
        rod = VMobject()
        rod.set_stroke("#C8D2DC", width=3.0)

        def swing(m, dt):
            if dt > 0:
                step(integrator, dt, True)
                theta1, theta2 = integrator.u[0], integrator.u[1]
                a = PIVOT + np.array((L * sin(theta1), -L * cos(theta1), 0), dtype=np.float32)
                state[0] = (a, a + np.array((L * sin(theta2), -L * cos(theta2), 0), dtype=np.float32))
            m.set_points_as_corners([PIVOT, state[0][0], state[0][1]])

        rod.add_updater(swing)

        def column(offset, shadow):
            """The same pendulum drawn in the column `offset`: rod and two masses."""
            if shadow:
                v = VMobject()
                v.set_stroke("#C8D2DC", width=3.0)
                v.add_updater(lambda m, dt: m.set_points_as_corners([PIVOT + offset, state[0][0] + offset, state[0][1] + offset]))
            else:
                v = rod
            b1 = Circle(radius=0.085)
            b1.set_fill("#C8D2DC", opacity=1.0)
            b2 = Circle(radius=0.105)
            b2.set_fill("#FFD25E", opacity=1.0)
            b1.set_stroke(opacity=0)
            b2.set_stroke(opacity=0)
            b1.add_updater(lambda m, dt: m.move_to(state[0][0] + offset))
            b2.add_updater(lambda m, dt: m.move_to(state[0][1] + offset))
            return (v, b1, b2)

        raw = TracedPath(lambda: state[0][1], stroke_color="#8894A6", stroke_width=2.8, time_traced=5.0)
        smooth = TracedPath(lambda: state[0][1] + OFFSET, stroke_color="#58C4DD", stroke_width=2.8, time_traced=5.0, smooth=True)
        self.add(*column(np.zeros(3, dtype=np.float32), False), *column(OFFSET, True), raw, smooth)
        raw.set_z_index(-1)
        smooth.set_z_index(-1)
        self.wait(14.0)
