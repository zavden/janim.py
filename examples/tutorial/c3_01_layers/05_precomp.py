"""Course 3 · 1.5 — Precomps (a composition inside a layer)

    Layer(inner_composition, blend=, opacity=, effects=, mask=)

A `Composition` can be a layer's CONTENT. It is rendered to its own texture
and then treated like any other layer — natural recursion, no special case
in the compositor.

Why you want it: it is the only way to apply an effect to the RESULT of a
blend. Consider three shapes that must be combined with "multiply" and then
blurred as one picture. Blurring each of them and multiplying afterwards is
a different image; a precomp gets the order right.

It is also how you keep a complicated piece of a scene readable — build the
gauge, the diagram, the lower third as its own Composition, then drop it
into the film as one layer.

The cost is one extra fullscreen texture per level of nesting, which is
cheap; the accumulators are local to each call, so a precomp never tramples
its parent's.

    python examples/tutorial/c3_01_layers/05_precomp.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.8

DISCS = ((-0.5, 0.35, "#FF5E5E"), (0.5, 0.35, "#58C4DD"), (0.0, -0.5, "#FFD25E"))


def ink(x):
    """Three discs that must be MULTIPLIED together — the thing to precomp."""
    cs = []
    for dx, dy, colour in DISCS:
        c = Circle(radius=1.0)
        c.set_fill(colour, 1.0)
        c.set_stroke(opacity=0)
        c.move_to((x + dx, dy - 0.2, 0))
        cs.append(Layer(c, blend="normal" if not cs else "multiply"))
    return Composition(*cs)


class Precomp(Scene):
    def construct(self):
        title = Text("a precomp blurs the RESULT of the blend", size=0.42, color=GREY_A)
        title.to_edge(UP, buff=0.3)

        l1 = Text("multiply, then blur (precomp)", size=0.32, color=GREY_B)
        l2 = Text("blur each, then multiply", size=0.32, color=GREY_B)
        l1.move_to((-3.4, -2.6, 0))
        l2.move_to((3.4, -2.6, 0))

        # LEFT: the three discs are composited FIRST (inside the precomp) and the
        # blur is applied to that one texture.
        left = Layer(ink(-3.4), effects=[Blur(0.09)])

        # RIGHT: the same three discs, each blurred on its own layer, multiplied
        # afterwards. Same ingredients, different picture.
        right = []
        for dx, dy, colour in DISCS:
            c = Circle(radius=1.0)
            c.set_fill(colour, 1.0)
            c.set_stroke(opacity=0)
            c.move_to((3.4 + dx, dy - 0.2, 0))
            right.append(
                Layer(
                    c,
                    blend="normal" if not right else "multiply",
                    effects=[Blur(0.09)],
                ),
            )

        self.use_composition(
            Composition(
                left,
                *right,
                Layer(title, l1, l2),
                background=(0.02, 0.03, 0.05, 1),
            ),
        )

        self.wait(2.0)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    Precomp(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
