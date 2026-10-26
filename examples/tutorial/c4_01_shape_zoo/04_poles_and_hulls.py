"""Course 4 · 1.4 — The pole of a polygon, the hull of a cloud

Two objects whose construction is an algorithm rather than a layout:

    LabeledPolygram(*rings, label, precision=0.01)
            CE's; a polygram with holes and a label at its POLE OF
            INACCESSIBILITY: the point inside farthest from every edge.
            `polygram.pole` is that point, `polygram.radius` its distance
            to the nearest edge — the circle drawn here.
    ConvexHull3D(*points, tolerance=1e-5)
            CE's; the smallest convex polyhedron around points in space,
            as triangles.

The pole comes from polylabel (Agafonkin's algorithm, ported from CE's code
with CE's order of work, so it lands on CE's point to the last bit): cover
the shape with square cells, keep the one whose centre is farthest inside,
and split every cell that could still hide a farther point. The hull is
incremental: a tetrahedron, then every other point replaces the faces it can
see with a fan to their horizon. CE's QuickHull returns the same triangles
in an order that comes out of a set; Janim's order depends only on the
points.

    python examples/tutorial/c4_01_shape_zoo/04_poles_and_hulls.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 2.0

OUTLINE = [
    (-3.8, -2.4, 0), (-2.4, -2.5, 0), (-1.3, -1.6, 0), (-0.2, -1.7, 0),
    (1.7, -2.5, 0), (2.9, -2.6, 0), (3.5, -1.5, 0), (4.9, -1.4, 0),
    (4.5, 0.2, 0), (4.7, 1.6, 0), (3.5, 2.4, 0), (1.1, 2.5, 0),
    (-0.1, 0.9, 0), (-1.2, 0.5, 0), (-1.6, 0.7, 0), (-1.4, 1.9, 0),
    (-2.6, 2.6, 0), (-4.4, 1.2, 0), (-4.9, -0.8, 0), (-3.8, -2.4, 0),
]
LAKE = [
    (0.2, -1.2, 0), (0.9, -1.2, 0), (1.4, -2.0, 0), (2.1, -1.6, 0),
    (2.2, -0.5, 0), (1.4, 0.0, 0), (0.4, -0.2, 0), (0.2, -1.2, 0),
]
POND = [(-2.7, 1.4, 0), (-2.3, 1.7, 0), (-2.8, 1.9, 0), (-2.7, 1.4, 0)]

CLOUD = [
    (1.93192757, 0.44134585, -1.52407061), (-0.93302521, 1.23206983, 0.64117067),
    (-0.44350918, -0.61043677, 0.21723705), (-0.42640268, -1.05260843, 1.61266094),
    (-1.84449637, 0.91238739, -1.85172623), (1.72068132, -0.11880457, 0.51881751),
    (0.41904805, 0.44938012, -1.86440686), (0.83864666, 1.66653337, 1.88960123),
    (0.22240514, -0.80986286, 1.34249326), (-1.29585759, 1.01516189, 0.46187522),
    (1.7776499, -1.59550796, -1.70240747), (0.80065226, -0.12530398, 1.70063977),
    (1.28960948, -1.44158255, 1.39938582), (-0.93538943, 1.33617705, -0.24852643),
    (-1.54868271, 1.7444399, -0.46170734),
]


class PolesAndHulls(Scene):
    def construct(self):
        title = Text("the pole of a polygon, the hull of a cloud", size=0.4, color=GREY_A)
        title.to_edge(UP, buff=0.25)

        # ── a country with two lakes, labelled where the label fits best ─────
        land = LabeledPolygram(
            OUTLINE,
            LAKE,
            POND,
            label="Pole",
            fill_color=GREEN_D,
            fill_opacity=0.8,
            stroke_color=GREEN_A,
            stroke_width=2,
        )
        reach = Circle(radius=land.radius).move_to(land.pole)
        reach.set_stroke(WHITE, width=2).set_fill(opacity=0)
        country = VGroup(land, reach).scale(0.62).move_to((-3.2, -0.4, 0))

        # ── a cloud of points and its hull, turning so the depth reads ───────
        hull = ConvexHull3D(
            *CLOUD,
            fill_color=BLUE_D,
            fill_opacity=0.55,
            stroke_color=BLUE_A,
            stroke_width=1.0,
        )
        dots = Group(*(Dot3D(point, radius=0.06, color=YELLOW) for point in CLOUD))
        cloud = Group(hull, dots).rotate(-70 * DEGREES, axis=RIGHT).scale(0.85).move_to((3.4, -0.4, 0))

        self.add(title)
        self.play(DrawBorderThenFill(land), run_time=1.4)
        self.play(ShowCreation(reach), run_time=0.8)
        self.play(FadeIn(dots, lag_ratio=0.1), run_time=0.8)
        self.play(FadeIn(hull), run_time=0.8)
        self.play(
            Rotate(cloud, TAU / 3, axis=OUT),
            run_time=2.4,
        )
        self.wait(0.4)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    PolesAndHulls(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
