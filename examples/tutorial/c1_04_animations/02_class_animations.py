"""Course 1 · 4.2 — Animations as objects

An animation is a VALUE. You build it, you can hold it, pass it around, put
it inside a group, and hand it to `self.play` later — it does not run until
something drives its three-act life cycle:

    a.begin()                   snapshot the start, align the structures, α=0
    a.interpolate(α) × N        the rate function is applied INSIDE
    a.finish()                  exact α=1 and cleanup

`play` makes exactly those three calls. So do `render_frame` and the live
window — which is why an animation never needs to know who is driving it.

Everything with a capital letter in this list is one of these values:

    Transform · ReplacementTransform · TransformFromCopy · FadeTransform
    FadeIn · FadeOut · ShowCreation/Create · Uncreate
    Write · Unwrite · DrawBorderThenFill
    GrowFromCenter/Point/Edge · GrowArrow · SpinInFromNothing · ShrinkToCenter
    Rotate · Rotating · MoveAlongPath
    Indicate · Flash · Circumscribe · FocusOn · Wiggle
    AnimationGroup · Succession · LaggedStart · TransformMatchingTex
    UpdateFromAlphaFunc · UpdateFromFunc      ← the escape valves

Two of them are worth singling out. `Transform` snapshots BOTH ends inside
`begin`, not when you build it — which is what makes chaining inside a
`Succession` capture the right states. And `Rotating` is not a Transform:
interpolating between two rotated states moves points along CHORDS, so a
half-turned square would visibly shrink; `Rotating` re-applies the rotation
to the start state each frame instead.

    python examples/tutorial/c1_04_animations/02_class_animations.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 3.0


class ClassAnimations(Scene):
    def construct(self):
        title = Text(
            "an animation is a value you build",
            size=0.46,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.35)
        self.add(title)

        square = Square(side_length=1.4)
        square.set_fill("#2C5F8A", 1.0)
        square.set_stroke(opacity=0)
        square.move_to(4.0 * LEFT + 0.8 * UP)

        ring = Circle(radius=0.75)
        ring.set_stroke("#58C4DD", width=5.0)
        ring.set_fill(opacity=0)
        ring.move_to(1.3 * LEFT + 0.8 * UP)

        star = Star(5, outer_radius=0.9)
        star.set_fill("#FFD25E", 1.0)
        star.set_stroke(opacity=0)
        star.move_to(1.5 * RIGHT + 0.8 * UP)

        arrow = Arrow((3.2, 0.2, 0), (5.2, 1.4, 0))
        arrow.set_fill("#7FDD58")

        # Build them all first — nothing has happened yet.
        plan = [
            ShowCreation(ring),
            GrowFromCenter(star),
            GrowArrow(arrow),
            FadeIn(square, shift=0.5 * DOWN),
        ]
        print(
            f"built {len(plan)} animations, total run_time ="
            f" {sum(a.get_run_time() for a in plan)} s — none of them has run",
        )

        # …and now hand them over, one after another.
        for a in plan:
            self.play(a, run_time=0.7)

        # Rotating vs Transform, side by side: same half-turn, different paths.
        left = Square(side_length=1.2)
        left.set_fill("#E8A33D", 1.0)
        left.set_stroke(opacity=0)
        left.move_to(2.2 * LEFT + 1.7 * DOWN)
        right = left.copy()
        right.move_to(2.2 * RIGHT + 1.7 * DOWN)
        target = right.copy()
        target.rotate(PI)
        for mob, text in ((left, "Rotating (arcs)"), (right, "Transform (chords)")):
            label = Text(text, size=0.3, color=GREY_C)
            label.next_to(mob, DOWN, buff=0.3)
            self.add(label)
        self.add(left, right)
        self.play(
            AnimationGroup(
                Rotating(left, PI, run_time=2.0),
                Transform(right, target, run_time=2.0),
            ),
            run_time=2.0,
        )
        self.wait(0.4)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    ClassAnimations(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
