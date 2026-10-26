"""The convex hull of points in space, for ConvexHull3D."""

import numpy as np


def convex_hull_triangles(points, tolerance=1e-5):
    """The triangles of the convex hull of `points`, as index triples.

    Incremental: a tetrahedron from four extreme points, then every other
    point in the given order replaces the faces it sees with a fan to the
    horizon. Points within `tolerance` of the hull are left out. Every
    triangle is counterclockwise seen from outside, and the order of the
    faces depends only on the input.
    """
    pts = np.asarray(points, dtype=np.float64)
    if pts.ndim != 2 or pts.shape[1] != 3:
        raise ValueError("ConvexHull3D needs points with three coordinates")
    if len(pts) < 4:
        raise ValueError("a 3D hull needs at least four points")
    tolerance = float(tolerance)

    first = 0
    second = int(np.argmax(np.linalg.norm(pts - pts[first], axis=1)))
    if np.linalg.norm(pts[second] - pts[first]) <= tolerance:
        raise ValueError("the points coincide")
    direction = pts[second] - pts[first]
    third = int(np.argmax(np.linalg.norm(np.cross(pts - pts[first], direction), axis=1)))
    if np.linalg.norm(np.cross(pts[third] - pts[first], direction)) / np.linalg.norm(direction) <= tolerance:
        raise ValueError("the points are collinear; use Line for a segment")
    normal = np.cross(pts[second] - pts[first], pts[third] - pts[first])
    heights = (pts - pts[first]) @ normal / np.linalg.norm(normal)
    fourth = int(np.argmax(np.abs(heights)))
    if abs(heights[fourth]) <= tolerance:
        raise ValueError("the points are coplanar; use ConvexHull for a flat hull")

    def planes(faces):
        corners = pts[np.asarray(faces)]
        normals = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
        normals /= np.linalg.norm(normals, axis=1, keepdims=True)
        return corners[:, 0], normals

    inside = pts[[first, second, third, fourth]].mean(axis=0)
    faces = [(first, second, third), (first, second, fourth), (first, third, fourth), (second, third, fourth)]
    origins, normals = planes(faces)
    faces = [
        (face[0], face[2], face[1]) if np.dot(inside - origin, normal) > 0 else face
        for face, origin, normal in zip(faces, origins, normals)
    ]
    origins, normals = planes(faces)

    seeded = {first, second, third, fourth}
    for index in range(len(pts)):
        if index in seeded:
            continue
        distances = np.einsum("ij,ij->i", pts[index] - origins, normals)
        mask = distances > tolerance
        if not mask.any():
            continue
        visible = [face for face, seen in zip(faces, mask) if seen]
        edges = {(face[k], face[(k + 1) % 3]) for face in visible for k in range(3)}
        horizon = [
            (face[k], face[(k + 1) % 3])
            for face in visible
            for k in range(3)
            if (face[(k + 1) % 3], face[k]) not in edges
        ]
        faces = [face for face, seen in zip(faces, mask) if not seen]
        faces.extend((a, b, index) for a, b in horizon)
        origins, normals = planes(faces)
    return faces
