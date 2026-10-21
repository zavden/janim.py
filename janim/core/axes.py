"""Coordinate systems whose maps are read from their live axis geometry."""

import math

import numpy as np

from janim.constants import BLUE, DOWN, GREY_A, GREY_B, LEFT, ORIGIN, UP, WHITE
from ._ranges import linear_range, step_range
from .algebra import norm, rotate_vector
from .functions import ParametricCurve
from .mobject import VGroup, VMobject
from .shapes import Circle, Line
from .transforms import point3


def tick_range(start, stop, step):
    start, stop, step = float(start), float(stop), float(step)
    if step == 0:
        return []
    count = math.floor((stop - start) / step + 1e-6)
    return [start + index * step for index in range(count + 1)]


def _near(first, second):
    return abs(first - second) <= max(
        1e-8,
        math.sqrt(np.finfo(np.float64).eps) * max(abs(first), abs(second)),
    )


class CoordinateObject(VGroup):
    @property
    def group(self):
        """The drawable tree; Python owns it directly instead of wrapping it."""
        return self


class NumberLine(CoordinateObject):
    def __init__(
        self,
        x_range=(-8.0, 8.0, 1.0),
        width=None,
        unit_size=1.0,
        include_ticks=True,
        include_numbers=False,
        tick_size=0.1,
        color=GREY_B,
        stroke_width=2.0,
        line_to_number_direction=DOWN,
        line_to_number_buff=0.25,
        num_decimal_places=0,
        numbers_to_exclude=(),
        big_tick_numbers=(),
        longer_tick_multiple=1.5,
        label_size=0.4,
        include_tip=False,
        tip_config=None,
        decimal_number_config=None,
        **kwargs,
    ):
        self.x_min, self.x_max, self.x_step = map(float, x_range)
        self.line_to_number_direction = point3(line_to_number_direction)
        self.line_to_number_buff = float(line_to_number_buff)
        self.numbers_to_exclude = tuple(numbers_to_exclude)
        self.decimal_number_config = {"num_decimal_places": 0, "font_size": 36, **(decimal_number_config or {})}
        self.tip_config = {"width": 0.25, "length": 0.25, **(tip_config or {})}
        self.include_tip = bool(include_tip)
        self.numbers = VGroup()
        if self.x_min == self.x_max:
            raise ValueError("NumberLine requires distinct range endpoints")
        unit = float(unit_size) if width is None else float(width) / (self.x_max - self.x_min)
        half = 0.5 * unit * (self.x_max - self.x_min)
        self.axis = Line((-half, 0, 0), (half, 0, 0)).set_stroke(color, width=stroke_width)
        self.ticks = VGroup()
        self.labels = VGroup()
        if include_ticks:
            ticks = []
            for value in self.get_tick_range():
                x = (value - 0.5 * (self.x_min + self.x_max)) * unit
                size = tick_size * longer_tick_multiple if any(
                    (_near(value, big) for big in big_tick_numbers),
                ) else tick_size
                ticks.append(Line((x, -size, 0), (x, size, 0)).set_stroke(color, width=stroke_width))
            self.ticks.add(*ticks)
        self.tip = VGroup()
        if include_tip:
            # ManimGL's NumberLine tip: an isosceles triangle whose apex sits on
            # the line's end, the line itself pulled back to the triangle's base
            # (`add_tip` → `reset_endpoints_based_on_tip`, geometry.py:71-82).
            width, length = float(self.tip_config["width"]), float(self.tip_config["length"])
            first, last = self.axis.get_start_and_end()
            triangle = VMobject().set_points_as_corners(
                [(0.0, 0.0, 0.0), (-length, 0.5 * width, 0.0), (-length, -0.5 * width, 0.0), (0.0, 0.0, 0.0)],
            )
            triangle.set_fill(color, 1.0).set_stroke(color, width=stroke_width)
            triangle.shift(last)
            self.tip.add(triangle)
            self.axis.put_start_and_end_on(first, last - np.float32(length) * np.array((1.0, 0.0, 0.0), dtype=np.float32))
        # the children are three (axis, ticks, labels); the tip joins only when asked for
        super().__init__(self.axis, self.ticks, self.labels, *((self.tip,) if include_tip else ()), **kwargs)
        if include_numbers:
            from janim.text.numbers import decimal_string
            from janim.text.text import Text

            direction = point3(line_to_number_direction)
            labels = []
            for value in self.get_tick_range():
                if any(_near(value, excluded) for excluded in numbers_to_exclude):
                    continue
                label = Text(decimal_string(value, num_decimal_places), size=label_size, color=color)
                label.move_to(self.number_to_point(value) + np.float32(line_to_number_buff) * direction)
                labels.append(label)
            self.labels.add(*labels)

    def number_to_point(self, value):
        first, last = self.axis.get_start_and_end()
        if self.include_tip:
            last = last + np.float32(self.tip_config["length"]) * self.get_unit_vector()
        alpha = (float(value) - self.x_min) / (self.x_max - self.x_min)
        return first + np.float32(alpha) * (last - first)

    n2p = number_to_point

    def get_unit_vector(self):
        vector = self.axis.get_vector().astype(np.float64)
        return (vector / norm(vector)).astype(np.float32)

    def get_number_mobject(self, x, direction=None, buff=None, unit=1.0, unit_tex="", **number_config):
        """ManimGL's: a DecimalNumber beside the tick of `x` (number_line.py:161-186)."""
        from janim.text.numbers import DecimalNumber

        config = {**self.decimal_number_config, **number_config}
        if unit_tex:
            config["unit"] = unit_tex
        number = DecimalNumber(x / unit, **config)
        number.next_to(
            self.number_to_point(x),
            self.line_to_number_direction if direction is None else point3(direction),
            buff=self.line_to_number_buff if buff is None else buff,
        )
        return number

    def add_numbers(self, x_values=None, excluding=None, font_size=24, **kwargs):
        """ManimGL's: DecimalNumbers under the ticks, kept as `self.numbers` (number_line.py:199-221)."""
        if x_values is None:
            x_values = self.get_tick_range()
        if excluding is None:
            excluding = self.numbers_to_exclude
        kwargs["font_size"] = font_size
        numbers = VGroup()
        for x in x_values:
            if any(_near(x, value) for value in excluding):
                continue
            numbers.add(self.get_number_mobject(x, **kwargs))
        self.add(numbers)
        self.numbers = numbers
        return numbers

    def point_to_number(self, point):
        first, last = self.axis.get_start_and_end()
        vector = (last - first).astype(np.float64)
        squares = vector * vector
        length2 = (squares[0] + squares[1]) + squares[2]
        if length2 == 0:
            return self.x_min
        products = (point3(point).astype(np.float64) - first.astype(np.float64)) * vector
        alpha = ((products[0] + products[1]) + products[2]) / length2
        return self.x_min + float(alpha) * (self.x_max - self.x_min)

    p2n = point_to_number

    def get_unit_size(self):
        return float(norm(self.axis.get_vector().astype(np.float64))) / (self.x_max - self.x_min)

    def get_tick_range(self):
        return tick_range(self.x_min, self.x_max, self.x_step)

    def get_vector(self):
        return self.axis.get_vector()

    def get_start(self):
        return self.axis.get_start()

    def get_end(self):
        return self.axis.get_end()


class UnitInterval(NumberLine):
    def __init__(self, unit_size=10.0, big_tick_numbers=(0.0, 1.0), num_decimal_places=1, **kwargs):
        super().__init__(
            (0.0, 1.0, 0.1),
            unit_size=unit_size,
            big_tick_numbers=big_tick_numbers,
            num_decimal_places=num_decimal_places,
            **kwargs,
        )


class Axes(CoordinateObject):
    def __init__(
        self,
        x_range=(-8.0, 8.0, 1.0),
        y_range=(-4.0, 4.0, 1.0),
        width=None,
        height=None,
        unit_size=1.0,
        include_numbers=False,
        axis_config=None,
        x_axis_config=None,
        y_axis_config=None,
        z_index=0,
        **kwargs,
    ):
        common = dict(width=width, unit_size=unit_size, include_numbers=include_numbers)
        common.update(kwargs)
        common.update(axis_config or {})
        x_config = {**common, **(x_axis_config or {})}
        y_config = {"line_to_number_direction": LEFT, **common, "width": height, **(y_axis_config or {})}
        self.x_range = tuple(map(float, x_range))
        self.y_range = tuple(map(float, y_range))
        self.x_axis = NumberLine(x_range, **x_config)
        self.y_axis = NumberLine(y_range, **{**y_config, "include_numbers": False}).rotate(math.pi / 2)
        if y_config.get("include_numbers", False):
            self._add_axis_numbers(self.y_axis, y_config)
        self.x_axis.shift(-self.x_axis.number_to_point(0))
        self.y_axis.shift(-self.y_axis.number_to_point(0))
        super().__init__(self.x_axis, self.y_axis, z_index=z_index)
        self.center()

    @staticmethod
    def _add_axis_numbers(axis, config, skip_zero=True):
        from janim.text.numbers import decimal_string
        from janim.text.text import Text

        direction = point3(config.get("line_to_number_direction", DOWN))
        labels = []
        for value in axis.get_tick_range():
            if skip_zero and abs(value) < 1e-8:
                continue
            if any(_near(value, excluded) for excluded in config.get("numbers_to_exclude", ())):
                continue
            label = Text(
                decimal_string(value, config.get("num_decimal_places", 0)),
                size=config.get("label_size", 0.4),
                color=config.get("color", GREY_B),
            )
            label.next_to(
                axis.number_to_point(value),
                direction,
                buff=config.get("line_to_number_buff", 0.25),
            )
            labels.append(label)
        axis.labels.add(*labels)

    def get_x_axis(self):
        return self.x_axis

    def get_y_axis(self):
        return self.y_axis

    def get_origin(self):
        return self.x_axis.number_to_point(0)

    def coords_to_point(self, x, y=0.0):
        # GL's `c2p(x)`: a coordinate not given is the origin's.
        origin = self.get_origin()
        return origin + (self.x_axis.number_to_point(x) - origin) + (self.y_axis.number_to_point(y) - origin)

    c2p = coords_to_point

    def point_to_coords(self, point):
        return self.x_axis.point_to_number(point), self.y_axis.point_to_number(point)

    p2c = point_to_coords

    def plot(
        self,
        function,
        x_range=None,
        n=100,
        color=GREY_A,
        stroke_width=4.0,
        discontinuities=(),
    ):
        first, last = (self.x_axis.x_min, self.x_axis.x_max) if x_range is None else map(float, x_range[:2])
        step = float(x_range[2]) if x_range is not None and len(x_range) >= 3 else (last - first) / n
        xs = step_range(first, last, step)
        if not xs:
            raise ValueError("plot: the x range is empty")
        if xs[-1] < last - 1e-9:
            xs.append(last)
        graph = VMobject().set_stroke(color, width=stroke_width).set_fill(opacity=0)
        graph.underlying_function = function
        graph.x_range = (first, last, step)
        cuts = sorted(map(float, discontinuities))
        segment = []

        def flush():
            if len(segment) >= 2:
                piece = VMobject().set_points_as_corners(segment)
                if graph.has_points():
                    graph.start_new_path(segment[0])
                    graph.append_points(piece.points[1:])
                else:
                    graph.set_points_as_corners(segment)
            segment.clear()

        for index, x in enumerate(xs):
            if index and any(xs[index - 1] < cut <= x for cut in cuts):
                flush()
            segment.append(self.c2p(x, function(x)))
        flush()
        return graph

    get_graph = plot

    def get_graph_label(
        self,
        graph,
        text,
        x=None,
        direction=(1, 1, 0),
        buff=0.2,
        size=0.5,
        color=WHITE,
        via="text",
    ):
        from .annotations import _label_via

        label = _label_via(text, via, size=size, color=color)
        points = graph.get_points()
        if not len(points):
            raise ValueError("a graph label requires a nonempty graph")
        anchor = points[-1] if x is None else min(
            points,
            key=lambda point: abs(self.point_to_coords(point)[0] - float(x)),
        )
        return label.move_to(anchor + np.float32(buff) * point3(direction))

    def update_graph(self, graph, function, x_range=None, n=100):
        first, last = (self.x_axis.x_min, self.x_axis.x_max) if x_range is None else map(float, x_range[:2])
        if len(graph.points) < 3:
            raise ValueError("build the graph with plot before updating it")
        count = (len(graph.points) + 1) // 2
        for index in range(count):
            x = first + (last - first) * index / (count - 1)
            graph.points[2 * index] = self.c2p(x, function(x))
        graph.points[1::2] = np.float32(0.5) * (graph.points[:-2:2] + graph.points[2::2])
        graph.note_changed_data()
        return graph

    def get_parametric_curve(self, function, **kwargs):
        def mapped(time):
            point = function(time)
            return self.c2p(point[0], point[1])

        return ParametricCurve(mapped, **kwargs)

    def get_area(self, function, x0, x1, color=BLUE, opacity=0.35, n=100):
        if isinstance(function, VMobject):
            function = function.underlying_function
        points = [self.c2p(x, function(x)) for x in linear_range(x0, x1, max(n, 2))]
        points.extend((self.c2p(x1, 0), self.c2p(x0, 0), points[0]))
        area = VMobject().set_points_as_corners(points)
        area.set_fill(color, opacity).set_stroke(width=0, opacity=0)
        return area

    def input_to_graph_point(self, x, graph):
        """ManimGL's `i2gp`: the point of `graph` above `x` (through its function when it has one)."""
        function = getattr(graph, "underlying_function", None)
        if function is not None:
            return self.c2p(x, function(x))
        points = graph.get_points()
        if not len(points):
            raise ValueError("input_to_graph_point requires a nonempty graph")
        return min(points, key=lambda point: abs(self.point_to_coords(point)[0] - float(x)))

    i2gp = input_to_graph_point

    def get_riemann_rectangles(
        self,
        graph,
        x_range=None,
        dx=None,
        input_sample_type="left",
        stroke_width=1.0,
        stroke_color="#000000",
        fill_opacity=1.0,
        colors=(BLUE, "#83C167"),
        negative_color="#FC6255",
        stroke_background=True,
        show_signed_area=True,
    ):
        """ManimGL's (coordinate_systems.py:363-411): one rectangle per step, coloured along `colors`."""
        from .colorspace import color_gradient
        from .shapes import Rectangle

        if x_range is None:
            x_range = [self.x_axis.x_min, self.x_axis.x_max]
        if dx is None:
            dx = self.x_axis.x_step
        x_range = list(x_range)
        if len(x_range) < 3:
            x_range = [*x_range, dx]
        x_range[1] = x_range[1] + dx
        xs = np.arange(*x_range)
        rects = []
        for x0, x1 in zip(xs, xs[1:]):
            if input_sample_type == "left":
                sample = x0
            elif input_sample_type == "right":
                sample = x1
            elif input_sample_type == "center":
                sample = 0.5 * x0 + 0.5 * x1
            else:
                raise ValueError("invalid input sample type")
            height_vector = self.i2gp(sample, graph) - self.c2p(sample, 0)
            rect = Rectangle(
                width=float(self.x_axis.n2p(x1)[0] - self.x_axis.n2p(x0)[0]),
                height=float(norm(height_vector.astype(np.float64))),
            )
            rect.positive = height_vector[1] > 0
            rect.move_to(self.c2p(x0, 0), (-1, 1, 0) if rect.positive else (-1, -1, 0))
            rects.append(rect)
        result = VGroup(*rects)
        for rect, color in zip(rects, color_gradient(list(colors), max(len(rects), 1))):
            rect.set_fill(color, fill_opacity)
        result.set_stroke(stroke_color, width=stroke_width)
        if show_signed_area:
            for rect in rects:
                if not rect.positive:
                    rect.set_fill(negative_color, fill_opacity)
        # `stroke_background` (GL's stroke behind the fill) has no renderer flag here
        return result

    def get_v_line(self, x, y=None, color=GREY_B, stroke_width=2.0, line_func=None):
        if y is None and np.ndim(x) == 1:
            # ManimGL's form: `get_v_line(point, line_func=DashedLine, color=GREY_A, stroke_width=2)`
            from .shapes import DashedLine

            point = point3(x)
            foot = self.c2p(self.p2c(point)[0], 0)
            return (DashedLine if line_func is None else line_func)(foot, point).set_stroke(GREY_A if color is GREY_B else color, width=stroke_width)
        if y is None:
            x, y = self.p2c(x)
        return Line(self.c2p(x, 0), self.c2p(x, y)).set_stroke(color, width=stroke_width)

    def get_h_line(self, x, y=None, color=GREY_B, stroke_width=2.0, line_func=None):
        if y is None and np.ndim(x) == 1:
            from .shapes import DashedLine

            point = point3(x)
            foot = self.c2p(0, self.p2c(point)[1])
            return (DashedLine if line_func is None else line_func)(foot, point).set_stroke(GREY_A if color is GREY_B else color, width=stroke_width)
        if y is None:
            x, y = self.p2c(x)
        return Line(self.c2p(0, y), self.c2p(x, y)).set_stroke(color, width=stroke_width)


class NumberPlane(CoordinateObject):
    def __init__(
        self,
        x_range=(-8.0, 8.0, 1.0),
        y_range=(-4.0, 4.0, 1.0),
        width=None,
        height=None,
        background_line_color=BLUE,
        background_stroke_width=2.0,
        faded_line_ratio=4,
        faded_stroke_width=1.0,
        faded_opacity=0.25,
        z_index=0,
        **kwargs,
    ):
        self.axes = Axes(x_range, y_range, width=width, height=height, **kwargs)
        self.background_lines = VGroup()
        self.faded_lines = VGroup()
        xa, ya = self.axes.x_axis, self.axes.y_axis
        xr, yr = xa.get_tick_range(), ya.get_tick_range()

        def make_line(first, last, width, opacity):
            return Line(first, last).set_stroke(background_line_color, width=width, opacity=opacity)

        background = []
        for x in xr:
            if abs(x) >= 1e-8:
                background.append(
                    make_line(self.c2p(x, ya.x_min), self.c2p(x, ya.x_max), background_stroke_width, 1.0),
                )
        for y in yr:
            if abs(y) >= 1e-8:
                background.append(
                    make_line(self.c2p(xa.x_min, y), self.c2p(xa.x_max, y), background_stroke_width, 1.0),
                )
        self.background_lines.add(*background)
        if faded_line_ratio > 0:
            faded = []
            # GL counts interior lines, and its arange includes the
            # measured extra endpoint for some ratios. Coordinates still
            # cross the same f32 n2p/c2p boundary as the rest of the core.
            density = 1 + faded_line_ratio
            dx = (1 / density) * xa.x_step
            dy = (1 / density) * ya.x_step
            for index, x in enumerate(np.arange(xa.x_min, xa.x_max + dx, dx)):
                if abs(x) >= 1e-8 and index % density:
                    faded.append(
                        make_line(
                            self.c2p(x, ya.x_min),
                            self.c2p(x, ya.x_max),
                            faded_stroke_width,
                            faded_opacity,
                        ),
                    )
            for index, y in enumerate(np.arange(ya.x_min, ya.x_max + dy, dy)):
                if abs(y) >= 1e-8 and index % density:
                    faded.append(
                        make_line(
                            self.c2p(xa.x_min, y),
                            self.c2p(xa.x_max, y),
                            faded_stroke_width,
                            faded_opacity,
                        ),
                    )
            self.faded_lines.add(*faded)
        super().__init__(self.faded_lines, self.background_lines, self.axes, z_index=z_index)

    def coords_to_point(self, x, y=0.0):
        return self.axes.c2p(x, y)

    c2p = coords_to_point

    def point_to_coords(self, point):
        return self.axes.p2c(point)

    p2c = point_to_coords

    def get_origin(self):
        return self.axes.get_origin()

    def number_to_point(self, value):
        return self.c2p(value.real, value.imag)

    n2p = number_to_point

    def point_to_number(self, point):
        return complex(*self.p2c(point))

    p2n = point_to_number


ComplexPlane = NumberPlane


class PolarPlane(CoordinateObject):
    def __init__(
        self,
        r_max=4.0,
        n_radii=8,
        n_circles=4,
        radius=3.0,
        color=BLUE,
        stroke_width=1.5,
        opacity=0.6,
        **kwargs,
    ):
        self.r_max = float(r_max)
        self.axis = Line(ORIGIN, (radius, 0, 0))
        self.axis.set_stroke(color, width=stroke_width, opacity=opacity if n_radii > 0 else 0.0)
        children = [self.axis]
        for index in range(1, n_radii):
            angle = index * math.tau / n_radii
            line = Line(ORIGIN, (radius * math.cos(angle), radius * math.sin(angle), 0))
            children.append(line.set_stroke(color, width=stroke_width, opacity=opacity))
        for index in range(1, n_circles + 1):
            circle = Circle(radius=radius * index / n_circles)
            children.append(circle.set_stroke(color, width=stroke_width, opacity=opacity).set_fill(opacity=0))
        super().__init__(*children, **kwargs)

    def polar_to_point(self, theta, radius):
        origin = self.axis.get_start()
        unit_x = (self.axis.get_end() - origin).astype(np.float64) / self.r_max
        unit_y = rotate_vector(unit_x, math.tau / 4)
        result = origin.astype(
            np.float64,
        ) + radius * (math.cos(
            theta,
        ) * unit_x + math.sin(
            theta,
        ) * unit_y.astype(
            np.float64,
        ))
        return result.astype(np.float32)


class ThreeDAxes(Axes):
    """Three NumberLines through one origin. The numbers are placed after the
    axes stand, the y and z labels to the LEFT, and the x axis keeps its zero.

    An `Axes` as in ManimGL (`ThreeDAxes(Axes)`): the graph, label, area and
    guide-line helpers work on the xy plane; `coords_to_point` takes z too.
    """

    def __init__(
        self,
        x_range=(-4.0, 4.0, 1.0),
        y_range=(-4.0, 4.0, 1.0),
        z_range=(-3.0, 3.0, 1.0),
        width=None,
        height=None,
        depth=None,
        **kwargs,
    ):
        numbers = bool(kwargs.get("include_numbers", False))
        config = {**kwargs, "include_numbers": False}
        self.x_range = tuple(map(float, x_range))
        self.y_range = tuple(map(float, y_range))
        self.z_range = tuple(map(float, z_range))
        self.x_axis = NumberLine(x_range, width=width, **config)
        self.y_axis = NumberLine(y_range, width=height, **config)
        self.z_axis = NumberLine(z_range, width=depth, **config)
        self.y_axis.rotate(math.pi / 2)
        self.z_axis.rotate(-math.pi / 2, axis=UP)
        if numbers:
            Axes._add_axis_numbers(self.x_axis, config, skip_zero=False)
            Axes._add_axis_numbers(self.y_axis, {"line_to_number_direction": LEFT, **config})
            Axes._add_axis_numbers(self.z_axis, {"line_to_number_direction": LEFT, **config})
        for axis in (self.x_axis, self.y_axis, self.z_axis):
            axis.shift(-axis.number_to_point(0))
        CoordinateObject.__init__(self, self.x_axis, self.y_axis, self.z_axis)
        self.center()

    def get_z_axis(self):
        return self.z_axis

    def get_parametric_curve(self, function, **kwargs):
        def mapped(time):
            return self.coords_to_point(*function(time))

        return ParametricCurve(mapped, **kwargs)

    def get_origin(self):
        return self.x_axis.number_to_point(0)

    def coords_to_point(self, x, y=0.0, z=0.0):
        origin = self.get_origin()
        point = origin + (self.x_axis.number_to_point(x) - origin)
        point = point + (self.y_axis.number_to_point(y) - origin)
        return point + (self.z_axis.number_to_point(z) - origin)

    c2p = coords_to_point

    def point_to_coords(self, point):
        return self.x_axis.point_to_number(point), self.y_axis.point_to_number(point), self.z_axis.point_to_number(point)

    p2c = point_to_coords


def coords_to_point(axes, *coordinates):
    return axes.coords_to_point(*coordinates)


def point_to_coords(axes, point):
    return axes.point_to_coords(point)


c2p = coords_to_point
p2c = point_to_coords


def number_to_point(axis, value):
    return axis.number_to_point(value)


def point_to_number(axis, point):
    return axis.point_to_number(point)


def polar_to_point(plane, theta, radius):
    return plane.polar_to_point(theta, radius)
