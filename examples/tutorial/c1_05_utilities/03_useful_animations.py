"""Course 1 · 5.3 — The animations you reach for constantly

Emphasis — "look HERE". None of them is a new mechanism; each is composition
over Transform / ShowCreation / rate functions, which is the test that the
primitives were the right ones:

    Indicate(m, scale_factor=…, color=…)    grow and tint, and come back
    Flash(point_or_mobject, num_lines=…)    the radial burst
    Circumscribe(m, shape="rectangle")      draw a box round it, rub it out
    FocusOn(target, opacity=…)              the camera-iris gesture
    Wiggle(m, n_wiggles=…)                  shake without moving anything

Appearing and disappearing:

    Write(m) / Unwrite(m)                   for text and formulas
    DrawBorderThenFill(m)                   outline first, then the fill rises
    ShowCreation(m) / Uncreate(m)           the stroke draws / retreats
    GrowFromCenter/Point/Edge · GrowArrow · SpinInFromNothing · ShrinkToCenter

And the two escape valves, for when nothing above fits:

    UpdateFromAlphaFunc(m, lambda m, a: …)  whatever you can write as a function
                                            of α. It takes NO snapshot, which
                                            is what lets it drive a Surface or
                                            a type of your own.
    UpdateFromFunc(m, lambda m: …)          no α: for a mobject that depends on
                                            another one being animated now.

Detail worth having: `Uncreate` and `Unwrite` hand the mobject back INTACT.
Manim leaves the collapsed husk behind, so re-adding it later shows nothing
and the bug looks like the renderer's.

    python examples/tutorial/c1_05_utilities/03_useful_animations.py
"""

from pathlib import Path

from janim import *
from janim.math import sin

PREVIEW_T = 3.4


def pulse_update(m, a):
    """The pulse nobody has a class for: rebuild the ring for every α."""
    s = sin(3 * PI * a)
    r = 0.35 + 0.55 * (s * s)
    c = Circle(radius=r)
    c.set_stroke(
        color="#C77DFF",
        width=4.0,
        opacity=1 - 0.6 * a,
    )
    c.set_fill(opacity=0)
    c.move_to(3.0 * RIGHT + 1.4 * DOWN)
    m.become(c)


class UsefulAnimations(Scene):
    def construct(self):
        title = Text(
            "emphasis is composition, not new machinery",
            size=0.44,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.35)
        self.add(title)

        targets = VGroup()
        for txt, colour in (
            ("Indicate", "#58C4DD"),
            ("Flash", "#FFD25E"),
            ("Circumscribe", "#7FDD58"),
            ("Wiggle", "#E8A33D"),
            ("FocusOn", "#FF5E5E"),
        ):
            t = Text(txt, size=0.42, color=colour)
            targets.add(t)
        targets.arrange(DOWN, buff=0.45)
        targets.move_to(3.4 * LEFT + 0.3 * DOWN)
        self.add(targets)
        self.play(FadeIn(targets), run_time=0.6)

        self.play(Indicate(targets[0]), run_time=0.9)
        self.play(
            Flash(
                targets[1],
                flash_radius=0.9,
                num_lines=16,
            ),
            run_time=0.9,
        )
        self.play(Circumscribe(targets[2], buff=0.15), run_time=1.0)
        self.play(Wiggle(targets[3]), run_time=1.2)
        self.play(FocusOn(targets[4]), run_time=1.2)

        # The appearance family, on the right.
        shapes = VGroup()
        for m in (
            Square(side_length=0.9),
            Circle(radius=0.5),
            Triangle(radius=0.6),
            Star(6, outer_radius=0.55),
        ):
            m.set_fill(color="#2C5F8A", opacity=1.0)
            m.set_stroke(color="#58C4DD", width=3.0)
            shapes.add(m)
        shapes.arrange(RIGHT, buff=0.5)
        shapes.move_to(3.0 * RIGHT + 1.4 * UP)

        self.play(
            LaggedStart(
                GrowFromCenter(shapes[0]),
                DrawBorderThenFill(shapes[1]),
                SpinInFromNothing(shapes[2]),
                ShowCreation(shapes[3]),
                lag_ratio=0.35,
            ),
            run_time=2.4,
        )

        # The escape valve: a pulse nobody has a class for.
        pulse = Circle(radius=0.8)
        pulse.set_stroke(color="#C77DFF", width=4.0)
        pulse.set_fill(opacity=0)
        pulse.move_to(3.0 * RIGHT + 1.4 * DOWN)
        self.add(pulse)
        self.play(UpdateFromAlphaFunc(pulse, pulse_update), run_time=2.0)
        self.wait(0.4)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    UsefulAnimations(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
