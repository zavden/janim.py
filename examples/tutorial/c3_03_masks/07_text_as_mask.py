"""Course 3 · 3.7 — Text as the cutter

A `Text` or a `Tex` is a mobject like any other, so it can be the mask. That
gives you the title-sequence look — the world seen THROUGH the letters — with
no new machinery.

It works because every glyph is real vector geometry with real antialiased
coverage: the cut is per pixel, so the letterforms keep their curves. A
rasterised text mask would show its own pixels at the edges.

TWO DIRECTIONS, both here:

    inside=word    the content shows INSIDE the letters
    minus=word     the letters are punched OUT of the content

And one composition detail: the moving content underneath is an ordinary
layer with its own updater, so the text stays still while the world slides
behind it.

    python examples/tutorial/c3_03_masks/07_text_as_mask.py
"""

from pathlib import Path

from janim import *
from janim.core._julia_math import sin

PREVIEW_T = 2.0


def drift(y):
    """A drifting field of colour to be seen through the letters."""
    g = VGroup()
    colours = color_gradient(["#FF3D8B", "#FFD25E", "#39D0FF"], 24)
    for k in range(24):
        c = Circle(radius=0.75)
        c.set_fill(color=colours[k], opacity=1.0)
        c.set_stroke(opacity=0)
        c.move_to((-8.0 + 0.7 * k, y + 0.5 * sin(0.9 * k), 0))
        g.add(c)

    def slide(m, dt):
        if not dt > 0:
            return
        m.shift((1.1 * dt, 0, 0))
        if m.get_center()[0] > 2.0:
            m.shift((-8.0, 0, 0))

    g.add_updater(slide)
    return g


class TextAsMask(Scene):
    def construct(self):
        top = Text("THROUGH", size=1.5)
        top.move_to(1.35 * UP)
        bottom = Text("AROUND", size=1.5)
        bottom.move_to(1.35 * DOWN)

        plate = Rectangle(width=8.6, height=2.2)
        plate.set_fill(color="#1B2430", opacity=1.0)
        plate.set_stroke(opacity=0)
        plate.move_to(1.35 * DOWN)

        caption = Text(
            "inside = the letters · minus = the letters",
            size=0.34,
            color=GREY_B,
        )
        caption.move_to(3.1 * DOWN)

        self.use_composition(
            Composition(
                crop(drift(1.35), inside=top),          # seen through the word
                Layer(plate),
                crop(drift(-1.35), minus=bottom),       # …and punched out of it
                Layer(caption),
                background=(0.02, 0.03, 0.05, 1),
            ),
        )

        self.wait(3.0)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    TextAsMask(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
