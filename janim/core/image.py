"""Raster mobjects: RGBA8, top row first, with immutable shared pixels."""

import json
import operator
from pathlib import Path
import struct
import subprocess
import zlib

import numpy as np

from .algebra import apply_matrix_rows, norm, rotation_matrix
from .mobject import Mobject
from .rates import straight_path
from .transforms import point3


def _unfilter(data, position, width, height, bits_per_pixel):
    stride = (width * bits_per_pixel + 7) // 8
    byte_width = max(1, (bits_per_pixel + 7) // 8)
    rows = np.empty((height, stride), dtype=np.uint8)
    previous = np.zeros(stride, dtype=np.uint8)
    for index in range(height):
        if position + stride + 1 > len(data):
            raise ValueError("truncated PNG scanline")
        kind = data[position]
        row = np.frombuffer(data, dtype=np.uint8, count=stride, offset=position + 1).copy()
        position += stride + 1
        if kind == 1:
            for offset in range(byte_width):
                row[offset::byte_width] = np.cumsum(row[offset::byte_width], dtype=np.uint64).astype(np.uint8)
        elif kind == 2:
            row = row + previous
        elif kind in (3, 4):
            for column in range(stride):
                left = int(row[column - byte_width]) if column >= byte_width else 0
                above = int(previous[column])
                upper_left = int(previous[column - byte_width]) if column >= byte_width else 0
                if kind == 3:
                    predictor = (left + above) // 2
                else:
                    estimate = left + above - upper_left
                    distances = abs(estimate - left), abs(estimate - above), abs(estimate - upper_left)
                    predictor = (left, above, upper_left)[distances.index(min(distances))]
                row[column] = (int(row[column]) + predictor) & 255
        elif kind != 0:
            raise ValueError(f"unknown PNG filter {kind}")
        rows[index] = row
        previous = row
    return rows, position


def read_png(path):
    """Decode PNG filters, palettes, transparency and Adam7 without Pillow."""
    source = Path(path).read_bytes()
    if not source.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"not a PNG file: {path}")
    position = 8
    payloads = []
    palette = transparency = None
    header = None
    while position + 12 <= len(source):
        length = struct.unpack_from(">I", source, position)[0]
        kind = source[position + 4:position + 8]
        payload = source[position + 8:position + 8 + length]
        if position + length + 12 > len(source):
            raise ValueError("truncated PNG chunk")
        crc = struct.unpack_from(">I", source, position + 8 + length)[0]
        if zlib.crc32(payload, zlib.crc32(kind)) != crc:
            raise ValueError(f"PNG checksum mismatch in {kind!r}")
        position += length + 12
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", payload)
        elif kind == b"PLTE":
            palette = np.frombuffer(payload, dtype=np.uint8).reshape(-1, 3)
        elif kind == b"tRNS":
            transparency = payload
        elif kind == b"IDAT":
            payloads.append(payload)
        elif kind == b"IEND":
            break
    if header is None or not payloads:
        raise ValueError("PNG has no header or image data")
    width, height, depth, color_type, compression, filtering, interlace = header
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type)
    valid_depths = (1, 2, 4, 8, 16) if color_type == 0 else (1, 2, 4, 8) if color_type == 3 else (8, 16)
    if not width or not height or channels is None or depth not in valid_depths or compression or filtering or interlace not in (0, 1):
        raise ValueError("unsupported or invalid PNG header")
    raw = zlib.decompress(b"".join(payloads))
    passes = ((0, 0, 1, 1),) if interlace == 0 else (
        (0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4),
        (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2),
    )
    pixels = np.empty((height, width, 4), dtype=np.uint8)
    position = 0
    for x0, y0, dx, dy in passes:
        pass_width = max(0, (width - x0 + dx - 1) // dx)
        pass_height = max(0, (height - y0 + dy - 1) // dy)
        if not pass_width or not pass_height:
            continue
        rows, position = _unfilter(raw, position, pass_width, pass_height, depth * channels)
        if depth == 16:
            values = rows.copy().view(">u2").reshape(pass_height, pass_width, channels).astype(np.uint16)
            scaled = np.rint(values.astype(np.float64) / 257).astype(np.uint8)
        elif depth == 8:
            values = rows.reshape(pass_height, pass_width, channels)
            scaled = values
        else:
            bits = np.unpackbits(rows, axis=1)[:, :pass_width * depth]
            weights = 1 << np.arange(depth - 1, -1, -1)
            values = (bits.reshape(pass_height, pass_width, depth) * weights).sum(axis=2)[..., None]
            scaled = (values * (255 // ((1 << depth) - 1))).astype(np.uint8)
        result = np.empty((pass_height, pass_width, 4), dtype=np.uint8)
        result[..., 3] = 255
        if color_type == 3:
            indices = values[..., 0]
            if palette is None or np.any(indices >= len(palette)):
                raise ValueError("PNG palette index is out of range")
            result[..., :3] = palette[indices]
            if transparency is not None:
                alpha = np.full(len(palette), 255, dtype=np.uint8)
                alpha[:len(transparency)] = np.frombuffer(transparency, dtype=np.uint8)
                result[..., 3] = alpha[indices]
        elif color_type in (0, 4):
            result[..., :3] = scaled[..., :1]
            if color_type == 4:
                result[..., 3] = scaled[..., 1]
            elif transparency is not None:
                result[..., 3][values[..., 0] == struct.unpack(">H", transparency)[0]] = 0
        else:
            result[..., :3] = scaled[..., :3]
            if color_type == 6:
                result[..., 3] = scaled[..., 3]
            elif transparency is not None:
                transparent = np.array(struct.unpack(">HHH", transparency))
                result[..., 3][np.all(values == transparent, axis=2)] = 0
        pixels[y0::dy, x0::dx] = result
    if position != len(raw):
        raise ValueError("PNG contains trailing scanline bytes")
    return pixels


def _load_pixels(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"image not found: {path}")
    if path.suffix.lower() == ".png":
        return read_png(path)
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", str(
                path,
            )],
            check=True,
            capture_output=True,
        )
        info = json.loads(probe.stdout)["streams"][0]
        decoded = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(
                path,
            ), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgba", "pipe:1"],
            check=True,
            capture_output=True,
        )
        return np.frombuffer(decoded.stdout, dtype=np.uint8).reshape(info["height"], info["width"], 4).copy()
    except (subprocess.CalledProcessError, ValueError, KeyError, IndexError) as error:
        raise ValueError(f"cannot decode image {path}: {error}") from error


class ImageMobject(Mobject):
    render_kind = "image"
    is_interpolable = True
    _shared_array_names = ("pixels",)
    _transform_bbox = False

    def __init__(self, source, height=4.0, opacity=1.0, **kwargs):
        pixels = _load_pixels(source) if isinstance(source, (str, Path)) else source
        super().__init__(**kwargs)
        self.set_pixels(pixels)
        self.opacity = float(opacity)
        width = float(height) * self.pixels.shape[1] / self.pixels.shape[0]
        half_width, half_height = width / 2, float(height) / 2
        self.set_points((
            (-half_width, half_height, 0),
            (-half_width, -half_height, 0),
            (half_width, half_height, 0),
            (half_width, -half_height, 0),
        ))

    def set_pixels(self, pixels):
        pixels = np.asarray(pixels)
        if pixels.dtype != np.uint8 or pixels.ndim != 3 or pixels.shape[2] not in (3, 4) or min(
            pixels.shape[:2],
        ) <= 0:
            raise ValueError("pixels must be a nonempty (height, width, 3 or 4) uint8 array")
        if pixels.shape[2] == 3:
            alpha = np.full((*pixels.shape[:2], 1), 255, dtype=np.uint8)
            pixels = np.concatenate((pixels, alpha), axis=2)
        self.pixels = np.ascontiguousarray(pixels)
        return self

    def pixel_size(self):
        return self.pixels.shape[1], self.pixels.shape[0]

    def get_width(self):
        return norm(self.points[2] - self.points[0])

    def get_height(self):
        return norm(self.points[1] - self.points[0])

    def _attribute_or(name, getter):
        def get(self):
            override = self.__dict__.get("_attribute_" + name)
            return getter(self) if override is None else override

        def put(self, value):
            self.__dict__["_attribute_" + name] = value

        return property(get, put)

    width = _attribute_or("width", get_width)
    height = _attribute_or("height", get_height)
    del _attribute_or

    def set_opacity(self, opacity, recurse=True):
        self.opacity = float(np.clip(opacity, 0, 1))
        return self

    def get_opacity(self):
        return self.opacity

    def _image_pivot(self, about_point, about_edge):
        return self._pivot(
            about_point,
            (0, 0, 0) if about_edge is None else about_edge,
        ).astype(np.float64)

    def scale(self, factor, about_point=None, about_edge=None, min_scale_factor=1e-8):
        center = self._image_pivot(about_point, about_edge)
        factor = float(np.maximum(float(factor), float(min_scale_factor)))
        self.points[:] = center + factor * (self.points.astype(np.float64) - center)
        return self.note_changed_data()

    def stretch(self, factor, dim, about_point=None, about_edge=None):
        dim = operator.index(dim)
        if dim not in (0, 1, 2):
            raise ValueError(f"dimension {dim} does not exist: 0=x, 1=y, 2=z")
        center = self._image_pivot(about_point, about_edge)
        scale = np.ones(3, dtype=np.float64)
        scale[dim] = float(factor)
        self.points[:] = center + scale * (self.points.astype(np.float64) - center)
        return self.note_changed_data()

    def rotate(self, angle, axis=(0, 0, 1), about_point=None, about_edge=None):
        center = self._image_pivot(about_point, about_edge)
        self.points[:] = apply_matrix_rows(
            self.points.astype(np.float64) - center,
            rotation_matrix(angle, axis),
        ) + center
        return self.note_changed_data()

    def set_width(self, width, stretch=False, **kwargs):
        if stretch:
            return self.rescale_to_fit(width, 0, stretch=True, **kwargs)
        return self.scale(float(width) / max(float(self.get_width()), 1e-12), **kwargs)

    def set_height(self, height, stretch=False, **kwargs):
        if stretch:
            return self.rescale_to_fit(height, 1, stretch=True, **kwargs)
        return self.scale(float(height) / max(float(self.get_height()), 1e-12), **kwargs)

    def align_points(self, other):
        if not isinstance(other, ImageMobject):
            raise TypeError("an image can align only with another image")
        return self

    def become(self, other, match_updaters=False):
        self.align_points(other)
        self.pixels = other.pixels
        self.points[:] = other.points
        self.opacity = other.opacity
        if match_updaters:
            self.match_updaters(other)
        return self.note_changed_data()

    def interpolate(self, first, second, alpha, path_func=straight_path):
        if path_func is straight_path:
            self.points[:] = first.points + np.float32(alpha) * (second.points - first.points)
        else:
            self.points[:] = path_func(first.points, second.points, alpha)
        self.opacity = first.opacity + float(alpha) * (second.opacity - first.opacity)
        self.pixels = first.pixels if alpha < 0.5 else second.pixels
        return self.note_changed_data()


def pixel_size(image):
    return image.pixel_size()


class TexturedSurface(Mobject):
    """A Surface whose vertex colour is replaced by a texture sampled at (u, v).

    The uv grid follows the mesh order (u-outer, v-inner): u from 0 to 1 and
    v from 1 down to 0, so the image's top row lands at the first v row.
    """

    render_kind = "textured_surface"
    is_interpolable = True
    _shared_array_names = ("pixels",)
    _transform_bbox = False

    def __init__(self, surface, image, *, opacity=1.0, **kwargs):
        super().__init__(**kwargs)
        self.set_pixels(_load_pixels(image) if isinstance(image, (str, Path)) else image)
        nu, nv = surface.resolution
        uv = np.empty((nu * nv, 2), dtype=np.float32)
        k = 0
        for iu in range(nu):
            for iv in range(nv):
                uv[k] = (np.float32(iu / max(nu - 1, 1)), np.float32(1 - iv / max(nv - 1, 1)))
                k += 1
        self.uv = uv
        self.resolution = (nu, nv)
        self.indices = surface.indices.copy()
        self.points = surface.points.copy()
        self.d_normal_points = surface.d_normal_points.copy()
        self.opacity = float(opacity)
        self.uniforms["shading"] = surface.uniforms["shading"].copy()
        self.uniforms["is_fixed_in_frame"] = surface.uniforms["is_fixed_in_frame"]
        self.depth_test = surface.depth_test
        self.note_changed_data()

    set_pixels = ImageMobject.set_pixels
    pixel_size = ImageMobject.pixel_size

    def get_bounding_box(self):
        # measured on every query, as a Surface's
        self._needs_new_bounding_box = True
        return super().get_bounding_box()

    def _point_arrays(self):
        return (self.points, self.d_normal_points)

    def set_opacity(self, opacity, recurse=True):
        self.opacity = float(np.clip(opacity, 0, 1))
        return self

    def get_opacity(self):
        return self.opacity

    def set_shading(self, reflectiveness=None, gloss=None, shadow=None, recurse=True):
        current = self.uniforms["shading"]
        values = [current[0], current[1], current[2]]
        for index, value in enumerate((reflectiveness, gloss, shadow)):
            if value is not None:
                values[index] = value
        self.uniforms["shading"] = np.array(values, dtype=np.float32)
        return self

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

    def align_data(self, other, **kwargs):
        if not isinstance(other, TexturedSurface) or len(other.points) != len(self.points):
            raise ValueError("cannot interpolate TexturedSurfaces of different resolutions")
        return self

    def interpolate(self, first, second, alpha, **kwargs):
        if len(first.points) != len(second.points):
            raise ValueError(
                f"cannot interpolate TexturedSurfaces of different resolutions "
                f"({first.resolution} vs {second.resolution})",
            )
        t = np.float32(alpha)
        self.points[:] = first.points + t * (second.points - first.points)
        self.d_normal_points[:] = first.d_normal_points + t * (second.d_normal_points - first.d_normal_points)
        self.opacity = first.opacity + float(alpha) * (second.opacity - first.opacity)
        self.pixels = first.pixels if alpha < 0.5 else second.pixels
        return self.note_changed_data()

    def become(self, other, match_updaters=False):
        self.pixels = other.pixels
        self.points[:] = other.points
        self.d_normal_points[:] = other.d_normal_points
        self.opacity = other.opacity
        if match_updaters:
            self.match_updaters(other)
        return self.note_changed_data()
