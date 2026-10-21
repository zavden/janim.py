"""Geometric algebra: vectors, matrices, rotations and quaternions.

Matrices and quaternions use float64. Products explicitly preserve
left-to-right three-term sums instead of delegating their order to BLAS.
Quaternions follow ManimGL's (x, y, z, w) convention.
"""

import math
import struct
import operator

import numpy as np

# Julia Base's libm (base/special), so the results do not depend on the
# system's libm.
from ._julia_math import acos as _jacos, cos as _jcos, sin as _jsin


def Vec3(x=0.0, y=None, z=None):
    values = x if y is None and z is None and not np.isscalar(x) else (
        x,
        0.0 if y is None else y,
        0.0 if z is None else z,
    )
    result = np.array(values, dtype=np.float64)
    if result.shape != (3,):
        raise ValueError("a vector must have three components")
    return result


def Mat4(values=None):
    result = np.eye(4) if values is None else np.array(values, dtype=np.float64)
    if result.shape != (4, 4):
        raise ValueError("a homogeneous matrix must have shape (4, 4)")
    return result


def Quat(values=(0, 0, 0, 1)):
    result = np.array(values, dtype=np.float64)
    if result.shape != (4,):
        raise ValueError("a quaternion must have four components (x, y, z, w)")
    return result


def norm(vector):
    values = np.asarray(vector)
    if values.shape[-1] != 3:
        raise ValueError("norm expects three components")
    squares = values * values
    return np.sqrt((squares[..., 0] + squares[..., 1]) + squares[..., 2])


def _normalize(vector):
    """StaticArrays normalizes by multiplying by the reciprocal norm."""
    values = np.asarray(vector)
    with np.errstate(divide="ignore", invalid="ignore"):
        return (values.dtype.type(1) / norm(values)) * values


def ordered_sum(values, axis=0, dtype=np.float64):
    """Sequential accumulation, including a leading zero, as a plain loop does."""
    values = np.asarray(values, dtype=dtype)
    if values.shape[axis] == 0:
        shape = list(values.shape)
        del shape[axis]
        return np.zeros(shape, dtype=dtype)
    return np.add.accumulate(values, axis=axis, dtype=dtype).take(-1, axis=axis)


_UNIT_AXES = {}         # the bits of an axis → its read-only unit vector


def _axis_key(axis):
    """The bits of a tuple, list or array axis; None for anything else."""
    if type(axis) is tuple or type(axis) is list:
        if len(axis) != 3:
            return None
        try:
            return struct.pack("<3d", float(axis[0]), float(axis[1]), float(axis[2]))
        except (TypeError, ValueError):
            return None
    if type(axis) is np.ndarray and axis.shape == (3,) and axis.dtype.kind == "f":
        return axis.dtype.str.encode() + axis.tobytes()
    return None


def unit_axis(axis):
    """The unit vector of `axis`, memoised on its bits (a verb over a thousand
    members with the default axis normalises it once, not a thousand times);
    the result is read-only, every caller only reads it. Invalid axes raise
    as before and are never stored."""
    key = _axis_key(axis)
    if key is not None:
        cached = _UNIT_AXES.get(key)
        if cached is not None:
            return cached
    vector = Vec3(axis)
    with np.errstate(over="ignore", under="ignore"):
        length = float(norm(vector))
    if np.isfinite(vector).all() and (length == 0 or not math.isfinite(length)):
        length = math.hypot(*map(float, vector))
    if not math.isfinite(length) or length <= 0:
        raise ValueError(f"rotation axis must be nonzero and finite, got {tuple(vector.tolist())}")
    result = vector / length
    if key is not None:
        result.flags.writeable = False
        if len(_UNIT_AXES) >= 64:
            _UNIT_AXES.clear()
        _UNIT_AXES[key] = result
    return result


_ROTATION_MATRICES = {}             # the bits of (angle, axis) → its read-only matrix, bounded
_AXIS_TERMS = {}                    # the bits of an axis → (cross matrix, its square)


def _rotation_matrix_unit(angle, axis):
    """Rodrigues' matrix in Python floats: the same nine `fma` of the squared
    cross matrix and the same two elementwise sums as the array form it
    replaces (bit for bit), memoised on the bits of
    (angle, axis) in a bounded dictionary: a verb over a thousand members
    with one angle builds it once, and a thousand updaters with a thousand
    angles (every point of a spiral with its own speed, every epicycle with
    its own frequency) build theirs once per process, not once per frame.
    The cached array is read-only; every caller only reads."""
    angle = float(angle)
    x, y, z = (float(component) for component in axis)
    axis_key = struct.pack("<3d", x, y, z)
    key = struct.pack("<d", angle) + axis_key
    matrix = _ROTATION_MATRICES.get(key)
    if matrix is not None:
        return matrix
    terms = _AXIS_TERMS.get(axis_key)
    if terms is None:
        # the cross matrix and its square depend on the axis alone
        cross = ((0.0, -z, y), (z, 0.0, -x), (-y, x, 0.0))
        squared = [
            [
                math.fma(
                    cross[i][2],
                    cross[2][j],
                    math.fma(
                        cross[i][1],
                        cross[1][j],
                        cross[i][0] * cross[0][j],
                    ),
                )
                for j in range(3)
            ]
            for i in range(3)
        ]
        if len(_AXIS_TERMS) >= 64:
            _AXIS_TERMS.clear()
        terms = _AXIS_TERMS[axis_key] = (cross, squared)
    cross, squared = terms
    cosine, sine = _jcos(angle), _jsin(angle)
    rest = 1 - cosine
    matrix = np.array(
        [
            [(float(i == j) + sine * cross[i][j]) + rest * squared[i][j] for j in range(3)]
            for i in range(3)
        ],
    )
    matrix.flags.writeable = False
    if len(_ROTATION_MATRICES) >= 4096:
        _ROTATION_MATRICES.clear()
    _ROTATION_MATRICES[key] = matrix
    return matrix


def rotation_matrix(angle, axis=(0, 0, 1)):
    return _rotation_matrix_unit(angle, unit_axis(axis))


def rotation_matrix_unchecked(angle, axis):
    """Renderer door: degenerate normals intentionally propagate NaN."""
    vector = Vec3(axis)
    with np.errstate(invalid="ignore", divide="ignore"):
        return _rotation_matrix_unit(angle, _normalize(vector))


def rotation_matrix_transpose(angle, axis=(0, 0, 1)):
    return rotation_matrix(angle, axis).T


def _muladd_rows(first, second, addend):
    """Vectorized error-free product/sum for the geometry's f64 muladd.

    StaticArrays.combine_products emits nested muladd calls. Geometry inputs
    are f32 rows and bounded rotation coefficients, safely inside the normal
    splitting range. The compensated result also preserves small cancellation
    residues that ordinary multiply/add discards before the f32 assignment.
    """
    splitter = 134217729.0
    product = first * second
    split_first, split_second = splitter * first, splitter * second
    high_first = split_first - (split_first - first)
    high_second = split_second - (split_second - second)
    low_first, low_second = first - high_first, second - high_second
    product_error = ((high_first * high_second - product) + high_first * low_second + low_first * high_second) + low_first * low_second
    total = product + addend
    virtual = total - product
    sum_error = (product - (total - virtual)) + (addend - virtual)
    result = total + (product_error + sum_error)
    # Error compensation introduces positive zero. An exact zero product
    # needs the ordinary IEEE addition to retain fma(-0, x, -0) == -0.
    return np.where((first == 0) | (second == 0), total, result)


def _muladd_rows_narrow(first, high_first, low_first, second, addend):
    """`_muladd_rows` when `second` carries at most 24 significant bits (a float32
    column cast up). The Veltkamp split of such a value is the value itself and
    a +0.0 low part (2^27·x + x is exact in 53 bits), so the two terms of the
    product error that carry it are signed zeros a finite result cannot see,
    and the split of the coefficients comes precomputed. Bit for bit the
    general form."""
    product = first * second
    product_error = (high_first * second - product) + low_first * second
    total = product + addend
    virtual = total - product
    sum_error = (product - (total - virtual)) + (addend - virtual)
    result = total + (product_error + sum_error)
    return np.where((first == 0) | (second == 0), total, result)


_COLUMN_SPLITS = {}     # the bytes of a matrix → the (high, low) halves of its coefficients, bounded


def _column_splits(matrix):
    key = matrix.tobytes()
    cached = _COLUMN_SPLITS.get(key)
    if cached is None:
        split = 134217729.0 * matrix
        high = split - (split - matrix)
        if len(_COLUMN_SPLITS) >= 1024:
            _COLUMN_SPLITS.clear()
        cached = _COLUMN_SPLITS[key] = (high, matrix - high)
    return cached


def apply_matrix_rows(points, matrix):
    narrow = isinstance(points, np.ndarray) and points.dtype == np.float32
    points = np.asarray(points, dtype=np.float64)
    matrix = np.asarray(matrix, dtype=np.float64)
    first = points[..., 0:1] * matrix[:, 0]
    if not narrow:
        second = _muladd_rows(matrix[:, 1], points[..., 1:2], first)
        return _muladd_rows(matrix[:, 2], points[..., 2:3], second)
    # float32 rows (the verbs' `array - pivot`): the narrow form, same bits, fewer array operations
    high, low = _column_splits(matrix)
    second = _muladd_rows_narrow(matrix[:, 1], high[:, 1], low[:, 1], points[..., 1:2], first)
    return _muladd_rows_narrow(matrix[:, 2], high[:, 2], low[:, 2], points[..., 2:3], second)


def rotate_vector(vector, angle, axis=(0, 0, 1)):
    return apply_matrix_rows(Vec3(vector), rotation_matrix(angle, axis)).astype(np.float32)


def compass_directions(n=4, start_vect=(1, 0, 0)):
    n = operator.index(n)
    if n <= 0:
        raise ValueError("the number of directions must be positive")
    return np.array([rotate_vector(start_vect, k * math.tau / n) for k in range(n)], dtype=np.float32)


def angle_of_vector(vector):
    from ._atan import scalar_atan2

    return scalar_atan2(float(vector[1]), float(vector[0]))


def angle_between_vectors(first, second):
    first, second = Vec3(first), Vec3(second)
    lengths = float(norm(first)) * float(norm(second))
    if lengths == 0:
        return 0.0
    products = first * second
    cosine = ((products[0] + products[1]) + products[2]) / lengths
    return _jacos(min(1.0, max(-1.0, float(cosine))))


def rotation_between_vectors(first, second):
    first, second = Vec3(first), Vec3(second)
    if norm(first - second) < 1e-8:
        return np.eye(3)
    axis = np.cross(first, second)
    if norm(axis) < 1e-8:
        axis = np.cross(first, (1.0, 0.0, 0.0))
    if norm(axis) < 1e-8:
        axis = np.cross(first, (0.0, 1.0, 0.0))
    return rotation_matrix(angle_between_vectors(first, second), axis)


def quat_identity():
    return Quat()


def quat_axis_angle(axis, angle):
    axis = unit_axis(axis)
    sine, cosine = _jsin(float(angle) / 2), _jcos(float(angle) / 2)
    return Quat((*list(sine * axis), cosine))


def quat_conj(quaternion):
    x, y, z, w = quaternion
    return Quat((-x, -y, -z, w))


def quat_normalize(quaternion):
    q = Quat(quaternion)
    length = math.sqrt(((q[0] * q[0] + q[1] * q[1]) + q[2] * q[2]) + q[3] * q[3])
    return q / length if length > 0 else quat_identity()


def quat_mul(first, second):
    x1, y1, z1, w1 = map(float, first)
    x2, y2, z2, w2 = map(float, second)
    return Quat(
        (
            w1 * x2 + w2 * x1 + y1 * z2 - z1 * y2,
            w1 * y2 + w2 * y1 + z1 * x2 - x1 * z2,
            w1 * z2 + w2 * z1 + x1 * y2 - y1 * x2,
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
        ),
    )


def quat_slerp(first, second, alpha):
    first, second = Quat(first), Quat(second)
    products = first * second
    dot = float(((products[0] + products[1]) + products[2]) + products[3])
    target = -second if dot < 0 else second
    dot = abs(dot)
    if dot > 0.9995:
        return quat_normalize(first + float(alpha) * (target - first))
    theta = _jacos(min(1.0, max(-1.0, dot)))
    sine = _jsin(theta)
    return (_jsin((1 - alpha) * theta) / sine) * first + (_jsin(alpha * theta) / sine) * target


def quat_to_matrix(quaternion):
    x, y, z, w = map(float, quaternion)
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
    )


def quat_from_euler_zxz(theta, phi, gamma):
    return quat_mul(
        quat_axis_angle((0, 0, 1), theta),
        quat_mul(quat_axis_angle((1, 0, 0), phi), quat_axis_angle((0, 0, 1), gamma)),
    )


def euler_zxz_from_quat(quaternion):
    if np.array_equal(quaternion, quat_identity()):
        return (0.0, 0.0, 0.0)
    matrix = quat_to_matrix(quaternion)
    from ._atan import scalar_atan2

    phi = _jacos(min(1.0, max(-1.0, float(matrix[2, 2]))))
    if min(phi, math.pi - phi) > 1e-2:
        return (scalar_atan2(float(matrix[0, 2]), float(-matrix[1, 2])), phi, scalar_atan2(float(matrix[2, 0]), float(matrix[2, 1])))
    return (scalar_atan2(float(matrix[1, 0]), float(matrix[0, 0])), 0.0 if phi < 1e-2 else phi, 0.0)


def frame_count(duration, fps):
    """Validate a duration and frame rate and return the frame count (at least 1)."""
    duration = float(duration)
    fps = operator.index(fps)
    if not math.isfinite(duration) or duration < 0:
        raise ValueError(f"duration must be finite and nonnegative, got {duration}")
    count = duration * fps
    if fps <= 0 or not math.isfinite(count) or count >= 2**63:
        raise ValueError(f"invalid or overflowing frame count: duration={duration}, fps={fps}")
    return max(1, round(count))


def complex_to_R3(value):
    """`complex_to_R3(1 + 2j)` is `(1, 2, 0)` (as in ManimGL)."""
    value = complex(value)
    return np.array((value.real, value.imag, 0.0), dtype=np.float32)


def R3_to_complex(point):
    """The first two coordinates as a complex number; z is dropped, as GL's `complex(*point[:2])`."""
    return complex(float(point[0]), float(point[1]))


def complex_func_to_R3_func(complex_func):
    """GL's: a map of the complex plane lifted to a map of points."""
    def result(point):
        return complex_to_R3(complex_func(R3_to_complex(point)))

    return result


def R3_func_to_complex_func(function):
    """GL's: a map of points read as a map of the complex plane."""
    def result(value):
        return R3_to_complex(function(complex_to_R3(value)))

    return result
