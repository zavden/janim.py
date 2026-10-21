"""Cached float32 boxes, with invalidation limited to affected ancestors."""

import numpy as np

from .algebra import ordered_sum


class BoundingBoxMixin:
    def get_bounding_box(self):
        if not self._needs_new_bounding_box:
            return self.bounding_box
        transient = {}
        pending = [(self, False)]
        while pending:
            mob, ready = pending.pop()
            # Pointless intermediate groups are skipped when asking for a
            # family's box. Their caches stay lazy: an eager child query
            # changes later f32 midpoint rounding after a translation.
            cache_member = mob is self or mob.has_points()
            if cache_member and not mob._needs_new_bounding_box:
                transient[mob] = mob.bounding_box, mob._bbox_has_points
                continue
            if not ready:
                pending.append((mob, True))
                pending.extend((child, False) for child in reversed(mob.submobjects))
                continue
            points = mob.get_points()
            has_points = bool(len(points))
            if has_points:
                low, high = points.min(axis=0), points.max(axis=0)
                # the sign of an exact zero: only looked at when there is one
                if not low.all() or not high.all():
                    for axis in range(3):
                        column = points[:, axis]
                        if low[axis] == 0:
                            low[axis] = -0.0 if np.signbit(column).any() else 0.0
                        if high[axis] == 0:
                            high[axis] = -0.0 if np.signbit(column).all() else 0.0
                mob._expand_leaf_box(low, high)
            else:
                low = np.full(3, np.inf, dtype=np.float32)
                high = np.full(3, -np.inf, dtype=np.float32)
            for child in mob.submobjects:
                child_box, child_has_points = transient[child]
                if child_has_points:
                    negative_low = np.signbit(low) | np.signbit(child_box[0])
                    negative_high = np.signbit(high) & np.signbit(child_box[2])
                    np.minimum(low, child_box[0], out=low)
                    np.maximum(high, child_box[2], out=high)
                    low[(low == 0) & negative_low] = -0.0
                    high[(high == 0) & ~negative_high] = 0.0
                    has_points = True
            box = mob.bounding_box if cache_member else np.empty((3, 3), dtype=np.float32)
            if has_points:
                box[0] = low
                box[1] = (low + high) / np.float32(2)
                box[2] = high
            else:
                box.fill(0)
            transient[mob] = box, has_points
            if cache_member:
                mob._bbox_has_points = has_points
                mob._needs_new_bounding_box = False
        return self.bounding_box

    def _expand_leaf_box(self, low, high):
        """Hook for leaves whose extent exceeds their points (dot radii)."""

    def compute_bounding_box(self):
        self._needs_new_bounding_box = True
        return self.get_bounding_box().copy()

    def refresh_bounding_box(self, recurse_down=False, recurse_up=True):
        roots = self.get_family() if recurse_down else (self,)
        for mob in roots:
            mob._needs_new_bounding_box = True
        if recurse_up:
            pending = [parent for mob in roots for parent in mob.parents]
            seen = {}
            while pending:
                parent = pending.pop()
                if parent in seen:
                    continue
                seen[parent] = None
                parent._needs_new_bounding_box = True
                pending.extend(parent.parents)
        return self

    def get_bounding_box_point(self, direction):
        direction = np.asarray(direction)
        if direction.shape != (3,):
            raise ValueError("a box direction must have three components")
        return self.get_bounding_box()[np.sign(direction).astype(np.intp) + 1, np.arange(3)]

    get_critical_point = get_bounding_box_point
    get_corner = get_bounding_box_point
    get_edge_center = get_bounding_box_point

    def get_center(self):
        return self.get_bounding_box()[1].copy()

    def get_left(self):
        return self.get_bounding_box_point((-1, 0, 0))

    def get_right(self):
        return self.get_bounding_box_point((1, 0, 0))

    def get_top(self):
        return self.get_bounding_box_point((0, 1, 0))

    def get_bottom(self):
        return self.get_bounding_box_point((0, -1, 0))

    def get_zenith(self):
        return self.get_bounding_box_point((0, 0, 1))

    def get_nadir(self):
        return self.get_bounding_box_point((0, 0, -1))

    def length_over_dim(self, dim):
        if dim not in (0, 1, 2):
            raise ValueError(f"dimension {dim} does not exist: 0=x, 1=y, 2=z")
        box = self.get_bounding_box()
        return abs(box[2, dim] - box[0, dim])

    def get_width(self):
        return self.length_over_dim(0)

    def get_height(self):
        return self.length_over_dim(1)

    def get_depth(self):
        return self.length_over_dim(2)

    # Manim CE reads `m.width`; ManimGL has no such property, so a scene written
    # for GL may ASSIGN `self.depth = 3` as a plain attribute. Both hold: the
    # property answers the geometry until the attribute is assigned, and from
    # then on it is that attribute (GL's semantics).
    def _attribute_or(name, getter):
        def get(self):
            override = self.__dict__.get("_attribute_" + name)
            return getter(self) if override is None else override

        def put(self, value):
            self.__dict__["_attribute_" + name] = value

        return property(get, put)

    width = _attribute_or("width", get_width)
    height = _attribute_or("height", get_height)
    depth = _attribute_or("depth", get_depth)
    del _attribute_or

    def get_center_of_mass(self):
        points = self.get_all_points()
        if not len(points):
            return np.zeros(3, dtype=np.float32)
        return (ordered_sum(points) / len(points)).astype(np.float32)

    def get_real_center_of_mass(self):
        """Exact Green integrals over quadratic segments in xy."""
        total = np.zeros(3, dtype=np.float64)
        nodes = (0.5 - 0.5 * np.sqrt(0.6), 0.5, 0.5 + 0.5 * np.sqrt(0.6))
        weights = (5 / 18, 8 / 18, 5 / 18)
        for mob in self.get_family():
            if not hasattr(mob, "get_subpaths"):
                continue
            for subpath in mob.get_subpaths():
                if len(subpath) < 3:
                    continue
                curves = np.array([subpath[2 * k:2 * k + 3] for k in range((len(subpath) - 1) // 2)])
                closing = np.array([subpath[-1], (subpath[-1] + subpath[0]) / np.float32(2), subpath[0]])
                curves = np.concatenate((curves, closing[None])).astype(np.float64)
                x0, y0 = curves[:, 0, 0], curves[:, 0, 1]
                a1x = 2 * (curves[:, 1, 0] - x0)
                a1y = 2 * (curves[:, 1, 1] - y0)
                a2x = x0 - 2 * curves[:, 1, 0] + curves[:, 2, 0]
                a2y = y0 - 2 * curves[:, 1, 1] + curves[:, 2, 1]
                integrals = np.zeros((len(curves), 3), dtype=np.float64)
                for t, weight in zip(nodes, weights):
                    x = x0 + a1x * t + a2x * t * t
                    y = y0 + a1y * t + a2y * t * t
                    dx, dy = a1x + 2 * a2x * t, a1y + 2 * a2y * t
                    integrals[:, 0] += weight * (x * dy - y * dx)
                    integrals[:, 1] += weight * (x * x * dy)
                    integrals[:, 2] += weight * (y * y * dx)
                total = ordered_sum(np.vstack((total, integrals)))
        area = total[0] / 2
        box = self.get_bounding_box()
        span = float(box[2, 0] - box[0, 0]) + float(box[2, 1] - box[0, 1])
        if abs(area) <= 1e-9 * span**2:
            raise ValueError("get_real_center_of_mass: this shape encloses no area")
        return np.array([total[1] / (2 * area), -total[2] / (2 * area), box[1, 2]], dtype=np.float32)
