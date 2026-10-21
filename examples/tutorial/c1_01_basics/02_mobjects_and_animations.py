"""Course 1 · 1.2 — Mobjects and animations

A MOBJECT is geometry plus style; it does not know about time. An ANIMATION
is a function of α ∈ [0,1] that mutates a mobject; it does not know about the
scene. `self.play` is the only thing that knows about both.

Two ways in, and the difference matters:

    self.add(m)              m is on screen from now on, unanimated
    self.play(FadeIn(m))     m is put on screen BY the animation

`play` adds the animation's mobject for you, so the second form needs no
`add`. And a "remover" (FadeOut, Uncreate, Unwrite) takes it back out.

    python examples/tutorial/c1_01_basics/02_mobjects_and_animations.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 3.2


class MobjectsAndAnimations(Scene):
    def construct(self):
        label = Text("mobject = geometry + style", size=0.5, color=GREY_A)
        label.to_edge(UP, buff=0.5)
        self.add(label)                          # on screen, no animation

        circle = Circle(radius=1.1)
        circle.set_fill(BLUE, 1.0)
        circle.set_stroke(WHITE, width=4.0)
        circle.shift(3.2 * LEFT)

        square = Square(side_length=2.0)
        square.set_fill("#E8A33D", 1.0)
        square.set_stroke(opacity=0)

        triangle = Triangle(radius=1.3)
        triangle.set_fill(GREEN, 1.0)
        triangle.set_stroke(opacity=0)
        triangle.shift(3.2 * RIGHT)

        # 1. ShowCreation draws the outline as if by hand.
        self.play(ShowCreation(circle), run_time=1.0)

        # 2. FadeIn: no `add` needed — `play` puts the mobject in the scene.
        self.play(FadeIn(square, shift=0.6 * UP), run_time=0.8)

        # 3. Transform morphs one shape into another. It leaves you holding
        #    `square`, now wearing the triangle's shape — see lesson 1.5.
        self.play(Transform(square, triangle), run_time=1.2)

        # 4. wait is not "nothing happens": it is frames of scene time, and
        #    updaters keep running during it (lesson 6.3).
        self.wait(0.6)

        # 5. FadeOut is a REMOVER: when it ends, the scene no longer holds it.
        self.play(FadeOut(square), run_time=0.8)
        # `self.mobjects` also holds the camera frame, as in ManimGL, so this
        # prints 3.
        print("mobjects left in the scene:", len(self.mobjects))
        self.wait(0.4)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    MobjectsAndAnimations(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
