"""Course 2 · 1.1 — Alpha updaters

An UPDATER runs every frame for as long as the mobject is in the scene. An
ALPHA updater runs only while an animation is playing, and it is handed how
far through that animation it is:

    UpdateFromAlphaFunc(m, lambda m, a: …)   α ∈ [0,1], rate function applied
    UpdateFromFunc(m, lambda m: …)           no α — for "follow that other
                                             mobject while IT is animated"

`UpdateFromAlphaFunc` takes NO snapshot of the mobject, and that is the
whole point: every other animation captures a start and an end and lerps
between them, which needs the mobject to be interpolable. This one does not
— so it drives a `Surface`, an `ImageMobject`, a camera, or a type of your
own, with no contract to implement.

When to reach for which:

  the state is a closed form of α          → UpdateFromAlphaFunc
  the state depends on something else       → UpdateFromFunc
  the state must persist after the animation → add_updater (lesson 1.2)

    python examples/tutorial/c2_01_updaters_and_custom_mobjects/01_alpha_updaters.py
"""

from pathlib import Path

import numpy as np

from janim import *
from janim.core._julia_math import cos, sin

PREVIEW_T = 2.0


def sphere_of(r):
    """A uv sphere of radius `r`.

    `cos`/`sin` come from janim.core._julia_math, so every vertex is the same on
    any machine."""
    return Surface(
        lambda u, v: (r * cos(u) * sin(v), r * sin(u) * sin(v), -r * cos(v)),
        u_range=(0.0, TAU),
        v_range=(0.0, PI),
        resolution=(61, 31),
        color="#2C5F8A",
    )


def breathe(m, a):
    """Rebuild the mesh's radius from α — a Transform could not do this,
    because a Surface is not interpolable."""
    r = 0.9 + 0.35 * sin(2 * TAU * a)
    c = m.get_center()
    s = sphere_of(r)
    m.points[:] = s.points + c
    m.d_normal_points[:] = s.d_normal_points + c
    # A Surface caches its bounding box: after writing the arrays in place,
    # say so, or the next `get_center` reads the stale box.
    m.note_changed_data()


class AlphaUpdaters(Scene):
    def construct(self):
        title = Text(
            "alpha updaters take no snapshot",
            size=0.46,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.35)
        self.add(title)

        # A Surface cannot be Transformed (it does not implement the contract),
        # but an alpha updater drives it happily.
        blob = Surface(
            lambda u, v: (cos(u) * sin(v), sin(u) * sin(v), -cos(v)),
            u_range=(0.0, TAU),
            v_range=(0.0, PI),
            resolution=(61, 31),
            color="#2C5F8A",
        )
        # A Float32 difference, like the mesh itself.
        blob.shift(np.array((-3.4, -0.3, 0), dtype=np.float32) - blob.get_center())
        blob.apply_depth_test()
        self.add(blob)

        # A dot travelling a Lissajous figure — a closed form of α, so no state.
        dot = Dot(ORIGIN, radius=0.13)
        dot.set_fill(color="#FFD25E")
        trail = TracedPath(
            dot.get_center,
            stroke_color="#FFD25E",
            stroke_width=2.5,
        )
        self.add(dot, trail)
        trail.set_z_index(-1)

        def lissajous(m, a):
            m.move_to((3.2 + 1.6 * sin(3 * TAU * a), -0.3 + 1.3 * sin(2 * TAU * a), 0))

        # A label that FOLLOWS the dot: it has no α of its own, it just reads the
        # dot each frame. That is UpdateFromFunc.
        tag_ = Text("(x, y)", size=0.34, color=GREY_B)
        self.add(tag_)

        def follow(m):
            m.move_to(dot.get_center() + np.array((0, 0.45, 0), dtype=np.float32))

        self.play(
            AnimationGroup(
                UpdateFromAlphaFunc(blob, breathe),
                UpdateFromAlphaFunc(dot, lissajous),
                UpdateFromFunc(tag_, follow),
                run_time=4.0,
            ),
            run_time=4.0,
        )
        self.wait(0.4)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    AlphaUpdaters(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
