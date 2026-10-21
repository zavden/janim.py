"""Deterministic RGB8 PNG files using only the standard library.

Raw pixels are tightly packed RGB24 scanlines, top to bottom. PNG bytes use
filter None and zlib level 6.
"""

import hashlib
import operator
from pathlib import Path
import struct
import zlib


def dimensions(width, height):
    values = []
    for value in (width, height):
        if isinstance(value, bool):
            raise ValueError("image dimensions must be positive integers")
        try:
            integer = operator.index(value)
        except TypeError as error:
            raise ValueError("image dimensions must be positive integers") from error
        if not 0 < integer <= 0x7FFFFFFF:
            raise ValueError("image dimensions must be in 1..2147483647")
        values.append(integer)
    return tuple(values)


def rgb_view(width, height, pixels):
    """Validate and borrow a contiguous buffer; the caller owns its lifetime."""
    width, height = dimensions(width, height)
    try:
        view = memoryview(pixels).cast("B")
    except (TypeError, ValueError) as error:
        raise ValueError("pixels must be a contiguous RGB24 buffer") from error
    expected = width * height * 3
    if view.nbytes != expected:
        raise ValueError(f"RGB24 buffer has {view.nbytes} bytes; expected {expected}")
    return view


def rgb_bytes(width, height, pixels):
    """Return an owned RGB24 copy for callers that need a snapshot."""
    return bytes(rgb_view(width, height, pixels))


def sha256_rgb(pixels):
    """Return SHA-256 over every byte of a contiguous RGB24 buffer."""
    return hashlib.sha256(memoryview(pixels).cast("B")).hexdigest()


def _chunk(kind, payload):
    checksum = zlib.crc32(payload, zlib.crc32(kind))
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def save_rgb_png(path, width, height, pixels):
    """Write an RGB8 PNG with fixed filtering and compression parameters."""
    width, height = dimensions(width, height)
    pixels = rgb_bytes(width, height, pixels)
    stride = width * 3
    scanlines = b"".join(
        b"\0" + pixels[start:start + stride]
        for start in range(0, len(pixels), stride)
    )
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    content = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(scanlines, level=6))
        + _chunk(b"IEND", b"")
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def save_png(path, pixels):
    """Save RGB bytes, or a premultiplied RGBA render as a straight-alpha PNG."""
    shape = getattr(pixels, "shape", ())
    if len(shape) != 3 or shape[2] not in (3, 4) or str(pixels.dtype) != "uint8":
        raise ValueError("save_png expects a (height, width, 3 or 4) uint8 image")
    if shape[2] == 4:
        from janim.core.colorspace import unpremultiply_rgba

        width, height = dimensions(shape[1], shape[0])
        data = bytearray(pixels.tobytes())
        unpremultiply_rgba(data)
        stride = width * 4
        scanlines = b"".join(b"\0" + data[start:start + stride] for start in range(0, len(data), stride))
        header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
        content = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(scanlines, level=6)) + _chunk(b"IEND", b"")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path
    return save_rgb_png(path, shape[1], shape[0], pixels)
