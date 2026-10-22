"""Course 2 · 4.1 — Simulations: a real integrator inside an updater

SciML's solvers are ordinary code, so the physics in a Janim scene can be
the same you would use for research — not a hand-rolled Euler step. Janim
ships SciML's Tsit5, step for step, as `janim.ode`:

    integ = init(ODEProblem(f, u0, tspan), Tsit5(), reltol=…, abstol=…)
    m.add_updater(lambda m, dt: …)   # `if dt > 0: step(integ, dt, True)`, then draw

FOUR RULES, all of them paid for:

  1. KEEP THE INTEGRATOR OUTSIDE the updater and `step` it by dt. Building
     it inside would re-start the simulation every frame.
  2. GUARD WITH `dt > 0`. Registration calls the updater once with dt = 0.
  3. ONE integrator drives everything. Two "identical" pendulums are two
     integrations, and a chaotic system separates them all by itself — you
     would be looking at the divergence, not at what you meant to show.
  4. DO NOT use motion blur over integrated physics. Subdividing dt makes
     the solver take n small steps instead of one big one; the total time is
     the same and the trajectory is not (measured: ~1e-2 for a non-linear
     system, five orders worse than a linear one).

The energy drift of this double pendulum with Tsit5 at reltol = 1e-10 is
~3·10⁻¹⁰ over the whole scene — printed at the end, so you can check rather
than believe.

    python examples/tutorial/c2_04_simulations/01_ode_pendulum.py
"""

from pathlib import Path

import numpy as np

from janim import *
from janim.math import cos, sin
from janim.ode import ODEProblem, Tsit5, init, step

G = 9.8
L = 1.15


def pendulum(du, u, p, t):
    """The double pendulum, equal masses and equal lengths (in units where L = 1).

    Uses `janim.math` and a fixed operation order: a chaotic
    system shows a one-ulp difference within seconds."""
    theta1, theta2, omega1, omega2 = u
    delta = theta1 - theta2
    den = 3 - cos(2 * delta)
    du[0] = omega1
    du[1] = omega2
    du[2] = (
        -3 * G * sin(theta1)
        - G * sin(theta1 - 2 * theta2)
        - 2 * sin(delta) * (omega2 * omega2 + omega1 * omega1 * cos(delta))
    ) / den
    du[3] = 2 * sin(delta) * (2 * (omega1 * omega1) + 2 * G * cos(theta1) + omega2 * omega2 * cos(delta)) / den


def energy(u):
    """Total energy — the number that says whether the integration is trustworthy."""
    theta1, theta2, omega1, omega2 = u
    kinetic = 0.5 * (2 * (omega1 * omega1) + omega2 * omega2 + 2 * omega1 * omega2 * cos(theta1 - theta2))
    potential = -G * (2 * cos(theta1) + cos(theta2))
    return kinetic + potential


PREVIEW_T = 5.0


class OdePendulum(Scene):
    def construct(self):
        title = Text("Tsit5 inside an updater", size=0.44, color=GREY_A)
        title.to_edge(UP, buff=0.3)
        self.add(title)

        pivot = np.array((0, 1.6, 0), dtype=np.float32)
        u0 = [2.3, 2.7, 0.0, 0.0]
        integ = init(
            ODEProblem(pendulum, list(u0), (0.0, 1e4)),
            Tsit5(),
            reltol=1e-10,
            abstol=1e-10,
        )                                                  # RULE 1: outside
        state = (pivot, pivot)

        rod = VMobject()
        rod.set_stroke(color="#C8D2DC", width=3.0)         # born with its style

        def swing(m, dt):
            nonlocal state
            if dt > 0:                                     # RULE 2
                step(integ, dt, True)
                theta1, theta2 = integ.u[0], integ.u[1]
                a = pivot + np.array((L * sin(theta1), -L * cos(theta1), 0), dtype=np.float32)
                state = (a, a + np.array((L * sin(theta2), -L * cos(theta2), 0), dtype=np.float32))
            m.set_points_as_corners([pivot, state[0], state[1]])

        rod.add_updater(swing)

        bob1 = Dot(pivot, radius=0.09)
        bob1.set_fill(color="#C8D2DC")
        bob2 = Dot(pivot, radius=0.11)
        bob2.set_fill(color="#FFD25E")
        bob1.add_updater(lambda m: m.move_to(state[0]))    # RULE 3: they READ
        bob2.add_updater(lambda m: m.move_to(state[1]))    # the one integrator

        # Add the trail AFTER what it follows, and layer it with set_z_index:
        # `bring_to_back` would put its updater first and cost a whole frame of
        # lag. `smooth=True` rounds the polyline through the same samples.
        self.add(rod, bob1, bob2)
        trail = TracedPath(
            lambda: state[1],
            stroke_color="#58C4DD",
            stroke_width=2.6,
            time_traced=4.0,
            smooth=True,
        )
        self.add(trail)
        trail.set_z_index(-1)

        readout = DecimalNumber(
            0.0,
            num_decimal_places=9,
            size=0.4,
            color=GREY_B,
        )
        readout.move_to((0, -3.3, 0))
        readout.add_updater(lambda d: d.set_value(energy(integ.u) - energy(u0)))
        caption = Text("energy drift", size=0.32, color=GREY_C)
        caption.move_to((0, -2.9, 0))
        self.add(readout, caption)

        self.wait(8.0)
        print("energy drift after ", round(self.t, 2), " s: ", energy(integ.u) - energy(u0), sep="")


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    OdePendulum(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
