"""Keyed and Hungarian shape matching."""

import numpy as np

from janim.core.algebra import norm
from janim.core._reductions import julia_cumsum, julia_sum
from janim.core.mobject import VGroup, VMobject
from janim.core.rates import smooth
from .animation import Animation
from .composition import AnimationGroup
from .fading import FadeIn, FadeOut, FadeTransform
from .transform import Transform


def glyph_children(mobject):
    return [
        child for child in mobject.get_family()[1:]
        if isinstance(child, VMobject) and child.has_points()
    ]


def _parts_by_key(mobject):
    parts = {}
    for child in glyph_children(mobject):
        for key in child.get_keys():
            if not key.startswith("_via"):
                parts.setdefault(key, []).append(child)
    return parts


def normalized_outline(mobject):
    center = mobject.get_center().astype(np.float64)
    height = max(float(mobject.get_height()), 1e-9)
    return (mobject.points.astype(np.float64) - center) / height


def _resample(points, count=64):
    anchors = points[::2]
    if len(anchors) < 2:
        return np.repeat((anchors[0] if len(anchors) else np.zeros(3))[None], count, axis=0)
    lengths = norm(anchors[1:] - anchors[:-1])
    cumulative = np.concatenate(([0.0], julia_cumsum(lengths)))
    total = julia_sum(lengths)
    if not total > 0:
        return np.repeat(anchors[:1], count, axis=0)
    result = np.empty((count, 3), dtype=np.float64)
    segment = 0
    for index in range(count):
        distance = total * index / (count - 1)
        while segment < len(lengths) - 1 and cumulative[segment + 1] < distance:
            segment += 1
        alpha = (distance - cumulative[segment]) / lengths[segment] if lengths[segment] > 0 else 0.0
        result[index] = anchors[segment] + min(max(alpha, 0), 1) * (anchors[segment + 1] - anchors[segment])
    return result


def shape_distance(first, second):
    first_points, second_points = normalized_outline(first), normalized_outline(second)
    if not len(first_points) or not len(second_points):
        return float("inf")
    if len(first_points) != len(second_points):
        first_points, second_points = _resample(first_points), _resample(second_points)
    width = max(float(first.get_width()) / max(float(first.get_height()), 1e-9), 1e-9)
    return float(np.max(norm(first_points - second_points))) / width


def hungarian(cost):
    """Return zero-based assigned columns, or -1 for an unmatched row."""
    cost = np.asarray(cost, dtype=np.float64)
    if cost.ndim != 2:
        raise ValueError("the assignment cost must be a matrix")
    rows, columns = cost.shape
    if rows > columns:
        transposed = hungarian(cost.T)
        assignment = [-1] * rows
        for column, row in enumerate(transposed):
            if row >= 0:
                assignment[row] = column
        return assignment
    if not np.isfinite(cost).all():
        raise ValueError("assignment costs must be finite")
    u = np.zeros(rows + 1, dtype=np.float64)
    v = np.zeros(columns + 1, dtype=np.float64)
    matched = np.zeros(columns + 1, dtype=np.int64)
    way = np.zeros(columns + 1, dtype=np.int64)
    for row in range(1, rows + 1):
        matched[0] = row
        current = 0
        minimum = np.full(columns + 1, np.inf)
        used = np.zeros(columns + 1, dtype=bool)
        while True:
            used[current] = True
            active = matched[current]
            delta = float("inf")
            following = 0
            for column in range(1, columns + 1):
                if used[column]:
                    continue
                value = cost[active - 1, column - 1] - u[active] - v[column]
                if value < minimum[column]:
                    minimum[column] = value
                    way[column] = current
                if minimum[column] < delta:
                    delta = minimum[column]
                    following = column
            for column in range(columns + 1):
                if used[column]:
                    u[matched[column]] += delta
                    v[column] -= delta
                else:
                    minimum[column] -= delta
            current = following
            if matched[current] == 0:
                break
        while True:
            previous = way[current]
            matched[current] = matched[previous]
            current = previous
            if current == 0:
                break
    assignment = [-1] * rows
    for column in range(1, columns + 1):
        if matched[column] > 0:
            assignment[matched[column] - 1] = column - 1
    return assignment


def match_by_shape(sources, targets, threshold):
    if not sources or not targets:
        return []
    costs = np.array([[shape_distance(source, target) for target in targets] for source in sources])
    return [(row, column) for row, column in enumerate(
        hungarian(costs),
    ) if column >= 0 and costs[row, column] <= threshold]


class TransformMatchingTex(Animation):
    def __init__(
        self,
        source,
        target,
        key_map=None,
        match_shapes=False,
        threshold=0.05,
        rate_func=smooth,
        path_arc=0.0,
        path_arc_axis=(0, 0, 1),
        **kwargs,
    ):
        if not isinstance(source, VMobject) or not isinstance(target, VMobject):
            raise TypeError("matching requires vector mobjects")
        motion = dict(rate_func=rate_func, path_arc=path_arc, path_arc_axis=path_arc_axis)
        sources, targets = _parts_by_key(source), _parts_by_key(target)
        claimed_source, claimed_target = {}, {}
        animations = []
        for key in sorted(sources, key=lambda value: (-len(value), value)):
            destination = key if key_map is None else str(key_map.get(key, key))
            if destination not in targets:
                continue
            source_parts = [part for part in sources[key] if part not in claimed_source]
            target_parts = [part for part in targets[destination] if part not in claimed_target]
            if not source_parts or not target_parts:
                continue
            claimed_source.update(dict.fromkeys(source_parts))
            claimed_target.update(dict.fromkeys(target_parts))
            animations.append(
                Transform(
                    VGroup(*(part.copy() for part in source_parts)),
                    VGroup(*(part.copy() for part in target_parts)),
                    **motion,
                ),
            )
        if match_shapes:
            source_parts = [part for part in glyph_children(source) if part not in claimed_source]
            target_parts = [part for part in glyph_children(target) if part not in claimed_target]
            for first, last in match_by_shape(source_parts, target_parts, threshold):
                claimed_source[source_parts[first]] = None
                claimed_target[target_parts[last]] = None
                animations.append(Transform(source_parts[first].copy(), target_parts[last].copy(), **motion))
        self._initialize(
            source,
            target,
            animations,
            [part for part in glyph_children(source) if part not in claimed_source],
            [part for part in glyph_children(target) if part not in claimed_target],
            kwargs,
            rate_func,
        )

    def _initialize(self, source, target, animations, source_orphans, target_orphans, kwargs, rate_func):
        if source_orphans:
            animations.append(FadeOut(VGroup(*(part.copy() for part in source_orphans)), rate_func=rate_func))
        if target_orphans:
            animations.append(FadeIn(VGroup(*(part.copy() for part in target_orphans)), rate_func=rate_func))
        if not animations:
            animations.append(FadeTransform(source.copy(), target, rate_func=rate_func))
        self.group = AnimationGroup(*animations, **kwargs)
        self.to_remove, self.to_add = source, target
        self.hidden = []
        options = {"run_time": self.group.run_time, "lag_ratio": self.group.lag_ratio, **kwargs}
        super().__init__(self.group.mobject, **options)

    def begin(self):
        if not self.hidden:
            self.hidden = [
                (
                    child,
                    child.fill_rgba.copy(),
                    child.stroke_rgba.copy(),
                    child.default_fill_rgba.copy(),
                    child.default_stroke_rgba.copy(),
                )
                for child in dict.fromkeys(self.to_remove.get_family())
                if isinstance(child, VMobject)
            ]
        self.to_remove.set_fill(opacity=0).set_stroke(opacity=0)
        self.group.begin()
        return self

    def interpolate(self, alpha):
        self.group.interpolate(alpha)
        return self

    def finish(self):
        self.group.finish()
        return self

    def clean_up_from_scene(self, stage):
        stage.remove(self.mobject)
        stage.replace(self.to_remove, self.to_add)
        for child, fill, stroke, default_fill, default_stroke in self.hidden:
            child.fill_rgba[:] = fill if len(child.fill_rgba) == len(fill) else default_fill
            child.stroke_rgba[:] = stroke if len(child.stroke_rgba) == len(stroke) else default_stroke
            child.default_fill_rgba = default_fill.copy()
            child.default_stroke_rgba = default_stroke.copy()
        self.hidden.clear()
        return self


class TransformMatchingShapes(TransformMatchingTex):
    def __init__(
        self,
        source,
        target,
        threshold=0.05,
        rate_func=smooth,
        path_arc=0.0,
        path_arc_axis=(0, 0, 1),
        **kwargs,
    ):
        if not isinstance(source, VMobject) or not isinstance(target, VMobject):
            raise TypeError("matching requires vector mobjects")
        def parts(mobject):
            return [mobject] if not mobject.submobjects and mobject.has_points() else glyph_children(mobject)

        sources, targets = parts(source), parts(target)
        pairs = match_by_shape(sources, targets, threshold)
        source_indices = dict.fromkeys(first for first, _ in pairs)
        target_indices = dict.fromkeys(last for _, last in pairs)
        self._initialize(
            source,
            target,
            [
                Transform(
                    sources[first].copy(),
                    targets[last].copy(),
                    rate_func=rate_func,
                    path_arc=path_arc,
                    path_arc_axis=path_arc_axis,
                )
                for first, last in pairs
            ],
            [part for index, part in enumerate(sources) if index not in source_indices],
            [part for index, part in enumerate(targets) if index not in target_indices],
            kwargs,
            rate_func,
        )


TransformMatchingStrings = TransformMatchingTex
