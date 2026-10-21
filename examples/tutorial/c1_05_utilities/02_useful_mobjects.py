"""Course 1 · 5.2 — The rest of the zoo

Shapes:      Arc · Circle · Ellipse · Polygon · RegularPolygon · Triangle ·
             Rectangle · RoundedRectangle · Square · Star · Annulus ·
             Sector · AnnularSector · ArcBetweenPoints · Elbow
Primitives:  Line · Arrow · Dot  (their ends may be MOBJECTS: the facing
             borders are used, which is what makes diagrams hold together)
Annotation:  Brace · BraceLabel · Underline · Cross · BackgroundRectangle ·
             SurroundingRectangle · DashedLine · DashedVMobject ·
             Angle · RightAngle (+ `angle_value`, `line_intersection`)
Grids:       MatrixMobject · Table (read them with get_entries/get_rows/
             get_columns/get_cell/get_brackets/get_lines, or by key "(i,j)")
Live:        TracedPath · ValueTracker · DecimalNumber · always_redraw
3D:          Sphere · Torus · Cylinder · Cone · PlaneXY · Surface ·
             Dot3D · Line3D · Arrow3D

Two of these are better than Manim's, for the same reason both times — the
renderer is ours. `Brace` is a native stretchable PATH, not
`Tex(r"\\underbrace{\\qquad}")`, so it needs no LaTeX and its strokes stay even
at any width. `Annulus` is two subpaths turning in opposite directions, and
the hole comes free from winding fill — no mask, no boolean op.

    python examples/tutorial/c1_05_utilities/02_useful_mobjects.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 3.2


class UsefulMobjects(Scene):
    def construct(self):
        title = Text("the zoo", size=0.5, color=GREY_A)
        title.to_edge(UP, buff=0.3)
        self.add(title)

        # ── row 1: shapes ────────────────────────────────────────────────────
        shapes = VGroup()
        for m in (
            RegularPolygon(6, radius=0.55),
            Star(5, outer_radius=0.6),
            Annulus(inner_radius=0.28, outer_radius=0.6),
            Sector(angle=TAU / 3, radius=0.6),
            RoundedRectangle(
                width=1.2,
                height=0.9,
                corner_radius=0.22,
            ),
            Ellipse(width=1.3, height=0.8),
        ):
            m.set_fill(color="#2C5F8A", opacity=1.0)
            m.set_stroke(color="#58C4DD", width=2.5)
            shapes.add(m)
        shapes.arrange(RIGHT, buff=0.35)
        shapes.move_to(1.7 * UP)

        # ── row 2: a diagram — Line/Arrow between MOBJECTS, plus an angle ─────
        a = Dot((-5.2, 0.0, 0), radius=0.1)
        a.set_fill(color=YELLOW)
        b = Dot((-2.6, 0.9, 0), radius=0.1)
        b.set_fill(color=YELLOW)
        c = Dot((-2.6, -0.9, 0), radius=0.1)
        c.set_fill(color=YELLOW)
        ab = Line(a, b, buff=0.12)  # the ends are mobjects: borders used
        ac = Line(a, c, buff=0.12)
        for line in (ab, ac):
            line.set_stroke(color=GREY_A, width=3.0)
        # `quadrant` and `other_angle` choose WHICH of the four angles at the
        # crossing you mean. The default (1, 1) here would sweep the reflex one —
        # 327°, i.e. almost a full circle round the vertex.
        mark = Angle(
            ab,
            ac,
            radius=0.55,
            other_angle=True,
            color="#FF5E5E",
        )
        arrow = Arrow(
            b,
            c,
            buff=0.15,
            thickness=3.0,
        )
        arrow.set_fill(color="#7FDD58")

        # ── row 3: annotation and grids ──────────────────────────────────────
        slab = Rectangle(width=2.2, height=0.7)
        slab.set_fill(color="#37506B", opacity=1.0)
        slab.set_stroke(opacity=0)
        slab.move_to((1.4, -1.4, 0))
        brace = Brace(
            slab,
            DOWN,
            buff=0.12,
            color=GREY_A,
        )
        blabel = Text("Brace: a native path", size=0.28, color=GREY_B)
        blabel.next_to(brace, DOWN, buff=0.12)

        dashed = DashedLine(
            (-1.2, -3.3, 0),
            (3.8, -3.3, 0),
            dash_length=0.12,
        )
        dashed.set_stroke(color="#8894A6", width=3.0)

        matrix = MatrixMobject(
            [[1, 2], [3, 4]],
            cell=lambda s: Tex(s, size=0.7),
        )
        matrix.scale(0.8)
        matrix.move_to((4.6, -1.2, 0))

        self.add(
            shapes,
            a,
            b,
            c,
            ab,
            ac,
            mark,
            arrow,
            slab,
            brace,
            blabel,
            dashed,
            matrix,
        )
        self.play(
            LaggedStart(
                FadeIn(shapes),
                ShowCreation(ab),
                ShowCreation(ac),
                ShowCreation(mark),
                GrowArrow(arrow),
                FadeIn(slab),
                FadeIn(brace),
                Write(blabel),
                ShowCreation(dashed),
                Write(matrix),
                lag_ratio=0.12,
            ),
            run_time=3.0,
        )
        print(
            "angle at the vertex: ",
            round(abs(angle_value(ab, ac, other_angle=True)) / DEG, 1),
            "° (the default quadrant would report its reflex, ",
            round(angle_value(ab, ac) / DEG, 1),
            "°)",
            sep="",
        )
        # What a mobject IS is its class name.
        print("matrix cell (1,2): ", type(matrix.get_cell(1, 2)).__name__, sep="")
        self.wait(0.5)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    UsefulMobjects(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
