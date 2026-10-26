"""Rotation and motion along a path, preserving snapshot boundaries."""

from janim.constants import ORIGIN, OUT, PI, TAU
from janim.core.transforms import point3
from janim.core.mobject import VMobject
from janim.core.rates import linear, smooth
from .animation import Animation, clip
from .composition import AnimationGroup


class Rotating(Animation):
    def __init__(
        self,
        mobject,
        angle=TAU,
        *,
        axis=OUT,
        about_point=None,
        about_edge=ORIGIN,
        rate_func=linear,
        run_time=5.0,
        **kwargs,
    ):
        super().__init__(mobject, rate_func=rate_func, run_time=run_time, **kwargs)
        self.angle = float(angle)
        self.axis = point3(axis)
        self.about_point = about_point
        self.about_edge = about_edge

    def interpolate_mobject(self, alpha):
        for mob, start in self.families:
            if isinstance(mob, VMobject) and isinstance(start, VMobject):
                mob.set_points(start.points)
            elif mob.has_points() and start.has_points():
                # A surface, a dot cloud or an image: GL restores EVERY member with
                # points before rotating (rotation.py:31), so a Cube under Rotate
                # does not accumulate the turn frame after frame. Every point array
                # moves together: a mesh's normals too.
                for destination, source in zip(mob._point_arrays(), start._point_arrays()):
                    destination[:] = source
                mob.note_changed_data()
        angle = self.get_sub_alpha(alpha, 0, max(len(self.families), 1)) * self.angle
        pivot = self.starting_mobject.get_bounding_box_point(self.about_edge) if self.about_point is None else self.about_point
        self.mobject.rotate(angle, axis=self.axis, about_point=pivot)


class Rotate(Rotating):
    def __init__(self, mobject, angle=PI, *, rate_func=smooth, run_time=1.0, **kwargs):
        super().__init__(mobject, angle, rate_func=rate_func, run_time=run_time, **kwargs)


class MoveAlongPath(Animation):
    def __init__(self, mobject, path, **kwargs):
        super().__init__(mobject, **kwargs)
        self.path = path

    def interpolate_mobject(self, alpha):
        self.mobject.move_to(self.path.quick_point_from_proportion(self.rate_func(clip(alpha))))


class ClockPassesTime(AnimationGroup):
    """Turn a `Clock`'s hands through `hours_passed` hours (GL's).

    The hands are `clock.hour_hand` and `clock.minute_hand`, turned about the
    clock's centre at the moment the animation is built; play adds the whole
    clock, as GL's `group=clock` does.
    """

    def __init__(self, clock, *, run_time=5.0, hours_passed=12.0, rate_func=linear, **kwargs):
        hour_hand = getattr(clock, "hour_hand", None)
        minute_hand = getattr(clock, "minute_hand", None)
        if hour_hand is None or minute_hand is None:
            raise TypeError("ClockPassesTime needs a Clock: a mobject with hour_hand and minute_hand")
        center = clock.get_center().copy()
        hour_radians = -float(hours_passed) * TAU / 12
        super().__init__(
            Animation(clock, run_time=run_time),
            Rotating(hour_hand, hour_radians, axis=OUT, about_point=center),
            Rotating(minute_hand, 12 * hour_radians, axis=OUT, about_point=center),
            run_time=run_time,
            rate_func=rate_func,
            **kwargs,
        )
        self.clock = clock
