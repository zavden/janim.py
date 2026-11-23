"""The end of a partial stroke is straight, and Create can move at a steady speed.

Run it directly (`python tests/test_partial_tips.py`) or with pytest.

`pointwise_become_partial` keeps the point count, as ManimGL's does: the curves
past the visible end collapse onto that end (and, with a > 0, the curves before
the start onto the start). The joint angle at the visible end then met a vector
of length zero, atan2(0, 0) = 0 made it minus the incoming direction (-90° for a
stroke going up), and the stroke shader grew a corner there: a spike at the tip
of every thick stroke while Create, Write or a dashed line drew it
(JANIM-BUG-CREATE-PUNTA.md, 2026-11-22). A side of zero length now takes the
direction of the other side, so there is no turn where a segment has no length.

`ShowCreation(by_length=True)` spends the time on each path by arc length, not
curve by curve.

Every test but the last runs without the GPU; the last renders two mobjects
and skips when no device can be opened.
"""
import math
import sys

import numpy as np

from janim import Annulus, Circle, Sector, ShowCreation, Square, Star, TAU, Uncreate, VMobject, WHITE, linear, render_frame
from janim.backend import expanded
from janim.backend.expanded import batched_joint_angles, joint_angles_of, joint_vectors_of
from janim.core.bezier import integer_interpolate, partial_quadratic_bezier_points

OUT = np.array((0, 0, 1), dtype=np.float32)
# a "⊓" as three straight curves: up 3.2, right 2, down 3.2 (the bug report's path)
CAP = [(-1.0, -2.0, 0.0), (-1.0, 1.2, 0.0), (1.0, 1.2, 0.0), (1.0, -2.0, 0.0)]


def cap_path(width=40.0):
    path = VMobject()
    path.set_points_as_corners([np.array(corner) for corner in CAP])
    path.set_fill(opacity=0).set_stroke(WHITE, width=width)
    return path


def partial(source, a, b):
    result = source.copy()
    result.pointwise_become_partial(source, a, b)
    return result


def degrees(mobject):
    return np.degrees(joint_angles_of(mobject, OUT))


def drawn_length(mobject):
    """The length of the curves the stroke draws (straight curves only)."""
    points = mobject.points.astype(np.float64)
    a0, handle, a1 = points[0:-1:2], points[1::2], points[2::2]
    drawn = ~np.all(a0 == handle, axis=1)
    return float(np.linalg.norm(a1 - a0, axis=1)[drawn].sum())


def test_the_visible_end_makes_no_turn():
    tip = partial(cap_path(), 0, 0.2)
    angles = degrees(tip)
    # before the fix: -90 at point 2, the last point of the visible part
    assert np.all(angles == 0), angles


def test_the_visible_start_makes_no_turn():
    late = partial(cap_path(), 0.8, 1.0)
    angles = degrees(late)
    # points 0..4 collapse onto the start, 40% of the way down the last leg; the
    # visible part leaves point 4 going down: before the fix, -90 there
    assert np.all(angles == 0), angles


def test_a_real_corner_inside_a_partial_keeps_its_turn():
    piece = partial(cap_path(), 0.5, 0.9)
    angles = degrees(piece)
    # from the middle of the top to 70% of the way down: the corner at point 4 stays -90
    assert np.isclose(angles[4], -90, atol=1e-4), angles
    assert np.all(np.delete(angles, 4) == 0), angles


def test_a_full_path_keeps_its_angles():
    angles = degrees(cap_path())
    assert np.allclose(angles, [0, 0, -90, 0, -90, 0, 0], atol=1e-4), angles
    square = VMobject()
    square.set_points_as_corners([(1, 1, 0), (-1, 1, 0), (-1, -1, 0), (1, -1, 0), (1, 1, 0)])
    angles = degrees(square)
    # a closed loop joins its ends: a turn of +90 at every corner, start and end included
    corners = angles[0::2]
    assert np.allclose(corners, 90, atol=1e-4), angles


def test_a_collapsed_run_inside_a_closed_path_keeps_the_corner():
    sector = Sector(angle=TAU / 3)
    points = sector.points
    # points 0..12 are the inner arc of radius 0, collapsed at the centre
    assert np.all(points[:13] == points[0])
    angles = degrees(sector)
    # the line out of the centre (from point 12) and the line back into it (to point 28)
    # meet at the true turn, +60; the old angles gave 0 at 12 and 60 at 28
    assert np.isclose(angles[12], 60, atol=1e-4), angles
    assert np.isclose(angles[28], 60, atol=1e-4), angles


def test_a_degenerate_handle_reads_the_curve_s_own_direction():
    path = VMobject()
    # a curve whose handle sits on its END: its tangent there is the chord's direction
    path.set_points(np.array([(0, 0, 0), (1, 0, 0), (2, 0, 0), (2, 1, 0), (2, 1, 0)], dtype=np.float32))
    angles = degrees(path)
    # (2,0) -> (2,1) arrives going up: the turn at point 2 is +90; the end makes none
    assert np.isclose(angles[2], 90, atol=1e-4), angles
    assert angles[4] == 0, angles


def test_without_zero_segments_the_slow_route_is_the_fast_one():
    shapes = [Circle(), Square(), Star(), Annulus(), cap_path(), partial(cap_path(), 0.2, 1.0)]
    for shape in shapes:
        points = shape.points.astype(np.float64)
        n = len(points)
        y, x = joint_vectors_of(shape, OUT)
        incoming, outgoing = expanded._vectors_past_zero_segments(points, shape.points, shape.get_subpath_end_indices())
        slow_y = np.concatenate((outgoing[:, 1], incoming[:, 1]))
        slow_x = np.concatenate((outgoing[:, 0], incoming[:, 0]))
        # every anchor agrees bit for bit (handles are never read)
        anchors = np.concatenate((np.arange(0, n, 2), n + np.arange(0, n, 2)))
        if shape is shapes[-1]:
            continue  # this one HAS zero segments; it is here to run the slow route at all
        assert np.array_equal(slow_y[anchors].view(np.uint64), y[anchors].view(np.uint64)), type(shape).__name__
        assert np.array_equal(slow_x[anchors].view(np.uint64), x[anchors].view(np.uint64)), type(shape).__name__


def test_the_batched_route_agrees_bit_for_bit():
    members = [partial(cap_path(), 0, 0.2), partial(cap_path(), 0.5, 0.9), cap_path()]
    entries = []
    for mobject in members:
        y, x = joint_vectors_of(mobject, OUT)
        entries.append((y, x, len(y) // 2))
    for mobject, batched in zip(members, batched_joint_angles(entries)):
        assert np.array_equal(batched.view(np.uint32), joint_angles_of(mobject, OUT).view(np.uint32))


def l_shape():
    """A long leg (4) and a short one (1): two curves of very different length."""
    path = VMobject()
    path.set_points_as_corners([(0, 0, 0), (4, 0, 0), (4, 1, 0)])
    return path


def created(animation, alpha):
    """The mobject of `animation` at `alpha` (build it with rate_func=linear)."""
    animation.begin()
    animation.interpolate(alpha)
    return animation.mobject


def test_by_length_moves_at_a_steady_speed():
    for alpha in (0.1, 0.3, 0.5, 0.7, 0.9):
        mobject = created(ShowCreation(l_shape(), by_length=True, rate_func=linear), alpha)
        assert math.isclose(drawn_length(mobject), 5 * alpha, abs_tol=1e-5), (alpha, drawn_length(mobject))
    # by curve, as ManimGL: half the time draws the whole long leg
    mobject = created(ShowCreation(l_shape(), rate_func=linear), 0.5)
    assert math.isclose(drawn_length(mobject), 4, abs_tol=1e-5)


def test_by_length_false_is_unchanged():
    for alpha in (0.0, 0.25, 0.6, 1.0):
        mobject = created(ShowCreation(l_shape(), rate_func=linear), alpha)
        assert np.array_equal(mobject.points, partial(l_shape(), 0, alpha).points)


def test_by_length_on_a_curved_path():
    """Quadratics are walked by sampled arc length, so a circle grows by equal arcs.

    A circle's curves are all the same length, so this measures the sampling's
    accuracy (2e-3 rad), not the remap: by curve gives the same circle."""
    circle = Circle(radius=2)
    for alpha in (0.125, 0.4, 0.75):
        mobject = created(ShowCreation(circle.copy(), by_length=True, rate_func=linear), alpha)
        end = mobject.points[-1].astype(np.float64)
        swept = math.atan2(end[1], end[0]) % math.tau
        assert math.isclose(swept, alpha * math.tau, abs_tol=2e-3), (alpha, swept)


def two_segments():
    """Two unit segments ten units apart: the jump between them is a curve of length 10."""
    path = VMobject()
    path.start_new_path((0, 0, 0))
    path.add_line_to((1, 0, 0))
    path.start_new_path((0, 10, 0))
    path.add_line_to((1, 10, 0))
    return path


def test_the_jump_between_subpaths_takes_no_time():
    for alpha, length in ((0.25, 0.5), (0.5, 1.0), (0.75, 1.5)):
        mobject = created(ShowCreation(two_segments(), by_length=True, rate_func=linear), alpha)
        assert math.isclose(drawn_length(mobject), length, abs_tol=1e-5), (alpha, drawn_length(mobject))


def test_uncreate_takes_by_length():
    animation = Uncreate(l_shape(), by_length=True, rate_func=lambda t: t)
    mobject = created(animation, 0.5)
    assert animation.by_length
    assert math.isclose(drawn_length(mobject), 2.5, abs_tol=1e-5)


def trimmed(source, b):
    """The visible part of `partial(source, 0, b)` with nothing collapsed after it."""
    count = source.get_num_curves()
    upper, residue = integer_interpolate(0, count, b)
    right = partial_quadratic_bezier_points(source.points[2 * upper:2 * upper + 3], 0, residue)
    result = source.copy()
    result.set_points(np.concatenate([source.points[:2 * upper], right]))
    return result


def test_the_tip_looks_like_the_cut_path():
    """GPU: a thick partial renders exactly as the same piece cut off by itself."""
    try:
        reference = render_frame(trimmed(cap_path(), 0.2), resolution=(640, 360))
    except Exception as error:  # no device on this machine
        print(f"SKIP test_the_tip_looks_like_the_cut_path: {error}")
        return
    # the collapsed curves sit on the visible end, so the two share every coordinate
    image = render_frame(partial(cap_path(), 0, 0.2), resolution=(640, 360))
    assert reference.any()
    assert np.array_equal(image, reference), int((image != reference).any(axis=-1).sum())


def test_a_collapsed_run_draws_nothing_and_changes_no_corner():
    """GPU: a thick Sector renders exactly as its outline without the collapsed run."""
    sector = Sector(angle=TAU / 3, radius=2.5).set_fill(opacity=0).set_stroke(WHITE, width=30)
    outline = sector.copy()
    outline.set_points(sector.points[12:])
    try:
        reference = render_frame(outline, resolution=(640, 360))
    except Exception as error:  # no device on this machine
        print(f"SKIP test_a_collapsed_run_draws_nothing_and_changes_no_corner: {error}")
        return
    image = render_frame(sector, resolution=(640, 360))
    assert reference.any()
    assert np.array_equal(image, reference), int((image != reference).any(axis=-1).sum())


def main():
    failures = 0
    for name, test in sorted(globals().items()):
        if name.startswith("test_") and callable(test):
            try:
                test()
                print(f"OK  {name}")
            except AssertionError as error:
                failures += 1
                print(f"BAD {name}: {error}")
    print("all tests passed" if not failures else f"{failures} test(s) failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
