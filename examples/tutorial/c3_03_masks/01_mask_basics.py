"""Course 3 · 3.1 — Masks

    Mask(*mobjects, invert=False, feather=0.0, hard=False, luma=False)
    Layer(*content, mask=Mask(shape))

The mask's mobjects are rendered into their own buffer and the layer is
MULTIPLIED by that buffer's alpha. So the cut-out is per PIXEL and exact —
antialiased edges included — not a polygon intersection.

What can be a mask: anything that draws. A circle, a text mobject, an
imported SVG, a group of a hundred dots, a shape being animated. If you can
see it, you can cut with it.

The masking mobjects are NOT drawn: they only contribute coverage. They do
still get updated, so a mask can follow something (lesson 3.6).

    python examples/tutorial/c3_03_masks/01_mask_basics.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.4


def stripes(x):
    """A striped field — something whose cut edge is easy to see."""
    g = VGroup()
    colours = color_gradient(["#FF5E5E", "#FFD25E", "#7FDD58", "#58C4DD", "#C77DFF"], 22)
    for k, c in enumerate(colours, start=1):
        r = Rectangle(width=0.22, height=3.6)
        r.set_fill(color=c, opacity=1.0)
        r.set_stroke(opacity=0)
        r.move_to((x - 2.3 + 0.22 * (k - 1), -0.1, 0))
        g.add(r)
    return g


class MaskBasics(Scene):
    def construct(self):
        title = Text(
            "the mask is coverage, per pixel",
            size=0.44,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.3)

        # LEFT: no mask.
        plain = stripes(-3.4)

        # RIGHT: the same stripes, cut by a star. The star is never drawn.
        cut = stripes(3.4)
        cutter = Star(5, outer_radius=1.8, fill_opacity=1.0)
        cutter.move_to((3.4, -0.1, 0))

        l1 = Text("as rendered", size=0.32, color=GREY_B)
        l2 = Text("mask = Mask(star)", size=0.32, color=GREY_B)
        l1.move_to((-3.4, -2.5, 0))
        l2.move_to((3.4, -2.5, 0))

        self.use_composition(
            Composition(
                Layer(plain),
                Layer(cut, mask=Mask(cutter)),
                Layer(title, l1, l2),
                background=(0.02, 0.03, 0.05, 1),
            ),
        )

        self.wait(1.5)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    MaskBasics(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
