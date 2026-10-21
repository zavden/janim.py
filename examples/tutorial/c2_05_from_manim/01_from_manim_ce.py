"""Course 2 · 5.1 — Translating a Manim CE scene

The CE original, line for line, is in the comments. Janim speaks Manim's
syntax, so most of the CE lines survive untouched; what is left is where CE
and this engine still disagree:

  1. `self.play(m.animate.shift(RIGHT).set_color(YELLOW))` works as in CE —
     one chainable proxy, the calls applied in order to a target built
     eagerly (ManimGL's builder).
  2. Colours and opacities read as in CE: `m.set_fill(BLUE, opacity=0.5)`.
  3. `Text` is FreeType text (no Pango), and `Tex`/`MathTex` run LaTeX —
     the only typesetting route.
  4. `config.frame_rate`, `manim.cfg` and `-ql` do not exist. Settings are
     `Scene` kwargs (`fps=`, `resolution=`), and the CLI has its own flags
     (course 1, lesson 2.2).
  5. `VGroup(*mobs)` and list comprehensions are the same Python as in CE.

    python examples/tutorial/c2_05_from_manim/01_from_manim_ce.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 2.6


class FromManimCE(Scene):
    def construct(self):
        # ── CE ──────────────────────────────────────────────────────────────
        # title = Text("From Manim CE", font_size=48).to_edge(UP)
        title = Text("From Manim CE", size=0.6)
        title.to_edge(UP, buff=0.4)
        self.add(title)

        # circle = Circle().set_fill(BLUE, opacity=0.5)
        circle = Circle(radius=1.2)
        circle.set_fill(BLUE, opacity=0.5)
        circle.set_stroke(BLUE, width=4.0)

        # square = Square().rotate(PI / 4).shift(3 * LEFT)
        square = Square(side_length=2.0)
        square.rotate(PI / 4)
        square.shift(3.4 * LEFT)
        square.set_fill("#E8A33D", opacity=0.7)
        square.set_stroke("#E8A33D", width=4.0)

        # dots = VGroup(*[Dot(RIGHT * i) for i in range(5)]).arrange(RIGHT, buff=0.4)
        dots = VGroup(*[Dot(ORIGIN, radius=0.13).set_fill("#7FDD58") for _ in range(5)])
        dots.arrange(RIGHT, buff=0.4)
        dots.move_to(3.4 * RIGHT)

        # self.play(Create(square), FadeIn(circle))
        self.play(
            AnimationGroup(
                Create(square),
                FadeIn(circle),
            ),
            run_time=1.2,
        )

        # self.play(LaggedStart(*[GrowFromCenter(d) for d in dots], lag_ratio=0.2))
        self.play(
            LaggedStart(
                *[GrowFromCenter(d) for d in dots.submobjects],
                lag_ratio=0.2,
            ),
            run_time=1.2,
        )

        # self.play(square.animate.shift(UP).set_color(YELLOW))
        #   ← two mutations, one animation: literal here
        self.play(square.animate.shift(1.0 * UP).set_color(YELLOW), run_time=1.0)

        # self.play(Transform(square, circle))
        self.play(Transform(square, circle), run_time=1.2)

        # self.wait()
        self.wait(1.0)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    FromManimCE(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
