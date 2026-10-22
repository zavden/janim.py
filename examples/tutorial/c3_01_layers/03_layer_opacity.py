"""Course 3 · 1.3 — Layer opacity vs mobject opacity

Two different things wear the same word, and choosing wrong is a classic
source of "why does that look wrong":

  m.set_fill(opacity=0.5)          per MOBJECT. Each shape becomes
                                   translucent, so shapes inside the same
                                   group show through EACH OTHER.
  Layer(*ms, opacity=0.5)          per LAYER. The group is composited as one
                                   picture and THEN faded, so overlaps
                                   inside it stay opaque.

The layer's opacity scales the PREMULTIPLIED texture, which is exactly what
After Effects does — and it is why a half-transparent layer never shows its
own internal seams.

Use the first when the shapes really are translucent (glass, shadows), the
second when a whole thing should fade as a thing (a panel, a diagram, a
subtitle card).

    python examples/tutorial/c3_01_layers/03_layer_opacity.py
"""

from pathlib import Path

from janim import *
from janim.math import sin

PREVIEW_T = 2.4


def cluster(x, opacity):
    """Three overlapping discs, as one group."""
    g = VGroup()
    for dx, dy, colour in ((-0.55, 0.3, "#3D7BC0"), (0.55, 0.3, "#E8A33D"), (0.0, -0.55, "#7FDD58")):
        c = Circle(radius=0.95)
        c.set_fill(colour, opacity)
        c.set_stroke(opacity=0)
        c.move_to((x + dx, dy - 0.1, 0))
        g.add(c)
    return g


class LayerOpacity(Scene):
    def construct(self):
        title = Text("mobject opacity shows the seams; layer opacity does not", size=0.4, color=GREY_A)
        title.to_edge(UP, buff=0.3)

        per_mobject = cluster(-3.3, 0.5)     # each disc is translucent
        per_layer = cluster(3.3, 1.0)        # opaque discs, faded as a layer

        l1 = Text("set_fill(opacity=0.5)", size=0.34, color=GREY_B)
        l2 = Text("Layer(…, opacity = 0.5)", size=0.34, color=GREY_B)
        l1.move_to((-3.3, -2.5, 0))
        l2.move_to((3.3, -2.5, 0))

        layer = Layer(per_layer, opacity=0.5)
        clock = VGroup()

        def breathe(m, dt):
            if dt <= 0:
                return
            layer.opacity = 0.5 + 0.45 * sin(1.4 * self.t) ** 2

        clock.add_updater(breathe)
        self.add(clock)

        self.use_composition(
            Composition(
                Layer(per_mobject),
                layer,
                Layer(title, l1, l2),
                background=(0.04, 0.05, 0.07, 1),
            ),
        )

        self.wait(3.0)
        print("layer opacity at the end:", round(layer.opacity, 3))


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    LayerOpacity(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
