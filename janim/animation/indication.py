"""Attention gestures composed from snapshots, partial paths and fades."""

import math
import operator

import numpy as np

from janim.constants import FRAME_X_RADIUS, FRAME_Y_RADIUS, GREY_C, ORIGIN, SMALL_BUFF, TAU, YELLOW
from janim.core.annotations import SurroundingRectangle
from janim.core.mobject import Mobject, VGroup, VMobject
from janim.core.rates import linear, smooth, squish_rate_func, there_and_back
from janim.core.shapes import Circle, Dot, Line
from .animation import Animation, clip
from .composition import AnimationGroup
from .fading import FadeIn
from .passing import ShowCreationThenDestruction, ShowCreationThenFadeOut, ShowPassingFlash, VShowPassingFlash
from .transform import _FunctionalTransform


class Indicate(_FunctionalTransform):
    def __init__(self, mobject, *, scale_factor=1.2, color=YELLOW, rate_func=there_and_back, **kwargs):
        from .animation import animation_copy

        super().__init__(
            mobject,
            lambda: animation_copy(mobject).scale(scale_factor).set_color(color),
            rate_func=rate_func,
            **kwargs,
        )


class FocusOn(_FunctionalTransform):
    def __init__(self, target, *, opacity=0.2, color=GREY_C, run_time=2.0, **kwargs):
        center = target.get_center() if isinstance(target, Mobject) else np.asarray(target, dtype=np.float32)

        def disc(radius, alpha):
            return Dot(center, radius=radius).set_stroke(width=0, opacity=0).set_fill(color=color, opacity=alpha)

        def start():
            return disc(FRAME_X_RADIUS + FRAME_Y_RADIUS, 0)

        super().__init__(start(), lambda: disc(0, opacity), start, run_time=run_time, **{"remover": True, **kwargs})


class Flash(AnimationGroup):
    def __init__(
        self,
        target,
        *,
        color=YELLOW,
        line_length=0.2,
        num_lines=12,
        flash_radius=0.3,
        line_stroke_width=3.0,
        run_time=1.0,
        **kwargs,
    ):
        center = target.get_center() if isinstance(target, Mobject) else np.asarray(target, dtype=np.float32)
        lines = []
        for index in range(operator.index(num_lines)):
            angle = index * TAU / num_lines
            direction = np.array((math.cos(angle), math.sin(angle), 0), dtype=np.float32)
            line = Line(center + np.float32(flash_radius) * direction, center + np.float32(flash_radius + line_length) * direction)
            lines.append(line.set_stroke(color=color, width=line_stroke_width))
        super().__init__(*(ShowCreationThenFadeOut(line, run_time=run_time) for line in lines), run_time=run_time, **kwargs)
        self.mobject = VGroup(*lines)
        self.remover = True


class Circumscribe(ShowCreationThenFadeOut):
    def __init__(self, mobject, *, shape="rectangle", buff=0.1, color=YELLOW, stroke_width=2.0, run_time=1.0, **kwargs):
        if shape == "rectangle":
            outline = SurroundingRectangle(mobject, buff=buff, color=color, stroke_width=stroke_width)
        elif shape == "circle" or shape is Circle:
            diagonal = np.float32(math.hypot(float(mobject.get_width()), float(mobject.get_height())))
            outline = Circle(radius=0.5 * float(diagonal) + buff)
            outline.set_stroke(color=color, width=stroke_width).set_fill(opacity=0)
            outline.move_to(mobject.get_center())
        else:
            raise ValueError("Circumscribe shape must be rectangle or circle")
        super().__init__(outline, run_time=run_time, **kwargs)
        self.mobject = outline
        self.remover = True


class Wiggle(Animation):
    def __init__(self, mobject, *, scale_value=1.1, rotation_angle=0.01 * TAU, n_wiggles=6, run_time=2.0, rate_func=linear, **kwargs):
        super().__init__(mobject, run_time=run_time, rate_func=rate_func, **kwargs)
        self.scale_value = float(scale_value)
        self.rotation_angle = float(rotation_angle)
        self.n_wiggles = operator.index(n_wiggles)

    def interpolate_mobject(self, alpha):
        for mob, start in self.families:
            if isinstance(mob, VMobject) and isinstance(start, VMobject):
                mob.set_points(start.points)
        alpha = self.rate_func(clip(alpha))
        center = self.starting_mobject.get_bounding_box_point(ORIGIN)
        self.mobject.scale(1 + (self.scale_value - 1) * there_and_back(alpha), about_point=center)
        self.mobject.rotate(self.rotation_angle * math.sin(self.n_wiggles * math.pi * alpha), about_point=center)


class ShowPassingFlashWithThinningStrokeWidth(AnimationGroup):
    """Several passing flashes of copies, thick and short to thin and long (CE's).

    The copies get stroke widths from 0 to the mobject's and time widths
    from `time_width` down to 0, as in CE; the copy with time width 0 draws
    nothing there and cannot be built here, so it is left out.
    `remover` is CE's signature only: every flash removes its copy.
    """

    def __init__(self, vmobject, *, n_segments=10, time_width=0.1, remover=True, **kwargs):
        n_segments = operator.index(n_segments)
        if n_segments < 1:
            raise ValueError("ShowPassingFlashWithThinningStrokeWidth needs at least one segment")
        self.n_segments = n_segments
        self.time_width = float(time_width)
        max_stroke_width = vmobject.get_stroke_width()
        flashes = [
            ShowPassingFlash(
                vmobject.copy().set_stroke(width=float(stroke_width)),
                time_width=float(width),
                **kwargs,
            )
            for stroke_width, width in zip(
                np.linspace(0, max_stroke_width, n_segments),
                np.linspace(self.time_width, 0, n_segments),
            )
            if width > 0
        ]
        if not flashes:
            raise ValueError("every segment has a time width of 0; give n_segments > 1 or a positive time_width")
        super().__init__(*flashes)


class FlashyFadeIn(AnimationGroup):
    """Fade in while a flash runs along the outline (GL's)."""

    def __init__(self, vmobject, *, stroke_width=2.0, fade_lag=0.0, time_width=1.0, **kwargs):
        outline = vmobject.copy()
        outline.set_fill(opacity=0)
        outline.set_stroke(width=stroke_width, opacity=1)
        rate_func = kwargs.get("rate_func", smooth)
        super().__init__(
            FadeIn(vmobject, rate_func=squish_rate_func(rate_func, fade_lag, 1)),
            VShowPassingFlash(outline, time_width=time_width),
            **kwargs,
        )


class AnimationOnSurroundingRectangle(AnimationGroup):
    """Run `RectAnimationType` on a rectangle around the mobject (GL's).

    The rectangle is placed on the mobject again when the animation begins.
    GL attaches `move_to(mobject)` to it as an updater instead, which in
    ManimGL 1.7.2 recentres the PARTIAL path on the mobject every frame
    (measured), so its flash runs through the middle; here the rectangle
    does not follow a mobject that moves during the animation.
    """

    RectAnimationType = Animation

    def __init__(self, mobject, *, stroke_width=2.0, stroke_color=YELLOW, buff=SMALL_BUFF, **kwargs):
        self.surrounded = mobject
        self.rectangle = SurroundingRectangle(
            mobject,
            buff=buff,
            color=stroke_color,
            stroke_width=stroke_width,
        )
        super().__init__(self.RectAnimationType(self.rectangle, **kwargs))

    def begin(self):
        self.rectangle.move_to(self.surrounded)
        return super().begin()


class ShowPassingFlashAround(AnimationOnSurroundingRectangle):
    RectAnimationType = ShowPassingFlash


class ShowCreationThenDestructionAround(AnimationOnSurroundingRectangle):
    RectAnimationType = ShowCreationThenDestruction


class ShowCreationThenFadeAround(AnimationOnSurroundingRectangle):
    RectAnimationType = ShowCreationThenFadeOut
