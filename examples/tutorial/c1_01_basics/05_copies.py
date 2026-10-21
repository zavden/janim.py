"""Course 1 · 1.5 — Copies

`m.copy()` is DEEP: points, style rows and the whole subtree. Two copies
share nothing, so mutating one never reaches the other. (The single
exception is documented and deliberate: an `ImageMobject`'s pixel array is
shared, because a texture can be megabytes and it is treated as immutable.)

Where copies show up whether you ask for them or not:

    Transform(a, b)          builds a copy of `b` in `begin` and morphs `a`
                             into it — `b` is never mutated, and afterwards
                             the scene still holds `a`, wearing b's shape.
    ReplacementTransform     …but the scene ends up holding `b` instead.
    TransformFromCopy(a, b)  `a` stays put; a copy of it flies to `b`.
    m.animate.f(x)           the target is `f` applied to a copy of `m`.

The trap: adding the SAME mobject to the scene twice draws it twice, and
with winding fill the overlap deepens instead of staying put. If you want
two of something, copy it.

    python examples/tutorial/c1_01_basics/05_copies.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 2.6


class Copies(Scene):
    def construct(self):
        title = Text(
            "copy is deep — Transform never mutates its target",
            size=0.48,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.4)
        self.add(title)

        source = Square(side_length=1.6)
        source.set_fill(BLUE, 1.0)
        source.set_stroke(opacity=0)
        source.move_to(4.2 * LEFT)

        target = Circle(radius=0.95)
        target.set_fill("#E8A33D", 1.0)
        target.set_stroke(opacity=0)
        target.move_to(4.2 * RIGHT)

        for mob, text in ((source, "source"), (target, "target")):
            label = Text(text, size=0.35, color=GREY_B)
            label.next_to(mob, DOWN, buff=0.3)
            self.add(label)
        self.add(source, target)

        # A copy is an independent mobject: painting it leaves the original alone.
        twin = source.copy()
        twin.set_fill(GREEN)
        twin.move_to(1.6 * LEFT)
        self.play(FadeIn(twin), run_time=0.6)
        print("source fill after painting the copy:", source.get_color())

        # TransformFromCopy: the source survives, the copy is what flies. The
        # scene keeps the TARGET afterwards (the copy is scaffolding).
        self.play(TransformFromCopy(source, target), run_time=1.6)
        self.wait(0.4)

        # Plain Transform consumes what you hand it: `twin` is now
        # circle-shaped and sits where the circle is, and you are still
        # holding `twin`.
        circle_2 = Circle(radius=0.6)
        circle_2.set_fill(GREEN, 1.0)
        circle_2.set_stroke(opacity=0)
        circle_2.move_to(1.6 * RIGHT)
        self.play(Transform(twin, circle_2), run_time=1.2)
        print(
            f"twin is a {type(twin).__name__} that now looks like a {type(circle_2).__name__}"
            " — its class never changes, only its points",
        )
        self.wait(0.5)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    Copies(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
