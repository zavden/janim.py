"""Demo 02 · THE GLOWING PENDULUM — physics inside an updater, a trail with
Bloom in an additive layer and a spotlight that is an ANIMATED MASK

A double pendulum integrated with Tsit5 INSIDE the rod's updater: the
integrator lives outside, the updater calls `step(integ, dt, True)` and
reads the state. The integrator is `janim.ode` (a Tsit5). Three things
Manim does not have:

  · the trail lives in a `blend="add"` layer with `Bloom`: light ADDS
    instead of covering, and the halo comes from the stroke's own color.
    Samples are joined with `set_points_smoothly` (GL's `make_smooth`):
    a curve through the same points, with no corners;
  · the bob has a `GlowDot` behind it: a ROUND per-fragment halo
    (`pow(1-r, 2)`), which Bloom cannot give a point — the widest level
    of its pyramid hit the kernel limit (±63 px) and the halo was SQUARE;
  · the spotlight following the tip is a mask with `feather`: it clips
    the lit grid, and as an ordinary mobject it moves with an updater;
  · the dim grid stays underneath, always visible — the same geometry
    twice, with two styles, in two layers.

This is act 2 of `examples/scenes/field_scene.py:FieldAndChaos`, without
the background field lines and with the complete grid.

Mutable updater state is held in single-element lists; sine and cosine
come from `janim.math`, and the grid range
(`-7.2` to `7.2` in steps of `0.8`) from `janim.math.step_range`, so the
samples are always the same.

    bin/janim render examples/demo/02_pendulum_glow.py -ql
"""

from pathlib import Path

import numpy as np

from janim import *
from janim.math import cos, sin, step_range
from janim.ode import ODEProblem, Tsit5, init, step

G02 = 9.8


def double_pendulum(du, u, p, t):
    theta1, theta2, omega1, omega2 = u
    delta = theta1 - theta2
    den = 3 - cos(2 * delta)
    du[0] = omega1
    du[1] = omega2
    du[2] = (
        -3 * G02 * sin(theta1)
        - G02 * sin(theta1 - 2 * theta2)
        - 2 * sin(delta) * (omega2 * omega2 + omega1 * omega1 * cos(delta))
    ) / den
    du[3] = 2 * sin(delta) * (2 * omega1 * omega1 + 2 * G02 * cos(theta1) + omega2 * omega2 * cos(delta)) / den


def grid(color, width):
    """The background grid, with the requested color and width."""
    g = VGroup()
    for x in step_range(-7.2, 7.2, 0.8):
        line = Line((x, -4.2, 0), (x, 4.2, 0))
        line.set_stroke(color, width=width)
        g.add(line)
    for y in step_range(-4.0, 4.0, 0.8):
        line = Line((-7.2, y, 0), (7.2, y, 0))
        line.set_stroke(color, width=width)
        g.add(line)
    return g


class PendulumGlow(Scene):
    def construct(self):
        background = Rectangle(
            width=16.0,
            height=9.0,
            fill_color="#0B0E14",
            fill_opacity=1.0,
            stroke_opacity=0,
            stroke_width=0,
        )
        grid_dim = grid("#182338", 1.2)      # the dim grid, always visible
        grid_lit = grid("#4A6FA8", 1.8)      # the lit grid under the spotlight

        # the spotlight: a filled circle that is NOT drawn — it clips the lit grid
        spotlight = Circle(radius=1.45, fill_opacity=1.0)

        # ── the pendulum ───────────────────────────────────────────────────
        pivot = np.array((0, 0.4, 0), dtype=np.float32)
        L = 1.25
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
        # the bob's halo: a GlowDot starts with its final style (an updater
        # moves it, and an updater does not reapply a DotCloud's opacity)
        halo = GlowDot(
            ORIGIN,
            color="#FFD25E",
            radius=0.55,
            glow_factor=2.0,
            opacity=0.0,
        )

        u0 = [2.1, 2.6, 0.0, 0.0]
        integ = init(
            ODEProblem(double_pendulum, u0, (0.0, 1e4)),
            Tsit5(),
            reltol=1e-9,
            abstol=1e-9,
        )

        def positions(u):
            p1 = pivot + np.array((L * sin(u[0]), -L * cos(u[0]), 0), dtype=np.float32)
            p2 = p1 + np.array((L * sin(u[1]), -L * cos(u[1]), 0), dtype=np.float32)
            return p1, p2

        # the initial state already drawn: nothing appears at the origin and then jumps
        p1, p2 = positions(u0)
        rod.set_points_as_corners([pivot, p1, p2])
        bob1.move_to(p1)
        bob2.move_to(p2)
        halo.move_to(p2)
        spotlight.move_to(p2)

        samples = []
        tip = [p2]
        running = [False]

        def swing(m, dt):
            if not (running[0] and dt > 0):
                return
            step(integ, dt, True)
            p1, p2 = positions(integ.u)
            m.set_points_as_corners([pivot, p1, p2])
            bob1.move_to(p1)
            bob2.move_to(p2)
            halo.move_to(p2)
            tip[0] = p2
            samples.append(p2)
            if len(samples) > 300:
                del samples[0]
            # corners + make_smooth in one call: the same curve
            if len(samples) > 1:
                trail.set_points_smoothly(list(samples))

        rod.add_updater(swing)

        def follow(m, dt):
            if running[0]:
                m.move_to(tip[0])

        spotlight.add_updater(follow)

        # ── the title ────────────────────────────────────────────────────
        def make_title(s, color):
            t = Tex(s, color=color, size=0.95)
            t.move_to(3.3 * UP)
            return t

        title = make_title(r"E = T + V", "#C8D2DC")

        self.use_composition(
            Composition(
                Layer(background, grid_dim),
                crop(grid_lit, inside=spotlight, feather=0.2),
                Layer(rod, bob1),
                # σ = 0.055 units is 5 px at 720p: all three pyramid levels
                # (σ, 2σ, 4σ) fit entirely in the kernel, so the halo is
                # truly Gaussian
                Layer(
                    trail,
                    halo,
                    bob2,
                    blend="add",
                    effects=[Bloom(threshold=0.25, intensity=1.8, sigma=0.055)],
                ),
                Layer(title),
            ),
        )

        # “appear” = Transform toward a copy with the final opacity (FadeIn
        # fades toward the CURRENT state, which here is 0)
        def appear(m, op):
            c = m.copy()
            c.set_fill(opacity=op)
            return Transform(m, c)

        self.play(
            AnimationGroup(
                FadeIn(title, shift=0.3 * DOWN),
                appear(bob1, 1.0),
                appear(bob2, 1.0),
                UpdateFromAlphaFunc(halo, lambda m, a: m.set_opacity(0.7 * a)),
            ),
            run_time=1.2,
        )
        running[0] = True
        self.wait(8.0)
        self.play(
            Transform(title, make_title(r"\dot\theta_1, \; \dot\theta_2", "#FFD25E")),
            run_time=1.0,
        )
        self.wait(10.0)

        # freeze BEFORE fading: if the updater continues, it reapplies the style
        # every frame and the fade is invisible
        running[0] = False
        self.play(
            AnimationGroup(
                FadeOut(rod),
                FadeOut(bob1),
                FadeOut(bob2),
                FadeOut(trail),
                FadeOut(title),
                UpdateFromAlphaFunc(halo, lambda m, a: m.set_opacity(0.7 * (1 - a))),
            ),
            run_time=1.8,
        )
        self.wait(0.6)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    PendulumGlow(output=str(here.with_suffix(".mp4")), fps=30, resolution=(1280, 720)).render()
