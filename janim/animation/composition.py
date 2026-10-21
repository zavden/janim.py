"""ManimGL time windows and lazy, equally sliced succession."""

from janim.core.bezier import integer_interpolate
from janim.core.mobject import Group, VGroup, VMobject
from .animation import Animation, clip, prepare_animation


class AnimationGroup(Animation):
    """Distribute raw time; time_span and suspension apply only to children.

    Like ManimGL's composition overrides, this lifecycle does not use the
    base animation's time-span remapping or updater suspension.
    """
    def __init__(self, *animations, lag_ratio=0.0, run_time=-1.0, **kwargs):
        self.animations = [prepare_animation(anim) for anim in animations]
        self.anims_with_timings = []
        time = 0.0
        for anim in self.animations:
            end = time + anim.get_run_time()
            self.anims_with_timings.append((anim, time, end))
            time = time + float(lag_ratio) * (end - time)
        self.max_end_time = max((end for _, _, end in self.anims_with_timings), default=0.0)
        mobs = [anim.mobject for anim in self.animations]
        group = VGroup(*mobs) if all(isinstance(mob, VMobject) for mob in mobs) else Group(*mobs)
        super().__init__(
            group,
            lag_ratio=lag_ratio,
            run_time=self.max_end_time if run_time < 0 else run_time,
            **kwargs,
        )

    def begin(self):
        for anim in self.animations:
            anim.begin()
        self.interpolate(0.0)
        return self

    def interpolate(self, alpha):
        time = float(alpha) * self.max_end_time
        for anim, start, end in self.anims_with_timings:
            duration = end - start
            anim.interpolate(0.0 if duration == 0 else clip((time - start) / duration))
        return self

    def finish(self):
        self.interpolate(1.0)
        for anim in self.animations:
            anim.finish()
        return self

    def clean_up_from_scene(self, stage):
        for anim in self.animations:
            anim.clean_up_from_scene(stage)
        return self


class LaggedStart(AnimationGroup):
    def __init__(self, *animations, lag_ratio=0.05, **kwargs):
        super().__init__(*animations, lag_ratio=lag_ratio, **kwargs)


class LaggedStartMap(LaggedStart):
    def __init__(self, animation_class, group, *, lag_ratio=0.05, run_time=2.0, **kwargs):
        children = list(group)
        if not children:
            raise ValueError("LaggedStartMap needs a group with children")
        super().__init__(
            *(animation_class(child, **kwargs) for child in children),
            lag_ratio=lag_ratio,
            run_time=run_time,
        )


class Succession(AnimationGroup):
    def __init__(self, *animations, **kwargs):
        super().__init__(*animations, **{"lag_ratio": 1.0, **kwargs})
        self.active = None

    def begin(self):
        if not self.animations:
            raise ValueError("Succession needs at least one animation")
        self.active = 0
        self.animations[0].begin()
        return self

    def interpolate(self, alpha):
        index, sub_alpha = integer_interpolate(0, len(self.animations), alpha)
        if index != self.active:
            self.animations[self.active].finish()
            self.animations[index].begin()
            self.active = index
        self.animations[index].interpolate(sub_alpha)
        return self

    def finish(self):
        if self.active is None:
            raise RuntimeError("Succession.finish requires begin first")
        self.animations[self.active].finish()
        return self


def leaf_animations(animation):
    if not isinstance(animation, AnimationGroup):
        return [animation]
    return [leaf for child in animation.animations for leaf in leaf_animations(child)]
