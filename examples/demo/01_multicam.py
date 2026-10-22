"""Demo 01 · CUATRO CÁMARAS, UN MUNDO — la multicámara 3D

El panel clásico de un editor 3D, hecho con la primitiva del compositor:
CUATRO capas que comparten la MISMA lista de mobjects, cada una con su
`CameraFrame` (`camera=`) y su rectángulo en pantalla (`window=`). No hay
copias ni proyecciones falsas: cada vista es un render de verdad, con su
z-buffer PROPIO — el satélite que enhebra el toro se esconde detrás del tubo
en unas vistas mientras sigue visible en otras, que es exactamente lo que una
copia escalada no puede hacer.

Por qué esto no se puede hacer en Manim: su cámara es UNA y dibuja al
framebuffer final. CE tiene `ZoomedScene` (una segunda cámara con un display
fijo) y nada más; GL ni eso. Aquí una cámara es un kwarg de la capa.

Dos reglas que este fichero enseña:
  · el mundo puede estar en las cuatro capas a la vez: los updaters corren
    UNA sola vez por frame (la lista viva se deduplica por identidad);
  · una ventana con la MISMA forma que el frame de su cámara (16:9 aquí)
    muestra la vista entera de esa cámara, sin recorte que adivinar.

La misma escena está en `examples/scenes/multicam_scenes.py:MulticamScene`.
El estado mutable de los updaters son listas de un elemento.

    bin/janim render examples/demo/01_multicam.py -ql
"""

from pathlib import Path

import numpy as np

from janim import *
from janim.math import cos, sin


class Multicam(Scene):
    def construct(self):
        # ── el mundo: un toro, sus ejes, y un satélite que lo enhebra ──────
        torus = Torus(
            r1=2.0,
            r2=0.55,
            resolution=(81, 41),
        )
        torus.set_color("#3F6FB0")
        torus.apply_depth_test()

        axes = VGroup()
        for direction, color in (
            ((3.2, 0, 0), "#E4573D"),
            ((0, 3.2, 0), "#63B463"),
            ((0, 0, 2.4), "#5AA8D8"),
        ):
            line = Line((0, 0, 0), direction)
            line.set_stroke(color, width=2.5)
            line.apply_depth_test()
            axes.add(line)

        sat = Sphere(radius=0.22)
        sat.set_color("#FFD25E")
        sat.apply_depth_test()
        phase = [0.0]

        def orbit(m, dt):
            phase[0] += 0.9 * dt
            m.move_to(
                np.array(
                    (2.0 + 1.1 * cos(phase[0]), 0, 1.1 * sin(phase[0])),
                    dtype=np.float32,
                ),
            )

        sat.add_updater(orbit)

        world = [torus, axes, sat]

        # ── cuatro cámaras sobre ese mundo ─────────────────────────────────
        cam_top = CameraFrame()
        cam_top.set_frame_height(7.0)

        cam_front = CameraFrame()
        cam_front.reorient(0.0, 90.0)
        cam_front.set_frame_height(7.0)

        cam_side = CameraFrame()
        cam_side.reorient(90.0, 90.0)
        cam_side.set_frame_height(7.0)

        cam_persp = CameraFrame()
        cam_persp.reorient(-35.0, 62.0)
        cam_persp.set_frame_height(8.5)
        sway = [0.0]

        def swing(frame, dt):
            sway[0] += dt
            frame.reorient(-35.0 + 18.0 * sin(0.35 * sway[0]), 62.0)

        cam_persp.add_updater(swing)

        # ── el panel: cuatro ventanas 16:9 que tejen el cuadro ─────────────
        def win(x, y):
            r = Rectangle(
                width=6.91,
                height=6.91 * 9 / 16,
            )
            r.set_stroke(GREY_B, width=3.0)
            r.set_fill(opacity=0)
            r.move_to((x, y, 0))
            return r

        w_tl = win(-3.555, 2.0)
        w_tr = win(3.555, 2.0)
        w_bl = win(-3.555, -2.0)
        w_br = win(3.555, -2.0)

        def tag(txt, w):
            t = Text(txt, size=0.26, color=GREY_B)
            t.align_to(w, UL)
            t.shift((0.18, -0.28, 0))
            return t

        tags = [
            tag("TOP", w_tl),
            tag("PERSPECTIVE", w_tr),
            tag("FRONT", w_bl),
            tag("SIDE", w_br),
        ]

        self.use_composition(
            Composition(
                Layer(*world, camera=cam_top, window=w_tl),
                Layer(*world, camera=cam_persp, window=w_tr),
                Layer(*world, camera=cam_front, window=w_bl),
                Layer(*world, camera=cam_side, window=w_br),
                Layer(w_tl, w_tr, w_bl, w_br, *tags),
                background=(0.015, 0.02, 0.04, 1),
            ),
        )

        # Todo el movimiento es de updaters: dos vueltas del satélite mientras
        # la perspectiva se mece. Las otras tres vistas ni se enteran — cada
        # cámara es suya.
        self.wait(14.0)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    Multicam(output=str(here.with_suffix(".mp4")), fps=30, resolution=(1280, 720)).render()
