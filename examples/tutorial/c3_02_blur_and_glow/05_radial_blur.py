"""Course 3 · 2.5 — RadialBlur (zoom blur)

    RadialBlur(strength, center_point=(0.0, 0.0))

32 samples along the line from each pixel TOWARDS the centre, averaged. The
centre stays sharp and everything smears outwards — the "warp speed" look,
and the honest way to draw attention to a point.

`strength ∈ [0, 1)` is how far along that line the last sample lands, so it
is a fraction of the distance to the centre rather than a length: a pixel at
the corner smears more than one near the middle, which is what makes the
effect read as radial in the first place.

`center_point` is in SCENE COORDINATES, so it can follow a mobject: put an
updater on it and the zoom blur tracks whatever you are pointing at.

    python examples/tutorial/c3_02_blur_and_glow/05_radial_blur.py
"""

from pathlib import Path

from janim import *
from janim.math import cos, sin

PREVIEW_T = 2.2


class RadialBlurLesson(Scene):
    def construct(self):
        title = Text("the centre stays sharp; the rest smears outwards", size=0.42, color=GREY_A)
        title.to_edge(UP, buff=0.3)

        # A field of spokes and rings: the pattern a zoom blur eats best.
        field = VGroup()
        for k in range(24):
            theta = k * TAU / 24
            l = Line(
                (1.1 * cos(theta), 1.1 * sin(theta) - 0.2, 0),
                (5.2 * cos(theta), 5.2 * sin(theta) - 0.2, 0),
            )
            l.set_stroke("#3D7BC0", width=3.0)
            field.add(l)
        for r in (1.6, 2.4, 3.2, 4.0):
            c = Circle(radius=r)
            c.set_stroke("#25405C", width=2.5)
            c.set_fill(opacity=0)
            c.move_to((0, -0.2, 0))
            field.add(c)

        core = Circle(radius=0.85)
        core.set_fill("#FFD25E", 1.0)
        core.set_stroke(opacity=0)
        core.move_to((0, -0.2, 0))

        zoom = RadialBlur(0.0, center_point=(0.0, -0.2))

        self.use_composition(
            Composition(
                Layer(field, effects=[zoom]),
                Layer(core),
                Layer(title),
                background=(0.02, 0.03, 0.05, 1),
            ),
        )

        # The strength swells and dies — one field, one animation.
        def swell(m, a):
            zoom.strength = 0.55 * there_and_back(a)

        self.play(UpdateFromAlphaFunc(core, swell), run_time=3.0)
        self.wait(0.4)
        print("strength returned to", round(zoom.strength, 4))


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    RadialBlurLesson(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
