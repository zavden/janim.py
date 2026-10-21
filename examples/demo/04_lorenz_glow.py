"""Demo 04 · EL ATRACTOR DE LORENZ — un millón de partículas con glow

El combo que solo esta biblioteca tiene entero: un `GlowDots` de 100³
partículas cuyo updater MUTA los puntos in place (el idioma de la primitiva:
`get_points()` entrega el array vivo), sobre una capa `"add"` con un Bloom
suave. Janim no emborrona el movimiento dentro del bucle de render (`Scene`
no acepta `motion_blur`), así que el vídeo sale con exposiciones simples.
Para ver un frame emborronado está `render_frame_motion` (ver
`examples/tutorial/c3_05_motion_blur/04_render_frame_motion.py`); ojo: avanza
el estado entre sub-exposiciones, y esta nube integra en su updater.

Manim no tiene ni nube de puntos con glow por fragmento, ni capas aditivas; y
un millón de mobjects lo pararía en seco.

El color es la condición inicial: cada partícula guarda para siempre la
franja z de la que salió (el mapa de 3b1b). Ver las bandas mezclarse ES ver la
sensibilidad a condiciones iniciales — a los ~8 s el cubo ordenado es mármol
veteado.

La misma escena, con otro vuelo de cámara, está en
`examples/scenes/lorenz_scene.py`.

El bucle por partícula es una operación de numpy sobre columnas float32.

    bin/janim render examples/demo/04_lorenz_glow.py -ql
"""

from pathlib import Path

import numpy as np

from janim import *

SIGMA04, RHO04, BETA04 = np.float32(10), np.float32(28), np.float32(8) / np.float32(3)
CENTER04 = np.array((0, 0, 25), dtype=np.float32)
SCALE04 = np.float32(0.125)


def lorenz_step(raw, dt):
    """Un paso de Euler explícito de cada partícula, en Float32."""
    x, y, z = raw[:, 0].copy(), raw[:, 1].copy(), raw[:, 2].copy()
    raw[:, 0] = x + dt * SIGMA04 * (y - x)
    raw[:, 1] = y + dt * (x * (RHO04 - z) - y)
    raw[:, 2] = z + dt * (x * y - BETA04 * z)


class LorenzGlow(Scene):
    def construct(self):
        self.frame.reorient(-50.0, 65.0, height=9.5)

        # 100³ semillas en un cubo pequeño cerca del atractor (i el más
        # externo, k el más interno)
        side = 100
        i, j, k = np.meshgrid(
            np.arange(1, side + 1),
            np.arange(1, side + 1),
            np.arange(1, side + 1),
            indexing="ij",
        )
        raw = np.empty((side ** 3, 3), dtype=np.float32)
        raw[:, 0] = (0.4 + 1.1 * i.ravel() / side).astype(np.float32)
        raw[:, 1] = (0.4 + 1.1 * j.ravel() / side).astype(np.float32)
        raw[:, 2] = (19.6 + 1.1 * k.ravel() / side).astype(np.float32)

        dc = GlowDots(
            np.zeros((len(raw), 3), dtype=np.float32),
            radius=0.024,
            glow_factor=2.0,
        )
        dc.set_opacity(0.13)
        # el color ES la condición inicial: la franja z de origen, para siempre
        band = color_gradient(["#1C758A", "#83C167", "#FFFF00", "#FC6255"], 256)
        zs = raw[:, 2]
        zlo, zhi = zs.min(), zs.max()
        index = np.rint(np.float32(255) * (zs - zlo) / (zhi - zlo)).astype(np.int64)
        dc.set_colors(band[index], opacity=0.13)

        def project(points):
            points[:] = SCALE04 * (raw - CENTER04)

        project(dc.get_points())

        def flow(m, dt):
            if dt <= 0:
                return
            h = np.float32(dt) / np.float32(4)
            for _ in range(4):                      # 4 subpasos: Lorenz pide dt corto
                lorenz_step(raw, h)
            project(m.get_points())

        dc.add_updater(flow)

        title = Text(
            "the Lorenz attractor — 10⁶ particles",
            size=0.4,
            color=GREY_A,
        )
        title.to_corner(UL, buff=0.35)
        title.fix_in_frame()

        self.use_composition(
            Composition(
                Layer(dc, effects=[Bloom(threshold=0.6, sigma=0.09)], blend="add"),
                Layer(title),
            ),
        )

        self.wait(1.0)                              # el cubo ordenado, un instante
        self.play(self.frame.animate.reorient(30.0, 55.0), run_time=15.0)
        self.wait(2.0)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    # El vídeo sale sin motion blur (ver el docstring).
    LorenzGlow(output=str(here.with_suffix(".mp4")), fps=30, resolution=(1280, 720)).render()
