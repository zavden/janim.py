"""Tsit5 and OrdinaryDiffEq's adaptive driver, bit for bit with Julia (MIT sources).

A port of the SciML stack at the versions below, as Julia 1.12.6 compiles it
on x86-64 with FMA (AVX-512 host):

- OrdinaryDiffEqTsit5 2.1.2, src/: tsit_tableaus.jl (Tsit5ConstantCacheActual
  and Tsit5Interp for Float64, lines 45-101 and 244-276), tsit_caches.jl
  (get_fsalfirstlast, line 56), tsit_perform_step.jl (initialize! 188-202 and
  perform_step! 204-262 for Tsit5Cache), interpolants.jl (tsit5pre0 30-40 and
  _ode_interpolant!(out::Array, ...) for Val{0}, 95-109).
- OrdinaryDiffEqCore 4.12.0, src/: solve.jl (_ode_init 128-874, solve!
  894-936, handle_dt! 958-975, initialize_tstops 978-997, initialize_saveat
  1030-1051), initdt.jl (_ode_initdt_iip 17-298), iterator_interface.jl (_step!
  2-27), integrators/integrator_utils.jl (loopheader! 65-100,
  handle_step_rejection! 103-123, apply_step! 146-174, update_fsal! 186-210,
  modify_dt_for_tstops! 239-295, handle_tstop_step! 297-304, _savevalues!
  311-385, save_dense_at_t! 426-444, _postamble! 464-475,
  solution_endpoint_match_cur_integrator! 511-558, _loopfooter! 568-648,
  fixed_t_for_tstop_error! 710-717, handle_callbacks! 764-814,
  calc_dt_propose! 881-892, fix_dt_at_bounds! 894-907, handle_tstop! 909-933,
  reset_fsal! 944-960), integrators/controllers.jl (the PI controller:
  get_current_qmax 288-293, stepsize_controller! 795-811,
  step_accept_controller! 813-826, step_reject_controller! 828-833),
  integrators/integrator_interface.jl (add_tstop! 325-329, auto_dt_reset!
  654-658), dense/generic_dense.jl (ode_interpolant 1380-1412).
- DiffEqBase 7.10.0, src/: calculate_residuals.jl (9-14 and 117-125),
  common_defaults.jl (ODE_DEFAULT_NORM, 63 and 69-75), utils.jl
  (timedepentdtmin, 50-54).
- SciMLBase 3.41.0, src/integrator_interface.jl: check_error 964-1033,
  check_error! 1068-1075 and step!(integ, dt, stop_at_tdt) 1275-1285.

`@muladd` rewrites `a*b + c*d + e` into nested muladd calls (the first product
stays a plain `*`, every later one wraps the running sum), and Julia lowers
muladd to `fmul contract` + `fadd contract`. Whether the pair becomes one fma
is decided by LLVM, so every formula below follows the optimized code of the
reference build (code_llvm and code_native, Julia 1.12.6), not only the source:

- perform_step! fuses every muladd of the stages, of `u` and of `utilde`
  (vfmadd chains in the scalar loops); `t + c1*dt` shares the product
  `dt*a21` (c1 == a21) and is an unfused add; `t + c2*dt`, `t + c3*dt` and
  `t + c4*dt` are fused.
- calculate_residuals!: fma(max(|u0|, |u1|), reltol, abstol), then a true
  division (the @fastmath div_fast stays vdivsd).
- ODE_DEFAULT_NORM: abs2 is a plain product, so the @fastmath sum is not
  contracted; below 33 entries it is sequential, above it the loop
  vectorizer's 4 x 8 lanes add up (the same tree as _reductions.julia_sum).
- The PI controller's @fastmath `(q11 / fastpower(errold, beta2)) / gamma` is
  reassociated by InstCombine into `q11 / (gamma * fastpower(errold, beta2))`.
- The interpolant's scalar tail (fewer than 8 entries) sums the seven stage
  products unfused (SLP vectorization pairs the products and the fma is lost),
  and the innermost Horner step of b4..b7 is a plain product plus an add; the
  8-wide vector body fuses the whole chain.

Julia's `init` saves every accepted step into `integrator.sol`; `init` here
keeps no solution (nothing reads it and the numbers do not depend on
it). `solve` saves exactly as Julia's `solve` does.
"""

import heapq
import math
import warnings

import numpy as np

from janim.core._julia_math import _fma, fastpower, log10, pow
from janim.core._ranges import step_range

__all__ = [
    "ODEProblem",
    "ODESolution",
    "ODEIntegrator",
    "Tsit5",
    "add_tstop",
    "init",
    "solve",
    "step",
]


# ── Tsit5ConstantCacheActual{Float64, Float64}: tsit_tableaus.jl 52-92 ──────

C1 = 0.161
C2 = 0.327
C3 = 0.9
C4 = 0.9800255409045097
A21 = 0.161
A31 = -0.008480655492356989
A32 = 0.335480655492357
A41 = 2.8971530571054935
A42 = -6.359448489975075
A43 = 4.3622954328695815
A51 = 5.325864828439257
A52 = -11.748883564062828
A53 = 7.4955393428898365
A54 = -0.09249506636175525
A61 = 5.86145544294642
A62 = -12.92096931784711
A63 = 8.159367898576159
A64 = -0.071584973281401
A65 = -0.028269050394068383
A71 = 0.09646076681806523
A72 = 0.01
A73 = 0.4798896504144996
A74 = 1.379008574103742
A75 = -3.290069515436081
A76 = 2.324710524099774
BTILDE1 = -0.00178001105222577714
BTILDE2 = -0.0008164344596567469
BTILDE3 = 0.007880878010261995
BTILDE4 = -0.1447110071732629
BTILDE5 = 0.5823571654525552
BTILDE6 = -0.45808210592918697
BTILDE7 = 0.015151515151515152

# ── Tsit5Interp{Float64}: tsit_tableaus.jl 243-278 ──────────────────────────

R11 = 1.0
R12 = -2.763706197274826
R13 = 2.9132554618219126
R14 = -1.0530884977290216
R22 = 0.13169999999999998
R23 = -0.2234
R24 = 0.1017
R32 = 3.9302962368947516
R33 = -5.941033872131505
R34 = 2.490627285651253
R42 = -12.411077166933676
R43 = 30.33818863028232
R44 = -16.548102889244902
R52 = 37.50931341651104
R53 = -88.1789048947664
R54 = 47.37952196281928
R62 = -27.896526289197286
R63 = 65.09189467479366
R64 = -34.87065786149661
R72 = 1.5
R73 = -4.0
R74 = 2.5

# ── PIController(Float64, Tsit5()): controllers.jl 755-765, alg_utils.jl ───
# beta2 = 2//(5*5), beta1 = 7//(10*5), qoldinit = 1//10^4, qmin = 1//5,
# qmax = 10, qmax_first_step = 10000, gamma = 9//10, qsteady = 1: each
# Rational converted to Float64 as num/den.

BETA1 = 7 / 50
BETA2 = 2 / 25
QOLDINIT = 1 / 10**4
QMIN = 1 / 5
QMAX = 10.0
QMAX_FIRST_STEP = 10000.0
GAMMA = 9 / 10
QSTEADY_MIN = 1.0
QSTEADY_MAX = 1.0

ALG_ORDER = 5
MAXITERS = 1000000

_DEFAULT = "Default"
_SUCCESS = "Success"


class Tsit5:
    """The Tsitouras 5(4) Runge-Kutta pair (OrdinaryDiffEqTsit5.Tsit5)."""

    order = ALG_ORDER

    def __repr__(self):
        return "Tsit5()"


class ODEProblem:
    """SciMLBase's ODEProblem in its in-place form: `f(du, u, p, t)` writes `du`.

    `u0` is copied into a Float64 array and `tspan` into a pair of floats.
    """

    def __init__(self, f, u0, tspan, p=None):
        self.f = f
        self.u0 = np.array(u0, dtype=np.float64)
        if self.u0.ndim != 1:
            raise ValueError("u0 must be a vector")
        self.tspan = (float(tspan[0]), float(tspan[1]))
        self.p = p


class ODESolution:
    """The saved trajectory: `t`, `u`, and the dense stages `k` per saved point."""

    __slots__ = ("t", "u", "k", "naccept", "nreject", "nf", "retcode")

    def __init__(self):
        self.t = []
        self.u = []
        self.k = []
        self.naccept = 0
        self.nreject = 0
        self.nf = 0
        self.retcode = _DEFAULT


class ODEIntegrator:
    """The integrator state of OrdinaryDiffEqCore (integrators/type.jl), Tsit5 only.

    `u`, `uprev`, `k1`..`k7`, `utilde`, `tmp` and `atmp` are Float64 arrays
    updated in place; `fsalfirst` and `fsallast` are `k1` and `k7` themselves
    (tsit_caches.jl line 56). `EEst`, `q11` and `errold` are the PI
    controller cache; `naccept`, `nreject` and `nf` are the solve statistics.
    """

    __slots__ = (
        "f",
        "p",
        "tspan",
        "tdir",
        "n",
        "u",
        "uprev",
        "t",
        "tprev",
        "dt",
        "dtcache",
        "dtpropose",
        "iter",
        "success_iter",
        "naccept",
        "nreject",
        "nf",
        "k1",
        "k2",
        "k3",
        "k4",
        "k5",
        "k6",
        "k7",
        "utilde",
        "tmp",
        "atmp",
        "EEst",
        "q11",
        "errold",
        "abstol",
        "reltol",
        "dtmax",
        "dtmin",
        "tstops",
        "saveat",
        "saveat_cache",
        "save_on",
        "save_everystep",
        "save_start",
        "save_end",
        "save_end_user",
        "dense",
        "accept_step",
        "force_stepfail",
        "last_stepfail",
        "next_step_tstop",
        "tstop_target",
        "just_hit_tstop",
        "isout",
        "reeval_fsal",
        "derivative_discontinuity",
        "do_error_check",
        "saveiter",
        "saveiter_dense",
        "retcode",
        "sol",
    )

    @property
    def fsalfirst(self):
        return self.k1

    @property
    def fsallast(self):
        return self.k7

    @property
    def k(self):
        return [self.k1, self.k2, self.k3, self.k4, self.k5, self.k6, self.k7]


# ── scalar helpers: Julia's Float64 min/max/eps as compiled ─────────────────


def _eps(x):
    """eps(x::Float64): |x - reinterpret(bits(x) xor 1)| in the optimized code."""
    if math.isfinite(x):
        return math.ulp(x)
    return math.nan


def _jmin(x, y):
    """min(x::Float64, y::Float64) = llvm.minimum: NaN wins, -0.0 < +0.0."""
    if x != x or y != y:
        return math.nan
    if x < y:
        return x
    if y < x:
        return y
    return x if math.copysign(1.0, x) < 0 else y


def _jmax(x, y):
    """max(x::Float64, y::Float64) = llvm.maximum: NaN wins, +0.0 > -0.0."""
    if x != x or y != y:
        return math.nan
    if x > y:
        return x
    if y > x:
        return y
    return y if math.copysign(1.0, x) < 0 else x


def _sign(x):
    """sign(x::Float64)."""
    if x != x or x == 0:
        return x
    return math.copysign(1.0, x)


def _egal(x, y):
    """x === y for Float64: bitwise identity (so -0.0 !== 0.0, NaN === NaN)."""
    if x != x:
        return y != y
    return x == y and math.copysign(1.0, x) == math.copysign(1.0, y)


def _timedepentdtmin(integ):
    """DiffEqBase.timedepentdtmin(integrator) = abs(max(eps(t), dtmin))."""
    return abs(_jmax(_eps(integ.t), integ.dtmin))


# ── the norm and the residuals: DiffEqBase, as compiled ─────────────────────


def _horizontal(lanes):
    """llvm.vector.reduce.fadd with fast flags: add halves until one lane is left."""
    while len(lanes) > 1:
        half = len(lanes) // 2
        lanes = lanes[:half] + lanes[half:]
    return lanes[0]


def internal_norm(values):
    """ODE_DEFAULT_NORM(u::Vector{Float64}, t): sqrt(sum(abs2, u) / length(u)).

    The optimized loop squares each entry with a plain fmul (abs2 is not a
    fast op) and adds with `fadd fast`: the first square is peeled, fewer
    than 33 entries add up in order, and longer vectors run the vectorizer's
    four 8-lane accumulators from the second entry on.
    """
    count = len(values)
    if count == 0:
        return 0.0
    first = values[0]
    total = first * first
    index = 1
    if count >= 33:
        stop = 1 + (count - 1) // 32 * 32
        lanes = np.zeros((4, 8), dtype=np.float64)
        lanes[0, 0] = total
        block = np.empty(32, dtype=np.float64)
        while index < stop:
            block[:] = values[index:index + 32]
            lanes += (block * block).reshape(4, 8)
            index += 32
        total = float(_horizontal(((lanes[1] + lanes[0]) + lanes[2]) + lanes[3]))
    for value in values[index:]:
        total = total + value * value
    # x / max(length(u), 1): the Int converts exactly, then sqrt_fast (vsqrtsd).
    return math.sqrt(total / count)


def _residual(error, previous, current, abstol, reltol):
    """calculate_residuals(ũ, u₀, u₁, α, ρ): ũ / muladd(max(|u₀|, |u₁|), ρ, α).

    The muladd is one fma; the @fastmath division stays a division.
    """
    return error / _fma(_jmax(abs(previous), abs(current)), reltol, abstol)


# ── construction: _ode_init, initialize!, handle_dt! ────────────────────────


def _saveat_heap(saveat, tspan, tdir):
    """initialize_saveat (solve.jl 1030-1051): the pending save times, min first."""
    t0, tf = tspan
    heap = []
    if saveat is None:
        return heap
    if isinstance(saveat, (int, float)):
        directional = tdir * abs(float(saveat))
        # (t0 + d):d:tf, Julia's StepRangeLen for Float64.
        for t in step_range(t0 + directional, tf, directional):
            heap.append(tdir * t)
    else:
        for t in saveat:
            tdir_t = tdir * float(t)
            if tdir * t0 < tdir_t <= tdir * tf:
                heap.append(tdir_t)
    heapq.heapify(heap)
    return heap


def _ode_init(problem, alg, *, reltol, abstol, saveat, save_on):
    """_ode_init (solve.jl 128-874) with Julia's defaults for an in-place problem."""
    if not isinstance(alg, Tsit5):
        raise TypeError("only Tsit5() is ported")
    integ = ODEIntegrator()
    tspan = problem.tspan
    t0, tf = tspan
    tdir = _sign(tf - t0)
    has_saveat = saveat is not None
    saveat_number = isinstance(saveat, (int, float))
    if has_saveat and not saveat_number:
        saveat = [float(t) for t in saveat]
        has_saveat = len(saveat) > 0
    save_everystep = not has_saveat
    save_start = save_everystep or not has_saveat or saveat_number or (t0 in saveat)
    save_end = save_everystep or not has_saveat or saveat_number or (tf in saveat)
    dense = save_everystep and not has_saveat
    # dtmax = tspan[end] - tspan[1], made to point along tdir; dtmin = 0.
    dtmax = tf - t0
    if dtmax > 0 and tdir < 0:
        dtmax = dtmax * tdir
    u = problem.u0.copy()
    n = len(u)
    integ.f = problem.f
    integ.p = problem.p
    integ.tspan = tspan
    integ.tdir = tdir
    integ.n = n
    integ.u = u
    integ.uprev = u.copy()
    integ.t = t0
    integ.tprev = t0
    integ.dt = 0.0
    integ.dtcache = 0.0
    integ.dtpropose = 0.0
    integ.iter = 0
    integ.success_iter = 0
    integ.naccept = 0
    integ.nreject = 0
    integ.nf = 0
    # alg_cache (tsit_caches.jl 33-54): zeroed stages and buffers.
    for name in ("k1", "k2", "k3", "k4", "k5", "k6", "k7", "utilde", "tmp", "atmp"):
        setattr(integ, name, np.zeros(n, dtype=np.float64))
    # PIControllerCache: q11 = 1, errold = qoldinit, EEst = oneunit.
    integ.EEst = 1.0
    integ.q11 = 1.0
    integ.errold = QOLDINIT
    integ.abstol = float(abstol)
    integ.reltol = float(reltol)
    integ.dtmax = dtmax
    integ.dtmin = 0.0
    # initialize_tstops (solve.jl 978-997): no user tstops, then tdir * tf.
    integ.tstops = [tdir * tf]
    integ.saveat = _saveat_heap(saveat, tspan, tdir)
    integ.saveat_cache = saveat
    integ.save_on = save_on
    integ.save_everystep = save_everystep
    integ.save_start = save_start
    integ.save_end = save_end
    integ.save_end_user = None
    integ.dense = dense
    integ.accept_step = False
    integ.force_stepfail = False
    integ.last_stepfail = False
    integ.next_step_tstop = False
    integ.tstop_target = 0.0
    integ.just_hit_tstop = False
    integ.isout = False
    integ.reeval_fsal = False
    integ.derivative_discontinuity = False
    integ.do_error_check = True
    integ.saveiter = 0
    integ.saveiter_dense = 0
    integ.retcode = _DEFAULT
    sol = ODESolution()
    integ.sol = sol
    if save_on and save_start:
        integ.saveiter = 1
        integ.saveiter_dense = 1
        sol.t.append(t0)
        sol.u.append(u.copy())
        # [rate_prototype]: a copy of u0 (solve.jl 815-817).
        sol.k.append([u.copy()])
    # initialize!(integrator, cache::Tsit5Cache): the pre-start FSAL.
    integ.f(integ.k1, integ.uprev, integ.p, integ.t)
    integ.nf += 1
    _handle_dt(integ)
    return integ


def _handle_dt(integ):
    """handle_dt!(integrator, nothing) (solve.jl 958-975): auto_dt_reset! (654-658)."""
    integ.dt = _ode_initdt_iip(integ)
    integ.dtpropose = integ.dt
    integ.nf += 2
    if _sign(integ.dt) != integ.tdir and integ.dt != 0 and not math.isnan(integ.dt):
        raise RuntimeError("Automatic dt setting has the wrong sign. Exiting. Please report this error.")
    if math.isnan(integ.dt):
        warnings.warn("Automatic dt set the starting dt as NaN, causing instability. Exiting.")


def _ode_initdt_iip(integ):
    """_ode_initdt_iip (initdt.jl 17-298): Hairer and Wanner's starting step.

    Under @muladd, `abstol + |u0|*reltol` and `u0 + dt0*f0` are fmas; the
    rest is plain arithmetic. Rational thresholds compare and multiply as
    Float64 (1//10^5 is 1e-5, `dt0 * 1//10^3` is dt0*0.001).
    """
    u0 = integ.u.tolist()
    t = integ.t
    tdir = integ.tdir
    f = integ.f
    p = integ.p
    abstol = integ.abstol
    reltol = integ.reltol
    dtmax_tdir = tdir * integ.dtmax
    dtmin = math.nextafter(_jmax(integ.dtmin, _eps(t)), math.inf)
    smalldt = _jmax(dtmin, 1 / 10**6)
    count = len(u0)
    if count == 0:
        return tdir * _jmax(smalldt, dtmin)
    # sk lives in cache.tmp (get_tmp_cache).
    sk = [_fma(abs(value), reltol, abstol) for value in u0]
    integ.tmp[:] = sk
    # f0 is integrator.fsallast, i.e. k7 (the method is FSAL).
    f0_array = integ.k7
    f(f0_array, integ.u, p, t)
    f0 = f0_array.tolist()
    d0 = internal_norm([u0[i] / sk[i] for i in range(count)])
    # f0 / sk * oneunit(t): the product by 1.0 is the identity.
    d1 = internal_norm([f0[i] / sk[i] for i in range(count)])
    if math.isnan(d1):
        warnings.warn(
            "First function call produced NaNs. Exiting. Double check that none of the "
            "initial conditions, parameters, or timespan values are NaN."
        )
        return tdir * dtmin
    if (d0 < 1 / 10**5) | (d1 < 1 / 10**5):
        dt0 = smalldt
    else:
        dt0 = (d0 / d1) / 100
    dt0 = _jmin(dt0, dtmax_tdir)
    if dt0 < 10 * 2.0**-52:
        return tdir * _jmax(smalldt, dtmin)
    dt0_tdir = tdir * dt0
    u1_list = [_fma(dt0_tdir, f0[i], u0[i]) for i in range(count)]
    u1 = np.array(u1_list, dtype=np.float64)
    f1_array = np.zeros(count, dtype=np.float64)
    f(f1_array, u1, p, t + dt0_tdir)
    f1 = f1_array.tolist()
    if all(f0[i] == f1[i] for i in range(count)):
        return tdir * _jmax(dtmin, 100 * dt0)
    d2 = internal_norm([(f1[i] - f0[i]) / sk[i] for i in range(count)]) / dt0
    max_d1d2 = _jmax(d1, d2)
    if max_d1d2 <= 1 / 10**15:
        dt1 = _jmax(1 / 10**6, dt0 * (1 / 10**3))
    else:
        # 10.0^(-(2 + log10(max_d1d2)) / order): Julia's pow and log10.
        dt1 = pow(10.0, -(2 + log10(max_d1d2)) / ALG_ORDER)
    return tdir * _jmax(dtmin, _jmin(_jmin(100 * dt0, dt1), dtmax_tdir))


# ── one step: perform_step! for Tsit5Cache ──────────────────────────────────

# The stage coefficients as @muladd folds them (tsit_perform_step.jl 215-253).
_STAGE3 = (A31, A32)
_STAGE4 = (A41, A42, A43)
_STAGE5 = (A51, A52, A53, A54)
_STAGE6 = (A61, A62, A63, A64, A65)
_STAGE7 = (A71, A72, A73, A74, A75, A76)
_BTILDE = (BTILDE1, BTILDE2, BTILDE3, BTILDE4, BTILDE5, BTILDE6, BTILDE7)


def _muladd_sum(coefficients, stages, i):
    """`c1*k1[i] + c2*k2[i] + ...` as @muladd nests it (sum_to_muladd).

    The first product is the plain `*` that seeds the fold; every later term
    wraps the running sum in muladd(c, k[i], sum), which the compiled
    perform_step! fuses (vfmadd231sd chains).
    """
    total = coefficients[0] * stages[0][i]
    for index in range(1, len(coefficients)):
        total = _fma(coefficients[index], stages[index][i], total)
    return total


def _stage(dt, uprev, coefficients, stages):
    """`uprev + dt * (a1*k1 + ...)`: muladd(dt, sum, uprev), one more fma."""
    return [
        _fma(dt, _muladd_sum(coefficients, stages, i), base)
        for i, base in enumerate(uprev)
    ]


def _perform_step(integ):
    """perform_step!(integrator, cache::Tsit5Cache) (tsit_perform_step.jl 204-262).

    The stage times follow the compiled code: `t + c1*dt` reuses the plain
    product `a = dt*a21` (c1 == a21) and is an unfused add, `t + c2*dt`,
    `t + c3*dt` and `t + c4*dt` are fmas, and the last two stages take
    `t + dt`. `utilde` is a plain `dt * (...)` around its muladd fold.
    """
    t = integ.t
    dt = integ.dt
    f = integ.f
    p = integ.p
    tmp = integ.tmp
    uprev = integ.uprev.tolist()
    k1 = integ.k1.tolist()
    # tmp = uprev + a*k1 with a = dt*a21: muladd(a, k1, uprev).
    a = dt * A21
    tmp[:] = [_fma(a, k1[i], base) for i, base in enumerate(uprev)]
    f(integ.k2, tmp, p, t + a)
    k2 = integ.k2.tolist()
    tmp[:] = _stage(dt, uprev, _STAGE3, (k1, k2))
    f(integ.k3, tmp, p, _fma(dt, C2, t))
    k3 = integ.k3.tolist()
    tmp[:] = _stage(dt, uprev, _STAGE4, (k1, k2, k3))
    f(integ.k4, tmp, p, _fma(dt, C3, t))
    k4 = integ.k4.tolist()
    tmp[:] = _stage(dt, uprev, _STAGE5, (k1, k2, k3, k4))
    f(integ.k5, tmp, p, _fma(dt, C4, t))
    k5 = integ.k5.tolist()
    tmp[:] = _stage(dt, uprev, _STAGE6, (k1, k2, k3, k4, k5))
    t_end = t + dt
    f(integ.k6, tmp, p, t_end)
    k6 = integ.k6.tolist()
    u = _stage(dt, uprev, _STAGE7, (k1, k2, k3, k4, k5, k6))
    integ.u[:] = u
    f(integ.k7, integ.u, p, t_end)
    k7 = integ.k7.tolist()
    integ.nf += 6
    stages = (k1, k2, k3, k4, k5, k6, k7)
    utilde = [dt * _muladd_sum(_BTILDE, stages, i) for i in range(len(uprev))]
    integ.utilde[:] = utilde
    abstol = integ.abstol
    reltol = integ.reltol
    atmp = [
        _residual(utilde[i], base, u[i], abstol, reltol)
        for i, base in enumerate(uprev)
    ]
    integ.atmp[:] = atmp
    integ.EEst = internal_norm(atmp)


# ── the PI controller: integrators/controllers.jl ───────────────────────────


def _stepsize_controller(integ):
    """stepsize_controller!(integrator, cache::PIControllerCache) (795-811).

    `@fastmath clamp(q / gamma, inv(qmax), inv(qmin))` with
    `q = q11 / fastpower(errold, beta2)`: InstCombine turns the two divisions
    into `q11 / (gamma * fastpower(errold, beta2))` (fast flags), one product
    and one division; inv(qmax) and inv(qmin) are true divisions.
    """
    # get_current_qmax: qmax_first_step until the first step is accepted.
    qmax = QMAX_FIRST_STEP if integ.success_iter == 0 else QMAX
    eest = integ.EEst
    if eest == 0:
        return 1.0 / qmax
    q11 = fastpower(eest, BETA1)
    q = q11 / (GAMMA * fastpower(integ.errold, BETA2))
    integ.q11 = q11
    low = 1.0 / qmax
    high = 1.0 / QMIN
    # clamp(x, lo, hi) = ifelse(x > hi, hi, ifelse(x < lo, lo, x))
    if q > high:
        return high
    if q < low:
        return low
    return q


def _step_accept_controller(integ, q):
    """step_accept_controller!(integrator, cache::PIControllerCache, alg, q) (813-826)."""
    if QSTEADY_MIN <= q <= QSTEADY_MAX:
        q = 1.0
    integ.errold = _jmax(integ.EEst, QOLDINIT)
    # handle_disco_accept! returns dt / q without discontinuity detection.
    return integ.dt / q


def _step_reject_controller(integ):
    """step_reject_controller!(integrator, cache::PIControllerCache, alg) (828-833)."""
    integ.dt = integ.dt / _jmin(1.0 / QMIN, integ.q11 / GAMMA)


# ── the driver: integrators/integrator_utils.jl ─────────────────────────────


def _fix_dt_at_bounds(integ):
    """fix_dt_at_bounds! (894-907)."""
    if integ.tdir > 0:
        integ.dt = _jmin(integ.dtmax, integ.dt)
    else:
        integ.dt = _jmax(integ.dtmax, integ.dt)
    dtmin = _timedepentdtmin(integ)
    if integ.tdir > 0:
        integ.dt = _jmax(integ.dt, dtmin)
    else:
        integ.dt = _jmin(integ.dt, dtmin)


def _modify_dt_for_tstops(integ):
    """modify_dt_for_tstops! (239-295), adaptive branch.

    A step within 100 eps of the next tstop is flagged to land on it exactly
    (fixed_t_for_tstop_error!); dtpropose keeps the untruncated |dt|.
    """
    if not integ.tstops:
        integ.next_step_tstop = False
        return
    tdir = integ.tdir
    t = integ.t
    tdir_t = tdir * t
    tdir_tstop = integ.tstops[0]
    distance = abs(tdir_tstop - tdir_t)
    if math.isfinite(tdir_tstop) and math.isfinite(t):
        tstop_tol = 100 * _eps(_jmax(abs(t), abs(tdir_tstop)))
    else:
        tstop_tol = 0.0
    original_dt = abs(integ.dt)
    integ.dtpropose = tdir * original_dt
    if original_dt + tstop_tol < distance:
        integ.next_step_tstop = False
    else:
        integ.next_step_tstop = True
        integ.tstop_target = tdir * tdir_tstop
    integ.dt = tdir * _jmin(original_dt, distance)


def _apply_step(integ):
    """apply_step! (146-174): uprev = u, dt = dtpropose, FSAL copy, tstops."""
    integ.uprev[:] = integ.u
    integ.dt = integ.dtpropose
    # update_fsal!: no discontinuity, no reeval_fsal: copy fsallast into fsalfirst.
    integ.k1[:] = integ.k7
    _modify_dt_for_tstops(integ)


def _handle_step_rejection(integ):
    """handle_step_rejection! (103-123) for an ODE (no noise process)."""
    if integ.isout:
        integ.dt = integ.dt * QMIN
    elif not integ.force_stepfail:
        _step_reject_controller(integ)


def _loopheader(integ):
    """loopheader! (65-100): accept or reject the previous step, then bound dt."""
    if integ.iter > 0:
        if not integ.force_stepfail and integ.accept_step:
            integ.success_iter += 1
            _apply_step(integ)
        elif not integ.accept_step or integ.force_stepfail:
            _handle_step_rejection(integ)
    elif integ.derivative_discontinuity:
        # on_derivative_discontinuity_at_init!: update_uprev!, then update_fsal!
        # re-evaluates the FSAL derivative (reset_fsal!).
        integ.uprev[:] = integ.u
        integ.nf += 1
        integ.f(integ.k1, integ.u, integ.p, integ.t)
    integ.iter += 1
    _fix_dt_at_bounds(integ)
    _modify_dt_for_tstops(integ)
    integ.force_stepfail = False


def _fixed_t_for_tstop_error(integ, ttmp):
    """fixed_t_for_tstop_error! (710-717)."""
    if integ.next_step_tstop:
        integ.next_step_tstop = False
        return integ.tstop_target
    return ttmp


def _calc_dt_propose(integ, dtnew):
    """calc_dt_propose! (881-892), with the updated t in timedepentdtmin."""
    tdir = integ.tdir
    dtpropose = tdir * _jmin(abs(integ.dtmax), abs(dtnew))
    dtpropose = tdir * _jmax(abs(dtpropose), _timedepentdtmin(integ))
    integ.dtpropose = dtpropose


def _loopfooter(integ):
    """_loopfooter! (568-648), adaptive branch; handle_callbacks! (764-814) only saves."""
    integ.reeval_fsal = False
    integ.derivative_discontinuity = False
    integ.do_error_check = True
    ttmp = integ.t + integ.dt
    q = _stepsize_controller(integ)
    integ.isout = False
    integ.accept_step = integ.EEst <= 1
    if integ.accept_step:
        integ.naccept += 1
        integ.last_stepfail = False
        integ.tprev = integ.t
        if integ.next_step_tstop:
            # dt was cut to reach the tstop; the controller sees dtpropose.
            integ.dt = integ.dtpropose
        integ.t = _fixed_t_for_tstop_error(integ, ttmp)
        _calc_dt_propose(integ, _step_accept_controller(integ, q))
        # handle_callbacks!: no callbacks, so savevalues!.
        _savevalues(integ)
    else:
        integ.nreject += 1


def _handle_tstop(integ):
    """handle_tstop! (909-933): pop every copy of a tstop just reached."""
    tstops = integ.tstops
    if not tstops:
        return
    tdir_t = integ.tdir * integ.t
    tdir_tstop = tstops[0]
    if tdir_t == tdir_tstop:
        while tdir_t == tdir_tstop:
            heapq.heappop(tstops)
            if tstops:
                tdir_tstop = tstops[0]
            else:
                break
        integ.just_hit_tstop = True
    elif tdir_t > tdir_tstop:
        raise RuntimeError(
            "Something went wrong. Integrator stepped past tstops but the algorithm "
            "was dtchangeable. Please report this error."
        )


def _check_error(integ):
    """SciMLBase.check_error (964-1033) and check_error! (1068-1075): the return code."""
    code = integ.retcode
    if code not in (_DEFAULT, _SUCCESS):
        return code
    if math.isnan(integ.dt):
        code = "DtNaN"
        warnings.warn(
            "NaN dt detected. Likely a NaN value in the state, parameters, or derivative "
            "value caused this outcome."
        )
    elif integ.iter > MAXITERS:
        code = "MaxIters"
        warnings.warn("Interrupted. Larger maxiters is needed.")
    else:
        step_accepted = integ.accept_step
        first_tstop = integ.tstops[0] if integ.tstops else math.inf
        if abs(integ.dt) <= abs(integ.dtmin) and (
            not step_accepted or integ.t + integ.dt < integ.tdir * first_tstop
        ):
            code = "DtLessThanMin"
            warnings.warn(f"dt({integ.dt}) <= dtmin({integ.dtmin}) at t={integ.t}. Aborting.")
        elif not step_accepted and abs(integ.dt) <= abs(_eps(integ.t)):
            code = "Unstable"
            warnings.warn(
                f"At t={integ.t}, dt was forced below floating point epsilon {integ.dt}. Aborting."
            )
        elif step_accepted and not all(math.isfinite(value) for value in integ.u.tolist()):
            code = "Unstable"
            warnings.warn("Instability detected. Aborting.")
        else:
            code = _SUCCESS
    integ.retcode = code
    integ.sol.retcode = code
    if code != _SUCCESS:
        _postamble(integ)
    return code


def _step(integ):
    """OrdinaryDiffEqCore._step! (iterator_interface.jl 2-27): one accepted step."""
    _loopheader(integ)
    if integ.do_error_check and _check_error(integ) != _SUCCESS:
        return integ.retcode
    _perform_step(integ)
    _loopfooter(integ)
    while not integ.accept_step:
        _loopheader(integ)
        if integ.do_error_check and _check_error(integ) != _SUCCESS:
            return integ.retcode
        _perform_step(integ)
        _loopfooter(integ)
    _handle_tstop(integ)
    return integ.retcode


# ── saving and the dense interpolant ────────────────────────────────────────


def _interpolant(theta, dt, y0, stages):
    """_ode_interpolant!(out::Array, Θ, dt, y₀, y₁, k, ::Tsit5Cache, nothing, Val{0}, nothing).

    tsit5pre0: b1Θ = Θ*evalpoly(Θ, r11..r14), biΘ = Θ²*evalpoly(Θ, ri2..ri4),
    evalpoly being nested muladd. The compiled code fuses the Horner steps of
    b1..b3, but pairs (b5, b4) and (b7, b6) in 2-wide vectors whose innermost
    step `Θ*ri4 + ri3` is a vmulpd plus a vaddpd/vsubpd (two roundings).
    The loop over entries is 8 wide (every muladd an fma) and its scalar tail
    multiplies the pairs with vmulpd and adds the seven products one by one;
    `dt*sum + y₀` is an fma in both.
    """
    k1, k2, k3, k4, k5, k6, k7 = stages
    theta2 = theta * theta
    b1 = _fma(theta, _fma(theta, _fma(theta, R14, R13), R12), R11) * theta
    b2 = theta2 * _fma(theta, _fma(theta, R24, R23), R22)
    b3 = theta2 * _fma(theta, _fma(theta, R34, R33), R32)
    b4 = theta2 * _fma(theta, theta * R44 + R43, R42)
    b5 = theta2 * _fma(theta, theta * R54 + R53, R52)
    b6 = theta2 * _fma(theta, theta * R64 + R63, R62)
    b7 = theta2 * _fma(theta, theta * R74 + R73, R72)
    count = len(y0)
    vector_end = count - count % 8
    out = []
    for i in range(count):
        total = b1 * k1[i]
        if i < vector_end:
            total = _fma(b2, k2[i], total)
            total = _fma(b3, k3[i], total)
            total = _fma(b4, k4[i], total)
            total = _fma(b5, k5[i], total)
            total = _fma(b6, k6[i], total)
            total = _fma(b7, k7[i], total)
        else:
            total = total + b2 * k2[i]
            total = total + b3 * k3[i]
            total = total + b4 * k4[i]
            total = total + b5 * k5[i]
            total = total + b6 * k6[i]
            total = total + b7 * k7[i]
        out.append(_fma(dt, total, y0[i]))
    return np.array(out, dtype=np.float64)


def _save_dense_at_t(integ):
    """save_dense_at_t! (integrator_utils.jl 426-444): a copy of k1..k7."""
    if integ.dense:
        integ.saveiter_dense += 1
        integ.sol.k.append([stage.copy() for stage in integ.k])


def _savevalues(integ, force_save=False):
    """_savevalues! (311-385): the saveat points passed, then every step if asked."""
    if not integ.save_on:
        return
    sol = integ.sol
    tdir = integ.tdir
    tdir_t = tdir * integ.t
    saveat = integ.saveat
    while saveat and saveat[0] <= tdir_t:
        integ.saveiter += 1
        curt = tdir * heapq.heappop(saveat)
        if curt != integ.t:
            theta = (curt - integ.tprev) / integ.dt
            stages = [stage.tolist() for stage in integ.k]
            value = _interpolant(theta, integ.dt, integ.uprev.tolist(), stages)
            sol.t.append(curt)
            sol.u.append(value)
        else:
            if curt == integ.tspan[1] and not integ.save_end:
                integ.saveiter -= 1
                continue
            sol.t.append(integ.t)
            sol.u.append(integ.u.copy())
            _save_dense_at_t(integ)
    if force_save or (
        integ.save_everystep
        and (
            not sol.t
            or (
                (not _egal(integ.t, sol.t[-1]) or integ.dt == 0)
                and (integ.save_end or not _egal(integ.t, integ.tspan[1]))
            )
        )
    ):
        integ.saveiter += 1
        sol.u.append(integ.u.copy())
        sol.t.append(integ.t)
        _save_dense_at_t(integ)


def _saveat_contains(saveat, t):
    if saveat is None:
        return False
    if isinstance(saveat, (int, float)):
        return t == saveat
    return t in saveat


def _postamble(integ):
    """_postamble! (464-475): solution_endpoint_match_cur_integrator! (511-558), the counts."""
    sol = integ.sol
    if integ.save_on and integ.save_end and (
        integ.saveiter == 0
        or (
            sol.t[integ.saveiter - 1] != integ.t
            and (
                integ.save_end_user is True
                or _saveat_contains(integ.saveat_cache, integ.t)
                or integ.t == integ.tspan[1]
                or not integ.saveat_cache
            )
        )
    ):
        integ.saveiter += 1
        sol.t.append(integ.t)
        sol.u.append(integ.u.copy())
        _save_dense_at_t(integ)
    sol.naccept = integ.naccept
    sol.nreject = integ.nreject
    sol.nf = integ.nf


def _handle_tstop_step(integ):
    """handle_tstop_step! (297-304): skip perform_step! for a dt below eps(t)."""
    if abs(integ.dt) < _eps(abs(integ.t)):
        integ.accept_step = True
    else:
        _perform_step(integ)


def _solve_loop(integ):
    """SciMLBase.solve!(integrator::ODEIntegrator) (solve.jl 894-936)."""
    tstops = integ.tstops
    while tstops:
        first_tstop = tstops[0]
        while integ.tdir * integ.t < first_tstop:
            _loopheader(integ)
            if integ.do_error_check and _check_error(integ) != _SUCCESS:
                return integ.sol
            if integ.next_step_tstop:
                _handle_tstop_step(integ)
            else:
                _perform_step(integ)
            should_exit = integ.next_step_tstop
            _loopfooter(integ)
            if not tstops or should_exit:
                break
        _handle_tstop(integ)
    _postamble(integ)
    if integ.sol.retcode == _DEFAULT:
        integ.sol.retcode = _SUCCESS
    return integ.sol


# ── public API ──────────────────────────────────────────────────────────────


def init(problem, alg, *, reltol=1e-3, abstol=1e-6):
    """`init(prob, Tsit5(); reltol, abstol)`: an integrator for step-by-step use.

    Julia's defaults: dtmax = tspan[2] - tspan[1], dtmin = 0, the PI
    controller of Tsit5, the end of tspan as the only tstop, and the
    automatic initial dt of _ode_initdt_iip.
    """
    return _ode_init(
        problem,
        alg,
        reltol=reltol,
        abstol=abstol,
        saveat=None,
        save_on=False,
    )


def add_tstop(integrator, t):
    """add_tstop!(integrator, t) (integrator_interface.jl 325-329)."""
    t = float(t)
    if integrator.tdir * (t - integrator.t) < 0:
        raise ValueError("Tried to add a tstop that is behind the current time. This is strictly forbidden")
    heapq.heappush(integrator.tstops, integrator.tdir * t)


def step(integrator, dt, stop_at_tdt=False):
    """SciMLBase.step!(integ, dt, stop_at_tdt): accepted steps until t + dt.

    With `stop_at_tdt` the last step lands exactly on t + dt (a tstop).
    """
    dt = float(dt)
    if dt * integrator.tdir < 0:
        raise ValueError("Cannot step backward.")
    next_t = integrator.t + dt
    if stop_at_tdt:
        add_tstop(integrator, next_t)
    while integrator.t * integrator.tdir < next_t * integrator.tdir:
        _step(integrator)
        if integrator.retcode not in (_DEFAULT, _SUCCESS):
            break


def solve(problem, alg, *, reltol=1e-3, abstol=1e-6, saveat=None):
    """`solve(prob, Tsit5(); reltol, abstol[, saveat])` as OrdinaryDiffEq saves it.

    Without `saveat` every accepted step is saved with its dense stages
    (`save_everystep = dense = true`); with a number, the points
    `tspan[1] + saveat : saveat : tspan[2]` are interpolated by Tsit5's free
    interpolant, plus the start and the end of tspan.
    """
    integ = _ode_init(
        problem,
        alg,
        reltol=reltol,
        abstol=abstol,
        saveat=saveat,
        save_on=True,
    )
    return _solve_loop(integ)
