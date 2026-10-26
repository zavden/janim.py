"""Course 1 · 3.8 — Code

    Code(code_file=None, code_string=None, language=None,
         formatter_style="vim", tab_width=4, add_line_numbers=True,
         line_numbers_from=1, background="rectangle", background_config=None,
         paragraph_config=None)

ManimCE's `Code`, with CE's names. pygments colours the listing token by
token; it is one of Janim's pinned dependencies, loaded only when a `Code`
is built. `language` is guessed from the file name or the code when you
leave it out, and guessing is flaky: name it.

The result is a parent with three named parts:

    code.background      a rounded rectangle; "window" adds three buttons
    code.line_numbers    one group per line, right-aligned (absent without
                         add_line_numbers)
    code.code_lines      one group per line, one child per glyph; spaces
                         make no glyph, so code_lines[i][j] is the j-th
                         VISIBLE character of line i

Every colour comes from the pygments style: the code, the line numbers and
the background (unless `background_config` sets `fill_color`). A `color` in
`paragraph_config` is ignored, as in CE. `Code.get_styles_list()` names the
styles; `Code.get_pygments_style(name)` returns one to subclass.

Two things differ from CE on purpose. The font: Janim resolves real
families, not fontconfig's "Monospace", so the default is the first of
DejaVu Sans Mono, Menlo, Consolas, Liberation Mono, Noto Sans Mono and
Courier New that your system has (`paragraph_config={"font": ...}` picks
one). The layout: every line sits on its own baseline at CE's pitch, and the
block's height is taken from the font's "A" and "p", so two listings of the
same number of lines have the same height whatever they contain.
`font_size` follows CE's scale — 24, the default, is CE's size.

    python examples/tutorial/c1_03_groups_and_text/08_code.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 3.2

SNIPPET = '''from janim import *


class Orbit(Scene):
    def construct(self):
        sun = Dot(color=YELLOW)
        planet = Dot().shift(2 * RIGHT)
        self.add(sun, planet)
        self.play(Rotate(planet, TAU, about_point=ORIGIN))'''


class CodeLesson(Scene):
    def construct(self):
        title = Text("a listing is a parent of glyphs", size=0.42, color=GREY_A)
        title.to_edge(UP, buff=0.3)

        listing = Code(
            code_string=SNIPPET,
            language="python",
            background="window",
        )
        listing.next_to(title, DOWN, buff=0.35)

        light = Code(
            code_string="for k in range(3):\n\tprint(k ** 2)",
            language="python",
            formatter_style="xcode",
            line_numbers_from=41,
        )
        bare = Code(
            code_string="orbit = Rotate(planet, TAU)",
            language="python",
            formatter_style="monokai",
            add_line_numbers=False,
        )
        others = VGroup(light, bare).arrange(RIGHT, buff=0.6)
        others.to_edge(DOWN, buff=0.35)

        print(len(Code.get_styles_list()), "pygments styles available")

        self.add(title)
        self.play(FadeIn(listing, shift=0.3 * DOWN), run_time=1.0)

        # The last line, and the glyphs of «TAU» inside it, are ordinary
        # children: frame them, recolour them. Spaces make no glyph, so the
        # index of a character counts the VISIBLE characters only.
        last = listing.code_lines[-1]
        frame = SurroundingRectangle(last, buff=0.08, color=YELLOW)
        self.play(ShowCreation(frame), run_time=0.8)
        visible = "".join(SNIPPET.split("\n")[-1].split())
        start = visible.index("TAU")
        tau = last[start:start + 3]
        self.play(tau.animate.set_color(RED), run_time=0.6)

        self.play(
            LaggedStart(
                FadeIn(light, shift=0.3 * UP),
                FadeIn(bare, shift=0.3 * UP),
                lag_ratio=0.3,
            ),
            run_time=1.2,
        )
        self.wait(0.6)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    CodeLesson(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
