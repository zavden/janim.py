"""Course 1 · 4.1 — Rate functions

A rate function reshapes α: the animation still runs from 0 to 1 over its
run_time, but WHERE it is at each instant is `rate_func(α)`. It is a
property of the ANIMATION, never of `self.play`.

    self.play(m.animate(rate_func=there_and_back).shift(2 * RIGHT))

The default is `smooth`, and ours is ManimGL's quintic
`t³(10(1−t)² + 5(1−t)t + t²)` — polynomial, exactly 0 and 1 at the ends,
zero first and second derivative at both. NOT Manim CE's rescaled sigmoid,
which is a different curve.

The family: linear · smooth · rush_into · rush_from · slow_into ·
double_smooth · there_and_back(_with_pause) · running_start · overshoot ·
not_quite_there · wiggle · lingering · exponential_decay ·
squish_rate_func(f, a, b) — plus the whole easings.net set,
ease_{in,out,in_out}_{sine,quad,cubic,quart,quint,expo,circ,back,elastic,
bounce}.

`squish_rate_func(f, a, b)` compresses `f` into a window and holds it
outside: it is how Flash and Circumscribe fit "draw, then rub out" into one
gesture, and it is worth knowing early.

    python examples/tutorial/c1_04_animations/01_rate_functions.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.8

SHOWN = [
    (linear, "linear", "#8894A6"),
    (smooth, "smooth", "#58C4DD"),
    (rush_into, "rush_into", "#7FDD58"),
    (there_and_back, "there_and_back", "#E8A33D"),
    (ease_out_bounce, "ease_out_bounce", "#FF5E5E"),
    (overshoot, "overshoot", "#C77DFF"),
]


class RateFunctions(Scene):
    def construct(self):
        title = Text(
            "rate_func reshapes alpha, not the clock",
            size=0.46,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.35)
        self.add(title)

        # Left: the curves themselves, α on x and rate_func(α) on y.
        # Style goes in the CONSTRUCTOR here: a coordinate object delegates
        # `set_color` but not `set_stroke`/`set_fill` (an Axes HAS a group of
        # VMobjects, it is not one).
        ax = Axes(
            (0.0, 1.0, 0.5),
            (-0.4, 1.4, 0.5),
            width=4.4,
            height=3.0,
            color="#37506B",
            stroke_width=2.0,
        )
        ax.move_to(3.6 * LEFT + 0.4 * DOWN)
        self.add(ax)

        # Right: a dot per rate function, all crossing the same track at once.
        track_x0, track_x1 = -0.6, 5.4
        runners = VGroup()
        for k, (f, name, colour) in enumerate(SHOWN, start=1):
            y = 2.0 - 0.75 * k
            rail = Line((track_x0, y, 0), (track_x1, y, 0))
            rail.set_stroke("#1E2A38", width=6.0)
            dot = Dot((track_x0, y, 0), radius=0.14)
            dot.set_fill(colour)
            label = Text(name, size=0.28, color=colour)
            label.move_to((track_x1 + 0.05, y + 0.3, 0))
            self.add(rail, label, dot)
            runners.add(dot)

            graph = ax.plot(
                f,
                x_range=(0.0, 1.0),
                n=80,
                color=colour,
                stroke_width=2.5,
            )
            self.add(graph)

        # One AnimationGroup, one run_time: every difference you see is the curve.
        self.play(
            AnimationGroup(
                *(
                    dot.animate(rate_func=f).shift((track_x1 - track_x0, 0, 0))
                    for dot, (f, _, _) in zip(runners.submobjects, SHOWN)
                ),
            ),
            run_time=3.0,
        )
        self.wait(0.5)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    RateFunctions(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
