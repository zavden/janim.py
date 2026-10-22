"""The deterministic libm of `_julia_math`, for float64 numpy arrays, bit for bit.

Every function here takes arrays and returns what the scalar function of
`_julia_math` returns element by element: the same branches, the same
operations in the same order, so every rounding happens at the same place.
Branches become boolean masks and each one is evaluated only on the elements
that take it; the bit manipulation goes through `uint64` views.

Julia's fused multiply-add (`math.fma` in the scalar port) has no numpy
counterpart, so it is emulated exactly with Boldo and Melquiond's algorithm:
an error-free product (Dekker), an error-free sum, and a sum rounded to odd,
which together give the correctly rounded a*b + c for binary64 as long as
nothing underflows or overflows.

The emulated fma is exact while no Dekker split overflows (|a|, |b| < 2^995),
nothing overflows (|c|, |a*b| < 2^1020) and the product stays out of the
underflow range (|a*b| >= 2^-900, or an exact zero). Every fma below either
stays in that domain or is dominated by its addend; the two places where some
inputs leave it check lane by lane (`_fma_checked`) and hand those lanes to
the scalar code.

What falls back to the scalar code, element by element, because it is rare:

- the Payne-Hanek reduction of sin, cos and tan for |x| >= 2^20 * pi/2;
- `pow` with an integral y in the squaring range (-2^12 <= y <= 3 * 2^13),
  for the lanes where an fma of the compensated squaring leaves the exact
  domain and the result still depends on its error terms: in practice,
  integral powers whose result or intermediate powers fall below ~1e-240 or
  rise above ~1e299 while the result stays finite;
- `hypot`, for the lanes where one of its three fmas leaves the exact
  domain: the smaller operand (after hypot's own scaling) below 2^-450, h at
  or above 2^510 (both operands between ~3e153 and ~9.5e153), or a NaN.
"""
import numpy as np

from . import _julia_math as J

_SPLIT = 134217729.0  # 2^27 + 1, Dekker's splitter
_U64, _U32, _I64, _I32, _F64 = np.uint64, np.uint32, np.int64, np.int32, np.float64


# ── fma and polynomials ────────────────────────────────────────────────────


def _two_prod(a, b):
    """a*b = p + e exactly (Dekker)."""
    p = a * b
    ta = a * _SPLIT
    ah = ta - (ta - a)
    al = a - ah
    tb = b * _SPLIT
    bh = tb - (tb - b)
    bl = b - bh
    e = ((ah * bh - p) + ah * bl + al * bh) + al * bl
    return p, e


def _two_sum(a, b):
    """a + b = s + e exactly (Knuth)."""
    s = a + b
    bb = s - a
    return s, (a - (s - bb)) + (b - bb)


def _ro_sum(a, b):
    """a + b rounded to odd: the nearest float when exact, else the neighbour with an odd last bit.

    When the nearest float is even and the sum is inexact, the odd neighbour
    on the side of the error is one step of the bit pattern away: up for a
    positive float above the sum, down for a positive float below it, and the
    other way round for a negative float.
    """
    s, e = _two_sum(a, b)
    s = np.asarray(s, dtype=np.float64)
    bits = s.view(_I64)
    fix = (e != 0.0) & ((bits & 1) == 0)
    towards_larger_magnitude = (e > 0.0) == (s > 0.0)
    step = np.where(fix, np.where(towards_larger_magnitude, 1, -1), 0).astype(_I64)
    return (bits + step).view(np.float64)


def fma(a, b, c):
    """The correctly rounded a*b + c (Boldo and Melquiond, 2008)."""
    a, b, c = np.broadcast_arrays(
        np.asarray(a, dtype=np.float64),
        np.asarray(b, dtype=np.float64),
        np.asarray(c, dtype=np.float64),
    )
    uh, ul = _two_prod(a, b)
    th, tl = _two_sum(c, uh)
    result = th + _ro_sum(tl, ul)
    # (+-0) * b + (+-0) is the IEEE sum of two signed zeros (the hardware's -0.0
    # for (-0) * b + (-0)); the round-to-odd path would give +0.0.
    zeros = (uh == 0.0) & (c == 0.0)
    if zeros.any():
        result = np.where(zeros, uh + c, result)
    return result


def _horner(x, *coefficients):
    """`_julia_math._horner`: fma from the last coefficient down."""
    value = np.full(x.shape, coefficients[-1])
    for coefficient in reversed(coefficients[:-1]):
        value = fma(x, value, coefficient)
    return value


def _highword(y):
    return (y.view(_U64) >> _U64(32)).astype(_U32)


def _zero_low_word(y):
    """The float with its low 32 bits cleared."""
    return ((y.view(_U64) >> _U64(32)) << _U64(32)).view(np.float64)


def _finite_or_raise(x, name):
    if np.isinf(x).any():
        raise ValueError(f"DomainError with {float(x[np.isinf(x)][0])!r}:\n{name}(x) is only defined for finite x.")


# ── sin, cos, tan ─────────────────────────────────────────────────────────


def _sin_kernel(y):
    y2 = y * y
    y4 = y2 * y2
    r = _horner(y2, J._DS2, J._DS3, J._DS4) + y2 * y4 * _horner(y2, J._DS5, J._DS6)
    y3 = y2 * y
    return y + y3 * (J._DS1 + y2 * r)


def _sin_kernel_double(hi, lo):
    y2 = hi * hi
    y4 = y2 * y2
    r = _horner(y2, J._DS2, J._DS3, J._DS4) + y2 * y4 * _horner(y2, J._DS5, J._DS6)
    y3 = y2 * hi
    return hi - ((y2 * (0.5 * lo - y3 * r) - lo) - y3 * J._DS1)


def _cos_kernel(y):
    y2 = y * y
    y4 = y2 * y2
    r = y2 * _horner(y2, J._DC1, J._DC2, J._DC3) + y4 * y4 * _horner(y2, J._DC4, J._DC5, J._DC6)
    half_y2 = 0.5 * y2
    w = 1.0 - half_y2
    return w + (((1.0 - w) - half_y2) + (y2 * r))


def _cos_kernel_double(hi, lo):
    y2 = hi * hi
    y4 = y2 * y2
    r = y2 * _horner(y2, J._DC1, J._DC2, J._DC3) + y4 * y4 * _horner(y2, J._DC4, J._DC5, J._DC6)
    half_y2 = 0.5 * y2
    w = 1.0 - half_y2
    return w + (((1.0 - w) - half_y2) + (y2 * r - hi * lo))


def _tan_kernel(hi, lo, k):
    """`_julia_math._tan_kernel` with k an array of 1.0 (tan) and -1.0 (-1/tan)."""
    yhi, ylo = hi.copy(), lo.copy()
    above = np.abs(yhi) >= J._TAN_THRESHOLD
    if above.any():
        negative = above & (yhi < 0.0)
        yhi[negative] = -yhi[negative]
        ylo[negative] = -ylo[negative]
        yhi[above] = (J._PI_4 - yhi[above]) + (J._PI_4_LO - ylo[above])
        ylo[above] = 0.0
    y2 = yhi * yhi
    y4 = y2 * y2
    r = _horner(y4, *J._DT_EVEN)
    v = y2 * _horner(y4, *J._DT_ODD)
    y3 = y2 * yhi
    r = ylo + y2 * (y3 * (r + v) + ylo)
    r = r + J._DT1 * y3
    px = yhi + r
    out = np.empty_like(hi)
    if above.any():
        sign = np.where(np.copysign(1.0, hi[above]) < 0, -1.0, 1.0)
        ka, pa, ya, ra = k[above], px[above], yhi[above], r[above]
        out[above] = sign * (ka - 2 * (ya - (pa * pa / (ka + pa) - ra)))
    plain = ~above & (k == 1.0)
    out[plain] = px[plain]
    inverse = ~above & (k == -1.0)
    if inverse.any():
        pi, yi, ri = px[inverse], yhi[inverse], r[inverse]
        px0 = _zero_low_word(pi)
        v = ri - (px0 - yi)
        a = -1.0 / pi
        t = _zero_low_word(a)
        s = 1.0 + t * px0
        out[inverse] = t + a * (s + t * v)
    return out


def _cody_waite_2c_pio2(x, fn):
    c1 = -fn * J._PIO2_1
    c1t = -fn * J._PIO2_1T
    z = x + c1
    y1 = z + c1t
    return y1, (z - y1) + c1t


def _cody_waite_ext_pio2(x, xhp):
    v = x * J._TWO_OVER_PI
    fn = np.copysign(np.rint(v), v)
    r = fma(-fn, J._PIO2_1, x)
    w = fn * J._PIO2_1T
    j = xhp >> _U32(20)
    y1 = r - w
    i = j - ((_highword(y1) >> _U32(20)) & _U32(0x7FF))  # uint32: wraps like the scalar's & MASK32
    second = i > _U32(16)
    if second.any():
        t, fn2 = r[second], fn[second]
        w2 = fn2 * J._PIO2_2
        r2 = t - w2
        w2 = fma(fn2, J._PIO2_2T, -((t - r2) - w2))
        y12 = r2 - w2
        i2 = j[second] - ((_highword(y12) >> _U32(20)) & _U32(0x7FF))
        third = i2 > _U32(49)
        if third.any():
            t3, fn3 = r2[third], fn2[third]
            w3 = fn3 * J._PIO2_3
            r3 = t3 - w3
            w3 = fma(fn3, J._PIO2_3T, -((t3 - r3) - w3))
            r2[third] = r3
            w2[third] = w3
            y12[third] = r3 - w3
        r[second] = r2
        w[second] = w2
        y1[second] = y12
    return fn, y1, (r - y1) - w


def _rem_pio2_kernel(x):
    """(n, hi, lo) with n*pi/2 = x - (hi + lo), the branches of `_julia_math._rem_pio2_kernel`."""
    xhp = _highword(x) & _U32(0x7FFFFFFF)
    n = np.zeros(x.shape, dtype=_I64)
    hi = np.zeros_like(x)
    lo = np.zeros_like(x)
    sign = np.where(x > 0.0, 1.0, -1.0)
    upto_5pi4 = xhp <= _U32(0x400F6A7A)
    ext_a = upto_5pi4 & ((xhp & _U32(0xFFFFF)) == _U32(0x921FB))
    one = upto_5pi4 & ~ext_a & (xhp <= _U32(0x4002D97C))
    two = upto_5pi4 & ~ext_a & ~one
    upto_7pi4 = ~upto_5pi4 & (xhp <= _U32(0x4015FDBC))
    ext_d = upto_7pi4 & (xhp == _U32(0x4012D97C))
    upto_9pi4 = ~upto_5pi4 & ~upto_7pi4 & (xhp <= _U32(0x401C463B))
    ext_e = upto_9pi4 & (xhp == _U32(0x401921FB))
    medium = ~upto_5pi4 & ~upto_7pi4 & ~upto_9pi4 & (xhp < _U32(0x413921FB))
    huge = ~upto_5pi4 & ~upto_7pi4 & ~upto_9pi4 & ~medium
    fn = np.zeros_like(x)
    fn[one] = 1.0
    fn[two] = 2.0
    fn[upto_7pi4 & ~ext_d] = 3.0
    fn[upto_9pi4 & ~ext_e] = 4.0
    cody = fn != 0.0
    if cody.any():
        fnc = fn[cody] * sign[cody]
        hi[cody], lo[cody] = _cody_waite_2c_pio2(x[cody], fnc)
        n[cody] = fnc.astype(_I64)
    ext = ext_a | ext_d | ext_e | medium
    if ext.any():
        f, y1, y2 = _cody_waite_ext_pio2(x[ext], xhp[ext])
        n[ext] = f.astype(_I64)
        hi[ext] = y1
        lo[ext] = y2
    for index in np.flatnonzero(huge):
        n[index], hi[index], lo[index] = J._paynehanek(float(x[index]))
    return n, hi, lo


def _trig(x, name, tiny_limit, tiny_value, kernel, quadrants):
    x = np.ascontiguousarray(x, dtype=np.float64)
    _finite_or_raise(x, name)
    out = np.empty_like(x)
    absx = np.abs(x)
    nan = np.isnan(x)
    small = absx < J._PI_4
    tiny = small & (absx < tiny_limit)
    out[nan] = x[nan]
    out[tiny] = x[tiny] if tiny_value is None else tiny_value
    plain = small & ~tiny
    if plain.any():
        out[plain] = kernel(x[plain])
    reduced = ~small & ~nan
    if reduced.any():
        n, hi, lo = _rem_pio2_kernel(x[reduced])
        quadrant = n & 3
        result = np.empty_like(hi)
        for k in range(4):
            here = quadrant == k
            if here.any():
                result[here] = quadrants[k](hi[here], lo[here])
        out[reduced] = result
    return out


def sin(x):
    """Julia's sin(x::Float64), element by element."""
    return _trig(
        x, "sin", J._SQRT_EPS, None, _sin_kernel,
        (
            _sin_kernel_double,
            _cos_kernel_double,
            lambda hi, lo: -_sin_kernel_double(hi, lo),
            lambda hi, lo: -_cos_kernel_double(hi, lo),
        ),
    )


def cos(x):
    """Julia's cos(x::Float64), element by element."""
    return _trig(
        x, "cos", J._SQRT_HALF_EPS, 1.0, _cos_kernel,
        (
            _cos_kernel_double,
            lambda hi, lo: -_sin_kernel_double(hi, lo),
            lambda hi, lo: -_cos_kernel_double(hi, lo),
            _sin_kernel_double,
        ),
    )


def tan(x):
    """Julia's tan(x::Float64), element by element."""
    x = np.ascontiguousarray(x, dtype=np.float64)
    _finite_or_raise(x, "tan")
    out = np.empty_like(x)
    absx = np.abs(x)
    nan = np.isnan(x)
    small = absx < J._PI_4
    tiny = small & (absx < J._SQRT_EPS / 2)
    out[nan] = x[nan]
    out[tiny] = x[tiny]
    plain = small & ~tiny
    if plain.any():
        xp = x[plain]
        out[plain] = _tan_kernel(xp, np.zeros_like(xp), np.ones_like(xp))
    reduced = ~small & ~nan
    if reduced.any():
        n, hi, lo = _rem_pio2_kernel(x[reduced])
        out[reduced] = _tan_kernel(hi, lo, np.where((n & 1) == 0, 1.0, -1.0))
    return out


# ── acos ──────────────────────────────────────────────────────────────────

_ARC_P = (
    1.66666666666666657415e-01,
    -3.25565818622400915405e-01,
    2.01212532134862925881e-01,
    -4.00555345006794114027e-02,
    7.91534994289814532176e-04,
    3.47933107596021167570e-05,
)
_ARC_Q = (
    1.0,
    -2.40339491173441421878e+00,
    2.02094576023350569471e+00,
    -6.88283971605453293030e-01,
    7.70381505559019352791e-02,
)


def _arc_trt(t):
    return (t * _horner(t, *_ARC_P)) / _horner(t, *_ARC_Q)


def acos(x):
    """Julia's acos(x::Float64), element by element."""
    x = np.ascontiguousarray(x, dtype=np.float64)
    out = np.empty_like(x)
    absx = np.abs(x)
    unit = absx >= 1.0
    if unit.any():
        beyond = absx > 1.0
        if beyond.any():
            value = float(x[beyond][0])
            raise ValueError(f"DomainError with {value!r}:\nacos(x) not defined for |x| > 1")
        out[unit] = np.where(x[unit] > 0.0, 0.0, np.pi)
    below_half = ~unit & (absx < 1.0 / 2)
    if below_half.any():
        tiny = below_half & (absx < J._ACOS_X_MIN_THRESHOLD)
        out[tiny] = np.pi / 2
        mid = below_half & ~tiny
        xm = x[mid]
        out[mid] = J._PIO2_HI - (xm - (J._PIO2_LO - xm * _arc_trt(xm * xm)))
    rest = ~unit & ~below_half
    if rest.any():
        xr = x[rest]
        z = (1.0 - np.abs(xr)) * 0.5
        z_rz = _arc_trt(z)
        s = np.sqrt(z)
        result = np.empty_like(xr)
        negative = xr < 0.0
        result[negative] = J._ACOS_PI - 2.0 * (s[negative] + (z_rz[negative] * s[negative] - J._PIO2_LO))
        positive = ~negative
        df = _zero_low_word(s[positive])
        c = (z[positive] - df * df) / (s[positive] + df)
        result[positive] = 2.0 * (df + (z_rz[positive] * s[positive] + c))
        out[rest] = result
    return out


# ── tables, converted once ──────────────────────────────────────────────────
_JT = np.array(J._J_TABLE, dtype=_U64)
_TLOG = np.array(J._T_LOG_FLOAT64, dtype=_F64)                 # (129, 2): l_hi, l_lo
_TLOG_HI = np.ascontiguousarray(_TLOG[:, 0])
_TLOG_LO = np.ascontiguousarray(_TLOG[:, 1])
_TC_WORD = np.array([w for w, _ in J._T_LOG_TABLE_COMPACT], dtype=_U64)
_TC_TAIL = np.array([t for _, t in J._T_LOG_TABLE_COMPACT], dtype=_F64)
_TC_MASK = len(J._T_LOG_TABLE_COMPACT) - 1

_JU_MASK = _U64(J._JU_MASK)
_JU_CONST = _U64(J._JU_CONST)
_JL_CONST = _U64(J._JL_CONST)

# the exact domain of the emulated fma (see the module docstring)
_FMA_OP_MAX = 2.0**995
_FMA_BIG = 2.0**1020
_FMA_TINY = 2.0**-900


def _flat(x):
    """(shape, the contiguous 1-D float64 view) of any array-like."""
    a = np.asarray(x, dtype=_F64)
    return a.shape, np.ascontiguousarray(a).ravel()


def _fma_checked(a, b, c):
    """fma(a, b, c), plus the lanes where the emulation is not proven exact (see the module docstring)."""
    p = a * b
    r = fma(a, b, c)
    ap = np.abs(p)
    ok = ((np.abs(a) < _FMA_OP_MAX) & (np.abs(b) < _FMA_OP_MAX) & (np.abs(c) < _FMA_BIG)
          & (ap < _FMA_BIG) & ((ap >= _FMA_TINY) | (a == 0.0) | (b == 0.0)))
    return r, ~ok


# ── exp: base/special/exp.jl ────────────────────────────────────────────────

def _expm1b_kernel(x):
    return x * _horner(x, 0.9999999999999912, 0.4999999999999997, 0.1666666857598779, 0.04166666857598777)


def _table_unpack(ind):
    j = _JT[ind & 255]
    return (_JU_CONST | (j & _JU_MASK)).view(_F64), (_JL_CONST | (j >> _U64(8))).view(_F64)


def _exp_reduce(x):
    n_float = fma(x, J._LOG_BO256_INV, J._MAGIC_ROUND_CONST)
    # _signed(_bits(n_float), 32): the low word as an Int32 (int64 -> int32 wraps)
    n = n_float.view(_I64).astype(_I32)
    n_float = n_float - J._MAGIC_ROUND_CONST
    r = fma(n_float, J._LOG_BO256_U, x)
    r = fma(n_float, J._LOG_BO256_L, r)
    return n, n >> 8, r


def _scale(k, small_part):
    return ((k.astype(_I64) << 52) + small_part.view(_I64)).view(_F64)


def _scale_subnormal(k, small_part):
    twopk = (k.astype(_I64) + 53) << 52
    return (twopk + small_part.view(_I64)).view(_F64) * 2.0**-53


def _exp_special(x, k, small_part, out, lo_branch):
    """The `!(abs(x) <= SUBNORM_EXP)` block of both exp_impl methods, in place."""
    sp = ~(np.abs(x) <= J._SUBNORM_EXP)
    if not sp.any():
        return
    idx = np.flatnonzero(sp)
    xs = x[idx]
    ks = k[idx]
    sps = small_part[idx]
    res = out[idx]
    if lo_branch:
        m = ks == 1024
        if m.any():
            res[m] = (sps[m] * 2.0) * 2.0**1023
    m = ks <= -53
    if m.any():
        res[m] = _scale_subnormal(ks[m], sps[m])
    res[xs <= J._MIN_EXP] = 0.0
    res[xs >= J._MAX_EXP] = np.inf
    nan = np.isnan(xs)
    res[nan] = xs[nan]
    out[idx] = res


def _exp_flat(x):
    n, k, r = _exp_reduce(x)
    j_u, j_l = _table_unpack(n)
    small_part = fma(j_u, _expm1b_kernel(r), j_l) + j_u
    out = _scale(k, small_part)
    _exp_special(x, k, small_part, out, False)
    return out


def exp(x):
    """Julia's exp(x::Float64), element by element."""
    shape, x = _flat(x)
    with np.errstate(all="ignore"):
        return _exp_flat(x).reshape(shape)


def _exp_impl_lo_flat(x, xlo):
    n, k, r = _exp_reduce(x)
    j_u, j_l = _table_unpack(n)
    kern = _expm1b_kernel(r)
    very_small = fma(kern, j_u * xlo, j_l)
    hi = 1.0 + kern
    lo = (1.0 - hi) + kern
    small_part = fma(j_u, hi, fma(j_u, lo + xlo, very_small))
    out = _scale(k, small_part)
    _exp_special(x, k, small_part, out, True)
    return out


def _exp_impl_lo(x, xlo):
    """exp_impl(x, xlo, Val(:e)), element by element (x and xlo of one shape)."""
    shape, x = _flat(x)
    _, xlo = _flat(xlo)
    with np.errstate(all="ignore"):
        return _exp_impl_lo_flat(x, xlo).reshape(shape)


# ── tanh: base/special/hyperbolic.jl ────────────────────────────────────────

_TANH_P = (1.0, -0.33333333333332904, 0.13333333333267555, -0.05396825393066753, 0.02186948742242217,
           -0.008863215974794633, 0.003591910693118715, -0.0014542587440487815, 0.0005825521659411748,
           -0.00021647574085351332, 5.5752458452673005e-5)


def tanh(x):
    """Julia's tanh(x::Float64), element by element."""
    shape, x = _flat(x)
    with np.errstate(all="ignore"):
        abs2x = np.abs(2 * x)
        out = np.empty_like(x)
        large = abs2x >= J._TANH_LARGE_X
        small = abs2x <= J._TANH_SMALL_X
        mid = ~large & ~small                      # NaN goes here, as in the scalar
        if large.any():
            out[large] = np.copysign(1.0, x[large])
        if small.any():
            xs = x[small]
            out[small] = xs * _horner(xs * xs, *_TANH_P)
        if mid.any():
            k = _exp_flat(abs2x[mid])
            out[mid] = np.copysign(1 - 2 / (k + 1), x[mid])
        return out.reshape(shape)


# ── log and log10: base/special/log.jl ──────────────────────────────────────

def _log_proc1(y, mf, F, f, logb):
    jp = (128.0 * F).astype(_I64) - 127                    # int(128.0*F): an exact integer
    hi = _TLOG_HI[jp - 1]
    lo = _TLOG_LO[jp - 1]
    l_hi = mf * 0.6931471805601177 + hi                    # unfused in the source
    l_lo = mf * -1.7239444525614835e-13 + lo
    u = (2.0 * f) / (y + F)
    v = u * u
    q = u * v * _horner(v, 0.08333333333303913, 0.012500053168098584)
    m_hi, m_lo = logb
    return fma(m_hi, l_hi, fma(m_hi, (u + (q + l_lo)), m_lo * l_hi))


def _log_proc2(f, logb):
    g = 1.0 / (2.0 + f)
    u = 2.0 * f * g
    v = u * u
    q = u * v * _horner(v, 0.08333333333333179, 0.012500000003771751, 0.0022321399879194482,
                        0.0004348877777076146)
    m_hi, m_lo = logb
    return fma(m_hi, u, fma(m_lo, u, m_hi * fma(fma(-u, f, 2 * (f - u)), g, q)))


def _log_vec(x, logb, name):
    shape, x = _flat(x)
    neg = x < 0.0
    if neg.any():
        v = float(x[np.flatnonzero(neg)[0]])
        raise J._domain_error(
            v,
            f"{name} was called with a negative real argument but will only return a "
            f"complex result if called with a complex argument. Try {name}(Complex(x)).",
        )
    with np.errstate(all="ignore"):
        out = np.empty_like(x)
        out[x == 0.0] = -np.inf
        out[np.isnan(x)] = np.nan                           # math.nan, not x
        isinf = x == np.inf
        out[isinf] = np.inf
        pos = (x > 0.0) & ~isinf
        near = pos & (0.9394130628134757 < x) & (x < 1.0644944589178595)
        if near.any():
            out[near] = _log_proc2(x[near] - 1.0, logb)
        far = pos & ~near
        if far.any():
            xf = x[far]
            xu = xf.view(_U64)
            m = ((xu >> _U64(52)) & _U64(0x07FF)).astype(_I64)
            sub = m == 0
            if sub.any():
                xu = xu.copy()
                xs = xf[sub] * 1.8014398509481984e16           # 0x1p54
                us = xs.view(_U64)
                xu[sub] = us
                m[sub] = ((us >> _U64(52)) & _U64(0x07FF)).astype(_I64) - 54
            m -= 1023
            y = ((xu & _U64(0x000F_FFFF_FFFF_FFFF)) | _U64(0x3FF0_0000_0000_0000)).view(_F64)
            mf = m.astype(_F64)
            F = (y + 3.5184372088832e13) - 3.5184372088832e13
            f = y - F
            out[far] = _log_proc1(y, mf, F, f, logb)
        return out.reshape(shape)


def log(x):
    """Julia's log(x::Float64), element by element."""
    return _log_vec(x, J._LOGB_E, "log")


def log10(x):
    """Julia's log10(x::Float64), element by element."""
    return _log_vec(x, J._LOGB_10, "log10")


def _log_tab_unpack(t):
    invc = (((t & _U64(0xFF)) | _U64(0x1FF00)) << _U64(45)).view(_F64)
    logc = (t & _U64(~0xFF & J._MASK64)).view(_F64)
    return invc, logc


def _log_ext_flat(xu):
    tmp = (xu - _U64(0x3FE6955500000000)).view(_I64)
    z = (xu - (tmp.view(_U64) & _U64(0xFFF0000000000000))).view(_F64)
    k = (tmp >> 52).astype(_F64)
    idx = (tmp >> 45) & _TC_MASK
    t = _TC_WORD[idx]
    logctail = _TC_TAIL[idx]
    invc, logc = _log_tab_unpack(t)
    r = fma(z, invc, -1.0)
    t1 = fma(k, 0.6931471805598903, logc)
    t2 = t1 + r
    lo1 = fma(k, 5.497923018708371e-14, logctail)
    lo2 = t1 - t2 + r
    ar = -0.5 * r
    ar2 = r * ar
    lo3 = fma(r, ar, -ar2)
    hi = t2 + ar2
    lo4 = t2 - hi + ar2
    p = _horner(r, *J._LOG_EXT_P)
    lo = lo1 + lo2 + lo3 + fma(r * ar2, p, lo4)
    return hi, lo


def _log_ext(xu):
    """_log_ext(xu::UInt64), element by element on a uint64 array: (hi, lo)."""
    xu = np.asarray(xu, dtype=_U64)
    shape = xu.shape
    with np.errstate(all="ignore"):
        hi, lo = _log_ext_flat(np.ascontiguousarray(xu).ravel())
    return hi.reshape(shape), lo.reshape(shape)


# ── x^y: base/math.jl ───────────────────────────────────────────────────────

def _pow_body_flat(x, y):
    """pow_body(x, y) for finite x > 0 and finite y."""
    xu = x.view(_U64)
    sub = xu < _U64(1 << 52)
    if sub.any():
        xu = xu.copy()
        s = ((x[sub] * 2.0**52).view(_U64)) & _U64(0x7FFF_FFFF_FFFF_FFFF)
        xu[sub] = s - _U64(52 << 52)                             # wraps like & _MASK64
    logxhi, logxlo = _log_ext_flat(xu)
    xyhi = logxhi * y
    xylo = fma(logxhi, y, -xyhi)
    xylo = fma(logxlo, y, xylo)
    hi = xyhi + xylo
    return _exp_impl_lo_flat(hi, xylo - (hi - xyhi))


def _pow_body_int_flat(x, n):
    """pow_body(x::Float64, n::Integer) for int64 n != 0, lane by lane."""
    N = x.size
    out = np.empty(N)
    m3 = n == 3
    if m3.any():
        x3 = x[m3]
        out[m3] = x3 * x3 * x3
    mm2 = n == -2
    if mm2.any():
        x2 = x[mm2]
        rx = 1.0 / x2                                       # inv(x): +-inf at +-0
        out[mm2] = rx * rx
    act = np.flatnonzero(~m3 & ~mm2)
    if act.size == 0:
        return out
    x0 = x[act]
    n0 = n[act]
    xa = x0.copy()
    na = n0.copy()
    ya = np.ones(act.size)
    xla = np.full(act.size, -0.0)
    yla = np.zeros(act.size)
    taint = np.zeros(act.size, dtype=bool)
    neg = na < 0
    if neg.any():
        ni = np.flatnonzero(neg)
        xn = xa[ni]
        rx = 1.0 / xn
        fin = np.isfinite(xn)
        if fin.any():
            fi = ni[fin]
            f, bad = _fma_checked(xn[fin], rx[fin], -1.0)
            xla[fi] = -f * rx[fin]
            taint[fi] |= bad
        xa[ni] = rx
        na[ni] = -na[ni]
    while True:
        live = na > 1
        if not live.any():
            break
        L = slice(None) if live.all() else np.flatnonzero(live)
        xs = xa[L]
        ns = na[L]
        xl = xla[L]
        ys = ya[L]
        yl = yla[L]
        tt = taint[L]
        odd = (ns & 1) > 0
        if odd.any():
            O = slice(None) if odd.all() else np.flatnonzero(odd)
            xo = xs[O]
            yo = ys[O]
            err, b1 = _fma_checked(yo, xl[O], xo * yl[O])
            yn = xo * yo
            ylo, b2 = _fma_checked(xo, yo, -yn)
            ys[O] = yn
            yl[O] = ylo + err
            tt[O] |= b1 | b2
        err = xs * 2 * xl
        xx = xs * xs
        xlo, b3 = _fma_checked(xs, xs, -xx)
        tt |= b3
        xa[L] = xx
        xla[L] = xlo + err
        ya[L] = ys
        yla[L] = yl
        taint[L] = tt
        na[L] = ns >> 1
    err, b4 = _fma_checked(ya, xla, xa * yla)
    taint |= b4
    xy = xa * ya
    special = ~np.isfinite(xa) | ~np.isfinite(xy)
    # the scalar's err = -0.0 when x or err is not finite; with x*y not finite
    # x*y + err is x*y + (-0.0) for every finite err as well
    err[special | ~np.isfinite(err)] = -0.0
    res = xy + err
    for i in np.flatnonzero(taint & ~special):
        res[i] = J._pow_body_int(float(x0[i]), int(n0[i]))
    out[act] = res
    return out


def _pow_body_int(x, n):
    """pow_body(x, n), element by element: x float64 array, n integer array of one shape."""
    shape, x = _flat(x)
    n = np.ascontiguousarray(np.asarray(n, dtype=_I64)).ravel()
    with np.errstate(all="ignore"):
        return _pow_body_int_flat(x, n).reshape(shape)


_POW_MSG = ("Exponentiation yielding a complex result requires a complex argument.\n"
            "Replace x^y with (x+0im)^y, Complex(x)^y, or similar.")


def pow(x, y):
    """Julia's x^y, element by element; x and y broadcast (array/array, array/scalar, scalar/array)."""
    xb, yb = np.broadcast_arrays(np.asarray(x, dtype=_F64), np.asarray(y, dtype=_F64))
    shape = xb.shape
    X = np.ascontiguousarray(xb).ravel()
    Y = np.ascontiguousarray(yb).ravel()
    out = np.empty(X.size)
    with np.errstate(all="ignore"):
        todo = X.view(_U64) != _U64(0x3FF0_0000_0000_0000)
        out[~todo] = 1.0
        ynan = np.isnan(Y)
        m = todo & ynan
        out[m] = Y[m]
        todo &= ~ynan
        # Exponents greater than this always overflow or underflow.
        Yc = np.where(np.abs(Y) < J._POW_Y_LIMIT, Y, np.copysign(1.0, Y) * J._POW_Y_LIMIT)
        Yt = np.trunc(Yc)
        yisint = Yt == Yc
        yint = np.where(todo, Yt, 0.0).astype(_I64)          # unsafe_trunc, in range here
        m = todo & yisint & (yint == 0)
        out[m] = 1.0
        ip = todo & yisint & (yint != 0) & (yint >= -(2**12)) & (yint <= 3 * 2**13)
        if ip.any():
            out[ip] = _pow_body_int_flat(X[ip], yint[ip])
        todo &= ~(m | ip)
        xz = todo & (X == 0.0)                              # x === +0.0 or -0.0
        if xz.any():
            yz = Yc[xz]
            v = np.abs(yz) * np.inf
            out[xz] = np.where(~(yz > 0), v, np.copysign(0.0, v))
        todo &= ~xz
        negx = todo & (X < 0.0)
        bad = negx & ~yisint
        if bad.any():
            raise J._domain_error(float(X[np.flatnonzero(bad)[0]]), _POW_MSG)
        s = np.where(negx & ((yint & 1) != 0), -1.0, 1.0)
        fin = np.isfinite(X)
        nf = todo & ~fin                                    # x is inf or NaN
        if nf.any():
            xs = X[nf]
            v = np.copysign(xs, s[nf])
            out[nf] = np.where((Yc[nf] > 0) | np.isnan(xs), v, np.copysign(0.0, v))
        fm = todo & fin
        if fm.any():
            out[fm] = np.copysign(_pow_body_flat(np.abs(X[fm]), Yc[fm]), s[fm])
    return out.reshape(shape)


# ── hypot: base/math.jl ─────────────────────────────────────────────────────

def hypot(x, y):
    """Julia's hypot(x::Float64, y::Float64), element by element; x and y broadcast."""
    xb, yb = np.broadcast_arrays(np.asarray(x, dtype=_F64), np.asarray(y, dtype=_F64))
    shape = xb.shape
    X = np.ascontiguousarray(xb).ravel()
    Y = np.ascontiguousarray(yb).ravel()
    with np.errstate(all="ignore"):
        axu = np.abs(X)
        ayu = np.abs(Y)
        out = np.empty_like(axu)
        isinf = np.isinf(axu) | np.isinf(ayu)
        out[isinf] = np.inf
        swap = ayu > axu
        ax = np.where(swap, ayu, axu)
        ay = np.where(swap, axu, ayu)
        wide = ~isinf & (ay <= ax * J._SQRT_HALF_EPS)
        out[wide] = ax[wide]
        rest = ~isinf & ~wide
        if rest.any():
            ri = np.flatnonzero(rest)
            a = ax[ri]
            b = ay[ri]
            large = a > J._HYPOT_LARGE
            small = ~large & (b < J._HYPOT_SMALL)
            HS = J._HYPOT_SCALE
            a = np.where(large, a * HS, np.where(small, a / HS, a))
            b = np.where(large, b * HS, np.where(small, b / HS, b))
            scale = np.where(large, 1.0 / HS, np.where(small, HS, 1.0))
            h = np.sqrt(b * b + a * a)                       # unfused in the compiled code
            hsquared = h * h
            axsquared = a * a
            f1, u1 = _fma_checked(-b, b, hsquared - axsquared)
            f2, u2 = _fma_checked(h, h, -hsquared)
            f3, u3 = _fma_checked(a, a, -axsquared)
            h = h - (f1 + f2 - f3) / (2 * h)
            res = h * scale
            for i in np.flatnonzero(u1 | u2 | u3):
                res[i] = J.hypot(float(X[ri[i]]), float(Y[ri[i]]))
            out[ri] = res
        return out.reshape(shape)
