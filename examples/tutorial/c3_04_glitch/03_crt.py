"""Course 3 · 4.3 — CRT

    CRT(intensity=1.0, scanlines=240, scan_depth=0.35, mask=0.3,
        curvature=0.15, vignette=0.35, roll=0.0)

A cathode-ray television in one pass: barrel curvature, scanlines, an
aperture-grille mask and a vignette.

    scanlines    how many visible lines fit in the FRAME HEIGHT. The shader
                 puts exactly that many minima there — a count, not a size.
    scan_depth   how dark the gaps between lines are.
    mask         depth of the aperture grille: a 3-pixel RGB stripe, the
                 period of a real shadow mask.
    curvature    barrel distortion. What falls outside the tube is
                 TRANSPARENT, not black, so the layer below still shows.
    vignette     the darkening towards the corners.
    intensity    master dial; 0 is an exact no-op.

The sizes here are fractions of the frame and counts, NOT scene units — and
deliberately so: that is how a television is specified. A blur radius is a
distance in the world; a scanline count is a property of the screen.

    python examples/tutorial/c3_04_glitch/03_crt.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.2


def programme(x):
    """Something worth putting on a tube: flat colour and big type."""
    group = VGroup()
    sky = Rectangle(width=3.0, height=2.1)
    sky.set_fill("#1B4F8C", 1.0)
    sky.set_stroke(opacity=0)
    sky.move_to((x, 0.4, 0))
    group.add(sky)
    sun = Circle(radius=0.42)
    sun.set_fill("#FFD25E", 1.0)
    sun.set_stroke(opacity=0)
    sun.move_to((x + 0.85, 1.0, 0))
    group.add(sun)
    hill = Triangle(radius=0.95)
    hill.set_fill("#3E8E52", 1.0)
    hill.set_stroke(opacity=0)
    hill.move_to((x - 0.3, -0.15, 0))
    group.add(hill)
    text = Text("CH 3", size=0.34, color=WHITE)
    text.move_to((x, -0.95, 0))
    group.add(text)
    return group


class CRTLesson(Scene):
    def construct(self):
        title = Text(
            "scanlines are a COUNT; curvature is a fraction of the frame",
            size=0.36,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.3)

        cases = (
            ("off", CRT(intensity=0.0)),
            ("default", CRT()),
            ("scanlines = 90", CRT(scanlines=90, scan_depth=0.55)),
            ("curvature = 0.4", CRT(curvature=0.4, vignette=0.6)),
        )

        layers = []
        labels = []
        for k, (name, fx) in enumerate(cases, start=1):
            x = -5.1 + 3.4 * (k - 1)
            layers.append(Layer(programme(x), effects=[fx]))
            label = Text(name, size=0.3, color=GREY_B)
            label.move_to((x, -2.0, 0))
            labels.append(label)
        layers.append(Layer(title, *labels))

        self.use_composition(
            Composition(
                *layers,
                background=(0.03, 0.03, 0.04, 1.0),
            ),
        )
        self.wait(1.5)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    CRTLesson(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
