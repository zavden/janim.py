"""Numeric text and its interpolation contract."""

import operator

import numpy as np

from janim.constants import DEFAULT_FONT_SIZE, DOWN, LEFT, RIGHT, UP, WHITE
from janim.core.mobject import VMobject
from .text import GL_SIZE_TEXT, Text, text_size


def _tex_unit(unit):
    return unit is not None and ("\\" in str(unit) or str(unit).startswith("^"))


def _append_tex_unit(group, unit, size, color):
    if not _tex_unit(unit):
        return group
    from .tex import Tex

    unit = str(unit)
    superscript = unit.startswith("^")
    label = Tex(
        "{}" + unit if superscript else unit,
        font_size=size * DEFAULT_FONT_SIZE * GL_SIZE_TEXT,
        color=color,
    )
    label.next_to(
        group.submobjects[-1],
        RIGHT,
        buff=0.001 * size * DEFAULT_FONT_SIZE * GL_SIZE_TEXT,
        aligned_edge=DOWN,
    )
    if superscript:
        label.align_to(group, UP)
    children = list(label.submobjects)
    label.remove(*children)
    group.add(*children).center()
    return group


def decimal_string(value, places, include_sign=False, unit=None):
    places = operator.index(places)
    number = float(value)
    result = str(round(number)) if places <= 0 else f"{number:.{places}f}"
    if result.startswith("-") and all(character in "0." for character in result[1:]):
        result = result[1:]
    if include_sign and not result.startswith("-"):
        result = "+" + result
    return result if unit is None or _tex_unit(unit) else result + str(unit)


class DecimalNumber(Text):
    def __init__(
        self,
        value=0.0,
        num_decimal_places=2,
        size=None,
        font_size=None,
        color=WHITE,
        include_sign=False,
        unit=None,
        edge_to_fix=LEFT,
        integer=False,
        **kwargs,
    ):
        self.value = float(value)
        self.num_decimal_places = operator.index(num_decimal_places)
        self.number_color = color
        self.include_sign = bool(include_sign)
        self.unit = unit
        self.edge_to_fix = np.array(edge_to_fix, dtype=np.float32)
        self.integer = bool(integer)
        size = text_size(size, font_size, GL_SIZE_TEXT, "DecimalNumber")
        super().__init__(
            decimal_string(self.value, self.num_decimal_places, self.include_sign, unit),
            size=size,
            color=color,
            **kwargs,
        )
        _append_tex_unit(self, unit, size, color)

    @property
    def group(self):
        return self

    def get_value(self):
        return round(self.value) if self.integer else self.value

    def _handle_scale_side_effects(self, factor):
        # Keep the uniform scale through subsequent glyph rebuilds.
        if np.isscalar(factor):
            self.size *= float(factor)
            self.font_size *= float(factor)

    def set_value(self, value):
        uniforms = {
            name: item.copy() if isinstance(item, np.ndarray) else item
            for name, item in self.uniforms.items()
        }
        depth_test = self.depth_test
        keys = self.get_keys()
        anchor = self.get_bounding_box_point(self.edge_to_fix)
        first = next((mob for mob in self.get_family() if mob.has_points()), None)
        text = decimal_string(value, self.num_decimal_places, self.include_sign, self.unit)
        fresh = Text(text, size=self.size, color=self.number_color)
        _append_tex_unit(fresh, self.unit, self.size, self.number_color)
        if first is not None:
            fresh.match_style(first)
        fresh.move_to(anchor, aligned_edge=self.edge_to_fix)
        if keys:
            fresh.set_key(*keys)
        if len(self.submobjects) != len(fresh.submobjects):
            self.set_submobjects([child.copy() for child in fresh.submobjects])
        VMobject.become(self, fresh)
        # This internal rebuild recomputes fresh bounding boxes, unlike public copy.
        self.refresh_bounding_box(recurse_down=True)
        for child in self.get_family():
            child.uniforms.update({
                name: item.copy() if isinstance(item, np.ndarray) else item
                for name, item in uniforms.items()
            })
            child.depth_test = depth_test
        self.value = float(value)
        self.string = text
        return self

    set_number = set_value

    def increment_value(self, delta):
        return self.set_value(self.value + delta)

    def interpolate(self, first, second, alpha, **kwargs):
        super().interpolate(first, second, alpha, **kwargs)
        if isinstance(first, DecimalNumber) and isinstance(second, DecimalNumber):
            self.value = first.value + float(alpha) * (second.value - first.value)
            self.size = first.size + float(alpha) * (second.size - first.size)
            self.font_size = first.font_size + float(alpha) * (second.font_size - first.font_size)
        return self

    def become(self, other, match_updaters=False):
        super().become(other, match_updaters=match_updaters)
        if isinstance(other, DecimalNumber):
            for name in (
                "value", "num_decimal_places", "size", "font_size", "number_color",
                "include_sign", "unit", "integer", "string",
            ):
                setattr(self, name, getattr(other, name))
            self.edge_to_fix = other.edge_to_fix.copy()
        return self


class Integer(DecimalNumber):
    def __init__(self, value=0, num_decimal_places=0, **kwargs):
        super().__init__(value, num_decimal_places=num_decimal_places, integer=True, **kwargs)


IntegerMobject = Integer


class Variable(VMobject):
    """"label = value", the value following a `ValueTracker` (CE's).

    A string label goes through LaTeX (`Tex`, CE's `MathTex`); any mobject is
    used as it is. The "=" becomes a child of the label, as in CE.
    `var_type` is `DecimalNumber` (with `num_decimal_places`) or `Integer`;
    `variable.tracker` is the `ValueTracker` to animate, and
    `variable.label` and `variable.value` are the two parts.
    """

    def __init__(self, var, label, var_type=None, num_decimal_places=2, **kwargs):
        from janim.core.trackers import ValueTracker
        from .tex import Tex

        var_type = DecimalNumber if var_type is None else var_type
        if not (isinstance(var_type, type) and issubclass(var_type, DecimalNumber)):
            raise TypeError("Variable's var_type is DecimalNumber or Integer")
        super().__init__(**kwargs)
        self.label = Tex(label) if isinstance(label, str) else label
        equals = Tex("=").next_to(self.label, RIGHT)
        self.label.add(equals)
        self.tracker = ValueTracker(var)
        if issubclass(var_type, Integer):
            self.value = var_type(self.tracker.get_value())
        else:
            self.value = var_type(
                self.tracker.get_value(),
                num_decimal_places=num_decimal_places,
            )
        tracker = self.tracker
        self.value.add_updater(lambda value: value.set_value(tracker.get_value()))
        self.value.next_to(self.label, RIGHT)
        self.add(self.label, self.value)
