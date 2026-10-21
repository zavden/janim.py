"""Julia 1.12.6's Float64 math and FastPower 1.4.0's power, bit for bit (MIT).

The simulations use this math, written in Julia, instead of the system libm
behind Python's math module, which varies in the last bit between machines
and libm versions (math.sin differs on about 3% of inputs). Using one
deterministic implementation makes the same scene give the same frames on
every machine. Ported branch for branch:

- base/special/trig.jl: sin, cos, tan, acos and the sin/cos/tan kernels;
- base/special/rem_pio2.jl: rem_pio2_kernel (Cody-Waite and Payne-Hanek);
- base/special/exp.jl: exp, exp_impl(x, xlo) for pow, exp2_fast(::Float32);
- base/special/hyperbolic.jl: tanh;
- base/special/log.jl: log, log10 and _log_ext for pow;
- base/math.jl: ^(::Float64, ::Float64) with both pow_body methods, hypot;
- FastPower.jl 1.4.0 (src/FastPower.jl): fastlog2 and fastpower.

Julia emits muladd as `fmul contract` + `fadd contract`, and the x86-64
backend fuses the pair into one fma unless an earlier optimization folded or
shared the product. So muladd and fma become math.fma and an unfused
a*b + c stays two roundings, except where the optimized IR (code_llvm) shows
that LLVM decided otherwise: cody_waite_2c_pio2, pow_body(x, n) and _hypot,
each of which says why. Float32 values round after every operation (numpy
float32 scalars), and a Float32 fma rounds once: the exact result is rounded
to odd in Float64, then to Float32. DomainError becomes ValueError with
Julia's message.
"""

import math
import struct
from fractions import Fraction

import numpy as np


__all__ = [
    "sin",
    "cos",
    "tan",
    "acos",
    "tanh",
    "exp",
    "pow",
    "log",
    "log10",
    "hypot",
    "exp2f",
    "fastlog2",
    "fastpower",
]

_MASK32 = 0xFFFF_FFFF
_MASK64 = 0xFFFF_FFFF_FFFF_FFFF
_MASK128 = (1 << 128) - 1


# ── bits, fma and polynomials ───────────────────────────────────────────────


def _bits(x):
    """reinterpret(UInt64, x::Float64)."""
    return struct.unpack("<Q", struct.pack("<d", x))[0]


def _from_bits(u):
    """reinterpret(Float64, u), with u wrapped to UInt64 first."""
    return struct.unpack("<d", struct.pack("<Q", u & _MASK64))[0]


def _bits32(x):
    """reinterpret(UInt32, x::Float32)."""
    return struct.unpack("<I", np.float32(x).tobytes())[0]


def _from_bits32(u):
    """reinterpret(Float32, u), with u wrapped to UInt32 first."""
    return np.frombuffer(struct.pack("<I", u & _MASK32), dtype=np.float32)[0]


def _signed(u, width):
    """u % Int32 / Int64 / Int128: the two's complement value of the low bits."""
    u &= (1 << width) - 1
    return u - (1 << width) if u >> (width - 1) else u


# x86's default NaN: what the hardware fma returns for inf*0 or inf - inf.
_DEFAULT_NAN = _from_bits(0xFFF8_0000_0000_0000)


def _fma(a, b, c):
    """fma, and muladd (fused on this machine), on Float64.

    math.fma raises on overflow and on invalid operations, where the
    hardware instruction returns a value; that value is returned instead.
    """
    try:
        return math.fma(a, b, c)
    except ValueError:
        return _DEFAULT_NAN
    except OverflowError:
        # c is finite here, so the exact result has the sign of the product.
        return math.copysign(math.inf, a * b)


def _two_mul(x, y):
    """two_mul(x::Float64, y::Float64) with have_fma(Float64) == true."""
    xy = x * y
    return xy, _fma(x, y, -xy)


def _horner(x, *coefficients):
    """evalpoly(x, p) and @horner(x, p...): muladd(x, ..., p[i]) from the end."""
    value = coefficients[-1]
    for coefficient in reversed(coefficients[:-1]):
        value = _fma(x, value, coefficient)
    return value


def _odd(nearest, error):
    """Round to odd, from a round-to-nearest Float64 and the sign of its error.

    Rounding a 53-bit round-to-odd value to 24 bits yields the correctly
    rounded Float32 of the exact value (Boldo and Melquiond, 2008).
    """
    bits = _bits(nearest)
    if error == 0 or bits & 1:
        return nearest
    if (error > 0) == (nearest > 0):
        return _from_bits(bits + 1)
    return _from_bits(bits - 1)


def _f32(literal):
    """A Julia Float32 literal such as 0.338953f0: its decimal rounded once."""
    exact = Fraction(literal)
    nearest = float(exact)
    return np.float32(_odd(nearest, exact - Fraction(nearest)))


def _fma32(a, b, c):
    """fma, and muladd (fused on this machine), on Float32: one rounding."""
    a, b, c = float(a), float(b), float(c)
    # Two 24-bit significands: the Float64 product is exact.
    product = a * b
    total = product + c
    if not math.isfinite(total):
        return np.float32(total)
    # TwoSum: the exact error of the Float64 sum.
    virtual = total - product
    error = (product - (total - virtual)) + (c - virtual)
    return np.float32(_odd(total, error))


def _horner32(x, *coefficients):
    """evalpoly(x, p) with Float32 coefficients: nested Float32 muladd."""
    value = coefficients[-1]
    for coefficient in reversed(coefficients[:-1]):
        value = _fma32(x, value, coefficient)
    return value


def _round(x):
    """round(x::Float64) for finite x: nearest integer, ties to even, sign kept."""
    return math.copysign(float(round(x)), x)


def _times_bool(value, flag):
    """value * flag for a Bool flag: `false` is a strong zero in Julia."""
    return value if flag else math.copysign(0.0, value)


def _domain_error(x, message):
    return ValueError(f"DomainError with {x!r}:\n{message}")


# ── sin and cos: base/special/trig.jl ───────────────────────────────────────

_PI_4 = math.pi / 4
_SQRT_EPS = math.sqrt(2.0**-52)
_SQRT_HALF_EPS = math.sqrt(2.0**-52 / 2.0)

# sin(x) ≈ x + S1*x³ + S2*x⁵ + S3*x⁷ + S4*x⁹ + S5*x¹¹ + S6*x¹³ on [0, π/4]
_DS1 = -1.66666666666666324348e-01
_DS2 = 8.33333333332248946124e-03
_DS3 = -1.98412698298579493134e-04
_DS4 = 2.75573137070700676789e-06
_DS5 = -2.50507602534068634195e-08
_DS6 = 1.58969099521155010221e-10

_DC1 = 4.16666666666666019037e-02
_DC2 = -1.38888888888741095749e-03
_DC3 = 2.48015872894767294178e-05
_DC4 = -2.75573143513906633035e-07
_DC5 = 2.08757232129817482790e-09
_DC6 = -1.13596475577881948265e-11


def _sin_kernel(y):
    """sin_kernel(y::Float64) on [-π/4, π/4]."""
    y2 = y * y
    y4 = y2 * y2
    r = _horner(y2, _DS2, _DS3, _DS4) + y2 * y4 * _horner(y2, _DS5, _DS6)
    y3 = y2 * y
    return y + y3 * (_DS1 + y2 * r)


def _sin_kernel_double(hi, lo):
    """sin_kernel(y::DoubleFloat64): y = hi + lo from rem_pio2_kernel."""
    y2 = hi * hi
    y4 = y2 * y2
    r = _horner(y2, _DS2, _DS3, _DS4) + y2 * y4 * _horner(y2, _DS5, _DS6)
    y3 = y2 * hi
    return hi - ((y2 * (0.5 * lo - y3 * r) - lo) - y3 * _DS1)


def _cos_kernel(y):
    """cos_kernel(y::Float64) on [-π/4, π/4]."""
    y2 = y * y
    y4 = y2 * y2
    r = y2 * _horner(y2, _DC1, _DC2, _DC3) + y4 * y4 * _horner(y2, _DC4, _DC5, _DC6)
    half_y2 = 0.5 * y2
    w = 1.0 - half_y2
    return w + (((1.0 - w) - half_y2) + (y2 * r))


def _cos_kernel_double(hi, lo):
    """cos_kernel(y::DoubleFloat64): y = hi + lo from rem_pio2_kernel."""
    y2 = hi * hi
    y4 = y2 * y2
    r = y2 * _horner(y2, _DC1, _DC2, _DC3) + y4 * y4 * _horner(y2, _DC4, _DC5, _DC6)
    half_y2 = 0.5 * y2
    w = 1.0 - half_y2
    return w + (((1.0 - w) - half_y2) + (y2 * r - hi * lo))


def sin(x):
    """Julia's sin(x::Float64)."""
    x = float(x)
    absx = abs(x)
    if absx < _PI_4:
        if absx < _SQRT_EPS:
            return x
        return _sin_kernel(x)
    elif math.isnan(x):
        return x
    elif math.isinf(x):
        raise _domain_error(x, "sin(x) is only defined for finite x.")
    n, hi, lo = _rem_pio2_kernel(x)
    n = n & 3
    if n == 0:
        return _sin_kernel_double(hi, lo)
    elif n == 1:
        return _cos_kernel_double(hi, lo)
    elif n == 2:
        return -_sin_kernel_double(hi, lo)
    else:
        return -_cos_kernel_double(hi, lo)


def cos(x):
    """Julia's cos(x::Float64)."""
    x = float(x)
    absx = abs(x)
    if absx < _PI_4:
        if absx < _SQRT_HALF_EPS:
            return 1.0
        return _cos_kernel(x)
    elif math.isnan(x):
        return x
    elif math.isinf(x):
        raise _domain_error(x, "cos(x) is only defined for finite x.")
    else:
        n, hi, lo = _rem_pio2_kernel(x)
        n = n & 3
        if n == 0:
            return _cos_kernel_double(hi, lo)
        elif n == 1:
            return -_sin_kernel_double(hi, lo)
        elif n == 2:
            return -_cos_kernel_double(hi, lo)
        else:
            return _sin_kernel_double(hi, lo)


# tan(y) ≈ y + T1*y³ + … + T13*y²⁷ on [0, 0.67434]; T2…T13 split by parity
_DT1 = 3.33333333333334091986e-01
_DT_EVEN = (
    1.33333333333201242699e-01,
    2.18694882948595424599e-02,
    3.59207910759131235356e-03,
    5.88041240820264096874e-04,
    7.81794442939557092300e-05,
    -1.85586374855275456654e-05,
)
_DT_ODD = (
    5.39682539762260521377e-02,
    8.86323982359930005737e-03,
    1.45620945432529025516e-03,
    2.46463134818469906812e-04,
    7.14072491382608190305e-05,
    2.59073051863633712884e-05,
)
_TAN_THRESHOLD = 0.6744
_PI_4_LO = 3.06161699786838301793e-17


def _tan_kernel(hi, lo, k):
    """tan_kernel(y::DoubleFloat64, k): tan(y) for k = 1, -1/tan(y) for k = -1."""
    yhi, ylo = hi, lo
    above = abs(yhi) >= _TAN_THRESHOLD
    if above:
        if yhi < 0.0:
            yhi = -yhi
            ylo = -ylo
        yhi = (_PI_4 - yhi) + (_PI_4_LO - ylo)
        ylo = 0.0
    y2 = yhi * yhi
    y4 = y2 * y2
    r = _horner(y4, *_DT_EVEN)
    v = y2 * _horner(y4, *_DT_ODD)
    y3 = y2 * yhi
    r = ylo + y2 * (y3 * (r + v) + ylo)
    r += _DT1 * y3
    px = yhi + r
    if above:
        sign = -1.0 if math.copysign(1.0, hi) < 0 else 1.0
        return sign * (k - 2 * (yhi - (px * px / (k + px) - r)))
    if k == 1:
        return px
    # -1/(y + r), accurately: both low words zeroed
    px0 = _from_bits((_bits(px) >> 32) << 32)
    v = r - (px0 - yhi)
    a = -1.0 / px
    t = _from_bits((_bits(a) >> 32) << 32)
    s = 1.0 + t * px0
    return t + a * (s + t * v)


def tan(x):
    """Julia's tan(x::Float64)."""
    x = float(x)
    absx = abs(x)
    if absx < _PI_4:
        if absx < _SQRT_EPS / 2:
            return x
        return _tan_kernel(x, 0.0, 1)
    elif math.isnan(x):
        return x
    elif math.isinf(x):
        raise _domain_error(x, "tan(x) is only defined for finite x.")
    n, hi, lo = _rem_pio2_kernel(x)
    return _tan_kernel(hi, lo, 1 if n % 2 == 0 else -1)


# ── reduction by π/2: base/special/rem_pio2.jl ──────────────────────────────

_TWO_OVER_PI = 2 / math.pi
_PIO2_1 = 1.57079632673412561417e+00
_PIO2_1T = 6.07710050650619224932e-11
_PIO2_2 = 6.07710050630396597660e-11
_PIO2_2T = 2.02226624879595063154e-21
_PIO2_3 = 2.02226624871116645580e-21
_PIO2_3T = 8.47842766036889956997e-32


def _highword(x):
    """highword(x::Float64) as a UInt32."""
    return _bits(x) >> 32


def _cody_waite_2c_pio2(x, fn, n):
    """cody_waite_2c_pio2(x, fn, n) as compiled.

    Every caller passes fn as a literal, so LLVM folds the products of the
    three muladds (x - fn*pio2_1, z - fn*pio2_1t, (z - y1) - fn*pio2_1t)
    into rounded constants and adds them: the optimized IR has
    `fadd contract double %x, 0xC012D97C7F300000` for fn = 3. The products
    are exact for fn = ±1, ±2, ±4; -3*pio2_1t rounds.
    """
    c1 = -fn * _PIO2_1
    c1t = -fn * _PIO2_1T
    z = x + c1
    y1 = z + c1t
    y2 = (z - y1) + c1t
    return n, y1, y2


def _cody_waite_ext_pio2(x, xhp):
    """cody_waite_ext_pio2(x, xhp): up to three Cody-Waite steps (85, 118, 151 bits)."""
    fn = _round(x * _TWO_OVER_PI)
    r = _fma(-fn, _PIO2_1, x)
    w = fn * _PIO2_1T
    j = xhp >> 20
    y1 = r - w
    high = _highword(y1)
    # UInt32 arithmetic: the difference wraps.
    i = (j - ((high >> 20) & 0x7FF)) & _MASK32
    if i > 16:
        t = r
        w = fn * _PIO2_2
        r = t - w
        w = _fma(fn, _PIO2_2T, -((t - r) - w))
        y1 = r - w
        high = _highword(y1)
        i = (j - ((high >> 20) & 0x7FF)) & _MASK32
        if i > 49:
            t = r
            w = fn * _PIO2_3
            r = t - w
            w = _fma(fn, _PIO2_3T, -((t - r) - w))
            y1 = r - w
    y2 = (r - y1) - w
    return int(fn), y1, y2


def _shift_left(x, count, mask):
    """x << count on an unsigned integer; a negative count shifts right."""
    return (x << count) & mask if count >= 0 else x >> -count


def _shift_right(x, count, mask):
    """x >> count on an unsigned integer; a negative count shifts left."""
    return x >> count if count >= 0 else (x << -count) & mask


def _fromfraction(f):
    """fromfraction(f::Int128): z1 + z2 == f / 2^128, z1 with 26 bits."""
    if f == 0:
        return 0.0, 0.0
    # 1. The leading term, truncated to 26 bits.
    s = (1 if f < 0 else 0) << 63
    x = abs(f) & _MASK128
    n1 = x.bit_length()
    m1 = ((_shift_right(x, n1 - 26, _MASK128) & _MASK64) << 27) & _MASK64
    d1 = (((n1 - 128 + 1021) & _MASK64) << 52) & _MASK64
    z1 = _from_bits(s | ((d1 + m1) & _MASK64))
    # 2. The remaining term.
    x2 = (x - _shift_left(m1, n1 - 53, _MASK128)) & _MASK128
    if x2 == 0:
        return z1, 0.0
    n2 = x2.bit_length()
    m2 = _shift_right(x2, n2 - 53, _MASK128) & _MASK64
    d2 = (((n2 - 128 + 1021) & _MASK64) << 52) & _MASK64
    z2 = _from_bits(s | ((d2 + m2) & _MASK64))
    return z1, z2


def _paynehanek(x):
    """paynehanek(x::Float64): the reduction for |x| >= 2^20*π/2."""
    # 1. x = X * 2^k with X a 53-bit integer.
    u = _bits(x)
    X = (u & 0x000F_FFFF_FFFF_FFFF) | (1 << 52)
    raw_exponent = (u & 0x7FF0_0000_0000_0000) >> 52
    k = raw_exponent - 1023 - 52
    # 2. The three 64-bit words of 1/2π that matter after 2^k.
    idx = k >> 6
    shift = k - (idx << 6)
    if shift == 0:
        a1 = _INV_2PI[idx]
        a2 = _INV_2PI[idx + 1]
        a3 = _INV_2PI[idx + 2]
    else:
        a1 = (
            (0 if idx < 0 else (_INV_2PI[idx] << shift) & _MASK64)
            | (_INV_2PI[idx + 1] >> (64 - shift))
        )
        a2 = ((_INV_2PI[idx + 1] << shift) & _MASK64) | (_INV_2PI[idx + 2] >> (64 - shift))
        a3 = ((_INV_2PI[idx + 2] << shift) & _MASK64) | (_INV_2PI[idx + 3] >> (64 - shift))
    # 3. The fraction of x/2π, as a UInt128.
    w1 = ((X * a1) & _MASK64) << 64
    w2 = X * a2
    w3 = (X * a3) >> 64
    w = (w1 + w2 + w3) & _MASK128
    # flipsign(w, x) on a UInt128.
    if _bits(x) >> 63:
        w = -w & _MASK128
    # 4. The nearest quadrant and the fraction of x/(π/2) in [-0.5, 0.5).
    q = ((w >> 125) + 1) >> 1
    f = _signed(w << 2, 128)
    # 5. The fraction as a split Float64.
    z_hi, z_lo = _fromfraction(f)
    # 6. Times π/2.
    pio2 = 1.5707963267948966
    pio2_hi = 1.5707963407039642
    pio2_lo = -1.3909067614167116e-8
    y_hi = (z_hi + z_lo) * pio2
    y_lo = (((z_hi * pio2_hi - y_hi) + z_hi * pio2_lo) + z_lo * pio2_hi) + z_lo * pio2_lo
    return q, y_hi, y_lo


def _rem_pio2_kernel(x):
    """rem_pio2_kernel(x::Float64): (n, hi, lo) with n*π/2 = x - (hi + lo)."""
    xhp = _highword(x) & 0x7FFF_FFFF
    # xhp <= highword(5π/4) implies |x| ~<= 5π/4.
    if xhp <= 0x400F6A7A:
        # |x| ~= π/2 or 2π/2: the precise Cody-Waite scheme.
        if (xhp & 0xFFFFF) == 0x921FB:
            return _cody_waite_ext_pio2(x, xhp)
        # xhp <= highword(3π/4) implies |x| ~<= 3π/4.
        if xhp <= 0x4002D97C:
            if x > 0.0:
                return _cody_waite_2c_pio2(x, 1.0, 1)
            else:
                return _cody_waite_2c_pio2(x, -1.0, -1)
        # 3π/4 < |x| <= 5π/4.
        else:
            if x > 0.0:
                return _cody_waite_2c_pio2(x, 2.0, 2)
            else:
                return _cody_waite_2c_pio2(x, -2.0, -2)
    # xhp <= highword(9π/4) implies |x| ~<= 9π/4.
    if xhp <= 0x401C463B:
        # xhp <= highword(7π/4) implies |x| ~<= 7π/4.
        if xhp <= 0x4015FDBC:
            # |x| ~= 3π/2.
            if xhp == 0x4012D97C:
                return _cody_waite_ext_pio2(x, xhp)
            if x > 0.0:
                return _cody_waite_2c_pio2(x, 3.0, 3)
            else:
                return _cody_waite_2c_pio2(x, -3.0, -3)
        # 7π/4 < |x| <= 9π/4.
        else:
            # |x| ~= 4π/2.
            if xhp == 0x401921FB:
                return _cody_waite_ext_pio2(x, xhp)
            if x > 0.0:
                return _cody_waite_2c_pio2(x, 4.0, 4)
            else:
                return _cody_waite_2c_pio2(x, -4.0, -4)
    # xhp < highword(2^20*π/2) implies |x| ~< 2^20*π/2.
    if xhp < 0x413921FB:
        return _cody_waite_ext_pio2(x, xhp)
    return _paynehanek(x)


# ── acos: base/special/trig.jl ──────────────────────────────────────────────

_ACOS_X_MIN_THRESHOLD = 2.0**-57
_PIO2_HI = 1.57079632679489655800e+00
_PIO2_LO = 6.12323399573676603587e-17
_ACOS_PI = 3.14159265358979311600e+00


def _arc_p(t):
    return t * _horner(
        t,
        1.66666666666666657415e-01,
        -3.25565818622400915405e-01,
        2.01212532134862925881e-01,
        -4.00555345006794114027e-02,
        7.91534994289814532176e-04,
        3.47933107596021167570e-05,
    )


def _arc_q(z):
    return _horner(
        z,
        1.0,
        -2.40339491173441421878e+00,
        2.02094576023350569471e+00,
        -6.88283971605453293030e-01,
        7.70381505559019352791e-02,
    )


def _arc_trt(t):
    return _arc_p(t) / _arc_q(t)


def acos(x):
    """Julia's acos(x::Float64)."""
    x = float(x)
    absx = abs(x)
    if absx >= 1.0:
        # acos(-1) = π, acos(1) = 0.
        if absx == 1.0:
            return 0.0 if x > 0.0 else math.pi
        raise _domain_error(x, "acos(x) not defined for |x| > 1")
    elif absx < 1.0 / 2:
        # If |x| is small enough, acos(x) ≈ π/2.
        if absx < _ACOS_X_MIN_THRESHOLD:
            return math.pi / 2
        # acos(x) = π/2 - (x + x*x^2*R(x^2)).
        return _PIO2_HI - (x - (_PIO2_LO - x * _arc_trt(x * x)))
    z = (1.0 - absx) * 0.5
    z_rz = _arc_trt(z)
    s = math.sqrt(z)
    if x < 0.0:
        # acos(x) = π - 2asin(sqrt((1 - |x|)/2)).
        return _ACOS_PI - 2.0 * (s + (z_rz * s - _PIO2_LO))
    else:
        # acos(x) = 2f + (2c + 2s*z*R(z)), f the high word of s.
        df = _from_bits((_bits(s) >> 32) << 32)
        c = (z - df * df) / (s + df)
        return 2.0 * (df + (z_rz * s + c))


# ── exp: base/special/exp.jl, base ℯ ────────────────────────────────────────

_MAGIC_ROUND_CONST = 6.755399441055744e15
_MAX_EXP = 709.7827128933841
_MIN_EXP = -745.1332191019412
_SUBNORM_EXP = 708.3964185322641
_LOG_BO256_INV = 369.3299304675746
_LOG_BO256_U = -0.002707606173999011
_LOG_BO256_L = -6.327543041662719e-14
_JU_MASK = _MASK64 >> 12
_JU_CONST = 0x3FF0000000000000
_JL_CONST = 0x3C00000000000000


def _expm1b_kernel(x):
    """expm1b_kernel(Val(:ℯ), x::Float64)."""
    return x * _horner(
        x,
        0.9999999999999912,
        0.4999999999999997,
        0.1666666857598779,
        0.04166666857598777,
    )


def _table_unpack(ind):
    """table_unpack(ind::Int32): 2^(j/256) as jU + jL, j = ind & 255."""
    j = _J_TABLE[ind & 255]
    j_u = _from_bits(_JU_CONST | (j & _JU_MASK))
    j_l = _from_bits(_JL_CONST | (j >> 8))
    return j_u, j_l


def _exp_reduce(x):
    """The first lines of both exp_impl methods: N, k = N >> 8, and r."""
    n_float = _fma(x, _LOG_BO256_INV, _MAGIC_ROUND_CONST)
    n = _signed(_bits(n_float), 32)
    # n_float now equals round(x*LogBo256INV).
    n_float -= _MAGIC_ROUND_CONST
    r = _fma(n_float, _LOG_BO256_U, x)
    r = _fma(n_float, _LOG_BO256_L, r)
    return n, n >> 8, r


def _scale(k, small_part):
    """reinterpret(Float64, (Int64(k) << 52) + reinterpret(Int64, small_part))."""
    return _from_bits((k << 52) + _bits(small_part))


def _scale_subnormal(k, small_part):
    """The k <= -53 branch: ((k + UInt64(53)) << 52) + bits, then times 2^-53."""
    twopk = ((k + 53) << 52) & _MASK64
    return _from_bits(twopk + _bits(small_part)) * 2.0**-53


def exp(x):
    """Julia's exp(x::Float64): exp_impl(x, Val(:ℯ))."""
    x = float(x)
    n, k, r = _exp_reduce(x)
    j_u, j_l = _table_unpack(n)
    small_part = _fma(j_u, _expm1b_kernel(r), j_l) + j_u
    if not (abs(x) <= _SUBNORM_EXP):
        if math.isnan(x):
            return x
        if x >= _MAX_EXP:
            return math.inf
        if x <= _MIN_EXP:
            return 0.0
        if k <= -53:
            return _scale_subnormal(k, small_part)
    return _scale(k, small_part)


def _exp_impl_lo(x, xlo):
    """exp_impl(x, xlo, Val(:ℯ)): ℯ^(x + xlo), the last step of pow."""
    n, k, r = _exp_reduce(x)
    j_u, j_l = _table_unpack(n)
    kern = _expm1b_kernel(r)
    very_small = _fma(kern, j_u * xlo, j_l)
    # Base.canonicalize2(1.0, kern).
    hi = 1.0 + kern
    lo = (1.0 - hi) + kern
    small_part = _fma(j_u, hi, _fma(j_u, lo + xlo, very_small))
    if not (abs(x) <= _SUBNORM_EXP):
        if math.isnan(x):
            return x
        if x >= _MAX_EXP:
            return math.inf
        if x <= _MIN_EXP:
            return 0.0
        if k <= -53:
            return _scale_subnormal(k, small_part)
        if k == 1024:
            return (small_part * 2.0) * 2.0**1023
    return _scale(k, small_part)


# ── tanh: base/special/hyperbolic.jl ────────────────────────────────────────

_TANH_LARGE_X = 44.0
_TANH_SMALL_X = 1.0


def _tanh_kernel(x):
    return _horner(
        x,
        1.0,
        -0.33333333333332904,
        0.13333333333267555,
        -0.05396825393066753,
        0.02186948742242217,
        -0.008863215974794633,
        0.003591910693118715,
        -0.0014542587440487815,
        0.0005825521659411748,
        -0.00021647574085351332,
        5.5752458452673005e-5,
    )


def tanh(x):
    """Julia's tanh(x::Float64)."""
    x = float(x)
    abs2x = abs(2 * x)
    if abs2x >= _TANH_LARGE_X:
        return math.copysign(1.0, x)
    if abs2x <= _TANH_SMALL_X:
        return x * _tanh_kernel(x * x)
    k = exp(abs2x)
    return math.copysign(1 - 2 / (k + 1), x)


# ── log and log10: base/special/log.jl ──────────────────────────────────────

# logbU and logbL for Val(:ℯ) and Val(10).
_LOGB_E = (1.0, 0.0)
_LOGB_10 = (0.4342944819032518, 1.098319650216765e-17)


def _log_proc1(y, mf, F, f, logb):
    """Procedure 1 of Tang's method, for x away from 1."""
    jp = int(128.0 * F) - 127
    # Steps 1 and 2 (the table is 1-based in Julia).
    hi, lo = _T_LOG_FLOAT64[jp - 1]
    l_hi = mf * 0.6931471805601177 + hi
    l_lo = mf * -1.7239444525614835e-13 + lo
    # Step 3'.
    u = (2.0 * f) / (y + F)
    v = u * u
    q = u * v * _horner(v, 0.08333333333303913, 0.012500053168098584)
    # Step 4.
    m_hi, m_lo = logb
    return _fma(m_hi, l_hi, _fma(m_hi, (u + (q + l_lo)), m_lo * l_hi))


def _log_proc2(f, logb):
    """Procedure 2 of Tang's method, for x near 1."""
    # Step 1.
    g = 1.0 / (2.0 + f)
    u = 2.0 * f * g
    v = u * u
    # Step 2.
    q = u * v * _horner(
        v,
        0.08333333333333179,
        0.012500000003771751,
        0.0022321399879194482,
        0.0004348877777076146,
    )
    # Step 3: u2 = (2(f - u1) - f*u1)/(2 + f).
    m_hi, m_lo = logb
    return _fma(m_hi, u, _fma(m_lo, u, m_hi * _fma(_fma(-u, f, 2 * (f - u)), g, q)))


def _log(x, logb, name):
    """_log(x::Float64, base, func)."""
    if x > 0.0:
        if x == math.inf:
            return x
        # Step 2.
        if 0.9394130628134757 < x < 1.0644944589178595:
            f = x - 1.0
            return _log_proc2(f, logb)
        # Step 3.
        xu = _bits(x)
        m = (xu >> 52) & 0x07FF
        if m == 0:
            # x is subnormal: normalise the significand with 0x1p54.
            x *= 1.8014398509481984e16
            xu = _bits(x)
            m = ((xu >> 52) & 0x07FF) - 54
        m -= 1023
        y = _from_bits((xu & 0x000F_FFFF_FFFF_FFFF) | 0x3FF0_0000_0000_0000)
        mf = float(m)
        # 0x1p-7*round(0x1p7*y).
        F = (y + 3.5184372088832e13) - 3.5184372088832e13
        f = y - F
        return _log_proc1(y, mf, F, f, logb)
    elif x == 0.0:
        return -math.inf
    elif math.isnan(x):
        return math.nan
    else:
        raise _domain_error(
            x,
            f"{name} was called with a negative real argument but will only return a "
            f"complex result if called with a complex argument. Try {name}(Complex(x)).",
        )


def log(x):
    """Julia's log(x::Float64)."""
    return _log(float(x), _LOGB_E, "log")


def log10(x):
    """Julia's log10(x::Float64): _log(x, Val(10), :log10), not log(x)/log(10)."""
    return _log(float(x), _LOGB_10, "log10")


# _log_ext's minimax polynomial, as Julia writes it (hexadecimal literals).
_LOG_EXT_P = (
    float.fromhex("-0x1.555555555556p-1"),
    float.fromhex("0x1.0000000000006p-1"),
    float.fromhex("-0x1.999999959554ep-2"),
    float.fromhex("0x1.555555529a47ap-2"),
    float.fromhex("-0x1.2495b9b4845e9p-2"),
    float.fromhex("0x1.0002b8b263fc3p-2"),
)


def _log_tab_unpack(t):
    """log_tab_unpack(t::UInt64): 1/c and log(c) packed in one word."""
    invc = (((t & 0xFF) | 0x1FF00) << 45) & _MASK64
    logc = t & (~0xFF & _MASK64)
    return _from_bits(invc), _from_bits(logc)


def _log_ext(xu):
    """_log_ext(xu::UInt64): log(x) as hi + lo, about 68 bits."""
    # x = 2^k z, z in [0x1.69555p-1, 0x1.69555p-0) and exact.
    tmp = _signed(xu - 0x3FE6955500000000, 64)
    z = _from_bits(xu - (tmp & 0xFFF0000000000000))
    k = float(tmp >> 52)
    # log(x) = k*Ln2 + log(c) + log1p(z/c-1); the table is 1-based in Julia.
    idx = (tmp >> 45) & (len(_T_LOG_TABLE_COMPACT) - 1)
    t, logctail = _T_LOG_TABLE_COMPACT[idx]
    invc, logc = _log_tab_unpack(t)
    # r = z/c - 1 is exact.
    r = _fma(z, invc, -1.0)
    # k*Ln2 + log(c) + r.
    t1 = _fma(k, 0.6931471805598903, logc)
    t2 = t1 + r
    lo1 = _fma(k, 5.497923018708371e-14, logctail)
    lo2 = t1 - t2 + r
    ar = -0.5 * r
    ar2, lo3 = _two_mul(r, ar)
    # k*Ln2 + log(c) + r + .5*r*r.
    hi = t2 + ar2
    lo4 = t2 - hi + ar2
    p = _horner(r, *_LOG_EXT_P)
    lo = lo1 + lo2 + lo3 + _fma(r * ar2, p, lo4)
    return hi, lo


# ── x^y: base/math.jl ───────────────────────────────────────────────────────

_POW_Y_LIMIT = float.fromhex("0x1.8p62")


def _use_power_by_squaring(n):
    return -(2**12) <= n <= 3 * 2**13


def _pow_body_int(x, n):
    """pow_body(x::Float64, n::Integer): compensated power by squaring."""
    y = 1.0
    xnlo = -0.0
    ynlo = 0.0
    # Keep compatibility with literal_pow.
    if n == 3:
        return x * x * x
    if n < 0:
        # inv(x), which Python's division would refuse at zero.
        rx = 1.0 / x if x != 0.0 else math.copysign(math.inf, x)
        # Keep compatibility with literal_pow.
        if n == -2:
            return rx * rx
        if math.isfinite(x):
            xnlo = -_fma(x, rx, -1.0) * rx
        x = rx
        n = -n
    while n > 1:
        if (n & 1) > 0:
            err = _fma(y, xnlo, x * ynlo)
            y, ynlo = _two_mul(x, y)
            ynlo += err
        err = x * 2 * xnlo
        x, xnlo = _two_mul(x, x)
        xnlo += err
        n >>= 1
    err = _fma(y, xnlo, x * ynlo)
    # The source ends with ifelse(isfinite(x) & isfinite(err), muladd(x, y, err), x*y).
    # LLVM shares x*y between both arms and emits x*y + ifelse(..., err, -0.0), so
    # this muladd is NOT fused (vmulsd + vaddsd in code_native): two roundings.
    if not (math.isfinite(x) and math.isfinite(err)):
        err = -0.0
    return x * y + err


def _pow_body(x, y):
    """pow_body(x::Float64, y::Float64) for x > 0: exp(y*log(x)) in extended precision."""
    xu = _bits(x)
    if xu < (1 << 52):
        # x is subnormal: normalize it and move the exponent into the sign bit.
        xu = _bits(x * 2.0**52)
        xu &= 0x7FFF_FFFF_FFFF_FFFF
        xu = (xu - (52 << 52)) & _MASK64
    logxhi, logxlo = _log_ext(xu)
    xyhi, xylo = _two_mul(logxhi, y)
    xylo = _fma(logxlo, y, xylo)
    hi = xyhi + xylo
    return _exp_impl_lo(hi, xylo - (hi - xyhi))


def pow(x, y):
    """Julia's x^y for x::Float64, y::Float64 (integral y goes by squaring)."""
    x = float(x)
    y = float(y)
    xu = _bits(x)
    if xu == 0x3FF0_0000_0000_0000:
        return 1.0
    # Exponents greater than this always overflow or underflow.
    if not (abs(y) < _POW_Y_LIMIT):
        if math.isnan(y):
            return y
        y = math.copysign(1.0, y) * _POW_Y_LIMIT
    # unsafe_trunc(Int64, y), in range here.
    yint = int(y)
    yisint = y == yint
    if yisint:
        if yint == 0:
            return 1.0
        if _use_power_by_squaring(yint):
            return _pow_body_int(x, yint)
    # x === +0.0 or -0.0.
    if ((2 * xu) & _MASK64) == 0:
        return _times_bool(abs(y) * math.inf, not (y > 0))
    s = 1
    if x < 0:
        if not yisint:
            raise _domain_error(
                x,
                "Exponentiation yielding a complex result requires a complex argument.\n"
                "Replace x^y with (x+0im)^y, Complex(x)^y, or similar.",
            )
        s = -1 if yint & 1 else 1
    # x is inf or NaN.
    if not math.isfinite(x):
        return _times_bool(math.copysign(x, s), y > 0 or math.isnan(x))
    return math.copysign(_pow_body(abs(x), y), s)


# ── hypot: base/math.jl ─────────────────────────────────────────────────────

_HYPOT_SCALE = 2.0**-52 * math.sqrt(2.0**-1022)
_HYPOT_LARGE = math.sqrt(1.7976931348623157e308 / 2)
_HYPOT_SMALL = math.sqrt(2.0**-1022)


def hypot(x, y):
    """Julia's hypot(x::Float64, y::Float64): _hypot, the fma branch."""
    axu = abs(float(x))
    ayu = abs(float(y))
    # Unitless: the division by oneunit is the identity on Float64.
    ax = axu
    ay = ayu
    # Inf if either input is Inf (IEEE 754), even with a NaN.
    if math.isinf(ax) or math.isinf(ay):
        return math.inf
    # Order the operands.
    if ay > ax:
        axu, ayu = ayu, axu
        ax, ay = ay, ax
    # Widely varying operands; this also gets ay == 0.
    if ay <= ax * _SQRT_HALF_EPS:
        return axu
    # Operands do not vary widely.
    scale = _HYPOT_SCALE
    if ax > _HYPOT_LARGE:
        ax = ax * scale
        ay = ay * scale
        scale = 1.0 / scale
    elif ay < _HYPOT_SMALL:
        ax = ax / scale
        ay = ay / scale
    else:
        scale = 1.0
    # h = sqrt(muladd(ax, ax, ay*ay)) in the source, but LLVM merges ax*ax with
    # axsquared below and the contract flag is lost: the optimized IR adds two
    # plain products, so this muladd is NOT fused.
    h = math.sqrt(ay * ay + ax * ax)
    # Correctly rounded, with a native hardware fma.
    hsquared = h * h
    axsquared = ax * ax
    h -= (
        _fma(-ay, ay, hsquared - axsquared)
        + _fma(h, h, -hsquared)
        - _fma(ax, ax, -axsquared)
    ) / (2 * h)
    return h * scale


# ── Float32: exp2_fast (base/special/exp.jl) and FastPower 1.4.0 ────────────

_F32_ZERO = _f32("0.0")
_F32_ONE = _f32("1.0")
_F32_INF = np.float32(np.inf)

# MAX_EXP, SUBNORM_EXP, LogBINV, LogBU and LogBL for Val(2), Float32.
_EXP2_MAX_EXP = _f32("128.0")
_EXP2_SUBNORM_EXP = _f32("126.00001")
_EXP2_LOGB_INV = _f32("1.0")
_EXP2_LOGB_U = _f32("-1.0")
_EXP2_LOGB_L = _f32("0.0")

# expb_kernel(Val(2), x::Float32).
_EXPB_KERNEL_2 = (
    _f32("1.0"),
    _f32("0.6931472"),
    _f32("0.2402265"),
    _f32("0.05550411"),
    _f32("0.009618025"),
    _f32("0.0013333423"),
    _f32("0.00015469732"),
    _f32("1.5316464e-5"),
)

# unsafe_trunc(Int32, NaN) is frozen to x86's integer indefinite.
_INT32_INDEFINITE = -(2**31)


def exp2f(x):
    """Base.Math.exp2_fast(x::Float32), i.e. exp_impl_fast(x, Val(2))."""
    x = np.float32(x)
    if x >= _EXP2_MAX_EXP:
        return _F32_INF
    if x <= -_EXP2_SUBNORM_EXP:
        return _F32_ZERO
    n_float = np.rint(x * _EXP2_LOGB_INV)
    n = int(n_float) if np.isfinite(n_float) else _INT32_INDEFINITE
    r = _fma32(n_float, _EXP2_LOGB_U, x)
    r = _fma32(n_float, _EXP2_LOGB_L, r)
    small_part = _horner32(r, *_EXPB_KERNEL_2)
    # Int32 arithmetic: (N + 127) << 23.
    twopk = _from_bits32((n + 127) << 23)
    return twopk * small_part


# (x-1)*(a*(x-1) + b)/((x-1) + c), line 8 of table 2 of Goldberg's post,
# with b = b-a and c = c-1.
_FASTLOG2_A = _f32("0.338953")
_FASTLOG2_B = _f32("1.8596461")
_FASTLOG2_C = _f32("0.523692")


def fastlog2(x):
    """FastPower.fastlog2(x::Float32)."""
    # IEEE is sgn(1):exp(8):frac(23), representing (1+frac)*2^(exp-127).
    ux1i = _bits32(x)
    exponent = (ux1i & 0x7F800000) >> 23
    if (ux1i & 0x00400000) == 0:
        # The significand is below 1.5.
        ux2i = (ux1i & 0x007FFFFF) | 0x3F800000
        exponent -= 0x7F
    else:
        # 126 instead of 127 compensates for the division by 2.
        ux2i = (ux1i & 0x007FFFFF) | 0x3F000000
        exponent -= 0x7E
    signif = _from_bits32(ux2i)
    quot = _fma32(signif, _FASTLOG2_A, _FASTLOG2_B) / (signif + _FASTLOG2_C)
    return _fma32(signif - _F32_ONE, quot, np.float32(exponent))


def fastpower(x, y):
    """FastPower.fastpower(x::Float64, y::Float64)."""
    x = float(x)
    y = float(y)
    if x == 0.0:
        return 0.0
    elif math.isinf(x) and math.isinf(y):
        return math.inf
    # @fastmath: a single Float32 multiply, then exp2_fast. The IEEE flags
    # that numpy would report (overflow, inf * 0) pass silently in Julia.
    with np.errstate(over="ignore", invalid="ignore"):
        product = np.float32(y) * fastlog2(np.float32(x))
    return float(exp2f(product))


# ── tables, copied from the Julia sources ───────────────────────────────────

# rem_pio2.jl: the bits of 1/2π, sum(x / 0x1p64^i for i, x = enumerate(INV_2PI)).
_INV_2PI = (
    0x28be_60db_9391_054a,
    0x7f09_d5f4_7d4d_3770,
    0x36d8_a566_4f10_e410,
    0x7f94_58ea_f7ae_f158,
    0x6dc9_1b8e_9093_74b8,
    0x0192_4bba_8274_6487,
    0x3f87_7ac7_2c4a_69cf,
    0xba20_8d7d_4bae_d121,
    0x3a67_1c09_ad17_df90,
    0x4e64_758e_60d4_ce7d,
    0x2721_17e2_ef7e_4a0e,
    0xc7fe_25ff_f781_6603,
    0xfbcb_c462_d682_9b47,
    0xdb4d_9fb3_c9f2_c26d,
    0xd3d1_8fd9_a797_fa8b,
    0x5d49_eeb1_faf9_7c5e,
    0xcf41_ce7d_e294_a4ba,
    0x9afe_d7ec_47e3_5742,
    0x1580_cc11_bf1e_daea,
)

# exp.jl: J_TABLE, 2^(j/256) in 60 bits (the high 52 bits of jU, the low bits of jL).
_J_TABLE = (
    0x0000000000000000,
    0xaac00b1afa5abcbe,
    0x9b60163da9fb3335,
    0xab502168143b0280,
    0xadc02c9a3e778060,
    0x656037d42e11bbcc,
    0xa7a04315e86e7f84,
    0x84c04e5f72f654b1,
    0x8d7059b0d3158574,
    0xa510650a0e3c1f88,
    0xa8d0706b29ddf6dd,
    0x83207bd42b72a836,
    0x6180874518759bc8,
    0xa4b092bdf66607df,
    0x91409e3ecac6f383,
    0x85d0a9c79b1f3919,
    0x98a0b5586cf9890f,
    0x94f0c0f145e46c85,
    0x9010cc922b7247f7,
    0xa210d83b23395deb,
    0x4030e3ec32d3d1a2,
    0xa5b0efa55fdfa9c4,
    0xae40fb66affed31a,
    0x8d41073028d7233e,
    0xa4911301d0125b50,
    0xa1a11edbab5e2ab5,
    0xaf712abdc06c31cb,
    0xae8136a814f204aa,
    0xa661429aaea92ddf,
    0xa9114e95934f312d,
    0x82415a98c8a58e51,
    0x58f166a45471c3c2,
    0xab9172b83c7d517a,
    0x70917ed48695bbc0,
    0xa7718af9388c8de9,
    0x94a1972658375d2f,
    0x8e51a35beb6fcb75,
    0x97b1af99f8138a1c,
    0xa351bbe084045cd3,
    0x9001c82f95281c6b,
    0x9e01d4873168b9aa,
    0xa481e0e75eb44026,
    0xa711ed5022fcd91c,
    0xa201f9c18438ce4c,
    0x8dc2063b88628cd6,
    0x935212be3578a819,
    0x82a21f49917ddc96,
    0x8d322bdda27912d1,
    0x99b2387a6e756238,
    0x8ac2451ffb82140a,
    0x8ac251ce4fb2a63f,
    0x93e25e85711ece75,
    0x82b26b4565e27cdd,
    0x9e02780e341ddf29,
    0xa2d284dfe1f56380,
    0xab4291ba7591bb6f,
    0x86129e9df51fdee1,
    0xa352ab8a66d10f12,
    0xafb2b87fd0dad98f,
    0xa572c57e39771b2e,
    0x9002d285a6e4030b,
    0x9d12df961f641589,
    0x71c2ecafa93e2f56,
    0xaea2f9d24abd886a,
    0x86f306fe0a31b715,
    0x89531432edeeb2fd,
    0x8a932170fc4cd831,
    0xa1d32eb83ba8ea31,
    0x93233c08b26416ff,
    0xab23496266e3fa2c,
    0xa92356c55f929ff0,
    0xa8f36431a2de883a,
    0xa4e371a7373aa9ca,
    0xa3037f26231e7549,
    0xa0b38cae6d05d865,
    0xa3239a401b7140ee,
    0xad43a7db34e59ff6,
    0x9543b57fbfec6cf4,
    0xa083c32dc313a8e4,
    0x7fe3d0e544ede173,
    0x8ad3dea64c123422,
    0xa943ec70df1c5174,
    0xa413fa4504ac801b,
    0x8bd40822c367a024,
    0xaf04160a21f72e29,
    0xa3d423fb27094689,
    0xab8431f5d950a896,
    0x88843ffa3f84b9d4,
    0x48944e086061892d,
    0xae745c2042a7d231,
    0x9c946a41ed1d0057,
    0xa1e4786d668b3236,
    0x73c486a2b5c13cd0,
    0xab1494e1e192aed1,
    0x99c4a32af0d7d3de,
    0xabb4b17dea6db7d6,
    0x7d44bfdad5362a27,
    0x9054ce41b817c114,
    0x98e4dcb299fddd0d,
    0xa564eb2d81d8abfe,
    0xa5a4f9b2769d2ca6,
    0x7a2508417f4531ee,
    0xa82516daa2cf6641,
    0xac65257de83f4eee,
    0xabe5342b569d4f81,
    0x879542e2f4f6ad27,
    0xa8a551a4ca5d920e,
    0xa7856070dde910d1,
    0x99b56f4736b527da,
    0xa7a57e27dbe2c4ce,
    0x82958d12d497c7fd,
    0xa4059c0827ff07cb,
    0x9635ab07dd485429,
    0xa245ba11fba87a02,
    0x3c45c9268a5946b7,
    0xa195d84590998b92,
    0x9ba5e76f15ad2148,
    0xa985f6a320dceb70,
    0xa60605e1b976dc08,
    0x9e46152ae6cdf6f4,
    0xa636247eb03a5584,
    0x984633dd1d1929fd,
    0xa8e6434634ccc31f,
    0xa28652b9febc8fb6,
    0xa226623882552224,
    0xa85671c1c70833f5,
    0x60368155d44ca973,
    0x880690f4b19e9538,
    0xa216a09e667f3bcc,
    0x7a36b052fa75173e,
    0xada6c012750bdabe,
    0x9c76cfdcddd47645,
    0xae46dfb23c651a2e,
    0xa7a6ef9298593ae4,
    0xa9f6ff7df9519483,
    0x59d70f7466f42e87,
    0xaba71f75e8ec5f73,
    0xa6f72f8286ead089,
    0xa7a73f9a48a58173,
    0x90474fbd35d7cbfd,
    0xa7e75feb564267c8,
    0x9b777024b1ab6e09,
    0x986780694fde5d3f,
    0x934790b938ac1cf6,
    0xaaf7a11473eb0186,
    0xa207b17b0976cfda,
    0x9f17c1ed0130c132,
    0x91b7d26a62ff86f0,
    0x7057e2f336cf4e62,
    0xabe7f3878491c490,
    0xa6c80427543e1a11,
    0x946814d2add106d9,
    0xa1582589994cce12,
    0x9998364c1eb941f7,
    0xa9c8471a4623c7ac,
    0xaf2857f4179f5b20,
    0xa01868d99b4492ec,
    0x85d879cad931a436,
    0x99988ac7d98a6699,
    0x9d589bd0a478580f,
    0x96e8ace5422aa0db,
    0x9ec8be05bad61778,
    0xade8cf3216b5448b,
    0xa478e06a5e0866d8,
    0x85c8f1ae99157736,
    0x959902fed0282c8a,
    0xa119145b0b91ffc5,
    0xab2925c353aa2fe1,
    0xae893737b0cdc5e4,
    0xa88948b82b5f98e4,
    0xad395a44cbc8520e,
    0xaf296bdd9a7670b2,
    0xa1797d829fde4e4f,
    0x7ca98f33e47a22a2,
    0xa749a0f170ca07b9,
    0xa119b2bb4d53fe0c,
    0x7c79c49182a3f090,
    0xa579d674194bb8d4,
    0x7829e86319e32323,
    0xaad9fa5e8d07f29d,
    0xa65a0c667b5de564,
    0x9c6a1e7aed8eb8bb,
    0x963a309bec4a2d33,
    0xa2aa42c980460ad7,
    0xa16a5503b23e255c,
    0x650a674a8af46052,
    0x9bca799e1330b358,
    0xa58a8bfe53c12e58,
    0x90fa9e6b5579fdbf,
    0x889ab0e521356eba,
    0xa81ac36bbfd3f379,
    0x97ead5ff3a3c2774,
    0x97aae89f995ad3ad,
    0xa5aafb4ce622f2fe,
    0xa21b0e07298db665,
    0x94db20ce6c9a8952,
    0xaedb33a2b84f15fa,
    0xac1b468415b749b0,
    0xa1cb59728de55939,
    0x92ab6c6e29f1c52a,
    0xad5b7f76f2fb5e46,
    0xa24b928cf22749e3,
    0xa08ba5b030a10649,
    0xafcbb8e0b79a6f1e,
    0x823bcc1e904bc1d2,
    0xafcbdf69c3f3a206,
    0xa08bf2c25bd71e08,
    0xa89c06286141b33c,
    0x811c199bdd85529c,
    0xa48c2d1cd9fa652b,
    0x9b4c40ab5fffd07a,
    0x912c544778fafb22,
    0x928c67f12e57d14b,
    0xa86c7ba88988c932,
    0x71ac8f6d9406e7b5,
    0xaa0ca3405751c4da,
    0x750cb720dcef9069,
    0xac5ccb0f2e6d1674,
    0xa88cdf0b555dc3f9,
    0xa2fcf3155b5bab73,
    0xa1ad072d4a07897b,
    0x955d1b532b08c968,
    0xa15d2f87080d89f1,
    0x93dd43c8eacaa1d6,
    0x82ed5818dcfba487,
    0x5fed6c76e862e6d3,
    0xa77d80e316c98397,
    0x9a0d955d71ff6075,
    0x9c2da9e603db3285,
    0xa24dbe7cd63a8314,
    0x92ddd321f301b460,
    0xa1ade7d5641c0657,
    0xa72dfc97337b9b5e,
    0xadae11676b197d16,
    0xa42e264614f5a128,
    0xa30e3b333b16ee11,
    0x839e502ee78b3ff6,
    0xaa7e653924676d75,
    0x92de7a51fbc74c83,
    0xa77e8f7977cdb73f,
    0xa0bea4afa2a490d9,
    0x948eb9f4867cca6e,
    0xa1becf482d8e67f0,
    0x91cee4aaa2188510,
    0x9dcefa1bee615a27,
    0xa66f0f9c1cb64129,
    0x93af252b376bba97,
    0xacdf3ac948dd7273,
    0x99df50765b6e4540,
    0x9faf6632798844f8,
    0xa12f7bfdad9cbe13,
    0xaeef91d802243c88,
    0x874fa7c1819e90d8,
    0xacdfbdba3692d513,
    0x62efd3c22b8f71f1,
    0x74afe9d96b2a23d9,
)

# log.jl: t_log_Float64, log(1 + j/128) as (l_hi, l_lo) for Tang's procedure 1.
_T_LOG_FLOAT64 = (
    (0.0, 0.0),
    (0.007782140442941454, -8.865052917267247e-13),
    (0.015504186536418274, -4.530198941364935e-13),
    (0.0231670592820592, -5.248209479295644e-13),
    (0.03077165866670839, 4.529814257790929e-14),
    (0.0383188643027097, -5.730994833076631e-13),
    (0.04580953603181115, -5.16945692881222e-13),
    (0.053244514518155484, 6.567993368985218e-13),
    (0.06062462181580486, 6.299848199383311e-13),
    (0.06795066190898069, -4.729424109166329e-13),
    (0.07522342123775161, -1.6408301585598662e-13),
    (0.08244366921098845, 8.614512936087814e-14),
    (0.08961215869021544, -5.283050530808144e-13),
    (0.09672962645890948, -3.5836667430094137e-13),
    (0.10379679368088546, 7.581073923016376e-13),
    (0.11081436634049169, -2.0157368416016215e-13),
    (0.11778303565552051, 8.629474042969438e-13),
    (0.1247034785010328, -7.556920687451337e-14),
    (0.1315763577895268, -8.075373495358435e-13),
    (0.13840232285838283, 7.363043577087051e-13),
    (0.14518200984457508, -7.718001336828099e-14),
    (0.15191604202664166, -7.996871607743758e-13),
    (0.15860503017574956, 8.890223439724663e-13),
    (0.16524957289584563, -5.384682618788232e-13),
    (0.17185025692742784, -7.686134224018169e-13),
    (0.17840765747314435, -3.2605717931058157e-13),
    (0.18492233849428885, -2.7685884310448306e-13),
    (0.1913948530000198, -3.903387893794952e-13),
    (0.1978257433293038, 6.160755775588723e-13),
    (0.20421554142922105, -5.30156516006026e-13),
    (0.21056476910780475, -4.55112422774782e-13),
    (0.21687393830143264, -8.182853292737783e-13),
    (0.22314355131493357, -7.238189921749681e-13),
    (0.22937410106533207, -4.86240001538379e-13),
    (0.23556607131286, -9.30945949519689e-14),
    (0.24171993688651128, 6.338907368997553e-13),
    (0.24783616390413954, 4.4171755371315547e-13),
    (0.25391520998164196, -6.785208495970588e-13),
    (0.25995752443668607, 2.3999540484211735e-13),
    (0.2659635484978935, -7.555569400283742e-13),
    (0.27193371548310097, 5.407904186145515e-13),
    (0.2778684510030871, 3.692037508208009e-13),
    (0.28376817313073843, -9.3834172236637e-14),
    (0.28963329258294834, 9.43339818951269e-14),
    (0.29546421289342106, 4.148131870425857e-13),
    (0.3012613305781997, -3.7923164802093147e-14),
    (0.3070250352957373, -8.25463138725004e-13),
    (0.31275571000333, 5.668653582900739e-13),
    (0.318453731119007, -4.723727821986367e-13),
    (0.32411946865431673, -1.0475750058776541e-13),
    (0.32975328637257917, -1.1118671389559323e-13),
    (0.33535554192167183, -5.339989292003297e-13),
    (0.3409265869704541, 1.3912841212197566e-13),
    (0.3464667673470103, -8.017372713972018e-13),
    (0.35197642315688427, 2.9391859187648e-13),
    (0.3574558889213222, 4.815896111723205e-13),
    (0.3629054936900502, -6.817539406325327e-13),
    (0.36832556115950865, -8.009990055432491e-13),
    (0.3737164097929053, 6.787566823158706e-13),
    (0.37907835293481185, 1.5761203773969435e-13),
    (0.3844116989112081, -8.760375990774874e-13),
    (0.38971675114044046, -4.152515806343612e-13),
    (0.3949938082405424, 3.2655698896907146e-13),
    (0.40024316412745975, -4.4704265010452445e-13),
    (0.4054651081078191, 3.452764795203977e-13),
    (0.4106599249844294, 8.390050778518307e-13),
    (0.4158278951435932, 1.1776978751369214e-13),
    (0.4209692946442374, -1.0774341461609579e-13),
    (0.42608439531068143, 2.186334329321591e-13),
    (0.43117346481813, 2.413263949133313e-13),
    (0.4362367667745275, 3.90574622098307e-13),
    (0.44127456080423144, 6.437879097373207e-13),
    (0.44628710262804816, 3.713514191959202e-13),
    (0.45127464413963025, -1.7166921336082432e-13),
    (0.4562374334818742, -2.8658285157914353e-13),
    (0.4611757151214988, 6.713692791384601e-13),
    (0.46608972992544295, -8.437281040871276e-13),
    (0.4709797152190731, -2.821014384618127e-13),
    (0.4758459048698569, 1.0701931762114255e-13),
    (0.4806885293455707, 1.8119346366441111e-13),
    (0.4855078157816024, 9.840465278232627e-14),
    (0.49030398804461583, 5.780031989454028e-13),
    (0.49507726679803454, -1.8302857356041668e-13),
    (0.4998278695566114, -1.620740015674495e-13),
    (0.5045560107519123, 4.83033149495532e-13),
    (0.5092619017905236, -7.156055317238212e-13),
    (0.5139457511013461, 8.882123951857185e-13),
    (0.5186077642083546, -3.0900580513238243e-13),
    (0.5232481437651586, -6.10765519728515e-13),
    (0.5278670896204858, 3.565996966334783e-13),
    (0.532464798869114, 3.5782396591276384e-13),
    (0.5370414658973459, -4.622608700154458e-13),
    (0.5415972824321216, 6.227976291722515e-13),
    (0.5461324375974073, 7.283894727206574e-13),
    (0.5506471179523942, 2.680964661521167e-13),
    (0.5551415075406112, -1.0960825046059278e-13),
    (0.5596157879353996, 2.3119493838005378e-14),
    (0.5640701382853877, -5.846905800529924e-13),
    (0.5685047353526897, -2.1037482511444942e-14),
    (0.5729197535620187, -2.332318294558741e-13),
    (0.5773153650352469, -4.2333694288141915e-13),
    (0.5816917396350618, -4.3933937969737843e-13),
    (0.5860490450031648, 4.1341647073835564e-13),
    (0.590387446602108, 6.841763641591467e-14),
    (0.5947071077462169, 4.758553400443064e-13),
    (0.5990081896452466, 8.367967867475769e-13),
    (0.6032908514389419, -8.576373464665864e-13),
    (0.6075552502243227, 2.1913281229340092e-13),
    (0.6118015411066153, -6.224284253643115e-13),
    (0.6160298772156239, -1.098359432543843e-13),
    (0.6202404097512044, 6.531043137763365e-13),
    (0.6244332880123693, -4.758019902171077e-13),
    (0.6286086594227527, -3.785425126545704e-13),
    (0.6327666695706284, 4.0939233218678666e-13),
    (0.636907462236195, 8.742438391485829e-13),
    (0.6410311794206791, 2.521818845684288e-13),
    (0.6451379613736208, -3.6081313604225574e-14),
    (0.649227946625615, -5.05185559242809e-13),
    (0.6533012720119586, 7.869940332335532e-13),
    (0.6573580727090302, -6.702087696194906e-13),
    (0.6613984822452039, 1.6108575753932459e-13),
    (0.6654226325445052, 5.852718843625151e-13),
    (0.6694306539429817, -3.5246757297904794e-13),
    (0.6734226752123504, -1.8372084495629058e-13),
    (0.6773988235909201, 8.860668981349492e-13),
    (0.6813592248072382, 6.64862680714687e-13),
    (0.6853040030982811, 6.383161517064652e-13),
    (0.6892332812385575, 2.5144230728376075e-13),
    (0.6931471805601177, -1.7239444525614835e-13),
)

# log.jl: t_log_table_compact, 1/c packed in the low byte of log(c), and the tail of log(c).
_T_LOG_TABLE_COMPACT = (
    (0xbfd62c82f2b9c8b5, 5.929407345889625e-15),
    (0xbfd5d1bdbf5808b4, -2.544157440035963e-14),
    (0xbfd57677174558b3, -3.443525940775045e-14),
    (0xbfd51aad872df8b2, -2.500123826022799e-15),
    (0xbfd4be5f957778b1, -8.929337133850617e-15),
    (0xbfd4618bc21c60b0, 1.7625431312172662e-14),
    (0xbfd404308686a8af, 1.5688303180062087e-15),
    (0xbfd3a64c556948ae, 2.9655274673691784e-14),
    (0xbfd347dd9a9880ad, 3.7923164802093147e-14),
    (0xbfd2e8e2bae120ac, 3.993416384387844e-14),
    (0xbfd2895a13de88ab, 1.9352855826489123e-14),
    (0xbfd2895a13de88ab, 1.9352855826489123e-14),
    (0xbfd22941fbcf78aa, -1.9852665484979036e-14),
    (0xbfd1c898c16998a9, -2.814323765595281e-14),
    (0xbfd1675cababa8a8, 2.7643769993528702e-14),
    (0xbfd1058bf9ae48a7, -4.025092402293806e-14),
    (0xbfd0a324e27390a6, -1.2621729398885316e-14),
    (0xbfd0402594b4d0a5, -3.600176732637335e-15),
    (0xbfd0402594b4d0a5, -3.600176732637335e-15),
    (0xbfcfb9186d5e40a4, 1.3029797173308663e-14),
    (0xbfcef0adcbdc60a3, 4.8230289429940886e-14),
    (0xbfce27076e2af0a2, -2.0592242769647135e-14),
    (0xbfcd5c216b4fc0a1, 3.149265065191484e-14),
    (0xbfcc8ff7c79aa0a0, 4.169796584527195e-14),
    (0xbfcc8ff7c79aa0a0, 4.169796584527195e-14),
    (0xbfcbc286742d909f, 2.2477465222466186e-14),
    (0xbfcaf3c94e80c09e, 3.6507188831790577e-16),
    (0xbfca23bc1fe2b09d, -3.827767260205414e-14),
    (0xbfca23bc1fe2b09d, -3.827767260205414e-14),
    (0xbfc9525a9cf4509c, -4.7641388950792196e-14),
    (0xbfc87fa06520d09b, 4.9278276214647115e-14),
    (0xbfc7ab890210e09a, 4.9485167661250996e-14),
    (0xbfc7ab890210e09a, 4.9485167661250996e-14),
    (0xbfc6d60fe719d099, -1.5003333854266542e-14),
    (0xbfc5ff3070a79098, -2.7194441649495324e-14),
    (0xbfc5ff3070a79098, -2.7194441649495324e-14),
    (0xbfc526e5e3a1b097, -2.99659267292569e-14),
    (0xbfc44d2b6ccb8096, 2.0472357800461955e-14),
    (0xbfc44d2b6ccb8096, 2.0472357800461955e-14),
    (0xbfc371fc201e9095, 3.879296723063646e-15),
    (0xbfc29552f81ff094, -3.6506824353335045e-14),
    (0xbfc1b72ad52f6093, -5.4183331379008994e-14),
    (0xbfc1b72ad52f6093, -5.4183331379008994e-14),
    (0xbfc0d77e7cd09092, 1.1729485484531301e-14),
    (0xbfc0d77e7cd09092, 1.1729485484531301e-14),
    (0xbfbfec9131dbe091, -3.811763084710266e-14),
    (0xbfbe27076e2b0090, 4.654729747598445e-14),
    (0xbfbe27076e2b0090, 4.654729747598445e-14),
    (0xbfbc5e548f5bc08f, -2.5799991283069902e-14),
    (0xbfba926d3a4ae08e, 3.7700471749674615e-14),
    (0xbfba926d3a4ae08e, 3.7700471749674615e-14),
    (0xbfb8c345d631a08d, 1.7306161136093256e-14),
    (0xbfb8c345d631a08d, 1.7306161136093256e-14),
    (0xbfb6f0d28ae5608c, -4.012913552726574e-14),
    (0xbfb51b073f06208b, 2.7541708360737882e-14),
    (0xbfb51b073f06208b, 2.7541708360737882e-14),
    (0xbfb341d7961be08a, 5.0396178134370583e-14),
    (0xbfb341d7961be08a, 5.0396178134370583e-14),
    (0xbfb16536eea38089, 1.8195060030168815e-14),
    (0xbfaf0a30c0118088, 5.213620639136504e-14),
    (0xbfaf0a30c0118088, 5.213620639136504e-14),
    (0xbfab42dd71198087, 2.532168943117445e-14),
    (0xbfab42dd71198087, 2.532168943117445e-14),
    (0xbfa77458f632c086, -5.148849572685811e-14),
    (0xbfa77458f632c086, -5.148849572685811e-14),
    (0xbfa39e87b9fec085, 4.6652946995830086e-15),
    (0xbfa39e87b9fec085, 4.6652946995830086e-15),
    (0xbf9f829b0e780084, -4.529814257790929e-14),
    (0xbf9f829b0e780084, -4.529814257790929e-14),
    (0xbf97b91b07d58083, -4.361324067851568e-14),
    (0xbf8fc0a8b0fc0082, -1.7274567499706107e-15),
    (0xbf8fc0a8b0fc0082, -1.7274567499706107e-15),
    (0xbf7fe02a6b100081, -2.298941004620351e-14),
    (0xbf7fe02a6b100081, -2.298941004620351e-14),
    (0x0000000000000080, 0.0),
    (0x0000000000000080, 0.0),
    (0x3f8010157589007e, -1.4902732911301337e-14),
    (0x3f9020565893807c, -3.527980389655325e-14),
    (0x3f98492528c9007a, -4.730054772033249e-14),
    (0x3fa0415d89e74078, 7.580310369375161e-15),
    (0x3fa466aed42e0076, -4.9893776716773285e-14),
    (0x3fa894aa149fc074, -2.262629393030674e-14),
    (0x3faccb73cdddc072, -2.345674491018699e-14),
    (0x3faeea31c006c071, -1.3352588834854848e-14),
    (0x3fb1973bd146606f, -3.765296820388875e-14),
    (0x3fb3bdf5a7d1e06d, 5.1128335719851986e-14),
    (0x3fb5e95a4d97a06b, -5.046674438470119e-14),
    (0x3fb700d30aeac06a, 3.1218748807418837e-15),
    (0x3fb9335e5d594068, 3.3871241029241416e-14),
    (0x3fbb6ac88dad6066, -1.7376727386423858e-14),
    (0x3fbc885801bc4065, 3.957125899799804e-14),
    (0x3fbec739830a2063, -5.2849453521890294e-14),
    (0x3fbfe89139dbe062, -3.767012502308738e-14),
    (0x3fc1178e8227e060, 3.1859736349078334e-14),
    (0x3fc1aa2b7e23f05f, 5.0900642926060466e-14),
    (0x3fc2d1610c86805d, 8.710783796122478e-15),
    (0x3fc365fcb015905c, 6.157896229122976e-16),
    (0x3fc4913d8333b05a, 3.821577743916796e-14),
    (0x3fc527e5e4a1b059, 3.9440046718453496e-14),
    (0x3fc6574ebe8c1057, 2.2924522154618074e-14),
    (0x3fc6f0128b757056, -3.742530094732263e-14),
    (0x3fc7898d85445055, -2.5223102140407338e-14),
    (0x3fc8beafeb390053, -1.0320443688698849e-14),
    (0x3fc95a5adcf70052, 1.0634128304268335e-14),
    (0x3fca93ed3c8ae050, -4.3425422595242564e-14),
    (0x3fcb31d8575bd04f, -1.2527395755711364e-14),
    (0x3fcbd087383be04e, -5.204008743405884e-14),
    (0x3fcc6ffbc6f0104d, -3.979844515951702e-15),
    (0x3fcdb13db0d4904b, -4.7955860343296286e-14),
    (0x3fce530effe7104a, 5.015686013791602e-16),
    (0x3fcef5ade4dd0049, -7.252318953240293e-16),
    (0x3fcf991c6cb3b048, 2.4688324156011588e-14),
    (0x3fd07138604d5846, 5.465121253624792e-15),
    (0x3fd0c42d67616045, 4.102651071698446e-14),
    (0x3fd1178e8227e844, -4.996736502345936e-14),
    (0x3fd16b5ccbacf843, 4.903580708156347e-14),
    (0x3fd1bf99635a6842, 5.089628039500759e-14),
    (0x3fd214456d0eb841, 1.1782016386565151e-14),
    (0x3fd2bef07cdc903f, 4.727452940514406e-14),
    (0x3fd314f1e1d3603e, -4.4204083338755686e-14),
    (0x3fd36b6776be103d, 1.548345993498083e-14),
    (0x3fd3c2527733303c, 2.1522127491642888e-14),
    (0x3fd419b423d5e83b, 1.1054030169005386e-14),
    (0x3fd4718dc271c83a, -5.534326352070679e-14),
    (0x3fd4c9e09e173039, -5.351646604259541e-14),
    (0x3fd522ae0738a038, 5.4612144489920215e-14),
    (0x3fd57bf753c8d037, 2.8136969901227338e-14),
    (0x3fd5d5bddf596036, -1.156568624616423e-14),
)
