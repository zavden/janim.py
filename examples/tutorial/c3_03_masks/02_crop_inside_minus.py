"""Course 3 · 3.2 — `crop`: the two ways to say it

    crop(*base, inside=shape, feather=0.0, hard=False, **kwargs)
    crop(*base, minus=shape, feather=0.0, hard=False, **kwargs)

Sugar over `Layer(*base, mask=Mask(shape, invert=…))`, and it returns a
`Layer`, so it drops straight into a `Composition`.

    inside=shape    KEEP what is inside the shape (a window)
    minus=shape     REMOVE what is inside it (a hole)

Exactly one of the two, always: asking for both, or neither, is an error
with that sentence in it. The reason there are two words instead of an
`invert` flag is that at the call site "keep the part inside this circle"
and "punch this circle out" are different intentions, and reading
`invert=True` six months later tells you neither.

    python examples/tutorial/c3_03_masks/02_crop_inside_minus.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.4


def mesh(x):
    """A dense grid, so the cut is unmistakable."""
    g = VGroup()
    for k in range(-8, 9):
        v = Line((x + 0.3 * k, -2.0, 0), (x + 0.3 * k, 2.0, 0))
        v.set_stroke(color="#3D7BC0", width=2.0)
        g.add(v)
    for k in range(-6, 7):
        h = Line((x - 2.4, 0.3 * k, 0), (x + 2.4, 0.3 * k, 0))
        h.set_stroke(color="#3D7BC0", width=2.0)
        g.add(h)
    return g


class CropInsideMinus(Scene):
    def construct(self):
        title = Text(
            "inside = a window · minus = a hole",
            size=0.44,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.3)

        left, right = mesh(-3.5), mesh(3.5)
        window = Circle(radius=1.5, fill_opacity=1.0)
        window.move_to((-3.5, 0, 0))
        hole = Circle(radius=1.5, fill_opacity=1.0)
        hole.move_to((3.5, 0, 0))

        l1 = Text("crop(mesh, inside=circle)", size=0.32, color=GREY_B)
        l2 = Text("crop(mesh, minus=circle)", size=0.32, color=GREY_B)
        l1.move_to((-3.5, -2.6, 0))
        l2.move_to((3.5, -2.6, 0))

        self.use_composition(
            Composition(
                crop(left, inside=window),
                crop(right, minus=hole),
                Layer(title, l1, l2),
                background=(0.02, 0.03, 0.05, 1),
            ),
        )

        self.wait(1.5)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    CropInsideMinus(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
