"""Layer and mask data; the compositor is loaded only when rendering."""

import math
import warnings

import numpy as np

from .mobject import Mobject
from ._reductions import julia_sum, sum_left_to_right
from .effects_types import Bloom, Blur, BoxBlur, DirectionalBlur, Dof, RadialBlur


BLEND_MODES = {"normal": 0, "add": 1, "multiply": 2, "screen": 3, "overlay": 4}
MATTE_MODES = ("alpha", "luma", "alpha_inv", "luma_inv")


class Composition:
    def __init__(self, *layers, background=(0, 0, 0, 0)):
        if any(not isinstance(layer, Layer) for layer in layers):
            raise TypeError("a Composition requires Layer objects")
        self.layers = list(layers)
        self.background = np.asarray(background, dtype=np.float32)
        if self.background.shape != (4,):
            raise ValueError("composition background must have four RGBA channels")

    def mobjects(self):
        result = [mob for members in self.content_lists() for mob in members]
        known = dict.fromkeys(result)
        for extra in self._view_extras():
            if extra is not None and extra not in known:
                known[extra] = None
                result.append(extra)
        return result

    def _view_extras(self):
        for layer in self.layers:
            if isinstance(layer.content, Composition):
                yield from layer.content._view_extras()
            yield layer.camera
            yield layer.window

    def content_lists(self):
        """Yield the live lists that scene removal and replacement may edit."""
        for layer in self.layers:
            if isinstance(layer.content, Composition):
                yield from layer.content.content_lists()
            elif layer.content is not None:
                yield layer.content
            if layer.mask is not None:
                yield layer.mask.content


def crop(*mobjects, minus=None, inside=None, feather=0.0, hard=False, **kwargs):
    if (minus is None) == (inside is None):
        raise ValueError("crop requires exactly one of minus or inside")
    shape = inside if minus is None else minus
    members = [shape] if isinstance(shape, Mobject) else list(shape)
    return Layer(
        *mobjects,
        mask=Mask(*members, invert=minus is not None, feather=feather, hard=hard),
        **kwargs,
    )


def gaussian_weights(sigma):
    sigma = float(sigma)
    requested = max(math.ceil(3 * sigma), 1)
    radius = min(requested, 63)
    if requested > 63:
        warnings.warn(
            f"gaussian-kernel-radius-limit: sigma {sigma} asks for radius {requested}; weights[64] caps it at 63",
            RuntimeWarning,
            stacklevel=2,
        )
    weights = np.array(
        [math.exp(-0.5 * (index / sigma) ** 2) for index in range(radius + 1)],
        dtype=np.float32,
    )
    total = sum_left_to_right(weights[1:])
    weights /= weights[0] + np.float32(2) * total
    return radius, weights


class Mask:
    def __init__(self, *mobjects, invert=False, feather=0.0, hard=False, luma=False):
        if any(not isinstance(mob, Mobject) for mob in mobjects):
            raise TypeError("Mask content must consist of Mobjects")
        self.content = list(mobjects)
        self.invert = bool(invert)
        self.feather = float(feather)
        self.hard = bool(hard)
        self.luma = bool(luma)


class Layer:
    def __init__(
        self,
        *mobjects,
        blend="normal",
        opacity=1.0,
        effects=(),
        mask=None,
        matte=None,
        camera=None,
        window=None,
    ):
        from janim.animation.camera import CameraFrame

        if camera is not None and not isinstance(camera, CameraFrame):
            raise TypeError("camera must be a CameraFrame")
        if not mobjects and (camera is not None or window is not None):
            raise ValueError("an adjustment layer cannot carry a camera or window")
        if not mobjects:
            for name, value, default in (
                ("mask", mask, None),
                ("opacity", opacity, 1.0),
                ("blend", blend, "normal"),
                ("matte", matte, None),
            ):
                if value != default:
                    raise ValueError(f"an adjustment layer cannot carry {name}={value!r}")
        precomp = len(mobjects) == 1 and isinstance(mobjects[0], Composition)
        if not precomp and any(not isinstance(mob, Mobject) for mob in mobjects):
            raise TypeError("Layer content must consist of Mobjects")
        if mask is not None and not isinstance(mask, Mask):
            raise TypeError("mask must be a Mask")
        if window is not None and not isinstance(window, Mobject):
            raise TypeError("window must be a Mobject")
        self.content = mobjects[0] if precomp else list(mobjects) if mobjects else None
        self.blend = blend
        self.opacity = float(opacity)
        self.effects = list(effects)
        self.mask = mask
        self.matte = matte
        self.camera = camera
        self.window = window


def validate_composition(composition):
    if not isinstance(composition, Composition):
        raise TypeError("composition must be a Composition")
    for index, layer in enumerate(composition.layers):
        if not isinstance(layer, Layer):
            raise TypeError("a Composition requires Layer objects")
        if layer.content is None:
            for name, default in (
                ("mask", None),
                ("opacity", 1.0),
                ("blend", "normal"),
                ("matte", None),
                ("camera", None),
                ("window", None),
            ):
                value = getattr(layer, name)
                if value != default:
                    raise ValueError(f"an adjustment layer cannot carry {name}={value!r}")
            continue
        if layer.blend not in BLEND_MODES:
            raise ValueError(f"unknown blend mode {layer.blend!r}; use {', '.join(BLEND_MODES)}")
        if layer.matte is not None:
            if index + 1 >= len(composition.layers):
                raise ValueError(f"matte={layer.matte!r} has no next layer to consume")
            if layer.matte not in MATTE_MODES:
                raise ValueError(f"unknown matte {layer.matte!r}; use {', '.join(MATTE_MODES)}")
        if isinstance(layer.content, Composition):
            validate_composition(layer.content)


def resolved_camera(layer, ambient):
    if layer.camera is None:
        return ambient
    from .camera import Camera

    camera = layer.camera.camera
    return Camera(
        width=ambient.width,
        height=ambient.height,
        frame_width=camera.frame_width,
        frame_height=camera.frame_height,
        fovy=camera.fovy,
        background=ambient.background,
        light_position=ambient.light_position,
        orientation=camera.orientation,
        center_point=camera.center_point,
    )


def project_ndc(camera, point, *, flip_y, fixed):
    from janim.constants import FRAME_HEIGHT, FRAME_WIDTH

    point = np.asarray(point, dtype=np.float64)
    if fixed:
        value = point
    else:
        view = camera.get_view_matrix()
        value = np.array(
            [
                view[index, 0] * point[0] + view[index, 1] * point[1]
                + view[index, 2] * point[2] + view[index, 3]
                for index in range(3)
            ],
            dtype=np.float64,
        )
    z = value[2] * camera.get_scale() / camera.get_focal_distance()
    w = 1.0 - z
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.array(
            (
                value[0] * 2 / float(FRAME_WIDTH) / w,
                value[1] * (-1.0 if flip_y else 1.0) * 2 / float(FRAME_HEIGHT) / w,
            ),
        )


def window_destination(camera, window, *, flip_y=False):
    # `fixed_in_frame` is read from any mobject that has the
    # field (a Surface or a cloud makes as good a window as a VMobject).
    uniforms = getattr(window, "uniforms", None)
    fixed = bool(uniforms["is_fixed_in_frame"]) if uniforms is not None else False
    box = window.get_bounding_box()
    first, last = box[0], box[2]
    x0 = y0 = math.inf
    x1 = y1 = -math.inf
    for x in (first[0], last[0]):
        for y in (first[1], last[1]):
            for z in (first[2], last[2]):
                point = project_ndc(camera, (x, y, z), flip_y=flip_y, fixed=fixed)
                x0, x1 = min(x0, point[0]), max(x1, point[0])
                y0, y1 = min(y0, point[1]), max(y1, point[1])
    if not (math.isfinite(x0) and math.isfinite(y1) and x1 - x0 > 1e-6 and y1 - y0 > 1e-6):
        return None
    return x0, y0, x1, y1


def window_source(width, height, camera, destination):
    dw = (destination[2] - destination[0]) / 2 * width
    dh = abs(destination[3] - destination[1]) / 2 * height
    aspect = dw / dh
    if camera.frame_width / camera.frame_height >= aspect:
        source_height = camera.frame_height
        source_width = aspect * source_height
    else:
        source_width = camera.frame_width
        source_height = source_width / aspect
    u = source_width / camera.frame_width / 2
    v = source_height / camera.frame_height / 2
    return 0.5 - u, 0.5 - v, 0.5 + u, 0.5 + v


def _mean_centers(content):
    centers = [mob.get_center().astype(np.float64) for mob in content]
    total = centers[0].copy()
    for center in centers[1:]:
        total = total + center
    return total / len(centers)


def focus_composition(composition, camera):
    from .algebra import quat_to_matrix

    for layer in composition.layers:
        view = resolved_camera(layer, camera)
        if isinstance(layer.content, Composition):
            focus_composition(layer.content, view)
        effects = [effect for effect in layer.effects if isinstance(effect, Dof)]
        if not effects:
            continue
        if not isinstance(layer.content, list) or not layer.content:
            for effect in effects:
                effect.current_sigma = 0.0
            continue
        center = _mean_centers(layer.content)
        eye = view.get_implied_camera_location()
        direction = -quat_to_matrix(view.orientation)[:, 2]
        distance = float(julia_sum((center - eye) * direction))
        for effect in effects:
            focus = view.get_focal_distance() if effect.focus is None else effect.focus
            effect.current_sigma = min(max(effect.aperture * abs(distance - focus), 0.0), effect.max_sigma)
    return composition
