"""Course 1 · 1.4 — Animation properties

Every animation carries the same four dials (they live in `Animation`):

    run_time    seconds. `self.play(…, run_time=t)` overrides it.
    rate_func   how α moves inside that time (lesson 4.1).
    lag_ratio   the delay between the members of the animated mobject's
                FAMILY: 0 = all together, 1 = strictly one after another.
    remover     when true, the scene drops the mobject at the end (FadeOut).

`lag_ratio` is the one people get wrong. On a single animation it staggers
the CHILDREN of the mobject being animated. On an `AnimationGroup` it
staggers the ANIMATIONS. Same word, two levels — both appear below.

Second thing this lesson teaches: `.animate` is Manim's proxy. It records
each chained method call with its own arguments, keywords included, so
`row.animate(lag_ratio=lag).set_color(YELLOW)` needs no adapter at all.

    python examples/tutorial/c1_01_basics/04_animation_properties.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.6


def row(y):
    """A row of six dots at height `y`. Narrow on purpose: the animation below
    scales the row by 1.5 about its own centre, and the labels live at x = 4.6."""
    group = VGroup()
    for k in range(6):
        dot = Dot((-3.6 + 1.0 * k, y, 0), radius=0.2)
        dot.set_fill("#37506B")
        group.add(dot)
    return group


class AnimationProperties(Scene):
    def construct(self):
        title = Text("lag_ratio staggers a family", size=0.5, color=GREY_A)
        title.to_edge(UP, buff=0.4)
        self.add(title)

        rows = [row(1.5), row(0.0), row(-1.5)]
        lags = [0.0, 0.15, 1.0]
        for group, lag, y in zip(rows, lags, (1.5, 0.0, -1.5)):
            label = Text(f"lag_ratio = {lag}", size=0.33, color=GREY_B)
            label.move_to((4.6, y, 0))
            self.add(group, label)

        # The three rows animate for the SAME 3 seconds. Only the lag differs,
        # so what you are looking at is purely what lag_ratio does.
        self.play(
            AnimationGroup(
                *(
                    group.animate(lag_ratio=lag).set_color(YELLOW).scale(1.5)
                    for group, lag in zip(rows, lags)
                ),
            ),
            run_time=3.0,
        )
        self.wait(0.4)

        # `remover`: FadeOut sets it, so the scene lets go of the mobject.
        # Compare `Uncreate`, which also hands the mobject back INTACT rather
        # than as the collapsed husk Manim leaves behind.
        self.play(
            AnimationGroup(
                *(FadeOut(group) for group in rows),
                lag_ratio=0.2,
            ),
            run_time=1.2,
        )
        print(
            "rows still in the scene:",
            sum(any(m is group for group in rows) for m in self.mobjects),
            "of 3",
        )


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    AnimationProperties(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
