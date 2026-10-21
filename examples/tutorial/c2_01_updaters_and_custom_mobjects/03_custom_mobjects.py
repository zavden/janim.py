"""Course 2 · 1.3 — Custom mobjects

There are TWO seams, and which one you want depends on whether your thing is
vector geometry. Both seams are subclasses.

SEAM A — a new SHAPE. `class Gear(VMobject)` plus a constructor. You get
everything a VMobject has (points, style, family, transforms, the
interpolation contract, every animation), and a method of your own class can
specialise any of it without touching Transform. The empty, styled mobject
comes from `super().__init__(**kwargs)`, the public base constructor: call it
FIRST, before touching points or style, and let unknown keywords through to
it so a typo still raises.

SEAM B — a new MOBJECT that is not vector geometry (a number, a camera, a
mesh, a physical body). Subclass `Mobject` — which already gives you the
family, zero points and the updaters — and implement the interpolation
contract:

    is_interpolable = True                 align_data(other) → self
    interpolate(first, second, alpha)      become(other)

(`copy` comes from Mobject.) That is exactly how `ValueTracker` is built, and
it is why `vt.animate.set_value(10)` needed no change to `Transform`. If you
find yourself editing Transform to support a new type, something has gone
wrong.

    python examples/tutorial/c2_01_updaters_and_custom_mobjects/03_custom_mobjects.py
"""

from pathlib import Path

import numpy as np

from janim import *
from janim.core._julia_math import cos, sin


# ══ SEAM A · a shape ═══════════════════════════════════════════════════════

class Gear(VMobject):
    """A gear as one closed path: the rim steps in and out `teeth` times, and the
    bore is a SECOND subpath turning the other way — with winding fill that is
    the hole, free (the same trick `Annulus` uses)."""

    def __init__(
        self,
        teeth=12,
        radius=1.0,
        tooth=0.22,
        bore=0.3,
        **kwargs,
    ):
        super().__init__(**kwargs)      # an unknown keyword here raises a TypeError
        pts = []
        for k in range(4 * teeth):
            theta = k * TAU / (4 * teeth)
            r = radius + tooth if k % 4 in (0, 1) else radius - tooth
            pts.append((r * cos(theta), r * sin(theta), 0))
        pts.append(pts[0])
        self.set_points_as_corners(pts)
        self.add_subpath([np.float32(bore) * p for p in quadratic_bezier_points_for_arc(-TAU)])


# ══ SEAM B · a mobject that is not geometry ════════════════════════════════

class Thermometer(Mobject):
    """A single number with a unit — like `ValueTracker`, but it knows what it is.
    Four short methods and it animates, lives in a scene, and drives updaters."""

    # ── the interpolation contract: this is what makes it animatable ──────
    is_interpolable = True

    def __init__(self, celsius=20.0):
        super().__init__()
        self.celsius = float(celsius)

    def align_data(self, other, **kwargs):
        return self

    def interpolate(self, first, second, alpha, **kwargs):
        self.celsius = first.celsius + alpha * (second.celsius - first.celsius)
        return self

    def become(self, other, **kwargs):
        self.celsius = other.celsius
        return self

    def set_celsius(self, celsius):
        """The verb `animate` will call: `th.animate.set_celsius(100.0)`."""
        self.celsius = float(celsius)
        return self


PREVIEW_T = 2.2


class CustomMobjects(Scene):
    def construct(self):
        title = Text(
            "two seams: a shape, or a contract",
            size=0.46,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.35)
        self.add(title)

        gear = Gear(
            teeth=14,
            radius=1.2,
            tooth=0.22,
            bore=0.45,
        )
        gear.set_fill(color="#2C5F8A", opacity=1.0)
        gear.set_stroke(color="#58C4DD", width=2.5)
        gear.move_to(3.6 * LEFT)
        self.add(gear)
        print("Gear: tag = ", type(gear).__name__, " · subpaths = ", len(gear.get_subpaths()), sep="")

        # Seam B in action: the thermometer drives a bar and a label.
        th = Thermometer(5.0)
        self.add(th)

        tube = Rectangle(width=0.7, height=4.0)
        tube.set_stroke(color=GREY_B, width=3.0)
        tube.set_fill(opacity=0)
        tube.move_to(2.6 * RIGHT)

        def mercury_bar():
            h = 4.0 * min(max((th.celsius + 10) / 110, 0), 1)
            bar = Rectangle(width=0.52, height=max(h, 0.02))
            bar.set_fill(color="#FF5E5E", opacity=1.0)
            bar.set_stroke(opacity=0)
            bar.move_to((2.6, -2.0 + h / 2, 0))
            return bar

        mercury = always_redraw(mercury_bar)

        readout = DecimalNumber(
            5.0,
            num_decimal_places=1,
            size=0.6,
            color="#FF5E5E",
            unit=" C",
        )
        readout.move_to((4.6, 0.0, 0))
        readout.add_updater(lambda d: d.set_value(th.celsius))

        self.add(tube, mercury, readout)

        # It animates because of the contract methods, not because Transform
        # knows anything about thermometers.
        self.play(
            AnimationGroup(
                th.animate(rate_func=ease_in_out_cubic).set_celsius(96.0),
                Rotating(gear, TAU, run_time=3.0),
            ),
            run_time=3.0,
        )
        self.wait(0.4)
        print("thermometer ended at ", round(th.celsius, 2), " °C", sep="")


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    CustomMobjects(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
