"""Course 1 · 1.6 — Layers (draw order)

The scene draws its list in order, and each mobject draws its family in DFS
order. So "ordering" is REORDERING — there is no z-buffer in 2D (that is
`apply_depth_test`, and it belongs to 3D).

Three tools, and the third one has a tooth:

    add order            last added draws on top
    m.set_z_index(z)     higher draws later; the sort is STABLE, so equal
                         z-indices keep insertion order. Touches DRAWING only.
    self.bring_to_front  moves the mobject in `self.mobjects` — which is the
    self.bring_to_back   UPDATE order as well as the draw order.

THE TOOTH: `self.bring_to_back(trail)` puts the trail's updater FIRST, so it
samples the previous frame's position and lags exactly one frame behind what
it follows (0.618 scene units for a point crossing a circle of radius 2 at
20 fps, as measured). `trail.set_z_index(-1)` gives the same picture with
no lag. Prefer it whenever an updater reads another mobject's state.

    python examples/tutorial/c1_01_basics/06_layers.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 2.0


def stack(x):
    """Three overlapping discs, left to right, added in the order given."""
    a = Circle(radius=0.9)
    a.set_fill("#2C5F8A", 1.0)
    b = Circle(radius=0.9)
    b.set_fill("#E8A33D", 1.0)
    c = Circle(radius=0.9)
    c.set_fill(GREEN, 1.0)
    for mob, dx in ((a, -0.5), (b, 0.0), (c, 0.5)):
        mob.set_stroke(BLACK, width=3.0)
        mob.move_to((x + dx, 0.3, 0))
    return a, b, c


class Layers(Scene):
    def construct(self):
        title = Text("draw order is list order", size=0.5, color=GREY_A)
        title.to_edge(UP, buff=0.4)
        self.add(title)

        # Left: plain add order — green last, so green on top.
        a1, b1, c1 = stack(-3.6)
        self.add(a1, b1, c1)

        # Right: the same three, added in the same order, but the BLUE one is
        # given a z-index so it lands on top. Nothing else changed.
        a2, b2, c2 = stack(3.6)
        self.add(a2, b2, c2)
        a2.set_z_index(1)

        for x, text in ((-3.6, "add order"), (3.6, "blue.set_z_index(1)")):
            label = Text(text, size=0.36, color=GREY_B)
            label.move_to((x, -1.6, 0))
            self.add(label)

        # A moving dot with its trail, laid out the RIGHT way: the trail is
        # added AFTER the dot it follows (so it samples this frame's position)
        # and sent behind with set_z_index, which does not touch the update
        # order.
        path = Circle(radius=0.55)
        path.move_to((0, -2.4, 0))
        dot = Dot((0.55, -2.4, 0), radius=0.11)
        dot.set_fill(YELLOW)
        trail = TracedPath(
            dot.get_center,
            stroke_color=YELLOW,
            stroke_width=3.0,
        )
        self.add(dot, trail)          # dot FIRST, trail after: no one-frame lag
        trail.set_z_index(-1)         # …and behind, without reordering updaters

        self.play(MoveAlongPath(dot, path, rate_func=linear), run_time=2.5)
        self.wait(0.4)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    Layers(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
