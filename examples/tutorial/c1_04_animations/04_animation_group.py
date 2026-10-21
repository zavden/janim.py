"""Course 1 · 4.4 — Composing animations in time

    AnimationGroup(*anims, lag_ratio=0, run_time=-1)
    LaggedStart(*anims, lag_ratio=0.05)      # the same thing, named
    Succession(*anims)                       # lag_ratio = 1, and LAZY

The time algebra is one line:

    start[k+1] = interpolate(start[k], end[k], lag_ratio)

so lag 0 = all at once, lag 1 = strictly one after another, small lag = a
cascade. `run_time=-1` means "as long as the last one needs".

WHY `Succession` IS ITS OWN TYPE and not just lag_ratio = 1: it begins each
animation when its turn comes. `AnimationGroup` begins them ALL at the
start, and since `begin` is where an animation snapshots its endpoints,
chaining two animations over the SAME mobject in an AnimationGroup would
snapshot the second one's start before the first one had run.

    python examples/tutorial/c1_04_animations/04_animation_group.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 2.0


def bar(y, colour):
    """Six squares in a row at height `y`, in one colour."""
    group = VGroup()
    for k in range(6):
        square = Square(side_length=0.6)
        square.set_fill(colour, 1.0)
        square.set_stroke(opacity=0)
        square.move_to((-3.2 + 0.8 * k, y, 0))
        group.add(square)
    return group


def fades(group):
    return [FadeIn(square, shift=0.4 * DOWN) for square in group.submobjects]


class AnimationGroupLesson(Scene):
    def construct(self):
        title = Text(
            "start[k+1] = lerp(start[k], end[k], lag_ratio)",
            size=0.42,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.35)
        self.add(title)

        together = bar(1.6, "#58C4DD")
        lagged = bar(0.4, "#E8A33D")
        chained = bar(-0.8, "#7FDD58")
        for group, text, y in (
            (together, "AnimationGroup (lag 0)", 1.6),
            (lagged, "LaggedStart (lag 0.15)", 0.4),
            (chained, "Succession (lag 1)", -0.8),
        ):
            label = Text(text, size=0.3, color=GREY_B)
            label.move_to((4.6, y, 0))
            self.add(label)

        # The same six FadeIns, composed three ways, all in 2.4 s.
        self.play(
            AnimationGroup(
                AnimationGroup(*fades(together), lag_ratio=0.0),
                LaggedStart(*fades(lagged), lag_ratio=0.15),
                Succession(*fades(chained)),
            ),
            run_time=2.4,
        )
        self.wait(0.4)

        # Succession over ONE mobject, which is where its laziness earns its
        # keep: each step snapshots the state the previous step left behind.
        # `.animate` would not do here: the proxy is ManimGL's and builds its
        # target EAGERLY, so three `.animate` of one mobject share the last
        # target. `ApplyMethod` builds its copy inside `begin`.
        trav = Dot((-3.2, -2.2, 0), radius=0.18)
        trav.set_fill("#FF5E5E")
        self.add(trav)
        self.play(
            Succession(
                ApplyMethod(trav.shift, 3.0 * RIGHT),
                ApplyMethod(trav.shift, 1.2 * UP),
                ApplyMethod(trav.scale, 2.0),
            ),
            run_time=2.4,
        )
        print("the dot ended at", tuple(round(float(c), 2) for c in trav.get_center()))
        self.wait(0.4)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    AnimationGroupLesson(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
