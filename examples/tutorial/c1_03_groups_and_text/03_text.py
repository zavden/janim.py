"""Course 1 · 3.3 — Text

    Text(s, font="DejaVu Sans", size=1.0, color=WHITE, t2c=None, t2w=None,
         center=True)

Plain text straight through FreeType: outlines, advances and kerning, turned
into quadratic Béziers. No LaTeX, no SVG round trip. Simple Latin is the
honest frontier — complex shaping (Arabic, ligature-heavy scripts) is
HarfBuzz's job and is deliberately out.

Every glyph is a CHILD carrying its character as a key (`text["a"]` groups
the a's), which is what makes colour-by-substring and per-symbol animation
work without a second mechanism.

    t2c={"orbit": YELLOW, range(0, 6): BLUE}     colour by substring or range
    t2w={"important": "bold"}                    weight, or a whole font name

`t2c`/`t2w` are applied INSIDE the constructor, not afterwards, because that
is the only place that knows which glyph came from which character — spaces
produce no child, so glyph number ≠ character number. Ranges are Python's:
0-based and half-open: `range(24, 32)` covers characters 25 to 32.

A miss is an ERROR, not a silent fallback: a fuzzy font lookup always
answers with SOMETHING, so asking for a weight your system lacks would
quietly give you the regular one. Janim checks and complains.

    python examples/tutorial/c1_03_groups_and_text/03_text.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 2.8


class TextLesson(Scene):
    def construct(self):
        lines = VGroup()

        plain = Text("plain text through FreeType", size=0.6)
        lines.add(plain)

        coloured = Text(
            "colour by substring and by range",
            size=0.6,
            t2c={"substring": YELLOW, range(24, 32): "#7FDD58"},
        )
        lines.add(coloured)

        weighted = Text(
            "weight comes from a real face",
            size=0.6,
            t2w={"real face": "bold"},
        )
        lines.add(weighted)

        serif = Text(
            "another family entirely",
            size=0.6,
            font="Liberation Serif",
            color="#E8A33D",
        )
        lines.add(serif)

        lines.arrange(DOWN, buff=0.45)
        lines.shift(0.4 * UP)
        self.add(lines)

        # Glyphs are children keyed by their character, so this is a real group.
        print("the letter «e» appears", len(plain.find_by_key("e")), "times")

        self.play(
            LaggedStart(
                *(Write(line) for line in lines.submobjects),
                lag_ratio=0.25,
            ),
            run_time=2.4,
        )

        # `plain["e"]` is a group of SCATTERED glyphs, so `Indicate`'s default
        # scale_factor would scale the CONSTELLATION and pull the letters out
        # of their words. `scale_factor=1.0` leaves the geometry alone and
        # keeps only the tint — which is what you meant by "highlight every e".
        self.play(
            Indicate(
                plain["e"],
                color="#FF5E5E",
                scale_factor=1.0,
            ),
            run_time=1.2,
        )
        self.wait(0.4)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    TextLesson(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
