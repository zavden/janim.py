"""ManimGL shallow metadata copies and saved state (mobject.py:665-745)."""

import copy

import numpy as np


class StateMixin:
    def copy(self, deep=False):
        if deep:
            return self.deepcopy()
        from .mobject import Mobject

        result = copy.copy(self)
        result.parents = []
        result.target = None
        result.saved_state = None
        result.draw_family = None
        result.keys = list(self.keys)
        result.key_runs = copy.deepcopy(self.key_runs)
        result._key_group_cache = {}
        result.uniforms = {
            key: value.copy() if isinstance(value, np.ndarray) else value
            for key, value in self.uniforms.items()
        }
        result.submobjects = [child.copy() for child in self.submobjects]
        for child in result.submobjects:
            child.parents = [result]
        result.family = [result]
        for child in result.submobjects:
            result.family.extend(child.get_family())
        result.updaters = list(self.updaters)
        result._data_has_changed = True
        result.shader_wrapper = None
        family = self.get_family()
        first_positions = {}
        for index, member in enumerate(family):
            first_positions.setdefault(member, index)
        for name, value in self.__dict__.items():
            if isinstance(value, Mobject) and value is not self:
                if value in first_positions:
                    setattr(result, name, result.family[first_positions[value]])
            elif isinstance(value, np.ndarray) and name not in getattr(self, "_shared_array_names", ()):
                setattr(result, name, value.copy())
        return result

    def deepcopy(self):
        # ManimGL stashes only the receiver's external pointers. Always put
        # them back, including when a user's deepcopy hook raises.
        saved = {name: getattr(self, name) for name in ("parents", "target", "saved_state")}
        try:
            self.parents = []
            self.target = self.saved_state = None
            return copy.deepcopy(self)
        finally:
            self.__dict__.update(saved)

    def save_state(self, use_deepcopy=False):
        self.saved_state = self.copy(deep=use_deepcopy)
        self.saved_state.target = self.target
        return self

    def restore(self):
        if self.saved_state is None:
            raise ValueError("cannot restore without a saved state; call save_state first")
        return self.become(self.saved_state)

    def generate_target(self, use_deepcopy=False):
        self.target = self.copy(deep=use_deepcopy)
        self.target.saved_state = self.saved_state
        return self.target

    def invisible_copy(self):
        return self.copy().set_opacity(0)
