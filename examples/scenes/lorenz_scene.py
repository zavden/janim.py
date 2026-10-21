"""A million glowing particles on the Lorenz attractor, as a Manim scene."""

import numpy as np

from janim import *

SIGMA, RHO, BETA = np.float32(10), np.float32(28), np.float32(8) / np.float32(3)
CENTER = np.array((0, 0, 25), dtype=np.float32)
SCALE = np.float32(0.125)


def lorenz_step(raw, dt):
    """One explicit Euler step of every particle, in Float32."""
    x, y, z = raw[:, 0].copy(), raw[:, 1].copy(), raw[:, 2].copy()
    raw[:, 0] = x + dt * SIGMA * (y - x)
    raw[:, 1] = y + dt * (x * (RHO - z) - y)
    raw[:, 2] = z + dt * (x * y - BETA * z)


class LorenzScene(Scene):
    def construct(self):
        self.frame.reorient(-50.0, 65.0, height=9.5)
        side = 100
        i, j, k = np.meshgrid(np.arange(1, side + 1), np.arange(1, side + 1), np.arange(1, side + 1), indexing="ij")
        raw = np.empty((side ** 3, 3), dtype=np.float32)
        raw[:, 0] = (0.4 + 1.1 * i.ravel() / side).astype(np.float32)
        raw[:, 1] = (0.4 + 1.1 * j.ravel() / side).astype(np.float32)
        raw[:, 2] = (19.6 + 1.1 * k.ravel() / side).astype(np.float32)
        dc = GlowDots(np.zeros((len(raw), 3), dtype=np.float32), radius=0.024, glow_factor=2.0)
        dc.set_opacity(0.13)
        band = color_gradient(["#1C758A", "#83C167", "#FFFF00", "#FC6255"], 256)
        zs = raw[:, 2]
        zlo, zhi = zs.min(), zs.max()
        index = np.rint(np.float32(255) * (zs - zlo) / (zhi - zlo)).astype(np.int64)
        dc.set_colors(band[index], opacity=0.13)

        def project(points):
            points[:] = SCALE * (raw - CENTER)

        project(dc.get_points())

        def flow(m, dt):
            if dt <= 0:
                return
            h = np.float32(dt) / np.float32(4)
            for _ in range(4):                      # four substeps: Lorenz wants a short dt
                lorenz_step(raw, h)
            project(m.get_points())

        dc.add_updater(flow)
        title = Text("el atractor de Lorenz — 10⁶ partículas", size=0.4, color=GREY_A)
        title.to_corner(UL, buff=0.35)
        title.fix_in_frame()
        self.use_composition(
            Composition(
                Layer(dc, effects=[Bloom(threshold=0.6, sigma=0.09)], blend="add"),
                Layer(title),
            ),
        )
        self.wait(1.0)                              # the ordered cube, for an instant
        self.play(self.frame.animate.reorient(30.0, 55.0), run_time=11.0)
        self.wait(2.0)
