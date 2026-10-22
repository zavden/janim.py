"""Course 3 · 5.5 — Why NOT to blur integrated physics

Motion blur subdivides `dt`: an integrator that took one step of 1/30 s now
takes `n` steps of 1/(30n) s. The total time per frame is identical; the
DISCRETISATION is not — and a chaotic system amplifies any difference
exponentially.

This lesson MEASURES it rather than asserting it. Two copies of the same
double pendulum from the same initial state, stepped for the same total
time, one in whole frames and one in eight pieces per frame. The numbers
below are printed by the scene, so you can check them:

    2 s    7.5e-11      ← indistinguishable
    5 s    1.1e-9
   10 s    1.6e-8
   15 s    5.4e-5
   20 s    6.7e-2       ← plainly a different pendulum

That is the shape to remember. It is NOT that the blurred integration is
wrong — both are accurate to the solver's tolerance. It is that a Lyapunov
exponent turns 1e-11 into 1e-1 in twenty seconds, and the two renders stop
being the same film. With a looser tolerance it happens sooner: at
reltol = 1e-6 the same test reaches 10 radians by 20 s.

So: blur animations, text, graphs and camera moves. If the TRAJECTORY is the
content, render without blur — or pre-compute the path once and animate
along it, which blurs safely because the path is then a function of time.

    python examples/tutorial/c3_05_motion_blur/05_physics_warning.py
"""

from decimal import Decimal
import math
from pathlib import Path

import numpy as np

from janim import *
from janim.math import cos, log10, sin
from janim.ode import ODEProblem, Tsit5, init, step

G = 9.8


def pendulum(du, u, p, t):
    """The double pendulum, term by term in a fixed evaluation order (so the trajectory is reproducible)."""
    theta1, theta2, omega1, omega2 = u
    delta = theta1 - theta2
    den = 3 - cos(2 * delta)
    du[0] = omega1
    du[1] = omega2
    du[2] = (-3 * G * sin(theta1) - G * sin(theta1 - 2 * theta2) - 2 * sin(delta) * (omega2 * omega2 + omega1 * omega1 * cos(delta))) / den
    du[3] = 2 * sin(delta) * (2 * omega1 * omega1 + 2 * G * cos(theta1) + omega2 * omega2 * cos(delta)) / den


def walk(u0, frames, sub, fps=30, tol=1e-10):
    """Step an integrator for `frames` frames, in `sub` pieces per frame."""
    integ = init(ODEProblem(pendulum, list(u0), (0.0, 1e4)), Tsit5(), reltol=tol, abstol=tol)
    dt = 1 / (fps * sub)
    for _ in range(frames * sub):
        step(integ, dt, True)
    return integ.u.copy()


def round_sigdigits(x, n):
    """Round a float to `n` significant digits: hidigit by log10, then round(x·10^k)/10^k."""
    if x == 0 or not math.isfinite(x):
        return x
    digits = n - (1 + math.floor(log10(abs(x))))
    if digits >= 0:
        invstep = 10.0 ** digits
        return float(round(x * invstep)) / invstep
    step_size = 10.0 ** -digits
    return float(round(x / step_size)) * step_size


def julia_string(x):
    """A float printed with its shortest round-trip digits: fixed form inside [1e-4, 1e6), exponent form outside."""
    sign, digits, exponent = Decimal(repr(float(x))).as_tuple()
    digits = list(digits)
    while len(digits) > 1 and digits[-1] == 0:
        digits.pop()
        exponent += 1
    text = "".join(map(str, digits))
    olength = len(digits)
    pt = exponent + olength
    if -4 < pt <= 6:                      # Ryu writeshortest: fixed form only in this window
        if pt <= 0:
            body = "0." + "0" * (-pt) + text
        elif pt >= olength:
            body = text + "0" * (pt - olength) + ".0"
        else:
            body = text[:pt] + "." + text[pt:]
    else:
        body = text[0] + "." + (text[1:] or "0") + "e" + str(pt - 1)
    return ("-" if sign else "") + body


PREVIEW_T = 2.0


class PhysicsWarning(Scene):
    def construct(self):
        u0 = [2.3, 2.7, 0.0, 0.0]

        header = Text("one step per frame  vs  eight (motion_blur = 8)", size=0.46, color=GREY_A)
        header.to_edge(UP, buff=0.4)
        self.add(header)

        rows = VGroup()
        for frames in (60, 150, 300, 450, 600):
            a = walk(u0, frames, 1)
            b = walk(u0, frames, 8)
            d = float(np.max(np.abs(a - b)))
            s = "after " + str(round(frames / 30)).rjust(2) + " s:  max |Δ| = " + julia_string(round_sigdigits(d, 3))
            colour = "#FF5E5E" if d > 1e-3 else "#FFD25E" if d > 1e-6 else "#7FDD58"
            rows.add(Text(s, size=0.42, color=colour, font="Liberation Mono"))
            print(s)
        rows.arrange(DOWN, buff=0.3, aligned_edge=LEFT)
        rows.move_to(0.3 * UP)
        self.add(rows)

        note = Text("chaos amplifies the discretisation, not the accuracy", size=0.36, color=GREY_B)
        note.move_to(2.6 * DOWN)
        self.add(note)

        self.play(
            LaggedStart(*(FadeIn(r, shift=0.25 * RIGHT) for r in rows.submobjects), lag_ratio=0.22),
            run_time=2.2,
        )
        self.play(Write(note), run_time=0.8)
        self.wait(0.8)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    PhysicsWarning(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
