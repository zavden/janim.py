"""ForwardDiff 1.4.3's forward-mode gradient, bit for bit with Julia (MIT sources).

Ported from ForwardDiff 1.4.3 (src/), as Julia 1.12.6 compiles it on x86-64:

- dual.jl: the arithmetic rules. `+` and `-` (lines 498-518) add or subtract
  values and partials; a Real operand leaves the partials untouched (or
  negates them, for `Real - Dual`). `*` comes from DiffRules' rule
  `(x, y) -> (y, x)` through binary_dual_definition (260-300):
  `Dual * Dual` has partials `_mul_partials(px, py, vy, vx)`, i.e.
  `px*vy + py*vx` (partials.jl mul_tuples, line 222: two rounded products
  and one add, no fma), `Dual * Real` scales the partials by the Real. `/`
  (531-543): `Dual / Real` divides values and partials, `Dual / Dual` uses
  `_div_partials` (partials.jl 99-101), `Real / Dual` scales by
  `-(divv / v)`. abs2 comes from DiffRules' `abs2(x) = x + x`
  (unary_dual_definition, 244-258): `Dual(v*v, p*(v + v))`.
- partials.jl: NANSAFE_MODE_ENABLED is false (prelude.jl line 1, no
  LocalPreferences), so `_mul_partial(p, x) = p*x` and `_div_partial(p, x) = p/x`.
- prelude.jl 29-36: pickchunksize with DEFAULT_CHUNK_THRESHOLD = 12.
- gradient.jl: gradient (16-24), vector_mode_gradient (97-102),
  chunk_mode_gradient (114-162); apiutils.jl: seed! (73-147).

A Dual here holds a value and a partials vector, and both may be arrays: a
scalar Dual times a Float64 array of shape (n,) is a Dual of value shape
(n,) and partials shape (n, chunk), element i being exactly the Julia Dual
of element i. Signed zeros follow the same rules, so the seeds that are not
in the chunk stay zero-partial Duals.

Julia's `sum(abs2, M)` is Base.mapreduce_impl (base/reduce.jl, Julia 1.12.6,
lines 245-267) with blksize 1024: `v = f(a1) + f(a2)` and a sequential
`@simd` loop. How LLVM compiles it depends on the element type (code_llvm and
code_native of the reference build):

- Matrix{Dual{T,Float64,10}}: the loop is not vectorized across elements
  (only SLP inside each Dual), carries no reassoc/contract flags, and adds
  the Duals one after the other: a plain sequential sum.
- Matrix{Float64}: the loop vectorizer runs four 8-lane accumulators whose
  `fmul contract` / `fadd reassoc contract` pairs become vfmadd231pd, and the
  scalar tail is vfmadd231sd too; the first two squares are plain. Below 16
  entries Base._mapreduce adds unfused squares in order.

`abs2` of a Float64 array therefore returns `x * x` as a `Squares` array that
also remembers `x`, so that `dual_sum` can fold the square into the
accumulation exactly as Julia's `sum(abs2, M)` does.
"""

import numpy as np

from janim.core._julia_math import _fma
from janim.core._reductions import julia_sum

__all__ = [
    "Dual",
    "Squares",
    "abs2",
    "dual_sum",
    "gradient",
    "pickchunksize",
]

DEFAULT_CHUNK_THRESHOLD = 12
PAIRWISE_BLOCKSIZE = 1024


def _is_real(x):
    """A Real operand: a Python or numpy number, or a numeric array."""
    if isinstance(x, bool):
        return False
    return isinstance(x, (int, float, np.floating, np.integer, np.ndarray))


def _real(x):
    """A Real operand as Float64 (a Python float or a Float64 array)."""
    if isinstance(x, np.ndarray):
        return x.astype(np.float64, copy=False)
    return float(x)


def _lanes(factor):
    """A value (scalar or array) shaped to scale partials along their last axis."""
    if isinstance(factor, np.ndarray):
        return factor[..., None]
    return factor


def _widen(partials, value):
    """Partials broadcast to the value's shape, when a Real operand widened it."""
    if isinstance(value, np.ndarray) and partials.ndim == 1:
        return np.broadcast_to(partials, (*value.shape, partials.shape[-1])).copy()
    return partials


class Dual:
    """ForwardDiff.Dual{T, Float64, N}: a value and N partials, or arrays of them.

    `value` is a float or a Float64 array of shape S; `partials` has shape
    S + (N,). Arithmetic with floats, ints and Float64 arrays follows
    ForwardDiff's rules operation by operation.
    """

    __slots__ = ("value", "partials")
    # numpy defers to the Dual methods instead of building object arrays.
    __array_ufunc__ = None

    def __init__(self, value, partials):
        self.value = value
        self.partials = partials

    @property
    def npartials(self):
        return self.partials.shape[-1]

    def __repr__(self):
        return f"Dual({self.value!r}, {self.partials!r})"

    # ── + and - (dual.jl 498-518) ──────────────────────────────────────────

    def __add__(self, other):
        if isinstance(other, Dual):
            return Dual(self.value + other.value, self.partials + other.partials)
        if not _is_real(other):
            return NotImplemented
        value = self.value + _real(other)
        return Dual(value, _widen(self.partials, value))

    def __radd__(self, other):
        if not _is_real(other):
            return NotImplemented
        value = _real(other) + self.value
        return Dual(value, _widen(self.partials, value))

    def __sub__(self, other):
        if isinstance(other, Dual):
            return Dual(self.value - other.value, self.partials - other.partials)
        if not _is_real(other):
            return NotImplemented
        value = self.value - _real(other)
        return Dual(value, _widen(self.partials, value))

    def __rsub__(self, other):
        if not _is_real(other):
            return NotImplemented
        value = _real(other) - self.value
        return Dual(value, _widen(-self.partials, value))

    def __neg__(self):
        return Dual(-self.value, -self.partials)

    def __pos__(self):
        return self

    # ── * (DiffRules `*`, dual.jl 260-301 and partials.jl 87-97, 222-224) ──

    def __mul__(self, other):
        if isinstance(other, Dual):
            value_x = self.value
            value_y = other.value
            # _mul_partials(px, py, vy, vx): px*vy + py*vx, each product rounded.
            partials = self.partials * _lanes(value_y) + other.partials * _lanes(value_x)
            return Dual(value_x * value_y, partials)
        if not _is_real(other):
            return NotImplemented
        other = _real(other)
        # val = vx * y; partials = partials(x) * y
        return Dual(self.value * other, self.partials * _lanes(other))

    def __rmul__(self, other):
        if not _is_real(other):
            return NotImplemented
        other = _real(other)
        # val = x * vy; partials = partials(y) * x
        return Dual(other * self.value, self.partials * _lanes(other))

    # ── / (dual.jl 531-543, partials.jl 91-93, 99-101) ─────────────────────

    def __truediv__(self, other):
        if isinstance(other, Dual):
            value_x = self.value
            value_y = other.value
            # _div_partials(px, py, vx, vy) = _mul_partials(px, py, inv(vy), -(vx / (vy*vy)))
            afactor = 1.0 / value_y
            bfactor = -(value_x / (value_y * value_y))
            partials = self.partials * _lanes(afactor) + other.partials * _lanes(bfactor)
            return Dual(value_x / value_y, partials)
        if not _is_real(other):
            return NotImplemented
        other = _real(other)
        return Dual(self.value / other, self.partials / _lanes(other))

    def __rtruediv__(self, other):
        if not _is_real(other):
            return NotImplemented
        value = self.value
        divv = _real(other) / value
        return Dual(divv, self.partials * _lanes(-(divv / value)))


class Squares(np.ndarray):
    """`abs2` of a Float64 array: the rounded squares, remembering their roots.

    It is an ordinary array of `x * x`; `dual_sum` reads `roots` to
    reproduce the fused accumulation of Julia's `sum(abs2, M)`.
    """

    def __new__(cls, roots):
        roots = np.array(roots, dtype=np.float64)
        squares = (roots * roots).view(cls)
        squares.roots = roots
        return squares

    def __array_finalize__(self, obj):
        # Slices and arithmetic results are no longer the squares of `roots`.
        self.roots = None


def abs2(x):
    """abs2: ForwardDiff's `Dual(v*v, p*(v + v))`, or `x * x` for Float64 values."""
    if isinstance(x, Dual):
        value = x.value
        return Dual(value * value, x.partials * _lanes(value + value))
    if isinstance(x, np.ndarray):
        return Squares(x)
    x = float(x)
    return x * x


# ── Base.sum(abs2, M) and Base.sum(M) (base/reduce.jl, Julia 1.12.6) ────────


def _dual_rows(parts):
    values = []
    partials = []
    for part in parts:
        value = np.asarray(part.value, dtype=np.float64)
        values.append(value.reshape(-1))
        width = part.partials.shape[-1]
        partials.append(np.asarray(part.partials, dtype=np.float64).reshape(-1, width))
    return np.concatenate(values), np.concatenate(partials)


def _dual_impl(values, partials, first, last):
    """mapreduce_impl over Duals: sequential below the block size, else pairwise."""
    if first == last:
        return values[first], partials[first].copy()
    if last - first < PAIRWISE_BLOCKSIZE:
        # v = op(f(a1), f(a2)); then v = op(v, f(ai)) in order, lane by lane:
        # np.add.accumulate is exactly that running sum.
        return (
            np.add.accumulate(values[first:last + 1])[-1],
            np.add.accumulate(partials[first:last + 1], axis=0)[-1],
        )
    middle = first + ((last - first) >> 1)
    left_value, left_partials = _dual_impl(values, partials, first, middle)
    right_value, right_partials = _dual_impl(values, partials, middle + 1, last)
    return left_value + right_value, left_partials + right_partials


def _fused_block(roots):
    """The sequential portion of mapreduce_impl(abs2, add_sum, ::Array{Float64}), as compiled.

    `op(f(a1), f(a2))` is two rounded squares and an add; then, from the
    third entry, four 8-lane accumulators (the first lane holding that sum,
    the others -0.0) take blocks of 32 with vfmadd231pd, are combined as
    ((acc1 + acc0) + acc2) + acc3 and reduced by halves, and the remaining
    entries go through vfmadd231sd one by one.
    """
    values = roots.tolist()
    count = len(values)
    result = values[0] * values[0] + values[1] * values[1]
    index = 2
    stop = 2 + (count - 2) // 32 * 32
    if stop > 2:
        lanes = [-0.0] * 32
        lanes[0] = result
        while index < stop:
            for lane in range(32):
                x = values[index + lane]
                lanes[lane] = _fma(x, x, lanes[lane])
            index += 32
        combined = [
            ((lanes[8 + j] + lanes[j]) + lanes[16 + j]) + lanes[24 + j]
            for j in range(8)
        ]
        while len(combined) > 1:
            half = len(combined) // 2
            combined = [combined[j] + combined[j + half] for j in range(half)]
        result = combined[0]
    for x in values[index:]:
        result = _fma(x, x, result)
    return result


def _fused_impl(roots, first, last):
    if first == last:
        x = float(roots[first])
        return x * x
    if last - first < PAIRWISE_BLOCKSIZE:
        return _fused_block(roots[first:last + 1])
    middle = first + ((last - first) >> 1)
    return _fused_impl(roots, first, middle) + _fused_impl(roots, middle + 1, last)


def _sum_abs2_float(roots):
    """sum(abs2, A::Array{Float64}): Base._mapreduce (reduce.jl 417-438)."""
    count = len(roots)
    if count == 0:
        return 0.0
    if count < 16:
        # The short-array loop outside mapreduce_impl: no @simd, no fusion.
        values = roots.tolist()
        total = values[0] * values[0]
        if count == 1:
            return total
        total = total + values[1] * values[1]
        for x in values[2:]:
            total = total + x * x
        return total
    return _fused_impl(roots, 0, count - 1)


def dual_sum(*parts):
    """`sum(abs2, M)` over the parts concatenated in column-major order.

    With Duals (the output of `abs2` on Duals), Julia's loop adds the Duals
    one after the other, value and partials alike. With Float64 arrays from
    `abs2` (`Squares`), it is the fused vectorized reduction of
    `sum(abs2, ::Matrix{Float64})`; plain Float64 arrays sum as Base.sum.
    """
    if any(isinstance(part, Dual) for part in parts):
        duals = [part if isinstance(part, Dual) else _constant_like(part, parts) for part in parts]
        values, partials = _dual_rows(duals)
        if len(values) == 0:
            raise ValueError("reducing over an empty collection is not allowed")
        value, total = _dual_impl(values, partials, 0, len(values) - 1)
        return Dual(float(value), total)
    if all(isinstance(part, Squares) and part.roots is not None for part in parts):
        roots = np.concatenate([part.roots.reshape(-1) for part in parts])
        return _sum_abs2_float(roots)
    values = [np.asarray(part, dtype=np.float64).reshape(-1) for part in parts]
    return float(julia_sum(np.concatenate(values)))


def _constant_like(part, parts):
    """A Float64 part next to Duals: zero partials, as convert(Dual, x) makes them."""
    width = next(p.partials.shape[-1] for p in parts if isinstance(p, Dual))
    value = np.asarray(part, dtype=np.float64)
    return Dual(value, np.zeros((*value.shape, width), dtype=np.float64))


# ── the gradient: gradient.jl and apiutils.jl ───────────────────────────────


def pickchunksize(input_length, threshold=DEFAULT_CHUNK_THRESHOLD):
    """ForwardDiff.pickchunksize (prelude.jl 29-36)."""
    if input_length <= threshold:
        return input_length
    chunks = -(-input_length // threshold)
    return -(-input_length // chunks)


def _seed(duals, x, chunk, first, count):
    """seed!(duals, x, index, seeds, chunksize): unit partials for `count` entries."""
    for offset in range(count):
        partials = np.zeros(chunk, dtype=np.float64)
        partials[offset] = 1.0
        duals[first + offset] = Dual(float(x[first + offset]), partials)


def _unseed(duals, x, chunk, first):
    """seed!(duals, x, index): zero partials from `first` to the end."""
    for index in range(first, len(x)):
        duals[index] = Dual(float(x[index]), np.zeros(chunk, dtype=np.float64))


def _extract(result, ydual, first, count):
    """extract_gradient_chunk!: the first `count` partials of f's Dual."""
    if isinstance(ydual, Dual) and np.ndim(ydual.value) != 0:
        raise ValueError(
            "gradient(f, x) expects that f(x) is a real number. Perhaps you meant jacobian(f, x)?"
        )
    for offset in range(count):
        if isinstance(ydual, Dual):
            result[first + offset] = ydual.partials[offset]
        else:
            result[first + offset] = 0.0


def gradient(f, x):
    """ForwardDiff.gradient(f, x) with the default GradientConfig.

    `f` receives a Float64-valued object array of Duals (indexable like the
    input vector) and must return a scalar Dual. The chunk size is
    pickchunksize(length(x)); with fewer entries than the threshold it is the
    vector mode (one evaluation), otherwise the chunk mode: every entry is a
    Dual, the chunk's entries carry unit seeds and the others zero partials.
    """
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 1:
        raise ValueError("gradient expects a vector")
    length = len(x)
    chunk = pickchunksize(length)
    result = np.empty(length, dtype=np.float64)
    duals = np.empty(length, dtype=object)
    if chunk == length:
        # vector_mode_gradient: seed!(xdual, x, cfg.seeds).
        _seed(duals, x, chunk, 0, length)
        _extract(result, f(duals), 0, length)
        return result
    remainder = length % chunk
    last_size = chunk if remainder == 0 else remainder
    last_index = length - last_size
    _unseed(duals, x, chunk, 0)
    # the first chunk, then the middle ones, resetting each afterwards
    _seed(duals, x, chunk, 0, chunk)
    _extract(result, f(duals), 0, chunk)
    _unseed(duals, x, chunk, 0)
    for c in range(2, (length - last_size) // chunk + 1):
        first = (c - 1) * chunk
        _seed(duals, x, chunk, first, chunk)
        _extract(result, f(duals), first, chunk)
        _unseed(duals, x, chunk, first)
    # the final chunk
    _seed(duals, x, chunk, last_index, last_size)
    _extract(result, f(duals), last_index, last_size)
    return result

