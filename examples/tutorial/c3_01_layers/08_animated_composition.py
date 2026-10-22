"""Course 3 · 1.8 — Animating the composition itself

Every layer parameter and every effect dial is a plain mutable field, so
animating them needs no new mechanism at all: an updater writes to them, or
`UpdateFromAlphaFunc` does.

    layer.opacity = …        layer.blend = "add"        effect.sigma = …

Two idioms, and the difference is when they run:

  an UPDATER on a mobject you `self.add` to the scene    → every frame, forever
  UpdateFromAlphaFunc over the run of a `self.play`      → only while it plays,
                                                           and with an α

The second is the honest one for a transition, because it ends exactly when
the animation does instead of drifting on with the scene clock.

`self.t` is available inside an updater, which makes "a function of time"
a one-liner — and it stays deterministic, because `self.t` advances by
exactly 1/fps per frame and never reads a wall clock.

    python examples/tutorial/c3_01_layers/08_animated_composition.py
"""

from pathlib import Path

from janim import *
from janim.math import cos, sin

PREVIEW_T = 3.2


class AnimatedComposition(Scene):
    def construct(self):
        title = Text("layers and effects are mutable structs", size=0.42, color=GREY_A)
        title.to_edge(UP, buff=0.3)

        ring = VGroup()
        for k in range(12):
            theta = k * TAU / 12
            d = Circle(radius=0.28)
            d.set_fill(color_gradient(["#58C4DD", "#FFD25E"], 12)[k], 1.0)
            d.set_stroke(opacity=0)
            d.move_to((2.1 * cos(theta), 2.1 * sin(theta) - 0.2, 0))
            ring.add(d)

        core = Star(7, outer_radius=1.1)
        core.set_fill("#FF5E5E", 1.0)
        core.set_stroke(opacity=0)
        core.move_to(0.2 * DOWN)

        glow = Bloom(threshold=0.35, intensity=0.2, sigma=0.10)
        soften = Blur(0.001)
        ring_layer = Layer(ring, effects=[glow])
        core_layer = Layer(core, blend="normal", opacity=1.0)

        self.use_composition(
            Composition(
                ring_layer,
                core_layer,
                Layer(effects=[soften]),
                Layer(title),
                background=(0.02, 0.02, 0.04, 1),
            ),
        )

        # A rotation the ordinary way, so there is motion under the effects.
        self.add(ring)

        def turn(m, dt):
            if dt > 0:
                m.rotate(0.6 * dt, about_point=(0, -0.2, 0))

        ring.add_updater(turn)

        # 1 · the glow swells, driven by α: it ends exactly with the play.
        def swell(m, a):
            glow.intensity = 0.2 + 1.6 * a
            core_layer.opacity = 1.0 - 0.3 * a

        self.play(UpdateFromAlphaFunc(core, swell), run_time=2.0)

        # 2 · the blend mode is just a field: switch it mid-scene.
        core_layer.blend = "add"
        self.wait(0.8)

        # 3 · a dream transition: the adjustment layer's blur rises and falls.
        def dream(m, a):
            soften.sigma = 0.001 + 0.18 * there_and_back(a)

        self.play(UpdateFromAlphaFunc(core, dream), run_time=2.4)
        print(
            "glow intensity:",
            round(glow.intensity, 2),
            "· core layer blend:",
            core_layer.blend,
            "· final sigma:",
            round(soften.sigma, 4),
        )


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    AnimatedComposition(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
