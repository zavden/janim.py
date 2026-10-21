"""Vector fields and stream lines over a coordinate system, .

The layout, widths and colours follow manimlib's vector_field.py: eight points per arrow (seven of them a two-segment polyline plus
a separator anchor), the 3b1b colormap over the magnitude, and RK4 solutions
seeded on a jittered grid. The jitter is a counter hash (splitmix64), not a
random stream, so every frame is reproducible.
"""
import math

import numpy as np

from janim.constants import GREY_A

from .axes import NumberPlane, ThreeDAxes
from .mobject import VGroup, VMobject

_CMAP_3B1B = (
    (np.float32(0x1C / 255), np.float32(0x75 / 255), np.float32(0x8A / 255)),   # BLUE_E
    (np.float32(0x83 / 255), np.float32(0xC1 / 255), np.float32(0x67 / 255)),   # GREEN
    (np.float32(0xFF / 255), np.float32(0xFF / 255), np.float32(0x00 / 255)),   # YELLOW
    (np.float32(0xFC / 255), np.float32(0x62 / 255), np.float32(0x55 / 255)),   # RED
)
_MASK64 = (1 << 64) - 1


def colormap_3b1b(value):
    """get_colormap_from_colors: clip to [0, 1], lerp between adjacent colours (Float32)."""
    count = len(_CMAP_3B1B)
    a = np.float32(min(max(np.float32(value), np.float32(0)), np.float32(1))) * np.float32(count - 1)
    i = min(int(math.floor(a)), count - 2)
    t = np.float32(a - np.float32(i))
    low, high = _CMAP_3B1B[i], _CMAP_3B1B[i + 1]
    one_minus = np.float32(np.float32(1) - t)
    return tuple(np.float32(one_minus * low[k] + t * high[k]) for k in range(3))


def _splitmix64(x):
    x = (x + 0x9E3779B97F4A7C15) & _MASK64
    x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
    x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & _MASK64
    return x ^ (x >> 31)


def hash01(k1, k2=0, k3=0):
    """A uniform in [0, 1) from a counter tuple: the replacement for np.random."""
    h = _splitmix64(
        _splitmix64(
            _splitmix64((int(k1) + 0x9E37) & _MASK64) ^ ((int(k2) * 0x85EB) & _MASK64),
        ) ^ ((int(k3) * 0xC2B2) & _MASK64),
    )
    return float(h >> 11) * 2.0 ** -53


def _julia_math():
    from . import _julia_math

    return _julia_math


def _axis_range(axis):
    return axis.x_min, axis.x_max, axis.x_step


def _all_ranges(coordinate_system):
    if isinstance(coordinate_system, ThreeDAxes):
        return [_axis_range(axis) for axis in (coordinate_system.x_axis, coordinate_system.y_axis, coordinate_system.z_axis)]
    if isinstance(coordinate_system, NumberPlane):
        return _all_ranges(coordinate_system.axes)
    return [_axis_range(coordinate_system.x_axis), _axis_range(coordinate_system.y_axis)]


def sample_coords(coordinate_system, density):
    """The grid of vector_field.py: arange(lo, hi + s, s) per axis, last axis fastest."""
    from ._ranges import step_range

    axes_values = []
    for low, high, step in _all_ranges(coordinate_system):
        s = step / float(density)
        axes_values.append(step_range(low, high + s / 2, s))
    if len(axes_values) == 2:
        return [(x, y) for x in axes_values[0] for y in axes_values[1]]
    return [(x, y, z) for x in axes_values[0] for y in axes_values[1] for z in axes_values[2]]


def _c2p(coordinate_system, coords):
    return coordinate_system.coords_to_point(*(float(value) for value in coords))


def _sum_squares(values):
    total = 0.0
    for index, value in enumerate(values):
        square = float(value) * float(value)
        total = square if index == 0 else total + square
    return total


def ode_solution_points(function, state0, time, *, dt=0.01):
    """RK4 samples of the flow from `state0`, one per `dt` (arange(0, time, dt) length)."""
    count = max(math.ceil(float(time) / float(dt)), 1)
    dimension = len(state0)
    h = float(dt)
    state = tuple(float(value) for value in state0)
    out = [state]
    for _ in range(1, count):
        k1 = function(state)
        k2 = function(tuple(state[i] + h / 2 * k1[i] for i in range(dimension)))
        k3 = function(tuple(state[i] + h / 2 * k2[i] for i in range(dimension)))
        k4 = function(tuple(state[i] + h * k3[i] for i in range(dimension)))
        state = tuple(state[i] + h / 6 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]) for i in range(dimension))
        out.append(state)
    return out


class VectorField(VMobject):
    """Arrows of `func(coords)` on a grid of the coordinate system (one polyline per arrow)."""

    def __init__(
        self,
        func,
        coordinate_system,
        *,
        density=2.0,
        magnitude_range=None,
        color=None,
        stroke_width=3.0,
        stroke_opacity=1.0,
        tip_width_ratio=4.0,
        tip_len_to_width=0.01,
        max_vect_len=None,
        max_vect_len_to_step_size=0.8,
        sample_coords=None,
        **kwargs,
    ):
        coords = globals()["sample_coords"](coordinate_system, density) if sample_coords is None else list(sample_coords)
        n = len(coords)
        points = np.array([_c2p(coordinate_system, c) for c in coords], dtype=np.float32).reshape(n, 3)
        if max_vect_len is None:
            delta = points[1] - points[0]
            max_len = float(max_vect_len_to_step_size) * float(np.sqrt(np.float32(_sum_squares_f32(delta))))
        else:
            max_len = float(max_vect_len) * coordinate_system.x_axis.get_unit_size()
        if magnitude_range is None and color is None:
            magnitude_range = (0.0, max(math.sqrt(_sum_squares(func(c))) for c in coords))
        base = np.ones(8 * n - 1, dtype=np.float32)
        for k in range(n):
            base[8 * k + 4] = np.float32(tip_width_ratio)
            base[8 * k + 5] = np.float32(tip_width_ratio / 2)
            base[8 * k + 6] = np.float32(0)
            if 8 * k + 7 < 8 * n - 1:
                base[8 * k + 7] = np.float32(0)
        super().__init__(
            stroke_color=GREY_A if color is None else color,
            stroke_opacity=stroke_opacity,
            stroke_width=stroke_width,
            **kwargs,
        )
        self.set_points(np.zeros((8 * n - 1, 3), dtype=np.float32))
        self.func = func
        self.coordinate_system = coordinate_system
        self.sample_coords = coords
        self.sample_points = points
        self.stroke_width_value = float(stroke_width)
        self.tip_width_ratio = float(tip_width_ratio)
        self.tip_len_to_width = float(tip_len_to_width)
        self.max_displayed_vect_len = max_len
        self.magnitude_range = None if magnitude_range is None else (float(magnitude_range[0]), float(magnitude_range[1]))
        self.base_width = base
        self.time = 0.0
        self.update_vectors()

    @property
    def mob(self):
        """ManimGL holds the arrows in `vf.mob`; here the field IS the VMobject."""
        return self

    def update_vectors(self):
        jm = _julia_math()
        tip_width = self.tip_width_ratio * self.stroke_width_value
        tip_len = self.tip_len_to_width * tip_width
        origin = np.asarray(self.coordinate_system.get_origin(), dtype=np.float32)
        max_len = self.max_displayed_vect_len
        points = self.points
        widths = self.stroke_width
        rgba = self.stroke_rgba
        low, high = (0.0, 1.0) if self.magnitude_range is None else self.magnitude_range
        w = np.float32(self.stroke_width_value)
        count = len(points)
        for k, c in enumerate(self.sample_coords):
            out = self.func(c)
            coord_norm = math.sqrt(_sum_squares(out[i] for i in range(len(c))))
            v = np.asarray(_c2p(self.coordinate_system, out[:len(c)]), dtype=np.float32) - origin
            norm_v = np.float32(np.sqrt(np.float32(_sum_squares_f32(v))))
            unit = v / norm_v if norm_v > 0 else np.zeros(3, dtype=np.float32)
            drawn = max_len * jm.tanh(float(norm_v) / max_len) if max_len < math.inf else float(norm_v)
            to_head_base = max(drawn - tip_len, 0.0)
            base = 8 * k
            b = points[base] = self.sample_points[k]
            hb = points[base + 2] = b + np.float32(to_head_base) * unit
            points[base + 4] = hb
            tip = points[base + 6] = b + np.float32(drawn) * unit
            points[base + 1] = (b + hb) / np.float32(2)
            points[base + 3] = hb
            points[base + 5] = (hb + tip) / np.float32(2)
            if base + 7 < count:
                points[base + 7] = tip
            scalar = np.float32(min(max(drawn / tip_len, 0.0), 1.0))
            stop = min(base + 8, count)
            if self.magnitude_range is None:
                widths[base:stop] = scalar * w * self.base_width[base:stop]
            else:
                r, g, bch = colormap_3b1b((coord_norm - low) / (high - low))
                widths[base:stop] = scalar * w * self.base_width[base:stop]
                rgba[base:stop, 0] = r
                rgba[base:stop, 1] = g
                rgba[base:stop, 2] = bch
        self.note_changed_data()
        return self


def _sum_squares_f32(vector):
    x, y, z = (np.float32(value) for value in vector)
    return (x * x + y * y) + z * z


class TimeVaryingVectorField(VectorField):
    """A VectorField whose `time_func(coords, t)` follows the scene clock through an updater."""

    def __init__(self, time_func, coordinate_system, **kwargs):
        clock = [0.0]
        super().__init__(lambda c: time_func(c, clock[0]), coordinate_system, **kwargs)

        def advance(mob, dt):
            clock[0] += dt
            mob.time = clock[0]
            mob.update_vectors()

        self.add_updater(advance)


class StreamLines(VGroup):
    """RK4 flow lines of `func` from a jittered grid, coloured by magnitude by default."""

    def __init__(
        self,
        func,
        coordinate_system,
        *,
        density=1.0,
        n_repeats=1,
        noise_factor=None,
        solution_time=3.0,
        dt=0.05,
        stroke_width=1.0,
        stroke_color=GREY_A,
        stroke_opacity=1.0,
        color_by_magnitude=True,
        magnitude_range=(0.0, 2.0),
        taper_stroke_width=False,
        jitter_seed=0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        cs = coordinate_system
        base_coords = sample_coords(cs, density)
        dimension = len(base_coords[0])
        nf = (cs.x_axis.get_unit_size() / float(density)) * 0.5 if noise_factor is None else float(noise_factor)
        counter = 0
        for _ in range(int(n_repeats)):
            for c in base_coords:
                counter += 1
                seed = tuple(c[i] + nf * hash01(jitter_seed, counter, i + 1) for i in range(dimension))
                solution = ode_solution_points(func, seed, solution_time, dt=dt)
                line = VMobject()
                line.set_points_smoothly(np.array([_c2p(cs, s) for s in solution], dtype=np.float32))
                if color_by_magnitude:
                    low, high = float(magnitude_range[0]), float(magnitude_range[1])
                    for i, p in enumerate(line.points):
                        pc = cs.point_to_coords(p)
                        out = func(tuple(float(pc[j]) for j in range(dimension)))
                        magnitude = math.sqrt(_sum_squares(out[j] for j in range(dimension)))
                        r, g, b = colormap_3b1b((magnitude - low) / (high - low))
                        line.stroke_rgba[i] = (r, g, b, np.float32(stroke_opacity))
                else:
                    line.set_stroke(stroke_color, opacity=stroke_opacity)
                if taper_stroke_width:
                    n = len(line.points)
                    for i in range(n):
                        t = 0.0 if n == 1 else i / (n - 1)
                        line.stroke_width[i] = np.float32(stroke_width * (1 - abs(2 * t - 1)))
                else:
                    line.stroke_width[:] = np.float32(stroke_width)
                self.add(line)
        self.func = func
        self.coordinate_system = cs
        self.virtual_time = float(solution_time)
        self.stroke_width_value = float(stroke_width)

    @property
    def group(self):
        return self


class AnimatedStreamLines(VGroup):
    """The stream lines with a travelling gaussian window of width, lagged per line."""

    def __init__(
        self,
        stream_lines,
        *,
        lag_range=4.0,
        rate_multiple=1.0,
        time_width=1.0,
        taper_width=0.05,
        phase_seed=1,
        **kwargs,
    ):
        super().__init__(**kwargs)
        lines = list(stream_lines.submobjects)
        tw = float(taper_width)

        def kern(x):
            if x < tw:
                return x
            return 1.0 - x if x > 1 - tw else 1.0

        base = []
        for line in lines:
            n = len(line.stroke_width)
            base.append(
                np.array(
                    [line.stroke_width[j] * kern(0.0 if n == 1 else j / (n - 1)) for j in range(n)],
                    dtype=np.float32,
                ),
            )
        self.stream_lines = stream_lines
        self.times = [-float(lag_range) * hash01(phase_seed, i + 1) for i in range(len(lines))]
        self.base_widths = base
        self.run_time = stream_lines.virtual_time / float(rate_multiple)
        self.time_width = float(time_width)
        for line in lines:
            self.add(line)
        self.add_updater(lambda mob, dt: mob.advance_flow(dt))
        self.advance_flow(0.0)

    @property
    def group(self):
        return self

    def advance_flow(self, dt):
        jm = _julia_math()
        tw = self.time_width
        sigma = tw / 6
        for i, line in enumerate(self.submobjects):
            self.times[i] += dt
            alpha = math.fmod(max(self.times[i], 0.0), self.run_time) / self.run_time
            mu = -tw / 2 + (1 + tw) * alpha
            widths = line.stroke_width
            base = self.base_widths[i]
            n = len(widths)
            for j in range(n):
                x = 0.0 if n == 1 else j / (n - 1)
                z = (x - mu) / sigma
                widths[j] = np.float32(0) if abs(x - mu) > 3 * sigma else base[j] * np.float32(jm.exp(-0.5 * z * z))
            line.note_changed_data()
        return self
