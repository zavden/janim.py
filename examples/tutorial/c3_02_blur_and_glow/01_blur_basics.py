"""Course 3 · 2.1 — Blur

    Blur(sigma, in_pixels=False)

A separable Gaussian in two passes (horizontal, then vertical), which is
what makes it O(2r) per pixel instead of O(r²).

sigma IS IN SCENE UNITS by default, converted through the camera. That is the
decision worth copying into your own effects: a blur specified in pixels
looks different at 480p and at 1080p, so the preview would lie about the
film. `in_pixels=True` is there for the rare case where you really mean
pixels.

Two numbers behind it: the kernel radius is `ceil(3σ)` (three sigmas cover
99.7% of the mass) clamped to 63, and below σ = 0.3 px the pass is SKIPPED —
it would be imperceptible, and skipping keeps σ → 0 continuous instead of
quantising to a one-pixel kernel.

    python examples/tutorial/c3_02_blur_and_glow/01_blur_basics.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.4


def card(x):
    """A test card: hard edges, thin lines and text — everything a blur shows off."""
    g = VGroup()
    sq = Square(side_length=1.5)
    sq.set_fill("#E8A33D", 1.0)
    sq.set_stroke(opacity=0)
    sq.move_to((x, 0.85, 0))
    g.add(sq)
    for k in range(7):
        l = Line((x - 1.1 + 0.36 * k, -0.6, 0), (x - 1.1 + 0.36 * k, -1.7, 0))
        l.set_stroke("#58C4DD", width=3.0)
        g.add(l)
    t = Text("edge", size=0.42, color=WHITE)
    t.move_to((x, -2.2, 0))
    g.add(t)
    return g


class BlurBasics(Scene):
    def construct(self):
        title = Text("sigma is in SCENE UNITS, so the look survives the resolution", size=0.38, color=GREY_A)
        title.to_edge(UP, buff=0.3)

        sigmas = (0.0, 0.03, 0.09, 0.22)
        layers = []
        labels = []
        for k, sigma in enumerate(sigmas, 1):
            x = -5.1 + 3.4 * (k - 1)
            layers.append(Layer(card(x), effects=[] if sigma == 0 else [Blur(sigma)]))
            lab = Text("no blur" if sigma == 0 else f"Blur({sigma})", size=0.32, color=GREY_B)
            lab.move_to((x, -3.0, 0))
            labels.append(lab)
        layers.append(Layer(title, *labels))

        self.use_composition(Composition(*layers, background=(0.02, 0.03, 0.05, 1)))
        self.wait(1.5)
        print(
            "at 854 px wide, 1 scene unit is",
            round(854 / FRAME_WIDTH, 1),
            "px — so Blur(0.09) is a",
            round(0.09 * 854 / FRAME_WIDTH, 1),
            "px sigma",
        )


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    BlurBasics(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
