"""Demo 11 · PERSECUCIÓN Y MINIMAPA — tres cámaras y un HUD fijo

Un cometa recorre un nudo trébol atravesando tres puertas. En pantalla, tres
vistas del MISMO mundo a la vez:

  · la principal, con la cámara de la escena orbitando por `animate`, en dos
    tramos: 11 s y otros 10 siguiendo la vuelta,
    para que el cometa complete dos pasadas por las puertas;
  · CHASE: una capa cuya cámara persigue al cometa con un updater (`move_to`
    al centro del cometa, cada frame) — el idiom que en CE pide un
    `ZoomedScene`, aquí es un updater sobre un `CameraFrame`;
  · TOP: un minimapa cenital en ventana CUADRADA — la ventana recorta la
    vista de su cámara al mayor corte central con su aspecto, así que una
    ventana cuadrada sobre una cámara 16:9 enseña el centro cuadrado.

El HUD entero (marcos, etiquetas, leyenda) va con `fix_in_frame()`: la
ventana de una capa se proyecta por la cámara del PADRE, y un mobject fijado
a pantalla se queda quieto aunque la principal orbite — por eso los recuadros
no derrapan durante el vuelo de cámara.

La estela es UNA `TracedPath` compartida por las tres capas: la lista de
updaters se deduplica por identidad, así que registra un punto por
frame, no tres.

La misma escena, con diez segundos menos de vuelo, está en
`examples/scenes/multicam_scenes.py:ChaseScene`.

`NumberPlane` ya ES el mobject (la capa lo recibe tal cual); el `normalize`
de un punto Float32 y el `cross` / `norm` sobre vectores Float64 se escriben
a mano (multiplicar por el inverso Float32 de la norma; `_cross`), y
`atan(s, v[3])` es `scalar_atan2`, el `atan` de dos argumentos.

    bin/janim render examples/demo/11_chase_camera.py -ql
"""

from pathlib import Path

import numpy as np

from janim import *
from janim.core._atan import scalar_atan2
from janim.core._julia_math import cos, sin
from janim.core.surface import _cross


def knot(t):
    return np.array(
        (
            0.85 * (sin(t) + 2 * sin(2 * t)),
            0.85 * (cos(t) - 2 * cos(2 * t)),
            -0.85 * sin(3 * t),
        ),
        dtype=np.float32,
    )


def normalize32(vector):
    """El `normalize` de StaticArrays sobre un Point3f: multiplica por el inverso Float32 de la norma."""
    x, y, z = vector
    length = np.float32(np.sqrt((x * x + y * y) + z * z))
    return (np.float32(1) / length) * vector


class ChaseCamera(Scene):
    def construct(self):
        self.frame.reorient(-30.0, 66.0, height=9.5)

        # ── el mundo: suelo, puertas, cometa y su estela ─────────────────
        floor = NumberPlane(
            (-4.0, 4.0, 1.0),
            (-4.0, 4.0, 1.0),
            width=8.0,
            height=8.0,
            background_line_color="#1E3350",
            faded_opacity=0.10,
        )

        def gate(t0):
            g = Torus(
                r1=0.42,
                r2=0.055,
                resolution=(49, 25),
            )
            g.set_color("#8AE08A")
            g.apply_depth_test()
            p = knot(t0)
            v = normalize32(knot(t0 + 1e-3) - p)
            axis = _cross(np.array((0.0, 0.0, 1.0)), v.astype(np.float64))
            s = float(np.sqrt((axis[0] * axis[0] + axis[1] * axis[1]) + axis[2] * axis[2]))
            if s > 1e-6:
                g.rotate(scalar_atan2(s, float(v[2])), axis=axis)
            g.move_to(p)
            return g

        gates = [gate(0.8), gate(2.9), gate(5.0)]

        comet = Sphere(radius=0.14)
        comet.set_color("#FFD25E")
        comet.apply_depth_test()
        tau = [0.0]

        def fly(m, dt):
            tau[0] += 0.55 * dt
            m.move_to(knot(tau[0]))

        comet.add_updater(fly)
        trail = TracedPath(
            lambda: comet.get_center(),
            stroke_color="#FFD25E",
            stroke_width=2.5,
            time_traced=4.0,
        )

        world = [floor, *gates, trail, comet]

        # ── las otras dos cámaras ────────────────────────────────────────
        cam_chase = CameraFrame()
        cam_chase.reorient(-30.0, 66.0)
        cam_chase.set_frame_height(2.4)
        cam_chase.add_updater(lambda f: f.move_to(comet.get_center()))

        cam_map = CameraFrame()
        cam_map.set_frame_height(7.5)             # cenital: φ = 0 es la planta

        # ── el HUD, fijado a pantalla ────────────────────────────────────
        w_chase = Rectangle(
            width=4.2,
            height=4.2 * 9 / 16,
        )
        w_chase.set_stroke(GREY_B, width=3.0)
        w_chase.set_fill(opacity=0)
        w_chase.to_corner(UR, buff=0.35)

        w_map = Square(side_length=2.9)
        w_map.set_stroke(GREY_B, width=3.0)
        w_map.set_fill(opacity=0)
        w_map.to_corner(DR, buff=0.35)

        def tag(txt, w):
            t = Text(txt, size=0.24, color=GREY_B)
            t.align_to(w, UL)
            t.shift((0.14, -0.26, 0))
            return t

        caption = Text(
            "three cameras, one world — the HUD does not drift: fix_in_frame",
            size=0.34,
            color=GREY_C,
        )
        caption.to_corner(DL, buff=0.4)
        hud = [w_chase, w_map, tag("CHASE", w_chase), tag("TOP", w_map), caption]
        for mob in hud:
            mob.fix_in_frame()

        self.use_composition(
            Composition(
                Layer(*world),
                Layer(*world, camera=cam_chase, window=w_chase),
                Layer(*world, camera=cam_map, window=w_map),
                Layer(*hud),
                background=(0.015, 0.02, 0.04, 1),
            ),
        )

        # dos tramos de vuelo: el original y otros diez segundos siguiendo la vuelta
        self.wait(0.5)
        self.play(self.frame.animate.reorient(25.0, 58.0), run_time=11.0)
        self.play(self.frame.animate.reorient(85.0, 64.0), run_time=10.0)
        self.wait(0.5)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    ChaseCamera(output=str(here.with_suffix(".mp4")), fps=30, resolution=(1280, 720)).render()
