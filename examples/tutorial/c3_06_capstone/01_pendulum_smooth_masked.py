"""Course 3 · 6 — CAPSTONE: the field and the chaos, without a word on screen

A tour of a field and a chaotic system would carry formulas, captions and
several acts. This is the same machine with the words taken away: one
double pendulum, a trail rounded by `make_smooth` and nothing on screen but
light. Everything it teaches is in this file's comments, which is where a
capstone's explanation belongs.

What is stacked here, and where each piece was taught:

  the trail is a TracedPath(smooth=True)              course 1, lesson 6.3
  the spotlight is an animated MASK following it      course 3, lesson 3.6
  the trail glows on an "add" layer with Bloom        course 3, lesson 2.8
  the streamlines sit behind a per-layer Dof          course 3, lesson 2.7
  the ending is an adjustment layer's blur            course 3, lesson 1.4
  the physics is a real integrator in an updater      course 2, lesson 4.1

THE ONE NEW THING, and it is the trap this scene exists to teach:

  WITH A COMPOSITION MOUNTED, PUT THE SIMULATION IN A SCENE-LEVEL MOBJECT.

The update pass runs `self.mobjects` FIRST and the layers' contents
afterwards, in layer order. A trail that reads the pendulum's state must be
updated AFTER the pendulum writes it — but the trail's layer has to sit
BELOW the pendulum's to be drawn behind it, and those two orders are the
same list. Driving the integrator from an invisible mobject added straight
to the scene breaks the tie: the state is written before any layer runs, so
every layer reads this frame's value and nothing lags.

(The 2D version of the same trap — `bring_to_back` costing a whole frame of
lag — is course 1, lesson 1.6.)

    python examples/tutorial/c3_06_capstone/01_pendulum_smooth_masked.py
"""

from pathlib import Path

import numpy as np

from janim import *
from janim.core._julia_math import cos, sin
from janim.core._ranges import step_range
from janim.ode import ODEProblem, Tsit5, init, solve, step

G = 9.8
L = 1.25                       # arm length, scene units
PIVOT = np.array((0, 1.5, 0), dtype=np.float32)      # a float32 point, like every mobject coordinate


def pendulum(du, u, p, t):
    """The double pendulum, term by term in a fixed evaluation order (so the trajectory is reproducible)."""
    theta1, theta2, omega1, omega2 = u
    delta = theta1 - theta2
    den = 3 - cos(2 * delta)
    du[0] = omega1
    du[1] = omega2
    du[2] = (-3 * G * sin(theta1) - G * sin(theta1 - 2 * theta2) - 2 * sin(delta) * (omega2 * omega2 + omega1 * omega1 * cos(delta))) / den
    du[3] = 2 * sin(delta) * (2 * omega1 * omega1 + 2 * G * cos(theta1) + omega2 * omega2 * cos(delta)) / den


def rotation(du, u, p, t):
    """The rotational field: its streamlines are circles."""
    du[0] = -u[1]
    du[1] = u[0]


PREVIEW_T = 11.0


class PendulumSmoothMasked(Scene):
    def construct(self):
        # ── the cast ─────────────────────────────────────────────────────────
        background = Rectangle(width=16.0, height=9.0)
        background.set_fill("#080B12", 1.0)
        background.set_stroke(opacity=0)

        # the rotational field, integrated properly so the streamlines are circles
        lines = VGroup()
        for r in step_range(0.8, 3.6, 0.5):
            sol = solve(ODEProblem(rotation, [r, 0.0], (0.0, TAU)), Tsit5(), reltol=1e-8, abstol=1e-8, saveat=0.06)
            v = VMobject()
            v.set_points_as_corners([(u[0], u[1], 0) for u in sol.u])
            v.set_stroke("#39D0FF", width=3.0, opacity=0.0)
            lines.add(v)

        # the grid nobody can see until the spotlight passes over it
        grid = VGroup()
        for x in step_range(-7.2, 7.2, 0.75):
            l = Line((x, -4.2, 0), (x, 4.2, 0))
            l.set_stroke("#2A3B55", width=1.8)
            grid.add(l)
        for y in step_range(-4.0, 4.0, 0.75):
            l = Line((-7.2, y, 0), (7.2, y, 0))
            l.set_stroke("#2A3B55", width=1.8)
            grid.add(l)
        spot = Circle(radius=1.45, fill_opacity=1.0)
        spot.move_to((99, 99, 0))        # parked: nothing is revealed yet

        # the pendulum
        rod = VMobject()
        rod.set_stroke("#C8D2DC", width=3.2)      # final style at birth
        bob1 = Dot(PIVOT, radius=0.10)
        bob1.set_fill("#C8D2DC", 0.0)
        bob2 = Dot(PIVOT, radius=0.13)
        bob2.set_fill("#FFD25E", 0.0)

        # ── the simulation, driven from a SCENE-LEVEL mobject (see the header) ──
        integ = init(ODEProblem(pendulum, [2.2, 2.65, 0.0, 0.0], (0.0, 1e4)), Tsit5(), reltol=1e-10, abstol=1e-10)
        state = [(PIVOT, PIVOT)]
        running = [False]

        physics = VGroup()                       # invisible, and in NO layer

        def simulate(m, dt):
            if not (running[0] and dt > 0):
                return
            step(integ, dt, True)
            theta1, theta2 = integ.u[0], integ.u[1]
            # Point3f arithmetic: each offset is rounded to Float32, then added in Float32
            a = PIVOT + np.array((L * sin(theta1), -L * cos(theta1), 0), dtype=np.float32)
            state[0] = (a, a + np.array((L * sin(theta2), -L * cos(theta2), 0), dtype=np.float32))

        physics.add_updater(simulate)
        self.add(physics)                        # ← updated BEFORE every layer

        rod.add_updater(lambda m: m.set_points_as_corners([PIVOT, state[0][0], state[0][1]]))
        bob1.add_updater(lambda m: m.move_to(state[0][0]))
        bob2.add_updater(lambda m: m.move_to(state[0][1]))
        spot.add_updater(lambda m: running[0] and m.move_to(state[0][1]))

        # THE TRAIL: the same samples the pendulum visits, joined as a CURVE.
        # `smooth=True` runs make_smooth over them each frame — it moves no
        # anchor, so the trail never invents a point the bob did not reach; it
        # only changes how the visits are joined up. Worth it exactly here, where
        # the tip moves far between one frame and the next.
        trail = TracedPath(
            lambda: state[0][1],
            stroke_color="#39D0FF",
            stroke_width=2.8,
            time_traced=6.0,
            smooth=True,
        )

        dream = Blur(0.001)                       # the adjustment layer's dial

        # ── the stack ────────────────────────────────────────────────────────
        self.use_composition(
            Composition(
                Layer(background),
                crop(grid, inside=spot, feather=0.35),
                Layer(lines, effects=[Dof(focal_distance(self.camera) - 1.4, aperture=0.05, max_sigma=2.0)]),
                Layer(trail, blend="add", effects=[Bloom(threshold=0.22, intensity=1.6, sigma=0.15)]),
                Layer(rod, bob1, bob2),
                Layer(effects=[dream]),
                background=(0.02, 0.025, 0.04, 1),
            ),
        )

        # ── act 1 · the field (0 – 4 s) ──────────────────────────────────────
        def appear(m, op):
            c = m.copy()
            c.set_stroke(opacity=op)
            return Transform(m, c)

        def appear_fill(m, op):
            c = m.copy()
            c.set_fill(opacity=op)
            return Transform(m, c)

        self.play(
            LaggedStart(*(appear(l, 0.9) for l in lines.submobjects), lag_ratio=0.12),
            run_time=3.2,
        )
        self.wait(0.6)

        # ── act 2 · the chaos (4 – 17 s) ─────────────────────────────────────
        self.play(
            AnimationGroup(appear(lines, 0.16), appear_fill(bob1, 1.0), appear_fill(bob2, 1.0)),
            run_time=1.2,
        )
        running[0] = True
        self.wait(12.0)

        # ── act 3 · the blur takes it (17 – 21 s) ────────────────────────────
        # Freeze the simulation BEFORE fading: an updater that keeps writing
        # points would re-stamp the factory style and the fade would show nothing.
        def rise(m, a):
            dream.sigma = 0.001 + 0.20 * a

        self.play(UpdateFromAlphaFunc(background, rise), run_time=1.6)
        running[0] = False
        spot.move_to((99, 99, 0))        # park the spotlight again
        self.play(
            AnimationGroup(FadeOut(rod), FadeOut(bob1), FadeOut(bob2), FadeOut(trail), appear(lines, 0.0)),
            run_time=1.8,
        )

        def fall(m, a):
            dream.sigma = 0.20 - 0.199 * a

        self.play(UpdateFromAlphaFunc(background, fall), run_time=1.2)
        self.wait(0.6)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    PendulumSmoothMasked(output=str(out), fps=60, resolution=(1920, 1080)).render()
    print("→", out)
