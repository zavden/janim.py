"""Course 3 · 2.6 — Bloom (the glow)

    Bloom(threshold=0.6, intensity=1.0, sigma=0.15)

Three steps, and knowing them is what lets you tune it instead of guessing:

  1. BRIGHT PASS — keep only what is brighter than `threshold`
     (`max(colour − threshold, 0)`), so a mid-grey contributes nothing;
  2. a PYRAMID of blurs at σ, 2σ and 4σ, summed. One σ gives a halo with a
     visible edge; three octaves give the soft falloff a lens has;
  3. ADD the halo back at `intensity`.

How to tune it: `threshold` decides WHAT glows (lower it and everything
does), `sigma` decides HOW FAR the light spills, `intensity` decides how
bright the spill is. If the picture looks washed out, the threshold is too
low — raise it before lowering the intensity.

Bloom on a layer whose blend is "add" is the classic neon recipe; that is
lesson 2.8.

    python examples/tutorial/c3_02_blur_and_glow/06_bloom.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.4


def pair(x):
    """A bright glyph and a mid-grey one: the threshold's whole point."""
    g = VGroup()
    hot = Star(6, outer_radius=0.85)
    hot.set_fill("#FFF6C0", 1.0)
    hot.set_stroke(opacity=0)
    hot.move_to((x, 0.75, 0))
    g.add(hot)
    cold = Star(6, outer_radius=0.85)
    cold.set_fill("#4A5568", 1.0)
    cold.set_stroke(opacity=0)
    cold.move_to((x, -1.1, 0))
    g.add(cold)
    return g


class BloomLesson(Scene):
    def construct(self):
        title = Text("threshold picks WHAT glows; sigma, how far", size=0.42, color=GREY_A)
        title.to_edge(UP, buff=0.3)

        cases = (
            ("no bloom", None),
            ("threshold 0.6", Bloom(threshold=0.6, intensity=1.2, sigma=0.10)),
            ("sigma 0.25", Bloom(threshold=0.6, intensity=1.2, sigma=0.25)),
            ("threshold 0.15", Bloom(threshold=0.15, intensity=1.2, sigma=0.10)),
        )

        layers = []
        labels = []
        for k, (name, bloom) in enumerate(cases, 1):
            x = -5.1 + 3.4 * (k - 1)
            layers.append(Layer(pair(x), effects=[] if bloom is None else [bloom]))
            lab = Text(name, size=0.3, color=GREY_B)
            lab.move_to((x, -2.6, 0))
            labels.append(lab)
        layers.append(Layer(title, *labels))

        self.use_composition(Composition(*layers, background=(0.02, 0.02, 0.04, 1)))
        self.wait(1.5)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    BloomLesson(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
