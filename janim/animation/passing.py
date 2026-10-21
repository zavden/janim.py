"""Moving path windows and appearance sequences."""

from janim.constants import YELLOW
from janim.core.annotations import SurroundingRectangle, Underline
from janim.core.mobject import VMobject
from janim.core.rates import there_and_back
from .animation import Animation, animation_copy, clip
from .composition import Succession
from .creation import ShowCreation
from .fading import FadeOut
from .transform import _FunctionalTransform


class VShowPassingFlash(Animation):
    def __init__(self, mobject, *, time_width=0.3, **kwargs):
        if not 0 < time_width <= 1:
            raise ValueError("time_width must be a fraction in (0, 1]")
        super().__init__(mobject, **{"remover": True, **kwargs})
        self.time_width = float(time_width)

    def interpolate_submobject(self, submobject, starting_submobject, alpha):
        if not isinstance(submobject, VMobject) or not starting_submobject.has_points():
            return
        upper = alpha * (1 + self.time_width)
        submobject.pointwise_become_partial(starting_submobject, clip(upper - self.time_width), clip(upper))

    def finish(self):
        if self.starting_mobject is not None:
            self.mobject.become(self.starting_mobject)
        return self._finish_updates()


ShowPassingFlash = VShowPassingFlash


class FlashAround(VShowPassingFlash):
    def __init__(self, mobject, *, buff=0.05, color=YELLOW, stroke_width=4.0, time_width=0.4, **kwargs):
        outline = SurroundingRectangle(mobject, buff=buff)
        outline.set_stroke(color=color, width=stroke_width).set_fill(opacity=0)
        super().__init__(outline, time_width=time_width, **kwargs)


class FlashUnder(VShowPassingFlash):
    def __init__(self, mobject, *, buff=0.1, color=YELLOW, stroke_width=4.0, time_width=0.4, **kwargs):
        super().__init__(
            Underline(mobject, buff=buff, color=color, stroke_width=stroke_width),
            time_width=time_width,
            **kwargs,
        )


class ShowCreationThenDestruction(ShowCreation):
    def __init__(self, mobject, **kwargs):
        super().__init__(mobject, **{"rate_func": there_and_back, **kwargs})


class ShowCreationThenFadeOut(Succession):
    def __init__(self, mobject, *, run_time=1.0, **kwargs):
        half = float(run_time) / 2
        super().__init__(ShowCreation(mobject, run_time=half), FadeOut(mobject, run_time=half), **kwargs)


class TurnInsideOut(_FunctionalTransform):
    def __init__(self, mobject, **kwargs):
        if not isinstance(mobject, VMobject):
            raise TypeError("TurnInsideOut requires a VMobject")
        super().__init__(mobject, lambda: animation_copy(mobject).set_points(mobject.points[::-1]), **kwargs)
