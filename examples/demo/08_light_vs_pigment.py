"""Demo 08 · LIGHT ADDS, PIGMENT MULTIPLIES — per-layer blend modes

On the left, three pure-light discs (R, G, B), each in its own layer with
`blend="add"`: two overlapping discs produce yellow, cyan or magenta,
and all three produce WHITE. On the right, three inks (C, M, Y) on paper,
each in its own layer with `blend="multiply"`: overlaps produce red,
green and blue, and all three together produce BLACK.

Each disc deliberately has ITS OWN layer: within a layer, mobjects are
drawn over one another (covering), and the blend mode acts between the
whole layer and what is below it. The three light discs go inside a
precomposition (`Layer(Composition(...))`) to apply Bloom to the group
without affecting the paper.

And the compositor works in LINEAR LIGHT: red + green + blue really makes
white, not the muddy gray of adding sRGB bytes. Manim has no blend modes:
one disc with opacity 0.5 over another is alpha blending, which neither
adds nor multiplies.

The mode is written `blend="add"` (a string), and `enumerate` starts at 1
(`start=1`) because `k` enters each disc's angle.

    bin/janim render examples/demo/08_light_vs_pigment.py -ql
"""

from pathlib import Path

import numpy as np

from janim import *
from janim.math import cos, sin


def disc(color, pos):
    """A flat-colored disc, without a border, at `pos`."""
    c = Circle(radius=1.15, fill_opacity=1.0)
    c.set_fill(color, opacity=1.0)
    c.set_stroke(opacity=0)
    c.move_to(pos)
    return c


def spread(center, k, r):
    """The k-th of three points at distance r from the center, spaced 120° apart."""
    return center + np.array(
        (
            r * cos(TAU / 4 + k * TAU / 3),
            r * sin(TAU / 4 + k * TAU / 3),
            0,
        ),
        dtype=np.float32,
    )


class LightVsPigment(Scene):
    def construct(self):
        c_light = np.array((-3.6, -0.35, 0), dtype=np.float32)
        c_pig = np.array((3.6, -0.35, 0), dtype=np.float32)
        far, near = 1.45, 0.62

        light = [
            disc(c, spread(c_light, k, far))
            for k, c in enumerate(("#FF0000", "#00FF00", "#0000FF"), start=1)
        ]
        pigment = [
            disc(c, spread(c_pig, k, far))
            for k, c in enumerate(("#00FFFF", "#FF00FF", "#FFFF00"), start=1)
        ]

        paper = RoundedRectangle(
            width=6.2,
            height=5.6,
            corner_radius=0.3,
        )
        paper.set_fill("#F4F1E8", opacity=1.0)
        paper.set_stroke(opacity=0)
        paper.move_to(c_pig)

        title = Text(
            "light ADDS, pigment MULTIPLIES",
            size=0.5,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.3)
        t_light = Text('blend = "add"', size=0.34, color=GREY_B)
        t_pig = Text('blend = "multiply"', size=0.34, color=GREY_B)
        t_light.move_to((-3.6, -3.35, 0))
        t_pig.move_to((3.6, -3.35, 0))

        glow = Bloom(threshold=0.55, intensity=0.55, sigma=0.14)
        self.use_composition(
            Composition(
                Layer(paper),
                Layer(
                    Composition(
                        Layer(light[0], blend="add"),
                        Layer(light[1], blend="add"),
                        Layer(light[2], blend="add"),
                    ),
                    blend="add",
                    effects=[glow],
                ),
                Layer(pigment[0], blend="multiply"),
                Layer(pigment[1], blend="multiply"),
                Layer(pigment[2], blend="multiply"),
                Layer(title, t_light, t_pig),
                background=(0.02, 0.02, 0.03, 1),
            ),
        )

        # all six rotate together while grouped: the blend does not depend
        # on which is on top, because there is no “on top”
        spinning = [False]

        def spin(m, dt):
            if not (spinning[0] and dt > 0):
                return
            for d in light:
                d.rotate(0.6 * dt, about_point=c_light)
            for d in pigment:
                d.rotate(0.6 * dt, about_point=c_pig)

        clock = VGroup()
        clock.add_updater(spin)
        self.add(clock)

        self.wait(0.8)
        self.play(
            AnimationGroup(
                *(
                    d.animate.move_to(spread(c_light, k, near))
                    for k, d in enumerate(light, start=1)
                ),
                *(
                    d.animate.move_to(spread(c_pig, k, near))
                    for k, d in enumerate(pigment, start=1)
                ),
            ),
            run_time=2.5,
        )
        self.wait(1.0)
        spinning[0] = True
        self.wait(4.5)
        spinning[0] = False
        self.play(
            AnimationGroup(
                *(
                    d.animate.move_to(spread(c_light, k, far))
                    for k, d in enumerate(light, start=1)
                ),
                *(
                    d.animate.move_to(spread(c_pig, k, far))
                    for k, d in enumerate(pigment, start=1)
                ),
            ),
            run_time=2.0,
        )
        self.wait(1.0)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    LightVsPigment(output=str(here.with_suffix(".mp4")), fps=30, resolution=(1280, 720)).render()
