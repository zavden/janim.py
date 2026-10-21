"""ManimGL rate functions, with deterministic float64 arithmetic."""

import math

import numpy as np

from .algebra import norm
from .bezier import bezier, interpolate


def linear(t):
    return float(t)


def smooth(t):
    s = 1 - t
    return (t * t * t) * (10 * s * s + 5 * s * t + t * t)


def rush_into(t):
    return 2 * smooth(0.5 * t)


def rush_from(t):
    return 2 * smooth(0.5 * (t + 1)) - 1


def double_smooth(t):
    return 0.5 * smooth(2 * t) if t < 0.5 else 0.5 * (1 + smooth(2 * t - 1))


def there_and_back(t):
    return smooth(2 * t if t < 0.5 else 2 * (1 - t))


def slow_into(t):
    return math.sqrt(1 - (1 - t) * (1 - t))


def there_and_back_with_pause(t, pause_ratio=1 / 3):
    a = 2 / (1 - pause_ratio)
    if t < 0.5 - pause_ratio / 2:
        return smooth(a * t)
    if t < 0.5 + pause_ratio / 2:
        return 1.0
    return smooth(a - a * t)


def running_start(t, pull_factor=-0.5):
    return float(bezier([0, 0, pull_factor, pull_factor, 1, 1, 1])(t))


def overshoot(t, pull_factor=1.5):
    return float(bezier([0, 0, pull_factor, pull_factor, 1, 1])(t))


def not_quite_there(func=smooth, proportion=0.7):
    return lambda t: proportion * func(t)


def wiggle(t, wiggles=2):
    return there_and_back(t) * math.sin(wiggles * math.pi * t)


def squish_rate_func(func, a=0.4, b=0.6):
    def result(t):
        if a == b:
            return float(a)
        if t < a:
            return float(func(0))
        if t > b:
            return float(func(1))
        return float(func((t - a) / (b - a)))

    return result


def lingering(t):
    return squish_rate_func(linear, 0, 0.8)(t)


def exponential_decay(t, half_life=0.1):
    return 1 - math.exp(-t / half_life)


def straight_path(start_points, end_points, alpha):
    start_points = np.asarray(start_points, dtype=np.float32)
    end_points = np.asarray(end_points, dtype=np.float32)
    if alpha == 0:
        return start_points.copy()
    if alpha == 1:
        return end_points.copy()
    return interpolate(start_points, end_points, alpha)


def path_along_arc(arc_angle, axis=(0, 0, 1)):
    """The path-arc interpolation exposed as Manim's array path callable."""
    if abs(arc_angle) < 0.01:
        return straight_path
    axis = np.asarray(axis, dtype=np.float32)
    length = norm(axis)
    if not np.isfinite(length) or length == 0:
        raise ValueError("path axis must be nonzero and finite")
    unit = axis / np.float32(length)

    def path(start_points, end_points, alpha):
        start = np.asarray(start_points, dtype=np.float32)
        end = np.asarray(end_points, dtype=np.float32)
        if alpha == 0 or alpha == 1:
            return (start if alpha == 0 else end).copy()
        middle = (end - start) / np.float32(2)
        offset = (np.cross(unit, middle).astype(np.float64) / math.tan(arc_angle / 2)).astype(np.float32)
        centers = (start + middle) + offset
        relative = start - centers
        perpendicular = np.cross(unit, relative).astype(np.float32)
        cosine, sine = math.cos(alpha * arc_angle), math.sin(alpha * arc_angle)
        return ((centers.astype(np.float64) + cosine * relative.astype(np.float64)) + sine * perpendicular.astype(np.float64)).astype(np.float32)

    return path


# ── the easings.net family (CE's `ease_*`) ──────────────────────────────────
# Thirty closed-form curves named ease_{in,out,in_out}_{curve}, evaluated in
# float64 with the same constants and branches everywhere: Julia Base's
# sin/cos/pow (janim.core._julia_math), x*x and x*x*x where Julia's
# literal_pow multiplies, and pow's compensated squaring for ^4 and ^5.
from ._julia_math import cos as _jcos, pow as _jpow, sin as _jsin
_EASE_C1 = 1.70158
_EASE_C2 = _EASE_C1 * 1.525
_EASE_C3 = _EASE_C1 + 1
_EASE_C4 = (2 * math.pi) / 3
_EASE_C5 = (2 * math.pi) / 4.5


def ease_in_sine(t):
    return 1 - _jcos((t * math.pi) / 2)


def ease_out_sine(t):
    return _jsin((t * math.pi) / 2)


def ease_in_out_sine(t):
    return -(_jcos(math.pi * t) - 1) / 2


def ease_in_quad(t):
    return t * t


def ease_out_quad(t):
    return 1 - (1 - t) * (1 - t)


def ease_in_out_quad(t):
    return 2 * t * t if t < 0.5 else 1 - (-2 * t + 2) * (-2 * t + 2) / 2


def ease_in_cubic(t):
    return t * t * t


def ease_out_cubic(t):
    return 1 - (1 - t) * (1 - t) * (1 - t)


def ease_in_out_cubic(t):
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) * (-2 * t + 2) * (-2 * t + 2) / 2


def ease_in_quart(t):
    return _jpow(t, 4)


def ease_out_quart(t):
    return 1 - _jpow(1 - t, 4)


def ease_in_out_quart(t):
    return 8 * _jpow(t, 4) if t < 0.5 else 1 - _jpow(-2 * t + 2, 4) / 2


def ease_in_quint(t):
    return _jpow(t, 5)


def ease_out_quint(t):
    return 1 - _jpow(1 - t, 5)


def ease_in_out_quint(t):
    return 16 * _jpow(t, 5) if t < 0.5 else 1 - _jpow(-2 * t + 2, 5) / 2


def ease_in_expo(t):
    return 0.0 if t == 0 else _jpow(2.0, 10 * t - 10)


def ease_out_expo(t):
    return 1.0 if t == 1 else 1 - _jpow(2.0, -10 * t)


def ease_in_out_expo(t):
    if t == 0:
        return 0.0
    if t == 1:
        return 1.0
    if t < 0.5:
        return _jpow(2.0, 20 * t - 10) / 2
    return (2 - _jpow(2.0, -20 * t + 10)) / 2


def ease_in_circ(t):
    return 1 - math.sqrt(1 - t * t)


def ease_out_circ(t):
    return math.sqrt(1 - (t - 1) * (t - 1))


def ease_in_out_circ(t):
    if t < 0.5:
        return (1 - math.sqrt(1 - (2 * t) * (2 * t))) / 2
    return (math.sqrt(1 - (-2 * t + 2) * (-2 * t + 2)) + 1) / 2


def ease_in_back(t):
    return _EASE_C3 * t * t * t - _EASE_C1 * t * t


def ease_out_back(t):
    return 1 + _EASE_C3 * ((t - 1) * (t - 1) * (t - 1)) + _EASE_C1 * ((t - 1) * (t - 1))


def ease_in_out_back(t):
    if t < 0.5:
        return (((2 * t) * (2 * t)) * ((_EASE_C2 + 1) * 2 * t - _EASE_C2)) / 2
    return (((2 * t - 2) * (2 * t - 2)) * ((_EASE_C2 + 1) * (t * 2 - 2) + _EASE_C2) + 2) / 2


def ease_in_elastic(t):
    if t == 0:
        return 0.0
    if t == 1:
        return 1.0
    return -_jpow(2.0, 10 * t - 10) * _jsin((t * 10 - 10.75) * _EASE_C4)


def ease_out_elastic(t):
    if t == 0:
        return 0.0
    if t == 1:
        return 1.0
    return _jpow(2.0, -10 * t) * _jsin((t * 10 - 0.75) * _EASE_C4) + 1


def ease_in_out_elastic(t):
    if t == 0:
        return 0.0
    if t == 1:
        return 1.0
    if t < 0.5:
        return -(_jpow(2.0, 20 * t - 10) * _jsin((20 * t - 11.125) * _EASE_C5)) / 2
    return (_jpow(2.0, -20 * t + 10) * _jsin((20 * t - 11.125) * _EASE_C5)) / 2 + 1


def ease_out_bounce(t):
    n1, d1 = 7.5625, 2.75
    if t < 1 / d1:
        return n1 * t * t
    if t < 2 / d1:
        return n1 * ((t - 1.5 / d1) * (t - 1.5 / d1)) + 0.75
    if t < 2.5 / d1:
        return n1 * ((t - 2.25 / d1) * (t - 2.25 / d1)) + 0.9375
    return n1 * ((t - 2.625 / d1) * (t - 2.625 / d1)) + 0.984375


def ease_in_bounce(t):
    return 1 - ease_out_bounce(1 - t)


def ease_in_out_bounce(t):
    if t < 0.5:
        return (1 - ease_out_bounce(1 - 2 * t)) / 2
    return (1 + ease_out_bounce(2 * t - 1)) / 2


EASE_FUNCTIONS = tuple(
    f"ease_{phase}_{curve}"
    for curve in ("sine", "quad", "cubic", "quart", "quint", "expo", "circ", "back", "elastic", "bounce")
    for phase in ("in", "out", "in_out")
)
