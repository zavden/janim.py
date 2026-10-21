"""Float32 atan from Julia 1.12.6 base/special/trig.jl (MIT)."""

import math

import numpy as np


F = np.float32
PI = F(math.pi)
PI_LO = F(-8.7422776573e-08)


def _horner(x, coefficients):
    value = F(coefficients[-1])
    for coefficient in reversed(coefficients[:-1]):
        # A Float32 product and this polynomial's addend fit in Float64.
        value = F(float(x) * float(value) + float(F(coefficient)))
    return value


def atan(value):
    value = F(value)
    absolute = abs(value)
    if absolute >= F(2**26):
        return np.copysign(F(math.pi / 2), value)
    if absolute < F(2**-12):
        return value
    reduced = value
    if absolute >= F(7 / 16):
        if absolute < F(11 / 16):
            high, low = F(4.6364760399e-01), F(5.0121582440e-09)
            reduced = (F(2) * absolute - F(1)) / (F(2) + absolute)
        elif absolute < F(19 / 16):
            high, low = F(7.8539812565e-01), F(3.7748947079e-08)
            reduced = (absolute - F(1)) / (absolute + F(1))
        elif absolute < F(39 / 16):
            high, low = F(9.8279368877e-01), F(3.4473217170e-08)
            reduced = (absolute - F(1.5)) / (F(1) + F(1.5) * absolute)
        else:
            high, low = F(1.5707962513), F(7.5497894159e-08)
            reduced = -F(1) / absolute
    square = reduced * reduced
    fourth = square * square
    p = square * _horner(fourth, (3.3333328366e-01, 1.4253635705e-01, 6.1687607318e-02))
    q = fourth * _horner(fourth, (-1.9999158382e-01, -1.0648017377e-01))
    if absolute < F(7 / 16) or np.isnan(value):
        return value - value * (p + q)
    return np.copysign(high - ((reduced * (p + q) - low) - reduced), value)


def atan2(y, x):
    y, x = F(y), F(x)
    if np.isnan(x) or np.isnan(y):
        return x if np.isnan(x) else y
    if x == F(1):
        return atan(y)
    negative_x = np.signbit(x)
    if y == 0:
        return np.copysign(PI, y) if negative_x else y
    if x == 0:
        return np.copysign(PI / F(2), y)
    if np.isinf(x):
        if np.isinf(y):
            return np.copysign(F(3) * PI / F(4) if negative_x else PI / F(4), y)
        return np.copysign(PI if negative_x else F(0), y)
    if np.isinf(y):
        return np.copysign(PI / F(2), y)
    exponent = (int(abs(y).view(np.uint32)) - int(abs(x).view(np.uint32))) >> 23
    if exponent > 26:
        return np.copysign(PI / F(2) + F(0.5) * PI_LO, y)
    if x < 0 and exponent < -26:
        angle = F(0)
    else:
        angle = atan(abs(y / x))
    if negative_x:
        angle = PI - (angle - PI_LO)
    return np.copysign(angle, y)
