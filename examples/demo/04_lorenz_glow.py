"""Demo 04 · THE LORENZ ATTRACTOR — a million glowing particles

The combination only this library offers in full: a `GlowDots` cloud of
100³ particles whose updater MUTATES points in place (the primitive's
idiom: `get_points()` returns the live array), on an `"add"` layer with
a gentle Bloom. Janim does not blur motion inside the render loop
(`Scene` does not accept `motion_blur`), so video uses single exposures.
For a blurred frame, use `render_frame_motion` (see
`examples/tutorial/c3_05_motion_blur/04_render_frame_motion.py`); beware:
it advances state between sub-exposures, and this cloud integrates in its updater.

Manim has neither a point cloud with per-fragment glow nor additive layers;
a million mobjects would bring it to a halt.

Color is the initial condition: each particle keeps its original z band
forever (the 3b1b colormap). Watching the bands mix IS watching sensitivity
to initial conditions — at ~8 s the ordered cube becomes veined marble.

The same scene, with a different camera flight, lives in
`examples/scenes/lorenz_scene.py`.

The per-particle loop uses numpy operations on contiguous float32 rows,
written in place with `out=`: no million-element temporaries.

    bin/janim render examples/demo/04_lorenz_glow.py -ql
"""

from pathlib import Path

import numpy as np

from janim import *

SIGMA04, RHO04, BETA04 = np.float32(10), np.float32(28), np.float32(8) / np.float32(3)
CENTER04 = np.array((0, 0, 25), dtype=np.float32)
SCALE04 = np.float32(0.125)


def lorenz_step(state, out, dt, t1, t2):
    """One explicit Euler step per particle, in Float32, from `state` to `out`.

    `state` and `out` are (3, N) arrays: one contiguous row per coordinate,
    so each operation traverses 4 MB sequentially instead of jumping
    between columns; `t1` and `t2` are two reused scratch rows, and every
    operation writes with `out=`. The arithmetic and its order match
    `x + dt * SIGMA * (y - x)`, etc.: frames do not change.
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

        # 100³ seeds in a small cube near the attractor (i outermost,
        # k innermost)
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
        # color IS the initial condition: the original z band, forever
        band = color_gradient(["#1C758A", "#83C167", "#FFFF00", "#FC6255"], 256)
        zs = raw[:, 2]
        zlo, zhi = zs.min(), zs.max()
        index = np.rint(np.float32(255) * (zs - zlo) / (zhi - zlo)).astype(np.int64)
        dc.set_colors(band[index], opacity=0.13)

        # state lives in (3, N) rows: contiguous x, y, z; two buffers swapped
        # each substep, two scratch rows and a (3, N) array for projection
        state = [np.ascontiguousarray(raw.T), np.empty((3, len(raw)), dtype=np.float32)]
        t1 = np.empty(len(raw), dtype=np.float32)
        t2 = np.empty(len(raw), dtype=np.float32)
        projected = np.empty((3, len(raw)), dtype=np.float32)
        center = CENTER04.reshape(3, 1)

        def project(points):
            np.subtract(state[0], center, out=projected)
            np.multiply(SCALE04, projected, out=projected)
            points[:] = projected.T                 # SCALE * (raw - CENTER), row-wise

        project(dc.get_points())

        def flow(m, dt):
            if dt <= 0:
                return
            h = np.float32(dt) / np.float32(4)
            for _ in range(4):                      # 4 substeps: Lorenz needs a small dt
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

        self.wait(1.0)                              # the ordered cube, for a moment
        self.play(self.frame.animate.reorient(30.0, 55.0), run_time=15.0)
        self.wait(2.0)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    # The video has no motion blur (see the docstring).
    LorenzGlow(output=str(here.with_suffix(".mp4")), fps=30, resolution=(1280, 720)).render()
