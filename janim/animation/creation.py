"""Partial paths, borrowed outlines and growth."""

from janim.constants import PI, TAU
import numpy as np

from janim.core.bezier import integer_interpolate
from janim.core.mobject import VMobject
from janim.core.rates import double_smooth, linear, smooth
from .animation import Animation, animation_copy, clip, families
from .transform import _FunctionalTransform


class ShowCreation(Animation):
    def __init__(self, mobject, **kwargs):
        super().__init__(mobject, **{"lag_ratio": 1.0, **kwargs})

    def interpolate_submobject(self, submobject, starting_submobject, alpha):
        if isinstance(submobject, VMobject):
            submobject.pointwise_become_partial(starting_submobject, 0, alpha)

    def finish(self):
        super().finish()
        if self.remover and self.starting_mobject is not None:
            self.mobject.become(self.starting_mobject)
        return self


Create = ShowCreation


def _restore_family(mobject, start, opacity_factor=1.0):
    """Copy points and colours back from the snapshot, scaling every alpha."""
    factor = np.float32(opacity_factor)
    for mob, source in zip(mobject.get_family(), start.get_family()):
        if isinstance(mob, VMobject) and isinstance(source, VMobject):
            mob.set_points(source.points)
            for name in ("fill_rgba", "stroke_rgba"):
                rows, before = getattr(mob, name), getattr(source, name)
                count = min(len(rows), len(before))
                rows[:count] = before[:count]
                if factor != 1:
                    rows[:count, 3] *= factor
            mob._data_has_changed = True
        elif mob.has_points() and source.has_points():
            for destination, origin in zip(mob._point_arrays(), source._point_arrays()):
                destination[:] = origin
            mob.note_changed_data()


class SpiralIn(Animation):
    """Fly every child in from far out on a spiral, fading in (CE's).

    Each child starts `scale_factor` times as far from the group's centre as
    it ends, turns once around that centre while it keeps its orientation,
    and reaches its full opacity after `fade_in_fraction` of the animation.
    A mobject without children flies in as one piece. Unlike CE, nothing is
    moved when the animation is built: the start is computed in `begin`.
    Only vector members fade; a surface or an image only flies.
    """

    def __init__(self, shapes, *, scale_factor=8.0, fade_in_fraction=0.3, **kwargs):
        if fade_in_fraction < 0:
            raise ValueError("fade_in_fraction must be nonnegative")
        super().__init__(shapes, **kwargs)
        self.scale_factor = float(scale_factor)
        self.fade_in_fraction = float(fade_in_fraction)
        self.shape_center = None

    def begin(self):
        self.shape_center = self.mobject.get_center().copy()
        return super().begin()

    def _pairs(self):
        shapes = self.mobject.submobjects or [self.mobject]
        starts = self.starting_mobject.submobjects or [self.starting_mobject]
        return zip(shapes, starts)

    def interpolate_mobject(self, alpha):
        alpha = self.rate_func(clip(alpha))
        center = self.shape_center
        fade = 1.0 if self.fade_in_fraction == 0 else min(1.0, alpha / self.fade_in_fraction)
        for shape, start in self._pairs():
            _restore_family(shape, start, fade)
            final = start.get_center()
            shape.shift((final - center) * self.scale_factor * (1.0 - alpha))
            shape.rotate(TAU * alpha, about_point=center)
            shape.rotate(-TAU * alpha, about_point=shape.get_center_of_mass())

    def finish(self):
        if self.final_alpha_value == 1.0 and self.starting_mobject is not None:
            # a whole turn leaves float residue; the end state is the snapshot
            for shape, start in self._pairs():
                _restore_family(shape, start)
            return self._finish_updates()
        return super().finish()


class Uncreate(ShowCreation):
    def __init__(self, mobject, *, rate_func=smooth, **kwargs):
        super().__init__(mobject, **{"rate_func": lambda t: rate_func(1 - t), "remover": True, **kwargs})


class DrawBorderThenFill(Animation):
    def __init__(
        self,
        mobject,
        *,
        stroke_width=2.0,
        stroke_color=None,
        run_time=2.0,
        rate_func=double_smooth,
        reverse_lag=False,
        **kwargs,
    ):
        if not isinstance(mobject, VMobject):
            raise TypeError("DrawBorderThenFill needs a VMobject with vector geometry")
        super().__init__(mobject, run_time=run_time, rate_func=rate_func, **kwargs)
        self.stroke_width = float(stroke_width)
        self.stroke_color = stroke_color
        self.reverse_lag = bool(reverse_lag)
        self.outline = None

    def begin(self):
        colors = [mob.get_color() if isinstance(mob, VMobject) and mob.has_points() else None for mob in self.mobject.get_family()]
        self.outline = animation_copy(self.mobject).set_fill(opacity=0)
        for mob, color in zip(self.outline.get_family(), colors):
            if color is not None and isinstance(mob, VMobject):
                mob.set_stroke(
                    color=color if self.stroke_color is None else self.stroke_color,
                    width=self.stroke_width,
                    opacity=1,
                    recurse=False,
                )
        self.starting_mobject = animation_copy(self.mobject)
        self.families = families(self.mobject, self.starting_mobject, self.outline)
        self._begin_updates()
        self.interpolate(0.0)
        return self

    def interpolate_mobject(self, alpha):
        count = len(self.families)
        for index, (mob, start, outline) in enumerate(self.families):
            if not all(isinstance(item, VMobject) for item in (mob, start, outline)):
                continue
            index = count - 1 - index if self.reverse_lag else index
            half, partial = integer_interpolate(0, 2, self.get_sub_alpha(alpha, index, count))
            if half == 0:
                mob.pointwise_become_partial(outline, 0, partial)
                for name in ("stroke_rgba", "fill_rgba", "stroke_width"):
                    getattr(mob, name)[:] = getattr(outline, name)
            else:
                mob.interpolate(outline, start, partial)

    def finish(self):
        super().finish()
        if self.remover and self.starting_mobject is not None:
            self.mobject.become(self.starting_mobject)
        return self


class Write(DrawBorderThenFill):
    def __init__(self, mobject, *, run_time=-1.0, lag_ratio=-1.0, rate_func=linear, **kwargs):
        count = sum(isinstance(mob, VMobject) and mob.has_points() for mob in mobject.get_family())
        super().__init__(
            mobject,
            run_time=(1.0 if count < 15 else 2.0) if run_time < 0 else run_time,
            lag_ratio=min(4.0 / (count + 1.0), 0.2) if lag_ratio < 0 else lag_ratio,
            rate_func=rate_func,
            **kwargs,
        )


class Unwrite(Write):
    def __init__(self, mobject, *, rate_func=linear, reverse=True, **kwargs):
        super().__init__(
            mobject,
            **{"rate_func": lambda t: rate_func(1 - t), "remover": True, "reverse_lag": reverse, **kwargs},
        )


class GrowFromPoint(_FunctionalTransform):
    def __init__(self, mobject, point, *, point_color=None, **kwargs):
        def make_start():
            start = animation_copy(mobject).scale(0).move_to(point)
            if point_color is not None:
                start.set_color(point_color)
            return start

        super().__init__(mobject, lambda: animation_copy(mobject), make_start, **kwargs)


class GrowFromCenter(GrowFromPoint):
    def __init__(self, mobject, **kwargs):
        super().__init__(mobject, mobject.get_center(), **kwargs)


class GrowFromEdge(GrowFromPoint):
    def __init__(self, mobject, edge, **kwargs):
        super().__init__(mobject, mobject.get_bounding_box_point(edge), **kwargs)


class GrowArrow(GrowFromPoint):
    def __init__(self, mobject, **kwargs):
        super().__init__(mobject, mobject.get_start(), **kwargs)


class SpinInFromNothing(GrowFromCenter):
    def __init__(self, mobject, *, angle=PI, **kwargs):
        super().__init__(mobject, path_arc=angle, **kwargs)


class ShrinkToCenter(_FunctionalTransform):
    def __init__(self, mobject, **kwargs):
        super().__init__(mobject, lambda: animation_copy(mobject).scale(0), **kwargs)


class UpdateFromAlphaFunc(Animation):
    def __init__(self, mobject, update_function, **kwargs):
        super().__init__(mobject, **kwargs)
        self.update_function = update_function

    def begin(self):
        self._begin_updates()
        self.interpolate(0.0)
        return self

    def interpolate_mobject(self, alpha):
        self.update_function(self.mobject, self.rate_func(clip(alpha)))


class UpdateFromFunc(UpdateFromAlphaFunc):
    def interpolate_mobject(self, alpha):
        self.update_function(self.mobject)
