"""Course 4 · 2.2 — A steady pen

`ShowCreation` (CE's `Create`) draws a path the way ManimGL's does: it hands
every CURVE of the path the same share of the time. A long straight run and a
tight rounded corner each take one curve's worth, so the pen dawdles through
the corner and rushes down the straight.

    ShowCreation(m)                    every curve the same time (GL, CE)
    ShowCreation(m, by_length=True)    the same speed along the whole path
    Uncreate(m, by_length=True)        the same, backwards

`by_length` works path by path: each path's arc length is sampled once when
the animation begins (16 samples per curve), and the jump from one subpath
to the next takes no time, because nothing is drawn there. Across the members
of a group, `lag_ratio` still decides who starts when.

The two hooks below are the same path, a long run up, a small rounded turn
and a run down, drawn with a stroke 30 pixels wide. Watch the turn: on the
left the pen slows down to go round it; on the right it keeps its pace, and
both reach the end together.

Watch the moving end too. A path being drawn keeps all its points, the
undrawn curves collapsed onto the moving end (as in ManimGL), and that end
used to turn a corner that is not there: a thick stroke grew a slanted spike
at its tip. A segment with no length makes no turn, so the tip is cut square
at every frame.

    python examples/tutorial/c4_02_animation_zoo/02_steady_pen.py
"""

from pathlib import Path

import numpy as np

from janim import *

PREVIEW_T = 1.2


def hook():
    """Up 4, a rounded turn of radius 0.3, down 1.5."""
    path = VMobject()
    path.start_new_path(np.array((0.0, -2.0, 0.0)))
    path.add_line_to(np.array((0.0, 2.0, 0.0)))
    turn = Arc(
        radius=0.3,
        start_angle=PI,
        angle=-PI,
        arc_center=np.array((0.3, 2.0, 0.0)),
    )
    path.append_points(turn.points[1:])
    path.add_line_to(np.array((0.6, 0.5, 0.0)))
    path.set_fill(opacity=0)
    return path


class SteadyPen(Scene):
    def construct(self):
        title = Text("a steady pen", size=0.4, color=GREY_A)
        title.to_edge(UP, buff=0.25)
        self.add(title)

        by_curve = hook().set_stroke(BLUE_C, width=30).shift(3.0 * LEFT)
        by_length = hook().set_stroke(ORANGE, width=30).shift(2.4 * RIGHT)
        labels = VGroup(
            Text("by curve", size=0.32, color=BLUE_C),
            Text("by_length=True", size=0.32, color=ORANGE),
        )
        labels[0].next_to(by_curve, DOWN, buff=0.3)
        labels[1].next_to(by_length, DOWN, buff=0.3)
        self.add(labels)

        self.play(
            ShowCreation(by_curve, rate_func=linear),
            ShowCreation(by_length, by_length=True, rate_func=linear),
            run_time=3.0,
        )
        self.wait(0.5)
        self.play(
            Uncreate(by_curve, rate_func=linear),
            Uncreate(by_length, by_length=True, rate_func=linear),
            run_time=2.0,
        )
        self.wait(0.3)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    SteadyPen(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
