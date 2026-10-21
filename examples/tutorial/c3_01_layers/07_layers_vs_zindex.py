"""Course 3 · 1.7 — Layers vs z-index: which one you want

Both change what is drawn on top. They are not interchangeable.

  m.set_z_index(z)       ORDER inside one texture. Cheap (a stable sort of a
                         list), works anywhere, and it is what you want 90%
                         of the time.
  a separate Layer       a texture of its OWN. Costs one fullscreen buffer,
                         and buys the only things a single framebuffer
                         cannot give: a blend mode, an effect applied to
                         this group and nothing else, a mask, a matte, and
                         a group opacity that does not show internal seams.

Rule of thumb: reach for z-index for ORDER, for a layer for TREATMENT.

And the trap from course 1, which is really about update order:
`bring_to_front`/`bring_to_back` move the mobject inside `self.mobjects`,
which is the UPDATE order too. A `TracedPath` sent to the back with
`bring_to_back` starts sampling the previous frame's position and lags a
whole frame behind what it follows. `set_z_index` does not touch updaters.

    python examples/tutorial/c3_01_layers/07_layers_vs_zindex.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.6


def bars(x):
    """Three overlapping bars at x, in a single group."""
    g = VGroup()
    for k, colour in enumerate(("#3D7BC0", "#E8A33D", "#7FDD58"), 1):
        r = RoundedRectangle(width=2.6, height=0.9, corner_radius=0.18)
        r.set_fill(colour, 1.0)
        r.set_stroke(opacity=0)
        r.move_to((x - 0.35 + 0.35 * k, 0.5 - 0.42 * k, 0))
        g.add(r)
    return g


class LayersVsZIndex(Scene):
    def construct(self):
        title = Text("z-index for ORDER · a layer for TREATMENT", size=0.42, color=GREY_A)
        title.to_edge(UP, buff=0.3)

        # LEFT: one layer, ordering done with z-index. The middle bar is lifted.
        left = bars(-3.5)
        left[1].set_z_index(1)

        # RIGHT: the same three bars, but the middle one lives on its OWN layer
        # with a blend mode and a glow — impossible with z-index alone.
        right = bars(3.5)
        middle = right[1]
        right.remove(middle)

        l1 = Text("bar.set_z_index(1)", size=0.32, color=GREY_B)
        l2 = Text("its own layer: :add + Bloom", size=0.32, color=GREY_B)
        l1.move_to((-3.5, -2.6, 0))
        l2.move_to((3.5, -2.6, 0))

        self.use_composition(
            Composition(
                Layer(left),
                Layer(right),
                Layer(
                    middle,
                    blend="add",
                    effects=[Bloom(threshold=0.25, intensity=1.3, sigma=0.13)],
                ),
                Layer(title, l1, l2),
                background=(0.03, 0.04, 0.06, 1),
            ),
        )

        self.wait(2.0)
        print(
            "left group children:",
            len(left.submobjects),
            "· right group children:",
            len(right.submobjects),
            "(the third one moved to a layer of its own)",
        )


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    LayersVsZIndex(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
