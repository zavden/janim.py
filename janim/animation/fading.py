"""Fades restore their starting state; stage cleanup performs removal."""

import math

import numpy as np

from janim.core.mobject import VGroup, VMobject
from janim.core.rates import there_and_back
from .animation import Animation, animation_copy
from .transform import Transform, _FunctionalTransform


def faded_copy(mobject, shift, scale):
    result = animation_copy(mobject)
    if scale != 1:
        result.scale(scale)
    if np.any(shift != 0):
        result.shift(shift)
    result.set_opacity(0)
    return result


class FadeIn(Transform):
    def __init__(self, mobject, *, shift=(0, 0, 0), scale=1.0, **kwargs):
        if not math.isfinite(scale) or scale <= 0:
            raise ValueError(f"scale must be positive and finite, got {scale}")
        super().__init__(mobject, **kwargs)
        self.shift_vector = np.array(shift, dtype=np.float32)
        self.shift_vect = self.shift_vector          # ManimGL's name, read by scenes that subclass Fade
        self.scale_factor = float(scale)

    def create_target(self):
        return animation_copy(self.mobject)

    def create_starting_state(self):
        return faded_copy(self.mobject, -self.shift_vector, 1 / self.scale_factor)


class FadeOut(FadeIn):
    def __init__(self, mobject, **kwargs):
        super().__init__(mobject, **{"remover": True, "final_alpha_value": 0.0, **kwargs})

    def create_target(self):
        return faded_copy(self.mobject, self.shift_vector, self.scale_factor)

    def create_starting_state(self):
        return None


class FadeInFromPoint(_FunctionalTransform):
    def __init__(self, mobject, point, **kwargs):
        # This one starting state is constructed eagerly, unlike FadeIn.
        start = animation_copy(mobject).scale(1e-3).move_to(point).set_stroke(opacity=0).set_fill(opacity=0)
        super().__init__(mobject, lambda: animation_copy(mobject), lambda: start, **kwargs)


class FadeOutToPoint(_FunctionalTransform):
    def __init__(self, mobject, point, **kwargs):
        def make_target():
            return animation_copy(mobject).scale(1e-3).move_to(point).set_stroke(opacity=0).set_fill(opacity=0)

        super().__init__(
            mobject,
            make_target,
            **{"remover": True, "final_alpha_value": 0.0, **kwargs},
        )


class VFadeIn(Animation):
    def __init__(self, mobject, **kwargs):
        super().__init__(mobject, **kwargs)
        self.out = False

    def interpolate_mobject(self, alpha):
        count = len(self.families)
        for index, (mob, start) in enumerate(self.families):
            if not isinstance(mob, VMobject) or not isinstance(start, VMobject):
                continue
            alpha_value = self.get_sub_alpha(alpha, index, count)
            if self.out:
                alpha_value = 1 - alpha_value
            for name in ("stroke_rgba", "fill_rgba"):
                rows, source = getattr(mob, name), getattr(start, name)
                rows[:, :3] = source[:, :3]
                rows[:, 3] = np.float32(alpha_value) * source[:, 3]
            mob._data_has_changed = True


class VFadeOut(VFadeIn):
    def __init__(self, mobject, **kwargs):
        super().__init__(mobject, **{"remover": True, "final_alpha_value": 0.0, **kwargs})
        self.out = True


class VFadeInThenOut(VFadeIn):
    def __init__(self, mobject, **kwargs):
        super().__init__(
            mobject,
            **{"rate_func": there_and_back, "remover": True, "final_alpha_value": 0.5, **kwargs},
        )


def ghost_to(source, target, *, stretch, dim_to_match):
    if not target.has_points() and not target.submobjects:
        source.scale(0)
    else:
        if stretch:
            for dimension in range(3):
                source.rescale_to_fit(target.length_over_dim(dimension), dimension, stretch=True)
        else:
            source.rescale_to_fit(target.length_over_dim(dim_to_match), dim_to_match)
        source.shift(target.get_center() - source.get_center())
    source.set_fill(opacity=0).set_stroke(opacity=0)


class FadeTransform(_FunctionalTransform):
    def __init__(self, mobject, target_mobject, *, stretch=True, dim_to_match=1, pieces=False, **kwargs):
        if dim_to_match not in (0, 1, 2):
            raise ValueError("dim_to_match must be 0, 1 or 2")
        mobject.save_state()
        mobject.saved_state.refresh_bounding_box(recurse_down=True, recurse_up=False)
        source, target = animation_copy(mobject), animation_copy(target_mobject)
        if pieces:
            source.align_data(target)
        group = VGroup(source, target)

        def ghost(first, second):
            pairs = zip(first.get_family(), second.get_family()) if pieces else [(first, second)]
            for start, end in pairs:
                ghost_to(start, end, stretch=stretch, dim_to_match=dim_to_match)

        def make_start():
            first, second = animation_copy(source), animation_copy(target)
            ghost(second, first)
            return VGroup(first, second)

        def make_target():
            first, second = animation_copy(source), animation_copy(target)
            ghost(first, second)
            return VGroup(first, second)

        super().__init__(group, make_target, make_start, **kwargs)
        self.source = mobject
        self.real_target = target_mobject

    def begin(self):
        self.source.set_opacity(0)
        return super().begin()

    def clean_up_from_scene(self, stage):
        stage.remove(self.mobject)
        self.source.restore()
        if self.remover:
            stage.remove(self.source)
        else:
            stage.replace(self.source, self.real_target)
        return self


class FadeTransformPieces(FadeTransform):
    def __init__(self, mobject, target_mobject, **kwargs):
        super().__init__(mobject, target_mobject, pieces=True, **kwargs)
