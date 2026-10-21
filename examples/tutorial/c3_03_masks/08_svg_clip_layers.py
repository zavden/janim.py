"""Course 3 · 3.8 — An SVG's own clipPaths

    clip_layers(svg) → list of Layer

An SVG file can declare `<clipPath>` elements, and a real renderer honours
them per pixel. Manim rasterises them away — the shapes are imported, the
clipping is not. Here the importer keeps them: every clipped child gets its
own `Layer` with a real `Mask`, and `clip_layers` hands you the list ready
to drop into a `Composition`.

    comp = Composition(*clip_layers(svg), background=(0, 0, 0, 1))
    self.use_composition(comp)

What to know:

  · children WITHOUT a clip share painter's-order layers; each clipped one
    gets a layer of its own, because two elements may reference the same
    clipPath from different transforms.
  · the mask shapes are COPIES frozen at call time — a static clip. Move the
    drawing and call `clip_layers` again if the clip must follow.
  · without it, `SVGMobject` still imports everything; the clip simply has
    no effect, which is exactly what you saw in course 1, lesson 2.4.

    python examples/tutorial/c3_03_masks/08_svg_clip_layers.py
"""

from pathlib import Path

from janim import *

# Keep the preview time INSIDE the scene: a `t` past the end is not the frame
# you meant, and a composition-based scene leaves `scene.mobjects` empty.
PREVIEW_T = 1.2


class SVGClipLayers(Scene):
    def construct(self):
        path = Path(__file__).resolve().parents[2] / "assets" / "badge.svg"

        plain = SVGMobject(path, height=3.6)
        plain.move_to(3.6 * LEFT + 0.2 * DOWN)

        clipped = SVGMobject(path, height=3.6)
        clipped.move_to(3.6 * RIGHT + 0.2 * DOWN)

        title = Text(
            "clipPath, honoured per pixel",
            size=0.44,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.3)
        l1 = Text("SVGMobject alone", size=0.32, color=GREY_B)
        l2 = Text("clip_layers(svg)", size=0.32, color=GREY_B)
        l1.move_to((-3.6, -2.6, 0))
        l2.move_to((3.6, -2.6, 0))

        layers = clip_layers(clipped)
        print(
            "clip_layers gave ",
            len(layers),
            " layers · ",
            sum(1 for layer in layers if layer.mask is not None),
            " of them masked",
            sep="",
        )

        self.use_composition(
            Composition(
                Layer(plain),
                *layers,
                Layer(title, l1, l2),
                background=(0.02, 0.03, 0.05, 1),
            ),
        )

        self.wait(1.5)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    SVGClipLayers(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
