"""ManimGL family padding, with explicit point and style interpolation seams."""

import operator

import numpy as np

from .bezier import insert_n_curves
from .algebra import norm, ordered_sum
from .rates import straight_path


def is_interpolable(mobject):
    trait = getattr(mobject, "is_interpolable", False)
    return bool(trait() if callable(trait) else trait)


def _subpath_sum(points):
    # Julia 1.12 Base.mapreduce_impl sums in sequential blocks of at most
    # 1024 Point3f values, splitting the inclusive interval at its midpoint.
    if len(points) <= 1024:
        return ordered_sum(points, dtype=np.float32)
    middle = (len(points) + 1) // 2
    return _subpath_sum(points[:middle]) + _subpath_sum(points[middle:])


class AlignmentMixin:
    def add_n_more_submobjects(self, n, *, padding="invisible"):
        if padding not in ("invisible", "visible"):
            raise ValueError("padding must be invisible or visible")
        n = operator.index(n)
        if n <= 0:
            return self
        current = len(self.submobjects)
        if current == 0:
            null_mob = self.copy().set_points([self.get_center()])
            return self.set_submobjects([null_mob.copy() for _ in range(n)])
        target = current + n
        children = []
        previous = -1
        for index in range(target):
            source = index * current // target
            child = self.submobjects[source]
            if source != previous:
                children.append(child)
            else:
                children.append(child.invisible_copy() if padding == "invisible" else child.copy())
            previous = source
        return self.set_submobjects(children)

    def align_family(self, other, *, padding="invisible"):
        if padding not in ("invisible", "visible"):
            raise ValueError("padding must be invisible or visible")
        if self is not other and (self in other.get_family() or other in self.get_family()):
            raise ValueError("cannot align an ancestor with its descendant")
        pending = [(self, other)]
        while pending:
            first, second = pending.pop()
            difference = len(second) - len(first)
            first.add_n_more_submobjects(max(0, difference), padding=padding)
            second.add_n_more_submobjects(max(0, -difference), padding=padding)
            pending.extend(reversed(list(zip(first.submobjects, second.submobjects))))
        return self

    def align_points(self, other):
        if not hasattr(self, "get_subpath_end_indices") or not hasattr(other, "get_subpath_end_indices"):
            # ManimGL's Mobject.align_points: resize both to the longer, preserving order
            longest = max(len(self.points), len(other.points))
            for mob in (self, other):
                count = len(mob.points)
                if count != longest and count:
                    indices = np.arange(longest) * count // longest
                    mob.set_points(mob.points[indices])
            return self
        first_cuts = self.get_subpath_end_indices() if self.has_points() else []
        second_cuts = other.get_subpath_end_indices() if other.has_points() else []
        if len(self.points) == len(other.points) and np.array_equal(first_cuts, second_cuts):
            return self
        for mob in (self, other):
            if not mob.has_points():
                mob.set_points([mob.get_center()])
        def length(points):
            return float(ordered_sum(norm(points[1:] - points[:-1])))

        paths = [sorted(mob.get_subpaths(), key=length, reverse=True) for mob in (self, other)]

        def nth(group, index):
            if index < len(group):
                return group[index]
            # The collapsed path avoids the overlapping opposite winding
            # of ManimGL's retraced path in the middle of a morph.
            center = _subpath_sum(group[0]) / np.float32(len(group[0]))
            return np.repeat(center[None, :], 3, axis=0)

        output = [[], []]
        for index in range(max(map(len, paths))):
            pair = [nth(group, index) for group in paths]
            target = max(map(len, pair))
            for side, points in enumerate(pair):
                if index:
                    output[side].append(output[side][-1][-1:])
                output[side].append(insert_n_curves(points, (target - len(points)) // 2))
        self.set_points(np.concatenate(output[0]))
        other.set_points(np.concatenate(output[1]))
        return self

    def align_data(self, other, *, padding="invisible"):
        self.align_family(other, padding=padding)
        for first, second in zip(self.get_family(), other.get_family()):
            first.align_points(second)
        return self

    def align_data_and_family(self, other, *, padding="invisible"):
        return self.align_data(other, padding=padding)

    def become(self, other, match_updaters=False):
        from .mobject import Mobject

        if not isinstance(other, Mobject):
            raise TypeError("become expects a Mobject")
        self.align_family(other)
        destination, source = self.get_family(), other.get_family()
        for first, second in zip(destination, source):
            first.set_data(second.data)
            first.set_uniforms(second.uniforms)
            first.default_fill_rgba = second.default_fill_rgba.copy()
            first.default_stroke_rgba = second.default_stroke_rgba.copy()
            first.default_stroke_width = second.default_stroke_width
            first.fill_gradient = second.fill_gradient
            first.keys = list(second.keys)
            first.key_runs = None if second.key_runs is None else {
                key: [list(run) for run in runs] for key, runs in second.key_runs.items()
            }
            first._key_group_cache = {}
            first.bounding_box[:] = second.bounding_box
            first._bbox_has_points = second._bbox_has_points
            first._needs_new_bounding_box = second._needs_new_bounding_box
            first.shader_folder = second.shader_folder
            first.texture_paths = second.texture_paths
            first.depth_test = second.depth_test
            first.render_primitive = second.render_primitive
            # Pointless interpolable members own state outside the geometry
            # arrays (trackers, camera views and user-defined contracts).
            if first is not self and type(first).become is not AlignmentMixin.become:
                first.become(second)
        first_positions = {}
        for index, member in enumerate(source):
            first_positions.setdefault(member, index)
        for name, value in list(other.__dict__.items()):
            if isinstance(value, Mobject) and value in first_positions:
                setattr(self, name, destination[first_positions[value]])
        if match_updaters:
            self.match_updaters(other)
        self._expire_key_memos()
        return self

    def interpolate(self, first, second, alpha, path_func=straight_path):
        if len(first.points) != len(second.points):
            raise ValueError("cannot interpolate different point counts; call align_points first")
        if not is_interpolable(self):
            raise TypeError("this object has not opted into the interpolation contract")
        alpha = np.float32(alpha)
        self._resize_style(len(first.points))
        if self.points.shape != first.points.shape:
            self.points = np.empty_like(first.points)
        for name in ("points", "fill_rgba", "stroke_rgba", "stroke_width"):
            target = getattr(self, name)
            start, end = getattr(first, name), getattr(second, name)
            if alpha == 0 or alpha == 1:
                target[:] = start if alpha == 0 else end
            elif name == "points" and path_func is not straight_path:
                target[:] = path_func(start, end, float(alpha))
            else:
                target[:] = start + alpha * (end - start)
        if alpha == 0 or alpha == 1:
            self.fill_gradient = (first if alpha == 0 else second).fill_gradient
        return self.note_changed_data()
