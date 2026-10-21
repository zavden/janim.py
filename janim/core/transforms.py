"""Array transforms at the f32/f64 seams."""

import math
import operator

import numpy as np

from .algebra import angle_between_vectors, apply_matrix_rows, norm, rotation_matrix


def point3(value):
    result = np.asarray(value, dtype=np.float32)
    if result.shape != (3,):
        raise ValueError("a point or direction must have three components")
    return result


class TransformMixin:
    _transform_bbox = True

    def _pivot(self, about_point, about_edge):
        if about_point is not None:
            return point3(about_point).copy()
        if about_edge is not None:
            return self.get_bounding_box_point(about_edge)
        return None

    def _point_arrays(self):
        """The arrays a rigid transform moves together; meshes add their normals."""
        return (self.points,)

    def _transform_arrays(self, operation, pivot, works_on_bounding_box):
        family = self.get_family()
        for mob in family:
            transform_box = works_on_bounding_box and mob._transform_bbox
            point_arrays = mob._point_arrays()
            arrays = (*point_arrays, mob.bounding_box) if transform_box else point_arrays
            for array in arrays:
                if len(array):
                    operation(array, pivot)
            mob.subpath_end_indices = None
            mob._data_has_changed = True
            if not transform_box:
                mob._needs_new_bounding_box = True
        members = dict.fromkeys(family)
        external = {}
        for mob in family:
            for parent in mob.parents:
                if parent not in members:
                    external[parent] = None
        for parent in external:
            parent.refresh_bounding_box()
        return self

    def shift(self, *vectors):
        if not vectors:
            return self
        displacement = point3(vectors[0])
        if len(vectors) > 1:
            displacement = displacement.copy()
            for vector in vectors[1:]:
                np.add(displacement, point3(vector), out=displacement)

        def translate(array, pivot):
            np.add(array, displacement, out=array)

        return self._transform_arrays(translate, None, True)

    def _scale(self, factor, about_point, about_edge):
        pivot = self._pivot(about_point, about_edge)

        def scale(array, pivot):
            if pivot is not None:
                np.subtract(array, pivot, out=array)
            np.multiply(array, factor, out=array)
            if pivot is not None:
                np.add(array, pivot, out=array)

        return self._transform_arrays(scale, pivot, True)

    def scale(
        self,
        scale_factor,
        min_scale_factor=1e-8,
        about_point=None,
        about_edge=(0, 0, 0),
    ):
        with np.errstate(over="ignore", invalid="ignore"):
            if np.isscalar(scale_factor):
                factor = np.float32(np.maximum(float(scale_factor), float(min_scale_factor)))
            else:
                factor = np.maximum(point3(scale_factor), np.float32(min_scale_factor))
            self._scale(factor, about_point, about_edge)
        for mob in self.get_family():
            mob._handle_scale_side_effects(factor)
        return self

    def _handle_scale_side_effects(self, factor):
        pass

    def stretch(self, factor, dim, about_point=None, about_edge=(0, 0, 0)):
        dim = operator.index(dim)
        if dim not in (0, 1, 2):
            raise ValueError(f"dimension {dim} does not exist: 0=x, 1=y, 2=z")
        scale = np.ones(3, dtype=np.float32)
        scale[dim] = np.float32(factor)
        return self._scale(scale, about_point, about_edge)

    def rotate(self, angle, axis=(0, 0, 1), about_point=None, about_edge=(0, 0, 0)):
        matrix = rotation_matrix(angle, axis)
        pivot = self._pivot(about_point, about_edge)

        def rotate(array, pivot):
            relative = array if pivot is None else array - pivot
            result = apply_matrix_rows(relative, matrix).astype(np.float32)
            if pivot is not None:
                np.add(result, pivot, out=result)
            array[:] = result

        return self._transform_arrays(rotate, pivot, False)

    def rotate_about_origin(self, angle, axis=(0, 0, 1)):
        return self.rotate(angle, axis, about_point=(0, 0, 0))

    def flip(self, axis=(0, 1, 0), **kwargs):
        return self.rotate(math.pi, axis, **kwargs)

    def apply_points_function(
        self,
        func,
        about_point=None,
        about_edge=(0, 0, 0),
        works_on_bounding_box=False,
    ):
        pivot = self._pivot(about_point, about_edge)

        def apply(array, pivot):
            relative = array if pivot is None else array - pivot
            result = np.asarray(func(relative), dtype=np.float64)
            if pivot is not None:
                result = result + pivot.astype(np.float64)
            array[:] = result

        return self._transform_arrays(apply, pivot, works_on_bounding_box)

    def apply_function(self, function, **kwargs):
        result = self._apply_function(function, **kwargs)
        for member in self.family_members_with_points():
            if getattr(member, "make_smooth_after_applying_functions", False):
                member.make_smooth()
        return result

    def _apply_function(self, function, **kwargs):
        if not kwargs:
            kwargs["about_point"] = (0, 0, 0)
        return self.apply_points_function(
            lambda points: np.array([function(point) for point in points]),
            **kwargs,
        )

    def apply_matrix(self, matrix, **kwargs):
        matrix = np.asarray(matrix, dtype=np.float64)
        if matrix.shape not in ((2, 2), (3, 3)):
            raise ValueError("apply_matrix expects a 2x2 or 3x3 matrix")
        full = np.eye(3)
        full[:len(matrix), :len(matrix)] = matrix
        if "about_point" not in kwargs and "about_edge" not in kwargs:
            kwargs["about_point"] = (0, 0, 0)
        return self.apply_points_function(lambda points: apply_matrix_rows(points, full), **kwargs)

    def apply_complex_function(self, function, **kwargs):
        def point_function(point):
            value = function(complex(float(point[0]), float(point[1])))
            return (value.real, value.imag, point[2])

        return self.apply_function(point_function, **kwargs)

    def move_to(self, target, aligned_edge=(0, 0, 0), coor_mask=(1, 1, 1)):
        destination = target.get_bounding_box_point(aligned_edge) if hasattr(target, "get_bounding_box_point") else point3(target)
        anchor = self.get_bounding_box_point(aligned_edge)
        return self.shift((destination - anchor) * point3(coor_mask))

    def set_x(self, value, direction=(0, 0, 0)):
        return self.set_coord(value, 0, direction)

    def set_y(self, value, direction=(0, 0, 0)):
        return self.set_coord(value, 1, direction)

    def set_z(self, value, direction=(0, 0, 0)):
        return self.set_coord(value, 2, direction)

    def get_x(self, direction=(0, 0, 0)):
        return self.get_bounding_box_point(direction)[0]

    def get_y(self, direction=(0, 0, 0)):
        return self.get_bounding_box_point(direction)[1]

    def get_z(self, direction=(0, 0, 0)):
        return self.get_bounding_box_point(direction)[2]

    def rescale_to_fit(self, length, dim, stretch=False, **kwargs):
        current = self.length_over_dim(dim)
        if current == 0:
            return self
        factor = float(length / current) if isinstance(length, np.float32) and isinstance(current, np.float32) else float(length) / float(current)
        return self.stretch(factor, dim, **kwargs) if stretch else self.scale(factor, **kwargs)

    def set_width(self, width, stretch=False, **kwargs):
        return self.rescale_to_fit(width, 0, stretch, **kwargs)

    def set_height(self, height, stretch=False, **kwargs):
        return self.rescale_to_fit(height, 1, stretch, **kwargs)

    def set_depth(self, depth, stretch=False, **kwargs):
        return self.rescale_to_fit(depth, 2, stretch, **kwargs)

    def stretch_to_fit_width(self, width, **kwargs):
        return self.set_width(width, stretch=True, **kwargs)

    def stretch_to_fit_height(self, height, **kwargs):
        return self.set_height(height, stretch=True, **kwargs)

    def stretch_to_fit_depth(self, depth, **kwargs):
        return self.set_depth(depth, stretch=True, **kwargs)

    def match_width(self, other, **kwargs):
        return self.rescale_to_fit(other.length_over_dim(0), 0, **kwargs)

    def match_height(self, other, **kwargs):
        return self.rescale_to_fit(other.length_over_dim(1), 1, **kwargs)

    def match_depth(self, other, **kwargs):
        return self.rescale_to_fit(other.length_over_dim(2), 2, **kwargs)

    def put_start_and_end_on(self, start, end):
        original_start, original_end = self.get_start_and_end()
        current = original_end - original_start
        if norm(current) <= np.float32(1e-8):
            raise ValueError("cannot reposition the endpoints of a closed path (start == end)")
        target = point3(end) - point3(start)
        self.scale(norm(target) / norm(current), about_point=original_start)
        axis = np.cross(current.astype(np.float64), target.astype(np.float64))
        self.rotate(
            angle_between_vectors(current, target),
            axis=(0, 0, 1) if norm(axis) < 1e-8 else axis.astype(np.float32),
            about_point=original_start,
        )
        return self.shift(point3(start) - self.get_start())
