"""Course 3 · 1.1 — The layer, the one primitive

Manim draws EVERYTHING into the final framebuffer in z order. There are no
intermediate textures, so there is nowhere to apply a blend mode or an
effect "to this group and not that one". It is not a missing feature — it
follows from the architecture.

Janim's compositing primitive is the LAYER: a texture plus its compositing
parameters. Everything in course 3 is a consequence.

    Layer(*mobjects, blend=, opacity=, effects=, mask=, matte=)
    Composition(*layers, background=(r, g, b, a))
    self.use_composition(comp)

THE RULE TO INTERNALISE FIRST: once a composition is mounted, the scene
renders IT and not `self.mobjects`. Anything you want on screen has to be
in a layer — titles and captions included. That is the honest shape of the
design: there is no privileged "just draw this" path.

`self.add(m)` still matters for one thing: UPDATERS. Mobjects inside
layers are updated too (the compositor walks them), so in practice you add
only what has an updater and lives nowhere else.

    python examples/tutorial/c3_01_layers/01_one_layer.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.6


class OneLayer(Scene):
    def construct(self):
        title = Text("everything on screen is a layer", size=0.48, color=GREY_A)
        title.to_edge(UP, buff=0.4)

        back = Rectangle(width=5.0, height=3.2)
        back.set_fill("#2C5F8A", 1.0)
        back.set_stroke(opacity=0)
        back.move_to(0.4 * DOWN)

        front = Star(6, outer_radius=1.5)
        front.set_fill("#FFD25E", 1.0)
        front.set_stroke(opacity=0)
        front.move_to(0.4 * DOWN)

        caption = Text("layer 2 is blurred; layer 3 is not", size=0.36, color=GREY_B)
        caption.move_to(2.9 * DOWN)

        # Bottom to top, exactly as written. The blur belongs to the BACK layer,
        # so the star in front of it stays sharp even where they overlap — the
        # thing a single framebuffer cannot do.
        self.use_composition(
            Composition(
                Layer(back, effects=[Blur(0.12)]),
                Layer(front),
                Layer(title, caption),
                background=(0.02, 0.03, 0.05, 1),
            ),
        )

        self.play(GrowFromCenter(front), run_time=1.0)
        self.wait(1.0)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    OneLayer(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
