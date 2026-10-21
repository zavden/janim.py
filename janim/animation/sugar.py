"""Named transforms and subset reveals."""

import math
import operator

from janim.constants import ORIGIN, TAU, YELLOW
from janim.core.mobject import VGroup, VMobject
from janim.core.rates import linear
from janim.core.shapes import Circle
from .animation import Animation, animation_copy, clip
from .composition import LaggedStart, Succession
from .creation import ShowCreation, UpdateFromAlphaFunc
from .fading import FadeOut, VFadeIn, VFadeOut
from .transform import _FunctionalTransform


class FadeToColor(_FunctionalTransform):
    def __init__(self, mobject, color, **kwargs):
        super().__init__(mobject, lambda: animation_copy(mobject).set_color(color), **kwargs)


class ScaleInPlace(_FunctionalTransform):
    def __init__(self, mobject, scale_factor, **kwargs):
        super().__init__(mobject, lambda: animation_copy(mobject).scale(scale_factor), **kwargs)


class CyclicReplace(_FunctionalTransform):
    def __init__(self, *mobjects, path_arc=TAU / 4, **kwargs):
        if len(mobjects) < 2:
            raise ValueError("CyclicReplace needs at least two mobjects")
        group = VGroup(*mobjects)

        def target():
            result = animation_copy(group)
            centers = [mob.get_center() for mob in mobjects]
            cycled = centers[-1:] + centers[:-1]
            for mob, center in zip(result.submobjects, cycled):
                mob.move_to(center)
            return result

        super().__init__(group, target, path_arc=path_arc, **kwargs)


Swap = CyclicReplace


class CircleIndicate(Succession):
    def __init__(self, mobject, *, color=YELLOW, scale_factor=1.2, run_time=1.0, **kwargs):
        width, height = float(mobject.get_width()), float(mobject.get_height())
        circle = Circle(radius=0.5 * math.sqrt(width * width + height * height) * scale_factor)
        circle.set_stroke(color=color, width=3).set_fill(opacity=0).move_to(mobject.get_center())
        super().__init__(ShowCreation(circle, run_time=run_time / 2), FadeOut(circle, run_time=run_time / 2), **kwargs)


class Broadcast(LaggedStart):
    def __init__(
        self,
        mobject,
        *,
        focal_point=ORIGIN,
        n=5,
        initial_width=0.0,
        final_opacity=0.0,
        lag_ratio=0.2,
        run_time=3.0,
        **kwargs,
    ):
        n = operator.index(n)
        if n < 1:
            raise ValueError("Broadcast needs at least one ring")
        animations = []
        for _ in range(n):
            ring = animation_copy(mobject).move_to(focal_point)
            target = animation_copy(ring).set_stroke(opacity=final_opacity).set_fill(opacity=final_opacity)
            if initial_width > 0:
                ring.set_width(initial_width)
            else:
                ring.scale(1e-3)
            animations.append(_FunctionalTransform(ring, lambda target=target: target, remover=True, run_time=run_time / 2))
        super().__init__(*animations, lag_ratio=lag_ratio, run_time=run_time, **kwargs)


BroadcastRipple = Broadcast


class Blink(Succession):
    def __init__(self, mobject, *, times=1, run_time=1.0, **kwargs):
        times = operator.index(times)
        if times < 1:
            raise ValueError("Blink needs at least one blink")
        each = float(run_time) / (2 * times)
        animations = []
        for _ in range(times):
            animations.extend((VFadeOut(mobject, run_time=each, remover=False), VFadeIn(mobject, run_time=each)))
        super().__init__(*animations, **kwargs)


def set_visible(mobject, visible, saved):
    if not isinstance(mobject, VMobject):
        return
    reference = saved.get_family() if isinstance(saved, VMobject) else []
    for index, mob in enumerate(mobject.get_family()):
        if not isinstance(mob, VMobject):
            continue
        source = reference[index] if index < len(reference) and isinstance(reference[index], VMobject) else mob
        for name in ("stroke_rgba", "fill_rgba"):
            rows, before = getattr(mob, name), getattr(source, name)
            if visible:
                count = min(len(rows), len(before))
                rows[:count, 3] = before[:count, 3]
            else:
                rows[:, 3] = 0
        mob._data_has_changed = True


class ShowIncreasingSubsets(Animation):
    def __init__(self, group, *, one_at_a_time=False, rate_func=linear, **kwargs):
        children = list(group)
        if not children:
            raise ValueError("ShowIncreasingSubsets needs a group with children")
        super().__init__(group, rate_func=rate_func, **kwargs)
        self.children = children
        self.one_at_a_time = bool(one_at_a_time)
        self.saved = []

    def begin(self):
        self.starting_mobject = animation_copy(self.mobject)
        self.saved = [animation_copy(child) for child in self.children]
        self._begin_updates()
        self.interpolate(0.0)
        return self

    def interpolate_mobject(self, alpha):
        count = len(self.children)
        alpha = self.rate_func(clip(alpha))
        shown = min(max(math.ceil(alpha * count), 0), count)
        for index, child in enumerate(self.children):
            visible = index == max(shown, 1) - 1 if self.one_at_a_time else index < shown
            set_visible(child, visible, self.saved[index] if index < len(self.saved) else None)


def AddTextLetterByLetter(text, *, run_time=-1, time_per_char=0.06, **kwargs):
    """Type a text out one glyph at a time: `ShowIncreasingSubsets` over the glyphs (as CE's)."""
    count = len(text.submobjects)
    if count == 0:
        raise ValueError("that mobject has no glyphs to type — AddTextLetterByLetter wants a Text or a Tex, whose children are the glyphs")
    duration = max(0.5, count * float(time_per_char)) if run_time < 0 else float(run_time)
    return ShowIncreasingSubsets(text, run_time=duration, **kwargs)


def TypeWithCursor(text, cursor, *, run_time=-1, time_per_char=0.06, buff=0.1, **kwargs):
    """`AddTextLetterByLetter` with a cursor that follows the last glyph typed (as CE's)."""
    from janim.constants import RIGHT
    from .composition import AnimationGroup

    count = len(text.submobjects)
    if count == 0:
        raise ValueError("that mobject has no glyphs to type")
    duration = max(0.5, count * float(time_per_char)) if run_time < 0 else float(run_time)
    typing = AddTextLetterByLetter(text, run_time=duration, time_per_char=time_per_char, **kwargs)

    def chase(mob, alpha):
        index = min(max(math.ceil(alpha * count), 1), count)
        return mob.next_to(text.submobjects[index - 1], RIGHT, buff=buff)

    follow = UpdateFromAlphaFunc(cursor, chase, run_time=duration, rate_func=linear)
    return AnimationGroup(typing, follow, run_time=duration)


class ShowSubmobjectsOneByOne(ShowIncreasingSubsets):
    def __init__(self, group, **kwargs):
        super().__init__(group, **{"one_at_a_time": True, **kwargs})


class MaintainPositionRelativeTo(UpdateFromAlphaFunc):
    def __init__(self, mobject, tracked_mobject, **kwargs):
        offset = mobject.get_center() - tracked_mobject.get_center()
        super().__init__(mobject, lambda mob, alpha: mob.move_to(tracked_mobject.get_center() + offset), **kwargs)
