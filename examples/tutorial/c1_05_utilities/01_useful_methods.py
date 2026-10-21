"""Course 1 · 5.1 — The layout family

ALWAYS place things relative to other things. Hand-written coordinates are
the first thing to break when a label gets longer or a font changes.

    m.next_to(other, RIGHT, buff=…, aligned_edge=…, coor_mask=…)
    m.align_to(other, UP)          match one edge, touch only that axis
    m.to_edge(UP, buff=…) · m.to_corner(UR, buff=…) · m.center()
    m.set_x/set_y/set_z(v, direction=…)      · m.get_coord/set_coord
    m.match_x/match_y/match_z · m.match_width/match_height/match_depth
    m.match_color/match_style
    group.arrange(DOWN, buff=…, aligned_edge=…)
    group.arrange_in_grid(n_rows=…, n_cols=…, buff=…, aligned_edge=…)
    m.replace(other, stretch=…) · m.surround(other, buff=…)

Two things to know:

  · `to_edge` uses the NOMINAL frame (FRAME_X_RADIUS/FRAME_Y_RADIUS), not
    the current camera. Zooming the camera does not move where it lands —
    same as Manim.
  · `next_to` takes a Mobject OR a point, and `aligned_edge` is the second
    dimension: `label.next_to(box, UP, aligned_edge=LEFT)` puts it above
    AND flush left.

    python examples/tutorial/c1_05_utilities/01_useful_methods.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.6


class UsefulMethods(Scene):
    def construct(self):
        title = Text(
            "place things relative to things",
            size=0.46,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.35)

        core = Rectangle(width=2.6, height=1.5)
        core.set_fill(color="#2C5F8A", opacity=1.0)
        core.set_stroke(opacity=0)
        core.move_to(3.0 * LEFT)

        # next_to in four directions, from the same call shape.
        tags = VGroup()
        for d, txt in ((UP, "UP"), (DOWN, "DOWN"), (LEFT, "LEFT"), (RIGHT, "RIGHT")):
            t = Text(txt, size=0.32, color="#58C4DD")
            t.next_to(core, d, buff=0.22)
            tags.add(t)

        # aligned_edge: above AND flush with the left side.
        flush = Text("aligned_edge = LEFT", size=0.28, color="#FFD25E")
        flush.next_to(
            core,
            UP,
            buff=0.9,
            aligned_edge=LEFT,
        )

        # A grid built by layout, not by coordinates.
        cells = VGroup()
        for _ in range(9):
            s = Square(side_length=0.55)
            s.set_fill(color="#37506B", opacity=1.0)
            s.set_stroke(color="#0B0E14", width=2.0)
            cells.add(s)
        cells.arrange_in_grid(
            n_rows=3,
            n_cols=3,
            buff=0.12,
        )
        cells.move_to(3.4 * RIGHT + 0.4 * UP)

        # surround — how SurroundingRectangle is built.
        halo = Rectangle(width=1.0, height=1.0)
        halo.set_stroke(color="#FF5E5E", width=3.0)
        halo.set_fill(opacity=0)
        halo.surround(
            cells,
            buff=0.25,
            stretch=True,
        )

        # A column laid out by arrange, then pinned to a corner.
        column = VGroup()
        for s in ("arrange!", "to_corner!", "buff = 0.2"):
            column.add(Text(s, size=0.3, color=GREY_B))
        column.arrange(
            DOWN,
            buff=0.16,
            aligned_edge=LEFT,
        )
        column.to_corner(DR, buff=0.35)

        self.add(title, core, tags, flush, cells, halo, column)
        self.play(
            AnimationGroup(
                FadeIn(core),
                FadeIn(tags, shift=0.2 * UP),
                ShowCreation(halo),
                FadeIn(cells),
                lag_ratio=0.2,
            ),
            run_time=2.0,
        )
        self.wait(0.5)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    UsefulMethods(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
