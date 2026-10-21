"""Course 1 · 3.2 — Comprehensions

Manim tutorials teach Python list comprehensions here, and they are exactly
what Janim uses. They compose with the splat `*`, which is what turns a
list of mobjects into a VGroup and a list of animations into a LaggedStart:

    VGroup(*(Dot(p) for p in points))
    LaggedStart(*(FadeIn(d) for d in g.submobjects), lag_ratio=0.1)

Two things worth knowing:

  · A nested comprehension gives a list of ROWS, `[[f(i, j) for j in …] for
    i in …]` — the shape `Table` and `Matrix` take as it stands.
  · Float ranges like 0, 0.05, …, TAU are best sampled in twice the
    precision, so their samples are not `start + k·step` rounded step by
    step. `step_range(start, stop, step)` does exactly that; this lesson
    uses it wherever it needs a range.

    python examples/tutorial/c1_03_groups_and_text/02_comprehensions.py
"""

import math
from pathlib import Path

from janim import *
from janim.core._ranges import step_range

PREVIEW_T = 2.4


class Comprehensions(Scene):
    def construct(self):
        title = Text("build many, animate as one", size=0.5, color=GREY_A)
        title.to_edge(UP, buff=0.4)
        self.add(title)

        # A curve as a comprehension over a range — the samples ARE the geometry.
        curve = VMobject()
        curve.set_points_as_corners(
            [(t, 1.3 * math.sin(1.5 * t), 0) for t in step_range(-6.0, 6.0, 0.1)],
        )
        curve.set_stroke("#37506B", width=3.0)
        curve.shift(1.1 * UP)

        # Dots ON that curve: one comprehension, splatted into a VGroup.
        def dot_at(t):
            dot = Dot((t, 1.3 * math.sin(1.5 * t) + 1.1, 0), radius=0.1)
            dot.set_fill("#58C4DD")
            return dot

        dots = VGroup(*(dot_at(t) for t in step_range(-6.0, 6.0, 0.6)))

        # A grid: the nested comprehension gives the rows, which is exactly
        # what `Table` wants.
        grid = Table(
            [[str(i * j) for j in range(1, 5)] for i in range(1, 4)],
            cell=lambda s: Text(s, size=0.42),
            row_labels=["1", "2", "3"],
            col_labels=["1", "2", "3", "4"],
            include_outer_lines=True,
        )
        grid.scale(0.75)
        grid.move_to(1.6 * DOWN)

        self.add(curve, dots, grid)
        self.play(ShowCreation(curve), run_time=1.0)

        # A list of ANIMATIONS, splatted. lag_ratio turns it into a wave.
        self.play(
            LaggedStart(
                *(FadeIn(dot, shift=0.35 * UP) for dot in dots.submobjects),
                lag_ratio=0.07,
            ),
            run_time=1.6,
        )
        self.play(
            LaggedStart(
                *(Write(entry) for entry in grid.get_entries().submobjects),
                lag_ratio=0.05,
            ),
            run_time=1.6,
        )
        self.wait(0.4)
        print(f"dots: {len(dots.submobjects)} · table cells: {len(grid.get_entries().submobjects)}")


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    Comprehensions(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
