"""Course 1 · 3.5 — Choosing the typesetting route

Janim has ONE typesetting route, LaTeX: `Tex`, `MathTex` and `TexText` all go
through latex + dvisvgm → SVG → VMobject, and texlive must be on the system.
So this lesson shows the LaTeX row only: the title and the label say what
Janim has.

The contract of the route is METRIC — x-height and baseline, calibrated
against a probe glyph — so a formula sits where its font says it should.

The cache stores the SVG TEXT (not the mobject), keyed by the tool versions
and the full compiled document. Edit a template and it invalidates honestly;
ask twice in a session and the second is a memo hit.

    python examples/tutorial/c1_03_groups_and_text/05_latex_config.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.5


class LatexConfig(Scene):
    def construct(self):
        title = Text("LaTeX: documents, measurements and keys", size=0.44, color=GREY_A)
        title.to_edge(UP, buff=0.4)
        self.add(title)

        formula = Tex(r"\frac{a^2}{b} + \sqrt{c}", size=0.9)
        formula.set_color("#E8A33D")
        label = Text("LaTeX", size=0.35, color=GREY_C)
        # `center=False` on Tex would keep the baseline at y = 0; here the
        # default centring is fine and the ROW is what we align.
        row = VGroup(label, formula)
        row.arrange(RIGHT, buff=0.8)
        rows = VGroup(row)
        rows.arrange(DOWN, buff=0.6, aligned_edge=LEFT)
        # The calibrated quantity is the X-HEIGHT, so that is what to measure.
        probe = Tex("x", size=1.0)
        print("LaTeX → x-height", round(float(probe.get_height()), 4))
        self.add(rows)

        self.play(
            LaggedStart(
                *(FadeIn(item, shift=0.3 * RIGHT) for item in rows.submobjects),
                lag_ratio=0.3,
            ),
            run_time=1.8,
        )
        self.wait(0.6)

        # A LaTeX SVG carries font ids, not characters, so Janim uses
        # ManimGL's trick: the formula is compiled ONCE with each isolated
        # part in a colour of its own, and the glyphs are attributed by that
        # colour. The consequence is worth knowing — a glyph answers only to
        # the `isolate` patterns and `t2c` keys you gave, and asking for
        # anything else says so.
        isolated = Tex("x^2 + y^2", isolate=["x^2"])
        print(
            f'isolate=["x^2"] → tex["x^2"] = {len(isolated["x^2"].submobjects)}'
            f" glyphs; keys: {isolated.get_all_keys()}",
        )
        try:
            isolated["y"]
            answer = "found"
        except KeyError as error:
            answer = str(error)[:120]
        print('and tex["y"], which was never isolated:', answer)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    LatexConfig(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
