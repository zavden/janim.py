"""Course 3 · 2.2 — An animated blur (the dream transition)

`Blur` is a mutable object, so sigma is just a field. Writing to it from
`UpdateFromAlphaFunc` — which stops exactly when the animation does — is the
whole technique.

It is continuous in sigma, on purpose: the weights are recomputed per frame and
the pass is skipped below 0.3 px rather than snapping to a 1-pixel kernel.
So a blur that rises from 0 has no visible first step.

THE STANDARD TRANSITION: an adjustment layer over everything, sigma up while the
old content leaves, sigma down while the new content arrives. Nothing else has
to know a transition is happening.

And a trap this lesson exists to avoid. **`FadeIn(m)` animates from
transparent TO THE MOBJECT AS IT STANDS** — so a mobject you already made
invisible (`m.set_fill(opacity=0)`) fades in to… invisible, and nothing
happens. Under a composition the fix is neater than fighting it: build the
content opaque and animate the LAYER's opacity, which is one field and shows
no internal seams (lesson 1.3).

    python examples/tutorial/c3_02_blur_and_glow/02_blur_animated.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 2.4


class BlurAnimated(Scene):
    def construct(self):
        caption = Text("blur up, swap, blur down", size=0.42, color=GREY_A)
        caption.to_edge(UP, buff=0.3)

        scene_a = VGroup()
        for k in range(6):
            c = Circle(radius=0.55)
            c.set_fill("#3D7BC0", 1.0)
            c.set_stroke(opacity=0)
            c.move_to((-3.5 + 1.4 * k, 0.2, 0))
            scene_a.add(c)

        scene_b = VGroup()
        for k in range(6):
            s = Star(5, outer_radius=0.62)
            s.set_fill("#FFD25E", 1.0)   # OPAQUE: see the note
            s.set_stroke(opacity=0)
            s.move_to((-3.5 + 1.4 * k, 0.2, 0))
            scene_b.add(s)

        soften = Blur(0.001)
        layer_a = Layer(scene_a)
        layer_b = Layer(scene_b, opacity=0.0)      # …and hidden by its LAYER

        self.use_composition(
            Composition(
                layer_a,
                layer_b,
                Layer(effects=[soften]),
                Layer(caption),
                background=(0.02, 0.03, 0.05, 1),
            ),
        )

        self.wait(0.5)

        # UP: sigma rises while the first set goes.
        def up(m, a):
            soften.sigma = 0.001 + 0.20 * a
            layer_a.opacity = 1.0 - a

        self.play(UpdateFromAlphaFunc(scene_a, up), run_time=1.2)

        # DOWN: sigma falls while the second arrives. The swap happened while nobody
        # could see it, which is the entire point of the gesture.
        def down(m, a):
            soften.sigma = 0.20 - 0.199 * a
            layer_b.opacity = a

        self.play(UpdateFromAlphaFunc(scene_b, down), run_time=1.2)
        self.wait(0.6)
        print(
            "sigma back to",
            round(soften.sigma, 4),
            "(the pass is skipped) · layer opacities",
            round(layer_a.opacity, 2),
            "/",
            round(layer_b.opacity, 2),
        )


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    BlurAnimated(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
