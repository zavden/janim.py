"""Mutable layer effects and deterministic noise."""

from dataclasses import dataclass, field, fields
import operator

import numpy as np


class _Effect:
    def __post_init__(self):
        for item in fields(self):
            value = getattr(self, item.name)
            if item.type is float:
                setattr(self, item.name, float(value))
            elif item.type is int:
                setattr(self, item.name, operator.index(value))
            elif item.type is bool:
                setattr(self, item.name, bool(value))
        if hasattr(self, "focus") and self.focus is not None:
            self.focus = float(self.focus)
        if hasattr(self, "center_point"):
            self.center_point = tuple(map(float, self.center_point))
            if len(self.center_point) != 2:
                raise ValueError("center_point requires two components")


@dataclass
class Blur(_Effect):
    """Separable Gaussian; sigma is in scene units unless in_pixels is true."""

    sigma: float
    in_pixels: bool = field(default=False, kw_only=True)


@dataclass
class BoxBlur(_Effect):
    radius: float


@dataclass
class DirectionalBlur(_Effect):
    sigma: float
    angle: float


@dataclass
class RadialBlur(_Effect):
    strength: float
    center_point: tuple = field(default=(0.0, 0.0), kw_only=True)


@dataclass
class Dof(_Effect):
    """Layer depth of field, resolved against the layer's camera each frame."""

    focus: object = None
    aperture: float = field(default=0.4, kw_only=True)
    max_sigma: float = field(default=4.0, kw_only=True)
    current_sigma: float = field(default=0.0, init=False)


@dataclass(kw_only=True)
class Bloom(_Effect):
    threshold: float = 0.6
    intensity: float = 1.0
    sigma: float = 0.15


@dataclass(kw_only=True)
class Glitch(_Effect):
    intensity: float = 0.5
    seed: int = 1
    rate: int = 3
    rgb_shift: float = 0.05
    slices: int = 12
    block: float = 0.3
    current_frame: int = field(default=0, init=False)


@dataclass(kw_only=True)
class CRT(_Effect):
    intensity: float = 1.0
    scanlines: float = 240.0
    scan_depth: float = 0.35
    mask: float = 0.3
    curvature: float = 0.15
    vignette: float = 0.35
    roll: float = 0.0


@dataclass(kw_only=True)
class VHS(_Effect):
    intensity: float = 0.5
    seed: int = 1
    rate: int = 2
    chroma_bleed: float = 0.15
    jitter: float = 0.04
    noise: float = 0.12
    head_switch: float = 0.08
    current_frame: int = field(default=0, init=False)


@dataclass(kw_only=True)
class ColorAdjust(_Effect):
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0
    hue: float = 0.0


@dataclass
class Pixelate(_Effect):
    size: float = 0.2


@dataclass(kw_only=True)
class Vignette(_Effect):
    amount: float = 0.5
    radius: float = 0.5
    feather: float = 0.4


@dataclass(kw_only=True)
class Grain(_Effect):
    amount: float = 0.15
    seed: int = 1
    rate: int = 1
    levels: int = 8
    current_frame: int = field(default=0, init=False)


@dataclass
class ChromaticAberration(_Effect):
    amount: float = 0.1


@dataclass
class Sharpen(_Effect):
    amount: float = 0.6
    sigma: float = field(default=0.05, kw_only=True)


@dataclass(kw_only=True)
class Wave(_Effect):
    amplitude: float = 0.1
    wavelength: float = 1.5
    angle: float = 0.0
    phase: float = 0.0


@dataclass(kw_only=True)
class EdgeDetect(_Effect):
    amount: float = 1.0
    color: object = None
    thickness: float = 1.0


def _hash32(value):
    value = int(value) & 0xffffffff
    value ^= value >> 16
    value = value * 0x7feb352d & 0xffffffff
    value ^= value >> 15
    value = value * 0x846ca68b & 0xffffffff
    return value ^ (value >> 16)


def _noise_hash(x, y, frame, seed):
    value = _hash32((int(seed) & 0xffffffff) ^ 0x9e3779b9)
    for component in (x, y, frame):
        value = _hash32(int(component) + value)
    return np.float32(value >> 8) * np.float32(2.0 ** -24)


def _noise_steps(x, y, frame, seed, levels):
    count = np.float32(max(operator.index(levels), 1))
    return np.floor(_noise_hash(x, y, frame, seed) * count) / count


def _frame_step(frame, every):
    frame, every = operator.index(frame), max(operator.index(every), 1)
    quotient = abs(frame) // every
    return -quotient if frame < 0 else quotient


def _fnv1a(name):
    value = 0x811c9dc5
    for byte in name.encode("utf-8"):
        value = ((value ^ byte) * 0x01000193) & 0xffffffff
    return value


def _noise_seed(effect, seed):
    value = _hash32(_fnv1a(type(effect).__name__) ^ ((operator.index(seed) * 0x9e3779b9) & 0xffffffff))
    return value - 0x100000000 if value >= 0x80000000 else value


def tick_effects(value, frame):
    from .compositor_types import Composition, Layer

    if isinstance(value, Composition):
        for layer in value.layers:
            tick_effects(layer, frame)
    elif isinstance(value, Layer):
        if isinstance(value.content, Composition):
            tick_effects(value.content, frame)
        for effect in value.effects:
            tick_effects(effect, frame)
    elif hasattr(value, "current_frame"):
        try:
            value.current_frame = operator.index(frame)
        except (AttributeError, TypeError) as error:
            raise TypeError(f"{type(value).__name__} declares current_frame but is not mutable") from error
    return value
