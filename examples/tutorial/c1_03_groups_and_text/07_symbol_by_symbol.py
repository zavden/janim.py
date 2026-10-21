"""Course 1 · 3.7 — Symbol by symbol

Three ways to address the pieces of a formula, weakest to strongest:

    tex[2] · tex[1:4]     by POSITION (0-based, as in Python). Fine for a
                          one-off, fragile under any edit of the formula.
    tex["x"]              by KEY. Through LaTeX (Janim's one route) a glyph
                          carries font ids, not characters, so it answers
                          only to the `isolate` patterns and `t2c` keys you
                          gave; this lesson addresses the two y's by
                          position instead.
    isolate=["x^2"]       by PATTERN. The formula is compiled ONCE with each
                          isolated part in a colour of its own (ManimGL's
                          trick), and every occurrence gets the pattern as a
                          key. So `tex["x^2"]` is the whole subexpression,
                          superscript included.

All of them return MEMOISED groups: `tex["x^2"] is tex["x^2"]`. That
matters — calling it inside an updater at 60 fps would otherwise build a new
VGroup every frame and register it as a parent of the glyphs, and the parent
list would grow without bound.

The known fragility, shared with Manim: matching is by glyph SEQUENCE, so
`isolate=["b"]` also claims the b of `b^2` when it comes first. Isolate the
longer pattern too when it bites.

    python examples/tutorial/c1_03_groups_and_text/07_symbol_by_symbol.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 3.0


class SymbolBySymbol(Scene):
    def construct(self):
        title = Text(
            "address the parts, then animate them",
            size=0.46,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.4)
        self.add(title)

        # isolate labels the glyph runs; the longer pattern is isolated too,
        # so it outranks its own substring when both could match.
        f = Tex(
            r"x^2 + 2xy + y^2",
            size=1.5,
            isolate=["x^2", "y^2", "2xy"],
        )
        f.move_to(0.6 * UP)
        self.add(f)
        self.play(Write(f), run_time=1.4)

        print("keys carried by this formula:", f.get_all_keys())
        print("glyphs labelled «x^2»:", len(f.find_by_key("x^2")))
        print("memoised?", f["x^2"] is f["x^2"])

        # By pattern: the subexpression as one group.
        self.play(
            Indicate(
                f["x^2"],
                color="#58C4DD",
                scale_factor=1.3,
            ),
            run_time=1.0,
        )
        self.play(
            Indicate(
                f["2xy"],
                color="#E8A33D",
                scale_factor=1.3,
            ),
            run_time=1.0,
        )

        # Every «y» at once, wherever it is. There is no key for
        # a bare «y», so address them by position: they are glyphs 5 and 7
        # of x, 2, +, 2, x, y, +, y, 2.
        self.play(
            Circumscribe(
                VGroup(f[5], f[7]),
                color="#7FDD58",
                buff=0.12,
            ),
            run_time=1.2,
        )

        # By position: the third child, whatever that turns out to be.
        self.play(Indicate(f[2], color="#FF5E5E"), run_time=0.8)

        # And the payoff — a matched morph that pairs the isolated parts, so
        # the square lands on the square and the cross term is the thing that
        # leaves.
        g = Tex(r"(x + y)^2", size=1.5, isolate=["x", "y"])
        g.move_to(0.6 * UP)
        self.play(TransformMatchingTex(f, g), run_time=1.8)
        self.wait(0.6)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    SymbolBySymbol(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
