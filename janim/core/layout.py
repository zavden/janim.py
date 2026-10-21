"""Bounding-box layout."""

import math
import operator

import numpy as np

from janim.constants import DL, FRAME_X_RADIUS, FRAME_Y_RADIUS, LEFT, ORIGIN, RIGHT
from .transforms import point3


def as_point(reference, direction):
    if hasattr(reference, "get_bounding_box_point"):
        return reference.get_bounding_box_point(direction)
    return point3(reference)


class LayoutMixin:
    def get_coord(self, dim, direction=ORIGIN):
        dim = operator.index(dim)
        if dim not in (0, 1, 2):
            raise ValueError(f"dimension {dim} does not exist: 0=x, 1=y, 2=z")
        return self.get_bounding_box_point(direction)[dim]

    def set_coord(self, value, dim, direction=ORIGIN):
        delta = np.float32(value) - self.get_coord(dim, direction)
        displacement = np.zeros(3, dtype=np.float32)
        displacement[dim] = delta
        return self.shift(displacement)

    def center(self):
        return self.shift(-self.get_center())

    def align_on_border(self, direction, buff=0.5):
        direction = point3(direction)
        signs = np.sign(direction)
        target = np.array(
            [float(signs[0]) * FRAME_X_RADIUS, float(signs[1]) * FRAME_Y_RADIUS, 0],
            dtype=np.float32,
        )
        delta = target - self.get_bounding_box_point(direction) - np.float32(buff) * direction
        return self.shift(delta * np.abs(signs))

    def to_edge(self, edge=LEFT, buff=0.5):
        return self.align_on_border(edge, buff)

    def to_corner(self, corner=DL, buff=0.5):
        return self.align_on_border(corner, buff)

    def next_to(
        self,
        reference,
        direction=RIGHT,
        buff=0.25,
        aligned_edge=ORIGIN,
        coor_mask=(1, 1, 1),
    ):
        direction = point3(direction)
        edge = point3(aligned_edge)
        target = as_point(reference, edge + direction)
        anchor = self.get_bounding_box_point(edge - direction)
        return self.shift((target - anchor + np.float32(buff) * direction) * point3(coor_mask))

    def align_to(self, reference, direction=ORIGIN):
        direction = point3(direction)
        target = as_point(reference, direction)
        for dim in range(3):
            if direction[dim] != 0:
                self.set_coord(target[dim], dim, direction)
        return self

    def match_coord(self, reference, dim, direction=ORIGIN):
        return self.set_coord(as_point(reference, direction)[dim], dim, direction)

    def match_x(self, reference, direction=ORIGIN):
        return self.match_coord(reference, 0, direction)

    def match_y(self, reference, direction=ORIGIN):
        return self.match_coord(reference, 1, direction)

    def match_z(self, reference, direction=ORIGIN):
        return self.match_coord(reference, 2, direction)

    def match_dim_size(self, other, dim, **kwargs):
        return self.rescale_to_fit(other.length_over_dim(dim), dim, **kwargs)

    def match_color(self, other):
        return self.set_color(other.get_color())

    def replace(self, other, dim_to_match=0, stretch=False):
        if not other.has_points() and not other.submobjects:
            return self.scale(0)
        if stretch:
            for dim in range(3):
                self.rescale_to_fit(other.length_over_dim(dim), dim, stretch=True)
        else:
            self.rescale_to_fit(other.length_over_dim(dim_to_match), dim_to_match)
        return self.shift(other.get_center() - self.get_center())

    def surround(self, other, dim_to_match=0, stretch=False, buff=0.25):
        self.replace(other, dim_to_match, stretch)
        length = float(other.length_over_dim(dim_to_match))
        if length:
            self.scale((length + buff) / length)
        return self

    def arrange(self, direction=RIGHT, center=True, **kwargs):
        from .trackers import ComplexValueTracker, ValueTracker

        previous = None
        for child in self.submobjects:
            if isinstance(child, (ValueTracker, ComplexValueTracker)):
                continue
            if previous is not None:
                child.next_to(previous, direction, **kwargs)
            previous = child
        return self.center() if center else self

    def arrange_in_grid(
        self,
        n_rows=None,
        n_cols=None,
        buff=None,
        h_buff=None,
        v_buff=None,
        buff_ratio=None,
        h_buff_ratio=0.5,
        v_buff_ratio=0.5,
        aligned_edge=ORIGIN,
        fill_rows_first=True,
    ):
        children = self.submobjects
        count = len(children)
        if not count:
            return self
        for value in (n_rows, n_cols):
            if value is not None and operator.index(value) <= 0:
                raise ValueError("grid dimensions must be positive")
        rows = operator.index(n_rows) if n_rows is not None else (
            max(1, math.floor(math.sqrt(count))) if n_cols is None else max(1, count // n_cols)
        )
        columns = max(1, count // rows) if n_cols is None else operator.index(n_cols)
        if buff is not None:
            horizontal = vertical = float(buff)
        else:
            hr = h_buff_ratio if buff_ratio is None else buff_ratio
            vr = v_buff_ratio if buff_ratio is None else buff_ratio
            horizontal = hr * float(children[0].get_width()) if h_buff is None else float(h_buff)
            vertical = vr * float(children[0].get_height()) if v_buff is None else float(v_buff)
        x_unit = horizontal + max(float(child.get_width()) for child in children)
        y_unit = vertical + max(float(child.get_height()) for child in children)
        for index, child in enumerate(children):
            x, y = (index % columns, index // columns) if fill_rows_first else (index // rows, index % rows)
            child.move_to(ORIGIN, aligned_edge=aligned_edge)
            child.shift((x * x_unit, -y * y_unit, 0))
        return self.center()

    def space_out_submobjects(self, factor=1.5, **kwargs):
        self.scale(factor, **kwargs)
        reciprocal = float(np.divide(1.0, float(factor)))
        for child in self.submobjects:
            child.scale(reciprocal)
        return self

    def add_background_rectangle(self, **kwargs):
        from .annotations import BackgroundRectangle

        self.background_rectangle = BackgroundRectangle(self, **kwargs)
        return self.add_to_back(self.background_rectangle)
