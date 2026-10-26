"""Planar shapes, stored as float32."""

import math
import operator

import numpy as np

from ._atan import scalar_atan2

from .algebra import (
    _normalize,
    angle_between_vectors,
    apply_matrix_rows,
    compass_directions,
    norm,
    rotate_vector,
    rotation_matrix,
)
from .bezier import cubic_to_two_quadratics, quadratic_bezier_points_for_arc
from .mobject import Mobject, VGroup, VMobject
from .transforms import point3


class Arc(VMobject):
    def __init__(
        self,
        start_angle=0.0,
        angle=math.tau / 4,
        radius=1.0,
        n_components=None,
        arc_center=(0, 0, 0),
        **kwargs,
    ):
        self.start_angle = float(start_angle)
        self.angle = float(angle)
        self.radius = float(radius)
        self.n_components = math.floor(
            15 * (abs(angle) / math.tau),
        ) + 1 if n_components is None else operator.index(
            n_components,
        )
        super().__init__(**kwargs)
        self.set_points(quadratic_bezier_points_for_arc(angle, self.n_components))
        # GL's constructor always rotates, scales and shifts. On points without a -0.0 a
        # rotation by +0.0 about the origin, a scale by 1 about the origin and a shift by a
        # +0.0 vector map every coordinate to itself bit for bit (only -0.0 - 0 + 0 moves, to
        # +0.0), and `set_points` already left the flags the verbs would set; so the identity
        # verbs are skipped: the same state at a
        # third of the cost, which a gasket of 1 460 circles per frame pays 121 times.
        identity = not (np.signbit(self.points) & (self.points == 0)).any()      # no -0.0 anywhere
        if not (identity and self.start_angle == 0.0 and math.copysign(1.0, self.start_angle) > 0):
            self.rotate(start_angle, about_point=(0, 0, 0))
        if not (identity and self.radius == 1.0):
            self.scale(radius, about_point=(0, 0, 0))
        centre = point3(arc_center)
        if not (identity and not centre.any() and not np.signbit(centre).any()):
            self.shift(arc_center)

    def get_arc_center(self):
        if len(self.points) < 3:
            raise ValueError("get_arc_center needs at least three curve points")
        first, handle, last = self.points[:3]
        normal1 = rotate_vector(handle - first, math.tau / 4)
        normal2 = rotate_vector(handle - last, math.tau / 4)
        return _find_intersection(first, normal1, last, normal2)

    def get_start_angle(self):
        vector = self.get_start() - self.get_arc_center()
        return scalar_atan2(float(vector[1]), float(vector[0])) % math.tau


class Circle(Arc):
    def __init__(self, radius=1.0, **kwargs):
        kwargs.setdefault("stroke_color", "#FC6255")
        super().__init__(angle=math.tau, radius=radius, **kwargs)

    def get_radius(self):
        return self.get_width() / np.float32(2)

    def point_at_angle(self, angle):
        return self.point_from_proportion((angle - self.get_start_angle()) % math.tau / math.tau)


class Dot(Circle):
    def __init__(self, point=(0, 0, 0), radius=0.08, **kwargs):
        kwargs.setdefault("fill_color", "#FFFFFF")
        kwargs.setdefault("fill_opacity", 1.0)
        kwargs.setdefault("stroke_color", "#000000")
        kwargs.setdefault("stroke_width", 0.0)
        point = point.get_center() if isinstance(point, Mobject) else point
        super().__init__(radius=radius, arc_center=point, **kwargs)


class Ellipse(Circle):
    def __init__(self, width=2.0, height=1.0, **kwargs):
        super().__init__(**kwargs)
        self.set_width(width, stretch=True)
        self.set_height(height, stretch=True)


class Polygon(VMobject):
    def __init__(self, *vertices, **kwargs):
        if len(vertices) < 3:
            raise ValueError("a polygon needs at least three vertices")
        super().__init__(**kwargs)
        points = np.asarray(vertices, dtype=np.float32)
        self.set_points_as_corners(np.vstack((points, points[:1])))

    def round_corners(self, radius=None):
        vertices = self.get_vertices().copy()
        count = len(vertices)
        if radius is None:
            lengths = norm(np.roll(vertices, -1, axis=0) - vertices)
            radius = 0.25 * float(np.min(lengths[lengths > np.float32(1e-8)]))
        arcs = []
        for index in range(count):
            first, vertex, last = vertices[index], vertices[(index + 1) % count], vertices[(index + 2) % count]
            incoming, outgoing = vertex - first, last - vertex
            incoming = _normalize(incoming)
            outgoing = _normalize(outgoing)
            angle = angle_between_vectors(incoming, outgoing)
            cut = np.float32(radius * math.tan(angle / 2))
            cross = incoming[0] * outgoing[1] - incoming[1] * outgoing[0]
            signed_angle = float(np.sign(radius * float(cross))) * angle
            start, end = vertex - cut * incoming, vertex + cut * outgoing
            if signed_angle == 0:
                arc = VMobject().set_points_as_corners([start, end])
            else:
                arc = Arc(angle=signed_angle, n_components=2)
                arc.put_start_and_end_on(start, end)
            arcs.append(arc)
        arcs = [arcs[-1], *arcs[:-1]]
        self.clear_points()
        for index, arc in enumerate(arcs):
            self.add_subpath(arc.points)
            self.add_line_to(arcs[(index + 1) % count].get_start())
        return self


class RegularPolygon(Polygon):
    def __init__(self, n=6, radius=1.0, start_angle=None, **kwargs):
        n = operator.index(n)
        if n < 3:
            raise ValueError("a regular polygon needs at least three vertices")
        if start_angle is None:
            start_angle = (n % 2) * 90 * (math.tau / 360)
        start = rotate_vector(point3((radius, 0, 0)), start_angle)
        super().__init__(*compass_directions(n, start), **kwargs)


class Triangle(RegularPolygon):
    def __init__(self, radius=1.0, start_angle=None, **kwargs):
        super().__init__(3, radius, start_angle, **kwargs)


class Rectangle(Polygon):
    def __init__(self, width=4.0, height=2.0, **kwargs):
        super().__init__((1, 1, 0), (-1, 1, 0), (-1, -1, 0), (1, -1, 0), **kwargs)
        self.set_width(width, stretch=True)
        self.set_height(height, stretch=True)


class Square(Rectangle):
    def __init__(self, side_length=2.0, **kwargs):
        super().__init__(side_length, side_length, **kwargs)


class RoundedRectangle(Rectangle):
    def __init__(self, width=4.0, height=2.0, corner_radius=0.5, **kwargs):
        super().__init__(width, height, **kwargs)
        self.round_corners(corner_radius)


class Star(Polygon):
    def __init__(
        self,
        n=5,
        outer_radius=1.0,
        inner_radius=None,
        density=2,
        start_angle=math.tau / 4,
        **kwargs,
    ):
        n = operator.index(n)
        if n < 2:
            raise ValueError("a star needs at least two points")
        inner_angle = math.tau / (2 * n)
        if inner_radius is None:
            if not 0 < density < n / 2:
                raise ValueError("density must be in [1, n/2), or specify inner_radius")
            outer_angle = math.tau * density / n
            inverse_x = 1 - math.tan(inner_angle) * ((math.cos(outer_angle) - 1) / math.sin(outer_angle))
            inner_radius = outer_radius / (math.cos(inner_angle) * inverse_x)
        outer = compass_directions(n, rotate_vector(point3((outer_radius, 0, 0)), start_angle))
        inner = compass_directions(n, rotate_vector(point3((inner_radius, 0, 0)), start_angle + inner_angle))
        vertices = np.empty((2 * n, 3), dtype=np.float32)
        vertices[::2], vertices[1::2] = outer, inner
        super().__init__(*vertices, **kwargs)


def endpoints(start, end):
    first = start.get_center() if isinstance(start, Mobject) else point3(start)
    last = end.get_center() if isinstance(end, Mobject) else point3(end)
    vector = (last - first).astype(np.float64)
    length = norm(vector)
    unit = np.zeros(3, dtype=np.float32) if length == 0 else _normalize(vector).astype(np.float32)
    first = start.get_bounding_box_point(unit) if isinstance(start, Mobject) else first
    last = end.get_bounding_box_point(-unit) if isinstance(end, Mobject) else last
    return first, last


class Line(VMobject):
    def __init__(self, start=(-1, 0, 0), end=(1, 0, 0), buff=0, path_arc=0, **kwargs):
        self.buff, self.path_arc = float(buff), float(path_arc)
        super().__init__(**kwargs)
        self.set_points_by_ends(*endpoints(start, end), buff=buff, path_arc=path_arc)

    def get_length(self):
        return float(norm(self.get_vector()))

    def put_start_and_end_on(self, start, end):
        if np.all(np.abs(self.get_vector()) <= np.float32(1e-8)):
            return self.set_points_by_ends(start, end, buff=0, path_arc=0)
        return super().put_start_and_end_on(start, end)


class DashedLine(Line):
    def __init__(
        self,
        start=(-1, 0, 0),
        end=(1, 0, 0),
        dash_length=0.05,
        positive_space_ratio=0.5,
        **kwargs,
    ):
        if dash_length <= 0 or not 0 < positive_space_ratio <= 1:
            raise ValueError("dash_length must be positive and positive_space_ratio must be in (0, 1]")
        base = Line(start, end, **kwargs)
        full = float(dash_length) / float(positive_space_ratio)
        count = max(1, math.ceil((base.get_arc_length() / full) * (1 - 1e-6)))
        VMobject.__init__(self)
        self.match_style(base)
        period = 1.0 / count
        partial = float(positive_space_ratio) * period
        ladder = 1.0 - period + partial
        for index in range(count):
            start = (index * period) / ladder
            end = min(start + partial, 1.0)
            piece = VMobject().match_points(base).pointwise_become_partial(base, start, end)
            piece.match_style(base)
            self.add(piece)

    def get_start(self):
        return self.submobjects[0].get_start() if self.submobjects else super().get_start()

    def get_end(self):
        return self.submobjects[-1].get_end() if self.submobjects else super().get_end()


class Arrow(Line):
    """One filled contour, including its tip, stored as float32."""

    def __init__(
        self,
        start=(-1, 0, 0),
        end=(1, 0, 0),
        buff=0.25,
        path_arc=0.0,
        thickness=3.0,
        tip_width_ratio=5.0,
        tip_angle=math.pi / 3,
        max_tip_length_to_length_ratio=0.5,
        max_width_to_length_ratio=0.1,
        **kwargs,
    ):
        self.thickness = float(thickness)
        self.tip_width_ratio = float(tip_width_ratio)
        self.tip_angle = float(tip_angle)
        self.max_tip_length_to_length_ratio = float(max_tip_length_to_length_ratio)
        self.max_width_to_length_ratio = float(max_width_to_length_ratio)
        kwargs.setdefault("fill_color", "#BBBBBB")
        kwargs.setdefault("fill_opacity", 1.0)
        kwargs.setdefault("stroke_width", 0.0)
        super().__init__(start, end, buff=buff, path_arc=path_arc, **kwargs)

    def set_points_by_ends(self, start, end, buff=0, path_arc=0):
        start, end = point3(start), point3(end)
        vector = (end - start).astype(np.float64)
        length = max(float(norm(vector)), 1e-8)
        unit = (vector / length).astype(np.float32)
        width = self.thickness * 0.015
        ratio = self.max_width_to_length_ratio / (width / (length - buff))
        if ratio < 1:
            width *= ratio
        tip_width = self.tip_width_ratio * width
        tip_length = tip_width / (2 * math.tan(self.tip_angle / 2))
        ratio = self.max_tip_length_to_length_ratio / (tip_length / (length - buff))
        if ratio < 1:
            tip_length *= ratio
            tip_width *= ratio
        if path_arc == 0:
            start = start + np.float32(buff) * unit
            end = end - np.float32(buff) * unit
        else:
            radius = length / 2 / math.sin(path_arc / 2)
            midpoint = (np.float64(0.5) * (start + end)).astype(np.float32)
            center = midpoint + rotate_vector((0.5 * vector).astype(np.float32), math.pi / 2).astype(
                np.float64,
            ) / math.tan(
                path_arc / 2,
            )
            start = center + rotate_vector(start - center, buff / radius)
            end = center + rotate_vector(end - center, -buff / radius)
            path_arc -= (2 * buff + tip_length) / radius
        vector = (end - start).astype(np.float64)
        length = float(norm(vector))
        if path_arc == 0:
            base = np.array(
                [(length - tip_length, 0, 0), (0.5 * (length - tip_length), 0, 0), (0, 0, 0)],
                dtype=np.float32,
            )
            first = base + np.array([0, width / 2, 0], dtype=np.float32)
            second = first[::-1] + np.array([0, -width, 0], dtype=np.float32)
        else:
            arc = quadratic_bezier_points_for_arc(path_arc)
            rotation = rotation_matrix(math.pi / 2 - path_arc)

            def place(points, r):
                rotated = apply_matrix_rows(points.astype(np.float64) * r, rotation).astype(np.float32)
                return rotated + np.array([0, -radius, 0], dtype=np.float32)

            first = place(arc, radius + width / 2)
            second = place(arc[::-1], radius - width / 2)
        self.set_points(first)
        self.add_line_to((0, tip_width / 2, 0))
        self.add_line_to((-tip_length, 0, 0))
        self.add_line_to((0, -tip_width / 2, 0))
        self.add_line_to(second[0])
        self.add_subpath(second)
        self.add_line_to(first[0])
        if length > 0.0:   # a zero-length arrow has no direction: GL rotates it by 0 about a zero axis (identity)
            self.rotate(scalar_atan2(float(vector[1]), float(vector[0])) - self.get_angle())
            self.rotate(
                math.pi / 2 - math.acos(float(np.clip(_normalize(vector)[2], -1, 1))),
                axis=rotate_vector(self.get_unit_vector(), -math.pi / 2),
            )
        return self.shift(start - self.get_start())

    def get_start(self):
        return ((self.points[0] + self.points[-3]) * np.float64(0.5)).astype(np.float32)

    def get_end(self):
        return self.points[(len(self.points) - 9) // 2 + 3].copy()

    def put_start_and_end_on(self, start, end):
        # The existing tip is transformed along with the shaft.
        return VMobject.put_start_and_end_on(self, start, end)


class AnnularSector(VMobject):
    def __init__(
        self,
        angle=math.tau / 4,
        start_angle=0.0,
        inner_radius=1.0,
        outer_radius=2.0,
        arc_center=(0, 0, 0),
        **kwargs,
    ):
        kwargs.setdefault("fill_opacity", 1.0)
        kwargs.setdefault("stroke_width", 0.0)
        super().__init__(**kwargs)
        outer = Arc(start_angle, angle, outer_radius, arc_center=arc_center)
        inner = np.repeat(point3(arc_center)[None], len(outer.points), axis=0) if inner_radius == 0 else Arc(
            start_angle,
            angle,
            inner_radius,
            arc_center=arc_center,
        ).points
        self.set_points(inner[::-1])
        self.add_line_to(outer.points[0])
        self.add_subpath(outer.points)
        self.add_line_to(inner[-1])


class Sector(AnnularSector):
    def __init__(self, angle=math.tau / 4, radius=1.0, start_angle=0.0, **kwargs):
        super().__init__(
            angle=angle,
            start_angle=start_angle,
            inner_radius=0.0,
            outer_radius=radius,
            **kwargs,
        )


class Annulus(VMobject):
    def __init__(self, inner_radius=1.0, outer_radius=2.0, center=(0, 0, 0), **kwargs):
        kwargs.setdefault("fill_opacity", 1.0)
        kwargs.setdefault("stroke_width", 0.0)
        super().__init__(**kwargs)
        self.add_subpath(np.float32(outer_radius) * quadratic_bezier_points_for_arc(math.tau))
        self.add_subpath(np.float32(inner_radius) * quadratic_bezier_points_for_arc(-math.tau))
        self.shift(center)


class ArcBetweenPoints(Arc):
    def __init__(self, start, end, angle=math.tau / 4, n_components=None, **kwargs):
        if angle == 0:
            VMobject.__init__(self, **kwargs)
            self.set_points_as_corners(((-1, 0, 0), (1, 0, 0)))
        else:
            super().__init__(angle=angle, n_components=n_components, **kwargs)
        self.put_start_and_end_on(start, end)


class TangentialArc(ArcBetweenPoints):
    """An arc of `radius` tangent to two intersecting lines (CE's).

    `corner=(s1, s2)` picks one of the four corners: each sign says which way
    to go along the corresponding line from the intersection.
    """

    def __init__(self, line1, line2, radius, corner=(1, 1), **kwargs):
        from .annotations import line_intersection

        radius = float(radius)
        if not radius > 0:
            raise ValueError("a tangential arc needs a positive radius")
        self.line1 = line1
        self.line2 = line2
        intersection = line_intersection(*line1.get_start_and_end(), *line2.get_start_and_end()).astype(np.float64)
        first_sign, second_sign = corner
        first = first_sign * line1.get_unit_vector().astype(np.float64)
        second = second_sign * line2.get_unit_vector().astype(np.float64)
        corner_angle = angle_between_vectors(first, second)
        distance = radius / math.tan(corner_angle / 2)
        first_point = intersection + distance * first
        second_point = intersection + distance * second
        cross = first[0] * second[1] - first[1] * second[0]
        start, end = (first_point, second_point) if cross < 0 else (second_point, first_point)
        half_chord = float(np.linalg.norm(end - start)) / 2
        super().__init__(start, end, angle=2 * math.asin(min(1.0, half_chord / radius)), **kwargs)
        self.radius = radius


class ArcPolygonFromArcs(VMobject):
    """One closed path through arcs given in order (CE's).

    A gap between an arc's end and the next arc's start is closed with a
    straight segment, split into as many curves as CE gives it (the arc's
    curve count times the length ratio, plus one). The arcs stay as children
    and are drawn too; hide them (`stroke_width=0`) to see only the outline.
    """

    def __init__(self, *arcs, **kwargs):
        if not arcs or not all(isinstance(arc, Arc) for arc in arcs):
            raise ValueError("All ArcPolygon submobjects must be of type Arc/ArcBetweenPoints")
        super().__init__(**kwargs)
        self.add(*arcs)
        self.arcs = list(arcs)
        self.set_points(arcs[0].points)
        for index, arc in enumerate(arcs):
            following = arcs[(index + 1) % len(arcs)]
            gap_start = arc.get_end().astype(np.float64)
            gap_end = following.get_start().astype(np.float64)
            length = float(np.linalg.norm(gap_end - gap_start))
            arc_length = float(arc.get_arc_length())
            if length > 1e-6 and arc_length > 0:
                pieces = int(arc.get_num_curves() * length / arc_length) + 1
                for step in range(1, pieces + 1):
                    self.add_line_to(gap_start + (gap_end - gap_start) * (step / pieces))
            if index + 1 < len(arcs):
                self.append_points(following.points[1:])


class Elbow(VMobject):
    def __init__(self, width=0.2, angle=0.0, **kwargs):
        super().__init__(**kwargs)
        self.set_points_as_corners(((0, 1, 0), (1, 1, 0), (1, 0, 0)))
        self.set_width(width, about_point=(0, 0, 0))
        self.rotate(angle, about_point=(0, 0, 0))


class ScreenRectangle(Rectangle):
    def __init__(self, aspect_ratio=16 / 9, height=4.0, **kwargs):
        super().__init__(width=aspect_ratio * height, height=height, **kwargs)


class FullScreenRectangle(ScreenRectangle):
    def __init__(self, height=8.0, **kwargs):
        kwargs.setdefault("fill_color", "#222222")
        kwargs.setdefault("fill_opacity", 1.0)
        kwargs.setdefault("stroke_width", 0.0)
        super().__init__(height=height, **kwargs)


class FullScreenFadeRectangle(FullScreenRectangle):
    def __init__(self, **kwargs):
        kwargs.setdefault("fill_color", "#000000")
        kwargs.setdefault("fill_opacity", 0.7)
        super().__init__(**kwargs)


class VDict(VGroup):
    def __init__(self, pairs=(), **kwargs):
        super().__init__(**kwargs)
        for key, mob in (pairs.items() if hasattr(pairs, "items") else pairs):
            self[key] = mob

    def __getitem__(self, key):
        if not isinstance(key, str):
            return super().__getitem__(key)
        for child in self.submobjects:
            if key in child.get_keys():
                return child
        raise KeyError(key)

    def __setitem__(self, key, mob):
        if not isinstance(mob, VMobject):
            raise TypeError("VDict values must be VMobjects")
        if key in self:
            del self[key]
        mob.set_key(key)
        self.add(mob)

    def __delitem__(self, key):
        self.remove(self[key])

    def __contains__(self, key):
        return any(key in child.get_keys() for child in self.submobjects)

    def get_keys(self):
        return self.keys

    def get_all_submobjects(self):
        return list(self.submobjects)


class Polygram(VMobject):
    def __init__(self, *vertex_groups, **kwargs):
        if not vertex_groups:
            raise ValueError("Polygram needs at least one vertex group")
        super().__init__(**kwargs)
        for vertices in vertex_groups:
            if len(vertices) < 3:
                raise ValueError("each closed outline needs at least three vertices")
            points = np.asarray(vertices, dtype=np.float32)
            curve = VMobject().set_points_as_corners(np.vstack((points, points[:1])))
            self.add_subpath(curve.points)


class RegularPolygram(Polygram):
    def __init__(self, n=5, density=2, radius=1.0, start_angle=None, **kwargs):
        n, density = operator.index(n), operator.index(density)
        if n < 3 or not 0 < density < n:
            raise ValueError("a polygram needs n >= 3 and 0 < density < n")
        groups = math.gcd(n, density)
        vertices, step = n // groups, density // groups
        if vertices < 3:
            raise ValueError("the density reduces this polygram to a segment")
        start_angle = (vertices % 2) * math.pi / 2 if start_angle is None else start_angle
        paths = []
        for group in range(groups):
            angle = start_angle + (group / groups) * math.tau / vertices
            base = compass_directions(vertices, rotate_vector(point3((radius, 0, 0)), angle))
            order = [(k * step) % vertices for k in range(vertices)]
            paths.append(base[order])
        super().__init__(*paths, **kwargs)


class ConvexHull(Polygon):
    def __init__(self, *points, **kwargs):
        if len(points) < 3:
            raise ValueError("a hull needs at least three points")
        points = sorted(dict.fromkeys(tuple(point3(point)) for point in points), key=lambda p: (p[0], p[1]))

        def cross(origin, first, second):
            return (first[0] - origin[0]) * (second[1] - origin[1]) - (first[1] - origin[1]) * (second[0] - origin[0])

        def half(sequence):
            result = []
            for point in sequence:
                while len(result) >= 2 and cross(result[-2], result[-1], point) <= 0:
                    result.pop()
                result.append(point)
            return result

        hull = half(points)[:-1] + half(reversed(points))[:-1]
        if len(hull) < 3:
            raise ValueError("the points are collinear; use Line for a segment")
        super().__init__(*hull, **kwargs)


class Polyline(VMobject):
    def __init__(self, *vertices, **kwargs):
        if len(vertices) < 2:
            raise ValueError("a polyline needs at least two points")
        super().__init__(**kwargs)
        self.set_points_as_corners(vertices)


class CubicBezier(VMobject):
    def __init__(self, start, handle1, handle2, end, **kwargs):
        super().__init__(**kwargs)
        first, middle, second = cubic_to_two_quadratics(start, handle1, handle2, end)
        self.set_points((point3(start), first, middle, second, point3(end)))


class ArcPolygon(VMobject):
    def __init__(self, *corners, radius=None, angle=math.pi / 4, **kwargs):
        if len(corners) < 3:
            raise ValueError("an arc polygon needs at least three corners")
        super().__init__(**kwargs)
        points = np.asarray(corners, dtype=np.float32)
        for start, end in zip(points, np.roll(points, -1, axis=0)):
            sweep = angle
            if radius is not None:
                distance = float(norm(end - start))
                if 2 * radius < distance:
                    raise ValueError("radius is smaller than half the distance between corners")
                sweep = 2 * math.asin(distance / (2 * radius))
            self.add_subpath(ArcBetweenPoints(start, end, angle=sweep).points)


class VectorizedPoint(VMobject):
    def __init__(self, location=(0, 0, 0), color="#000000", **kwargs):
        kwargs.setdefault("fill_color", color)
        kwargs.setdefault("stroke_color", color)
        kwargs.setdefault("fill_opacity", 0.0)
        kwargs.setdefault("stroke_width", 0.0)
        super().__init__(**kwargs)
        self.set_points([location])

    def length_over_dim(self, dim):
        if operator.index(dim) not in (0, 1, 2):
            raise ValueError("dimension must be 0, 1 or 2")
        return np.float32(1e-6)


def _find_intersection(p0, v0, p1, v1, threshold=1e-5):
    """Ray intersection, with a 1e-5 degeneracy threshold."""
    p0, v0, p1, v1 = np.asarray([p0, v0, p1, v1], dtype=np.float64)
    difference = p1 - p0
    if any(value[2] != 0 for value in (p0, v0, p1, v1)):
        first, second = np.cross(v1, difference), np.cross(v1, v0)
        products = first * first
        numerator = (products[0] + products[1]) + products[2]
        products = first * second
        denominator = (products[0] + products[1]) + products[2]
    else:
        numerator = v1[0] * difference[1] - v1[1] * difference[0]
        denominator = v1[0] * v0[1] - v1[1] * v0[0]
    if abs(denominator) < threshold:
        denominator = math.inf
    return (p0 + (numerator / denominator) * v0).astype(np.float32)
