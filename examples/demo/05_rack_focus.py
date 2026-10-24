"""Demo 05 · RACK FOCUS — manually focused depth of field PER LAYER

Five cards at five depths, each in its own layer with a `Dof`. Each
layer's blur is recalculated EVERY FRAME from its distance to the camera's
focal plane:

    σ = min(aperture · |d − focus|, max_sigma)

and `focus` is a field of a mutable dataclass: focusing means writing a
number. That is exactly what a focus puller does, and what Manim cannot
do because it has no layers: everything goes into a single framebuffer,
so a blur that only affects “what is far away” has nowhere to apply.

As a bonus, the camera sways sideways slightly: because the cards have
different z coordinates and the camera uses perspective, PARALLAX comes naturally.

Closures in the focus loop are created with a function (`pull`) so each
keeps ITS pair of depths (a `lambda` inside Python's `for` would see only
the last one).

    bin/janim render examples/demo/05_rack_focus.py -ql
"""

from pathlib import Path

import numpy as np

from janim import *
from janim.math import sin


def card(formula, color, pos):
    """A card: a rounded panel with a formula, placed at `pos` (including z)."""
    panel = RoundedRectangle(
        width=3.7,
        height=1.55,
        corner_radius=0.25,
    )
    panel.set_fill("#121A29", opacity=0.94)
    panel.set_stroke(color, width=3.0)
    tex = Tex(formula, color=color, size=0.95)
    if tex.get_width() > 3.2:
        tex.set_width(3.2)
    g = VGroup(panel, tex)
    g.move_to(pos)
    return g


DEPTHS = [1.6, 0.8, 0.0, -0.8, -1.6]


class RackFocus(Scene):
    def construct(self):
        cards = [
            card(r"e^{i\Pi} + 1 = 0", "#FFD25E", np.array((-3.6, -1.9, DEPTHS[0]), dtype=np.float32)),
            card(r"i\hbar \, \partial_t \psi = H \psi", "#58C4DD", np.array((-1.8, -1.0, DEPTHS[1]), dtype=np.float32)),
            card(r"\nabla \cdot E = \rho / \varepsilon_0", "#7FDD58", np.array((0.0, -0.1, DEPTHS[2]), dtype=np.float32)),
            card(r"G_{\mu\nu} = 8 \pi G \, T_{\mu\nu}", "#F0A045", np.array((1.8, 0.8, DEPTHS[3]), dtype=np.float32)),
            card(r"\Delta S \geq 0", "#FF3D8B", np.array((3.6, 1.7, DEPTHS[4]), dtype=np.float32)),
        ]
        # σ in scene units: 0.23 is ~21 px at 720p, the largest radius
        # the compositor kernel computes in full (asking for more only warns
        # and truncates)
        dofs = [Dof(aperture=0.22, max_sigma=0.23) for _ in cards]

        title = Text(
            "depth of field per layer: focusing is animating a number",
            size=0.4,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.3)
        title.fix_in_frame()

        # layers run from farthest to nearest: the near one covers the others
        layers = [
            Layer(c, effects=[d])
            for c, d in zip(reversed(cards), reversed(dofs))
        ]
        self.use_composition(
            Composition(
                *layers,
                Layer(title),
                background=(0.02, 0.03, 0.05, 1),
            ),
        )

        # the focal plane at depth z: the camera looks along -z from `focal`
        focal = self.camera.get_focal_distance()

        def set_focus(z):
            for d in dofs:
                d.focus = focal - z

        set_focus(DEPTHS[0])

        # the camera sways: parallax between depths, for free
        pilot = VGroup()

        def sway(m, dt):
            self.frame.move_to(np.array((0.35 * sin(0.4 * self.t), 0, 0), dtype=np.float32))

        pilot.add_updater(sway)
        self.add(pilot)

        def pull(z0, z1):
            """Focus from z0 to z1 over an animation."""
            return lambda m, a: set_focus(z0 + a * (z1 - z0))

        self.wait(1.0)
        # from nearest to farthest, stopping at each
        for k in range(4):
            z0, z1 = DEPTHS[k], DEPTHS[k + 1]
            self.play(
                UpdateFromAlphaFunc(cards[k], pull(z0, z1)),
                run_time=1.2,
            )
            self.wait(0.8)
        # and back in one continuous move
        self.play(
            UpdateFromAlphaFunc(cards[0], pull(DEPTHS[4], DEPTHS[0])),
            run_time=2.4,
        )
        self.wait(1.2)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    RackFocus(output=str(here.with_suffix(".mp4")), fps=30, resolution=(1280, 720)).render()
