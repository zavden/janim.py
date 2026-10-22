"""Janim's deterministic libm: Julia's Float64 math, bit for bit, for scalars and arrays.

`math.sin` depends on the system's libm and `np.sin` on the CPU's SIMD path,
and both differ from each other and from machine to machine in the last bit
on about 3 % of inputs. The functions here reproduce Julia 1.12.6's
implementations exactly (`janim.core._julia_math`), so a scene that computes
its geometry with them gives the same frames on every machine, and the same
frames as Janim.jl.

Every function takes a Python float and returns a float, or takes a numpy
array (or a list or tuple) and returns a float64 array computed element by
element by the vectorized port (`janim.core._vector_math`), which gives the
same bits as the scalar path and runs about five times faster per element.
Write an updater over the whole array rather than a Python loop over its
elements:

    from janim.math import cos, sin

    def waves(m, dt):
        t = self.t
        z = 0.3 * sin(1.7 * U + 1.8 * t) * cos(1.4 * V + 1.3 * t)   # U, V arrays
        m.points[:, 2] = z
        m.note_changed_data()

`atan` and `atan2` are Julia's too (`janim.core._atan`, vectorized from the
start). `fma(a, b, c)` is the correctly rounded a*b + c (Julia's `fma`, and its
`muladd` where LLVM fuses it); `linear_range(a, b, n)` and
`step_range(a, b, h)` are Julia's `range(a, b; length = n)` and `a:h:b`,
with the same floats. `exp2f`, `fastlog2` and `fastpower` are the Float32
helpers of the integrator and take scalars only.
"""
import numpy as np

from .core import _atan
from .core import _julia_math as _scalar
from .core import _vector_math as _vector
from .core._julia_math import exp2f, fastlog2, fastpower
from .core._ranges import linear_range, step_range

__all__ = [
    "sin",
    "cos",
    "tan",
    "acos",
    "tanh",
    "exp",
    "log",
    "log10",
    "pow",
    "hypot",
    "atan",
    "atan2",
    "fma",
    "exp2f",
    "fastlog2",
    "fastpower",
    "linear_range",
    "step_range",
]


def _is_array(value):
    return isinstance(value, (list, tuple)) or (isinstance(value, np.ndarray) and value.ndim > 0)


def _elementwise(scalar, *arrays):
    """The scalar function over broadcast arrays, element by element (no vectorized port)."""
    arrays = np.broadcast_arrays(*(np.asarray(a, dtype=np.float64) for a in arrays))
    flat = zip(*(a.ravel().tolist() for a in arrays))
    return np.array([scalar(*values) for values in flat], dtype=np.float64).reshape(arrays[0].shape)


def _unary(name, doc):
    scalar = getattr(_scalar, name)
    vector = getattr(_vector, name, None)

    def function(x):
        if _is_array(x):
            if vector is None:
                return _elementwise(scalar, x)
            return vector(np.asarray(x, dtype=np.float64))
        return scalar(x)

    function.__name__ = function.__qualname__ = name
    function.__doc__ = doc
    return function


def _binary(name, doc):
    scalar = getattr(_scalar, name)
    vector = getattr(_vector, name, None)

    def function(x, y):
        if _is_array(x) or _is_array(y):
            if vector is None:
                return _elementwise(scalar, x, y)
            x, y = np.broadcast_arrays(np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64))
            return vector(np.ascontiguousarray(x), np.ascontiguousarray(y))
        return scalar(x, y)

    function.__name__ = function.__qualname__ = name
    function.__doc__ = doc
    return function


sin = _unary("sin", "Julia's sin(x::Float64); x may be an array.")
cos = _unary("cos", "Julia's cos(x::Float64); x may be an array.")
tan = _unary("tan", "Julia's tan(x::Float64); x may be an array.")
acos = _unary("acos", "Julia's acos(x::Float64); x may be an array.")
tanh = _unary("tanh", "Julia's tanh(x::Float64); x may be an array.")
exp = _unary("exp", "Julia's exp(x::Float64); x may be an array.")
log = _unary("log", "Julia's log(x::Float64); x may be an array.")
log10 = _unary("log10", "Julia's log10(x::Float64): not log(x)/log(10); x may be an array.")
pow = _binary("pow", "Julia's x^y for two Float64; either may be an array.")
hypot = _binary("hypot", "Julia's hypot(x::Float64, y::Float64); either may be an array.")


def fma(a, b, c):
    """The correctly rounded a*b + c (Julia's fma); any argument may be an array."""
    if _is_array(a) or _is_array(b) or _is_array(c):
        return _vector.fma(a, b, c)
    return _scalar._fma(float(a), float(b), float(c))


def atan(x):
    """Julia's atan(x::Float64); x may be an array."""
    if _is_array(x):
        return _atan.atan(np.asarray(x, dtype=np.float64))
    return _atan.scalar_atan(float(x))


def atan2(y, x):
    """Julia's atan(y::Float64, x::Float64); either may be an array."""
    if _is_array(y) or _is_array(x):
        y, x = np.broadcast_arrays(np.asarray(y, dtype=np.float64), np.asarray(x, dtype=np.float64))
        return _atan.atan2(np.ascontiguousarray(y), np.ascontiguousarray(x))
    return _atan.scalar_atan2(float(y), float(x))
