"""Demo 03 · PORTALES — una figura, tres cámaras: la de la escena en el centro
y dos LUPAS iguales a los lados, una circular y otra con forma de estrella

Un mundo 2D (una roseta con rótulos diminutos y dos puntos que la recorren en
sentidos opuestos) dibujado por la cámara de la escena en el centro. A los
lados, dos capas que ven el MISMO mundo con cámaras propias, y cuya ventana no
es un rectángulo. Las dos cámaras son la misma lupa ×3 que persigue a un punto
(un updater sobre el `CameraFrame`, lo que en CE pide un `ZoomedScene`
entero): el círculo va tras el punto amarillo y la estrella tras el verde. Es
un render de verdad, no una copia escalada: el trazo no engorda con el zoom y
los rótulos de 0.1 unidades salen nítidos. La forma del portal es solo la
máscara — la cámara no sabe si es un círculo o una estrella. Y la estrella
GIRA sobre sí misma (máscara y aro, con un updater): la imagen de dentro sigue
derecha, lo que gira es el recorte. Como la caja de una estrella que gira
cambia de tamaño y de centro, la VENTANA de esa capa es un cuadrado fijo que
no se dibuja, y la estrella es solo la máscara: el aumento no oscila y la
imagen no baila.

La mecánica: `window=` coloca la vista en la CAJA del mobject (la lupa es un
cuadrado; la estrella, casi), y `crop(..., inside=forma)` recorta esa caja con
la forma de verdad. La máscara se aplica en el espacio del PADRE, después de
la ventana, así que la misma forma sirve de ventana y de recorte. La forma que
recorta va rellena y NO se dibuja; el aro visible es otro mobject, solo
stroke, en la capa de arriba.

Las muestras de la roseta salen de `linear_range`. El desplazamiento de cada
rótulo se calcula con cuidado de tipos: `hypot` de dos Float32 se hace en
Float64 y se redondea a Float32, y `0.22 * punto` sube a Float64 (en numpy 2,
`0.22 * array_float32` se quedaría en float32).

    bin/janim render examples/demo/03_portals.py -ql
"""

import math
from pathlib import Path

import numpy as np

from janim import *
from janim.core._julia_math import cos, sin
from janim.core._ranges import linear_range


def rosette_point(t):
    """Una hipotrocoide: cinco lóbulos, cerrada tras dos vueltas."""
    R, r, d = 2.0, 0.8, 1.15
    k = (R - r) / r
    return np.array(
        (
            (R - r) * cos(t) + d * cos(k * t),
            (R - r) * sin(t) - d * sin(k * t),
            0,
        ),
        dtype=np.float32,
    )


class Portals(Scene):
    def construct(self):
        # ── el mundo 2D ────────────────────────────────────────────────────
        plane = NumberPlane(
            (-7.0, 7.0, 1.0),
            (-4.0, 4.0, 1.0),
            width=14.0,
            height=8.0,
            background_line_color="#1C2E4A",
            faded_opacity=0.12,
        )

        rosette = VMobject()
        rosette.set_points_smoothly([rosette_point(t) for t in linear_range(0, 4 * PI, 721)])
        rosette.set_stroke(width=4.0)
        rosette.set_stroke_by_gradient("#FF3D8B", "#FFD25E", "#39D0FF", "#7FDD58", "#FF3D8B")

        # rótulos DIMINUTOS a lo largo de la curva: en el centro apenas se
        # leen, en la lupa salen nítidos — la prueba de que la lupa es un
        # render y no un zoom de píxeles
        labels = VGroup()
        for k in range(1, 11):
            p = rosette.point_from_proportion((k - 0.5) / 10)
            t = Text(str(k), size=0.11, color=GREY_A)
            # hypot de dos Float32: en Float64, redondeado a Float32
            h = np.float32(math.sqrt(float(p[0]) * float(p[0]) + float(p[1]) * float(p[1])))
            normal = np.array((-p[1], p[0], 0), dtype=np.float32).astype(np.float64)
            t.move_to(p.astype(np.float64) + 0.22 * normal / max(float(h), 1e-6))
            labels.add(t)
        fine_print = Text("a real render, not a copy", size=0.09, color=GREY_B)
        fine_print.move_to((0, -0.1, 0))

        # dos puntos, del color del aro que los persigue, recorriendo la
        # roseta en sentidos opuestos (una vuelta cada 7 s)
        def runner(color, alpha_of_t):
            d = Dot(ORIGIN, radius=0.11)
            d.set_fill(color)
            d.set_stroke(WHITE, width=1.5, opacity=1.0)

            def run(m, dt):
                m.move_to(rosette.point_from_proportion(alpha_of_t(self.t)))

            d.add_updater(run)
            return d

        dot_a = runner("#FFD25E", lambda t: (t / 7.0) % 1.0)
        dot_b = runner("#7FDD58", lambda t: (0.5 - t / 7.0) % 1.0)
        # las colas van DESPUÉS de sus puntos en la lista: así muestrean la
        # posición de este frame y no la del anterior
        tail_a = TracingTail(
            lambda: dot_a.get_center(),
            time_traced=0.9,
            color=WHITE,
            stroke_width=7.0,
        )
        tail_b = TracingTail(
            lambda: dot_b.get_center(),
            time_traced=0.9,
            color=WHITE,
            stroke_width=7.0,
        )

        world = [plane, rosette, labels, fine_print, tail_a, tail_b, dot_a, dot_b]

        # ── las dos cámaras ────────────────────────────────────────────────
        # la misma lupa dos veces: ×3, pegada a su punto. La estrella recorta
        # con una caja de aspecto ~1.05, así que ve 1.3 unidades de alto igual
        # que el círculo — el aumento es el mismo
        cam_lens = CameraFrame()
        cam_lens.set_frame_height(1.3)
        cam_lens.add_updater(lambda f: f.move_to(dot_a.get_center()))

        cam_star = CameraFrame()
        cam_star.set_frame_height(1.3)
        cam_star.add_updater(lambda f: f.move_to(dot_b.get_center()))

        # ── los portales: la forma RELLENA recorta y no se dibuja; el aro se ve
        lens_mask = Circle(radius=1.9, fill_opacity=1.0)
        lens_mask.set_fill(WHITE, opacity=1.0)
        lens_mask.set_stroke(opacity=0)
        lens_mask.move_to((-4.9, 0.2, 0))
        lens_rim = Circle(radius=1.9)
        lens_rim.set_fill(opacity=0)
        lens_rim.set_stroke("#FFD25E", width=4.0)
        lens_rim.move_to((-4.9, 0.2, 0))

        # El centro de la CAJA de una estrella de cinco puntas no es su
        # centro: está 0.2 u por encima (la punta de arriba llega a R y las de
        # abajo a R·cos 36°). Girar sobre él la haría orbitar, así que se
        # coloca y se gira por el centroide, que `get_real_center_of_mass` da
        # exacto.
        star_center = np.array((4.9, 0.2, 0), dtype=np.float32)
        star_mask = Star(5, outer_radius=2.15, inner_radius=1.15)
        star_mask.set_fill(WHITE, opacity=1.0)
        star_mask.set_stroke(opacity=0)
        star_mask.shift(star_center - star_mask.get_real_center_of_mass())
        star_rim = Star(5, outer_radius=2.15, inner_radius=1.15)
        star_rim.set_fill(opacity=0)
        star_rim.set_stroke("#7FDD58", width=4.0)
        star_rim.shift(star_center - star_rim.get_real_center_of_mass())
        # la ventana: una caja fija del tamaño de la estrella (no se dibuja)
        star_window = Square(side_length=4.3)
        star_window.move_to(star_center)

        # la estrella gira: la máscara (que recorta y hace de ventana) y el aro
        # visible reciben el mismo giro cada frame, sobre el mismo punto
        def spin(m, dt):
            if not dt > 0:
                return
            m.rotate(0.3 * dt, about_point=star_center)
            star_rim.rotate(0.3 * dt, about_point=star_center)

        star_mask.add_updater(spin)

        # ── rótulos ────────────────────────────────────────────────────────
        tag_lens = Text("LENS ×3", size=0.34, color="#FFD25E")
        tag_lens.next_to(lens_rim, DOWN, buff=0.3)
        tag_star = Text("LENS ×3", size=0.34, color="#7FDD58")
        tag_star.move_to((4.9, -2.65, 0))       # bajo la punta más baja que pueda haber
        tag_mid = Text("the scene camera", size=0.3, color=GREY_B)
        tag_mid.move_to((0, -2.65, 0))
        caption = Text(
            "one 2D world, three cameras — two identical lenses, each chasing its own dot: "
            "the portal's shape is just a mask, and it can spin",
            size=0.3,
            color=GREY_C,
        )
        if caption.get_width() > FRAME_WIDTH - 1.0:
            caption.set_width(FRAME_WIDTH - 1.0)
        caption.to_edge(DOWN, buff=0.3)

        self.use_composition(
            Composition(
                Layer(*world),
                crop(
                    *world,
                    inside=lens_mask,
                    feather=0.02,
                    camera=cam_lens,
                    window=lens_mask,
                ),
                crop(
                    *world,
                    inside=star_mask,
                    feather=0.02,
                    camera=cam_star,
                    window=star_window,
                ),
                Layer(lens_rim, star_rim, tag_lens, tag_star, tag_mid, caption),
                background=(0.015, 0.02, 0.04, 1),
            ),
        )

        # dos vueltas de cada punto; todo lo demás son updaters
        self.wait(14.0)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    Portals(output=str(here.with_suffix(".mp4")), fps=30, resolution=(1280, 720)).render()
