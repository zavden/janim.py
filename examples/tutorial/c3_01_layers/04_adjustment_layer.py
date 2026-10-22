"""Course 3 · 1.4 — Adjustment layers

    Layer(effects=[ … ])            ← no mobjects at all

A layer with no content applies its effects to WHATEVER IS ALREADY
COMPOSITED BELOW IT. That is After Effects' adjustment layer, and it is what
gives you "grade everything up to here" without touching any of it.

The order in the list is the order of operations:

    Layer(a)                   ← graded
    Layer(b)                   ← graded
    Layer(effects=[Blur])      ← the adjustment: it blurs a and b together
    Layer(c)                   ← NOT graded: it composites afterwards

Two consequences worth having in your head:

  · an adjustment layer blurs the SEAM between the layers below, not each
    one separately — that is the whole difference from putting the same blur
    on each of them;
  · a title placed above it stays sharp while the film behind it goes soft,
    which is the standard "dream transition" and costs one line.

    python examples/tutorial/c3_01_layers/04_adjustment_layer.py
"""

from pathlib import Path

from janim import *
from janim.math import step_range

PREVIEW_T = 3.0


class AdjustmentLayer(Scene):
    def construct(self):
        title = Text("one adjustment layer grades everything below it", size=0.42, color=GREY_A)
        title.to_edge(UP, buff=0.3)

        # step_range(-6.5, 6.5, 0.9) is inclusive of both ends: exactly fifteen samples, no float drift.
        grid = VGroup()
        for x in step_range(-6.5, 6.5, 0.9):
            l = Line((x, -3.6, 0), (x, 3.6, 0))
            l.set_stroke("#25405C", width=2.0)
            grid.add(l)
        for y in step_range(-3.6, 3.6, 0.9):
            l = Line((-6.8, y, 0), (6.8, y, 0))
            l.set_stroke("#25405C", width=2.0)
            grid.add(l)

        shapes = VGroup()
        for k, (x, colour) in enumerate(((-3.4, "#3D7BC0"), (0.0, "#E8A33D"), (3.4, "#7FDD58")), 1):
            s = RegularPolygon(3 + k, radius=1.2)
            s.set_fill(colour, 1.0)
            s.set_stroke(opacity=0)
            s.move_to((x, -0.2, 0))
            shapes.add(s)

        caption = Text("this text is ABOVE the adjustment, so it stays sharp", size=0.36, color=GREY_A)
        caption.move_to(2.9 * DOWN)

        # The adjustment: a blur and a colour grade, applied to the grid AND the
        # shapes as one picture. Animated, so you can watch it take hold.
        soften = Blur(0.001)
        grade = ColorAdjust(saturation=1.0, brightness=1.0)

        clock = VGroup()

        def take_hold(m, dt):
            if dt <= 0:
                return
            a = min(max((self.t - 0.6) / 2.2, 0), 1)
            soften.sigma = 0.001 + 0.16 * a
            grade.saturation = 1.0 - 0.75 * a
            grade.brightness = 1.0 - 0.25 * a

        clock.add_updater(take_hold)
        self.add(clock)

        self.use_composition(
            Composition(
                Layer(grid),
                Layer(shapes),
                Layer(effects=[soften, grade]),     # ← the adjustment layer
                Layer(title, caption),
                background=(0.02, 0.03, 0.05, 1),
            ),
        )

        self.wait(3.4)
        print("final sigma:", round(soften.sigma, 3), "· saturation:", round(grade.saturation, 3))


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    AdjustmentLayer(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
