"""The vectorized surface sampler gives the bits of the per-vertex loop.

Run it directly (`python tests/test_surface.py`) or with pytest.
"""
import math
import sys

import numpy as np

from janim import math as jm
from janim.constants import TAU
from janim.core.surface import Cone, Cylinder, PlaneXY, Sphere, Surface, Torus, sample_surface

CASES = {
    "Sphere r=1 (101, 51)": (lambda u, v: (1.0 * jm.cos(u) * jm.sin(v), 1.0 * jm.sin(u) * jm.sin(v), -1.0 * jm.cos(v)), (0.0, TAU), (0.0, math.pi), 101, 51),
    "Sphere r=0.9 (17, 9)": (lambda u, v: (0.9 * jm.cos(u) * jm.sin(v), 0.9 * jm.sin(u) * jm.sin(v), -0.9 * jm.cos(v)), (0.0, TAU), (0.0, math.pi), 17, 9),
    "Torus (101, 101)": (lambda u, v: ((3.0 - 1.0 * jm.cos(v)) * jm.cos(u), (3.0 - 1.0 * jm.cos(v)) * jm.sin(u), -1.0 * jm.sin(v)), (0.0, TAU), (0.0, TAU), 101, 101),
    "PlaneXY (101, 51)": (lambda u, v: (u, v, 0.0), (-12.0, 12.0), (-5.5, 5.5), 101, 51),
    "Cylinder (2, 25)": (lambda u, v: (1.0 * jm.cos(v), 1.0 * jm.sin(v), u), (-1.0, 1.0), (0.0, TAU), 2, 25),
    "Cone (2, 25)": (lambda u, v: (u * 0.7071067811865475 * jm.cos(v), u * 0.7071067811865475 * jm.sin(v), u * 0.7071067811865476), (0.0, 1.4142135623730951), (0.0, TAU), 2, 25),
    "degenerate normal (flat line)": (lambda u, v: (u, 0.0 * v, 0.0), (0.0, 1.0), (0.0, 1.0), 5, 5),
}


def _same(a, b):
    return all(x.shape == y.shape and bool(np.all(x.view(np.uint32) == y.view(np.uint32))) for x, y in zip(a, b))


def test_vectorized_sampling_matches_the_loop():
    for name, (uv_func, u_range, v_range, nu, nv) in CASES.items():
        loop = sample_surface(uv_func, u_range, v_range, nu, nv, 1e-3, 1e-3)
        arrays = sample_surface(uv_func, u_range, v_range, nu, nv, 1e-3, 1e-3, vectorized=True)
        assert _same(loop, arrays), f"{name}: the vectorized sampler differs from the loop"


def test_builtin_surfaces_match_a_loop_sampled_surface():
    for built, (uv_func, u_range, v_range, _nu, _nv) in (
        (Sphere(resolution=(17, 9)), CASES["Sphere r=1 (101, 51)"]),
        (Torus(resolution=(21, 21)), CASES["Torus (101, 101)"]),
        (PlaneXY(x_range=(-12.0, 12.0), y_range=(-5.5, 5.5), resolution=(11, 7)), CASES["PlaneXY (101, 51)"]),
        (Cylinder(resolution=(2, 25)), CASES["Cylinder (2, 25)"]),
        (Cone(resolution=(2, 25)), CASES["Cone (2, 25)"]),
    ):
        looped = Surface(uv_func, u_range=u_range, v_range=v_range, resolution=built.resolution)
        name = type(built).__name__
        assert np.array_equal(built.points.view(np.uint32), looped.points.view(np.uint32)), name
        # Sphere replaces the sampler's nudge by the exact radial one; the others keep it
        if built.resolution != (17, 9):
            assert np.array_equal(built.d_normal_points.view(np.uint32), looped.d_normal_points.view(np.uint32)), name


def main():
    failures = 0
    for name, test in sorted(globals().items()):
        if name.startswith("test_") and callable(test):
            try:
                test()
                print(f"OK  {name}")
            except AssertionError as error:
                failures += 1
                print(f"BAD {name}: {error}")
    print("all tests passed" if not failures else f"{failures} test(s) failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
