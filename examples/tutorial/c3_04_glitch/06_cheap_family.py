"""Course 3 · 4.6 — The cheap family

Four effects that cost one pass each and are used constantly:

    ColorAdjust(brightness=1, contrast=1, saturation=1, hue=0)
    Pixelate(size=0.2)
    Vignette(amount=0.5, radius=0.5, feather=0.4)
    Grain(amount=0.15, seed=1, rate=1, levels=8)

`ColorAdjust` is ONE dataclass with four dials rather than four, because
they are always used together and each alone would pay for its own
fullscreen pass. `brightness` multiplies, `contrast` pivots about 0.5,
`saturation` mixes towards the luma, and `hue` rotates in radians about the
grey axis (Rodrigues) — so greys are a fixed point and the rotation is
exactly 2π-periodic. All four at identity → the pass is skipped.

`Pixelate`'s `size` is in scene units, so "zoom until you see the pixels"
looks the same at any resolution. Every cell takes the colour of its CENTRE,
so a cell really is one colour.

`Vignette`'s `radius` and `feather` are fractions of the half-diagonal: the
centre is untouched exactly and the corner falls by exactly `amount`.

`Grain`'s `levels` quantises the noise factor to exact binary steps. That is
not decoration: a continuous factor over a colour leaves ~0.3% of pixels
within one ULP of the 8-bit rounding edge, and those flip between runs.

    python examples/tutorial/c3_04_glitch/06_cheap_family.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.2


def tile(x):
    """A photographic-looking tile."""
    group = VGroup()
    sky = Rectangle(width=2.9, height=2.1)
    sky.set_fill_by_gradient("#1B4F8C", "#39D0FF")
    sky.set_fill(opacity=1.0)
    sky.set_stroke(opacity=0)
    sky.move_to((x, 0.5, 0))
    group.add(sky)
    sun = Circle(radius=0.36)
    sun.set_fill("#FFF0B0", 1.0)
    sun.set_stroke(opacity=0)
    sun.move_to((x + 0.8, 1.1, 0))
    group.add(sun)
    hill = Triangle(radius=1.0)
    hill.set_fill("#2F7A46", 1.0)
    hill.set_stroke(opacity=0)
    hill.move_to((x - 0.3, -0.1, 0))
    group.add(hill)
    return group


class CheapFamily(Scene):
    def construct(self):
        title = Text("four dials, one pass each", size=0.44, color=GREY_A)
        title.to_edge(UP, buff=0.3)

        cases = (
            ("as rendered", []),
            ("ColorAdjust(hue = 2.1)", [ColorAdjust(hue=2.1, saturation=1.3)]),
            ("Pixelate(0.13)", [Pixelate(0.13)]),
            (
                "Vignette + Grain",
                [
                    Vignette(amount=0.75, radius=0.35),
                    Grain(amount=0.28, seed=9),
                ],
            ),
        )

        layers = []
        labels = []
        for k, (name, fx) in enumerate(cases, start=1):
            x = -5.1 + 3.4 * (k - 1)
            layers.append(Layer(tile(x), effects=fx))
            label = Text(name, size=0.28, color=GREY_B)
            label.move_to((x, -1.6, 0))
            labels.append(label)
        layers.append(Layer(title, *labels))

        self.use_composition(
            Composition(
                *layers,
                background=(0.02, 0.03, 0.05, 1.0),
            ),
        )
        self.wait(1.5)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    CheapFamily(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
