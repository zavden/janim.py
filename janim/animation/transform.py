"""Transforms over the interpolation contract and ManimGL's eager builder."""

import math

import numpy as np

from janim.core.algebra import norm
from janim.core.alignment import is_interpolable
from janim.core.mobject import Group, Mobject, VMobject
from .animation import Animation, animation_copy, families


def forwards_to_children(mob):
    """A `Group` only forwards `interpolate` to its children, and every child
    already has its own entry (with its own sub-alpha) in the families: the
    forwarded write is repeated by the child's entry and only the last one
    survives, so the group's entry is skipped, as ManimGL writes each member
    once. A group with a child outside the contract keeps the old path."""
    return type(mob).interpolate is Group.interpolate and all(is_interpolable(child) for child in mob.submobjects)


class Transform(Animation):
    def __init__(
        self,
        mobject,
        target_mobject=None,
        *,
        path_arc=0.0,
        path_arc_axis=(0, 0, 1),
        path_func=None,
        padding="invisible",
        replace_mobject_with_target_in_scene=False,
        **kwargs,
    ):
        if padding not in ("invisible", "visible"):
            raise ValueError("padding must be invisible or visible")
        if target_mobject is not None and not isinstance(target_mobject, Mobject):
            raise TypeError("Transform target must be a Mobject")
        super().__init__(mobject, **kwargs)
        self.target_mobject = target_mobject
        self.target_copy = None
        self.path_arc = float(path_arc)
        self.path_arc_axis = np.array(path_arc_axis, dtype=np.float32)
        if self.path_arc_axis.shape != (3,):
            raise ValueError("path_arc_axis needs three components")
        self.path_func = path_func
        self.padding = padding
        self.replace_mobject_with_target_in_scene = bool(replace_mobject_with_target_in_scene)
        self.animatable = []
        self.mesh_batch = None

    def create_target(self):
        if self.target_mobject is None:
            raise ValueError("Transform needs a target or an overridden create_target method")
        return animation_copy(self.target_mobject)

    def create_starting_state(self):
        return None

    def begin(self):
        if not is_interpolable(self.mobject):
            raise TypeError(f"{type(self.mobject).__name__} does not implement the interpolation contract")
        self.target_copy = self.create_target()
        if not isinstance(self.target_copy, Mobject):
            raise TypeError("Transform.create_target must return a Mobject")
        start = self.create_starting_state()
        if start is not None:
            self.mobject.become(start)
        self.mobject.align_data(self.target_copy, padding=self.padding)
        self.starting_mobject = animation_copy(self.mobject)
        self.families = families(self.mobject, self.starting_mobject, self.target_copy)
        if not self.families or self.families[0][0] is not self.mobject:
            self.families.insert(0, (self.mobject, self.starting_mobject, self.target_copy))
        self.animatable = [
            all(is_interpolable(mob) for mob in pair) and not forwards_to_children(pair[0])
            for pair in self.families
        ]
        self.mesh_batch = self._mesh_batch()
        self._begin_updates()
        self.interpolate(0.0)
        return self

    def _mesh_batch(self):
        """The families that are plain meshes of one resolution, when every member shares the
        alpha (no lag, no path): they lerp stacked, with the bits of one `interpolate` each."""
        if self.lag_ratio != 0 or self.path_func is not None:
            return None
        batch = []
        for index, (triple, allowed) in enumerate(zip(self.families, self.animatable)):
            mob, start, target = triple
            plain = getattr(type(mob), "_plain_interpolate", None)
            if (
                allowed
                and plain is not None
                and type(mob).interpolate is plain
                and type(start).interpolate is plain
                and type(target).interpolate is plain
                and len(mob.points) == len(start.points) == len(target.points)
            ):
                batch.append((index, triple))
        return batch or None

    def interpolate_mobject(self, alpha):
        count = len(self.families)
        batch = self.mesh_batch
        if batch:
            skip = dict.fromkeys(index for index, _ in batch)      # no sets under janim/
            batch[0][1][0].interpolate_stacked([triple for _, triple in batch], self.get_sub_alpha(alpha, batch[0][0], count))
        else:
            skip = ()
        for index, (pair, allowed) in enumerate(zip(self.families, self.animatable)):
            if allowed and index not in skip:
                self.interpolate_submobject(*pair, self.get_sub_alpha(alpha, index, count))

    def interpolate_submobject(self, submobject, starting_submobject, target_copy, alpha):
        if self.path_func is None:
            submobject.interpolate(starting_submobject, target_copy, alpha)
        else:
            submobject.interpolate(starting_submobject, target_copy, alpha, path_func=self.path_func)
        self._apply_path_arc(submobject, starting_submobject, target_copy, alpha)

    def _apply_path_arc(self, mob, start, end, alpha):
        if self.path_func is not None or abs(self.path_arc) < 0.01 or alpha in (0, 1):
            return
        if not all(isinstance(item, VMobject) for item in (mob, start, end)):
            return
        axis = self.path_arc_axis / np.float32(norm(self.path_arc_axis))
        midpoint = (end.points - start.points) / np.float32(2)
        center = start.points + midpoint + (np.cross(axis, midpoint).astype(np.float64) / math.tan(self.path_arc / 2)).astype(np.float32)
        relative = start.points - center
        cross = np.cross(axis, relative)
        cosine, sine = math.cos(alpha * self.path_arc), math.sin(alpha * self.path_arc)
        mob.points[:] = (center.astype(np.float64) + cosine * relative.astype(np.float64)) + sine * cross.astype(np.float64)
        mob.note_changed_data()

    def clean_up_from_scene(self, stage):
        super().clean_up_from_scene(stage)
        if self.replace_mobject_with_target_in_scene and self.target_mobject is not None:
            stage.replace(self.mobject, self.target_mobject)
        return self


class _FunctionalTransform(Transform):
    def __init__(self, mobject, target_factory, starting_factory=None, **kwargs):
        super().__init__(mobject, **kwargs)
        self.target_factory = target_factory
        self.starting_factory = starting_factory

    def create_target(self):
        return self.target_factory()

    def create_starting_state(self):
        return None if self.starting_factory is None else self.starting_factory()


class ReplacementTransform(Transform):
    def __init__(self, mobject, target_mobject, **kwargs):
        super().__init__(
            mobject,
            target_mobject,
            **{"replace_mobject_with_target_in_scene": True, **kwargs},
        )


class TransformFromCopy(ReplacementTransform):
    def __init__(self, mobject, target_mobject, **kwargs):
        super().__init__(animation_copy(mobject), target_mobject, **kwargs)


class MoveToTarget(Transform):
    def __init__(self, mobject, **kwargs):
        if mobject.target is None:
            raise ValueError("MoveToTarget needs a target; call generate_target first")
        super().__init__(mobject, mobject.target, **kwargs)


class Restore(Transform):
    def __init__(self, mobject, **kwargs):
        if mobject.saved_state is None:
            raise ValueError("Restore needs a saved state; call save_state first")
        super().__init__(mobject, mobject.saved_state, **kwargs)


class _MethodAnimation(MoveToTarget):
    def __init__(self, mobject, methods, **kwargs):
        self.methods = list(methods)
        super().__init__(mobject, **kwargs)


class _AnimationBuilder:
    """Each access replaces mobject.target; calls mutate that target eagerly."""

    def __init__(self, mobject):
        self.mobject = mobject
        mobject.generate_target()
        # Targets obey the same internal cold-box contract as animation_copy.
        mobject.target.refresh_bounding_box(recurse_down=True, recurse_up=False)
        self.methods = []
        self.anim_args = {}
        self.can_pass_args = True

    def __getattr__(self, name):
        method = getattr(self.mobject.target, name)
        if not callable(method):
            raise TypeError(f"animate.{name} must be a method")
        self.methods.append(method)

        def update_target(*args, **kwargs):
            method(*args, **kwargs)
            return self

        return update_target

    def __call__(self, **kwargs):
        return self.set_anim_args(**kwargs)

    def set_anim_args(self, **kwargs):
        if not self.can_pass_args:
            raise ValueError("animation arguments can only be passed once")
        self.anim_args = dict(kwargs)
        self.can_pass_args = False
        return self

    def build(self):
        return _MethodAnimation(self.mobject, self.methods, **self.anim_args)
