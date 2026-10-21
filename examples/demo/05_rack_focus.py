"""Demo 05 · RACK FOCUS — profundidad de campo POR CAPA, enfocada a mano

Cinco tarjetas a cinco profundidades, cada una en su capa con un `Dof`. El
desenfoque de cada capa se recalcula CADA FRAME a partir de su distancia al
plano focal de la cámara:

    σ = min(aperture · |d − focus|, max_sigma)

y `focus` es un campo de un dataclass mutable: enfocar es escribir un número.
Eso es exactamente lo que hace un foquista, y es lo que Manim no puede hacer
porque no tiene capas: todo va a un único framebuffer, y un blur que solo
afecte a «lo que está lejos» no tiene dónde aplicarse.

De propina, la cámara se mece un poco de lado: como las tarjetas están a
distintas z y la cámara es de perspectiva, el PARALAJE sale solo.

Los cierres del bucle de enfoque se crean con una función (`pull`) para que
cada uno guarde SU par de profundidades (un `lambda` dentro del `for` de
Python vería solo el último).

    bin/janim render examples/demo/05_rack_focus.py -ql
"""

from pathlib import Path

import numpy as np

from janim import *
from janim.core._julia_math import sin


def card(formula, color, pos):
    """Una tarjeta: un panel redondeado con una fórmula, colocado en `pos` (con z)."""
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
        # σ en unidades de escena: 0.23 son ~21 px a 720p, el radio más grande
        # que el kernel del compositor calcula entero (pedir más solo avisa y
        # recorta)
        dofs = [Dof(aperture=0.22, max_sigma=0.23) for _ in cards]

        title = Text(
            "depth of field per layer: focusing is animating a number",
            size=0.4,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.3)
        title.fix_in_frame()

        # las capas van de la más lejana a la más cercana: la cercana tapa
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

        # el plano focal a la profundidad z: la cámara mira por -z desde `focal`
        focal = self.camera.get_focal_distance()

        def set_focus(z):
            for d in dofs:
                d.focus = focal - z

        set_focus(DEPTHS[0])

        # la cámara se mece: paralaje entre profundidades, gratis
        pilot = VGroup()

        def sway(m, dt):
            self.frame.move_to(np.array((0.35 * sin(0.4 * self.t), 0, 0), dtype=np.float32))

        pilot.add_updater(sway)
        self.add(pilot)

        def pull(z0, z1):
            """El foco de z0 a z1 a lo largo de una animación."""
            return lambda m, a: set_focus(z0 + a * (z1 - z0))

        self.wait(1.0)
        # de la más cercana a la más lejana, parando en cada una
        for k in range(4):
            z0, z1 = DEPTHS[k], DEPTHS[k + 1]
            self.play(
                UpdateFromAlphaFunc(cards[k], pull(z0, z1)),
                run_time=1.2,
            )
            self.wait(0.8)
        # y la vuelta de un tirón
        self.play(
            UpdateFromAlphaFunc(cards[0], pull(DEPTHS[4], DEPTHS[0])),
            run_time=2.4,
        )
        self.wait(1.2)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    RackFocus(output=str(here.with_suffix(".mp4")), fps=30, resolution=(1280, 720)).render()
