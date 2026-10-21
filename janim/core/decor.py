"""Vector decorations."""

import math

import numpy as np

from janim.constants import DOWN, GREEN, GREY_B, LEFT, ORIGIN, RED, WHITE, YELLOW
from .mobject import VGroup, VMobject
from .shapes import Circle, Dot, Line
from .trackers import TracedPath


def CurvesAsSubmobjects(vmobject, **kwargs):
    """One child per curve of `vmobject`'s path, each a three-point VMobject in its style (as in ManimGL)."""
    group = VGroup(**kwargs)
    for index in range(vmobject.get_num_curves()):
        part = VMobject()
        part.set_points(vmobject.get_nth_curve_points(index))
        part.match_style(vmobject)
        group.add(part)
    return group


def _line_box(font, size):
    from janim.text.glyphs import _FONT_LOCK, find_face

    with _FONT_LOCK:
        face, _ = find_face("DejaVu Sans" if font is None else font)
        return (float(face.ascender) - float(face.descender)) / float(face.units_per_EM) * size


def _stack_lines(group, line_spacing, aligned_edge, blank, line_box):
    previous = None
    gap = 0
    for child, is_blank in zip(group.submobjects, blank):
        if is_blank:
            gap += 1
            continue
        buff = line_spacing if gap == 0 else line_spacing + gap * (line_box + line_spacing)
        if previous is not None:
            child.next_to(previous, DOWN, buff=buff, aligned_edge=aligned_edge)
        previous = child
        gap = 0
    return group.center()


class Paragraph(VGroup):
    def __init__(
        self,
        *lines,
        size=0.5,
        line_spacing=0.3,
        alignment=LEFT,
        color=WHITE,
        font=None,
        **kwargs,
    ):
        from janim.text.text import Text

        if not lines:
            raise ValueError("a paragraph needs at least one line")
        options = {} if font is None else {"font": font}
        blank = [not line.strip() for line in lines]
        group = VGroup(*(
            VGroup() if is_blank else Text(line, size=size, color=color, **options)
            for line, is_blank in zip(lines, blank)
        ))
        _stack_lines(group, line_spacing, alignment, blank, _line_box(font, size) if any(blank) else 0.0)
        super().__init__(*group.submobjects, **kwargs)


class BulletedList(VGroup):
    def __init__(
        self,
        *items,
        size=0.5,
        line_spacing=0.35,
        dot_buff=0.25,
        dot_color=GREY_B,
        color=WHITE,
        **kwargs,
    ):
        from janim.text.text import Text

        if not items:
            raise ValueError("a bulleted list needs at least one item")
        group = VGroup()
        blank = [not item.strip() for item in items]
        for item, is_blank in zip(items, blank):
            if is_blank:
                group.add(VGroup())
                continue
            text = Text(item, size=size, color=color)
            dot = Dot(radius=0.045 + 0.05 * size).set_fill(dot_color, 1.0)
            dot.next_to(text, LEFT, buff=dot_buff)
            group.add(VGroup(dot, text))
        _stack_lines(group, line_spacing, LEFT, blank, _line_box(None, size) if any(blank) else 0.0)
        super().__init__(*group.submobjects, **kwargs)


class Cutout(VMobject):
    def __init__(self, shape, *holes, **kwargs):
        if not shape.has_points() or not holes:
            raise ValueError("Cutout requires a shape with points and at least one hole")
        super().__init__(**kwargs)
        self.set_points(shape.points).match_style(shape)
        for hole in holes:
            if not hole.has_points():
                raise ValueError("each hole needs points of its own")
            for subpath in hole.get_subpaths():
                self.add_subpath(subpath[::-1])


class Checkmark(VMobject):
    def __init__(self, size=0.5, color=GREEN, stroke_width=6.0, **kwargs):
        super().__init__(**kwargs)
        self.set_points_as_corners(((-0.5, 0.1, 0), (-0.15, -0.35, 0), (0.5, 0.45, 0)))
        self.scale(size).set_stroke(color, width=stroke_width).set_fill(opacity=0)


class Exmark(VGroup):
    def __init__(self, size=0.5, color=RED, stroke_width=6.0, **kwargs):
        super().__init__(
            Line((-0.4, -0.4, 0), (0.4, 0.4, 0)),
            Line((-0.4, 0.4, 0), (0.4, -0.4, 0)),
            **kwargs,
        )
        self.scale(size).set_stroke(color, width=stroke_width)


class Clock(VGroup):
    def __init__(
        self,
        radius=1.0,
        hour=12,
        minute=0,
        color=WHITE,
        stroke_width=3.0,
        n_ticks=12,
        **kwargs,
    ):
        face = Circle(radius=radius).set_stroke(color, width=stroke_width).set_fill(opacity=0)
        marks = []
        for index in range(n_ticks):
            angle = math.pi / 2 - index * math.tau / n_ticks
            outer = (radius * math.cos(angle), radius * math.sin(angle), 0)
            inner = (0.86 * radius * math.cos(angle), 0.86 * radius * math.sin(angle), 0)
            marks.append(Line(inner, outer).set_stroke(color, width=stroke_width * 0.7))
        hour_angle = math.pi / 2 - (float(hour) % 12 + float(minute) / 60) * math.tau / 12
        minute_angle = math.pi / 2 - float(minute) * math.tau / 60
        hour_hand = Line(
            ORIGIN,
            (0.5 * radius * math.cos(hour_angle), 0.5 * radius * math.sin(hour_angle), 0),
        )
        minute_hand = Line(
            ORIGIN,
            (0.8 * radius * math.cos(minute_angle), 0.8 * radius * math.sin(minute_angle), 0),
        )
        hour_hand.set_stroke(color, width=stroke_width * 1.4)
        minute_hand.set_stroke(color, width=stroke_width)
        super().__init__(face, hour_hand, minute_hand, VGroup(*marks), **kwargs)


class VHighlight(VGroup):
    def __init__(self, mobject, n=5, max_stroke=15.0, color=YELLOW, max_opacity=0.5, **kwargs):
        if n < 1 or not (mobject.has_points() or mobject.submobjects):
            raise ValueError("VHighlight requires geometry and at least one layer")
        layers = []
        for index in range(n):
            fraction = (n - index) / n
            layer = mobject.copy()
            layer.set_stroke(color, width=max_stroke * fraction, opacity=max_opacity * (1 - fraction) + 0.05)
            layer.set_fill(opacity=0)
            layers.append(layer)
        super().__init__(*layers, **kwargs)


class TracingTail(TracedPath):
    def __init__(
        self,
        point_func,
        time_traced=1.0,
        stroke_width=6.0,
        color=WHITE,
        taper=True,
        smooth=True,
        **kwargs,
    ):
        if time_traced <= 0:
            raise ValueError("time_traced must be positive")
        super().__init__(
            point_func,
            time_traced=time_traced,
            smooth=smooth,
            stroke_color=color,
            stroke_width=stroke_width,
            **kwargs,
        )
        if taper:
            def apply_taper(mobject, dt):
                count = len(mobject.points)
                if count >= 2:
                    fractions = np.arange(count, dtype=np.float64) / (count - 1)
                    mobject.stroke_rgba[:, 3] = fractions
                    mobject.stroke_width[:] = stroke_width * fractions
                return mobject

            self.add_updater(apply_taper)
