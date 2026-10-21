"""Matrices and tables of mobjects."""

import re

from janim.constants import GREY_B, LEFT, RIGHT, WHITE, YELLOW
from .annotations import _as_label
from .mobject import Mobject, VGroup, VMobject
from .shapes import Line


def matrix_bracket(height, width, left=True, color=WHITE, stroke_width=4.0):
    import numpy as np

    half = np.float32(height) / np.float32(2)
    width = np.float32(width) * (1 if left else -1)
    bracket = VMobject().set_points_as_corners(
        ((width, half, 0), (0, half, 0), (0, -half, 0), (width, -half, 0)),
    )
    return bracket.set_stroke(color, width=stroke_width).set_fill(opacity=0)


def _grid(entries):
    rows = []
    for row in entries:
        if isinstance(row, (str, bytes)):
            raise TypeError("a matrix row must be a sequence of cells, not a string")
        rows.append(list(row))
    if not rows or not rows[0] or any(len(row) != len(rows[0]) for row in rows):
        raise ValueError("entries must form a nonempty rectangular grid")
    return rows


def _cell(value, factory):
    if isinstance(value, Mobject):
        return value
    if factory is None:
        return _as_label(value)
    result = factory(str(value))
    if not isinstance(result, Mobject):
        raise TypeError("the cell factory must return a Mobject")
    return result


class _Cells(VMobject):
    def get_entries(self):
        return self.submobjects[0]

    def _indexed_cells(self):
        cells = []
        for child in self.get_family()[1:]:
            for key in child.get_keys():
                match = re.fullmatch(r"\((\d+),(\d+)\)", key)
                if match:
                    cells.append((int(match[1]), int(match[2]), child))
        return sorted(cells, key=lambda entry: entry[:2])

    def get_rows(self):
        def construct():
            cells = self._indexed_cells()
            if not cells:
                raise ValueError("this matrix or table has no indexed cells")
            rows = {}
            for row, column, mob in cells:
                rows.setdefault(row, []).append(mob)
            return VGroup(*(VGroup(*rows.get(index, ())) for index in range(1, max(rows) + 1)))

        return self._memoized_group("rows", construct)

    def get_columns(self):
        def construct():
            cells = self._indexed_cells()
            if not cells:
                raise ValueError("this matrix or table has no indexed cells")
            columns = {}
            for row, column, mob in cells:
                columns.setdefault(column, []).append(mob)
            return VGroup(*(VGroup(*columns.get(index, ())) for index in range(1, max(columns) + 1)))

        return self._memoized_group("columns", construct)

    def get_cell(self, row, column=None):
        """Return the one-based (row, column) cell, including labels."""
        if column is None:
            row, column = row
        matches = self.find_by_key(f"({row},{column})")
        if matches:
            return matches[0]
        raise KeyError(f"no cell ({row},{column})")


class Matrix(_Cells):
    def __init__(
        self,
        entries,
        cell=None,
        h_buff=1.3,
        v_buff=0.8,
        bracket_h_buff=0.2,
        bracket_v_buff=0.25,
        bracket_width=0.22,
        color=WHITE,
        stroke_width=4.0,
        **kwargs,
    ):
        if cell is None:
            from janim.text.tex import Tex

            cell = Tex
        rows = _grid(entries)
        super().__init__(**kwargs)
        cells = []
        for i, row in enumerate(rows):
            for j, value in enumerate(row):
                mob = _cell(value, cell)
                mob.set_key(f"({i + 1},{j + 1})")
                mob.move_to((j * h_buff, -i * v_buff, 0))
                cells.append(mob)
        body = VGroup(*cells).center()
        height = float(body.get_height()) + 2 * bracket_v_buff
        left = matrix_bracket(height, bracket_width, color=color, stroke_width=stroke_width)
        right = matrix_bracket(height, bracket_width, left=False, color=color, stroke_width=stroke_width)
        left.next_to(body, LEFT, buff=bracket_h_buff)
        right.next_to(body, RIGHT, buff=bracket_h_buff)
        self.add(body, VGroup(left, right)).center()

    def get_brackets(self):
        return self.submobjects[1]


MatrixMobject = Matrix


class TexMatrix(Matrix):
    def __init__(self, entries, tex_config=None, **kwargs):
        from janim.text.tex import Tex

        options = {} if tex_config is None else dict(tex_config)
        super().__init__(entries, cell=lambda value: Tex(value, **options), **kwargs)


class Table(_Cells):
    def __init__(
        self,
        entries,
        cell=None,
        row_labels=None,
        col_labels=None,
        h_buff=0.9,
        v_buff=0.6,
        include_outer_lines=False,
        line_color=GREY_B,
        line_width=2.0,
        label_color=YELLOW,
        **kwargs,
    ):
        entries = _grid(entries)
        rows, columns = len(entries), len(entries[0])
        if row_labels is not None and len(row_labels) != rows:
            raise ValueError("row_labels must match the number of rows")
        if col_labels is not None and len(col_labels) != columns:
            raise ValueError("col_labels must match the number of columns")
        offset_row, offset_column = int(col_labels is not None), int(row_labels is not None)
        total_rows, total_columns = rows + offset_row, columns + offset_column
        grid = [[None] * total_columns for _ in range(total_rows)]
        for i, row in enumerate(entries):
            for j, value in enumerate(row):
                grid[i + offset_row][j + offset_column] = _cell(value, cell)
        if col_labels is not None:
            for j, value in enumerate(col_labels):
                grid[0][j + offset_column] = _cell(value, cell).set_color(label_color)
        if row_labels is not None:
            for i, value in enumerate(row_labels):
                grid[i + offset_row][0] = _cell(value, cell).set_color(label_color)
        widths = [max(
            (float(grid[i][j].get_width()) if grid[i][j] is not None else 0 for i in range(total_rows)),
        ) for j in range(
            total_columns,
        )]
        heights = [max(float(mob.get_height()) if mob is not None else 0 for mob in row) for row in grid]
        xs, ys = [], []
        accumulated = 0.0
        for width in widths:
            xs.append(accumulated + width / 2)
            accumulated += width + h_buff
        accumulated = 0.0
        for height in heights:
            ys.append(-(accumulated + height / 2))
            accumulated += height + v_buff
        cells = []
        for i, row in enumerate(grid):
            for j, mob in enumerate(row):
                if mob is not None:
                    mob.set_key(f"({i + 1},{j + 1})").move_to((xs[j], ys[i], 0))
                    cells.append(mob)
        x0, x1 = xs[0] - widths[0] / 2 - h_buff / 2, xs[-1] + widths[-1] / 2 + h_buff / 2
        y0, y1 = ys[-1] - heights[-1] / 2 - v_buff / 2, ys[0] + heights[0] / 2 + v_buff / 2
        lines = []
        first = 0 if include_outer_lines else 1
        for i in range(first, total_rows + int(include_outer_lines)):
            y = ys[i] + heights[i] / 2 + v_buff / 2 if i < total_rows else y0
            lines.append(Line((x0, y, 0), (x1, y, 0)).set_stroke(line_color, width=line_width))
        for j in range(first, total_columns + int(include_outer_lines)):
            x = xs[j] - widths[j] / 2 - h_buff / 2 if j < total_columns else x1
            lines.append(Line((x, y0, 0), (x, y1, 0)).set_stroke(line_color, width=line_width))
        super().__init__(**kwargs)
        self.add(VGroup(*cells), VGroup(*lines)).center()

    def get_lines(self):
        return self.submobjects[1]


class MobjectTable(Table):
    def __init__(self, entries, **kwargs):
        entries = _grid(entries)
        if any(not isinstance(value, Mobject) for row in entries for value in row):
            raise TypeError("MobjectTable accepts only Mobjects; use Table with a cell factory")
        super().__init__(entries, **kwargs)


class MathTable(Table):
    def __init__(self, entries, cell=None, **kwargs):
        if cell is None:
            from janim.text.tex import Tex

            cell = lambda value: Tex(value, size=0.5)
        super().__init__(entries, cell=cell, **kwargs)


class DecimalTable(Table):
    def __init__(self, entries, num_decimal_places=1, **kwargs):
        from numbers import Real

        def format_cell(value):
            if isinstance(value, Mobject):
                return value
            if isinstance(value, Real):
                return str(round(value)) if num_decimal_places <= 0 else f"{value:.{num_decimal_places}f}"
            return str(value)

        formatted = [
            [format_cell(value) for value in row]
            for row in _grid(entries)
        ]
        super().__init__(formatted, **kwargs)


class IntegerTable(DecimalTable):
    def __init__(self, entries, **kwargs):
        super().__init__(entries, num_decimal_places=0, **kwargs)
