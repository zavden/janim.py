"""Course 3 · 3.5 — Luma masks

    Mask(shape, luma=True)

Coverage is taken from the mask's LUMINANCE (0.2126 R + 0.7152 G + 0.0722 B)
instead of its alpha. White shows, black hides, and every grey in between is
a partial cut.

Careful with one detail, and it is the only surprise here: the luminance is
read from a PREMULTIPLIED texture, so it is already multiplied by alpha.
Black and transparent both count as "hide", which is what you want — a
transparent region has no light to give.

What it buys you over an alpha mask: gradients. Paint a mask with
`set_fill_by_gradient` and you have a soft wipe with a shape you control
exactly; add a noise texture and you have a dissolve.

    python examples/tutorial/c3_03_masks/05_luma_mask.py
"""

from pathlib import Path

from janim import *
from janim.core._julia_math import sin

PREVIEW_T = 2.4


class LumaMask(Scene):
    def construct(self):
        title = Text(
            "luma: white shows, black hides, grey partly",
            size=0.42,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.3)

        def content(x):
            """The content to be revealed."""
            g = VGroup()
            colours = color_gradient(["#FF3D8B", "#FFD25E"], 8)
            for k in range(8):
                c = RegularPolygon(6, radius=0.55)
                c.set_fill(color=colours[k], opacity=1.0)
                c.set_stroke(opacity=0)
                c.move_to((x - 2.4 + 0.7 * k, -0.2 + 0.35 * sin(1.4 * k), 0))
                g.add(c)
            return g

        # A gradient painted onto a rectangle: its brightness IS the coverage.
        ramp = Rectangle(width=6.2, height=3.0)
        ramp.set_fill_by_gradient(BLACK, WHITE)
        ramp.set_fill(opacity=1.0)
        ramp.set_stroke(opacity=0)
        ramp.move_to((-3.5, -0.2, 0))

        # A moving wipe: the same idea with the gradient sliding across.
        wipe = Rectangle(width=6.2, height=3.0)
        wipe.set_fill_by_gradient(WHITE, BLACK)
        wipe.set_fill(opacity=1.0)
        wipe.set_stroke(opacity=0)
        wipe.move_to((3.5, -0.2, 0))

        def slide(m, dt):
            if not dt > 0:
                return
            m.move_to((3.5 + 2.4 * sin(0.9 * self.t), -0.2, 0))

        wipe.add_updater(slide)

        l1 = Text("a still gradient", size=0.3, color=GREY_B)
        l2 = Text("…and the same thing, moving", size=0.3, color=GREY_B)
        l1.move_to((-3.5, -2.5, 0))
        l2.move_to((3.5, -2.5, 0))

        self.use_composition(
            Composition(
                Layer(content(-3.5), mask=Mask(ramp, luma=True)),
                Layer(content(3.5), mask=Mask(wipe, luma=True)),
                Layer(title, l1, l2),
                background=(0.02, 0.03, 0.05, 1),
            ),
        )

        self.wait(3.5)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    LumaMask(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
