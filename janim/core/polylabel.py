"""The pole of inaccessibility of a polygon with holes (polylabel).

Ported from ManimCE's `manim/utils/polylabel.py` (MIT; see
THIRD_PARTY_NOTICES.md), an implementation of Vladimir Agafonkin's polylabel
algorithm: cover the polygon with square cells, keep the cell whose centre
is farthest inside, and split every cell that could still hide a farther
point, until none can by more than `precision`.

The queue pops cells in CE's order (the smallest distance first), so the
pole and its distance are CE's to the last bit. Three changes: the
point-in-polygon test runs over all the edges at once instead of edge by
edge (the same comparisons, so the same answers), a polygon of zero area
starts from its box centre instead of failing, and an edge of zero length
does not turn the distances into NaN.
"""

import heapq

import numpy as np


class Polygon:
    """The rings of a polygon (the first is the outline, the rest are holes), as edges."""

    def __init__(self, rings):
        np_rings = [np.asarray(ring, dtype=np.float64) for ring in rings]
        csum = np.cumsum([ring.shape[0] for ring in np_rings])
        self.array = np.concatenate(np_rings, axis=0)
        self.start = np.delete(self.array, csum - 1, axis=0)
        self.stop = np.delete(self.array, csum % csum[-1], axis=0)
        self.diff = np.delete(np.diff(self.array, axis=0), csum[:-1] - 1, axis=0)
        lengths = np.einsum("ij,ij->i", self.diff, self.diff).reshape(-1, 1)
        self.norm = np.divide(
            self.diff,
            lengths,
            out=np.zeros_like(self.diff),
            where=lengths > 0,
        )
        x, y = self.start[:, 0], self.start[:, 1]
        xr, yr = self.stop[:, 0], self.stop[:, 1]
        self.area = 0.5 * (np.dot(x, yr) - np.dot(xr, y))
        if self.area:
            factor = x * yr - xr * y
            cx = np.sum((x + xr) * factor) / (6.0 * self.area)
            cy = np.sum((y + yr) * factor) / (6.0 * self.area)
            self.centroid = np.array([cx, cy])
        else:
            self.centroid = (self.array.min(axis=0) + self.array.max(axis=0)) / 2

    def compute_distance(self, point):
        """The distance from `point` to the nearest edge: positive inside, negative outside."""
        scalars = np.einsum("ij,ij->i", self.norm, point - self.start)
        clips = np.clip(scalars, 0, 1).reshape(-1, 1)
        d = float(np.min(np.linalg.norm(self.start + self.diff * clips - point, axis=1)))
        return d if self.inside(point) else -d

    def inside(self, point):
        """Ray casting; a point on an edge counts as inside."""
        x, y = float(point[0]), float(point[1])
        x0, y0 = self.start[:, 0], self.start[:, 1]
        x1, y1 = self.stop[:, 0], self.stop[:, 1]
        within = (
            (np.minimum(x0, x1) <= x)
            & (x <= np.maximum(x0, x1))
            & (np.minimum(y0, y1) <= y)
            & (y <= np.maximum(y0, y1))
        )
        cross = (x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)
        if np.any(within & np.isclose(cross, 0.0)):
            return True
        straddle = (y0 > y) != (y1 > y)
        with np.errstate(divide="ignore", invalid="ignore"):
            x_intersect = (x1 - x0) / (y1 - y0) * (y - y0) + x0
        return int(np.count_nonzero(straddle & (x < x_intersect))) % 2 == 1


class Cell:
    """A square of half-size `h` centred on `c`; `d` is its centre's distance, `p` the most any point in it can reach."""

    def __init__(self, c, h, polygon):
        self.c = np.asarray(c, dtype=np.float64)
        self.h = h
        self.d = polygon.compute_distance(self.c)
        self.p = self.d + self.h * np.sqrt(2)

    def __lt__(self, other):
        return self.d < other.d

    def __gt__(self, other):
        return self.d > other.d

    def __le__(self, other):
        return self.d <= other.d

    def __ge__(self, other):
        return self.d >= other.d


def polylabel(rings, precision=0.01):
    """The `Cell` whose centre is the pole of inaccessibility of `rings`, to `precision`.

    `rings` are closed sequences of points (x, y or x, y, z; z is ignored):
    the first is the outline and the rest are holes.
    """
    np_rings = [np.asarray(ring, dtype=np.float64)[:, :2] for ring in rings]
    polygon = Polygon(np_rings)
    mins = np.min(polygon.array, axis=0)
    maxs = np.max(polygon.array, axis=0)
    dims = maxs - mins
    s = np.min(dims)
    h = s / 2.0
    queue = []
    if s > 0:
        xv, yv = np.meshgrid(np.arange(mins[0], maxs[0], s), np.arange(mins[1], maxs[1], s))
        for corner in np.vstack([xv.ravel(), yv.ravel()]).T:
            heapq.heappush(queue, Cell(corner + h, h, polygon))
    best = Cell(polygon.centroid, 0, polygon)
    bbox = Cell(mins + (dims / 2), 0, polygon)
    if bbox.d > best.d:
        best = bbox
    directions = np.array([[-1, -1], [1, -1], [-1, 1], [1, 1]])
    while queue:
        cell = heapq.heappop(queue)
        if cell > best:
            best = cell
        if cell.p - best.d > precision:
            h = cell.h / 2.0
            for offset in cell.c + directions * h:
                heapq.heappush(queue, Cell(offset, h, polygon))
    return best
