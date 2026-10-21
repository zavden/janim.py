"""Line and arrow variants."""

import math

import numpy as np

from janim.constants import DEFAULT_SMALL_DOT_RADIUS, GREY_A, LEFT, ORIGIN, RIGHT
from .algebra import norm
from .mobject import VGroup
from .shapes import Arrow, Dot, Line, Polygon, endpoints
from .transforms import point3


class SmallDot(Dot):
    def __init__(self, point=ORIGIN, radius=DEFAULT_SMALL_DOT_RADIUS, **kwargs):
        super().__init__(point, radius, **kwargs)


class Vector(Arrow):
    def __init__(self, direction=RIGHT, buff=0.0, **kwargs):
        if len(direction) == 2:
            direction = (*direction, 0)
        super().__init__(ORIGIN, direction, buff=buff, **kwargs)


VectorMobject = Vector


class DoubleArrow(VGroup):
    def __init__(self, start=LEFT, end=RIGHT, buff=0.25, path_arc=0.0, **kwargs):
        spine = Line(start, end, buff=buff, path_arc=path_arc)
        midpoint = spine.point_from_proportion(0.5)
        super().__init__(
            Arrow(midpoint, spine.get_end(), buff=0.0, path_arc=path_arc / 2, **kwargs),
            Arrow(midpoint, spine.get_start(), buff=0.0, path_arc=-path_arc / 2, **kwargs),
        )


class CurvedArrow(Arrow):
    def __init__(self, start, end, angle=math.tau / 4, **kwargs):
        super().__init__(start, end, path_arc=angle, **kwargs)


class CurvedDoubleArrow(DoubleArrow):
    def __init__(self, start, end, angle=math.tau / 4, **kwargs):
        super().__init__(start, end, path_arc=angle, **kwargs)


class TangentLine(Line):
    def __init__(self, mobject, alpha, length=1.0, d_alpha=1e-6, **kwargs):
        start = float(np.clip(alpha - d_alpha, 0, 1))
        end = float(np.clip(alpha + d_alpha, 0, 1))
        if start == end:
            raise ValueError("d_alpha is too small to take a derivative")
        vector = mobject.point_from_proportion(end) - mobject.point_from_proportion(start)
        magnitude = norm(vector)
        if not magnitude > 0:
            raise ValueError("the path has no tangent here; try a larger d_alpha")
        unit = vector / np.float32(magnitude)
        center = mobject.point_from_proportion(alpha)
        half = np.float32(length) / np.float32(2)
        super().__init__(center - half * unit, center + half * unit, buff=0.0, **kwargs)


class StrokeArrow(VGroup):
    def __init__(
        self,
        start=LEFT,
        end=RIGHT,
        stroke_width=5.0,
        buff=0.25,
        color=GREY_A,
        tip_length=0.25,
        tip_width_ratio=1.2,
        **kwargs,
    ):
        first, last = endpoints(start, end)
        vector = last - first
        magnitude = float(norm(vector))
        if magnitude <= 2 * buff:
            raise ValueError("the buff trims the entire arrow")
        unit = vector / np.float32(magnitude)
        first = first + np.float32(buff) * unit
        last = last - np.float32(buff) * unit
        length = min(float(tip_length), 0.5 * (magnitude - 2 * buff))
        base = last - np.float32(length) * unit
        perpendicular = point3((-unit[1], unit[0], 0)) * np.float32(length * tip_width_ratio / 2)
        shaft = Line(first, base).set_stroke(color, width=stroke_width)
        head = Polygon(last, base + perpendicular, base - perpendicular)
        head.set_fill(color, 1.0).set_stroke(width=0.0)
        super().__init__(shaft, head, **kwargs)
