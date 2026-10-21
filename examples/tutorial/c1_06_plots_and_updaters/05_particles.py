"""Course 1 · 6.5 — Particles: DotCloud, TrueDot and the glow question

    DotCloud(points, radius=…, color=…, opacity=…, glow_factor=…)
    TrueDot(center) · GlowDot(center) · GlowDots(points)
    set_radius / set_radii / scale_radii / set_colors / set_opacity
    dc.make_3d()                      fake spheres: shading + z-buffer
    dc.get_points()                   the LIVE array — mutate it in place

One cloud is ONE draw call, however many points: the geometry shader
expands each point into a camera-facing disc, and glow is a per-fragment
falloff (`pow(1−r, g)` on alpha) — no extra passes. The updater idiom is
IN PLACE: `dc.get_points()` hands you the live array on purpose, because
the upload is per-frame anyway.

WHEN GLOW, WHEN BLOOM — measured, not guessed:
  · sparse or volumetric clouds → `glow_factor`. It is 2–8× cheaper than
    a Bloom pass and local density reads as brightness (the Lorenz short
    in examples/demo/04_lorenz_glow.py is this recipe).
  · densely OVERLAPPING dots (points packed on a curve) → the per-dot
    alphas saturate and the halo flattens into a solid line; there, a
    Bloom layer on the FINAL image keeps the neon look — at the price of
    a fixed per-resolution pyramid.

    python examples/tutorial/c1_06_plots_and_updaters/05_particles.py
"""

from pathlib import Path

import numpy as np

from janim import *
from janim.core._atan import atan2
from janim.core._julia_math import cos, hypot, sin

PREVIEW_T = 2.5


def orbit(m, dt):
    """Move every particle along its ellipse, in place, with Julia Base's math
    (janim.core._julia_math)."""
    pts = m.get_points()                       # the live array
    xs = pts[:, 0].astype(np.float64) + 3.2    # back to circle coords
    ys = pts[:, 1].astype(np.float64) / 0.8
    thetas = atan2(ys, xs) + 0.6 * dt          # orbit (atan2, one call per frame)
    for i, (x, y, theta) in enumerate(zip(xs.tolist(), ys.tolist(), thetas.tolist())):
        r = hypot(x, y)
        pts[i] = (r * cos(theta) - 3.2, 0.8 * r * sin(theta), 0)


class Particles(Scene):
    def construct(self):
        # Left: a ring of glowing particles orbiting — the in-place idiom.
        n = 900
        ring = GlowDots(
            [(2.0 * cos(TAU * i / n) - 3.2, 1.6 * sin(TAU * i / n), 0) for i in range(1, n + 1)],
            radius=0.09,
        )
        ring.set_colors(
            color_gradient(["#1C758A", "#58C4DD", "#FFFF00"], n),
            opacity=0.55,
        )
        ring.add_updater(orbit)

        # Right: make_3d — the same primitive as little lit spheres.
        grid = DotCloud(
            [(1.6 + 0.55 * i, -1.1 + 0.55 * j, 0) for i in range(5) for j in range(5)],
            radius=0.22,
            color="#E8A33D",
        )
        grid.make_3d()

        hud = Text("one cloud, one draw call", size=0.4, color=GREY_A)
        hud.to_corner(UL, buff=0.35)
        hud.fix_in_frame()

        self.add(ring, grid, hud)
        self.play(grid.animate.rotate(0.5), run_time=2.0)
        self.wait(3.0)
        print(
            "ring: ",
            ring.get_num_points(),
            " particles · grid: ",
            grid.get_num_points(),
            " spheres · radius max ",
            round(grid.get_radius(), 2),
            sep="",
        )


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    Particles(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
