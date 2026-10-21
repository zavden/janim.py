"""Self-validating fill-gradient data."""

from dataclasses import dataclass

import numpy as np


RAMP_RESOLUTION = 1024


@dataclass(frozen=True, eq=False)
class FillGradient:
    kind: str
    uv: np.ndarray
    focus: tuple
    spread: int
    ramp: np.ndarray
    baked_rgba: np.ndarray

    def __post_init__(self):
        if self.kind not in ("linear", "radial") or self.spread not in (0, 1, 2):
            raise ValueError("a fill gradient needs linear/radial and spread 0, 1 or 2")
        for name, columns in (("uv", 2), ("ramp", 4), ("baked_rgba", 4)):
            array = np.array(getattr(self, name), dtype=np.float32, copy=True).reshape(-1, columns)
            object.__setattr__(self, name, array)
        if len(self.ramp) != RAMP_RESOLUTION:
            raise ValueError(f"a gradient ramp needs {RAMP_RESOLUTION} RGBA texels")
        focus = np.asarray(self.focus, dtype=np.float32)
        if focus.shape != (2,):
            raise ValueError("a gradient focus needs two coordinates")
        object.__setattr__(self, "focus", tuple(focus))


def gradient_alpha_scale(gradient, rows):
    baked = gradient.baked_rgba
    if baked.shape != rows.shape or not np.array_equal(baked[:, :3], rows[:, :3]):
        return None
    nonzero = baked[:, 3] != 0
    if np.any(rows[~nonzero, 3] != 0):
        return None
    if not np.any(nonzero):
        return np.float32(1)
    scales = rows[nonzero, 3] / baked[nonzero, 3]
    # The sentinel remains negative until the first nonnegative scale.
    scale = np.float32(-1)
    for value in scales:
        if scale < 0:
            scale = value
        elif abs(value - scale) > np.float32(1e-3):
            return None
    return np.float32(1) if scale < 0 else np.clip(scale, np.float32(0), np.float32(1))


def active_fill_gradient(mobject):
    gradient = mobject.fill_gradient
    if gradient is None or len(gradient.uv) != len(mobject.points):
        return None
    return None if gradient_alpha_scale(gradient, mobject.fill_rgba) is None else gradient


def fill_gradient_opacity(mobject):
    gradient = mobject.fill_gradient
    scale = None if gradient is None else gradient_alpha_scale(gradient, mobject.fill_rgba)
    return np.float32(1) if scale is None else scale
