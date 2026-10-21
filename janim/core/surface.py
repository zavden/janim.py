"""Parametric meshes and the 3D zoo.

A Surface owns two point arrays: the vertices and the vertices nudged along
the unit normal (`d_normal_points`), which the shader turns back into normals.
Every rigid verb moves both. The verbs called ON a Surface use the f64 forms
(`c + factor * (p - c)` rounded once); a Group verb reaches the
same arrays through `_point_arrays` and keeps the f32 in-place form of the
generic `_apply!`.
"""
import math
import operator

import numpy as np

from janim.constants import IN, ORIGIN, OUT, RIGHT, TAU, UP

from janim.constants import BLUE, BLUE_D, BLUE_E, GREY_A, GREY_C
from ._ranges import linear_range
from .algebra import apply_matrix_rows, compass_directions, norm, rotation_matrix
from .colorspace import color_to_rgba
from .mobject import Group, Mobject, VGroup, VMobject
from .shapes import Polygon, Square
from .transforms import point3

SURFACE_SHADING = (0.3, 0.2, 0.4)


def triangle_indices(nu, nv):
    """The index mesh of surface.py:149 (two triangles per cell, 0-based)."""
    nu, nv = operator.index(nu), operator.index(nv)
    if nu == 0 or nv == 0:
        return np.empty(0, dtype=np.int32)
    indices = np.empty(6 * (nu - 1) * (nv - 1), dtype=np.int32)
    k = 0
    for i in range(nu - 1):
        for j in range(nv - 1):
            top_left = i * nv + j
            bottom_left = (i + 1) * nv + j
            top_right = i * nv + j + 1
            bottom_right = (i + 1) * nv + j + 1
            indices[k:k + 6] = (top_left, bottom_left, top_right, top_right, bottom_left, bottom_right)
            k += 6
    return indices


def _cross(a, b):
    """StaticArrays' cross product: the six products and three differences, in order."""
    return np.array(
        (
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        ),
        dtype=np.float64,
    )


def sample_surface(uv_func, u_range, v_range, nu, nv, epsilon, normal_nudge):
    """Vertices and nudged vertices of a parametric patch, u-outer / v-inner."""
    epsilon, normal_nudge = float(epsilon), float(normal_nudge)
    points = np.empty((nu * nv, 3), dtype=np.float32)
    nudged = np.empty((nu * nv, 3), dtype=np.float32)
    k = 0
    for u in linear_range(u_range[0], u_range[1], nu):
        for v in linear_range(v_range[0], v_range[1], nv):
            p = np.array(uv_func(u, v), dtype=np.float64)
            du = np.array(uv_func(u + epsilon, v), dtype=np.float64) - p
            dv = np.array(uv_func(u, v + epsilon), dtype=np.float64) - p
            n = _cross(du, dv)
            length = float(norm(n))
            n = n / length if length > 0 else np.array((0.0, 0.0, 1.0))
            points[k] = p
            nudged[k] = p + normal_nudge * n
            k += 1
    return points, nudged


class Surface(Mobject):
    """A parametric mesh: `uv_func(u, v)` sampled on a `resolution` grid."""

    render_kind = "surface"
    is_interpolable = True
    _transform_bbox = False

    def __init__(
        self,
        uv_func=None,
        *,
        u_range=(0.0, 1.0),
        v_range=(0.0, 1.0),
        resolution=(101, 101),
        color=GREY_C,
        opacity=1.0,
        shading=SURFACE_SHADING,
        epsilon=1e-3,
        normal_nudge=1e-3,
        depth_test=True,
        **kwargs,
    ):
        nu, nv = (operator.index(n) for n in resolution)
        super().__init__(shading=shading, depth_test=depth_test, **kwargs)
        self.resolution = (nu, nv)
        self.d_normal_points = np.empty((0, 3), dtype=np.float32)
        self.rgba = np.empty((0, 4), dtype=np.float32)
        self.indices = triangle_indices(nu, nv)
        if uv_func is not None:
            points, nudged = sample_surface(uv_func, u_range, v_range, nu, nv, epsilon, normal_nudge)
            self._set_mesh(points, nudged, np.tile(color_to_rgba(color, opacity), (nu * nv, 1)))

    @classmethod
    def from_arrays(cls, points, d_normal_points, rgba, resolution, indices, *, shading=SURFACE_SHADING, depth_test=True):
        """A mesh from explicit arrays (models, copies): no sampling at all."""
        result = cls(resolution=resolution, shading=shading, depth_test=depth_test)
        result.indices = np.ascontiguousarray(indices, dtype=np.int32)
        result._set_mesh(points, d_normal_points, rgba)
        return result

    def _set_mesh(self, points, d_normal_points, rgba):
        self.points = np.ascontiguousarray(points, dtype=np.float32)
        self.d_normal_points = np.ascontiguousarray(d_normal_points, dtype=np.float32)
        self.rgba = np.ascontiguousarray(rgba, dtype=np.float32)
        return self.note_changed_data()

    def get_bounding_box(self):
        # A mesh is measured on every query, so points
        # written in place (`m.points[:] = …`) are seen by the next `get_center`.
        # A Group ABOVE the mesh still caches: `note_changed_data()` tells it.
        self._needs_new_bounding_box = True
        return super().get_bounding_box()

    def _point_arrays(self):
        return (self.points, self.d_normal_points)

    # ── normals ──────────────────────────────────────────────────────────
    def get_unit_normals(self):
        """Per-vertex unit normals as the shader recovers them (get_unit_normals)."""
        delta = (self.d_normal_points - self.points).astype(np.float64)
        with np.errstate(divide="ignore", invalid="ignore"):
            return ((1.0 / norm(delta))[:, None] * delta).astype(np.float32)

    # ── the verbs of a surface (f64 forms on BOTH arrays) ───────────────
    def _mesh_pivot(self, about_point, about_edge):
        pivot = self._pivot(about_point, about_edge)
        return (self.get_center() if pivot is None else pivot).astype(np.float64)

    def scale(self, factor, min_scale_factor=1e-8, about_point=None, about_edge=(0, 0, 0)):
        center = self._mesh_pivot(about_point, about_edge)
        factor = float(factor)
        for array in self._point_arrays():
            array[:] = center + factor * (array.astype(np.float64) - center)
        return self.note_changed_data()

    def rotate(self, angle, axis=(0, 0, 1), about_point=None, about_edge=(0, 0, 0)):
        center = self._mesh_pivot(about_point, about_edge)
        matrix = rotation_matrix(angle, axis)
        for array in self._point_arrays():
            array[:] = apply_matrix_rows(array.astype(np.float64) - center, matrix) + center
        return self.note_changed_data()

    @staticmethod
    def rotate_stacked(surfaces, angle, axis, about_point):
        """`rotate` of many plain meshes about ONE point in one numpy pass per array kind: the
        same f64 arithmetic element by element (`apply_matrix_rows` is elementwise), so the bits
        are those of one `rotate` per mesh, at a
        tenth of the calls. A `Rotate` of 330 cubes turns 1 980 of them every frame."""
        center = point3(about_point).astype(np.float64)
        matrix = rotation_matrix(angle, axis)
        for arrays in zip(*(surface._point_arrays() for surface in surfaces)):
            stacked = apply_matrix_rows(np.concatenate(arrays).astype(np.float64) - center, matrix) + center
            offset = 0
            for array in arrays:
                count = len(array)
                array[:] = stacked[offset:offset + count]
                offset += count
        for surface in surfaces:
            surface.note_changed_data()

    @staticmethod
    def interpolate_stacked(triples, alpha):
        """`interpolate` of many plain meshes of one resolution at one alpha, stacked: the same
        f32 lerp element by element."""
        t = np.float32(alpha)
        for name in ("points", "d_normal_points", "rgba"):
            first = np.concatenate([getattr(start, name) for _, start, _ in triples])
            second = np.concatenate([getattr(target, name) for _, _, target in triples])
            stacked = first + t * (second - first)
            offset = 0
            for mob, _, _ in triples:
                array = getattr(mob, name)
                count = len(array)
                array[:] = stacked[offset:offset + count]
                offset += count
        for mob, _, _ in triples:
            mob.note_changed_data()

    def stretch(self, factor, dim, about_point=None, about_edge=(0, 0, 0)):
        dim = operator.index(dim)
        if dim not in (0, 1, 2):
            raise ValueError(f"dimension {dim} does not exist: 0=x, 1=y, 2=z")
        center = float(self._mesh_pivot(about_point, about_edge)[dim])
        factor = float(factor)
        for array in self._point_arrays():
            array[:, dim] = center + factor * (array[:, dim].astype(np.float64) - center)
        return self.note_changed_data()

    # ── colour and shading ───────────────────────────────────────────────
    def set_color(self, color=None, opacity=None, recurse=True):
        if color is not None:
            self.rgba[:, :3] = color_to_rgba(color, 1.0)[:3]
        if opacity is not None:
            self.rgba[:, 3] = np.float32(opacity)
        return self

    def set_opacity(self, opacity, recurse=True):
        return self.set_color(opacity=opacity)

    def get_opacity(self):
        return 1.0 if not len(self.rgba) else float(self.rgba[0, 3])

    def set_shading(self, reflectiveness=None, gloss=None, shadow=None, recurse=True):
        """Keeps every component that is not given, like set_shading!."""
        current = self.uniforms["shading"]
        values = [current[0], current[1], current[2]]
        for index, value in enumerate((reflectiveness, gloss, shadow)):
            if value is not None:
                values[index] = value
        self.uniforms["shading"] = np.array(values, dtype=np.float32)
        return self

    # ── points, copies and interpolation ─────────────────────────────────
    def set_points(self, points):
        """Same count only: the nudged vertices ride along with their offsets."""
        points = np.asarray(points, dtype=np.float32).reshape(-1, 3)
        if len(points) != len(self.points):
            raise ValueError(
                f"set_points(Surface): {len(points)} points for a mesh of {len(self.points)} "
                f"({self.resolution[0]}x{self.resolution[1]}); the count comes from `resolution`",
            )
        self.d_normal_points[:] = points + (self.d_normal_points - self.points)
        self.points[:] = points
        return self.note_changed_data()

    def align_data(self, other, **kwargs):
        if not isinstance(other, Surface) or len(other.points) != len(self.points):
            raise ValueError("cannot interpolate Surfaces of different resolutions")
        return self

    def interpolate(self, first, second, alpha, **kwargs):
        if len(first.points) != len(second.points):
            raise ValueError(
                f"cannot interpolate Surfaces of different resolutions ({first.resolution} vs {second.resolution})",
            )
        if len(self.points) != len(first.points):
            self.become(first)
        t = np.float32(alpha)
        self.points[:] = first.points + t * (second.points - first.points)
        self.d_normal_points[:] = first.d_normal_points + t * (second.d_normal_points - first.d_normal_points)
        self.rgba[:] = first.rgba + t * (second.rgba - first.rgba)
        return self.note_changed_data()

    def become(self, other, match_updaters=False):
        self.resolution = other.resolution
        self.indices = other.indices.copy()
        self._set_mesh(other.points.copy(), other.d_normal_points.copy(), other.rgba.copy())
        if match_updaters:
            self.match_updaters(other)
        return self


# the verbs a stacked pass may replace: a subclass that overrides them keeps its own
Surface._plain_rotate = Surface.rotate
Surface._plain_interpolate = Surface.interpolate

ParametricSurface = Surface


def _julia_trig():
    from . import _julia_math

    return _julia_math


def Sphere(*, radius=1.0, resolution=(101, 51), **kwargs):
    """A sphere with true radial normals: d_normal_points = (r + 1e-3) / r * points."""
    jm = _julia_trig()
    r = float(radius)
    surface = Surface(
        lambda u, v: (r * jm.cos(u) * jm.sin(v), r * jm.sin(u) * jm.sin(v), -r * jm.cos(v)),
        u_range=(0.0, TAU),
        v_range=(0.0, math.pi),
        resolution=resolution,
        **kwargs,
    )
    factor = (r + 1e-3) / r
    surface.d_normal_points[:] = factor * surface.points.astype(np.float64)
    return surface


def Torus(*, r1=3.0, r2=1.0, resolution=(101, 101), **kwargs):
    """(r1 - r2 cos v)(cos u, sin u, 0) - r2 sin v z."""
    jm = _julia_trig()
    return Surface(
        lambda u, v: ((r1 - r2 * jm.cos(v)) * jm.cos(u), (r1 - r2 * jm.cos(v)) * jm.sin(u), -r2 * jm.sin(v)),
        u_range=(0.0, TAU),
        v_range=(0.0, TAU),
        resolution=resolution,
        **kwargs,
    )


def PlaneXY(*, x_range=(-3.0, 3.0), y_range=(-3.0, 3.0), resolution=(2, 2), **kwargs):
    """The parametric plane [x0, x1] x [y0, y1] at z = 0."""
    return Surface(
        lambda u, v: (u, v, 0.0),
        u_range=(float(x_range[0]), float(x_range[1])),
        v_range=(float(y_range[0]), float(y_range[1])),
        resolution=resolution,
        **kwargs,
    )


def _aim_z_to(surface, direction):
    """Turn a mesh built along +Z so that its axis points along `direction`."""
    jm = _julia_trig()
    d = point3(direction).astype(np.float64)
    length = float(norm(d))
    if length == 0:
        return surface
    d = d / length
    c = min(max(d[2], -1.0), 1.0)
    if math.isclose(c, 1.0, rel_tol=math.sqrt(np.finfo(np.float64).eps), abs_tol=0.0):
        return surface
    if math.isclose(c, -1.0, rel_tol=math.sqrt(np.finfo(np.float64).eps), abs_tol=0.0):
        axis = np.array((1.0, 0.0, 0.0))
    else:
        axis = _cross(np.array((0.0, 0.0, 1.0)), d)
    surface.rotate(jm.acos(c), axis=point3(axis), about_point=ORIGIN)
    return surface


def Cylinder(*, radius=1.0, height=2.0, direction=OUT, resolution=(2, 25), **kwargs):
    jm = _julia_trig()
    r, h = float(radius), float(height)
    surface = Surface(
        lambda u, v: (r * jm.cos(v), r * jm.sin(v), u),
        u_range=(-h / 2, h / 2),
        v_range=(0.0, TAU),
        resolution=resolution,
        **kwargs,
    )
    return _aim_z_to(surface, direction)


def Cone(*, base_radius=1.0, height=1.0, direction=OUT, resolution=(2, 25), **kwargs):
    jm = _julia_trig()
    r, h = float(base_radius), float(height)
    slant = jm.hypot(r, h)
    st, ct = r / slant, h / slant
    surface = Surface(
        lambda u, v: (u * st * jm.cos(v), u * st * jm.sin(v), u * ct),
        u_range=(0.0, slant),
        v_range=(0.0, TAU),
        resolution=resolution,
        **kwargs,
    )
    return _aim_z_to(surface, direction)


def Dot3D(point=ORIGIN, *, radius=0.08, resolution=(17, 9), **kwargs):
    surface = Sphere(radius=radius, resolution=resolution, **kwargs)
    surface.shift(point3(point))
    return surface


def _f32_norm(vector):
    """LinearAlgebra.norm of a Point3f: the sum of squares in Float32."""
    x, y, z = (np.float32(value) for value in vector)
    return float(np.sqrt((x * x + y * y) + z * z))


def Line3D(start=(-1, 0, 0), stop=(1, 0, 0), *, thickness=0.02, resolution=(2, 25), **kwargs):
    a, b = point3(start), point3(stop)
    d = b - a
    length = _f32_norm(d)
    if length == 0:
        raise ValueError("Line3D needs two different points (start == stop)")
    surface = Cylinder(radius=thickness, height=length, direction=d, resolution=resolution, **kwargs)
    surface.shift((0.5 * (a + b).astype(np.float64)).astype(np.float32))
    return surface


def Arrow3D(
    start=(-1, 0, 0),
    stop=(1, 0, 0),
    *,
    thickness=0.02,
    height=0.3,
    base_radius=0.08,
    resolution=(33, 25),
    **kwargs,
):
    """A shaft, one ring where the head starts, and a cone tapering to the tip."""
    jm = _julia_trig()
    a, b = point3(start), point3(stop)
    d = b - a
    length = _f32_norm(d)
    if not length > height:
        raise ValueError(
            f"Arrow3D: the arrow ({round(length, 3)}) is shorter than its own head (height={height})",
        )
    shoulder = length - float(height)
    r_shaft, r_base = float(thickness), float(base_radius)
    nu = max(operator.index(resolution[0]), 4)
    step = 1 / (nu - 1)
    u_shoulder = min(max(round(0.5 * (nu - 1)), 1), nu - 2) * step
    u_head = u_shoulder + step

    def profile(u):
        if u <= u_shoulder:
            return u / u_shoulder * shoulder, r_shaft
        if u <= u_head:
            return shoulder, r_shaft + (u - u_shoulder) / step * (r_base - r_shaft)
        t = (u - u_head) / (1 - u_head)
        return shoulder + t * float(height), r_base * (1 - t)

    def uv_func(u, v):
        z, r = profile(u)
        return r * jm.cos(v), r * jm.sin(v), z

    surface = Surface(
        uv_func,
        u_range=(0.0, 1.0),
        v_range=(0.0, TAU),
        resolution=(nu, resolution[1]),
        **kwargs,
    )
    _aim_z_to(surface, d)
    surface.shift(a)
    return surface


class SurfaceMesh(VGroup):
    """A wireframe of `resolution` smooth curves lifted off the mesh along its normals.

    A class as in ManimGL (`SurfaceMesh(VGroup)` with `init_points`), so a scene
    can subclass it and build the lines its own way; the geometry is the same.
    """

    def __init__(
        self,
        uv_surface,
        resolution=(21, 11),
        stroke_width=1.0,
        stroke_color=GREY_A,
        normal_nudge=1e-2,
        depth_test=True,
        joint_type="no_joint",
        **kwargs,
    ):
        self.uv_surface = uv_surface
        self.resolution = tuple(operator.index(n) for n in resolution)
        self.normal_nudge = float(normal_nudge)
        self.mesh_stroke = (stroke_color, float(stroke_width), joint_type, bool(depth_test))
        super().__init__(**kwargs)          # Mobject.__init__ calls init_points(), as in GL
        stroke_color, stroke_width, joint_type, depth_test = self.mesh_stroke
        for path in self.submobjects:
            path.set_stroke(stroke_color, width=stroke_width)
            path.set_joint_type(joint_type)
            if depth_test:
                path.apply_depth_test()

    def init_points(self):
        surface = self.uv_surface
        full_nu, full_nv = surface.resolution
        part_nu, part_nv = self.resolution
        normals = surface.get_unit_normals()
        nudged = surface.points.astype(np.float64) + self.normal_nudge * normals.astype(np.float64)

        def row(i):
            return nudged[i * full_nv:(i + 1) * full_nv]

        def column(j):
            return nudged[j::full_nv]

        def indices(count, full):
            return [0.0] if count == 1 else linear_range(0.0, full - 1, count)

        for count, full, pick in ((part_nu, full_nu, row), (part_nv, full_nv, column)):
            for index in indices(count, full):
                low, high = math.floor(index), math.ceil(index)
                t = index - low
                path = VMobject()
                path.set_points_smoothly(((1 - t) * pick(low) + t * pick(high)).astype(np.float32))
                self.add(path)


# ── polygon solids ────────────────────────────────────────────────────────
class VGroup3D(VGroup):
    """A VGroup whose members join the z-buffer with flat joints and one shading."""

    def __init__(self, *vmobjects, depth_test=True, shading=(0.2, 0.2, 0.2), joint_type="no_joint", **kwargs):
        super().__init__(*vmobjects, **kwargs)
        self.set_shading(*shading)
        self.set_joint_type(joint_type)
        if depth_test:
            self.apply_depth_test()


class Polyhedron(VGroup):
    """Faces as polygons over shared vertices; `faces` index the vertices from 0."""

    def __init__(
        self,
        vertices,
        faces,
        *,
        fill_color=BLUE_D,
        fill_opacity=1.0,
        stroke_color=BLUE_E,
        stroke_width=1.0,
        shading=(0.2, 0.2, 0.2),
        depth_test=True,
        **kwargs,
    ):
        vertices = [point3(vertex) for vertex in vertices]
        if not len(faces):
            raise ValueError("a polyhedron needs at least one face")
        polygons = []
        for k, face in enumerate(faces):
            if len(face) < 3:
                raise ValueError(f"face {k} has {len(face)} corners and a face needs 3")
            for i in face:
                if not 0 <= operator.index(i) < len(vertices):
                    raise ValueError(
                        f"face {k} refers to vertex {i} and there are {len(vertices)}; the indices start at 0",
                    )
            polygons.append(
                Polygon(
                    *(vertices[i] for i in face),
                    fill_color=fill_color,
                    fill_opacity=fill_opacity,
                    stroke_color=stroke_color,
                    stroke_width=stroke_width,
                ),
            )
        super().__init__(*polygons, **kwargs)
        self.set_shading(*shading)
        self.set_joint_type("no_joint")
        if depth_test:
            self.apply_depth_test()


def Tetrahedron(*, edge_length=1.0, **kwargs):
    u = edge_length * math.sqrt(2) / 4
    return Polyhedron(
        [(u, u, u), (u, -u, -u), (-u, u, -u), (-u, -u, u)],
        [[0, 1, 2], [3, 0, 2], [0, 1, 3], [3, 1, 2]],
        **kwargs,
    )


def Octahedron(*, edge_length=1.0, **kwargs):
    u = edge_length / math.sqrt(2)
    return Polyhedron(
        [(u, 0, 0), (-u, 0, 0), (0, u, 0), (0, -u, 0), (0, 0, u), (0, 0, -u)],
        [[2, 4, 1], [0, 4, 2], [4, 3, 0], [1, 3, 4], [3, 5, 0], [1, 5, 3], [2, 5, 1], [0, 5, 2]],
        **kwargs,
    )


def Icosahedron(*, edge_length=1.0, **kwargs):
    phi = (1 + math.sqrt(5)) / 2
    a, b = edge_length / 2, edge_length * phi / 2
    return Polyhedron(
        [
            (0, a, b), (0, -a, b), (0, a, -b), (0, -a, -b),
            (a, b, 0), (a, -b, 0), (-a, b, 0), (-a, -b, 0),
            (b, 0, a), (b, 0, -a), (-b, 0, a), (-b, 0, -a),
        ],
        [
            [1, 8, 0], [1, 5, 7], [8, 5, 1], [7, 3, 5], [5, 9, 3],
            [8, 9, 5], [3, 2, 9], [9, 4, 2], [8, 4, 9], [0, 4, 8],
            [6, 4, 0], [6, 2, 4], [11, 2, 6], [3, 11, 2], [0, 6, 10],
            [10, 1, 0], [10, 7, 1], [11, 7, 3], [10, 11, 7], [10, 11, 6],
        ],
        **kwargs,
    )


def Dodecahedron(*, edge_length=1.0, **kwargs):
    phi = (1 + math.sqrt(5)) / 2
    a, b, c = edge_length * phi / 2, edge_length / 2, edge_length * (phi * phi) / 2
    return Polyhedron(
        [
            (a, a, a), (a, a, -a), (a, -a, a), (a, -a, -a),
            (-a, a, a), (-a, a, -a), (-a, -a, a), (-a, -a, -a),
            (0, b, c), (0, b, -c), (0, -b, -c), (0, -b, c),
            (b, c, 0), (-b, c, 0), (b, -c, 0), (-b, -c, 0),
            (c, 0, b), (-c, 0, b), (c, 0, -b), (-c, 0, -b),
        ],
        [
            [18, 16, 0, 12, 1], [3, 18, 16, 2, 14],
            [3, 10, 9, 1, 18], [1, 9, 5, 13, 12],
            [0, 8, 4, 13, 12], [2, 16, 0, 8, 11],
            [4, 17, 6, 11, 8], [17, 19, 5, 13, 4],
            [19, 7, 15, 6, 17], [6, 15, 14, 2, 11],
            [19, 5, 9, 10, 7], [7, 10, 3, 14, 15],
        ],
        **kwargs,
    )


# ── cubes and prisms ──────────────────────────────────────────────────────
def Square3D(*, side_length=2.0, resolution=(2, 2), color=GREY_C, opacity=1.0, shading=SURFACE_SHADING, **kwargs):
    """A flat unit patch scaled to `side_length`, ready to become a cube face."""
    surface = Surface(
        lambda u, v: (u, v, 0.0),
        u_range=(-1.0, 1.0),
        v_range=(-1.0, 1.0),
        resolution=resolution,
        color=color,
        opacity=opacity,
        shading=shading,
        **kwargs,
    )
    return surface.scale(float(side_length) / 2)


def _square_to_cube_faces(square):
    """cube.py's six faces: +Z, then the four compass rotations, then -Z."""
    radius = np.float32(square.get_height()) / np.float32(2)
    square.move_to(radius * OUT)
    faces = [square.copy()]
    for vector in compass_directions(4):
        faces.append(square.copy().rotate(math.pi / 2, axis=vector, about_point=ORIGIN))
    faces.append(square.copy().rotate(math.pi, axis=RIGHT, about_point=ORIGIN))
    return faces


def _check_no_vector_style(what, kwargs):
    for key in ("fill_color", "fill_opacity", "stroke_color", "stroke_width", "stroke_opacity"):
        if key in kwargs:
            raise ValueError(
                f"{what} is built from meshes and a mesh has one colour: no {key}. "
                f"Use `color=` and `opacity=`, or ask for V{what}, the six-polygon version",
            )


class Cube(Group):
    """Six Square3D meshes (a Group, like GL's Cube of Square3D faces)."""

    def __init__(
        self,
        *,
        side_length=2.0,
        color=BLUE,
        opacity=1.0,
        shading=(0.1, 0.5, 0.1),
        square_resolution=(2, 2),
        depth_test=True,
        **kwargs,
    ):
        _check_no_vector_style("Cube", kwargs)
        face = Square3D(
            side_length=side_length,
            resolution=square_resolution,
            color=color,
            opacity=opacity,
            shading=shading,
            depth_test=depth_test,
        )
        super().__init__(*_square_to_cube_faces(face), **kwargs)


class VCube(VGroup):
    """Six Square polygons: the vector cube (takes the vector style keywords)."""

    def __init__(
        self,
        *,
        side_length=2.0,
        fill_color=BLUE_D,
        fill_opacity=1.0,
        stroke_width=0.0,
        shading=(0.2, 0.2, 0.2),
        depth_test=True,
        **kwargs,
    ):
        r = float(side_length) / 2
        faces = []
        for axis, sign in ((2, 1), (1, -1), (0, 1), (1, 1), (0, -1), (2, -1)):
            square = Square(side_length, fill_color=fill_color, fill_opacity=fill_opacity, stroke_width=stroke_width)
            if axis == 0:
                square.rotate(math.pi / 2, axis=UP, about_point=ORIGIN)
            if axis == 1:
                square.rotate(math.pi / 2, axis=RIGHT, about_point=ORIGIN)
            offset = np.zeros(3, dtype=np.float32)
            offset[axis] = np.float32(sign * r)
            square.shift(offset)
            faces.append(square)
        super().__init__(*faces, **kwargs)
        self.set_shading(*shading)
        self.set_joint_type("no_joint")
        if depth_test:
            self.apply_depth_test()


class Prism(Cube):
    def __init__(self, width=3.0, height=2.0, depth=1.0, **kwargs):
        super().__init__(**kwargs)
        self.set_width(width, stretch=True)
        self.set_height(height, stretch=True)
        self.set_depth(depth, stretch=True)


class VPrism(VCube):
    def __init__(self, width=3.0, height=2.0, depth=1.0, **kwargs):
        super().__init__(**kwargs)
        self.set_width(width, stretch=True)
        self.set_height(height, stretch=True)
        self.set_depth(depth, stretch=True)


class Prismify(VGroup):
    """A flat shape extruded along `direction`: the base, one wall per edge, the top."""

    def __init__(self, flat, *, depth=1.0, direction=IN, shading=(0.2, 0.2, 0.2), depth_test=True, **kwargs):
        if not flat.has_points():
            raise ValueError("Prismify needs a shape with points; a group has none of its own")
        vector = np.float32(depth) * point3(direction)
        anchors = flat.get_anchors()
        pieces = [flat.copy()]
        count = len(anchors)
        for i in range(count):
            p1, p2 = anchors[i], anchors[(i + 1) % count]
            delta = p2 - p1
            if np.float32((delta[0] * delta[0] + delta[1] * delta[1]) + delta[2] * delta[2]) < np.float32(1e-12):
                continue
            wall = VMobject()
            wall.match_style(flat)
            wall.set_points_as_corners((p1, p2, p2 + vector, p1 + vector, p1))
            pieces.append(wall)
        top = flat.copy()
        top.shift(vector)
        pieces.append(top)
        super().__init__(*pieces, **kwargs)
        self.set_shading(*shading)
        self.set_joint_type("no_joint")
        if depth_test:
            self.apply_depth_test()
