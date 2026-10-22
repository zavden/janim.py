"""Course 2 · 4.2 — Animation by gradient descent

Automatic differentiation differentiates ORDINARY code, so an updater can
descend a loss instead of following a script. Janim carries ForwardDiff's
forward mode as `janim.ode.dual` (`gradient`, `abs2`, `dual_sum`). The
animation is not "a shape moving towards another shape" — it is an optimiser
running in front of the viewer, and what you see is where the maths goes.

The rules are the updater rules again: the parameters live OUTSIDE (they are
state), the updater takes the steps, and the mobject is rebuilt from the
parameters every frame — so it must be born with its final style.

Here the curve is a truncated Fourier series

    z(s) = Σ_{k=-K}^{K} c_k · e^{2πiks}

and the loss is the mean squared distance to a target polygon, sampled at
the same parameter values. The gradient is taken through the WHOLE thing,
series evaluation included, with no derivative written by hand.

    python examples/tutorial/c2_04_simulations/02_gradient_descent.py
"""

from pathlib import Path

import numpy as np

from janim import *
from janim.math import cos, hypot, linear_range, sin
from janim.ode.dual import abs2, dual_sum, gradient

K = 10          # harmonics kept, each way
S = 140         # samples along the curve
M = 2 * K + 1   # coefficients


def star_target():
    """A five-pointed star, sampled by arc length so the loss is not biased."""
    verts = []
    for i in range(1, 11):
        r = 1.9 if i % 2 == 1 else 0.8
        theta = PI / 2 + (i - 1) * TAU / 10
        verts.append((r * cos(theta), r * sin(theta)))
    sides = [hypot(verts[i % 10][0] - verts[i - 1][0], verts[i % 10][1] - verts[i - 1][1]) for i in range(1, 11)]
    acc = [0.0]
    for side in sides:
        acc.append(acc[-1] + side)
    total = sides[0]                              # a plain left fold over the ten sides
    for side in sides[1:]:
        total = total + side
    out = np.zeros((S, 2))
    for j, s in enumerate(linear_range(0, total, S + 1)[:S]):
        i = 1
        for k in range(len(acc), 0, -1):          # last index with acc <= s + 1e-12
            if acc[k - 1] <= s + 1e-12:
                i = k
                break
        i = min(i, 10)
        alpha = (s - acc[i - 1]) / sides[i - 1]
        first, second = verts[i - 1], verts[i % 10]
        out[j, 0] = first[0] + alpha * (second[0] - first[0])
        out[j, 1] = first[1] + alpha * (second[1] - first[1])
    return out


_SAMPLES = np.array(linear_range(0, 1, S + 1)[:S])
_HARMONICS = list(range(-K, K + 1))
# cos(2πks) and sin(2πks) per harmonic, evaluated one s at a time with the
# functions of janim.math
_COS = [np.array([cos(2 * PI * k * s) for s in _SAMPLES]) for k in _HARMONICS]
_SIN = [np.array([sin(2 * PI * k * s) for s in _SAMPLES]) for k in _HARMONICS]


def fourier(params):
    """The curve the parameters describe, as two arrays (x, y) over the S samples.

    Works on floats and on duals: every sample accumulates the harmonics in a
    fixed order (`x += params[i] * c - params[M + i] * sn`)."""
    x = 0.0
    y = 0.0
    for i in range(M):
        c, sn = _COS[i], _SIN[i]
        x = x + (params[i] * c - params[M + i] * sn)
        y = y + (params[i] * sn + params[M + i] * c)
    return x, y


PREVIEW_T = 4.0


class GradientDescent(Scene):
    def construct(self):
        title = Text(
            "the shape is not scripted: it is descending a loss",
            size=0.42,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.3)
        self.add(title)

        target = star_target()

        def loss(p):
            xs, ys = fourier(p)
            # squares summed in a fixed order: every x term, then every y term
            return dual_sum(abs2(xs - target[:, 0]), abs2(ys - target[:, 1])) / S

        ghost = VMobject()
        ghost.set_points_as_corners([(target[j, 0], target[j, 1], 0) for j in [*range(S), 0]])
        ghost.set_stroke(color="#3A4558", width=2.0)
        self.add(ghost)

        params = np.zeros(2 * M)
        params[K + 1] = 1.0                       # start: the unit circle
        curve = VMobject()
        curve.set_stroke(color="#FFD25E", width=4.0)   # final style at birth
        running = False

        def descend(m, dt):
            if running and dt > 0:
                for _ in range(2):                # two steps per frame
                    params[:] = params - 0.35 * gradient(loss, params)
            xs, ys = fourier(params)
            m.set_points_as_corners([(xs[j], ys[j], 0) for j in [*range(S), 0]])

        curve.add_updater(descend)
        self.add(curve)

        readout = DecimalNumber(
            loss(params),
            num_decimal_places=5,
            size=0.5,
            color="#FFD25E",
        )
        readout.move_to((4.6, 2.2, 0))
        readout.add_updater(lambda d: d.set_value(loss(params)))
        caption = Text("loss", size=0.34, color=GREY_C)
        caption.move_to((4.6, 2.7, 0))
        self.add(readout, caption)

        self.wait(0.6)
        running = True
        self.wait(6.0)
        running = False
        print("final loss: ", round(loss(params), 6), sep="")
        self.wait(0.6)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    GradientDescent(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
