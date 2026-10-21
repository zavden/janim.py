"""Numeric state, redraw updaters and trails."""

import math

import numpy as np

from janim.constants import WHITE
from .mobject import Mobject, VMobject


class ValueTracker(Mobject):
    is_interpolable = True
    value_type = float

    def __init__(self, value=0.0):
        super().__init__()
        self.value = self.value_type(value)

    def get_value(self):
        return self.value

    def set_value(self, value):
        self.value = self.value_type(value)
        return self

    def increment_value(self, value):
        return self.set_value(self.value + value)

    def align_data(self, other, **kwargs):
        return self

    def interpolate(self, first, second, alpha, **kwargs):
        self.value = first.value + float(alpha) * (second.value - first.value)
        return self

    def become(self, other, **kwargs):
        return self.set_value(other.get_value())


class ComplexValueTracker(ValueTracker):
    value_type = complex

    def __init__(self, value=0j):
        super().__init__(value)


def always_redraw(factory, *args, **kwargs):
    mob = factory(*args, **kwargs)
    if not isinstance(mob, Mobject):
        raise TypeError("always_redraw must construct a Mobject")
    mob.add_updater(lambda current: current.become(factory(*args, **kwargs)), call=False)
    return mob


class TracedPath(VMobject):
    def __init__(
        self,
        point_func,
        *,
        stroke_color=WHITE,
        stroke_width=2.0,
        stroke_opacity=1.0,
        time_traced=math.inf,
        time_per_anchor=None,
        smooth=False,
        **kwargs,
    ):
        # ManimGL 1.7 declares `time_per_anchor` and never reads it in
        # `update_path`: accepted here for verbatim scenes, with the same effect.
        self.time_per_anchor = time_per_anchor
        super().__init__(
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            stroke_opacity=stroke_opacity,
            **kwargs,
        )
        self.set_fill(opacity=0)
        seen = []

        def trace(mob, dt):
            if dt == 0:
                return
            seen.append(np.array(point_func(), dtype=np.float32))
            points = seen
            if math.isfinite(time_traced):
                relevant = max(2, round(float(time_traced) / dt))
                if len(seen) > relevant:
                    if len(seen) > 10 * relevant:
                        del seen[:-relevant]
                    points = seen[-relevant:]
            if len(points) >= 2:
                mob.set_points_as_corners(points)
                if smooth:
                    mob.make_smooth()
            else:
                mob.set_points([points[0], points[0], points[0]])

        self.add_updater(trace)


class _UpdaterBuilder:
    def __init__(self, mobject, *, functional=False):
        self.mobject = mobject
        self.functional = functional

    def __getattr__(self, name):
        if not callable(getattr(self.mobject, name)):
            raise TypeError(f"updater target {name} must be a method")

        def register(*args, **kwargs):
            if self.functional:
                def update(mob):
                    return getattr(mob, name)(
                        *(value() for value in args),
                        **{key: value() for key, value in kwargs.items()},
                    )
            else:
                def update(mob):
                    return getattr(mob, name)(*args, **kwargs)
            self.mobject.add_updater(update)
            return self

        return register
