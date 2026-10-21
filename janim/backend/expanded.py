"""CPU render preparation."""

import math

import numpy as np

from janim.core.algebra import _normalize, apply_matrix_rows, norm, rotation_matrix_unchecked
from janim.core.mobject import Mobject
from janim.core._atan import atan2


ARRAY_NAMES = (
    "point", "fill_rgba", "stroke_rgba", "stroke_width",
    "joint_angle", "base_normal", "grad_uv", "grad_uv_base",
)
ELEMENT_BYTES = (12, 16, 16, 4, 4, 12, 8, 8)


class RenderMesh(Mobject):
    """Internal source-array bridge for indexed meshes, rasters and point clouds.

    Constructors can supply these arrays without changing the draw protocol. This type does not generate geometry.
    """

    def __init__(self, kind, **arrays):
        if kind not in ("dots", "surface", "image", "textured_surface"):
            raise ValueError(f"unknown render primitive: {kind}")
        super().__init__()
        self.render_kind = kind
        for name, array in arrays.items():
            dtype = np.uint8 if name == "pixels" else np.int32 if name == "indices" else np.float32
            setattr(self, name, np.ascontiguousarray(array, dtype=dtype))
        self.opacity = 1.0
        self.glow_factor = 0.0
        self.anti_alias_width = 2.0


_LEAD = np.zeros((1, 3), dtype=np.float64)
_NEXT_AXIS = (1, 2, 0)
_LAST_AXIS = (2, 0, 1)


def vector_area(mobject):
    """The shoelace sum over every subpath, in one pass over the anchors.

    The anchors of all the subpaths are `points[::2]` in order (the degenerate
    handle that separates two subpaths sits at an odd index), and the only
    thing that distinguishes a subpath is that its last anchor pairs with its
    own first one. One gather builds that pairing, the three axes share the
    elementwise products, and a single sequential accumulation from zero is
    the same as summing subpath after subpath: it carries the running total
    across the boundary exactly as a per-subpath loop would."""
    points = mobject.points
    if not len(points):
        return np.zeros(3, dtype=np.float64)
    anchors = points[::2]
    following = np.arange(1, len(anchors) + 1)
    ends = mobject.get_subpath_end_indices()
    if len(ends) == 1:
        following[-1] = 0
    else:
        starts = np.concatenate(([0], ends[:-1] + 2))
        following[ends // 2] = starts // 2
    following = anchors[following]
    sums = (anchors + following).astype(np.float64)
    differences = following - anchors
    values = (0.5 * sums[:, _NEXT_AXIS]) * differences[:, _LAST_AXIS]
    return np.add.accumulate(np.concatenate((_LEAD, values)), axis=0)[-1]


def unit_normal_of(mobject):
    if len(mobject.points) < 3:
        return np.array((0, 0, 1), dtype=np.float32)
    area = vector_area(mobject)
    length = norm(area)
    if length > 0:
        return (area / length).astype(np.float32)
    points = mobject.points
    first = _normalize((points[1] - points[0]).astype(np.float64))
    second = _normalize((points[2] - points[1]).astype(np.float64))
    cross = np.cross(first, second)
    length = norm(cross)
    if length < 1e-6:
        return np.array((0, 0, 1), dtype=np.float32)
    with np.errstate(invalid="ignore", divide="ignore"):
        return (cross / length).astype(np.float32)


def joint_angles_of(mobject, normal):
    """The joint angle at every point."""
    n = len(mobject.points)
    if n < 3:
        return np.zeros(n, dtype=np.float32)
    y, x = joint_vectors_of(mobject, normal)
    return joint_angles_from(atan2(y, x), n)


def joint_angles_from(stacked, n):
    """The angles out of the stacked `atan2` of (outgoing, incoming): their
    difference wrapped to (-pi, pi], in float32. Elementwise, so a slice of a
    larger `atan2` over several members gives the same bits as its own call."""
    angles = stacked[:n] - stacked[n:]
    angles[angles < -math.pi] += math.tau
    angles[angles > math.pi] -= math.tau
    return angles.astype(np.float32)


def batched_joint_angles(entries):
    """One `atan2` for every member of the frame whose stroke reads its joints.

    `entries` holds `(y, x, n)` per member, the two stacked vectors of
    `joint_vectors_of` and its point count; the result is one float32 angle
    array per entry, bit for bit what `joint_angles_of` gives member by
    member (the kernel is elementwise). A thousand circles cost one call
    instead of a thousand."""
    if not entries:
        return []
    stacked = atan2(np.concatenate([y for y, _, _ in entries]), np.concatenate([x for _, x, _ in entries]))
    result = []
    start = 0
    for _, _, n in entries:
        result.append(joint_angles_from(stacked[start:start + 2 * n], n))
        start += 2 * n
    return result


def joint_vectors_of(mobject, normal):
    """The (y, x) components, stacked outgoing then incoming, whose `atan2`
    difference is the joint angle; the per-member half of `joint_angles_of`
    (the rotation into the +z plane and the subpath closure fix-ups)."""
    n = len(mobject.points)
    points = mobject.points.astype(np.float64)
    out = np.array((0, 0, 1), dtype=np.float32)
    # Float32 approximate comparison: tolerance sqrt(eps(Float32)).
    approximate = norm(normal - out) <= math.sqrt(np.finfo(np.float32).eps) * max(norm(normal), 1)
    if not approximate:
        axis = np.array((-normal[1], normal[0], 0), dtype=np.float64)
        if norm(axis) < 1e-8:
            rotation = np.diag((1.0, -1.0, -1.0))
        else:
            angle = math.acos(float(np.clip(normal[2], -1, 1)))
            rotation = rotation_matrix_unchecked(angle, axis)
        points = apply_matrix_rows(points, rotation.T)
    incoming = np.zeros_like(points)
    outgoing = np.zeros_like(points)
    count = (n - 1) // 2
    first = points[1:2 * count:2] - points[:2 * count:2]
    second = points[2:2 * count + 1:2] - points[1:2 * count:2]
    incoming[1:2 * count:2] = first
    incoming[2:2 * count + 1:2] = second
    outgoing[:2 * count:2] = first
    outgoing[1:2 * count:2] = second
    start = 0
    for end in mobject.get_subpath_end_indices() if len(points) else ():
        if start != end:
            if np.array_equal(mobject.points[start], mobject.points[end]):
                incoming[start] = outgoing[end - 1]
                outgoing[end] = incoming[start + 1]
            else:
                incoming[start] = outgoing[start]
                outgoing[end] = incoming[end]
        start = end + 2
    # one call over both halves: the kernel is element by element, so the
    # stacked result is the two results side by side at half the overhead
    return np.concatenate((outgoing[:, 1], incoming[:, 1])), np.concatenate((outgoing[:, 0], incoming[:, 0]))


_CURVE_INDICES = {}


def curve_indices(count):
    """The vertex gather `(0,1,2, 2,3,4, …)` of `count` curves and its odd mask,
    built once per curve count: every member of a frame with the same number
    of curves shares them (read-only, no caller writes)."""
    cached = _CURVE_INDICES.get(count)
    if cached is None:
        indices = (2 * np.arange(count)[:, None] + np.arange(3)).reshape(-1)
        odd = indices % 2 != 0
        indices.flags.writeable = False
        odd.flags.writeable = False
        cached = _CURVE_INDICES[count] = (indices, odd)
    return cached


def stroke_collapses(mobject):
    """The two guards of `stroke.wgsl` (every width of the curve zero, or every
    stroke alpha zero) hold for every curve of the member: its stroke returns
    before reading a joint angle, so the angles need not exist. `Dot`, `Arrow`
    and the glyphs of `Tex` are born this way."""
    return not np.any(mobject.stroke_width != 0) or not np.any(mobject.stroke_rgba[:, 3] != 0)


DEFER = "defer"


def expanded_data(mobject, *, grad=None, joints=True):
    """The per-vertex arrays of a VMobject.

    With `joints=False` the joint angles are zeros: the draw cache asks for
    that when `stroke_collapses`, and nothing else reads the slot. With
    `joints=DEFER` the `joint_angle` slot is None and the dict carries
    `joint_vectors` (the stacked (y, x) of `joint_vectors_of`) and `indices`:
    the draw cache collects them over the whole frame and resolves them with
    one `atan2` (`batched_joint_angles`). The default computes them here."""
    points = mobject.points
    indices, odd = curve_indices(mobject.get_num_curves())
    normal = unit_normal_of(mobject)
    vectors = None
    if joints is DEFER and len(points) >= 3:
        vectors = joint_vectors_of(mobject, normal)
        joints = None
    elif joints:
        joints = joint_angles_of(mobject, normal)
    else:
        joints = np.zeros(len(points), dtype=np.float32)
    bases = np.empty_like(points)
    uv_bases = None if grad is None else np.empty_like(grad.uv)
    start = 0
    for end in mobject.get_subpath_end_indices() if len(points) else ():
        bases[start:end + 2] = points[start]
        if grad is not None:
            uv_bases[start:end + 2] = grad.uv[start]
        start = end + 2
    base_normal = bases[indices]
    base_normal[odd] = normal
    return {
        "point": points[indices],
        "fill_rgba": mobject.fill_rgba[indices],
        "stroke_rgba": mobject.stroke_rgba[indices],
        "stroke_width": mobject.stroke_width[indices],
        "joint_angle": None if joints is None else joints[indices],
        "base_normal": base_normal,
        "grad_uv": None if grad is None else grad.uv[indices],
        "grad_uv_base": None if grad is None else uv_bases[indices],
        "n": len(indices),
        "joint_vectors": vectors,
        "indices": indices,
    }


def batch_key(mobject):
    return (
        mobject.joint_type,
        mobject.uniforms["is_fixed_in_frame"],
        tuple(mobject.uniforms["shading"]),
        mobject.depth_test,
    )


def max_sqrt_area(points):
    """The largest sqrt of a curve triangle's area, as the step budget reads it.

    `np.cross` on (n, 3) f32 rows is `a1*b2 - a2*b1` and its two rotations,
    each product and difference a float32 ufunc call; the same nine calls are
    written out here on the columns, without the axis bookkeeping of the
    library function, and `norm` is unrolled on the three components exactly
    as `algebra.norm` sums them: `(c0² + c1²) + c2²`."""
    count = len(points) // 3
    if count == 0:
        return np.float32(0)
    triples = points[:3 * count].reshape(-1, 3, 3)
    first = triples[:, 1] - triples[:, 0]
    second = triples[:, 2] - triples[:, 0]
    a0, a1, a2 = first[:, 0], first[:, 1], first[:, 2]
    b0, b1, b2 = second[:, 0], second[:, 1], second[:, 2]
    c0 = a1 * b2 - a2 * b1
    c1 = a2 * b0 - a0 * b2
    c2 = a0 * b1 - a1 * b0
    return np.max(np.sqrt(np.float32(0.5) * np.sqrt((c0 * c0 + c1 * c1) + c2 * c2)))


def step_budget(areas, frame_unit):
    largest = np.max(areas) if len(areas) else np.float32(0)
    count = round(float(np.float32(100) * largest / np.float32(frame_unit)))
    return min(2 + count, 32) + 1
