"""Course 1 · 3.4 — Formulas

    Tex(formula, size=1.0, color=WHITE, isolate=())

Janim has ONE typesetting route: real LaTeX + dvisvgm → SVG → VMobject,
cached by document.

THE STRUCTURE MATTERS, and it is not decoration: a `Tex` is a parent with no
points and ONE CHILD PER GLYPH. Two reasons, both learned the hard way:

  · with every glyph in a single VMobject, a Transform's intermediate blob
    flies over its neighbours and CANCELS their winding fill — the formula
    flickers;
  · `Transform` pairs child with child, i.e. glyph with glyph in reading
    order, instead of pairing subpaths sorted by length.

Consequence to remember: `pointwise_become_partial` is NOT recursive, so on
a Tex (a parent with no points of its own) it does nothing. The creation
animations walk the family themselves, which is why `Write(tex)` works.

    python examples/tutorial/c1_03_groups_and_text/04_latex.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 2.4


class Formulas(Scene):
    def construct(self):
        euler = Tex(r"e^{i\pi} + 1 = 0", size=1.2)
        gauss = Tex(r"\int_{-\infty}^{\infty} e^{-x^2}\,dx = \sqrt{\pi}", size=0.95)
        series = Tex(r"\sum_{n=1}^{\infty} \frac{1}{n^2} = \frac{\pi^2}{6}", size=0.95)
        # Colour per part (lesson 3.7 addresses the parts themselves).
        series.set_color_by_gradient("#58C4DD", "#FFD25E")

        # `arrange` instead of three hand-written heights: a formula's extent
        # depends on its tallest construct (that ∫ with limits is 1.5 units on
        # its own), so stacking them by eye is how you get an overlap.
        board = VGroup(euler, gauss, series)
        board.arrange(DOWN, buff=0.65)
        board.move_to(0.2 * DOWN)
        self.add(board)
        # Through LaTeX a glyph carries only the keys you asked for (`isolate`,
        # `t2c`), so this formula has none.
        print(
            f"children of the Euler formula (one per glyph): {len(euler.submobjects)}"
            f" · its keys: {euler.get_all_keys()}",
        )

        self.play(Write(euler), run_time=1.5)
        self.play(Write(gauss), run_time=1.8)
        self.play(DrawBorderThenFill(series), run_time=2.0)
        self.wait(0.5)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    Formulas(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
