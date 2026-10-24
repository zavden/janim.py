"""A million glowing particles on the Lorenz attractor, as a Manim scene."""

import numpy as np

from janim import *

SIGMA, RHO, BETA = np.float32(10), np.float32(28), np.float32(8) / np.float32(3)
CENTER = np.array((0, 0, 25), dtype=np.float32)
SCALE = np.float32(0.125)


def lorenz_step(state, out, dt, t1, t2):
    """One explicit Euler step of every particle, in Float32, from `state` into `out`.

    Both are (3, N) arrays, one contiguous row per coordinate, and every
    operation writes with `out=` into the two work rows `t1`, `t2` or into
    `out`: the same arithmetic as `x + dt * SIGMA * (y - x)`, etc., in the
    same order, without million-element temporaries.
    """
    x, y, z = state
    nx, ny, nz = out
    np.subtract(y, x, out=t1)
    np.multiply(t1, dt * SIGMA, out=t1)
    np.add(x, t1, out=nx)
    np.subtract(RHO, z, out=t1)
    np.multiply(x, t1, out=t1)
    np.subtract(t1, y, out=t1)
    np.multiply(dt, t1, out=t1)
    np.add(y, t1, out=ny)
    np.multiply(x, y, out=t1)
    np.multiply(BETA, z, out=t2)
    np.subtract(t1, t2, out=t1)
    np.multiply(dt, t1, out=t1)
    np.add(z, t1, out=nz)


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

        # the state lives by rows (3, N); two buffers alternate on every substep
        state = [np.ascontiguousarray(raw.T), np.empty((3, len(raw)), dtype=np.float32)]
        t1 = np.empty(len(raw), dtype=np.float32)
        t2 = np.empty(len(raw), dtype=np.float32)
        projected = np.empty((3, len(raw)), dtype=np.float32)
        center = CENTER.reshape(3, 1)

        def project(points):
            np.subtract(state[0], center, out=projected)
            np.multiply(SCALE, projected, out=projected)
            points[:] = projected.T                 # SCALE * (raw - CENTER), by rows

        project(dc.get_points())

        def flow(m, dt):
            if dt <= 0:
                return
            h = np.float32(dt) / np.float32(4)
            for _ in range(4):                      # four substeps: Lorenz wants a short dt
                lorenz_step(state[0], state[1], h, t1, t2)
                state[0], state[1] = state[1], state[0]
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
