"""Course 3 · 2.7 — Depth of field

    Dof(focus=None, aperture=0.4, max_sigma=4.0)

A blur whose sigma is recomputed EVERY FRAME from the layer's distance to the
camera's focal plane:

    σ = min(aperture · |d − focus|, max_sigma)

where `d` is the camera→layer-centre distance measured along the view axis.
`focus=None` means the camera's own focal distance, so with the default
camera the plane through the origin is in focus.

It is PER LAYER, which is the honest scope: a layer is composited to one
texture, so it has one depth. A real lens blurs per pixel; this blurs per
layer, and for a scene built out of planes at different depths — which is
most explanatory 3D — the two agree.

Two ways to drive it, both here:

  · MOVE THE CAMERA and leave `focus=None`: the layers go in and out of
    focus by themselves, because the compositor resolves every `Dof` against
    the camera of the frame being composited;
  · RACK FOCUS: keep the camera still and animate `dof.focus`, which is what
    a camera operator actually does.

    python examples/tutorial/c3_02_blur_and_glow/07_depth_of_field.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 3.4


def card(z, y, colour, label):
    """A row of dots at depth z, placed up the frame so all three are visible."""
    g = VGroup()
    for k in range(6):
        c = Circle(radius=0.32)
        c.set_fill(colour, 1.0)
        c.set_stroke(opacity=0)
        c.move_to((-3.2 + 1.05 * k, y, z))
        g.add(c)
    t = Text(label, size=0.32, color=colour)
    t.move_to((3.6, y, z))
    g.add(t)
    return g


class DepthOfField(Scene):
    def construct(self):
        # The DEFAULT camera: it looks straight down −z, so depth IS the z
        # coordinate and the arithmetic above is easy to check by eye.
        near = card(2.0, 1.7, "#7FDD58", "z = +2")
        mid = card(0.0, 0.0, "#FFD25E", "z =  0")
        far = card(-2.0, -1.7, "#58C4DD", "z = -2")

        title = Text("rack focus: one field, animated", size=0.42, color=GREY_A)
        title.to_edge(UP, buff=0.3)

        d_near = Dof(aperture=0.5, max_sigma=3.0)
        d_mid = Dof(aperture=0.5, max_sigma=3.0)
        d_far = Dof(aperture=0.5, max_sigma=3.0)

        self.use_composition(
            Composition(
                Layer(far, effects=[d_far]),
                Layer(mid, effects=[d_mid]),
                Layer(near, effects=[d_near]),
                Layer(title),
                background=(0.02, 0.03, 0.05, 1),
            ),
        )

        focal = focal_distance(self.camera)
        print("focal distance", round(focal, 3), "— with focus = None, the z = 0 plane is the sharp one")
        self.wait(1.0)

        # Rack the focus from the far plane to the near one and back.
        def rack(a):
            f = focal + 2.0 - 4.0 * a                 # focal+2 (far) → focal−2 (near)
            for d in (d_near, d_mid, d_far):
                d.focus = f

        self.play(UpdateFromAlphaFunc(mid, lambda m, a: rack(a)), run_time=2.5)
        self.wait(0.4)
        self.play(UpdateFromAlphaFunc(mid, lambda m, a: rack(1 - a)), run_time=2.5)
        self.wait(0.4)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    DepthOfField(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
