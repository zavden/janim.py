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

El bucle por partícula son operaciones de numpy sobre filas float32 contiguas,
escritas en sitio con `out=`: sin temporales de un millón de elementos.

    bin/janim render examples/demo/04_lorenz_glow.py -ql
"""

from pathlib import Path

import numpy as np

from janim import *

SIGMA04, RHO04, BETA04 = np.float32(10), np.float32(28), np.float32(8) / np.float32(3)
CENTER04 = np.array((0, 0, 25), dtype=np.float32)
SCALE04 = np.float32(0.125)


def lorenz_step(state, out, dt, t1, t2):
    """Un paso de Euler explícito de cada partícula, en Float32, de `state` a `out`.

    `state` y `out` son arrays (3, N): una fila contigua por coordenada, así
    que cada operación recorre 4 MB seguidos en vez de saltar de columna en
    columna; `t1` y `t2` son dos filas de trabajo que se reutilizan, y todas
    las operaciones escriben con `out=`. Es la misma aritmética, en el mismo
    orden, que `x + dt * SIGMA * (y - x)`, etc.: los frames no cambian.
    """
    x, y, z = state
    nx, ny, nz = out
    np.subtract(y, x, out=t1)
    np.multiply(t1, dt * SIGMA04, out=t1)
    np.add(x, t1, out=nx)                      # x + dt * σ * (y - x)
    np.subtract(RHO04, z, out=t1)
    np.multiply(x, t1, out=t1)
    np.subtract(t1, y, out=t1)
    np.multiply(dt, t1, out=t1)
    np.add(y, t1, out=ny)                      # y + dt * (x * (ρ - z) - y)
    np.multiply(x, y, out=t1)
    np.multiply(BETA04, z, out=t2)
    np.subtract(t1, t2, out=t1)
    np.multiply(dt, t1, out=t1)
    np.add(z, t1, out=nz)                      # z + dt * (x * y - β * z)


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

        # el estado vive por filas (3, N): x, y, z contiguas; dos buffers que se
        # alternan en cada subpaso, dos filas de trabajo y una (3, N) para proyectar
        state = [np.ascontiguousarray(raw.T), np.empty((3, len(raw)), dtype=np.float32)]
        t1 = np.empty(len(raw), dtype=np.float32)
        t2 = np.empty(len(raw), dtype=np.float32)
        projected = np.empty((3, len(raw)), dtype=np.float32)
        center = CENTER04.reshape(3, 1)

        def project(points):
            np.subtract(state[0], center, out=projected)
            np.multiply(SCALE04, projected, out=projected)
            points[:] = projected.T                 # SCALE * (raw - CENTER), por filas

        project(dc.get_points())

        def flow(m, dt):
            if dt <= 0:
                return
            h = np.float32(dt) / np.float32(4)
            for _ in range(4):                      # 4 subpasos: Lorenz pide dt corto
                lorenz_step(state[0], state[1], h, t1, t2)
                state[0], state[1] = state[1], state[0]
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
