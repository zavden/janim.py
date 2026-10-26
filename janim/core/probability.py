"""ManimGL's sample space: a rectangle that splits into probabilities."""

import numpy as np

from janim.constants import (
    BLUE_E,
    DOWN,
    GREEN_E,
    GREY_B,
    GREY_D,
    LEFT,
    MAROON_B,
    MED_SMALL_BUFF,
    RIGHT,
    SMALL_BUFF,
    UP,
    YELLOW,
)
from .colorspace import color_gradient
from .mobject import Mobject, VGroup
from .shapes import Rectangle

EPSILON = 0.0001


class SampleSpace(Rectangle):
    """A rectangle of probabilities (GL's).

    `divide_horizontally(p_list)` stacks parts whose heights are the
    probabilities (the rest up to 1 is added as a last part), and
    `divide_vertically(p_list)` does the same with widths; indexing the
    sample space then indexes those parts. Braces and labels come from
    `get_side_braces_and_labels`, `get_top_braces_and_labels` and
    `get_bottom_braces_and_labels`; a string label goes through LaTeX.
    """

    def __init__(
        self,
        width=3.0,
        height=3.0,
        fill_color=GREY_D,
        fill_opacity=1.0,
        stroke_width=0.5,
        stroke_color=GREY_B,
        default_label_scale_val=1.0,
        **kwargs,
    ):
        super().__init__(width, height, **kwargs)
        self.set_fill(fill_color, opacity=fill_opacity)
        self.set_stroke(stroke_color, width=stroke_width)
        self.default_label_scale_val = default_label_scale_val

    def add_title(self, title="Sample space", buff=MED_SMALL_BUFF):
        from janim.text.tex import TexText

        title_mob = TexText(title)
        if title_mob.get_width() > self.get_width():
            title_mob.set_width(self.get_width())
        title_mob.next_to(self, UP, buff=buff)
        self.title = title_mob
        self.add(title_mob)

    def add_label(self, label):
        self.label = label

    def complete_p_list(self, p_list):
        new_p_list = list(p_list) if isinstance(p_list, (list, tuple, np.ndarray)) else [p_list]
        remainder = 1.0 - sum(new_p_list)
        if abs(remainder) > EPSILON:
            new_p_list.append(remainder)
        return new_p_list

    def get_division_along_dimension(self, p_list, dim, colors, vect):
        p_list = self.complete_p_list(p_list)
        colors = color_gradient(colors, len(p_list))
        last_point = self.get_edge_center(-np.asarray(vect))
        parts = VGroup()
        for factor, color in zip(p_list, colors):
            part = SampleSpace()
            part.set_fill(color, 1)
            part.replace(self, stretch=True)
            part.stretch(factor, dim)
            part.move_to(last_point, -np.asarray(vect))
            last_point = part.get_edge_center(vect)
            parts.add(part)
        return parts

    def get_horizontal_division(self, p_list, colors=(GREEN_E, BLUE_E), vect=DOWN):
        return self.get_division_along_dimension(p_list, 1, colors, vect)

    def get_vertical_division(self, p_list, colors=(MAROON_B, YELLOW), vect=RIGHT):
        return self.get_division_along_dimension(p_list, 0, colors, vect)

    def divide_horizontally(self, *args, **kwargs):
        self.horizontal_parts = self.get_horizontal_division(*args, **kwargs)
        self.add(self.horizontal_parts)

    def divide_vertically(self, *args, **kwargs):
        self.vertical_parts = self.get_vertical_division(*args, **kwargs)
        self.add(self.vertical_parts)

    def get_subdivision_braces_and_labels(self, parts, labels, direction, buff=SMALL_BUFF):
        from janim.text.tex import Tex
        from .annotations import Brace

        label_mobs = VGroup()
        braces = VGroup()
        for label, part in zip(labels, parts):
            brace = Brace(part, direction, buff=buff)
            if isinstance(label, Mobject):
                label_mob = label
            else:
                label_mob = Tex(label)
                label_mob.scale(self.default_label_scale_val)
            label_mob.next_to(brace, direction, buff=buff)
            braces.add(brace)
            label_mobs.add(label_mob)
        parts.braces = braces
        parts.labels = label_mobs
        parts.label_kwargs = {
            "labels": label_mobs.copy(),
            "direction": direction,
            "buff": buff,
        }
        return VGroup(parts.braces, parts.labels)

    def get_side_braces_and_labels(self, labels, direction=LEFT, **kwargs):
        if not hasattr(self, "horizontal_parts"):
            raise ValueError("divide_horizontally first: the side braces measure the horizontal parts")
        return self.get_subdivision_braces_and_labels(self.horizontal_parts, labels, direction, **kwargs)

    def get_top_braces_and_labels(self, labels, **kwargs):
        if not hasattr(self, "vertical_parts"):
            raise ValueError("divide_vertically first: the top braces measure the vertical parts")
        return self.get_subdivision_braces_and_labels(self.vertical_parts, labels, UP, **kwargs)

    def get_bottom_braces_and_labels(self, labels, **kwargs):
        if not hasattr(self, "vertical_parts"):
            raise ValueError("divide_vertically first: the bottom braces measure the vertical parts")
        return self.get_subdivision_braces_and_labels(self.vertical_parts, labels, DOWN, **kwargs)

    def add_braces_and_labels(self):
        for attr in ("horizontal_parts", "vertical_parts"):
            if not hasattr(self, attr):
                continue
            parts = getattr(self, attr)
            for subattr in ("braces", "labels"):
                if hasattr(parts, subattr):
                    self.add(getattr(parts, subattr))

    def __getitem__(self, index):
        if hasattr(self, "horizontal_parts"):
            return self.horizontal_parts[index]
        if hasattr(self, "vertical_parts"):
            return self.vertical_parts[index]
        return self.split()[index]
