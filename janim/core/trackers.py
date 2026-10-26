"""Numeric state, redraw updaters and trails."""

import math

import numpy as np

from janim.constants import BLUE_B, BLUE_D, BLUE_E, GREY_BROWN, WHITE
from .mobject import Mobject, VGroup, VMobject
from .rates import smooth


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


class ExponentialValueTracker(ValueTracker):
    """A `ValueTracker` that stores log(value), so it moves geometrically (GL's).

    Halfway between 1 and 100 it reads 10. The value must stay positive.
    ManimGL 1.7.2 stores its constructor's argument AS the logarithm
    (`ExponentialValueTracker(5).get_value()` is e⁵ there, measured); here
    the constructor takes the value, as `set_value` does.
    """

    def __init__(self, value=1.0):
        super().__init__(0.0)
        self.set_value(value)

    def get_value(self):
        from janim.math import exp

        return exp(self.value)

    def set_value(self, value):
        from janim.math import log

        value = float(value)
        if not value > 0:
            raise ValueError(f"an ExponentialValueTracker holds positive values, got {value}")
        self.value = log(value)
        return self

    def increment_value(self, value):
        return self.set_value(self.get_value() + value)


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


class AnimatedBoundary(VGroup):
    """A boundary that draws itself around `vmobject` in cycling colours (GL's).

    Two stroke-only copies of the outline: one grows (and, with
    `back_and_forth`, shrinks back every other cycle) in the current colour
    while the other fades out in the previous one. It runs on its own
    updater, `cycle_rate` cycles per second.
    """

    def __init__(
        self,
        vmobject,
        colors=(BLUE_D, BLUE_B, BLUE_E, GREY_BROWN),
        max_stroke_width=3.0,
        cycle_rate=0.5,
        back_and_forth=True,
        draw_rate_func=smooth,
        fade_rate_func=smooth,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if not colors:
            raise ValueError("AnimatedBoundary needs at least one colour")
        self.vmobject = vmobject
        self.colors = list(colors)
        self.max_stroke_width = float(max_stroke_width)
        self.cycle_rate = float(cycle_rate)
        self.back_and_forth = bool(back_and_forth)
        self.draw_rate_func = draw_rate_func
        self.fade_rate_func = fade_rate_func
        self.boundary_copies = [
            vmobject.copy().set_stroke(width=0).set_fill(opacity=0)
            for _ in range(2)
        ]
        self.add(*self.boundary_copies)
        self.total_time = 0.0
        self.add_updater(lambda mob, dt: mob.update_boundary_copies(dt))

    def update_boundary_copies(self, dt):
        time = self.total_time * self.cycle_rate
        growing, fading = self.boundary_copies
        colors = self.colors
        width = self.max_stroke_width
        index = int(time % len(colors))
        alpha = time % 1
        draw_alpha = self.draw_rate_func(alpha)
        fade_alpha = self.fade_rate_func(alpha)
        if self.back_and_forth and int(time) % 2 == 1:
            bounds = (1 - draw_alpha, 1)
        else:
            bounds = (0, draw_alpha)
        self.full_family_become_partial(growing, self.vmobject, *bounds)
        growing.set_stroke(colors[index], width=width)
        if time >= 1:
            self.full_family_become_partial(fading, self.vmobject, 0, 1)
            fading.set_stroke(colors[index - 1], width=(1 - fade_alpha) * width)
        self.total_time += dt
        return self

    def full_family_become_partial(self, first, second, a, b):
        pairs = zip(first.family_members_with_points(), second.family_members_with_points())
        for target, source in pairs:
            target.pointwise_become_partial(source, a, b)
        return self
