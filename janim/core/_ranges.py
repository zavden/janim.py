"""Range construction at the floating-point sampling boundary, after Julia 1.12.

The rational search and compensated interpolation follow Julia Base's
twiceprecision.jl (MIT license). Fractions retain the rational
reference and step without introducing a runtime dependency.
"""

from fractions import Fraction
import math
import struct


def _rational(value):
    remainder = float(value)
    a = d = 1
    b = c = 0
    while abs(remainder) <= 2**24:
        integer = math.trunc(remainder)
        remainder -= integer
        a, c = integer * a + c, a
        b, d = integer * b + d, b
        if max(abs(a), abs(b)) > 2**24:
            a, b = c, d
            break
        if b and a / b == value:
            break
        if remainder == 0:
            break
        remainder = 1 / remainder
    return Fraction(a, b) if b and a / b == value else None


def _add12(first, second):
    if abs(second) > abs(first):
        first, second = second, first
    high = first + second
    return high, (first - high) + second


def _truncate(value, bits):
    raw = struct.unpack("Q", struct.pack("d", value))[0]
    return struct.unpack("d", struct.pack("Q", raw & ~((1 << bits) - 1)))[0]


def _rational_samples(reference, step, count, offset):
    # The high step must multiply every integer displacement exactly.
    bits = min(27, max(0, (max(offset, count - 1 - offset) - 1).bit_length()))
    high_reference = float(reference)
    low_reference = float(reference - Fraction(high_reference))
    high_step = _truncate(float(step), bits)
    low_step = float(step - Fraction(high_step))
    result = []
    for index in range(count):
        displacement = index - offset
        high, low = _add12(high_reference, displacement * high_step)
        result.append(high + (low + (displacement * low_step + low_reference)))
    return result


def step_range(start, stop, step):
    start, stop, step = float(start), float(stop), float(step)
    if not all(map(math.isfinite, (start, stop, step))) or step == 0:
        raise ValueError("range endpoints must be finite and step must be nonzero")
    rational_start, rational_stop, rational_step = map(_rational, (start, stop, step))
    if all(value is not None for value in (rational_start, rational_stop, rational_step)):
        count = max(0, math.trunc((rational_stop - rational_start) / rational_step + 1))
        if not count:
            return []
        offset = min(count - 1, max(0, round(-rational_start / rational_step)))
        return _rational_samples(
            rational_start + offset * rational_step,
            rational_step,
            count,
            offset,
        )
    length = (stop - start) / step
    count = 0 if length < 0 else round(length) + 1
    if count and (start < stop < start + (count - 1) * step or start > stop > start + (count - 1) * step):
        count -= 1
    return [start + index * step for index in range(count)]


def linear_range(start, stop, count):
    start, stop = float(start), float(stop)
    if count < 0 or not math.isfinite(start) or not math.isfinite(stop):
        raise ValueError("linear range requires finite endpoints and nonnegative count")
    if count < 2:
        return [start] if count else []
    if start == stop:
        return [start] * count
    first, last = _rational(start), _rational(stop)
    offset = min(count - 1, max(0, round(-(start / (stop - start)) * (count - 1) + 1) - 1))
    if first is not None and last is not None:
        step = (last - first) / (count - 1)
        return _rational_samples(first + offset * step, step, count, offset)
    if 0 < offset < count - 1:
        alpha = offset / (count - 1)
        reference = (1 - alpha) * start + alpha * stop
        step = (reference - start) / offset if offset < count - 1 - offset else (stop - reference) / (count - 1 - offset)
    else:
        reference = start if offset == 0 else stop
        step = (stop - start) / (count - 1)
    bits = min(27, max(0, (max(offset, count - 1 - offset) - 1).bit_length()))
    high_step = _truncate(step, bits)
    first_high, first_low = _add12(-offset * high_step, reference)
    last_high, last_low = _add12((count - 1 - offset) * high_step, reference)
    a = (start - first_high) - first_low
    b = (stop - last_high) - last_low
    low_step = (b - a) / (count - 1)
    low_reference = a + offset * low_step
    result = []
    for index in range(count):
        shift = index - offset
        high, low = _add12(reference, shift * high_step)
        result.append(high + (low + (shift * low_step + low_reference)))
    return result
