"""Course 3 · 2.3 — BoxBlur

    BoxBlur(radius)        radius in scene units

One horizontal pass and one vertical pass with UNIFORM weights. It is the
cheapest blur there is (no exponentials, no weight table) and it looks it:
a box kernel has a hard cut-off, so a bright edge leaves a visible square
halo where a Gaussian would fall off smoothly.

The useful fact: chaining THREE box blurs approximates a Gaussian to within
a few percent. That is the central limit theorem doing the work — convolving
a uniform distribution with itself three times is already close to normal —
and it is how most real-time engines fake a Gaussian.

Reach for `BoxBlur` when you want the boxy look (a pixel-art bloom, a cheap
shadow) or when you are chaining; reach for `Blur` when you want a blur.

    python examples/tutorial/c3_02_blur_and_glow/03_box_blur.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.4


def target(x):
    """A bright cross on a dark field: the shape that shows a kernel's profile."""
    g = VGroup()
    for w, h in ((1.8, 0.24), (0.24, 1.8)):
        r = Rectangle(width=w, height=h)
        r.set_fill(WHITE, 1.0)
        r.set_stroke(opacity=0)
        r.move_to((x, 0.1, 0))
        g.add(r)
    dot = Circle(radius=0.42)
    dot.set_fill("#FFD25E", 1.0)
    dot.set_stroke(opacity=0)
    dot.move_to((x, 0.1, 0))
    g.add(dot)
    return g


class BoxBlurLesson(Scene):
    def construct(self):
        title = Text("a box kernel cuts off; a Gaussian falls off", size=0.42, color=GREY_A)
        title.to_edge(UP, buff=0.3)

        cases = (
            ("no blur", []),
            ("BoxBlur(0.08)", [BoxBlur(0.08)]),
            ("BoxBlur ×3", [BoxBlur(0.08), BoxBlur(0.08), BoxBlur(0.08)]),
            ("Blur(0.08)", [Blur(0.08)]),
        )

        layers = []
        labels = []
        for k, (name, fx) in enumerate(cases, 1):
            x = -5.1 + 3.4 * (k - 1)
            layers.append(Layer(target(x), effects=fx))
            lab = Text(name, size=0.32, color=GREY_B)
            lab.move_to((x, -2.2, 0))
            labels.append(lab)
        layers.append(Layer(title, *labels))

        self.use_composition(Composition(*layers, background=(0.02, 0.03, 0.05, 1)))
        self.wait(1.5)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    BoxBlurLesson(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
