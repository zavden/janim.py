"""The field, the chaos and the descent, as a Manim scene.

Stream lines by Tsit5, a double pendulum stepped inside an updater with a
bloomed trail, a spotlight mask over a grid, depth of field per layer, an
animated blur transition, morphing formulas, and a Fourier curve descending
by gradient (forward-mode duals) onto a star.
"""

import numpy as np

from janim import *
from janim.core._julia_math import cos, hypot, sin
from janim.core._ranges import linear_range, step_range
from janim.ode import ODEProblem, Tsit5, init, solve, step
from janim.ode.dual import abs2, dual_sum, gradient

G = 9.8
KF, SF = 12, 160


def double_pendulum(du, u, p, t):
    theta1, theta2, omega1, omega2 = u
    delta = theta1 - theta2
    den = 3 - cos(2 * delta)
    du[0] = omega1
    du[1] = omega2
    du[2] = (-3 * G * sin(theta1) - G * sin(theta1 - 2 * theta2) - 2 * sin(delta) * (omega2 * omega2 + omega1 * omega1 * cos(delta))) / den
    du[3] = 2 * sin(delta) * (2 * omega1 * omega1 + 2 * G * cos(theta1) + omega2 * omega2 * cos(delta)) / den


def star():
    """The target: 160 samples along a ten-pointed star, at equal arc length."""
    verts = []
    for i in range(1, 11):
        r = 2.0 if i % 2 == 1 else 0.85
        theta = PI / 2 + (i - 1) * TAU / 10
        verts.append((r * cos(theta), r * sin(theta)))
    sides = [hypot(verts[i % 10][0] - verts[i - 1][0], verts[i % 10][1] - verts[i - 1][1]) for i in range(1, 11)]
    accumulated = [0.0]
    for side in sides:
        accumulated.append(accumulated[-1] + side)
    total = sides[0]
    for side in sides[1:]:
        total = total + side
    target = np.zeros((SF, 2))
    for j, s in enumerate(linear_range(0, total, SF + 1)[:SF]):
        i = 1
        for k in range(len(accumulated), 0, -1):
            if accumulated[k - 1] <= s + 1e-12:
                i = k
                break
        i = min(i, 10)
        alpha = (s - accumulated[i - 1]) / sides[i - 1]
        first, second = verts[i - 1], verts[i % 10]
        target[j, 0] = first[0] + alpha * (second[0] - first[0])
        target[j, 1] = first[1] + alpha * (second[1] - first[1])
    return target


_SAMPLES = np.array(linear_range(0, 1, SF + 1)[:SF])
_HARMONICS = list(range(-KF, KF + 1))
# cos(2πks) and sin(2πks) per harmonic, evaluated one s at a time with the library's own trig
_COS = [np.array([cos(2 * PI * k * s) for s in _SAMPLES]) for k in _HARMONICS]
_SIN = [np.array([sin(2 * PI * k * s) for s in _SAMPLES]) for k in _HARMONICS]


def fourier(params):
    """The curve of 2KF + 1 harmonics at the SF samples, as two arrays (x, y).

    Works on floats and on duals: every element follows the scalar order of
    the loop `x += params[i] * c - params[M + i] * sn`.
    """
    m = 2 * KF + 1
    x = 0.0
    y = 0.0
    for i in range(m):
        c, sn = _COS[i], _SIN[i]
        x = x + (params[i] * c - params[m + i] * sn)
        y = y + (params[i] * sn + params[m + i] * c)
    return x, y


class FieldAndChaos(Scene):
    def construct(self):
        background = Rectangle(width=16.0, height=9.0, fill_color="#0B0E14", fill_opacity=1.0, stroke_opacity=0, stroke_width=0)

        # stream lines of the rotation field (Tsit5: true circles)
        lines = VGroup()
        for r in step_range(0.7, 3.4, 0.45):
            def rotation(du, u, p, t):
                du[0] = -u[1]
                du[1] = u[0]

            solution = solve(ODEProblem(rotation, [r, 0.0], (0.0, 2 * PI)), Tsit5(), reltol=1e-8, abstol=1e-8, saveat=0.06)
            v = VMobject()
            v.set_points_as_corners([(u[0], u[1], 0) for u in solution.u])
            v.set_stroke("#58C4DD", width=3.0, opacity=0.95)
            lines.add(v)

        # a grid revealed by the SPOTLIGHT (an animated mask)
        grid = VGroup()
        for x in step_range(-7.2, 7.2, 0.8):
            line = VMobject()
            line.start_new_path((x, -4.2, 0))
            line.add_line_to((x, 4.2, 0))
            line.set_stroke("#2A3B55", width=1.6)
            grid.add(line)
        for y in step_range(-4.0, 4.0, 0.8):
            line = VMobject()
            line.start_new_path((-7.2, y, 0))
            line.add_line_to((7.2, y, 0))
            line.set_stroke("#2A3B55", width=1.6)
            grid.add(line)
        spot = Circle(radius=1.35, fill_opacity=1.0)
        spot.move_to((99, 99, 0))            # parked: the grid stays hidden

        # the double pendulum and its trail
        pivot = np.array((0, 1.55, 0), dtype=np.float32)
        scale_factor = 1.25
        rod = VMobject()
        rod.set_stroke("#C8D2DC", width=3.5)
        bob1 = Circle(radius=0.11, fill_opacity=1.0)
        bob1.set_fill("#C8D2DC", opacity=0.0)
        bob1.set_stroke(opacity=0)
        bob2 = Circle(radius=0.13, fill_opacity=1.0)
        bob2.set_fill("#FFD25E", opacity=0.0)
        bob2.set_stroke(opacity=0)
        trail = VMobject()
        trail.set_stroke("#58C4DD", width=2.6, opacity=0.85)

        integrator = init(ODEProblem(double_pendulum, [2.1, 2.6, 0.0, 0.0], (0.0, 1e4)), Tsit5(), reltol=1e-9, abstol=1e-9)
        track = []
        tip = [np.array((99, 99, 0), dtype=np.float32)]
        pendulum_on = [False]

        def swing(m, dt):
            if not (pendulum_on[0] and dt > 0):
                return
            step(integrator, dt, True)
            u = integrator.u
            p1 = pivot + np.array((scale_factor * sin(u[0]), -scale_factor * cos(u[0]), 0), dtype=np.float32)
            p2 = p1 + np.array((scale_factor * sin(u[1]), -scale_factor * cos(u[1]), 0), dtype=np.float32)
            m.set_points_as_corners([pivot, p1, p2])
            bob1.move_to(p1)
            bob2.move_to(p2)
            tip[0] = p2
            track.append(p2)
            if len(track) > 260:
                del track[0]
            if len(track) > 1:
                trail.set_points_as_corners(list(track))

        rod.add_updater(swing)

        def follow(m, dt):
            if pendulum_on[0]:
                m.move_to(tip[0])

        spot.add_updater(follow)

        # the Fourier curve against the ghost star
        target = star()

        def loss(p):
            xs, ys = fourier(p)
            # sum of squares in column-major order: every x term, then every y term
            return dual_sum(abs2(xs - target[:, 0]), abs2(ys - target[:, 1])) / SF

        params = np.zeros(2 * (2 * KF + 1))
        params[KF + 1] = 1.0
        curve = VMobject()
        curve.set_stroke("#FFD25E", width=4.0)
        ghost = VMobject()
        ghost.set_points_as_corners([(target[j, 0], target[j, 1], 0) for j in [*range(SF), 0]])
        ghost.shift(0.6 * Vec3(DOWN))
        ghost.set_stroke("#3A4558", width=2.0, opacity=0.0)
        descent_on = [False]

        def descend(m, dt):
            if not descent_on[0]:
                return
            for _ in range(2):
                params[:] = params - 0.33 * gradient(loss, params)
            xs, ys = fourier(params)
            m.set_points_as_corners([(xs[j], ys[j] - 0.6, 0) for j in [*range(SF), 0]])

        curve.add_updater(descend)

        title = Tex(r"\frac{dx}{dt} = F(x)", color="#FFFFFF", size=1.05)
        title.move_to(3.0 * Vec3(UP))

        def make_title(source, color):
            return Tex(source, color=color, size=1.05).move_to(3.0 * Vec3(UP))

        blur_adjust = Blur(0.001)
        self.use_composition(
            Composition(
                Layer(background),
                crop(grid, inside=spot, feather=0.3),
                Layer(lines, effects=[Dof(self.camera.get_focal_distance() - 1.5, aperture=0.04)]),
                Layer(trail, blend="add", effects=[Bloom(threshold=0.25, intensity=1.5, sigma=0.16)]),
                Layer(rod, bob1, bob2),
                Layer(ghost, curve, blend="add", effects=[Bloom(threshold=0.3, intensity=1.2, sigma=0.12)]),
                Layer(effects=[blur_adjust]),
                Layer(title),
            ),
        )

        def appear(m, opacity):
            c = m.copy()
            c.set_stroke(opacity=opacity)
            return Transform(m, c)

        def appear_fill(m, opacity):
            c = m.copy()
            c.set_fill(opacity=opacity)
            return Transform(m, c)

        # act 1: the field (0-9 s)
        self.play(
            AnimationGroup(
                FadeIn(title, shift=0.3 * Vec3(DOWN)),
                LaggedStart(*[ShowCreation(line) for line in lines.submobjects], lag_ratio=0.12),
            ),
            run_time=4.0,
        )
        self.wait(2.4)

        # act 2: the chaos (9-36 s)
        self.play(
            AnimationGroup(
                Transform(title, make_title(r"E = T + V", "#C8D2DC")),
                appear(lines, 0.16),
                appear_fill(bob1, 1.0),
                appear_fill(bob2, 1.0),
            ),
            run_time=1.4,
        )
        pendulum_on[0] = True
        self.wait(9.0)
        self.play(Transform(title, make_title(r"\dot\theta_1, \; \dot\theta_2", "#FFD25E")), run_time=1.0)
        self.wait(18.0)

        # the dreamed transition: an animated blur (36-41 s)
        rising = [True]
        blur_clock = VGroup()

        def breathe(m, dt):
            blur_adjust.sigma = min(max(blur_adjust.sigma + (0.09 if rising[0] else -0.11) * dt, 0.001), 0.22)

        blur_clock.add_updater(breathe)
        self.add(blur_clock)
        pendulum_on[0] = False               # freeze: otherwise the updater re-stamps
        spot.move_to((99, 99, 0))            # the default style and the fade is lost
        self.play(
            AnimationGroup(FadeOut(rod), FadeOut(bob1), FadeOut(bob2), FadeOut(trail), appear(lines, 0.0)),
            run_time=2.2,
        )
        rising[0] = False
        self.wait(1.6)

        # act 3: the gradient (41-58 s)
        self.play(
            AnimationGroup(
                Transform(title, make_title(r"\theta \leftarrow \theta - \eta \nabla L", "#FFD25E")),
                appear(ghost, 0.8),
            ),
            run_time=1.4,
        )
        descent_on[0] = True
        self.wait(14.0)
        descent_on[0] = False
        self.play(Transform(title, make_title(r"L(\theta) \to 0", "#7FDD58")), run_time=1.0)
        self.wait(2.6)

        # coda (58-62 s)
        self.play(AnimationGroup(FadeOut(curve), FadeOut(ghost), FadeOut(title)), run_time=1.6)
        self.wait(1.4)
