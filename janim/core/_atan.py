"""Vectorized Float64 atan from Julia 1.12.6 base/special/trig.jl (MIT).

The range reduction matters when two almost equal tangent angles are
subtracted, as the renderer does.

The kernel works element by element (masks, `where`, `copysign` and
arithmetic ufuncs, no reduction), so three shortcuts cannot move a bit and
halve its cost on the renderer's short arrays: a reduction band or a special
case that selects nothing is skipped instead of being evaluated on an empty
selection, the argument of Horner's rule is split once instead of at each
of its nine steps, and inputs whose shapes already agree are not broadcast.
The results are bit for bit those of the plain kernel.
"""

import math

import numpy as np

_SPLITTER = 134217729.0

_P = (
    3.33333333333329318027e-01,
    1.42857142725034663711e-01,
    9.09088713343650656196e-02,
    6.66107313738753120669e-02,
    4.97687799461593236017e-02,
    1.62858201153657823623e-02,
)
_Q = (
    -1.99999999998764832476e-01,
    -1.11111104054623557880e-01,
    -7.69187620504482999495e-02,
    -5.83357013379057348645e-02,
    -3.65315727442169155270e-02,
)


def _horner(x, coefficients):
    """Horner's rule (Julia Base `@horner`) as nested f64 muladd calls: the
    error-free product and sum of `_muladd_rows`, with the Dekker split of `x` done once."""
    split = _SPLITTER * x
    high = split - (split - x)
    low = x - high
    zero = x == 0
    value = np.full_like(x, coefficients[-1])
    for coefficient in reversed(coefficients[:-1]):
        product = x * value
        split_value = _SPLITTER * value
        high_value = split_value - (split_value - value)
        low_value = value - high_value
        product_error = ((high * high_value - product) + high * low_value + low * high_value) + low * low_value
        total = product + coefficient
        virtual = total - product
        sum_error = (product - (total - virtual)) + (coefficient - virtual)
        result = total + (product_error + sum_error)
        # An exact zero product keeps the ordinary IEEE sum (fma(-0, x, -0) == -0).
        value = np.where(zero | (value == 0), total, result)
    return value


def atan(values):
    values = np.asarray(values, dtype=np.float64)
    absolute = np.abs(values)
    reduced = values.copy()
    hi = np.zeros_like(values)
    lo = np.zeros_like(values)
    for mask, high, low, offset in (
        ((absolute >= 7 / 16) & (absolute < 11 / 16), 4.63647609000806093515e-01, 2.26987774529616870924e-17, 0.5),
        ((absolute >= 11 / 16) & (absolute < 19 / 16), 7.85398163397448278999e-01, 3.06161699786838301793e-17, 1),
        ((absolute >= 19 / 16) & (absolute < 39 / 16), 9.82793723247329054082e-01, 1.39033110312309984516e-17, 1.5),
    ):
        if not mask.any():
            continue
        x = absolute[mask]
        if offset == 0.5:
            reduced[mask] = (2 * x - 1) / (2 + x)
        elif offset == 1:
            reduced[mask] = (x - 1) / (x + 1)
        else:
            reduced[mask] = (x - 1.5) / (1 + 1.5 * x)
        hi[mask], lo[mask] = high, low
    mask = absolute >= 39 / 16
    if mask.any():
        reduced[mask] = -1 / absolute[mask]
        hi[mask], lo[mask] = math.pi / 2, 6.12323399573676603587e-17
    square = reduced * reduced
    fourth = square * square
    pq = square * _horner(fourth, _P) + fourth * _horner(fourth, _Q)
    result = values - values * pq
    mask = absolute >= 7 / 16
    if mask.any():
        result[mask] = np.copysign(
            hi[mask] - ((reduced[mask] * pq[mask] - lo[mask]) - reduced[mask]),
            values[mask],
        )
    mask = absolute < 2**-27
    if mask.any():
        result[mask] = values[mask]
    mask = absolute >= 2**66
    if mask.any():
        result[mask] = np.copysign(math.pi / 2, values[mask])
    return result


def atan2(y, x):
    y, x = np.asarray(y, dtype=np.float64), np.asarray(x, dtype=np.float64)
    if y.shape != x.shape:
        y, x = np.broadcast_arrays(y, x)
    negative_x = np.signbit(x)
    with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
        exponent_y = (np.abs(y).view(np.uint64) >> 32).astype(np.int64)
        exponent_x = (np.abs(x).view(np.uint64) >> 32).astype(np.int64)
        k = (exponent_y - exponent_x) >> 20
        z = atan(np.abs(y / x))
        z[(x < 0) & (k < -60)] = 0
        large = k > 60
        z[large] = math.pi / 2 + 0.5 * 1.2246467991473531772e-16
        corrected = math.pi - (z - 1.2246467991473531772e-16)
        result = np.copysign(np.where(negative_x & ~large, corrected, z), y)
        ones = x == 1
        if ones.any():
            result[ones] = atan(y[ones])
        zero_y = y == 0
        if zero_y.any():
            mask = zero_y & ~negative_x
            result[mask] = y[mask]
            mask = zero_y & negative_x
            result[mask] = np.copysign(math.pi, y[mask])
        mask = (x == 0) & (y != 0)
        if mask.any():
            result[mask] = np.copysign(math.pi / 2, y[mask])
        infinite_x, infinite_y = np.isinf(x), np.isinf(y)
        if infinite_x.any() or infinite_y.any():
            mask = infinite_x & ~infinite_y & (y != 0)
            result[mask] = np.copysign(np.where(negative_x[mask], math.pi, 0), y[mask])
            mask = infinite_y & ~infinite_x
            result[mask] = np.copysign(math.pi / 2, y[mask])
            mask = infinite_x & infinite_y
            result[mask] = np.copysign(np.where(negative_x[mask], 3 * math.pi / 4, math.pi / 4), y[mask])
        nan_y, nan_x = np.isnan(y), np.isnan(x)
        if nan_y.any():
            result[nan_y] = y[nan_y]
        if nan_x.any():
            result[nan_x] = x[nan_x]
    return result


def scalar_atan(value):
    return float(atan([value])[0])


def scalar_atan2(y, x):
    return float(atan2([y], [x])[0])
