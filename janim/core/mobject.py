"""Mobject graphs holding float32 data, with ManimGL object semantics."""

import inspect
import operator

import numpy as np

from janim.constants import BLACK

from .alignment import AlignmentMixin
from .bbox import BoundingBoxMixin
from .colorspace import color_gradient, color_to_rgba, rgb_to_hex
from .layout import LayoutMixin
from .paths import PathMixin
from .states import StateMixin
from .transforms import TransformMixin


JOINT_TYPES = ("no_joint", "auto", "bevel", "miter")


class Updater:
    def __init__(self, func):
        if not callable(func):
            raise TypeError("an updater must be callable")
        self.func = func
        # By ARITY, as ManimGL 1.7 does:
        # whatever accepts two positional arguments is handed dt in the second,
        # a defaulted one included (`lambda mob, n=3:` receives dt in `n`). The
        # published ManimGL 1.7.2 decided by the NAME `dt` instead.
        try:
            inspect.signature(func).bind(None, None)
        except (TypeError, ValueError):
            self.takes_dt = False
        else:
            self.takes_dt = True

    def __call__(self, mobject, dt=0, frame_rate=None):
        if not self.takes_dt:
            self.func(mobject)
            return
        steps = 1 if frame_rate is None else max(int(dt * frame_rate), 1)
        for _ in range(steps):
            self.func(mobject, dt / steps)


class Mobject(LayoutMixin, BoundingBoxMixin, TransformMixin, AlignmentMixin, StateMixin):
    """A node owns ordered child/parent lists; point arrays are ordinary numpy."""

    shader_folder = ""
    render_primitive = 5
    is_interpolable = False
    _factory_fill_color = "#FFFFFF"
    _factory_stroke_color = "#FFFFFF"
    _factory_fill_opacity = 1.0
    _factory_stroke_width = 0.0

    def __init__(
        self,
        color=None,
        *,
        points=None,
        fill_color=None,
        fill_opacity=None,
        stroke_color=None,
        stroke_opacity=1.0,
        stroke_width=None,
        opacity=None,
        joint_type="auto",
        z_index=0,
        shading=(0.0, 0.0, 0.0),
        depth_test=False,
        is_fixed_in_frame=False,
        texture_paths=None,
        key=None,
    ):
        if joint_type not in JOINT_TYPES:
            raise ValueError("joint_type must be no_joint, auto, bevel or miter; round belongs to Cairo/ManimCE")
        self.submobjects = []
        self.parents = []
        self.family = [self]
        self.draw_family = None
        self.keys = [] if key is None else [str(key)]
        self.key_runs = None
        self._key_group_cache = {}
        self.points = np.empty((0, 3), dtype=np.float32)
        self.fill_rgba = np.empty((0, 4), dtype=np.float32)
        self.stroke_rgba = np.empty((0, 4), dtype=np.float32)
        self.stroke_width = np.empty(0, dtype=np.float32)
        fill = fill_color if fill_color is not None else color if color is not None else self._factory_fill_color
        stroke = stroke_color if stroke_color is not None else color if color is not None else self._factory_stroke_color
        fill_opacity = self._factory_fill_opacity if fill_opacity is None else fill_opacity
        stroke_width = self._factory_stroke_width if stroke_width is None else stroke_width
        self.default_fill_rgba = color_to_rgba(fill, fill_opacity if opacity is None else opacity)
        self.default_stroke_rgba = color_to_rgba(stroke, stroke_opacity if opacity is None else opacity)
        self.default_stroke_width = np.float32(stroke_width)
        self.bounding_box = np.zeros((3, 3), dtype=np.float32)
        self._needs_new_bounding_box = True
        self._bbox_has_points = False
        self._data_has_changed = True
        self.subpath_end_indices = None
        self.updaters = []
        self.updating_suspended = False
        self._has_updaters_in_family = False
        self._has_time_based_updaters_in_family = False
        self._is_animating = False
        self.saved_state = None
        self.target = None
        self.z_index = float(z_index)
        self.joint_type = joint_type
        self.depth_test = bool(depth_test)
        self.texture_paths = texture_paths
        self.shader_wrapper = None
        self.fill_gradient = None
        self.uniforms = {
            "joint_type": JOINT_TYPES.index(joint_type),
            "shading": np.array(shading, dtype=np.float32),
            "is_fixed_in_frame": float(is_fixed_in_frame),
        }
        self.init_points()
        if points is not None:
            self.set_points(points)

    def init_points(self):
        """Subclass construction hook, called after the base data is ready."""

    def __repr__(self):
        return f"{type(self).__name__}({len(self.points)} points, {len(self)} children)"

    def __len__(self):
        return len(self.submobjects)

    def __iter__(self):
        return iter(self.submobjects)

    def __getitem__(self, value):
        if isinstance(value, slice):
            indices = tuple(range(*value.indices(len(self.submobjects))))
            return self._memoized_group(
                ("range", indices),
                lambda: self.get_group_class()(*(self.submobjects[index] for index in indices)),
            )
        return self.submobjects[value]

    def __add__(self, other):
        return self.get_group_class()(self, other)

    def __mul__(self, count):
        return self.replicate(count)

    def split(self):
        return self.submobjects

    def get_group_class(self):
        return Group

    def get_family(self, recurse=True):
        if not recurse:
            return [self]
        if self.family is None:
            family = []
            pending = [self]
            while pending:
                mob = pending.pop()
                family.append(mob)
                pending.extend(reversed(mob.submobjects))
            self.family = family
        return self.family

    def family_members_with_points(self):
        return [mob for mob in self.get_family() if mob.has_points()]

    def _draw_family(self):
        if self.draw_family is not None:
            return self.draw_family
        family = self.get_family()
        if not any(member.z_index != 0 for member in family):
            self.draw_family = family
            return family
        result = []
        pending = [self]
        while pending:
            member = pending.pop()
            result.append(member)
            pending.extend(reversed(sorted(member.submobjects, key=lambda child: child.z_index)))
        self.draw_family = result
        return result

    def _invalidate_ancestors(self, family=False, bbox=False, updaters=False):
        pending = [self]
        seen = {}
        while pending:
            mob = pending.pop()
            if mob in seen:
                continue
            seen[mob] = None
            if family:
                mob.family = None
                mob.draw_family = None
                mob._key_group_cache = {}
                mob.key_runs = None
            if bbox:
                mob._needs_new_bounding_box = True
            if updaters:
                mob._has_updaters_in_family = None
                mob._has_time_based_updaters_in_family = None
            mob._data_has_changed = True
            pending.extend(mob.parents)
        return self

    def note_changed_family(self, only_changed_order=False):
        return self._invalidate_ancestors(
            family=True,
            bbox=not only_changed_order,
            updaters=not only_changed_order,
        )

    def note_changed_data(self):
        self.subpath_end_indices = None
        return self._invalidate_ancestors(bbox=True)

    def _check_children(self, children):
        for child in children:
            if not isinstance(child, Mobject):
                raise TypeError("all children must be Mobjects")
            if isinstance(self, VMobject) and not isinstance(child, VMobject):
                raise TypeError("VMobject children must be VMobjects; use Group for mixed objects")
            if child is self:
                raise ValueError("a mobject cannot contain itself")
            for descendant in child.get_family():
                if descendant is self:
                    raise ValueError("adding this child would create a family cycle")

    def add(self, *mobjects):
        self._check_children(mobjects)
        changed = False
        known = dict.fromkeys(self.submobjects)
        for mob in mobjects:
            if mob not in known:
                self.submobjects.append(mob)
                known[mob] = None
                changed = True
            if self not in mob.parents:
                mob.parents.append(self)
                changed = True
        if changed:
            self.note_changed_family()
        return self

    def remove(self, *to_remove, reassemble=True, recurse=True):
        excluded = dict.fromkeys(to_remove)
        for parent in self.get_family(recurse):
            removed = [child for child in parent.submobjects if child in excluded]
            if not removed:
                continue
            parent.submobjects[:] = [child for child in parent.submobjects if child not in excluded]
            for child in removed:
                child.parents[:] = [ancestor for ancestor in child.parents if ancestor is not parent]
            if reassemble:
                parent.note_changed_family()
        return self

    def clear(self):
        return self.remove(*self.submobjects, recurse=False)

    def set_submobjects(self, submobjects):
        children = list(dict.fromkeys(submobjects))
        if self.submobjects == children:
            return self
        self._check_children(children)
        previous = dict.fromkeys(self.submobjects)
        following = dict.fromkeys(children)
        for child in previous:
            if child not in following:
                child.parents[:] = [parent for parent in child.parents if parent is not self]
        for child in following:
            if self not in child.parents:
                child.parents.append(self)
        self.submobjects[:] = children
        return self.note_changed_family()

    def replace_submobject(self, index, new_submob):
        children = self.submobjects.copy()
        children[index] = new_submob
        return self.set_submobjects(children)

    def insert_submobject(self, index, new_submob):
        children = self.submobjects.copy()
        children.insert(index, new_submob)
        return self.set_submobjects(children)

    def add_to_back(self, *mobjects):
        fresh = [mob for mob in dict.fromkeys(mobjects) if mob not in self.submobjects]
        return self.set_submobjects([*fresh, *self.submobjects]) if fresh else self

    def get_points(self):
        return self.points

    def get_num_points(self):
        return len(self.points)

    def has_points(self):
        return bool(len(self.points))

    def get_all_points(self):
        if not self.submobjects:
            return self.points.copy()
        return np.concatenate([mob.points for mob in self.get_family()])

    def _resize_style(self, size):
        for name, default in (
            ("fill_rgba", self.default_fill_rgba),
            ("stroke_rgba", self.default_stroke_rgba),
            ("stroke_width", self.default_stroke_width),
        ):
            rows = getattr(self, name)
            if len(rows) == size:
                continue
            filler = rows[-1] if len(rows) else default
            resized = np.empty((size, *rows.shape[1:]), dtype=np.float32)
            kept = min(size, len(rows))
            resized[:kept] = rows[:kept]
            resized[kept:] = filler
            setattr(self, name, resized)

    def set_points(self, points):
        points = np.asarray(points, dtype=np.float32)
        if points.size == 0:
            points = points.reshape(0, 3)
        if points.ndim != 2 or points.shape[1] != 3:
            raise ValueError("points must have shape (n, 3)")
        self._resize_style(len(points))
        if self.points.shape == points.shape:
            self.points[:] = points
        else:
            self.points = points.copy()
        return self.note_changed_data()

    def append_points(self, points):
        points = np.asarray(points, dtype=np.float32).reshape(-1, 3)
        return self.set_points(np.concatenate((self.points, points)))

    def clear_points(self):
        return self.set_points(np.empty((0, 3), dtype=np.float32))

    def match_points(self, other):
        return self.set_points(other.get_points())

    @property
    def data(self):
        return {
            "point": self.points,
            "fill_rgba": self.fill_rgba,
            "stroke_rgba": self.stroke_rgba,
            "stroke_width": self.stroke_width,
        }

    def set_data(self, data):
        for name, key in (("points", "point"), ("fill_rgba", "fill_rgba"), ("stroke_rgba", "stroke_rgba"), ("stroke_width", "stroke_width")):
            source = np.asarray(data[key], dtype=np.float32)
            current = getattr(self, name)
            if current.shape == source.shape:
                current[:] = source
            else:
                setattr(self, name, source.copy())
        return self.note_changed_data()

    def shuffle(self, recurse=False):
        """ManimGL's: shuffle the children in place (Python's `random`; seed it for a deterministic scene)."""
        import random

        if recurse:
            for child in self.submobjects:
                child.shuffle(recurse=True)
        random.shuffle(self.submobjects)
        return self.note_changed_family()

    def get_uniforms(self):
        return dict(self.uniforms)

    def set_uniform(self, recurse=True, **new_uniforms):
        """ManimGL's keyword form of `set_uniforms`, over the family."""
        for mob in self.get_family() if recurse else (self,):
            mob.set_uniforms(new_uniforms)
        return self

    def set_uniforms(self, uniforms):
        self.uniforms.update(
            (
                (key, value.copy() if isinstance(value, np.ndarray) else value)
                for key, value in uniforms.items()
            ),
        )
        self.joint_type = JOINT_TYPES[int(self.uniforms["joint_type"])]
        self._data_has_changed = True
        return self

    def _set_rgba(self, name, color, opacity, recurse):
        color_list = isinstance(color, (list, tuple, np.ndarray)) and (
            len(color) == 0 or not np.isscalar(color[0]) or isinstance(color[0], str)
        )
        opacity_list = isinstance(opacity, (list, tuple, np.ndarray))
        if color_list or opacity_list:
            if color_list and not len(color):
                raise ValueError("a color list needs at least one color")
            if opacity_list and not len(opacity):
                raise ValueError("an opacity list needs at least one entry")
            colors = None if color is None else np.array(
                [color_to_rgba(value) for value in (color if color_list else [color])],
                dtype=np.float32,
            )
            alphas = None if opacity is None else np.asarray(
                opacity if opacity_list else [opacity],
                dtype=np.float32,
            )
            for mob in self.get_family(recurse):
                rows = getattr(mob, name)
                fallback = getattr(mob, "default_" + name)
                count = max(len(rows), 1)
                if colors is not None:
                    rgb = _resize_with_interpolation(colors, count)
                    if len(rows):
                        rows[:, :3] = rgb[:, :3]
                    else:
                        fallback[:3] = rgb[0, :3]
                if alphas is not None:
                    alpha = _resize_with_interpolation(alphas, count)
                    rows[:, 3] = alpha[:len(rows)]
                    if not len(rows) or not opacity_list:
                        fallback[3] = alpha[0]
                mob._data_has_changed = True
            return self._invalidate_ancestors()
        base = None if color is None else color_to_rgba(color)
        for mob in self.get_family(recurse):
            rows = getattr(mob, name)
            fallback = getattr(mob, "default_" + name)
            if base is not None:
                rows[:, :3] = base[:3]
                fallback[:3] = base[:3]
            if opacity is not None:
                rows[:, 3] = np.float32(opacity)
                fallback[3] = np.float32(opacity)
            mob._data_has_changed = True
        return self._invalidate_ancestors()

    def set_fill(self, color=None, opacity=None, recurse=True):
        return self._set_rgba("fill_rgba", color, opacity, recurse)

    def set_backstroke(self, color=BLACK, width=3):
        """GL's `set_backstroke` = `set_stroke(color, width, behind=True)`.

        There is no stroke-behind-the-fill pass, so this is a plain stroke:
        exact for a line, over the fill on a filled shape (GL draws it under).
        """
        return self.set_stroke(color=color, width=width)

    def set_stroke(self, color=None, width=None, opacity=None, recurse=True):
        self._set_rgba("stroke_rgba", color, opacity, recurse)
        if width is not None:
            for mob in self.get_family(recurse):
                mob.stroke_width[:] = np.float32(width)
                mob.default_stroke_width = np.float32(width)
        return self

    def set_color(self, color, opacity=None, recurse=True):
        self.set_fill(color, opacity, recurse).set_stroke(color, opacity=opacity, recurse=recurse)
        for mob in self.get_family(recurse):
            if mob is not self and getattr(mob, "render_kind", None) in ("surface", "dots"):
                mob.set_color(color, opacity)
        return self

    def set_opacity(self, opacity, recurse=True):
        self.set_fill(opacity=opacity, recurse=recurse).set_stroke(opacity=opacity, recurse=recurse)
        for mob in self.get_family(recurse):
            kind = getattr(mob, "render_kind", None)
            if kind in ("image", "textured_surface"):
                mob.opacity = float(np.clip(opacity, 0, 1))
            elif kind in ("surface", "dots"):
                mob.rgba[:, 3] = np.float32(opacity)
        return self

    def fade(self, darkness=0.5, recurse=True):
        return self.set_opacity(1 - darkness, recurse=recurse)

    def set_style(
        self,
        *,
        fill_color=None,
        fill_opacity=None,
        stroke_color=None,
        stroke_opacity=None,
        stroke_width=None,
        shading=None,
        recurse=True,
    ):
        self.set_fill(fill_color, fill_opacity, recurse)
        self.set_stroke(stroke_color, stroke_width, stroke_opacity, recurse)
        if shading is not None:
            self.set_shading(*shading, recurse=recurse)
        return self

    def set_shading(self, reflectiveness=0.0, gloss=0.0, shadow=0.0, recurse=True):
        for mob in self.get_family(recurse):
            mob.uniforms["shading"] = np.array([reflectiveness, gloss, shadow], dtype=np.float32)
        return self

    def get_shading(self):
        return self.uniforms["shading"].copy()

    def apply_depth_test(self, recurse=True):
        for mob in self.get_family(recurse):
            mob.depth_test = True
        return self

    def deactivate_depth_test(self, recurse=True):
        for mob in self.get_family(recurse):
            mob.depth_test = False
        return self

    def fix_in_frame(self, recurse=True):
        for mob in self.get_family(recurse):
            mob.uniforms["is_fixed_in_frame"] = 1.0
        return self

    def unfix_from_frame(self, recurse=True):
        for mob in self.get_family(recurse):
            mob.uniforms["is_fixed_in_frame"] = 0.0
        return self

    def _paint_gradient(self, name, colors):
        if self.has_points():
            rows = getattr(self, name)
            rows[:, :3] = color_gradient(colors, len(rows))[:, :3]
            getattr(self, "default_" + name)[:3] = color_gradient(colors, 2)[-1, :3]
        else:
            members = self.family_members_with_points()
            for mob, color in zip(members, color_gradient(colors, len(members))):
                mob._set_rgba(name, color, None, False)
        self._data_has_changed = True
        return self

    def set_fill_by_gradient(self, *colors):
        return self._paint_gradient("fill_rgba", colors)

    def set_stroke_by_gradient(self, *colors):
        return self._paint_gradient("stroke_rgba", colors)

    def set_color_by_gradient(self, *colors):
        return self.set_fill_by_gradient(*colors).set_stroke_by_gradient(*colors)

    def get_fill_color(self):
        return rgb_to_hex(self.fill_rgba[0] if self.has_points() else self.default_fill_rgba)

    def get_stroke_color(self):
        return rgb_to_hex(self.stroke_rgba[0] if self.has_points() else self.default_stroke_rgba)

    def get_fill_opacity(self):
        return float((self.fill_rgba[0] if self.has_points() else self.default_fill_rgba)[3])

    def get_stroke_opacity(self):
        return float((self.stroke_rgba[0] if self.has_points() else self.default_stroke_rgba)[3])

    def get_stroke_width(self):
        return float(self.stroke_width[0] if self.has_points() else self.default_stroke_width)

    def get_color(self):
        return self.get_fill_color() if self.get_fill_opacity() > 0 else self.get_stroke_color()

    get_opacity = get_fill_opacity

    def get_style(self):
        return {
            "fill_rgba": self.fill_rgba.copy(),
            "stroke_rgba": self.stroke_rgba.copy(),
            "stroke_width": self.stroke_width.copy(),
        }

    def match_style(self, other, recurse=True):
        self.set_fill(other.get_fill_color(), opacity=other.get_fill_opacity(), recurse=False)
        self.set_stroke(other.get_stroke_color(), width=other.get_stroke_width(), opacity=other.get_stroke_opacity(), recurse=False)
        if len(self.points) == len(other.points):
            for name in ("fill_rgba", "stroke_rgba", "stroke_width"):
                getattr(self, name)[:] = getattr(other, name)
        if recurse and self.submobjects:
            sources = other.submobjects or [other]
            count = max(len(self), len(sources))
            for index in range(count):
                self.submobjects[index * len(self) // count].match_style(sources[index * len(sources) // count])
        return self

    def set_joint_type(self, joint_type, recurse=True):
        if joint_type not in JOINT_TYPES:
            raise ValueError("joint_type must be no_joint, auto, bevel or miter; round is a Cairo join")
        for mob in self.get_family(recurse):
            mob.joint_type = joint_type
            mob.uniforms["joint_type"] = JOINT_TYPES.index(joint_type)
        return self

    def get_joint_type(self):
        return self.uniforms["joint_type"]

    def set_z_index(self, z_index, recurse=True):
        family = self.get_family(recurse)
        for mob in family:
            mob.z_index = float(z_index)
        pending = list(family)
        seen = {}
        while pending:
            mob = pending.pop()
            if mob in seen:
                continue
            seen[mob] = None
            mob.draw_family = None
            pending.extend(mob.parents)
        return self

    def get_z_index(self):
        return self.z_index

    def get_keys(self):
        return self.keys

    def has_key(self, key):
        return str(key) in self.keys

    def find_by_key(self, key):
        return [mob for mob in self.get_family()[1:] if mob.has_key(key)]

    def get_all_keys(self):
        return list(dict.fromkeys(key for mob in self.get_family()[1:] for key in mob.get_keys()))

    def _memoized_group(self, key, factory):
        if key not in self._key_group_cache:
            self._key_group_cache[key] = factory()
        return self._key_group_cache[key]

    def set_key(self, key):
        self.keys[:] = [str(key)]
        return self._expire_key_memos()

    def add_key(self, key):
        key = str(key)
        if key not in self.keys:
            self.keys.append(key)
            self._expire_key_memos()
        return self

    def _expire_key_memos(self):
        pending = list(self.parents)
        seen = {}
        while pending:
            mob = pending.pop()
            if mob in seen:
                continue
            seen[mob] = None
            for key in tuple(mob._key_group_cache):
                if isinstance(key, tuple) and key[:1] in (("key",), ("parts",)):
                    del mob._key_group_cache[key]
            pending.extend(mob.parents)
        return self

    def refresh_has_updater_status(self):
        return self._invalidate_ancestors(updaters=True)

    def has_updaters(self):
        if self._has_updaters_in_family is None:
            self._has_updaters_in_family = any(mob.updaters for mob in self.get_family())
        return self._has_updaters_in_family

    def has_time_based_updaters(self):
        if self._has_time_based_updaters_in_family is None:
            self._has_time_based_updaters_in_family = any(u.takes_dt for mob in self.get_family() for u in mob.updaters)
        return self._has_time_based_updaters_in_family

    def get_updaters(self):
        return [updater.func for updater in self.updaters]

    def add_updater(self, update_func, call=True):
        self.updaters.append(Updater(update_func))
        self.refresh_has_updater_status()
        if call:
            self.update(0)
        return self

    def insert_updater(self, update_func, index=0):
        self.updaters.insert(index, Updater(update_func))
        return self.refresh_has_updater_status()

    def match_updaters(self, other):
        self.updaters = list(other.updaters)
        return self.refresh_has_updater_status()

    def remove_updater(self, update_func):
        self.updaters[:] = [updater for updater in self.updaters if updater.func is not update_func]
        return self.refresh_has_updater_status()

    def clear_updaters(self, recurse=True):
        for mob in self.get_family(recurse):
            mob.updaters.clear()
            mob._has_updaters_in_family = None
            mob._has_time_based_updaters_in_family = None
        return self.refresh_has_updater_status()

    def update(self, dt=0, recurse=True, frame_rate=None):
        if not self.has_updaters() or self.updating_suspended:
            return self
        if recurse:
            for child in self.submobjects:
                child.update(dt, recurse, frame_rate)
        updaters = self.updaters
        index = 0
        while index < len(updaters):
            updater = updaters[index]
            updater(self, dt, frame_rate)
            if index < len(updaters) and updaters[index] is updater:
                index += 1
        return self

    def suspend_updating(self, recurse=True):
        for mob in self.get_family(recurse):
            mob.updating_suspended = True
        return self

    def resume_updating(self, recurse=True, call_updater=True):
        self.updating_suspended = False
        if recurse:
            for child in self.submobjects:
                child.resume_updating(recurse=True, call_updater=False)
        pending = list(self.parents)
        seen = {}
        while pending:
            parent = pending.pop()
            if parent in seen:
                continue
            seen[parent] = None
            parent.updating_suspended = False
            pending.extend(parent.parents)
        if call_updater:
            self.update(0)
        return self

    def replicate(self, count):
        return self.get_group_class()(*(self.copy() for _ in range(operator.index(count))))

    @property
    def animate(self):
        from janim.animation.transform import _AnimationBuilder

        return _AnimationBuilder(self)

    @property
    def always(self):
        from .trackers import _UpdaterBuilder

        return _UpdaterBuilder(self)

    @property
    def f_always(self):
        from .trackers import _UpdaterBuilder

        return _UpdaterBuilder(self, functional=True)


class VMobject(PathMixin, Mobject):
    """An interleaved quadratic path: anchor, handle, anchor, ... ."""

    is_interpolable = True
    _factory_fill_color = "#888888"
    _factory_stroke_color = "#DDDDDD"
    _factory_fill_opacity = 0.0
    _factory_stroke_width = 4.0

    def __getitem__(self, value):
        if isinstance(value, str):
            def select():
                parts = self.find_by_key(value)
                if not parts:
                    available = ", ".join(self.get_all_keys()) or "(none)"
                    hint = "; use isolate or t2c when constructing a formula" if getattr(self, "_labelled_text", False) else ""
                    if getattr(self, "_plain_text", False):
                        hint = "; Text keys are single characters; use t2c/t2w for substrings or select glyphs by index"
                    raise KeyError(f"no child carries {value!r}; available keys: {available}{hint}")
                return VGroup(*parts)

            return self._memoized_group(("key", value), select)
        return super().__getitem__(value)

    def get_group_class(self):
        return VGroup

    def get_parts_by_tex(self, selector):
        if not isinstance(selector, str):
            raise TypeError("a text selector must be a string")

        def construct():
            whole = self[selector]
            runs = None if self.key_runs is None else self.key_runs.get(selector)
            if runs is None:
                return VGroup(whole)
            return VGroup(*(VGroup(*(self.submobjects[index] for index in run)) for run in runs))

        return self._memoized_group(("parts", selector), construct)

    def get_part_by_tex(self, selector, index=0):
        parts = self.get_parts_by_tex(selector)
        if not 0 <= index < len(parts):
            raise IndexError(
                f"{selector!r} occurs {len(parts)} times; requested index {index}; indices are zero-based, 0 through {len(parts) - 1}",
            )
        return parts[index]

    select_parts = get_parts_by_tex
    select_part = get_part_by_tex


class Group(Mobject):
    is_interpolable = True
    _transform_bbox = False

    def __init__(self, *mobjects, **kwargs):
        if len(mobjects) == 1 and not isinstance(mobjects[0], Mobject):
            mobjects = tuple(mobjects[0])
        super().__init__(**kwargs)
        self.add(*mobjects)

    def __add__(self, other):
        return self.add(other)

    def length_over_dim(self, dim):
        return float(super().length_over_dim(dim))

    _PER_CHILD_KINDS = ("image", "surface", "textured_surface", "dots")

    def _needs_per_child_verbs(self):
        """Group verbs call each child with the group's pivot: an image
        or a mesh child then takes its own f64 verb instead of the f32 family walk."""
        return any(getattr(mob, "render_kind", None) in self._PER_CHILD_KINDS for mob in self.get_family())

    def scale(self, factor, min_scale_factor=1e-8, about_point=None, about_edge=(0, 0, 0)):
        if not self._needs_per_child_verbs():
            return super().scale(factor, min_scale_factor, about_point, about_edge)
        pivot = self._pivot(about_point, about_edge)
        for child in self.submobjects:
            child.scale(factor, min_scale_factor=min_scale_factor, about_point=pivot)
        return self

    def rotate(self, angle, axis=(0, 0, 1), about_point=None, about_edge=(0, 0, 0)):
        if not self._needs_per_child_verbs():
            return super().rotate(angle, axis, about_point, about_edge)
        pivot = self._pivot(about_point, about_edge)
        surfaces = self._plain_surfaces() if pivot is not None else None
        if not surfaces:
            for child in self.submobjects:
                child.rotate(angle, axis=axis, about_point=pivot)
            return self
        # every plain mesh of the family turns in one pass (same bits: Surface.rotate_stacked),
        # the other members exactly as the per-child walk above would turn them
        surfaces[0].rotate_stacked(surfaces, angle, axis, pivot)
        self._rotate_rest(self, angle, axis, pivot)
        return self

    def _plain_surfaces(self):
        """The meshes of the family a stacked rotate may take: every Group on the way turns with
        Group.rotate and every mesh with Surface.rotate; an override anywhere → None (the
        per-child walk honours it)."""
        found = []
        pending = [self]
        while pending:
            mob = pending.pop()
            if isinstance(mob, Group):
                if type(mob).rotate is not Group.rotate:
                    return None
                pending.extend(mob.submobjects)
            elif getattr(mob, "render_kind", None) == "surface":
                if type(mob).rotate is not getattr(type(mob), "_plain_rotate", None):
                    return None
                found.append(mob)
        return found

    def _rotate_rest(self, group, angle, axis, pivot):
        """The per-child walk of `rotate` with the plain meshes already turned: a nested Group
        with per-child kinds walks its children with the same pivot (as its own `rotate` would),
        anything else turns as before."""
        for child in group.submobjects:
            if getattr(child, "render_kind", None) == "surface":
                continue
            if isinstance(child, Group) and child._needs_per_child_verbs():
                self._rotate_rest(child, angle, axis, pivot)
            else:
                child.rotate(angle, axis=axis, about_point=pivot)

    def stretch(self, factor, dim, about_point=None, about_edge=(0, 0, 0)):
        if not self._needs_per_child_verbs():
            return super().stretch(factor, dim, about_point, about_edge)
        pivot = self._pivot(about_point, about_edge)
        for child in self.submobjects:
            child.stretch(factor, dim, about_point=pivot)
        return self

    def align_data(self, other, *, padding="invisible"):
        if isinstance(other, Group) and len(self) != len(other) and (not len(self) or not len(other)):
            raise ValueError("cannot align an empty Group with a nonempty Group; use VGroup for point padding")
        return super().align_data(other, padding=padding)

    def interpolate(self, first, second, alpha, **kwargs):
        for child, start, target in zip(self.submobjects, first.submobjects, second.submobjects):
            child.interpolate(start, target, alpha, **kwargs)
        return self


class VGroup(VMobject):
    def __init__(self, *mobjects, **kwargs):
        if len(mobjects) == 1 and not isinstance(mobjects[0], Mobject):
            mobjects = tuple(mobjects[0])
        super().__init__(**kwargs)
        self.add(*mobjects)
        if self.submobjects:
            self.uniforms.update(self.submobjects[0].uniforms)
            self.joint_type = self.submobjects[0].joint_type

    def __add__(self, other):
        return self.add(other)


def _resize_with_interpolation(rows, count):
    if len(rows) == count:
        return rows.copy()
    if len(rows) == 1 or count == 1 or np.all(rows == rows[0]):
        return np.repeat(rows[:1], count, axis=0)
    positions = np.arange(count, dtype=np.float64) * (len(rows) - 1) / (count - 1)
    left = np.floor(positions).astype(np.intp)
    right = np.ceil(positions).astype(np.intp)
    alpha = positions - left
    if rows.ndim == 2:
        alpha = alpha[:, None]
    return ((1 - alpha) * rows[left] + alpha * rows[right]).astype(np.float32)
