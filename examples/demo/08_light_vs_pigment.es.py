"""Demo 08 · LA LUZ SUMA, EL PIGMENTO MULTIPLICA — modos de fusión por capa

A la izquierda, tres discos de luz pura (R, G, B), cada uno en su capa con
`blend="add"`: donde se solapan dos sale amarillo, cian o magenta, y donde se
solapan los tres, BLANCO. A la derecha, tres tintas (C, M, Y) sobre un papel,
cada una en su capa con `blend="multiply"`: los solapes dan rojo, verde y
azul, y los tres juntos, NEGRO.

Cada disco va en SU capa a propósito: dentro de una misma capa los mobjects se
dibujan uno sobre otro (tapan), y el modo de fusión actúa entre la capa entera
y lo que tiene debajo. Los tres de luz van dentro de una precomposición
(`Layer(Composition(...))`) para ponerle el Bloom al conjunto y no al papel.

Y el compositor compone en LUZ LINEAL: rojo + verde + azul da blanco
de verdad, no el gris sucio de sumar bytes sRGB. Manim no tiene modos de
fusión: un disco con opacidad 0.5 sobre otro es una mezcla alfa, que ni suma
ni multiplica.

El modo se escribe `blend="add"` (una cadena), y el `enumerate` empieza en 1
(`start=1`) porque `k` entra en el ángulo de cada disco.

    bin/janim render examples/demo/08_light_vs_pigment.py -ql
"""

from pathlib import Path

import numpy as np

from janim import *
from janim.math import cos, sin


def disc(color, pos):
    """Un disco de color plano, sin borde, en `pos`."""
    c = Circle(radius=1.15, fill_opacity=1.0)
    c.set_fill(color, opacity=1.0)
    c.set_stroke(opacity=0)
    c.move_to(pos)
    return c


def spread(center, k, r):
    """El k-ésimo de tres puntos a distancia r del centro, a 120°."""
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

        # los seis giran como un todo mientras están juntos: la mezcla no
        # depende de quién está encima, porque no hay «encima»
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
