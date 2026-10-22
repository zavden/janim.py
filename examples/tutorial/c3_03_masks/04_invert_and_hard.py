"""Course 3 · 3.4 — invert and hard

    Mask(shape, invert=True)     coverage → 1 − coverage
    Mask(shape, hard=True)       coverage → step(0.5, coverage)

`invert` is what `crop(…, minus=…)` is built on.

`hard` thresholds the mask at 0.5, which throws away the antialiasing and
gives a crisp, aliased edge. That is usually the wrong thing — and exactly
the right thing when the mask is a FEATHERED or NOISY shape being used as a
stencil: threshold a blurred circle and you get a hard edge you can animate
smoothly, because the σ moves continuously while the cut stays sharp.

The two compose: `invert` is applied first, then `hard`.

    python examples/tutorial/c3_03_masks/04_invert_and_hard.py
"""

from pathlib import Path

from janim import *
from janim.math import sin

PREVIEW_T = 2.2


def bars(x):
    """Diagonal bars: fine edges, so aliasing is visible."""
    g = VGroup()
    for k in range(14):
        r = Rectangle(width=0.22, height=5.0)
        r.set_fill(color="#58C4DD" if k % 2 == 0 else "#FFD25E", opacity=1.0)
        r.set_stroke(opacity=0)
        r.rotate(PI / 6)
        r.move_to((x - 1.5 + 0.31 * k, -0.1, 0))
        g.add(r)
    return g


class InvertAndHard(Scene):
    def construct(self):
        title = Text(
            "invert flips the coverage; hard thresholds it",
            size=0.42,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.3)

        # The third panel's mask is FEATHERED and then thresholded: the σ can be
        # animated smoothly while the edge stays crisp — a growing stencil.
        grow = 0.35
        stencil = Circle(radius=1.4, fill_opacity=1.0)
        stencil.move_to((4.6, -0.1, 0))
        soft = Mask(
            stencil,
            feather=0.35,
            hard=True,
        )
        clock = VGroup()

        def breathe(m, dt):
            if not dt > 0:
                return
            soft.feather = 0.05 + 0.55 * (0.5 + 0.5 * sin(1.3 * self.t))

        clock.add_updater(breathe)
        self.add(clock)

        win1 = Circle(radius=1.4, fill_opacity=1.0)
        win1.move_to((-4.6, -0.1, 0))
        win2 = Circle(radius=1.4, fill_opacity=1.0)
        win2.move_to((0.0, -0.1, 0))

        labels = []
        for x, s in ((-4.6, "plain"), (0.0, "invert = true"), (4.6, "feather + hard = true")):
            lab = Text(s, size=0.3, color=GREY_B)
            lab.move_to((x, -2.7, 0))
            labels.append(lab)

        self.use_composition(
            Composition(
                Layer(bars(-4.6), mask=Mask(win1)),
                Layer(bars(0.0), mask=Mask(win2, invert=True)),
                Layer(bars(4.6), mask=soft),
                Layer(title, *labels),
                background=(0.02, 0.03, 0.05, 1),
            ),
        )

        self.wait(3.0)
        print("stencil feather at the end: ", round(soft.feather, 3), sep="")


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    InvertAndHard(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
