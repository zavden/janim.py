"""Janim's lazy public entry points; importing the package opens no driver."""

__version__ = "1.0.0"
__all__ = [
    "render_solid_frame",
    "render_two_band_frame",
    "renderer_info",
    "gpu_info",
    "driver_header",
    "save_rgb_png",
    "sha256_rgb",
    "VideoWriter",
]

_EXPORTS = {
    "render_solid_frame": "janim.backend",
    "render_two_band_frame": "janim.backend",
    "renderer_info": "janim.backend",
    "gpu_info": "janim.backend",
    "driver_header": "janim.backend",
    "save_rgb_png": "janim.png",
    "sha256_rgb": "janim.png",
    "VideoWriter": "janim.video",
}

from ._exports_basics import BASIC_EXPORTS as _BASIC_EXPORTS

_EXPORTS.update(_BASIC_EXPORTS)
__all__.extend(_BASIC_EXPORTS)

_RENDER_EXPORTS = {
    "Camera": "janim.core.camera",
    "camera_uniforms": "janim.core.camera",
    "get_view_matrix": "janim.core.camera",
    "focal_distance": "janim.core.camera",
    "render_frame": "janim.backend",
    "render_mobjects": "janim.backend",
    "setup_render_vm": "janim.backend",
    "save_png": "janim.png",
    "strict_gl": "janim.backend.determinism",
    "set_strict_gl": "janim.backend.determinism",
    "strict_gl_env": "janim.backend.determinism",
    "strict_gl_cmd": "janim.backend.determinism",
    "strict_gl_pinned": "janim.backend.determinism",
}
_EXPORTS.update(_RENDER_EXPORTS)
__all__.extend(_RENDER_EXPORTS)

from ._exports_animation import ANIMATION_EXPORTS as _ANIMATION_EXPORTS

_EXPORTS.update(_ANIMATION_EXPORTS)
__all__.extend(name for name in _ANIMATION_EXPORTS if name not in __all__)

from ._exports_geometry import GEOMETRY_EXPORTS as _GEOMETRY_EXPORTS

_EXPORTS.update(_GEOMETRY_EXPORTS)
__all__.extend(name for name in _GEOMETRY_EXPORTS if name not in __all__)

from ._exports_text import TEXT_EXPORTS as _TEXT_EXPORTS

_EXPORTS.update(_TEXT_EXPORTS)
__all__.extend(name for name in _TEXT_EXPORTS if name not in __all__)

from ._exports_effects import EFFECT_EXPORTS as _EFFECT_EXPORTS

_EXPORTS.update(_EFFECT_EXPORTS)
__all__.extend(name for name in _EFFECT_EXPORTS if name not in __all__)

from ._exports_3d import THREE_D_EXPORTS as _THREE_D_EXPORTS

_EXPORTS.update(_THREE_D_EXPORTS)
__all__.extend(name for name in _THREE_D_EXPORTS if name not in __all__)


def __dir__():
    return sorted(dict.fromkeys((*globals(), *__all__)))


def __getattr__(name):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module 'janim' has no attribute {name!r}")
    from importlib import import_module

    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value
