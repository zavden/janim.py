"""Course 1 · 6.1 — 2D plots

    Axes(x_range, y_range, width=…, height=…, include_numbers=…)
    NumberLine(x_range, width=…, unit_size=…, include_numbers=…, …)
    NumberPlane(x_range, y_range, …)   ComplexPlane   PolarPlane

    ax.c2p(x, y) / coords_to_point      data  → scene point
    ax.p2c(point) / point_to_coords     point → data
    ax.plot(f, x_range=…, n=…, color=…, discontinuities=…)
    ax.update_graph(graph, f)           re-sample IN PLACE (the hot loop)
    ax.get_area(f, x0, x1) · get_graph_label · get_v_line · get_h_line

THE DESIGN DECISION, and everything else follows from it: the map is DERIVED
FROM THE LIVE GEOMETRY, never stored as numbers. `number_to_point` reads the
axis line's CURRENT endpoints, so `ax.shift(2 * RIGHT)`, `ax.scale(0.5)`
and even `ax.rotate(…)` move the whole coordinate world coherently — with no
invalidation logic and nothing to keep in sync.

`get_area` is worth a look too: it is the EXACT polygon under the curve,
closed along the axis. Manim approximates it with a stack of rectangles
because its fill cannot be trusted on a self-touching outline; ours is
filled by real winding, so the exact polygon just works.

    python examples/tutorial/c1_06_plots_and_updaters/01_plots_2d.py
"""

from pathlib import Path

from janim import *
from janim.math import sin, step_range

PREVIEW_T = 5.0


class Plots2D(Scene):
    def construct(self):
        title = Text(
            "the map is read off the geometry",
            size=0.44,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.3)
        self.add(title)

        # Two details about the labels, both worth stealing:
        #   · pick a range whose TICKS are the numbers you want printed. With
        #     `(-3.5, 3.5, 1)` the ticks are -3.5, -2.5, … and at 0 decimals both
        #     -0.5 and 0.5 print "0" — two zeros, side by side.
        #   · `numbers_to_exclude=[0]` drops the origin label, which the two
        #     axes would otherwise write on top of each other.
        ax = Axes(
            (-4.0, 4.0, 1.0),
            (-1.0, 1.0, 0.5),
            width=7.4,
            height=3.4,
            include_numbers=True,
            color="#37506B",
            stroke_width=2.0,
            label_size=0.3,
            num_decimal_places=1,
            numbers_to_exclude=[0.0],
        )
        ax.move_to(2.6 * LEFT + 0.4 * DOWN)

        # `sin` comes from janim.math (Julia Base's math
        # functions), so the samples are the same on any machine.
        sine = ax.plot(sin, color="#58C4DD", stroke_width=4.0)
        area = ax.get_area(
            sin,
            0.0,
            PI,
            color="#58C4DD",
            opacity=0.3,
        )
        label = ax.get_graph_label(
            sine,
            "sin x",
            x=1.6,
            direction=UP,
            size=0.4,
            color="#58C4DD",
        )

        # A discontinuous function: the cut makes it two subpaths instead of the
        # vertical stroke a naive sampler draws across the jump.
        def step_fn(x):
            return -1.0 if x < 0 else 1.0

        steps = ax.plot(
            step_fn,
            x_range=(-2.4, 2.4),
            color="#FF5E5E",
            stroke_width=3.0,
            discontinuities=[0.0],
        )

        marker = Dot(ax.c2p(1.0, sin(1.0)), radius=0.09)
        marker.set_fill(color=YELLOW)
        vline = ax.get_v_line(1.0, sin(1.0), color=YELLOW)

        # TWO things about this `add`.
        #
        # `ax` straight in: a coordinate object HAS a group of VMobjects and
        # delegates the whole scene interface to it — including
        # `set_stroke`/`set_fill`, which is what the fade animations call on
        # their copy. So `FadeIn(ax)` just works. One rule still stands: add the
        # SAME object you animate — adding both `ax` and one of its axes would
        # give the scene two roots over one family and draw it twice.
        #
        # And note what is NOT here: `sine`, `area`, `label`, `steps` and `spiral`
        # are brought in by their own animations. `play` adds the animation's
        # mobject for you, so adding it first only makes it visible BEFORE it is
        # created — the classic "why is it already there" in Manim too.
        self.add(ax, vline, marker)

        # A polar grid, to show the family is bigger than Axes.
        polar = PolarPlane(
            r_max=3.0,
            radius=1.55,
            n_radii=12,
            n_circles=3,
            color="#37506B",
        )
        polar.move_to(4.6 * RIGHT + 0.5 * DOWN)
        # `polar_to_point` reads the LIVE θ=0 radius, exactly like `c2p` reads
        # its axes. The plane was just moved: the spiral lands on it with no
        # bookkeeping. Every coordinate object answers `get_center`/`get_width`/…
        # by delegation. `step_range` samples the range in twice the precision.
        spiral = VMobject()
        spiral.set_points_as_corners(
            [polar.polar_to_point(theta, 0.45 * theta) for theta in step_range(0, TAU, 0.05)],
        )
        spiral.set_stroke(color="#FFD25E", width=3.0)
        self.add(polar)

        print("c2p(1, sin 1) = ", tuple(round(float(v), 3) for v in ax.c2p(1.0, sin(1.0))), sep="")
        print(
            "p2c of that point = ",
            tuple(round(float(v), 6) for v in ax.p2c(ax.c2p(1.0, sin(1.0)))),
            sep="",
        )

        self.play(
            AnimationGroup(
                FadeIn(ax),
                FadeIn(polar),
                lag_ratio=0.2,
            ),
            run_time=1.0,
        )
        self.play(ShowCreation(sine), run_time=1.2)
        self.play(
            AnimationGroup(
                FadeIn(area),
                Write(label),
            ),
            run_time=0.8,
        )
        self.play(ShowCreation(steps), run_time=0.8)
        self.play(ShowCreation(spiral), run_time=1.2)

        # The whole coordinate world moves as one, map included: the marker is
        # re-placed through c2p AFTER the axes have moved, and it lands right.
        self.play(ax.animate.shift(0.5 * UP).scale(0.9), run_time=1.2)
        marker.move_to(ax.c2p(1.0, sin(1.0)))
        self.wait(0.5)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    Plots2D(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
