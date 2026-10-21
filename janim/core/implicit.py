"""Isolines of f(x, y) = 0 by the isosurfaces quadtree.

The tracer is a quadtree refined where the sign changes (or f
is undefined), a triangulation of the leaves through their dual points, and a
walk over the triangle links that emits one polyline per connected piece.
"""
import math

import numpy as np

from janim.constants import FRAME_X_RADIUS, FRAME_Y_RADIUS

from .mobject import VMobject


class _IsoPoint:
    __slots__ = ("pos", "val")

    def __init__(self, pos, val):
        self.pos = pos
        self.val = val


def _iso(fn, pos):
    return _IsoPoint(pos, fn(pos))


def _iso_mid(a, b, fn):
    return _iso(fn, (a.pos + b.pos) / 2)


def _iso_zero(a, b, fn):
    """The point on the segment a-b whose linearly interpolated value is 0."""
    denom = a.val - b.val
    k1 = -b.val / denom
    k2 = a.val / denom
    return _iso(fn, k1 * a.pos + k2 * b.pos)


def _sign(value):
    if math.isnan(value):
        return math.nan
    return 1.0 if value > 0 else -1.0 if value < 0 else 0.0


def _binary_search_zero(a, b, fn, tol):
    while True:
        if bool(np.all(np.abs(b.pos - a.pos) < tol)):
            pt = _iso_zero(a, b, fn)
            is_zero = pt.val == 0 or _sign(pt.val - a.val) == _sign(b.val - pt.val)
            return pt, is_zero
        mid = _iso_mid(a, b, fn)
        if mid.val == 0:
            return mid, True
        if (mid.val > 0) == (a.val > 0):
            a = mid
        else:
            b = mid


class _IsoCell:
    __slots__ = ("vertices", "depth", "children", "parent", "child_direction")

    def __init__(self, vertices, depth, parent, child_direction):
        self.vertices = vertices      # bottom-left, bottom-right, top-left, top-right
        self.depth = depth
        self.children = []            # same order as the vertices
        self.parent = parent
        self.child_direction = child_direction


def _iso_vertices(pmin, pmax, fn):
    w = pmax - pmin
    return [
        _iso(fn, np.array((pmin[0] + (i & 1) * w[0], pmin[1] + ((i >> 1) & 1) * w[1])))
        for i in range(4)
    ]


def _iso_split(cell, fn):
    for i, vertex in enumerate(cell.vertices):
        pmin = (cell.vertices[0].pos + vertex.pos) / 2
        pmax = (cell.vertices[-1].pos + vertex.pos) / 2
        cell.children.append(_IsoCell(_iso_vertices(pmin, pmax, fn), cell.depth + 1, cell, i))
    return cell


def _iso_should_descend(cell, tol):
    """Descend only where the isoline may cross: a sign change, or an undefined corner."""
    if bool(np.all(cell.vertices[-1].pos - cell.vertices[0].pos < 10 * tol)):
        return False
    if all(math.isnan(v.val) for v in cell.vertices):
        return False
    if any(math.isnan(v.val) for v in cell.vertices):
        return True
    s0 = _sign(cell.vertices[0].val)
    return any(_sign(v.val) != s0 for v in cell.vertices[1:])


def _iso_build_tree(fn, pmin, pmax, min_depth, max_cells, tol):
    max_cells = max(4 ** min_depth, max_cells)        # min_depth takes precedence
    root = _IsoCell(_iso_vertices(pmin, pmax, fn), 0, None, 0)
    queue = [root]
    head = 0
    leaves = 1
    while head < len(queue) and leaves < max_cells:
        cell = queue[head]
        head += 1
        if cell.depth < min_depth or _iso_should_descend(cell, tol):
            _iso_split(cell, fn)
            queue.extend(cell.children)
            leaves += 3                                # four new leaves, one fewer
    return root


class _IsoTriangle:
    __slots__ = ("vertices", "next", "next_bisect", "prev", "visited")

    def __init__(self, a, b, c):
        self.vertices = (a, b, c)
        self.next = None
        self.next_bisect = None
        self.prev = None
        self.visited = False


def _iso_four(a, b, c, d, center):
    """Four triangles from `center` to the (clockwise) quad a, b, c, d."""
    return (_IsoTriangle(a, b, center), _IsoTriangle(b, c, center), _IsoTriangle(c, d, center), _IsoTriangle(d, a, center))


class _IsoTriangulator:
    def __init__(self, fn, tol):
        self.triangles = []
        self.hanging = {}       # keyed by the hanging edge's midpoint x 2
        self.fn = fn
        self.tol = tol

    def triangulate_inside(self, quad):
        if not quad.children:
            return
        for child in quad.children:
            self.triangulate_inside(child)
        c = quad.children
        self.crossing_row(c[0], c[1])
        self.crossing_row(c[2], c[3])
        self.crossing_col(c[0], c[2])
        self.crossing_col(c[1], c[3])

    def crossing_row(self, a, b):
        """Quad `b` is to the right of quad `a`."""
        if a.children and b.children:
            self.crossing_row(a.children[1], b.children[0])
            self.crossing_row(a.children[3], b.children[2])
        elif a.children:
            self.crossing_row(a.children[1], b)
            self.crossing_row(a.children[3], b)
        elif b.children:
            self.crossing_row(a, b.children[0])
            self.crossing_row(a, b.children[2])
        else:
            face_a = self.face_dual(a)
            face_b = self.face_dual(b)
            if a.depth < b.depth:                     # b is the smaller quad
                edge = self.edge_dual(b.vertices[2], b.vertices[0])
                self.add_four(_iso_four(b.vertices[2], face_b, b.vertices[0], face_a, edge))
            else:
                edge = self.edge_dual(a.vertices[3], a.vertices[1])
                self.add_four(_iso_four(a.vertices[3], face_b, a.vertices[1], face_a, edge))

    def crossing_col(self, a, b):
        """Quad `b` is above quad `a`."""
        if a.children and b.children:
            self.crossing_col(a.children[2], b.children[0])
            self.crossing_col(a.children[3], b.children[1])
        elif a.children:
            self.crossing_col(a.children[2], b)
            self.crossing_col(a.children[3], b)
        elif b.children:
            self.crossing_col(a, b.children[0])
            self.crossing_col(a, b.children[1])
        else:
            face_a = self.face_dual(a)
            face_b = self.face_dual(b)
            if a.depth < b.depth:
                edge = self.edge_dual(b.vertices[0], b.vertices[1])
                self.add_four(_iso_four(b.vertices[0], face_b, b.vertices[1], face_a, edge))
            else:
                edge = self.edge_dual(a.vertices[2], a.vertices[3])
                self.add_four(_iso_four(a.vertices[2], face_b, a.vertices[3], face_a, edge))

    def add_four(self, tris):
        for i in range(4):
            self.next_sandwich(tris[i], tris[(i + 1) % 4], tris[(i + 2) % 4])
        self.triangles.extend(tris)

    def set_next(self, tri1, tri2, vpos, vneg):
        if not (vpos.val > 0 >= vneg.val):
            return
        pt, is_zero = _binary_search_zero(vpos, vneg, self.fn, self.tol)
        if not is_zero:
            return
        tri1.next_bisect = pt
        tri1.next = tri2
        tri2.prev = tri1

    def next_sandwich(self, a, b, c):
        center = b.vertices[2]
        x = b.vertices[0]
        y = b.vertices[1]
        if center.val > 0 >= y.val:
            self.set_next(b, c, center, y)
        if x.val > 0 >= center.val:
            self.set_next(b, a, x, center)
        key = tuple((x.pos + y.pos).tolist())
        if y.val > 0 >= x.val:
            if key in self.hanging:
                self.set_next(b, self.hanging.pop(key), y, x)
            else:
                self.hanging[key] = b
        elif y.val <= 0 < x.val:
            if key in self.hanging:
                self.set_next(self.hanging.pop(key), b, x, y)
            else:
                self.hanging[key] = b

    def edge_dual(self, p1, p2):
        """The dual point on the edge p1-p2: the midpoint when it crosses, else gradient-guided."""
        if (p1.val > 0) != (p2.val > 0):
            return _iso_mid(p1, p2, self.fn)
        dt = 0.01
        df1 = self.fn(p1.pos * (1 - dt) + p2.pos * dt)
        df2 = self.fn(p1.pos * dt + p2.pos * (1 - dt))
        if (df1 > 0) == (df2 > 0):
            return _iso_mid(p1, p2, self.fn)
        return _iso_zero(_IsoPoint(p1.pos, df1), _IsoPoint(p2.pos, df2), self.fn)

    def face_dual(self, quad):
        return _iso_mid(quad.vertices[0], quad.vertices[-1], self.fn)


def _iso_trace(triangles):
    curves = []
    for start in triangles:
        if start.visited or start.next is None:
            continue
        curve = []
        tri = start
        closed = False
        while tri.prev is not None:                 # walk back to the curve's start
            tri = tri.prev
            if tri is start:
                closed = True
                break
        while tri is not None and not tri.visited:
            if tri.next_bisect is not None:
                curve.append(tri.next_bisect.pos)
            tri.visited = True
            tri = tri.next
        if closed and curve:
            curve.append(curve[0])
        curves.append(curve)
    return curves


def plot_isoline(fn, pmin, pmax, *, min_depth=5, max_quads=10000):
    """The isoline f = 0 over the box as polylines (the isosurfaces plot_isoline)."""
    pmin = np.asarray(pmin, dtype=np.float64)
    pmax = np.asarray(pmax, dtype=np.float64)
    tol = (pmax - pmin) / 1000
    root = _iso_build_tree(fn, pmin, pmax, min_depth, max_quads, tol)
    triangulator = _IsoTriangulator(fn, tol)
    triangulator.triangulate_inside(root)
    return _iso_trace(triangulator.triangles)


class ImplicitFunction(VMobject):
    """The curve f(x, y) = 0 over a box, as one VMobject of polylines."""

    def __init__(
        self,
        func,
        *,
        x_range=(-FRAME_X_RADIUS, FRAME_X_RADIUS),
        y_range=(-FRAME_Y_RADIUS, FRAME_Y_RADIUS),
        min_depth=5,
        max_quads=1500,
        use_smoothing=False,
        joint_type="auto",
        **kwargs,
    ):
        super().__init__(joint_type=joint_type, **kwargs)

        def fn(p):
            return float(func(float(p[0]), float(p[1])))

        curves = plot_isoline(
            fn,
            (float(x_range[0]), float(y_range[0])),
            (float(x_range[1]), float(y_range[1])),
            min_depth=int(min_depth),
            max_quads=int(max_quads),
        )
        for curve in curves:
            if not curve:
                continue
            self.start_new_path(np.array((curve[0][0], curve[0][1], 0.0), dtype=np.float32))
            for q in curve[1:]:
                self.add_line_to(np.array((q[0], q[1], 0.0), dtype=np.float32))
        if use_smoothing:
            self.make_smooth()
