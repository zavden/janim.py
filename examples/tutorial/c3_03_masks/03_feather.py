"""Course 3 · 3.3 — Feather: the soft edge

    Mask(shape, feather=0.25)        σ in SCENE UNITS

`feather` blurs THE MASK, not the layer. The layer keeps every bit of its
detail; what softens is the coverage, so the content fades out towards the
edge instead of stopping at it.

That distinction matters when the layer is also blurred: blurring the layer
and feathering its mask look nothing alike. The first smears the content;
the second leaves it sharp and dissolves it.

Numbers to keep: σ is in scene units like every other size here, and the
usable range is small — 0.05 is a soft edge, 0.4 is a vignette, and past
about 1.0 there is no hard part of the mask left at all.

    python examples/tutorial/c3_03_masks/03_feather.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.4


def detail(x):
    """A photograph stand-in: something with fine detail to keep."""
    g = VGroup()
    colours = color_gradient(["#FFD25E", "#FF3D8B"], 10)
    for k in range(10):
        c = Circle(radius=0.16 + 0.16 * k)
        c.set_stroke(color=colours[k], width=3.0)
        c.set_fill(opacity=0)
        c.move_to((x, -0.1, 0))
        g.add(c)
    return g


class Feather(Scene):
    def construct(self):
        title = Text(
            "feather blurs the MASK, not the layer",
            size=0.44,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.3)

        feathers = (0.0, 0.06, 0.25)
        xs = (-5.1, -1.7, 1.7, 5.1)          # four columns, so nothing collides
        layers = []
        labels = []
        for k, f in enumerate(feathers):
            x = xs[k]
            window = Circle(radius=1.25, fill_opacity=1.0)
            window.move_to((x, -0.1, 0))
            layers.append(Layer(detail(x), mask=Mask(window, feather=f)))
            lab = Text(f"feather = {f}", size=0.3, color=GREY_B)
            lab.move_to((x, -2.4, 0))
            labels.append(lab)

        # …and the comparison that makes the point: the SAME window, but the LAYER
        # blurred instead of the mask feathered.
        x = xs[3]
        window = Circle(radius=1.25, fill_opacity=1.0)
        window.move_to((x, -0.1, 0))
        layers.append(
            Layer(
                detail(x),
                mask=Mask(window),
                effects=[Blur(0.09)],
            ),
        )
        lab = Text("the LAYER blurred", size=0.3, color="#FF5E5E")
        lab.move_to((x, -2.4, 0))
        labels.append(lab)

        layers.append(Layer(title, *labels))
        self.use_composition(
            Composition(
                *layers,
                background=(0.02, 0.03, 0.05, 1),
            ),
        )
        self.wait(1.5)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    Feather(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
