"""Course 3 · 4.9 — EdgeDetect

    EdgeDetect(amount=1.0, color=None, thickness=1.0)

A Sobel operator over luma: the silhouette of whatever is on the layer.

    color=None       the edges keep the original colour — a rim-light look
    color=WHITE      the layer becomes a LINE DRAWING on transparency, which
                     is the pedagogical use: show the outline of a shape
                     without redrawing it
    thickness        the sampling step in pixels (a fatter kernel, not a
                     thicker stroke)
    amount           gain; 0 skips the pass entirely

Two uses worth knowing. Put it on a layer of its OWN, on top of the same
content with `blend="add"`, and you get outlines drawn over the solid
shapes — the "annotate what is already there" move. Or put it on the only
copy and the solid disappears, leaving the drawing.

    python examples/tutorial/c3_04_glitch/09_edge_detect.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.4


def blobs(x):
    """Solid shapes, which is what an edge detector wants."""
    group = VGroup()
    for dx, dy, r, colour in (
        (-0.7, 0.5, 0.85, "#3D7BC0"),
        (0.6, 0.75, 0.6, "#FFD25E"),
        (0.15, -0.7, 1.0, "#FF3D8B"),
    ):
        circle = Circle(radius=r)
        circle.set_fill(colour, 1.0)
        circle.set_stroke(opacity=0)
        circle.move_to((x + dx, dy - 0.1, 0))
        group.add(circle)
    square = Square(side_length=1.1)
    square.rotate(PI / 7)
    square.set_fill("#7FDD58", 1.0)
    square.set_stroke(opacity=0)
    square.move_to((x - 0.1, -0.2, 0))
    group.add(square)
    return group


class EdgeDetectLesson(Scene):
    def construct(self):
        title = Text(
            "Sobel over luma: the silhouette",
            size=0.44,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.3)

        labels = []
        for x, text in (
            (-4.6, "as rendered"),
            (0.0, "EdgeDetect(color = WHITE)"),
            (4.6, "solid + edges on :add"),
        ):
            label = Text(text, size=0.28, color=GREY_B)
            label.move_to((x, -2.6, 0))
            labels.append(label)

        # The third panel needs TWO layers over the same geometry: the solid,
        # and a copy that has been reduced to its edges.
        solid = blobs(4.6)
        outline = solid.copy()

        self.use_composition(
            Composition(
                Layer(blobs(-4.6)),
                Layer(blobs(0.0), effects=[EdgeDetect(color=WHITE, amount=1.4)]),
                Layer(solid),
                Layer(
                    outline,
                    blend="add",
                    effects=[
                        EdgeDetect(
                            color="#FFFFFF",
                            amount=2.0,
                            thickness=1.6,
                        ),
                    ],
                ),
                Layer(title, *labels),
                background=(0.02, 0.03, 0.05, 1.0),
            ),
        )

        self.wait(1.6)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    EdgeDetectLesson(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
