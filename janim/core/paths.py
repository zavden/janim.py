"""Interleaved quadratic VMobject paths."""

import math
import operator

import numpy as np

from ._atan import scalar_atan2

from .algebra import _normalize, apply_matrix_rows, norm, rotation_between_vectors
from .bezier import (
    bezier,
    cubic_to_two_quadratics,
    insert_n_curves,
    integer_interpolate,
    inverse_interpolate,
    partial_quadratic_bezier_points,
    polyline_length,
    quadratic_bezier_points_for_arc,
    quadratic_point,
    smooth_quadratic_handles,
)
from .transforms import point3


class PathMixin:
    def set_anchors_and_handles(self, anchors, handles):
        anchors = np.asarray(anchors, dtype=np.float32).reshape(-1, 3)
        handles = np.asarray(handles, dtype=np.float32).reshape(-1, 3)
        if not len(anchors):
            return self.clear_points()
        if len(anchors) != len(handles) + 1:
            raise ValueError("n handles need n+1 anchors")
        points = np.empty((2 * len(anchors) - 1, 3), dtype=np.float32)
        points[::2], points[1::2] = anchors, handles
        return self.set_points(points)

    def set_points_as_corners(self, corners):
        anchors = np.asarray(corners, dtype=np.float32).reshape(-1, 3)
        handles = (anchors[:-1] + anchors[1:]) / np.float32(2)
        return self.set_anchors_and_handles(anchors, handles)

    def start_new_path(self, point):
        return self.append_points([self.points[-1], point3(point)]) if self.has_points() else self.set_points([point3(point)])

    def add_line_to(self, point):
        if not self.has_points():
            raise ValueError("add_line_to needs a start; call start_new_path first")
        target = point3(point)
        return self.append_points([(self.points[-1] + target) / np.float32(2), target])

    def add_quadratic_bezier_curve_to(self, handle, anchor):
        if not self.has_points():
            raise ValueError("a quadratic needs a start; call start_new_path first")
        return self.append_points([point3(handle), point3(anchor)])

    add_quadratic_bezier_to = add_quadratic_bezier_curve_to          # alias

    def set_points_by_ends(self, start, end, buff=0, path_arc=0):
        """A line or arc from start to end, trimmed by `buff`, on any VMobject."""
        self.clear_points().start_new_path(start).add_arc_to(end, path_arc)
        if buff > 0:
            chord = float(norm(point3(end) - point3(start)))
            length = chord * path_arc / (2 * math.sin(path_arc / 2)) if path_arc > 0 else chord
            if length > 0:
                alpha = min(buff / length, 0.5)
                self.pointwise_become_partial(self, alpha, 1 - alpha)
        return self

    def add_cubic_bezier_curve_to(self, handle1, handle2, anchor):
        if not self.has_points():
            raise ValueError("a cubic needs a start; call start_new_path first")
        first, middle, second = cubic_to_two_quadratics(self.points[-1], handle1, handle2, anchor)
        return self.append_points([first, middle, second, point3(anchor)])

    def close_path(self):
        if self.has_points():
            first = self.get_subpaths()[-1][0]
            if np.any(np.abs(self.points[-1] - first) > np.float32(1e-8)):
                self.add_line_to(first)
        return self

    def add_subpath(self, points):
        points = np.asarray(points, dtype=np.float32).reshape(-1, 3)
        if not len(points):
            return self
        if not self.has_points():
            return self.set_points(points)
        if not np.all(np.abs(points[0] - self.points[-1]) <= np.float32(1e-8)):
            self.start_new_path(points[0])
        return self.append_points(points[1:])

    def append_vectorized_mobject(self, vmobject):
        """`vmobject`'s path as a new subpath, its per-point style kept."""
        count = len(vmobject.points)
        self.add_subpath(vmobject.points)
        if count == 0:
            return self
        total = len(self.points)
        self.stroke_rgba[total - count:] = vmobject.stroke_rgba
        self.fill_rgba[total - count:] = vmobject.fill_rgba
        self.stroke_width[total - count:] = vmobject.stroke_width
        return self.note_changed_data()

    def prepare_for_nonlinear_transform(self, num_inserted_curves=50):
        """ManimGL's: every member with points gets at least `num_inserted_curves` curves and smooths after a function."""
        for member in self.family_members_with_points():
            num_curves = member.get_num_curves()
            if num_inserted_curves > num_curves:
                member.insert_n_curves(num_inserted_curves - num_curves)
            member.make_smooth_after_applying_functions = True
        return self

    def add_arc_to(self, point, angle, n_components=None, threshold=1e-3):
        if not self.has_points():
            raise ValueError("an arc needs a start; call start_new_path first")
        if abs(angle) < threshold:
            return self.add_line_to(point)
        count = math.ceil(8 * abs(angle) / math.tau) if n_components is None else operator.index(n_components)
        points = quadratic_bezier_points_for_arc(angle, count)
        tail = self.points[-1].copy()
        target_vector = point3(point) - tail
        current_vector = points[-1] - points[0]
        matrix = rotation_between_vectors(current_vector, target_vector)
        factor = norm(target_vector) / norm(current_vector)
        rotated = (np.float64(factor) * apply_matrix_rows(points, matrix)).astype(np.float32)
        delta = tail - rotated[0]
        return self.append_points(rotated[1:] + delta)

    def get_num_curves(self):
        return len(self.points) // 2

    def get_anchors(self):
        return self.points[::2]

    def get_handles(self):
        return self.points[1::2]

    def get_vertices(self):
        return self.get_anchors()[:-1]

    def get_nth_curve_points(self, index):
        index = operator.index(index)
        if not 0 <= index < self.get_num_curves():
            raise IndexError(f"curve {index} does not exist")
        return self.points[2 * index:2 * index + 3]

    def get_nth_curve_function(self, index):
        return bezier(self.get_nth_curve_points(index))

    def get_bezier_tuples(self):
        return (self.get_nth_curve_points(index) for index in range(self.get_num_curves()))

    def get_subpath_end_indices(self):
        if self.subpath_end_indices is None:
            count = (len(self.points) - 1) // 2
            if count <= 0:
                self.subpath_end_indices = np.array([len(self.points) - 1], dtype=np.intp)
            else:
                anchors = self.points[:2 * count:2]
                handles = self.points[1:2 * count:2]
                next_anchors = self.points[2:2 * count + 1:2]
                ends = np.all(anchors == handles, axis=1) & np.any(np.abs(handles - next_anchors) > np.float32(1e-4), axis=1)
                self.subpath_end_indices = np.append(2 * np.flatnonzero(ends), len(self.points) - 1)
        return self.subpath_end_indices

    def get_subpaths(self):
        if not self.has_points():
            return []
        ends = self.get_subpath_end_indices()
        starts = [0, *(ends[:-1] + 2)]
        return [self.points[start:end + 1] for start, end in zip(starts, ends)]

    def get_start(self):
        return self.points[0].copy()

    def get_end(self):
        return self.points[-1].copy()

    def get_start_and_end(self):
        return self.get_start(), self.get_end()

    def get_vector(self):
        return self.get_end() - self.get_start()

    def get_unit_vector(self):
        vector = self.get_vector().astype(np.float64)
        return _normalize(vector).astype(np.float32)

    def get_angle(self):
        vector = self.get_vector()
        return scalar_atan2(float(vector[1]), float(vector[0]))

    def get_length(self):
        return float(norm(self.get_vector().astype(np.float64)))

    def set_length(self, length, **kwargs):
        current = self.get_length()
        if current <= 1e-8:
            raise ValueError("this path has no endpoint distance to scale")
        return self.scale(length / current, **kwargs)

    def set_angle(self, angle, about_point=None):
        pivot = self.get_start() if about_point is None else point3(about_point)
        return self.rotate(angle - self.get_angle(), about_point=pivot)

    def quick_point_from_proportion(self, alpha):
        count = self.get_num_curves()
        if count == 0:
            raise ValueError("a path without curves has no points by proportion")
        index, residue = integer_interpolate(0, count, alpha)
        return quadratic_point(self.get_nth_curve_points(index), residue)

    def curve_and_prop_of_partial_point(self, alpha):
        count = self.get_num_curves()
        if count == 0:
            raise ValueError("a path without curves has no points by proportion")
        if alpha <= 0:
            return 0, 0.0
        anchors, handles, following = self.points[:-2:2], self.points[1::2], self.points[2::2]
        lengths = norm(following - anchors).astype(np.float64)
        lengths[np.all(np.abs(handles - anchors) < np.float32(1e-8), axis=1)] = 0
        partials = np.concatenate(([0.0], np.add.accumulate(lengths)))
        full = partials[-1]
        if full == 0:
            return count - 1, 1.0
        index = min(int(np.searchsorted(partials, full * alpha, side="left")), count)
        if index == 0:
            return 0, 0.0
        residue = inverse_interpolate(partials[index - 1] / full, partials[index] / full, alpha)
        return index - 1, float(residue)

    def point_from_proportion(self, alpha):
        if self.get_num_curves() == 0:
            raise ValueError("a path without curves has no points by proportion")
        if alpha <= 0:
            return self.get_start()
        if alpha >= 1:
            return self.get_end()
        index, residue = self.curve_and_prop_of_partial_point(alpha)
        return quadratic_point(self.get_nth_curve_points(index), residue)

    def get_arc_length(self, n_sample_points=None):
        if n_sample_points is not None:
            count = operator.index(n_sample_points)
            if count < 2:
                raise ValueError("n_sample_points must be at least two")
            return polyline_length([self.quick_point_from_proportion(k / (count - 1)) for k in range(count)])
        inner, outer = polyline_length(self.get_anchors()), polyline_length(self.points)
        return inner + (outer - inner) / 3

    def insert_n_curves(self, count, recurse=True):
        count = operator.index(count)
        if count < 0:
            raise ValueError("the number of added curves must be nonnegative")
        for mob in self.get_family(recurse):
            if mob.get_num_curves():
                points = insert_n_curves(mob.points, count)
                indices = np.arange(len(points)) * len(mob.points) // len(points)
                for name in ("fill_rgba", "stroke_rgba", "stroke_width"):
                    setattr(mob, name, getattr(mob, name)[indices].copy())
                mob.set_points(points)
        return self

    def pointwise_become_partial(self, source, a, b):
        points = source.points
        if a <= 0 and b >= 1:
            return self.set_points(points)
        count = source.get_num_curves()
        if count == 0:
            return self.set_points(np.zeros_like(points))
        lower, lower_residue = integer_interpolate(0, count, a)
        upper, upper_residue = integer_interpolate(0, count, b)
        first, lower_end, last, upper_end = 2 * lower, 2 * lower + 3, 2 * upper, 2 * upper + 3
        result = points.copy()
        if lower == upper:
            partial = partial_quadratic_bezier_points(points[first:lower_end], lower_residue, upper_residue)
            result[:first], result[first:upper_end], result[upper_end:] = partial[0], partial, partial[2]
        else:
            left = partial_quadratic_bezier_points(points[first:lower_end], lower_residue, 1)
            right = partial_quadratic_bezier_points(points[last:upper_end], 0, upper_residue)
            result[:first], result[first:lower_end] = left[0], left
            result[last:upper_end], result[upper_end:] = right, right[2]
        return self.set_points(result)

    def get_subcurve(self, a, b):
        return self.copy().pointwise_become_partial(self, a, b)

    def reverse_points(self, recurse=True):
        for mob in self.get_family(recurse):
            if not mob.has_points():
                continue
            ends = mob.get_subpath_end_indices()[:-1]
            mob.points[ends + 1] = mob.points[ends + 2]
            for array in mob.data.values():
                array[:] = array[::-1]
            mob.note_changed_data()
        return self

    def make_jagged(self, recurse=True):
        for mob in self.get_family(recurse):
            mob.points[1::2] = (mob.points[:-2:2] + mob.points[2::2]) / np.float32(2)
            mob.note_changed_data()
        return self

    def is_smooth(self, angle_tol=math.pi / 180):
        def angles(first, second):
            lengths = norm(first) * norm(second)
            products = first * second
            dots = (products[:, 0] + products[:, 1]) + products[:, 2]
            valid = (norm(first) >= np.float32(1e-8)) & (norm(second) >= np.float32(1e-8))
            ratios = np.clip(dots[valid] / lengths[valid], -1, 1)
            return all(math.acos(float(value)) < angle_tol for value in ratios)

        for subpath in self.get_subpaths():
            if len(subpath) < 5:
                continue
            if not angles(subpath[2:-1:2] - subpath[1:-2:2], subpath[3::2] - subpath[2:-1:2]):
                return False
            if np.max(np.abs(subpath[0] - subpath[-1])) <= np.float32(1e-5) and not angles(
                (subpath[-1] - subpath[-2])[None],
                (subpath[1] - subpath[0])[None],
            ):
                return False
        return True

    def make_smooth(self, recurse=True):
        for mob in self.get_family(recurse):
            if not mob.has_points() or mob.is_smooth():
                continue
            for subpath in mob.get_subpaths():
                subpath[1::2] = smooth_quadratic_handles(subpath[::2])
            mob.note_changed_data()
        return self

    def set_points_smoothly(self, points):
        return self.set_points_as_corners(points).make_smooth()
