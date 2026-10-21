"""Demo 07 · LETRAS DE MAR — el título como MÁSCARA de un mundo 3D animado

Un `Text` es un mobject como cualquier otro, así que puede ser el recorte de
una capa: `crop(sea, inside=word)`. Y la capa recortada tiene su PROPIA
cámara (`camera=`), inclinada sobre un mar de olas que se mueve por updater
con normales analíticas (luz de verdad, no un degradado). Dentro de cada
letra hay un render 3D iluminado; el resto de la pantalla no sabe que existe.

El final es el plano clásico de cabecera: la máscara se agranda hasta que el
ojo entra por la «I» y aparece el mar entero. La máscara es un mobject, así
que ese vuelo es un `animate` cualquiera con un `about_point`.

Manim no tiene máscaras: un `Text` solo se puede dibujar, no recortar.

Las muestras de la malla salen de `linear_range`; las olas se escriben en
los arrays vivos `points`/`d_normal_points` de la superficie y se avisa con
`note_changed_data()`; y un `animate` con dos operaciones es una cadena del
constructor `.animate`.

    bin/janim render examples/demo/07_text_mask.py -ql
"""

import math
from pathlib import Path

from janim import *
from janim.core._julia_math import cos, sin
from janim.core._ranges import linear_range


class TextMask(Scene):
    def construct(self):
        # ── el mar: una superficie animada con normales analíticas ─────────
        X, Y, NU, NV = 12.0, 5.5, 101, 51
        sea = PlaneXY(
            x_range=(-X, X),
            y_range=(-Y, Y),
            resolution=(NU, NV),
            color="#0F3D6E",
            opacity=1.0,
            shading=(0.25, 0.35, 0.5),
        )
        us = linear_range(-X, X, NU)
        vs = linear_range(-Y, Y, NV)

        def waves(m, dt):
            t = self.t
            points = m.points
            nudged = m.d_normal_points
            k = 0
            for u in us:
                for v in vs:
                    z = 0.34 * sin(1.7 * u + 1.8 * t) * cos(1.4 * v + 1.3 * t) + 0.12 * sin(2.6 * u - 1.1 * t)
                    dzx = 0.578 * cos(1.7 * u + 1.8 * t) * cos(1.4 * v + 1.3 * t) + 0.312 * cos(2.6 * u - 1.1 * t)
                    dzy = -0.476 * sin(1.7 * u + 1.8 * t) * sin(1.4 * v + 1.3 * t)
                    inv = 1e-3 / math.sqrt(dzx * dzx + dzy * dzy + 1)
                    points[k] = (u, v, z)
                    nudged[k] = (u - dzx * inv, v - dzy * inv, z + inv)
                    k += 1
            m.note_changed_data()

        sea.add_updater(waves)
        sun = Sphere(radius=0.9)
        sun.set_color("#FFB84D")
        sun.move_to((1.5, 5.5, 1.6))

        # la cámara del mar: inclinada, y meciéndose un poco
        cam_sea = CameraFrame()
        cam_sea.reorient(0.0, 62.0)
        cam_sea.set_frame_height(6.0)
        cam_sea.move_to((0, 0.6, 0))

        def rock(f, dt):
            f.reorient(6.0 * sin(0.22 * self.t), 62.0)

        cam_sea.add_updater(rock)

        # ── las letras: la RELLENA recorta y no se dibuja; el aro sí ───────
        word_mask = Text("JANIM", font="DejaVu Sans", size=2.3)
        if word_mask.get_width() > FRAME_WIDTH - 1.6:
            word_mask.set_width(FRAME_WIDTH - 1.6)
        word_mask.set_fill(WHITE, opacity=1.0)
        word_mask.set_stroke(opacity=0)
        word_mask.move_to(0.25 * UP)
        word_rim = word_mask.copy()
        word_rim.set_fill(opacity=0)
        word_rim.set_stroke("#9ADCFF", width=2.5, opacity=1.0)

        caption = Text(
            "the world seen THROUGH the letters: a lit 3D render, cut out by a TextMobject",
            size=0.3,
            color=GREY_C,
        )
        caption.to_edge(DOWN, buff=0.35)

        self.use_composition(
            Composition(
                crop(sea, sun, inside=word_mask, feather=0.015, camera=cam_sea),
                Layer(
                    word_rim,
                    blend="add",
                    effects=[Bloom(threshold=0.25, intensity=1.1, sigma=0.055)],
                ),
                Layer(caption),
                background=(0.01, 0.012, 0.03, 1),
            ),
        )
        caption.set_opacity(0.0)
        self.wait(1.0)
        caption.set_opacity(1.0)
        self.play(FadeIn(caption, shift=0.2 * UP), run_time=1.0)
        self.wait(2.5)
        self.play(FadeOut(caption), run_time=0.6)

        # el vuelo: la máscara crece 90× alrededor de la «I» — el ojo entra
        # por la letra y el mar lo llena todo
        anchor = word_mask["I"].get_center()
        # el aro se agranda Y se apaga en el MISMO animate: dos animaciones
        # sobre un mobject se pisan (cada una escribe el estado entero), una
        # sola no
        self.play(
            AnimationGroup(
                word_mask.animate(rate_func=ease_in_cubic).scale(90.0, about_point=anchor),
                word_rim.animate(rate_func=ease_in_cubic).scale(90.0, about_point=anchor).set_stroke(opacity=0.0),
            ),
            run_time=5,
        )
        self.wait(4)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    TextMask(output=str(here.with_suffix(".mp4")), fps=30, resolution=(1280, 720)).render()
