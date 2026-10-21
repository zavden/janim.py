"""Course 4 · 1.1 — Every flat shape, in one frame

Course 4 is the REFERENCE course: between its chapters, every one of Janim's
exported names appears in a lesson that runs.

This lesson is the 2D zoo. Every constructor below is a `VMobject`: one flat
array of points in the interleaved quadratic layout, so they all take the
same setters and all interpolate into each other.

    python examples/tutorial/c4_01_shape_zoo/01_every_flat_shape.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 2.3   # after the cascade finishes


def cell(gallery, m, i, name):
    """Place `m` on a 6-column grid and label it (`i` is 1-based)."""
    row, col = divmod(i - 1, 6)
    # cap BOTH dimensions: set_width alone lets a tall shape run into its label
    m.set_width(1.5, stretch=False)
    if m.get_height() > 1.1:
        m.set_height(1.1, stretch=False)
    m.move_to((-5.9 + 2.35 * col, 1.9 - 2.05 * row, 0))
    label = Text(name, size=0.2, color=GREY_B)
    if label.get_width() > 2.1:
        label.set_width(2.1)
    label.next_to(m, DOWN, buff=0.14)
    gallery.add(m, label)


class EveryFlatShape(Scene):
    def construct(self):
        title = Text("the flat zoo — every VMobject constructor", size=0.42, color=GREY_A)
        title.to_edge(UP, buff=0.25)

        shapes = [
            (Circle(radius=1.0), "Circle"),
            (Ellipse(width=2.0, height=1.2), "Ellipse"),
            (Arc(angle=TAU / 3, radius=1.0), "Arc"),
            (ArcBetweenPoints(LEFT, RIGHT, angle=TAU / 5), "ArcBetweenPoints"),
            (Annulus(inner_radius=0.5, outer_radius=1.0), "Annulus"),
            (Sector(angle=TAU / 3), "Sector"),
            (AnnularSector(inner_radius=0.4, outer_radius=1.0, angle=TAU / 3), "AnnularSector"),
            (Square(side_length=2.0), "Square"),
            (Rectangle(width=2.4, height=1.4), "Rectangle"),
            (RoundedRectangle(width=2.4, height=1.4, corner_radius=0.3), "RoundedRectangle"),
            (Triangle(radius=1.0), "Triangle"),
            (RegularPolygon(6, radius=1.0), "RegularPolygon(6)"),
            (Polygon((-1, -0.8, 0), (1, -0.8, 0), (0.4, 0.9, 0), (-0.9, 0.4, 0)), "Polygon"),
            (Star(outer_radius=1.0), "Star"),
            (Elbow(width=1.4, angle=0.0), "Elbow"),
            (Line(LEFT, RIGHT), "Line"),
            (Arrow(LEFT, RIGHT), "Arrow"),
            (Dot(ORIGIN, radius=0.5), "Dot"),
        ]

        gallery = VGroup()
        for i, (m, name) in enumerate(shapes, 1):
            # every one of them takes the same two setters — that is the point
            m.set_stroke(BLUE_B, width=2.5)
            m.set_fill(BLUE_E, 0.35)
            cell(gallery, m, i, name)

        self.add(title, gallery)
        self.play(ShowCreation(gallery, lag_ratio=0.03), run_time=2.0)
        self.wait(0.5)


if __name__ == "__main__":
    # The tutorial's default settings are used here.
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    EveryFlatShape(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
