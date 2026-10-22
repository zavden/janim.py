"""janim.math: the array path gives the bits of the scalar port, for every function.

Run it directly (`python tests/test_math.py`) or with pytest. Every check
compares the vectorized result with the scalar `_julia_math` function called
element by element, as 64-bit patterns (so -0.0 and 0.0 differ and NaNs
compare by their bits), over inputs that reach every branch of each function.
"""
import math
import sys

import numpy as np

from janim import math as jm
from janim.core import _julia_math as scalar_math
from janim.core import _vector_math as vector_math

RNG = np.random.default_rng(20261022)


def _bits_equal(got, ref):
    got, ref = np.asarray(got, dtype=np.float64), np.asarray(ref, dtype=np.float64)
    return got.shape == ref.shape and bool(np.all(got.view(np.uint64) == ref.view(np.uint64)))


def _elementwise(function, *arrays):
    return np.array([function(*values) for values in zip(*(a.tolist() for a in arrays))], dtype=np.float64)


def _check(name, *arrays):
    vector, scalar = getattr(vector_math, name), getattr(scalar_math, name)
    got, ref = vector(*arrays), _elementwise(scalar, *arrays)
    if not _bits_equal(got, ref):
        bad = np.flatnonzero(got.view(np.uint64) != ref.view(np.uint64))
        sample = ", ".join(f"x={tuple(float(a[i]) for a in arrays)} vector={float(got[i])!r} scalar={float(ref[i])!r}" for i in bad[:3])
        raise AssertionError(f"{name}: {len(bad)} of {len(ref)} elements differ: {sample}")
    return len(ref)


def _signed_log_uniform(low, high, n):
    return np.copysign(10.0 ** RNG.uniform(low, high, n), RNG.uniform(-1, 1, n))


TRIG_INPUTS = {
    "uniform [-50, 50]": RNG.uniform(-50, 50, 300_000),
    "uniform [-1.6e6, 1.6e6] (three Cody-Waite steps)": RNG.uniform(-1.6e6, 1.6e6, 100_000),
    "log-uniform magnitudes 1e-12..1e3": _signed_log_uniform(-12, 3, 100_000),
    "near multiples of pi/2": RNG.integers(-2000, 2000, 50_000) * (math.pi / 2) + RNG.uniform(-1e-9, 1e-9, 50_000),
    "beyond 2^20 pi/2 (Payne-Hanek)": RNG.uniform(2e6, 1e9, 200),
    "special values": np.array([
        0.0, -0.0, 1e-170, 1e-9, 2.0**-27, 2.0**-26, math.pi / 4, -math.pi / 4, 0.6744, -0.6744, 0.67,
        math.pi / 2, -math.pi / 2, 3 * math.pi / 2, 2 * math.pi, np.nextafter(math.pi / 4, 1), np.nan,
    ]),
}


def test_sin():
    for inputs in TRIG_INPUTS.values():
        _check("sin", inputs)


def test_cos():
    for inputs in TRIG_INPUTS.values():
        _check("cos", inputs)


def test_tan():
    for inputs in TRIG_INPUTS.values():
        _check("tan", inputs)


def test_acos():
    for inputs in (
        RNG.uniform(-1, 1, 300_000),
        _signed_log_uniform(-60, 0, 100_000),
        1 - 10.0 ** RNG.uniform(-17, -1, 50_000),
        -(1 - 10.0 ** RNG.uniform(-17, -1, 50_000)),
        np.array([0.0, -0.0, 1.0, -1.0, 0.5, -0.5, 2.0**-57, -(2.0**-57), np.nextafter(0.5, 0), np.nextafter(1.0, 0), -np.nextafter(1.0, 0), 5e-324, np.nan]),
    ):
        _check("acos", inputs)


def _log_uniform(low, high, n):
    return 10.0 ** RNG.uniform(low, high, n)


def _around(*values):
    out = []
    for value in values:
        down, up = np.nextafter(value, -np.inf), np.nextafter(value, np.inf)
        out += [np.nextafter(down, -np.inf), down, value, up, np.nextafter(up, np.inf)]
    return out


def test_exp():
    for inputs in (
        RNG.uniform(-745, 710, 200_000),
        RNG.uniform(-745.2, -708, 50_000),          # subnormal results
        RNG.uniform(708, 709.8, 50_000),            # just below the overflow
        _signed_log_uniform(-320, 3, 100_000),
        np.array([0.0, -0.0, np.inf, -np.inf, np.nan, 5e-324, -5e-324, 1e300, -1e300, 1.7976931348623157e308]
                 + _around(scalar_math._MAX_EXP, scalar_math._MIN_EXP, scalar_math._SUBNORM_EXP, -scalar_math._SUBNORM_EXP)),
    ):
        _check("exp", inputs)


def test_tanh():
    for inputs in (
        RNG.uniform(-50, 50, 200_000),
        RNG.uniform(-1, 1, 200_000),
        _signed_log_uniform(-320, 2, 100_000),
        np.array([0.0, -0.0, np.inf, -np.inf, np.nan, 5e-324] + _around(22.0, -22.0, 0.5, -0.5, 1.0, -1.0)),
    ):
        _check("tanh", inputs)


def test_log_and_log10():
    specials = np.array([0.0, -0.0, np.inf, np.nan, 5e-324, 1.0, 2.0, 10.0, 0.1, 1e-308, 2.2250738585072014e-308]
                        + _around(0.9394130628134757, 1.0644944589178595, 1.0, 1e100, 1e-100))
    for name in ("log", "log10"):
        for inputs in (
            _log_uniform(-320, 308, 200_000),
            RNG.uniform(0.9, 1.1, 200_000),         # Tang's procedure 2
            _log_uniform(-323.3, -307.7, 50_000),   # subnormals
            specials,
        ):
            _check(name, inputs)
        for bad in ([-1.0], [2.0, -5e-324]):
            try:
                getattr(jm, name)(np.array(bad))
            except ValueError:
                continue
            raise AssertionError(f"{name}({bad}) did not raise")


def test_hypot():
    n = 200_000
    for xs, ys in (
        (_signed_log_uniform(-320, 308, n), _signed_log_uniform(-320, 308, n)),
        (RNG.uniform(-10, 10, n), RNG.uniform(-10, 10, n)),
        (_signed_log_uniform(0, 10, n), _signed_log_uniform(0, 10, n) * 10.0 ** RNG.uniform(-30, 30, n)),
        (_log_uniform(-160, -130, 20_000), _log_uniform(-160, -130, 20_000)),   # the small scaling
        (_log_uniform(153, 154, 20_000), _log_uniform(153, 154, 20_000)),       # the large scaling
    ):
        _check("hypot", xs, ys)
    specials = np.array([0.0, -0.0, 1.0, -1.0, 3.0, 4.0, 1e308, 1e-308, 5e-324, np.inf, -np.inf, np.nan,
                         scalar_math._HYPOT_LARGE, scalar_math._HYPOT_SMALL])
    grid_x, grid_y = np.meshgrid(specials, specials)
    _check("hypot", grid_x.ravel(), grid_y.ravel())


def test_pow():
    n = 200_000
    x = _log_uniform(-300, 300, n)
    y = RNG.uniform(-300, 300, n) / np.maximum(np.abs(np.log10(x)), 1.0)   # results stay finite
    _check("pow", x, y)
    xi = RNG.uniform(-10, 10, n)
    _check("pow", xi, RNG.integers(-5000, 30000, n).astype(np.float64))     # power by squaring
    xr = RNG.uniform(0.9, 1.1, n)
    _check("pow", xr, RNG.integers(-4096, 24576, n).astype(np.float64))
    for exponent in (3.0, -2.0, 2.0, -1.0, 0.5, 1.5, 1.0 / 3.0, 10.0):
        _check("pow", RNG.uniform(-10, 10, 50_000) if float(exponent).is_integer() else RNG.uniform(0, 10, 50_000),
               np.full(50_000, exponent))
    limit = scalar_math._POW_Y_LIMIT
    _check("pow", RNG.uniform(0.5, 2.0, 20_000), RNG.choice([limit, -limit, np.inf, -np.inf, np.nextafter(limit, 0)], 20_000))
    xs = np.array([0.0, -0.0, 1.0, -1.0, np.inf, -np.inf, np.nan, 5e-324, 2.0, 0.5, -2.0])
    ys = np.array([0.0, -0.0, 1.0, -1.0, 2.0, -2.0, 3.0, 0.5, -0.5, 1e300, -1e300, np.inf, -np.inf, np.nan, 7.0, -7.0, 100.0])
    grid_x, grid_y = np.meshgrid(xs, ys)
    # negative x with a non-integral y raises in both; keep the lanes that do not
    keep = ~((grid_x.ravel() < 0) & ~np.isnan(grid_y.ravel()) & (np.trunc(grid_y.ravel()) != grid_y.ravel()) & ~np.isnan(grid_x.ravel()))
    _check("pow", grid_x.ravel()[keep], grid_y.ravel()[keep])
    for bad_x, bad_y in (([-2.0], [0.5]), ([2.0, -3.0], [0.5, 0.5]), ([-np.inf], [0.5])):
        try:
            jm.pow(np.array(bad_x), np.array(bad_y))
        except ValueError:
            continue
        raise AssertionError(f"pow({bad_x}, {bad_y}) did not raise")


def test_fma_is_correctly_rounded():
    a, b, c = (RNG.uniform(-1e3, 1e3, 200_000) for _ in range(3))
    got = vector_math.fma(a, b, c)
    ref = np.array([math.fma(x, y, z) for x, y, z in zip(a.tolist(), b.tolist(), c.tolist())])
    assert _bits_equal(got, ref)
    # cancellation: a*b + c with c = -a*b, where the fma keeps the product's error
    got = vector_math.fma(a, b, -(a * b))
    ref = np.array([math.fma(x, y, -(x * y)) for x, y in zip(a.tolist(), b.tolist())])
    assert _bits_equal(got, ref)


def test_domain_errors():
    for function, bad in ((jm.sin, [1.0, np.inf]), (jm.cos, [-np.inf]), (jm.tan, [np.inf]), (jm.acos, [0.5, 1.5]), (jm.acos, [-1.0000001])):
        try:
            function(np.array(bad))
        except ValueError:
            continue
        raise AssertionError(f"{function.__name__}({bad}) did not raise")


def test_dispatch():
    assert isinstance(jm.sin(0.5), float) and jm.sin(0.5) == scalar_math.sin(0.5)
    assert isinstance(jm.sin(np.float64(0.5)), float)
    assert isinstance(jm.sin([0.5, 1.0]), np.ndarray) and _bits_equal(jm.sin([0.5, 1.0]), [scalar_math.sin(0.5), scalar_math.sin(1.0)])
    grid = RNG.uniform(-9, 9, (7, 11))
    assert jm.cos(grid).shape == (7, 11) and _bits_equal(jm.cos(grid).ravel(), _elementwise(scalar_math.cos, grid.ravel()))
    assert jm.hypot(3.0, 4.0) == 5.0 and _bits_equal(jm.hypot(np.array([3.0, 5.0]), 4.0), [5.0, scalar_math.hypot(5.0, 4.0)])
    assert jm.fma(2.0, 3.0, 1.0) == 7.0 and _bits_equal(jm.fma(np.array([2.0]), 3.0, 1.0), [7.0])
    assert jm.linear_range(0, 1, 3) == [0.0, 0.5, 1.0]
    ys, xs = RNG.uniform(-5, 5, 1000), RNG.uniform(-5, 5, 1000)
    assert _bits_equal(jm.atan2(ys, xs), [jm.atan2(float(y), float(x)) for y, x in zip(ys, xs)])
    assert _bits_equal(jm.atan(ys), [jm.atan(float(y)) for y in ys])


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
