"""Course 3 · 1.2 — Blend modes

    Layer(m, blend="normal" | "add" | "multiply" | "screen" | "overlay")

The compositor uses the W3C / PDF / SVG equation over PREMULTIPLIED colour:

    C = (1−αs)·Cb + (1−αb)·Cs + αs·αb·B(Cb, Cs)
    α = αs + αb·(1−αs)

where B is the mode over non-premultiplied colour:

    normal    B = Cs                       (collapses to Porter-Duff `over`)
    multiply  B = Cb·Cs                    (darkens; white is the identity)
    screen    B = Cb + Cs − Cb·Cs          (lightens; black is the identity)
    overlay   multiply or screen, per channel, depending on the BACKDROP
    add       a plain sum of premultiplied values — the classic glow mode,
              and the only one that is not the equation above

Blending happens in LINEAR light: each layer's premultiplied sRGB is decoded
on the way in and the result is encoded once on the way out, so the equation
above acts on physically meaningful values (red + green + blue adds up to
real white, not a muddy grey).

    python examples/tutorial/c3_01_layers/02_blend_modes.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.2

MODES = ("normal", "add", "multiply", "screen", "overlay")


class BlendModes(Scene):
    def construct(self):
        title = Text("the same two shapes, five equations", size=0.44, color=GREY_A)
        title.to_edge(UP, buff=0.3)

        def pair(k):
            """A backdrop disc and a source disc, at column `k` (1-based)."""
            x = -5.4 + 2.7 * (k - 1)
            b = Circle(radius=0.95)
            b.set_fill("#3D7BC0", 1.0)
            b.set_stroke(opacity=0)
            b.move_to((x - 0.32, 0.1, 0))
            s = Circle(radius=0.95)
            s.set_fill("#E8A33D", 1.0)
            s.set_stroke(opacity=0)
            s.move_to((x + 0.32, -0.35, 0))
            lab = Text(":" + MODES[k - 1], size=0.34, color=GREY_B)
            lab.move_to((x, -2.1, 0))
            return b, s, lab

        layers = []
        labels = []
        for k in range(1, 6):
            b, s, lab = pair(k)
            layers.append(Layer(b))                        # the backdrop
            layers.append(Layer(s, blend=MODES[k - 1]))    # …and the source over it
            labels.append(lab)
        layers.append(Layer(title, *labels))

        self.use_composition(Composition(*layers, background=(0.05, 0.05, 0.06, 1)))
        self.wait(1.5)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    BlendModes(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
