"""Bézier algebra and the float32 seams of path interpolation."""

import math
import operator

import numpy as np

from .algebra import norm, ordered_sum


def interpolate(start, end, alpha):
    """a + float32(alpha) * (b - a), with the input storage dtype."""
    start, end = np.asarray(start), np.asarray(end)
    return start + np.float32(alpha) * (end - start)


def inverse_interpolate(start, end, value):
    with np.errstate(divide="ignore", invalid="ignore"):
        return (np.float64(value) - np.float64(start)) / (np.float64(end) - np.float64(start))


def integer_interpolate(start, end, alpha):
    if alpha >= 1:
        return end - 1, 1.0
    if alpha <= 0:
        return start, 0.0
    return math.floor((1 - alpha) * start + alpha * end), ((end - start) * alpha) % 1


def bezier(points):
    points = np.asarray(points, dtype=np.float64)
    if not len(points):
        raise ValueError("bezier needs at least one control point")
    degree = len(points) - 1

    def evaluate(t):
        result = np.zeros(points.shape[1:], dtype=np.float64)
        for k, point in enumerate(points):
            result = result + (math.comb(degree, k) * _pow_int(1 - t, degree - k) * _pow_int(t, k)) * point
        return result

    return evaluate


def _two_mul(x, y):
    product = x * y
    return product, math.fma(x, y, -product) if math.isfinite(product) else math.nan


def _pow_int(x, n):
    """Julia 1.12 Base `pow_body` for nonnegative Bezier exponents."""
    x = float(x)
    if n == 0:
        return 1.0
    if n == 3:
        return x * x * x
    if not math.isfinite(x):
        return x**n
    y, x_low, y_low = 1.0, -0.0, 0.0
    while n > 1:
        if n & 1:
            error = y * x_low + x * y_low
            y, y_low = _two_mul(x, y)
            y_low += error
        error = x * 2 * x_low
        x, x_low = _two_mul(x, x)
        x_low += error
        n >>= 1
    error = y * x_low + x * y_low
    # Base's precompiled pow_body does not contract these muladd sites
    # in the reference Julia build. two_mul still uses the exact fma residual.
    return x * y + error if math.isfinite(x) and math.isfinite(error) else x * y


def partial_bezier_points(points, a, b):
    points = np.asarray(points, dtype=np.float64)
    if a == 1:
        return np.repeat(points[-1:], len(points), axis=0)
    suffix = np.array([bezier(points[i:])(a) for i in range(len(points))])
    proportion = (b - a) / (1 - a)
    return np.array([bezier(suffix[:i + 1])(proportion) for i in range(len(points))])


def split_bezier(points, t=0.5):
    return partial_bezier_points(points, 0, t), partial_bezier_points(points, t, 1)


def quadratic_point(points, t):
    """The explicitly f32 parameter and operation order used by PFP."""
    points = np.asarray(points, dtype=np.float32)
    t = np.float32(t)
    s = np.float32(1) - t
    return ((s * s) * points[0] + ((np.float32(2) * t) * s) * points[1]) + (t * t) * points[2]


def partial_quadratic_bezier_points(points, a, b):
    """Partial Bézier: f64 evaluation, f32 at each saved handle."""
    points = np.asarray(points, dtype=np.float32)
    if a == 1:
        return np.repeat(points[2:3], 3, axis=0)
    p0, p1, p2 = points.astype(np.float64)

    def curve(t):
        return (((1 - t)**2 * p0 + (2 * t * (1 - t)) * p1) + (t * t) * p2).astype(np.float32)

    h0 = curve(a) if a > 0 else points[0]
    h2 = curve(b) if b < 1 else points[2]
    prime = ((1 - a) * p1 + a * p2).astype(np.float32)
    proportion = (b - a) / (1 - a)
    h1 = ((1 - proportion) * h0.astype(np.float64) + proportion * prime.astype(np.float64)).astype(np.float32)
    return np.array([h0, h1, h2], dtype=np.float32)


_ARC_POINTS = {}        # (the bits of the angle, n) → the float32 points of that arc, bounded


def quadratic_bezier_points_for_arc(angle, n_components=8):
    """The anchors and handles of an arc of `angle` from the x axis, memoised on the bits
    of (angle, n): an Apollonian gasket builds 1 460 circles per frame from the same full
    turn. Callers get their own copy (the verbs write points in place)."""
    n_components = operator.index(n_components)
    if n_components <= 0:
        raise ValueError("n_components must be positive")
    key = (float(angle).hex(), n_components)
    cached = _ARC_POINTS.get(key)
    if cached is None:
        angles = np.array([float(angle) * k / (2 * n_components) for k in range(2 * n_components + 1)])
        points = np.column_stack((np.cos(angles), np.sin(angles), np.zeros(len(angles))))
        points[1::2] *= 1 / math.cos(angle / n_components / 2)
        cached = points.astype(np.float32)
        cached.flags.writeable = False
        if len(_ARC_POINTS) >= 1024:
            _ARC_POINTS.clear()
        _ARC_POINTS[key] = cached
    return cached.copy()


def polyline_length(points):
    points = np.asarray(points, dtype=np.float32)
    lengths = norm(points[1:] - points[:-1])
    return float(ordered_sum(lengths))


def insert_n_curves(points, n):
    points = np.asarray(points, dtype=np.float32)
    n = operator.index(n)
    if n < 0:
        raise ValueError("the number of added curves must be nonnegative")
    if len(points) == 1:
        return np.repeat(points, 2 * n + 1, axis=0)
    count = (len(points) - 1) // 2
    if count < 1:
        return points.copy()
    norms = norm(points[2::2] - points[:-2:2]).astype(np.float64)
    norms[norm(points[1::2] - points[:-2:2]) < np.float32(1e-8)] = 0
    insertions = np.zeros(count, dtype=np.int64)
    for _ in range(n):
        index = int(np.argmax(norms))
        insertions[index] += 1
        norms[index] *= int(insertions[index]) / (int(insertions[index]) + 1)
    result = [points[:1]]
    for k, number in enumerate(insertions):
        parts = int(number) + 1
        curve = points[2 * k:2 * k + 3]
        for index in range(parts):
            partial = partial_quadratic_bezier_points(curve, index / parts, (index + 1) / parts)
            result.append(partial[1:])
    return np.concatenate(result)


def cubic_to_two_quadratics(a0, c1, c2, a1):
    a0, c1, c2, a1 = np.asarray([a0, c1, c2, a1], dtype=np.float32)
    m01, m12, m23 = (a0 + c1) / 2, (c1 + c2) / 2, (c2 + a1) / 2
    m012, m123 = (m01 + m12) / 2, (m12 + m23) / 2
    middle = (m012 + m123) / 2
    return ((3 * (m01 + m012) - a0 - middle) / 4, middle, (3 * (m123 + m23) - middle - a1) / 4)


def smooth_quadratic_handles(anchors):
    anchors = np.asarray(anchors, dtype=np.float32)
    n = len(anchors)
    if n <= 1:
        return np.empty((0, 3), dtype=np.float32)
    if n == 2:
        return (anchors[:1] + anchors[1:]) / np.float32(2)
    quarter = np.float32(0.25)
    right = quarter * anchors[:-2] + anchors[1:-1] - quarter * anchors[2:]
    left = quarter * anchors[2:] + anchors[1:-1] - quarter * anchors[:-2]
    closed = np.max(np.abs(anchors[0] - anchors[-1])) <= np.float32(1e-5)
    last = quarter * anchors[-2] + anchors[-1] - quarter * anchors[1] if closed else left[-1]
    first = quarter * anchors[1] + anchors[0] - quarter * anchors[-2] if closed else right[0]
    return (np.vstack((right, last)) + np.vstack((first, left))) / np.float32(2)
