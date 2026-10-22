"""Course 2 · 2.2 — A custom animation worth keeping

`TraceGraph`: draw a curve while a dot rides it and a readout follows. Manim
needs three coordinated animations plus an updater for this; here it is one
object with one α, which means one `run_time`, one `rate_func`, and no way
for the three parts to drift apart.

The lesson inside the lesson: an animation may drive SEVERAL mobjects. Its
`mobject` is the one the scene adds and removes — so make that a group
containing everything the animation touches, exactly as `AnimationGroup`
does.

    python examples/tutorial/c2_02_custom_animations/02_a_real_one.py
"""

from pathlib import Path

import numpy as np

from janim import *
from janim.math import exp, linear_range, sin


class TraceGraph(Animation):
    """Draw the graph of `f` over `ax` from left to right, keeping `dot` on the pen
    and `readout` showing the current y. One animation, one α, no drift."""

    def __init__(
        self,
        ax,
        f,
        graph,
        dot,
        readout,
        x_range=None,
        **kwargs,
    ):
        if x_range is None:
            x0, x1 = ax.x_axis.x_min, ax.x_axis.x_max
        else:
            x0, x1 = float(x_range[0]), float(x_range[1])
        group = Group(graph, dot, readout)      # one Group holding all three parts
        super().__init__(group, **kwargs)
        self.ax, self.f = ax, f
        self.graph, self.dot, self.readout = graph, dot, readout
        self.x0, self.x1 = x0, x1

    def begin(self):
        # Nothing to snapshot here — the graph is rebuilt from f every frame — so
        # `begin` only has to put the animation at α = 0.
        self.interpolate(0.0)
        return self

    def interpolate(self, alpha):
        a = self.rate_func(min(max(alpha, 0), 1))
        x = self.x0 + a * (self.x1 - self.x0)
        if a <= 0:
            # a degenerate path still needs points, or the renderer has nothing
            p = self.ax.coords_to_point(self.x0, self.f(self.x0))
            self.graph.set_points(np.array([p, p, p], dtype=np.float32))
        else:
            n = max(3, round(160 * a))
            self.graph.set_points_as_corners(
                [self.ax.coords_to_point(xi, self.f(xi)) for xi in linear_range(self.x0, x, n)],
            )
        self.dot.move_to(self.ax.coords_to_point(x, self.f(x)))
        self.readout.set_value(self.f(x))
        self.readout.move_to(
            self.ax.coords_to_point(x, self.f(x)) + np.array((0.55, 0.4, 0), dtype=np.float32),
        )
        return self


PREVIEW_T = 2.2


class ARealOne(Scene):
    def construct(self):
        title = Text(
            "one animation, three mobjects, one alpha",
            size=0.44,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.35)
        self.add(title)

        ax = Axes(
            (-4.0, 4.0, 1.0),
            (-2.0, 2.0, 1.0),
            width=9.0,
            height=4.0,
            include_numbers=True,
            num_decimal_places=0,
            numbers_to_exclude=[0.0],
            color="#37506B",
            stroke_width=2.0,
            label_size=0.3,
        )
        ax.move_to(0.4 * DOWN)
        self.add(ax)

        # `sin` and `exp` come from janim.math (Julia Base's math
        # functions); `x^2` is `x * x`.
        def f(x):
            return 1.5 * sin(1.6 * x) * exp(-0.12 * (x * x))

        graph = VMobject()
        graph.set_stroke(color="#58C4DD", width=4.0)   # born with its style
        graph.set_fill(opacity=0)
        dot = Dot(ORIGIN, radius=0.12)
        dot.set_fill(color="#FFD25E")
        readout = DecimalNumber(
            0.0,
            num_decimal_places=2,
            size=0.45,
            color="#FFD25E",
        )

        self.play(
            TraceGraph(
                ax,
                f,
                graph,
                dot,
                readout,
                rate_func=ease_in_out_sine,
            ),
            run_time=3.5,
        )
        self.wait(0.4)

        # Because it is an ordinary Animation, it composes: run it backwards by
        # inverting the rate function, and the three parts still agree.
        self.play(
            TraceGraph(
                ax,
                f,
                graph,
                dot,
                readout,
                rate_func=lambda t: 1 - smooth(t),
            ),
            run_time=1.6,
        )
        print("graph anchors at the end: ", (graph.get_num_points() + 1) // 2, sep="")


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    ARealOne(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
