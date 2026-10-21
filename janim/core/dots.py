"""Point clouds: DotCloud, TrueDot, GlowDots and PGroup.

A cloud keeps one radius and one RGBA per point; the renderer draws each as an
instanced disc (`render_kind = "dots"`). The verbs called on a cloud use the
f64 forms; a Group verb reaches `points` through the generic path.
"""

import numpy as np

from janim.constants import GREY_C, YELLOW
from .algebra import apply_matrix_rows, rotation_matrix
from .colorspace import color_to_rgba
from .mobject import Group, Mobject, VMobject
from .transforms import point3

DEFAULT_TRUE_DOT_RADIUS = 0.05
DEFAULT_GLOW_DOT_RADIUS = 0.2


class DotCloud(Mobject):
    render_kind = "dots"
    is_interpolable = True
    _transform_bbox = False

    def __init__(
        self,
        points=(),
        *,
        color=GREY_C,
        opacity=1.0,
        radius=DEFAULT_TRUE_DOT_RADIUS,
        glow_factor=0.0,
        anti_alias_width=2.0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        points = np.asarray(points, dtype=np.float32).reshape(-1, 3)
        self.points = points.copy()
        self.radii = np.full(len(points), np.float32(radius), dtype=np.float32)
        self.rgba = np.tile(color_to_rgba(color, opacity), (len(points), 1))
        self.glow_factor = float(glow_factor)
        self.anti_alias_width = float(anti_alias_width)
        self.note_changed_data()

    def __repr__(self):
        glow = f", glow={self.glow_factor}" if self.glow_factor > 0 else ""
        return f"DotCloud({len(self.points)} points, r~{round(self.get_radius(), 3)}{glow})"

    # ── points ───────────────────────────────────────────────────────────
    def set_points(self, points):
        """New points; radii and colours are refitted (kept, trimmed or the last repeated)."""
        points = np.asarray(points, dtype=np.float32).reshape(-1, 3)
        n = len(points)

        def refit(values, fallback):
            if not len(values):
                return np.repeat(np.asarray(fallback, dtype=np.float32)[None], n, axis=0)
            if n <= len(values):
                return values[:n].copy()
            return np.concatenate((values, np.repeat(values[-1:], n - len(values), axis=0)))

        self.radii = refit(self.radii, np.float32(DEFAULT_TRUE_DOT_RADIUS)).reshape(n)
        self.rgba = refit(self.rgba, color_to_rgba(GREY_C, 1.0)).reshape(n, 4)
        self.points = points.copy()
        return self.note_changed_data()

    # ── radii and glow ───────────────────────────────────────────────────
    def set_radius(self, radius):
        self.radii.fill(np.float32(radius))
        return self

    def set_radii(self, radii):
        radii = np.asarray(radii, dtype=np.float32).reshape(-1)
        if len(radii) != len(self.points):
            raise ValueError(f"set_radii: {len(radii)} radii for {len(self.points)} points")
        self.radii[:] = radii
        return self

    def get_radii(self):
        return self.radii

    def get_radius(self):
        return 0.0 if not len(self.radii) else float(self.radii.max())

    def scale_radii(self, factor):
        self.radii *= np.float32(factor)
        return self

    def set_glow_factor(self, glow_factor):
        self.glow_factor = float(glow_factor)
        return self

    def get_glow_factor(self):
        return self.glow_factor

    # ── colour ───────────────────────────────────────────────────────────
    def set_color(self, color=None, opacity=None, recurse=True):
        if color is not None:
            self.rgba[:, :3] = color_to_rgba(color, 1.0)[:3]
        if opacity is not None:
            self.rgba[:, 3] = np.float32(opacity)
        return self

    def set_opacity(self, opacity, recurse=True):
        return self.set_color(opacity=opacity)

    def get_opacity(self):
        return 1.0 if not len(self.rgba) else float(self.rgba[0, 3])

    def set_colors(self, colors, *, opacity=None):
        """Per-point colours (a colormap over speeds); lengths must match."""
        if len(colors) != len(self.points):
            raise ValueError(f"set_colors: {len(colors)} colours for {len(self.points)} points")
        if isinstance(colors, np.ndarray) and colors.ndim == 2 and colors.shape[1] in (3, 4):
            self.rgba[:, :3] = colors[:, :3].astype(np.float32)     # rgb(a) rows in [0, 1], e.g. a color_gradient
        else:
            for index, color in enumerate(colors):
                self.rgba[index, :3] = color_to_rgba(color, 1.0)[:3]
        if opacity is not None:
            self.rgba[:, 3] = np.float32(opacity)
        return self

    def make_3d(self, reflectiveness=0.5, gloss=0.1, shadow=0.2):
        """ManimGL's fake spheres: shading plus the z-buffer."""
        self.uniforms["shading"] = np.array((reflectiveness, gloss, shadow), dtype=np.float32)
        self.depth_test = True
        return self

    def set_shading(self, reflectiveness=None, gloss=None, shadow=None, recurse=True):
        current = self.uniforms["shading"]
        values = [current[0], current[1], current[2]]
        for index, value in enumerate((reflectiveness, gloss, shadow)):
            if value is not None:
                values[index] = value
        self.uniforms["shading"] = np.array(values, dtype=np.float32)
        return self

    # ── extent ───────────────────────────────────────────────────────────
    def _expand_leaf_box(self, low, high):
        radius = np.float32(self.get_radius())
        np.subtract(low, radius, out=low)
        np.add(high, radius, out=high)

    def get_bounding_box(self):
        self._needs_new_bounding_box = True
        return super().get_bounding_box()

    def get_center_of_mass(self):
        total = np.zeros(3, dtype=np.float64)
        count = 0
        for mob in self.get_family():
            if isinstance(mob, (DotCloud, VMobject)):
                for point in mob.points:
                    total += point.astype(np.float64)
                    count += 1
        if count == 0:
            return np.zeros(3, dtype=np.float32)
        return (total / count).astype(np.float32)

    # ── the verbs of a cloud ─────────────────────────────────────────────
    def _cloud_pivot(self, about_point, about_edge):
        pivot = self._pivot(about_point, about_edge)
        return (self.get_center() if pivot is None else pivot).astype(np.float64)

    def scale(self, factor, min_scale_factor=1e-8, about_point=None, about_edge=(0, 0, 0), scale_radii=True):
        """Scales the points in f64; the radii follow (GL parity) unless `scale_radii=False`."""
        center = self._cloud_pivot(about_point, about_edge)
        f = float(factor)
        self.points[:] = center + f * (self.points.astype(np.float64) - center)
        if scale_radii:
            self.radii *= np.float32(abs(f))
        return self.note_changed_data()

    def rotate(self, angle, axis=(0, 0, 1), about_point=None, about_edge=(0, 0, 0)):
        center = self._cloud_pivot(about_point, about_edge)
        matrix = rotation_matrix(float(angle), axis)
        self.points[:] = center + apply_matrix_rows(self.points.astype(np.float64) - center, matrix)
        return self.note_changed_data()

    # ── interpolation ────────────────────────────────────────────────────
    def align_data(self, other, **kwargs):
        if not isinstance(other, DotCloud) or len(other.points) != len(self.points):
            raise ValueError(
                f"Transform between DotClouds needs equal sizes "
                f"({len(self.points)} vs {len(getattr(other, 'points', ()))}): pointwise lerp is the whole story",
            )
        return self

    def interpolate(self, first, second, alpha, **kwargs):
        t = np.float32(alpha)
        self.points[:] = first.points + t * (second.points - first.points)
        self.radii[:] = (1 - t) * first.radii + t * second.radii
        self.rgba[:] = (1 - t) * first.rgba + t * second.rgba
        self.glow_factor = first.glow_factor + float(alpha) * (second.glow_factor - first.glow_factor)
        return self.note_changed_data()

    def become(self, other, match_updaters=False):
        self.points = other.points.copy()
        self.radii = other.radii.copy()
        self.rgba = other.rgba.copy()
        self.glow_factor = other.glow_factor
        self.uniforms["shading"] = other.uniforms["shading"].copy()
        self.depth_test = other.depth_test
        if match_updaters:
            self.match_updaters(other)
        return self.note_changed_data()


def TrueDot(center=(0, 0, 0), **kwargs):
    """One honest disc (ManimGL's name for the shader too)."""
    return DotCloud([point3(center)], **kwargs)


def GlowDots(points=(), *, color=YELLOW, radius=DEFAULT_GLOW_DOT_RADIUS, glow_factor=2.0, **kwargs):
    """The glow preset: a bigger radius and the `pow(1 - r, 2)` falloff."""
    return DotCloud(points, color=color, radius=radius, glow_factor=glow_factor, **kwargs)


def GlowDot(center=(0, 0, 0), **kwargs):
    return GlowDots([point3(center)], **kwargs)


class PGroup(Group):
    """A Group that accepts point clouds only."""

    def __init__(self, *clouds, **kwargs):
        for index, cloud in enumerate(clouds):
            if not isinstance(cloud, DotCloud):
                raise TypeError(
                    f"PGroup takes point clouds (DotCloud, TrueDot, GlowDots) and member {index} "
                    f"is a {type(cloud).__name__}; use Group for a mixed bag",
                )
        super().__init__(*clouds, **kwargs)
