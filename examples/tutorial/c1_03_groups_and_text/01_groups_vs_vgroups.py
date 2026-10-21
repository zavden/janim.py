"""Course 1 · 3.1 — Group vs VGroup

    VGroup(*mobs)   a VMobject that holds VMobjects. It accepts transforms
                    and style (`shift`, `scale`, `set_color` reach every
                    child), it can be Transformed, and it has a bounding box
                    — so all the relative layout works on it.
    Group(*mobs)    holds ANY Mobject: a ValueTracker, a CameraFrame, a
                    Surface, an ImageMobject. It draws nothing itself and
                    carries no style; it exists so things can live and
                    update together.

Rule of thumb: if everything in it is vector geometry, use VGroup. The
moment one member is not, `VGroup.add` refuses it (the vector restriction of
ManimGL) — that is when Group is the answer. `AnimationGroup` picks between
them for you, for exactly this reason.

Also here: a group is a real parent. `g[1]` is its second child, `g[0:3]` a
memoised VGroup of the first three, and `g.get_family()` is the DFS the
renderer and Transform both walk.

    python examples/tutorial/c1_03_groups_and_text/01_groups_vs_vgroups.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 2.0


class GroupsVsVGroups(Scene):
    def construct(self):
        title = Text(
            "VGroup transforms · Group only gathers",
            size=0.48,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.4)
        self.add(title)

        # ── a VGroup: geometry, so it moves and paints as one ────────────
        tiles = VGroup()
        for k in range(1, 7):
            square = Square(side_length=0.8)
            square.set_fill("#2C5F8A", 1.0)
            square.set_stroke("#0B0E14", width=3.0)
            tiles.add(square)
        tiles.arrange_in_grid(
            n_rows=2,
            n_cols=3,
            buff=0.15,
        )
        tiles.move_to(3.4 * LEFT)

        print(
            f"children: {len(tiles.submobjects)}"
            f" · family (DFS, parent included): {len(tiles.get_family())}",
        )

        # ── a Group: a tracker and a surface, which no VGroup could hold ─
        knob = ValueTracker(0.4)
        ball = Sphere(radius=0.9, resolution=(61, 31))
        ball.set_color("#E8A33D")
        # A Surface answers the whole transform family, `move_to` included.
        ball.move_to((3.4, 0.2, 0))
        ball.apply_depth_test()
        mixed = Group(knob, ball)
        ball.add_updater(lambda m: m.set_color(opacity=knob.get_value()))

        self.add(tiles, mixed)

        # One animation over the whole VGroup: every child follows.
        self.play(tiles.animate.rotate(TAU / 16).scale(1.15), run_time=1.2)
        # Addressing children: `tiles[1]` is a child, `tiles[3:6]` a memoised
        # group (the 4th to 6th children).
        self.play(Indicate(tiles[3:6], color=YELLOW), run_time=1.0)
        # The Group's members are driven by whatever drives them — here, the
        # tracker the sphere's updater reads.
        self.play(knob.animate.set_value(1.0), run_time=1.0)
        self.wait(0.4)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    GroupsVsVGroups(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
