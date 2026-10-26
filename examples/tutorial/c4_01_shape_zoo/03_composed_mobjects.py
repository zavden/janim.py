"""Course 4 · 1.3 — Composed mobjects

Seven objects that Manim builds out of others, and Janim too:

    TangentialArc(line1, line2, radius, corner=(1, 1))
                    CE's; tangent to two crossing lines, in the corner
                    picked by the signs
    ArcPolygonFromArcs(*arcs)
                    CE's; one closed path through the arcs, with a straight
                    piece wherever an arc does not meet the next
    SampleSpace(width=3, height=3)
                    GL's; divide_horizontally / divide_vertically by
                    probabilities, braces and labels from the parts
    Disk3D(radius=1)
                    GL's; a flat disc as a shaded mesh, for 3D scenes
    Variable(value, label, var_type=DecimalNumber)
                    CE's; "label = value", the value following
                    `variable.tracker`
    ExponentialValueTracker(value)
                    GL's; stores log(value), so it moves geometrically:
                    halfway from 1 to 1000 it reads about 31.6
    AnimatedBoundary(vmobject)
                    GL's; an outline that keeps drawing itself in cycling
                    colours, on its own updater

One deliberate difference: ManimGL 1.7.2 stores the argument of
`ExponentialValueTracker(5)` as the logarithm, so it reads e⁵; Janim's
reads 5, as `set_value(5)` does in both.

    python examples/tutorial/c4_01_shape_zoo/03_composed_mobjects.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 2.5


class ComposedMobjects(Scene):
    def construct(self):
        title = Text("composed mobjects", size=0.4, color=GREY_A)
        title.to_edge(UP, buff=0.25)

        # ── tangential arcs: the four corners of two crossing lines ──────────
        line1 = DashedLine(1.8 * LEFT, 1.8 * RIGHT).set_stroke(GREY_B, width=2)
        line2 = DashedLine(1.4 * DOWN, 1.4 * UP).set_stroke(GREY_B, width=2)
        line2.rotate(20 * DEGREES, about_point=ORIGIN)
        corners = VGroup(*(
            TangentialArc(line1, line2, radius=0.6, corner=corner).set_stroke(color, width=4)
            for corner, color in (
                ((1, 1), RED),
                ((1, -1), GREEN),
                ((-1, 1), BLUE),
                ((-1, -1), YELLOW),
            )
        ))
        tangents = VGroup(line1, line2, corners).move_to((-4.6, 1.6, 0))

        # ── a Reuleaux triangle from three arcs ──────────────────────────────
        a, b, c = (-0.9, 0, 0), (0.9, 0, 0), (0, 0.9 * 3**0.5, 0)
        outline = dict(stroke_width=0)
        reuleaux = ArcPolygonFromArcs(
            ArcBetweenPoints(a, b, angle=PI / 3, **outline),
            ArcBetweenPoints(b, c, angle=PI / 3, **outline),
            ArcBetweenPoints(c, a, angle=PI / 3, **outline),
            fill_color=PURPLE,
            fill_opacity=0.8,
            stroke_color=WHITE,
            stroke_width=4,
        )
        reuleaux.move_to((0, 1.5, 0))

        # ── a sample space divided by probabilities ──────────────────────────
        space = SampleSpace(width=2.4, height=2.4)
        space.divide_horizontally([0.3])
        sides = space.get_side_braces_and_labels([r"P(A)", r"P(\bar A)"])
        VGroup(space, sides).move_to((4.6, 1.4, 0))

        # ── a disc as a mesh, tilted to show its shading ─────────────────────
        disk = Disk3D(radius=1.2, color=TEAL)
        disk.rotate(60 * DEGREES, axis=RIGHT).move_to((-4.6, -2.2, 0))

        # ── a variable, and a tracker that moves geometrically ───────────────
        x = Variable(1.0, "x", num_decimal_places=2)
        growth = ExponentialValueTracker(1.0)
        readout = DecimalNumber(1.0, num_decimal_places=1, size=0.45, color=ORANGE)
        readout.add_updater(lambda number: number.set_value(growth.get_value()))
        caption = Text("exponential tracker", size=0.3, color=GREY_B)
        numbers = VGroup(x, VGroup(caption, readout).arrange(RIGHT, buff=0.25))
        numbers.arrange(DOWN, buff=0.5, aligned_edge=LEFT).move_to((0, -2.2, 0))

        # ── a boundary that keeps drawing itself ─────────────────────────────
        square = Square(side_length=1.8).set_fill(GREY_E, opacity=1).set_stroke(width=0)
        square.move_to((4.6, -2.2, 0))
        boundary = AnimatedBoundary(square, cycle_rate=1.0)

        self.add(title, tangents, reuleaux, space, sides, disk, numbers, square, boundary, readout)
        self.play(
            x.tracker.animate.set_value(10.0),
            growth.animate.set_value(1000.0),
            run_time=3.0,
            rate_func=linear,
        )
        self.wait(0.5)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    ComposedMobjects(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
