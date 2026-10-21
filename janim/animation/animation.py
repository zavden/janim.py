"""Four-act animation lifecycle with ManimGL's public API."""

import math

from janim.core.mobject import Mobject, VGroup
from janim.core.rates import smooth


def clip(value, low=0.0, high=1.0):
    return min(max(float(value), low), high)


def check_duration(value, fps, what="run_time"):
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{what} must be finite and nonnegative, got {value}")
    if not value * fps < 4.0e18:
        raise ValueError(f"{what}={value} at {fps} fps overflows the frame counter")
    return value


def families(*mobjects):
    members = [mob.get_family() for mob in mobjects]
    counts = [len(family) for family in members]
    if any(count != counts[0] for count in counts):
        raise ValueError(f"animation families do not match: {counts}")
    return list(zip(*members))


def animation_copy(mobject):
    """Keep Python's copy contract, then discard the internal box cache.

    Animation snapshots start with dirty boxes. A transformed cached
    center can differ by one float32 ulp from recomputing the same points;
    scaling a snapshot must use the latter without changing public copy().
    """
    result = mobject.copy()
    result.refresh_bounding_box(recurse_down=True, recurse_up=False)
    return result


class Animation:
    def __init__(
        self,
        mobject,
        *,
        run_time=1.0,
        rate_func=smooth,
        lag_ratio=0.0,
        remover=False,
        final_alpha_value=1.0,
        final_alpha=None,
        time_span=None,
        name=None,
        suspend_mobject_updating=False,
    ):
        if not isinstance(mobject, Mobject):
            raise TypeError("Animation requires a Mobject")
        if not callable(rate_func):
            raise TypeError("rate_func must be callable")
        self.mobject = mobject
        self.run_time = float(run_time)
        self.rate_func = rate_func
        self.lag_ratio = float(lag_ratio)
        self.remover = bool(remover)
        self.final_alpha_value = float(final_alpha_value if final_alpha is None else final_alpha)
        self.time_span = None if time_span is None else tuple(map(float, time_span))
        if self.time_span is not None:
            if len(self.time_span) != 2 or not all(math.isfinite(value) for value in self.time_span):
                raise ValueError("time_span must contain two finite times")
            if self.time_span[0] < 0 or self.time_span[1] <= self.time_span[0]:
                raise ValueError("time_span must have a nonnegative start and a later end")
        self.name = type(self).__name__ if name is None else str(name)
        self.starting_mobject = None
        self.families = []
        self.suspend_mobject_updating = bool(suspend_mobject_updating)
        self._resume_updating = False

    def _begin_updates(self):
        if self.suspend_mobject_updating:
            self._resume_updating = not self.mobject.updating_suspended
            self.mobject.suspend_updating()

    def _finish_updates(self):
        if self._resume_updating:
            self._resume_updating = False
            self.mobject.resume_updating()
        return self

    def begin(self):
        self.starting_mobject = self.create_starting_mobject()
        self.families = families(self.mobject, self.starting_mobject)
        self._begin_updates()
        self.interpolate(0.0)
        return self

    def create_starting_mobject(self):
        return animation_copy(self.mobject)

    def interpolate(self, alpha):
        self.interpolate_mobject(self.time_spanned_alpha(alpha))
        return self

    def interpolate_mobject(self, alpha):
        count = len(self.families)
        for index, pair in enumerate(self.families):
            self.interpolate_submobject(*pair, self.get_sub_alpha(alpha, index, count))

    def interpolate_submobject(self, submobject, starting_submobject, alpha):
        pass

    def get_sub_alpha(self, alpha, index, num_submobjects):
        total = (num_submobjects - 1) * self.lag_ratio + 1
        return self.rate_func(clip(float(alpha) * total - index * self.lag_ratio))

    def time_spanned_alpha(self, alpha):
        if self.time_span is None:
            return float(alpha)
        start, end = self.time_span
        return clip(float(alpha) * self.get_run_time() - start, 0, end - start) / (end - start)

    def finish(self):
        self.interpolate(self.final_alpha_value)
        return self._finish_updates()

    def clean_up_from_scene(self, stage):
        if self.is_remover():
            stage.remove(self.mobject)
        return self

    def is_remover(self):
        return self.remover

    def get_run_time(self):
        return self.run_time if self.time_span is None else max(self.run_time, self.time_span[1])

    def set_run_time(self, value):
        self.run_time = float(value)
        return self

    def get_rate_func(self):
        return self.rate_func

    def set_rate_func(self, function):
        if not callable(function):
            raise TypeError("rate_func must be callable")
        self.rate_func = function
        return self

    def update_rate_info(self, run_time=None, rate_func=None, lag_ratio=None):
        if run_time is not None:
            self.run_time = float(run_time)
        if rate_func is not None:
            self.set_rate_func(rate_func)
        if lag_ratio is not None:
            self.lag_ratio = float(lag_ratio)
        return self

    def update(self, alpha):
        return self.interpolate(alpha)

    def __str__(self):
        return self.name


class Wait(Animation):
    def __init__(self, duration=1.0, **kwargs):
        super().__init__(VGroup(), **{"run_time": duration, **kwargs})

    def clean_up_from_scene(self, stage):
        stage.remove(self.mobject)
        return self


def prepare_animation(proto):
    from .transform import _AnimationBuilder

    if isinstance(proto, _AnimationBuilder):
        return proto.build()
    if isinstance(proto, Animation):
        return proto
    raise TypeError(f"cannot convert {type(proto).__name__} to an Animation")


def turn_animation_into_updater(animation, *, cycle=False):
    animation = prepare_animation(animation)
    animation.begin()
    total = 0.0

    def update(mob, dt):
        nonlocal total
        duration = animation.get_run_time()
        ratio = total / duration if duration > 0 else 1.0
        alpha = ratio - math.floor(ratio) if cycle else clip(ratio)
        if not cycle and alpha >= 1:
            animation.finish()
            mob.remove_updater(update)
            return
        animation.interpolate(alpha)
        total += dt

    animation.mobject.add_updater(update)
    return animation.mobject
