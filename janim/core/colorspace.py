"""RGBA interpolation and the IEC sRGB transfer pair; no graphics IO."""

import math
import operator

import numpy as np


def unpremultiply_rgba(pixels):
    """Convert owned premultiplied byte rows in place, using float32 arithmetic."""
    rows = np.frombuffer(pixels, dtype=np.uint8).reshape(-1, 4)
    alpha = rows[:, 3]
    mask = (alpha != 0) & (alpha != 255)
    if np.any(mask):
        inverse = np.float32(255) / alpha[mask].astype(np.float32)
        values = rows[mask, :3].astype(np.float32) * inverse[:, None]
        rows[mask, :3] = np.rint(np.minimum(np.float32(255), values)).astype(np.uint8)
    return pixels

from ._palette import PALETTE
from ._named_colors import NAMED_COLORS


COLORMAPS = {
    "viridis": ("#440154", "#482475", "#414487", "#355f8d", "#2a788e", "#21918c", "#22a884", "#43bf71", "#7ad151", "#bddf26", "#fde725"),
    "magma": ("#000004", "#100b2d", "#2c115f", "#51127c", "#721f81", "#932b80", "#b73779", "#d8456c", "#f1605d", "#fc9366", "#fcfdbf"),
    "plasma": ("#0d0887", "#3a049a", "#5c01a6", "#7e03a8", "#9c179e", "#b52f8c", "#cc4778", "#de5f65", "#ed7953", "#f89540", "#f0f921"),
    "inferno": ("#000004", "#110a30", "#320a5e", "#57157e", "#781c6d", "#9a2865", "#bc3754", "#d84c3e", "#ed6925", "#fb9b06", "#fcffa4"),
}


def _as_rgba(color):
    if isinstance(color, str):
        code = color.strip()
        if not code.startswith("#"):
            rgb = NAMED_COLORS.get(code.lower())
            code = "#" + "".join(f"{value:02X}" for value in rgb) if rgb is not None else PALETTE.get(code, code)
            if len(code) in (3, 6) and all(c in "0123456789abcdefABCDEF" for c in code):
                code = "#" + code
        if code.startswith("#") and len(code) in (4, 5):
            code = "#" + "".join(c * 2 for c in code[1:])
        if not code.startswith("#") or len(code) not in (7, 9):
            raise ValueError(f"unknown color {color!r}; use a named color or #RRGGBB")
        try:
            values = [int(code[i:i + 2], 16) / 255 for i in range(1, len(code), 2)]
        except ValueError as error:
            raise ValueError(f"invalid hexadecimal color {color!r}") from error
    else:
        values = np.asarray(color, dtype=np.float32)
    if len(values) == 3:
        values = [*values, 1.0]
    result = np.array(values, dtype=np.float32)
    if result.shape != (4,):
        raise ValueError("a color must have three RGB or four RGBA components")
    return result


def color_to_rgba(color, opacity=1.0):
    result = _as_rgba(color)
    result[3] = np.float32(opacity)
    return result


def color_to_rgb(color):
    return _as_rgba(color)[:3].astype(np.float64)


def rgb_to_color(rgb):
    rgb = np.asarray(rgb, dtype=np.float32)
    if rgb.ndim != 1 or len(rgb) < 3:
        raise ValueError("an RGB color needs at least three components")
    return np.array([*rgb[:3], 1.0], dtype=np.float32)


def rgba_to_color(rgba):
    return rgb_to_color(rgba)


def hex_to_rgb(code):
    return color_to_rgb(code)


def color_to_hex(color):
    return rgb_to_hex(color_to_rgb(color))


def invert_color(color):
    result = _as_rgba(color)
    result[:3] = np.float32(1) - result[:3]
    return result


def rgb_to_hex(rgb):
    values = np.asarray(rgb, dtype=np.float64)[:3]
    return "#" + "".join(f"{math.floor(float(np.clip(value, 0, 1)) * 255 + 0.5 - 1e-5):02X}" for value in values)


def _check_mix(by):
    if by not in ("squares", "channels"):
        raise ValueError("by must be squares (ManimGL) or channels (ManimCE)")


def _muladd32(a, b, c):
    # A product of two f32 significands fits exactly in f64. Round at
    # each explicit muladd seam of the normalized color arithmetic.
    return (np.asarray(a, dtype=np.float64) * np.asarray(b, dtype=np.float64) + c).astype(np.float32)


def _mix_rgba(first, second, alpha, by):
    t = np.asarray(alpha, dtype=np.float32)
    if by == "channels":
        result = first + t * (second - first)
    else:
        squared = first * first
        delta = _muladd32(second, second, -squared)
        result = np.sqrt(_muladd32(t, delta, squared))
        result[..., 3] = _muladd32(t[..., 0], second[..., 3] - first[..., 3], first[..., 3])
    return np.where(t <= 0, first, np.where(t >= 1, second, result))


def interpolate_color(first, second, alpha, *, by="squares"):
    _check_mix(by)
    # Explicit fma is used for every input type, so parsing a string does
    # not select a different contraction of the inner product.
    first, second = _as_rgba(first), _as_rgba(second)
    if alpha <= 0:
        return first
    if alpha >= 1:
        return second
    return _mix_rgba(
        first,
        second,
        np.array([alpha], dtype=np.float32),
        by,
    )


def _expand_colors(colors):
    if isinstance(colors, str):
        if colors in COLORMAPS:
            return [_as_rgba(color) for color in COLORMAPS[colors]]
        return [_as_rgba(colors)]
    if isinstance(colors, np.ndarray) and colors.ndim == 1:
        return [_as_rgba(colors)]
    result = []
    for color in colors:
        result.extend(_expand_colors(color))
    return result


def color_gradient(colors, length, *, by="squares"):
    _check_mix(by)
    colors = _expand_colors(colors)
    if not colors:
        raise ValueError("color_gradient needs at least one color")
    length = operator.index(length)
    if length <= 0:
        return np.empty((0, 4), dtype=np.float32)
    if length == 1 or len(colors) == 1:
        return np.repeat(np.array(colors[:1]), length, axis=0)
    last = len(colors) - 1
    positions = np.array([k * last / (length - 1) for k in range(length)])
    indices = np.minimum(positions.astype(np.int64), last - 1)
    proportions = (positions - indices).astype(np.float32)[:, None]
    palette = np.array(colors, dtype=np.float32)
    return _mix_rgba(palette[indices], palette[indices + 1], proportions, by)


def interpolate_gradient(colors, alpha, *, by="squares"):
    _check_mix(by)
    colors = _expand_colors(colors)
    if not colors:
        raise ValueError("interpolate_gradient needs at least one color")
    if alpha <= 0 or len(colors) == 1:
        return colors[0].copy()
    if alpha >= 1:
        return colors[-1].copy()
    position = float(alpha) * (len(colors) - 1)
    index = int(position)
    return interpolate_color(colors[index], colors[index + 1], np.float32(position - index), by=by)


def colormap_colors(name, n=None):
    if name not in COLORMAPS:
        raise ValueError(f"unknown color map {name!r}; available: {', '.join(COLORMAPS)}")
    colors = np.array([color_to_rgba(color) for color in COLORMAPS[name]])
    return colors if n is None else color_gradient(colors, n)


def srgb_to_linear(value):
    value = float(value)
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055)**2.4


def linear_to_srgb(value):
    value = float(value)
    return 12.92 * value if value <= 0.0031308 else 1.055 * value**(1 / 2.4) - 0.055


def decode_premult_srgb(rgba):
    alpha = float(rgba[3])
    if alpha <= 0:
        return np.zeros(4, dtype=np.float32)
    return np.array(
        [*(srgb_to_linear(min(1.0, max(0.0, float(x) / alpha))) * alpha for x in rgba[:3]), alpha],
        dtype=np.float32,
    )
