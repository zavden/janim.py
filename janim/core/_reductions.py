"""Julia 1.12.6 Base reductions (MIT), with the measured AVX512 sum order.

The scalar operations reproduce that order on any Python host; numpy never
chooses the reduction tree.
"""

import numpy as np


def sum_left_to_right(values):
    """foldl(+, values; init=zero(eltype(values))) as in Julia, with one lane."""
    values = np.asarray(values)
    result = values.dtype.type(0)
    for value in values:
        result = result + value
    return result


def _horizontal(values):
    while len(values) > 1:
        half = len(values) // 2
        values = values[:half] + values[half:]
    return values[0]


def julia_sum(values):
    values = np.asarray(values)
    if values.ndim != 1 or values.dtype not in (np.dtype("float32"), np.dtype("float64")):
        raise TypeError("the reference reduction requires a Float32 or Float64 vector")
    count = len(values)
    if count == 0:
        return values.dtype.type(0)
    if count == 1:
        return values[0]
    if count > 1024:
        middle = (count + 1) // 2
        return julia_sum(values[:middle]) + julia_sum(values[middle:])
    result = values[0] + values[1]
    index = 2
    if count >= 16:
        width = 16 if values.dtype.itemsize == 4 else 8
        block = 4 * width
        stop = 2 + (count - 2) // block * block
        if stop > 2:
            lanes = np.full((4, width), -0.0, dtype=values.dtype)
            lanes[0, 0] = result
            while index < stop:
                lanes += values[index:index + block].reshape(4, width)
                index += block
            result = _horizontal(((lanes[1] + lanes[0]) + lanes[2]) + lanes[3])
        if values.dtype.itemsize == 4 and count - index >= 8:
            lanes = np.full(8, -0.0, dtype=values.dtype)
            lanes[0] = result
            stop = index + (count - index) // 8 * 8
            while index < stop:
                lanes += values[index:index + 8]
                index += 8
            result = _horizontal(lanes)
    for value in values[index:]:
        result = result + value
    return result


def julia_cumsum(values):
    values = np.asarray(values)
    result = np.empty_like(values)
    if not len(values):
        return result
    result[0] = values[0]

    def accumulate(offset, first, count):
        if count < 128:
            subtotal = values[first]
            result[first] = offset + subtotal
            for index in range(first + 1, first + count):
                subtotal = subtotal + values[index]
                result[index] = offset + subtotal
            return subtotal
        half = count // 2
        left = accumulate(offset, first, half)
        right = accumulate(offset + left, first + half, count - half)
        return left + right

    if len(values) > 1:
        accumulate(values[0], 1, len(values) - 1)
    return result
