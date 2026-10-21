"""Course 3 · 1.6 — Track mattes

    Layer(content, matte="alpha" | "luma" | "alpha_inv" | "luma_inv")

The layer CONSUMES THE NEXT LAYER IN THE LIST as its matte: that next layer
is not drawn, its alpha (or luminance) becomes the coverage of this one.
After Effects spells it "the layer above"; here the list runs bottom-to-top,
so it is the following entry.

    "alpha"     where the matte has alpha, the content shows
    "luma"      where the matte is BRIGHT, the content shows
    "alpha_inv" / "luma_inv"     the same, inverted

Matte vs mask, since both cut things out:

  Mask(*shapes)     belongs to the layer, is built from mobjects you name,
                    and takes `feather`, `hard`, `invert`, `luma`.
  matte="luma"      consumes a whole LAYER, so the cutter can itself be a
                    precomp with effects — a gradient, a noise field, a
                    blurred silhouette. That is the reason it exists.

    python examples/tutorial/c3_01_layers/06_track_matte.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 2.4


class TrackMatte(Scene):
    def construct(self):
        title = Text("a matte is a whole layer used as coverage", size=0.42, color=GREY_A)
        title.to_edge(UP, buff=0.3)

        def band(x):
            """A band of colour to be cut."""
            g = VGroup()
            for k, c in enumerate(color_gradient(["#FF5E5E", "#FFD25E", "#7FDD58", "#58C4DD"], 24), 1):
                r = Rectangle(width=0.19, height=3.0)
                r.set_fill(c, 1.0)
                r.set_stroke(opacity=0)
                r.move_to((x - 2.3 + 0.2 * (k - 1), -0.1, 0))
                g.add(r)
            return g

        # LEFT · "alpha" — the matte's shape cuts the band.
        letters = Text("MATTE", size=1.1)
        letters.move_to((-3.4, -0.1, 0))

        # RIGHT · "luma" — a gradient's BRIGHTNESS becomes a soft gradient wipe.
        ramp = Rectangle(width=4.8, height=3.0)
        ramp.set_fill_by_gradient(BLACK, WHITE)
        ramp.set_fill(opacity=1.0)
        ramp.set_stroke(opacity=0)
        ramp.move_to((3.4, -0.1, 0))

        l1 = Text('matte = "alpha"', size=0.32, color=GREY_B)
        l2 = Text('matte = "luma"', size=0.32, color=GREY_B)
        l1.move_to((-3.4, -2.4, 0))
        l2.move_to((3.4, -2.4, 0))

        self.use_composition(
            Composition(
                Layer(band(-3.4), matte="alpha"),   # ← consumes the NEXT layer
                Layer(letters),                      #    …which is this one
                Layer(band(3.4), matte="luma"),
                Layer(ramp),
                Layer(title, l1, l2),
                background=(0.02, 0.03, 0.05, 1),
            ),
        )

        self.wait(2.5)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    TrackMatte(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
