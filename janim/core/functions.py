"""Sampled parametric paths."""

import numpy as np

from ._ranges import step_range
from .mobject import VMobject
from .transforms import point3


class ParametricCurve(VMobject):
    def __init__(
        self,
        t_func,
        t_range=(0.0, 1.0, 0.1),
        epsilon=1e-8,
        discontinuities=(),
        use_smoothing=True,
        **kwargs,
    ):
        start, stop, step = map(float, t_range)
        if step <= 0:
            raise ValueError("ParametricCurve requires a positive t_range step")
        self.t_func = t_func
        self.t_range = (start, stop, step)
        self.epsilon = float(epsilon)
        self.discontinuities = list(discontinuities)
        self.use_smoothing = bool(use_smoothing)
        super().__init__(**kwargs)
        jumps = sorted(float(value) for value in discontinuities if start < value < stop)
        bounds = sorted(
            [start, stop, *(value - epsilon for value in jumps), *(value + epsilon for value in jumps)],
        )
        pieces = []
        for first, last in zip(bounds[::2], bounds[1::2]):
            times = step_range(first, last, step)
            if times and times[-1] >= last:
                times.pop()
            times.append(last)
            points = np.array([point3(t_func(time)) for time in times], dtype=np.float32)
            piece = np.empty((2 * len(points) - 1, 3), dtype=np.float32)
            piece[::2] = points
            piece[1::2] = (points[:-1] + points[1:]) / np.float32(2)
            if pieces:
                pieces.append(pieces[-1][-1:])
            pieces.append(piece)
        if pieces:
            self.set_points(np.concatenate(pieces))
        if use_smoothing:
            self.make_smooth()
        if not self.has_points():
            self.set_points([point3(t_func(start))])

    def get_point_from_function(self, time):
        return point3(self.t_func(time))

    def get_t_func(self):
        return self.t_func

    def get_function(self):
        return getattr(self, "function", self.t_func)


class FunctionGraph(ParametricCurve):
    def __init__(self, function, x_range=(-8.0, 8.0, 0.25), **kwargs):
        self.function = function
        self.x_range = tuple(x_range)
        super().__init__(lambda x: (x, function(x), 0), t_range=x_range, **kwargs)

    def get_x_range(self):
        return self.x_range
