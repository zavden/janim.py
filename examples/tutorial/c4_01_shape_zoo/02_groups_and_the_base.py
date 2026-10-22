"""Course 4 · 1.2 — Groups, the base type, and building a path by hand

Three things live under every shape in lesson 1.1:

  VMobject  the base: an EMPTY path plus a factory style. Build one by hand
            with the path API and you have a shape the engine cannot tell
            from a Circle.
  VGroup    a parent of VMobjects. Styling it styles the family.
  Group     a parent of ANYTHING — a Surface, a ValueTracker, a camera
            frame. It moves and animates like a VGroup, and like manim's
            Group: the verbs recurse into the members that can take them,
            and a member that cannot (a ValueTracker has no position) is
            left alone rather than throwing. What VGroup gives on top is
            STYLE: `set_fill` on a Group has nothing generic to set.

`Mobject` is the abstract supertype the three share. The raw `VMobject(...)`
constructor the shape zoo is written on is the extension seam: the last shape
below is a plain `VMobject` built by hand.

    python examples/tutorial/c4_01_shape_zoo/02_groups_and_the_base.py
"""

from pathlib import Path

from janim import *
from janim.math import cos, linear_range, sin

PREVIEW_T = 1.2

CORNERS = [(-1, -1, 0), (0, 1, 0), (1, -1, 0), (1.6, 0.6, 0)]


class GroupsAndTheBase(Scene):
    def construct(self):
        title = Text("a path built by hand is a first-class shape", size=0.4, color=GREY_A)
        title.to_edge(UP, buff=0.25)

        # ── a VMobject built one segment at a time ────────────────────────────
        hand = VMobject(color=YELLOW, stroke_width=4.0)
        hand.start_new_path((-2, -1, 0))
        hand.add_line_to((-1, 1, 0))
        hand.add_quadratic_bezier_to((0, 2, 0), (1, 1, 0))
        hand.add_arc_to((2, -1, 0), -TAU / 6)
        hand.shift(3.2 * LEFT + 0.6 * UP)

        # a second subpath in the same mobject: one shape, two contours
        hand.add_subpath(Circle(radius=0.35, arc_center=ORIGIN).get_points())

        # ── the same points, described three ways ─────────────────────────────
        corners = VMobject(color=TEAL, stroke_width=3.0)
        corners.set_points_as_corners(CORNERS)
        smooth_one = corners.copy()
        smooth_one.set_points_smoothly(CORNERS)
        smooth_one.set_stroke(PINK)
        jagged = smooth_one.copy()
        jagged.make_jagged()
        jagged.set_stroke(ORANGE)
        smoothed = corners.copy()
        smoothed.make_smooth()
        smoothed.set_stroke(GREEN)

        lines = VGroup(corners, smooth_one, jagged, smoothed)
        lines.arrange(DOWN, buff=0.25)
        lines.move_to((2.6, 0.4, 0))
        lines.scale(0.75)

        # a VGroup takes the setters of a single mobject and passes them down
        lines.set_stroke(width=3.0)

        # Group holds anything at all — here a VMobject and a point cloud
        cloud = GlowDots(
            [(0.35 * cos(t), 0.35 * sin(t), 0) for t in linear_range(0, TAU, 24)],
            radius=0.06,
            color=GOLD,
        )
        # Group moves as one, exactly like VGroup — a cloud and a shape together
        sq = Square(side_length=0.9)
        mixed = Group(sq, cloud)
        mixed.move_to((0, -2.6, 0))

        note = Text(
            "is_smooth: " + str(smoothed.is_smooth()).lower()
            + "   ·   subpaths: " + str(len(hand.get_subpaths()))
            + "   ·   VMobject() is the seam",
            size=0.26,
            color=GREY_B,
        )
        note.to_edge(DOWN, buff=0.3)

        raw = VMobject(color=MAROON_B, stroke_width=2.0)       # the raw constructor
        raw.set_points_by_ends((-1, 0, 0), (1, 0, 0), path_arc=TAU / 4)
        raw.move_to((-3.2, -2.4, 0))

        self.add(title, note)
        self.play(ShowCreation(hand), ShowCreation(lines, lag_ratio=0.1), run_time=1.4)
        # a Group cannot be animated as one — its members can
        self.add(cloud)
        self.play(FadeIn(sq), ShowCreation(raw), run_time=0.8)
        # …and animates as one: an animation of FUNCTIONS over the whole container
        self.play(mixed.animate.shift(0.3 * RIGHT), run_time=0.4)
        self.wait(0.4)


if __name__ == "__main__":
    # The tutorial's default settings are used here.
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    GroupsAndTheBase(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
