"""Point deformations in absolute coordinates."""

import math

import numpy as np

from janim.constants import LEFT, ORIGIN, RIGHT, TAU, UP
from janim.core.algebra import apply_matrix_rows, norm
from janim.core.mobject import Mobject, VMobject
from .animation import Animation, animation_copy, families
from .transform import Transform, _FunctionalTransform


class Homotopy(Animation):
    def __init__(self, homotopy, mobject, *, run_time=3.0, smooth_handles=False, **kwargs):
        super().__init__(mobject, run_time=run_time, **kwargs)
        self.homotopy = homotopy
        self.smooth_handles = bool(smooth_handles)

    def interpolate_submobject(self, submobject, starting_submobject, alpha):
        if not isinstance(submobject, VMobject) or not isinstance(starting_submobject, VMobject):
            return
        submobject.set_points(starting_submobject.points)
        if not submobject.has_points():
            return
        # The callback inputs are converted to Float64, then its return to
        # Point3f before apply_points_function adds the (zero) origin.
        submobject.apply_function(
            lambda point: np.array(self.homotopy(*map(float, point), float(alpha)), dtype=np.float32),
            about_point=ORIGIN,
        )
        if self.smooth_handles:
            submobject.make_smooth(recurse=False)


class SmoothedVectorizedHomotopy(Homotopy):
    def __init__(self, homotopy, mobject, **kwargs):
        super().__init__(homotopy, mobject, **{"smooth_handles": True, **kwargs})


class ComplexHomotopy(Homotopy):
    def __init__(self, homotopy, mobject, **kwargs):
        def function(x, y, z, time):
            result = homotopy(complex(x, y), time)
            return result.real, result.imag, z

        super().__init__(function, mobject, **kwargs)


class ApplyWave(Homotopy):
    def __init__(self, mobject, *, direction=UP, amplitude=0.2, ripples=1, run_time=2.0, **kwargs):
        if not isinstance(ripples, int) or ripples < 1:
            raise ValueError("ripples must be an integer of at least one")
        left = float(mobject.get_bounding_box_point(LEFT)[0])
        right = float(mobject.get_bounding_box_point(RIGHT)[0])
        span = max(right - left, 1e-6)
        direction = np.asarray(direction, dtype=np.float32)
        length = norm(direction)
        vector = float(amplitude) * (direction / length).astype(np.float64) if length > 0 else np.zeros(3)

        def wave(x, y, z, time):
            position = (x - left) / span
            amount = math.sin(TAU * ripples * (position - time)) * math.sin(math.pi * time)
            return x + amount * vector[0], y + amount * vector[1], z + amount * vector[2]

        super().__init__(wave, mobject, run_time=run_time, **kwargs)


class PhaseFlow(Animation):
    def __init__(self, function, mobject, *, run_time=3.0, virtual_time=None, **kwargs):
        from janim.core.rates import linear

        super().__init__(mobject, run_time=run_time, **{"rate_func": linear, **kwargs})
        self.function = function
        self.virtual_time = float(run_time if virtual_time is None else virtual_time)
        self.last_alpha = None

    def begin(self):
        self.starting_mobject = animation_copy(self.mobject)
        self.last_alpha = None
        self._begin_updates()
        return self

    def interpolate(self, alpha):
        if self.last_alpha is not None:
            dt = np.float32(self.virtual_time * (float(alpha) - self.last_alpha))
            self.mobject.apply_function(
                lambda point: point + dt * np.asarray(self.function(point), dtype=np.float32),
                about_point=ORIGIN,
            )
        self.last_alpha = float(alpha)
        return self


class ApplyPointwiseFunction(_FunctionalTransform):
    def __init__(self, function, mobject, *, run_time=3.0, **kwargs):
        super().__init__(
            mobject,
            lambda: animation_copy(mobject).apply_function(function, about_point=ORIGIN),
            run_time=run_time,
            **kwargs,
        )


class ApplyPointwiseFunctionToCenter(_FunctionalTransform):
    """Move the mobject, unchanged, to `function(its center)` (GL's: a Transform, one second)."""

    def __init__(self, function, mobject, **kwargs):
        super().__init__(
            mobject,
            lambda: animation_copy(mobject).move_to(function(mobject.get_center())),
            **kwargs,
        )


class ApplyMatrix(ApplyPointwiseFunction):
    def __init__(self, matrix, mobject, *, about_point=ORIGIN, run_time=3.0, **kwargs):
        matrix = np.asarray(matrix, dtype=np.float64)
        if matrix.shape == (2, 2):
            full = np.eye(3)
            full[:2, :2] = matrix
            matrix = full
        if matrix.shape != (3, 3):
            raise ValueError(f"ApplyMatrix needs a 2x2 or 3x3 matrix, got {matrix.shape}")
        origin = np.asarray(about_point, dtype=np.float32)

        def function(point):
            relative = point.astype(np.float64) - origin.astype(np.float64)
            return apply_matrix_rows(relative, matrix).astype(np.float32) + origin

        super().__init__(function, mobject, run_time=run_time, **kwargs)


class ApplyComplexFunction(ApplyPointwiseFunction):
    def __init__(self, function, mobject, **kwargs):
        def point_function(point):
            value = function(complex(float(point[0]), float(point[1])))
            return np.array((value.real, value.imag, point[2]), dtype=np.float32)

        super().__init__(point_function, mobject, **kwargs)


class ApplyFunction(Transform):
    def __init__(self, function, mobject, **kwargs):
        target = function(animation_copy(mobject))
        if not isinstance(target, Mobject):
            raise TypeError("ApplyFunction's function must return a Mobject")
        super().__init__(mobject, target, **kwargs)


class ApplyMethod(_FunctionalTransform):
    def __init__(self, method, *args, **kwargs):
        mob = getattr(method, "__self__", None)
        if not isinstance(mob, Mobject):
            raise TypeError("ApplyMethod needs a bound Mobject method")
        has_method_kwargs = bool(args) and isinstance(args[-1], dict)
        method_kwargs = args[-1] if has_method_kwargs else {}
        args = args[:-1] if has_method_kwargs else args

        def target():
            result = animation_copy(mob)
            result.saved_state = mob.saved_state
            getattr(result, method.__name__)(*args, **method_kwargs)
            return result

        super().__init__(mob, target, **kwargs)
