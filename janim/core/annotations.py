"""Braces, marks and labels."""

import math

import numpy as np

from janim.constants import (
    BLACK,
    BLUE,
    DOWN,
    FRAME_WIDTH,
    GREY_A,
    GREY_C,
    LEFT,
    ORIGIN,
    RED,
    RIGHT,
    UP,
    WHITE,
    YELLOW,
)
from .algebra import angle_of_vector, norm
from .mobject import Mobject, VGroup, VMobject
from .shapes import Arc, Arrow, Dot, Line, Polygon, Polygram, Rectangle, endpoints
from .transforms import point3


class SurroundingRectangle(Rectangle):
    def __init__(self, mobject, *, buff=0.1, color=YELLOW, stroke_width=2.0, **kwargs):
        # ManimGL passes any style keyword (fill_opacity, fill_color, …) down to Rectangle
        super().__init__(
            width=float(mobject.get_width()) + 2 * buff,
            height=float(mobject.get_height()) + 2 * buff,
            **kwargs,
        )
        self.set_stroke(color=color, width=stroke_width)
        if "fill_opacity" not in kwargs and "fill_color" not in kwargs:
            self.set_fill(opacity=0)
        self.move_to(mobject.get_center())


class Underline(Line):
    def __init__(self, mobject, *, buff=0.1, color=WHITE, stroke_width=3.0):
        half = np.float32(mobject.get_width()) / np.float32(2)
        center = mobject.get_bounding_box_point(DOWN)
        super().__init__(
            center + np.array((-half, -buff, 0), dtype=np.float32),
            center + np.array((half, -buff, 0), dtype=np.float32),
        )
        self.set_stroke(color=color, width=stroke_width)


class Brace(VMobject):
    def __init__(
        self,
        mobject,
        direction=DOWN,
        buff=0.2,
        color=WHITE,
        thickness=0.18,
        tip_length=0.3,
        stroke_width=0.0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        direction = point3(direction)
        perpendicular = point3((-direction[1], direction[0], 0))
        span = abs(mobject.get_width() * perpendicular[0]) + abs(mobject.get_height() * perpendicular[1])
        half = 0.5 * max(float(span), 4 * float(tip_length))
        thickness, tip = float(thickness), float(tip_length)
        self.set_points_as_corners(
            (
                (-half, 0, 0),
                (-half + tip, -thickness, 0),
                (-tip, -thickness, 0),
                (0, -2 * thickness, 0),
                (tip, -thickness, 0),
                (half - tip, -thickness, 0),
                (half, 0, 0),
            ),
        )
        self.set_stroke(color, width=max(stroke_width, 3.0)).set_fill(opacity=0)
        from ._atan32 import atan2

        theta = float(atan2(direction[1], direction[0]))
        self.rotate(theta + math.pi / 2)
        self.move_to(mobject.get_bounding_box_point(direction))
        self.shift(np.float32(buff + 2 * thickness) * direction)

    def get_tip(self):
        if not self.has_points():
            raise ValueError("this brace has no points")
        return self.points[(len(self.points) - 1) // 2].copy()

    def get_direction(self):
        vector = (self.get_tip() - self.get_center()).astype(np.float64)
        return (vector / norm(vector)).astype(np.float32)

    def get_tex(self, *strings, buff=0.1, **kwargs):
        from janim.text.tex import Tex

        return Tex(*strings, **kwargs).next_to(self.get_tip(), np.round(self.get_direction()), buff=buff)


class BraceLabel(VGroup):
    _math_mode = False

    def __init__(
        self,
        mobject,
        text,
        direction=DOWN,
        buff=0.2,
        label_buff=0.15,
        size=0.5,
        color=WHITE,
        via=None,
        **kwargs,
    ):
        brace = Brace(mobject, direction, buff=buff, color=color, **kwargs)
        route = ("latex" if self._math_mode else "text") if via is None else via
        label = _label_via(text, route, size=size, color=color)
        label.next_to(brace, direction, buff=label_buff)
        super().__init__(brace, label)


class BraceText(BraceLabel):
    _math_mode = True

    def put_at_tip(self, mobject, buff=0.1):
        mobject.next_to(self.get_tip(), np.round(self.get_direction()), buff=buff)
        return mobject


class BraceBetweenPoints(Brace):
    def __init__(self, start, end, direction=None, **kwargs):
        start, end = point3(start), point3(end)
        vector = end - start
        direction = point3((vector[1], -vector[0], 0)) if direction is None else point3(direction)
        magnitude = norm(direction)
        if magnitude <= 0:
            raise ValueError("coincident points have no segment to brace")
        super().__init__(Line(start, end), direction / np.float32(magnitude), **kwargs)


class LineBrace(BraceBetweenPoints):
    def __init__(self, line, **kwargs):
        super().__init__(line.get_start(), line.get_end(), **kwargs)


class BackgroundRectangle(Rectangle):
    def __init__(self, mobject, color=BLACK, opacity=0.75, buff=0.1, fill_opacity=None, **kwargs):
        super().__init__(
            width=float(mobject.get_width()) + 2 * buff,
            height=float(mobject.get_height()) + 2 * buff,
            **kwargs,
        )
        self.set_fill(color, opacity if fill_opacity is None else fill_opacity)
        self.set_stroke(width=0, opacity=0).move_to(mobject.get_center())


class Cross(VGroup):
    def __init__(self, mobject, color=RED, stroke_width=6.0, scale_factor=1.0, **kwargs):
        width = 0.5 * float(mobject.get_width()) * scale_factor
        height = 0.5 * float(mobject.get_height()) * scale_factor
        center = mobject.get_center()
        first = Line(center + point3((-width, -height, 0)), center + point3((width, height, 0)))
        second = Line(center + point3((-width, height, 0)), center + point3((width, -height, 0)))
        first.set_stroke(color, width=stroke_width)
        second.set_stroke(color, width=stroke_width)
        super().__init__(first, second, **kwargs)


class DashedVMobject(VGroup):
    def __init__(
        self,
        mobject,
        num_dashes=15,
        positive_space_ratio=0.5,
        color=None,
        stroke_width=None,
        **kwargs,
    ):
        if num_dashes < 1 or not 0 < positive_space_ratio <= 1:
            raise ValueError("num_dashes must be positive and positive_space_ratio in (0, 1]")
        super().__init__(**kwargs)
        self.match_style(mobject)
        period = 1.0 / num_dashes
        partial = float(positive_space_ratio) * period
        ladder = 1.0 - period + partial
        pieces = []
        for index in range(num_dashes):
            start = (index * period) / ladder
            end = min(start + partial, 1.0)
            piece = VMobject().match_points(mobject).pointwise_become_partial(mobject, start, end)
            piece.match_style(mobject)
            if color is not None:
                piece.set_color(color)
            if stroke_width is not None:
                piece.set_stroke(width=stroke_width)
            pieces.append(piece)
        self.add(*pieces)

    def get_start(self):
        return self.submobjects[0].get_start()

    def get_end(self):
        return self.submobjects[-1].get_end()


def line_intersection(first, second, third=None, fourth=None):
    if third is None and fourth is None:
        first, second, third, fourth = first[0], first[1], second[0], second[1]
    a, b, c, d = map(point3, (first, second, third, fourth))
    xd = a[0] - b[0], c[0] - d[0]
    yd = a[1] - b[1], c[1] - d[1]

    def determinant(u, v):
        return u[0] * v[1] - u[1] * v[0]

    divisor = determinant(xd, yd)
    if divisor == 0:
        raise ValueError("parallel lines have no intersection")
    dd = determinant(a, b), determinant(c, d)
    return point3((determinant(dd, xd) / divisor, determinant(dd, yd) / divisor, 0))


def _angle_geometry(line1, line2, radius=None, quadrant=(1, 1), other_angle=False):
    intersection = line_intersection(*line1.get_start_and_end(), *line2.get_start_and_end())
    if radius is None:
        distances = [
            norm((line.get_end() if sign == 1 else line.get_start()) - intersection)
            for line, sign in zip((line1, line2), quadrant)
        ]
        shortest = float(min(distances))
        radius = (2 / 3) * shortest if shortest < 0.6 else 0.4
    first = intersection + np.float32(quadrant[0]) * np.float32(radius) * line1.get_unit_vector()
    second = intersection + np.float32(quadrant[1]) * np.float32(radius) * line2.get_unit_vector()
    angle1 = angle_of_vector(first - intersection)
    angle2 = angle_of_vector(second - intersection)
    if other_angle:
        value = angle2 - angle1 if angle2 < angle1 else (angle2 - angle1) - math.tau
    else:
        value = angle2 - angle1 if angle2 > angle1 else math.tau - (angle1 - angle2)
    return intersection, float(radius), first, second, angle1, value


def angle_value(line1, line2, **kwargs):
    return _angle_geometry(line1, line2, **kwargs)[-1]


class Angle(Arc):
    def __init__(
        self,
        line1,
        line2,
        radius=None,
        quadrant=(1, 1),
        other_angle=False,
        elbow=False,
        color=GREY_A,
        stroke_width=4.0,
        dot=False,
        dot_radius=None,
        dot_distance=0.55,
        dot_color=WHITE,
        **kwargs,
    ):
        center, radius, first, second, start_angle, value = _angle_geometry(
            line1,
            line2,
            radius,
            quadrant,
            other_angle,
        )
        if elbow:
            VMobject.__init__(self, **kwargs)
            middle = center + np.float32(quadrant[0] * radius) * line1.get_unit_vector()
            middle = middle + np.float32(quadrant[1] * radius) * line2.get_unit_vector()
            self.set_points_as_corners((first, middle, second))
        else:
            super().__init__(start_angle, value, radius, arc_center=center, **kwargs)
        self.set_stroke(color, width=stroke_width).set_fill(opacity=0)
        if dot and not elbow:
            marker = Dot(radius=radius / 10 if dot_radius is None else dot_radius, fill_color=dot_color)
            vector = self.get_center().astype(np.float64) - center.astype(np.float64)
            point = center.astype(np.float64) + (vector / norm(vector)) * radius * float(dot_distance)
            self.add(marker.move_to(point.astype(np.float32)))


class RightAngle(Angle):
    def __init__(self, line1, line2, length=None, **kwargs):
        super().__init__(line1, line2, radius=length, elbow=True, **kwargs)


class AnnotationDot(Arc):
    def __init__(self, point=ORIGIN, radius=1.3 * 0.08, **kwargs):
        kwargs.setdefault("fill_color", BLUE)
        kwargs.setdefault("fill_opacity", 1.0)
        kwargs.setdefault("stroke_color", WHITE)
        kwargs.setdefault("stroke_width", 5.0)
        super().__init__(angle=math.tau, radius=radius, arc_center=point, **kwargs)


class DimensionLine(VGroup):
    def __init__(
        self,
        start,
        end,
        color=GREY_A,
        stroke_width=1.5,
        tip_length=0.11,
        tip_width=0.11,
        max_tip_length_ratio=0.28,
        **kwargs,
    ):
        super().__init__(**kwargs)
        start, end = point3(start), point3(end)
        vector = (end - start).astype(np.float64)
        length = float(norm(vector))
        if length < 1e-8:
            return
        unit = (vector / length).astype(np.float32)
        normal = point3((-unit[1], unit[0], 0))
        length = np.float32(min(tip_length, max_tip_length_ratio * length))
        half = np.float32(tip_width / 2)
        inner0, inner1 = start + length * unit, end - length * unit
        shaft = Line(inner0, inner1).set_stroke(color, width=stroke_width)
        darts = []
        for apex, waist in ((start, inner0), (end, inner1)):
            dart = Polygon(apex, waist + half * normal, waist, waist - half * normal)
            dart.set_fill(color, 1.0).set_stroke(color, width=0.0)
            darts.append(dart)
        self.add(shaft, *darts)


def _as_label(value, size=0.5, color=WHITE, math_mode=False):
    if isinstance(value, Mobject):
        return value
    if math_mode:
        from janim.text.tex import Tex

        return Tex(str(value), size=size, color=color)
    from janim.text.text import Text

    return Text(str(value), size=size, color=color)


def _label_via(value, via, *, size, color):
    if isinstance(value, Mobject):
        return value
    if via == "typst":
        raise NotImplementedError("via='typst' is unavailable; formulas use LaTeX")
    if via not in ("text", "math", "latex", "auto"):
        raise ValueError(f"unknown label via={via!r}; use text, math, latex or auto; typst is unavailable")
    return _as_label(value, size=size, color=color, math_mode=via != "text")


class LabeledDot(VGroup):
    def __init__(
        self,
        label,
        point=ORIGIN,
        buff=0.2,
        radius=None,
        size=0.5,
        fill_color=BLUE,
        fill_opacity=1.0,
        stroke_color=WHITE,
        stroke_width=0.0,
        **kwargs,
    ):
        label = _as_label(label, size=size, math_mode=True)
        if radius is None:
            radius = math.sqrt(
                (float(label.get_width()) / 2) ** 2 + (float(label.get_height()) / 2) ** 2,
            ) + buff
        disc = Dot(
            radius=radius,
            fill_color=fill_color,
            fill_opacity=fill_opacity,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
        )
        label.move_to(ORIGIN)
        super().__init__(disc, label, **kwargs)
        self.move_to(point)


class Label(VGroup):
    def __init__(
        self,
        text,
        buff=0.15,
        size=0.5,
        color=WHITE,
        box_color=WHITE,
        background=BLACK,
        background_opacity=0.85,
        stroke_width=2.0,
        **kwargs,
    ):
        label = _as_label(text, size=size, color=color)
        dimensions = dict(
            width=float(label.get_width()) + 2 * buff,
            height=float(label.get_height()) + 2 * buff,
        )
        background_mob = Rectangle(**dimensions).set_fill(background, background_opacity)
        background_mob.set_stroke(width=0.0, opacity=0.0).move_to(label.get_center())
        border = Rectangle(**dimensions).set_fill(opacity=0.0)
        border.set_stroke(box_color, width=stroke_width).move_to(label.get_center())
        super().__init__(background_mob, label, border, **kwargs)


class LabeledPolygram(Polygram):
    """A polygram with a label at its pole of inaccessibility (CE's).

    The pole is the point inside the polygram farthest from every edge,
    holes included, found by polylabel to `precision` (the same pole as CE,
    to the last bit); `polygram.pole` is that point and `polygram.radius`
    its distance to the nearest edge. The label is Janim's `Label`: a string
    becomes a `Text` (CE's becomes a `MathTex`), a mobject is used as it is.
    `label_config` goes to `Label` (`buff`, `size`, `color`, `box_color`,
    `background`, `background_opacity`, `stroke_width`); CE's `box_config`
    (`color`/`fill_color`, `fill_opacity`, `buff`) and `frame_config`
    (`color`/`stroke_color`, `stroke_width`, `buff`) are translated to it.
    A vertex group may repeat its first vertex at the end or not.
    """

    def __init__(
        self,
        *vertex_groups,
        label,
        precision=0.01,
        label_config=None,
        box_config=None,
        frame_config=None,
        **kwargs,
    ):
        from .polylabel import polylabel

        groups = [np.asarray(group, dtype=np.float64) for group in vertex_groups]
        open_groups = [group[:-1] if len(group) > 3 and np.array_equal(group[0], group[-1]) else group for group in groups]
        super().__init__(*open_groups, **kwargs)
        options = dict(label_config or {})
        for key, value in (box_config or {}).items():
            target = {"color": "background", "fill_color": "background", "fill_opacity": "background_opacity", "buff": "buff"}.get(key)
            if target is None:
                raise TypeError(f"LabeledPolygram's box_config does not take {key!r}")
            if value is not None:
                options[target] = value
        for key, value in (frame_config or {}).items():
            target = {"color": "box_color", "stroke_color": "box_color", "stroke_width": "stroke_width", "buff": "buff"}.get(key)
            if target is None:
                raise TypeError(f"LabeledPolygram's frame_config does not take {key!r}")
            if value is not None:
                options[target] = value
        self.label = Label(label, **options)
        rings = [np.vstack((group, group[:1])) for group in open_groups]
        cell = polylabel(rings, precision=precision)
        self.pole = np.array((cell.c[0], cell.c[1], 0.0))
        self.radius = float(cell.d)
        self.label.move_to(self.pole)
        self.add(self.label)


class LabeledLine(VGroup):
    def __init__(self, text, start=LEFT, end=RIGHT, alpha=0.5, buff=0.0, path_arc=0.0, **kwargs):
        shaft = Line(start, end, buff=buff, path_arc=path_arc)
        first, last = shaft.get_start_and_end()
        label = Label(text, **kwargs).move_to(first + np.float32(np.clip(alpha, 0, 1)) * (last - first))
        super().__init__(shaft, label)


class LabeledArrow(VGroup):
    def __init__(self, text, start=LEFT, end=RIGHT, alpha=0.5, buff=0.25, path_arc=0.0, **kwargs):
        shaft = Arrow(start, end, buff=buff, path_arc=path_arc)
        first, last = endpoints(start, end)
        label = Label(text, **kwargs).move_to(first + np.float32(np.clip(alpha, 0, 1)) * (last - first))
        super().__init__(shaft, label)


class Title(VGroup):
    def __init__(
        self,
        text,
        underline=True,
        size=0.8,
        color=WHITE,
        underline_width=FRAME_WIDTH - 2,
        match_underline_width=False,
        underline_buff=0.1,
        underline_color=GREY_C,
        underline_stroke=2.0,
        via="text",
        **kwargs,
    ):
        label = _label_via(text, via, size=size, color=color).to_edge(UP, buff=0.25)
        super().__init__(label, **kwargs)
        if underline:
            rule = Line(LEFT, RIGHT).set_stroke(underline_color, width=underline_stroke)
            rule.set_width(label.get_width() if match_underline_width else underline_width, stretch=True)
            rule.next_to(label, DOWN, buff=underline_buff)
            self.add(rule)
