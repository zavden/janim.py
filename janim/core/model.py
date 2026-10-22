"""Wavefront OBJ/MTL models as meshes.

Each `usemtl` run becomes one part: a TexturedSurface when its material has a
readable `map_Kd`, otherwise a Surface coloured by `Kd` (or the model colour).
Corners without an explicit normal get an area-weighted vertex normal.
"""
from pathlib import Path

import numpy as np

from janim.constants import WHITE

from .colorspace import color_to_rgba
from .image import TexturedSurface, _load_pixels
from .mobject import Group
from .surface import Surface, _cross

_MODEL_SHADING = (0.3, 0.2, 0.4)        # Surface's default
_MODEL_NORMAL_NUDGE = 1e-3              # Surface's default


class _ObjMaterial:
    __slots__ = ("name", "kd", "map_kd")

    def __init__(self, name, kd, map_kd):
        self.name = name
        self.kd = kd
        self.map_kd = map_kd


def _read_mtl(path):
    """The materials of an MTL file: `newmtl`, `Kd` and `map_Kd` (its last token is the file)."""
    materials = {}
    path = Path(path)
    if not path.is_file():
        return materials
    directory = path.parent
    name = ""
    kd = None
    map_kd = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        key = parts[0]
        if key == "newmtl":
            if name:
                materials[name] = _ObjMaterial(name, kd, map_kd)
            name = " ".join(parts[1:])
            kd = None
            map_kd = None
        elif key == "Kd" and len(parts) >= 4:
            kd = (float(parts[1]), float(parts[2]), float(parts[3]))
        elif key == "map_Kd" and len(parts) >= 2:
            file = parts[-1]
            map_kd = file if Path(file).is_absolute() else str(directory / file)
    if name:
        materials[name] = _ObjMaterial(name, kd, map_kd)
    return materials


def _obj_corner(token, nv, nt, nn):
    """One `v/vt/vn` token as 1-based indices (0 = absent); negative indices count from the end."""
    fields = token.split("/")

    def at(i, n):
        if i < len(fields) and fields[i]:
            k = int(fields[i])
            return n + k + 1 if k < 0 else k
        return 0

    return (at(0, nv), at(1, nt), at(2, nn))


def _read_obj(path):
    vertices, texcoords, normals = [], [], []
    faces = {}
    order = []
    materials = {}
    current = ""
    path = Path(path)
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        key = parts[0]
        if key == "v" and len(parts) >= 4:
            vertices.append(np.array((float(parts[1]), float(parts[2]), float(parts[3]))))
        elif key == "vt" and len(parts) >= 2:
            texcoords.append(np.array((float(parts[1]), float(parts[2]) if len(parts) >= 3 else 0.0)))
        elif key == "vn" and len(parts) >= 4:
            normals.append(np.array((float(parts[1]), float(parts[2]), float(parts[3]))))
        elif key == "mtllib" and len(parts) >= 2:
            materials.update(_read_mtl(path.parent / " ".join(parts[1:])))
        elif key == "usemtl":
            current = " ".join(parts[1:])
        elif key == "f" and len(parts) >= 4:
            corners = [_obj_corner(token, len(vertices), len(texcoords), len(normals)) for token in parts[1:]]
            if current not in faces:
                order.append(current)
                faces[current] = []
            faces[current].append(corners)
    return vertices, texcoords, normals, faces, order, materials


def _obj_mesh(vertices, texcoords, normals, faces):
    """Unique (v, vt, vn) corners, fan-triangulated faces, and area-weighted missing normals."""
    index_of = {}
    points, uvs, corner_normals = [], [], []
    indices = []
    zero3 = np.zeros(3)
    for face in faces:
        ids = []
        for corner in face:
            if not 1 <= corner[0] <= len(vertices):
                raise ValueError(f"OBJ face refers to vertex {corner[0]} of {len(vertices)}")
            if corner not in index_of:
                points.append(vertices[corner[0] - 1])
                uvs.append(np.zeros(2) if corner[1] == 0 else texcoords[corner[1] - 1])
                corner_normals.append(zero3 if corner[2] == 0 else normals[corner[2] - 1])
                index_of[corner] = len(points) - 1
            ids.append(index_of[corner])
        for k in range(1, len(ids) - 1):
            indices.extend((ids[0], ids[k], ids[k + 1]))
    if any(np.array_equal(n, zero3) for n in corner_normals):
        accumulated = [zero3.copy() for _ in points]
        for t in range(0, len(indices), 3):
            a = points[indices[t]]
            b = points[indices[t + 1]]
            c = points[indices[t + 2]]
            face_normal = _cross(b - a, c - a)          # length = twice the area
            for j in range(3):
                accumulated[indices[t + j]] = accumulated[indices[t + j]] + face_normal
        for i, normal in enumerate(corner_normals):
            if not np.array_equal(normal, zero3):
                continue
            n = accumulated[i]
            length = float(np.sqrt((n[0] * n[0] + n[1] * n[1]) + n[2] * n[2]))
            corner_normals[i] = n / length if length > 0 else np.array((0.0, 0.0, 1.0))
    return points, uvs, corner_normals, np.array(indices, dtype=np.int32)


def _nudged(points, corner_normals):
    return np.array([p + _MODEL_NORMAL_NUDGE * n for p, n in zip(points, corner_normals)], dtype=np.float32).reshape(-1, 3)


def _obj_surface(points, corner_normals, indices, color, opacity):
    pts = np.array(points, dtype=np.float32).reshape(-1, 3)
    rgba = color_to_rgba(color, opacity) if isinstance(color, str) else np.array((*color, opacity), dtype=np.float32)
    return Surface.from_arrays(
        pts,
        _nudged(points, corner_normals),
        np.tile(rgba, (len(pts), 1)),
        (len(pts), 1),
        indices,
        shading=_MODEL_SHADING,
        depth_test=True,
    )


def _obj_textured(points, uvs, corner_normals, indices, pixels, opacity):
    pts = np.array(points, dtype=np.float32).reshape(-1, 3)
    base = Surface.from_arrays(
        pts,
        _nudged(points, corner_normals),
        np.tile(color_to_rgba(WHITE, 1.0), (len(pts), 1)),
        (len(pts), 1),
        indices,
        shading=_MODEL_SHADING,
        depth_test=True,
    )
    textured = TexturedSurface(base, pixels, opacity=opacity)
    # image rows run top-down (GL flips too): v -> 1 - v
    textured.uv = np.array([(np.float32(t[0]), np.float32(1 - t[1])) for t in uvs], dtype=np.float32).reshape(-1, 2)
    return textured


class ThreeDModel(Group):
    """A model from an OBJ file, scaled to `height` and centred."""

    def __init__(self, path, *, height=3.0, color=WHITE, opacity=1.0, **kwargs):
        path = Path(path)
        if not path.is_file():
            raise ValueError(f"model not found: {path}")
        vertices, texcoords, normals, faces, order, materials = _read_obj(path)
        if not vertices:
            raise ValueError(f"{path} has no vertices; is it a Wavefront OBJ?")
        parts = []
        for name in order:
            points, uvs, corner_normals, indices = _obj_mesh(vertices, texcoords, normals, faces[name])
            if not len(indices):
                continue
            material = materials.get(name)
            image = None if material is None else material.map_kd
            if image is not None and Path(image).is_file():
                parts.append(_obj_textured(points, uvs, corner_normals, indices, _load_pixels(image), opacity))
            else:
                kd = color if material is None or material.kd is None else material.kd
                parts.append(_obj_surface(points, corner_normals, indices, kd, opacity))
        if not parts:
            raise ValueError(f"{path} has no faces")
        super().__init__(*parts, **kwargs)
        self.set_height(height)
        self.center()
