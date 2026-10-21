"""Recorded effect passes."""

from functools import singledispatch
import math
import warnings

import numpy as np

from janim.constants import FRAME_HEIGHT, FRAME_WIDTH
from janim.core.colorspace import color_to_rgba, srgb_to_linear
from janim.core.compositor_types import gaussian_weights
from janim.core.effects_types import (
    Bloom,
    Blur,
    BoxBlur,
    ChromaticAberration,
    ColorAdjust,
    CRT,
    DirectionalBlur,
    Dof,
    EdgeDetect,
    Glitch,
    Grain,
    Pixelate,
    RadialBlur,
    Sharpen,
    VHS,
    Vignette,
    Wave,
    _noise_seed,
)
from .uniforms import quad_params


def _clip(value):
    return min(max(value, 0), 1)


def _one(cg, entry, source, *, f0=(), f1=(), i0=(), weights=None):
    return cg._quad(
        entry,
        cg._scratch(source),
        source,
        params=quad_params(f0=f0, f1=f1, i0=i0, w=() if weights is None else weights),
    )


@singledispatch
def apply_effect(effect, compositor, source):
    """Register a custom type with @apply_effect.register(MyEffect).

    A handler receives (effect, compositor, source_slot), writes a scratch
    slot and returns its index. Returning source skips the effect exactly.
    """
    raise TypeError(f"no layer effect handler for {type(effect).__name__}")


@apply_effect.register(Blur)
def _blur(effect, cg, source):
    sigma = effect.sigma if effect.in_pixels else effect.sigma * cg.ppu
    if sigma < 0.3:
        return source
    return cg._blur_hv(source, *gaussian_weights(sigma))


@apply_effect.register(Dof)
def _dof(effect, cg, source):
    return apply_effect(Blur(effect.current_sigma), cg, source) if effect.current_sigma > 1e-6 else source


@apply_effect.register(BoxBlur)
def _box(effect, cg, source):
    requested = max(round(effect.radius * cg.ppu), 1)
    radius = min(requested, 63)
    if requested > 63:
        warnings.warn(
            f"box-kernel-radius-limit: radius {effect.radius} units is {requested} px; weights[64] caps it at 63",
            RuntimeWarning,
            stacklevel=2,
        )
    weights = np.full(radius + 1, np.float32(1 / (2 * radius + 1)), dtype=np.float32)
    return cg._blur_hv(source, radius, weights)


@apply_effect.register(DirectionalBlur)
def _directional(effect, cg, source):
    sigma = effect.sigma * cg.ppu
    if sigma < 0.3:
        return source
    radius, weights = gaussian_weights(sigma)
    return _one(
        cg,
        "blur",
        source,
        f0=(math.cos(effect.angle) / cg.width, math.sin(effect.angle) / cg.height),
        i0=(radius,),
        weights=weights,
    )


@apply_effect.register(RadialBlur)
def _radial(effect, cg, source):
    return _one(
        cg,
        "zoom",
        source,
        f0=(0.5 + effect.center_point[0] / FRAME_WIDTH, 0.5 + effect.center_point[1] / FRAME_HEIGHT, effect.strength),
    )


@apply_effect.register(Bloom)
def _bloom(effect, cg, source):
    sigma = max(effect.sigma * cg.ppu, 0.5)
    halo = 4
    with cg._keep(source, 4, 5):
        for index, amount in enumerate((sigma, 2 * sigma, 4 * sigma)):
            bright = _one(cg, "bright", source, f0=(effect.threshold,))
            cg._blur_hv(bright, *gaussian_weights(amount))
            other = 5 if halo == 4 else 4
            if index == 0:
                cg._quad("saturate", other, bright)
            else:
                cg._quad("add2", other, halo, bright, quad_params(f0=(1,)))
            halo = other
    with cg._keep(halo):
        return cg._quad("add2", cg._scratch(source), source, halo, quad_params(f0=(effect.intensity,)))


@apply_effect.register(Glitch)
def _glitch(effect, cg, source):
    if effect.intensity <= 0:
        return source
    return _one(
        cg,
        "glitch",
        source,
        i0=(effect.current_frame, _noise_seed(effect, effect.seed), max(effect.rate, 1), max(effect.slices, 1)),
        f0=(
            _clip(effect.intensity),
            effect.rgb_shift * cg.ppu / cg.width,
            max(effect.block * cg.ppu / cg.width, 1e-4),
            max(effect.block * cg.ppu / cg.height, 1e-4),
        ),
    )


@apply_effect.register(CRT)
def _crt(effect, cg, source):
    if effect.intensity <= 0:
        return source
    return _one(
        cg,
        "crt",
        source,
        f0=(_clip(effect.intensity), max(effect.scanlines, 0), _clip(effect.scan_depth), _clip(effect.mask)),
        f1=(effect.curvature, _clip(effect.vignette), effect.roll, cg.height),
    )


@apply_effect.register(VHS)
def _vhs(effect, cg, source):
    if effect.intensity <= 0:
        return source
    return _one(
        cg,
        "vhs",
        source,
        i0=(effect.current_frame, _noise_seed(effect, effect.seed), max(effect.rate, 1)),
        f0=(_clip(effect.intensity), effect.jitter * cg.ppu / cg.width, effect.chroma_bleed * cg.ppu / cg.width, _clip(effect.noise)),
        f1=(_clip(effect.head_switch),),
    )


@apply_effect.register(ColorAdjust)
def _color(effect, cg, source):
    if effect.brightness == effect.contrast == effect.saturation == 1 and effect.hue == 0:
        return source
    return _one(cg, "color", source, f0=(effect.brightness, effect.contrast, effect.saturation, effect.hue))


@apply_effect.register(Pixelate)
def _pixelate(effect, cg, source):
    pixels = effect.size * cg.ppu
    if pixels < 1:
        return source
    return _one(cg, "pixelate", source, f0=(pixels / cg.width, pixels / cg.height))


@apply_effect.register(Vignette)
def _vignette(effect, cg, source):
    if effect.amount <= 0:
        return source
    return _one(cg, "vignette", source, f0=(_clip(effect.amount), effect.radius, effect.feather))


@apply_effect.register(Grain)
def _grain(effect, cg, source):
    if effect.amount <= 0:
        return source
    return _one(
        cg,
        "grain",
        source,
        i0=(effect.current_frame, _noise_seed(effect, effect.seed), max(effect.rate, 1), max(effect.levels, 1)),
        f0=(_clip(effect.amount),),
    )


@apply_effect.register(ChromaticAberration)
def _chroma(effect, cg, source):
    if effect.amount == 0:
        return source
    pixels = effect.amount * cg.ppu
    return _one(cg, "chroma", source, f0=(2 * pixels / cg.width, 2 * pixels / cg.height))


@apply_effect.register(Sharpen)
def _sharpen(effect, cg, source):
    sigma = effect.sigma * cg.ppu
    if effect.amount <= 0 or sigma < 0.3:
        return source
    blurred = cg._blur_to(source, *gaussian_weights(sigma))
    with cg._keep(blurred):
        return cg._quad("sharpen", cg._scratch(source), source, blurred, quad_params(f0=(effect.amount,)))


@apply_effect.register(Wave)
def _wave(effect, cg, source):
    if effect.amplitude == 0:
        return source
    amplitude = effect.amplitude * cg.ppu
    wavelength = max(effect.wavelength * cg.ppu, 1.0)
    return _one(
        cg,
        "wave",
        source,
        f0=(
            -math.sin(effect.angle) * amplitude / cg.width,
            math.cos(effect.angle) * amplitude / cg.height,
            math.tau / wavelength,
            effect.phase % math.tau,
        ),
        f1=(math.cos(effect.angle) * cg.width, math.sin(effect.angle) * cg.height),
    )


@apply_effect.register(EdgeDetect)
def _edge(effect, cg, source):
    if effect.amount <= 0:
        return source
    color = (0, 0, 0) if effect.color is None else tuple(srgb_to_linear(float(channel)) for channel in color_to_rgba(effect.color)[:3])
    return _one(
        cg,
        "edge",
        source,
        f0=(effect.thickness / cg.width, effect.thickness / cg.height, effect.amount),
        f1=color,
        i0=(effect.color is not None,),
    )
