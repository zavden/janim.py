"""The composed mobjects of course 4.1.3: geometry measured on Manim, and behaviour.

Run it directly (`python tests/test_composed_mobjects.py`) or with pytest.
The tests of `Variable` and of the labels of `SampleSpace` go through LaTeX
and are skipped without `latex` and `dvisvgm` on the PATH.
"""
import math
import shutil
import sys

import numpy as np

from janim import (
    DEGREES,
    DOWN,
    LEFT,
    PI,
    RIGHT,
    UP,
    AnimatedBoundary,
    Arc,
    ArcBetweenPoints,
    ArcPolygonFromArcs,
    Circle,
    DecimalNumber,
    Disk3D,
    ExponentialValueTracker,
    Integer,
    Line,
    SampleSpace,
    Square,
    TangentialArc,
    Text,
    ValueTracker,
    Variable,
)
from janim.constants import BLUE_B, BLUE_D, BLUE_E, GREY_BROWN


class _Skipped(Exception):
    pass


def _require_latex():
    if shutil.which("latex") is None or shutil.which("dvisvgm") is None:
        if "pytest" in sys.modules:
            import pytest

            pytest.skip("latex and dvisvgm are not on the PATH")
        raise _Skipped("latex and dvisvgm are not on the PATH")


def test_exponential_value_tracker_moves_geometrically():
    tracker = ExponentialValueTracker(5)
    # ManimGL 1.7.2 reads e**5 here; Janim takes the argument as the value
    assert abs(tracker.get_value() - 5) < 1e-12
    first, second = ExponentialValueTracker(1), ExponentialValueTracker(100)
    middle = first.copy()
    middle.interpolate(first, second, 0.5)
    assert abs(middle.get_value() - 10) < 1e-9
    tracker.increment_value(1)
    assert abs(tracker.get_value() - 6) < 1e-12
    assert abs(ExponentialValueTracker().get_value() - 1) < 1e-15
    copy = ExponentialValueTracker(3).become(ExponentialValueTracker(7))
    assert abs(copy.get_value() - 7) < 1e-12
    for bad in (0, -1):
        try:
            ExponentialValueTracker(bad)
        except ValueError:
            continue
        raise AssertionError(f"{bad} must be refused")


def test_disk3d_is_a_flat_disc_of_the_radius():
    disk = Disk3D(radius=2.0)
    assert disk.resolution == (2, 100)
    # GL scales about the box's centre, which the 100 samples of v leave
    # 2.5e-4 off the origin (no sample at v = pi); Janim does the same
    radii = np.linalg.norm(disk.points[:, :2].astype(np.float64), axis=1)
    assert abs(float(radii.max()) - 2.0) < 1e-3 and float(radii.min()) < 1e-3
    assert float(np.abs(disk.points[:, 2]).max()) == 0.0
    assert abs(disk.get_width() - 4.0) < 2e-3
    ring = Disk3D(radius=1.0, u_range=(0.5, 1.0))
    radii = np.linalg.norm(ring.points[:, :2].astype(np.float64), axis=1)
    assert float(radii.min()) > 0.49


def test_tangential_arc_matches_ce_measured():
    """CE 0.22 measured on itself (2026-10-26): same endpoints to 1e-6."""
    line1 = Line(3 * LEFT, 3 * RIGHT)
    line2 = Line(3 * UP, 3 * DOWN).rotate(20 * DEGREES, about_point=(0, 0, 0))
    expected = {
        (1, 1): ((2.142222, 0.0), (0.732683, -2.01303), (0.913494, -0.639635)),
        (1, -1): ((-0.359228, 0.98697), (1.050311, 0.0), (0.189947, 0.271272)),
        (-1, 1): ((0.359228, -0.98697), (-1.050311, 0.0), (-0.189947, -0.271272)),
        (-1, -1): ((-2.142222, 0.0), (-0.732683, 2.01303), (-0.913494, 0.639635)),
    }
    for corner, (start, end, middle) in expected.items():
        arc = TangentialArc(line1, line2, radius=1.5, corner=corner)
        assert arc.radius == 1.5
        assert np.allclose(arc.get_start()[:2], start, atol=2e-6), corner
        assert np.allclose(arc.get_end()[:2], end, atol=2e-6), corner
        # CE's cubic and Janim's quadratics differ in the middle by 2e-4
        assert np.allclose(arc.point_from_proportion(0.5)[:2], middle, atol=1e-3), corner


def test_tangential_arc_ce_unit_test():
    line1 = Line(LEFT, RIGHT)
    line2 = Line(DOWN, UP).rotate(45 * DEGREES, about_point=(0, 0, 0))
    arc = TangentialArc(line1, line2, radius=1.0)
    assert arc.radius == 1.0
    # tangent: both ends sit on the lines, at the same distance from the corner
    start, end = arc.get_start().astype(np.float64), arc.get_end().astype(np.float64)
    assert abs(start[1] - (-start[0])) < 1e-6 or abs(start[1]) < 1e-6
    assert abs(np.linalg.norm(start) - np.linalg.norm(end)) < 1e-6


def test_arc_polygon_from_arcs_is_one_closed_path():
    a, b, c = np.array((-1.0, 0, 0)), np.array((1.0, 0, 0)), np.array((0, math.sqrt(3), 0))
    arcs = [ArcBetweenPoints(p, q, angle=PI / 3) for p, q in ((a, b), (b, c), (c, a))]
    polygon = ArcPolygonFromArcs(*arcs, fill_opacity=1.0)
    assert polygon.arcs == arcs and polygon.submobjects == arcs
    assert polygon.get_num_curves() == sum(arc.get_num_curves() for arc in arcs)
    assert np.allclose(polygon.points[0], polygon.points[-1], atol=1e-6)
    assert len(polygon.get_subpaths()) == 1


def test_arc_polygon_from_arcs_closes_gaps_with_ce_pieces():
    first = Arc(angle=PI / 2)
    second = Arc(angle=PI / 2).shift(3 * RIGHT)
    polygon = ArcPolygonFromArcs(first, second)
    gaps = []
    for arc, following in ((first, second), (second, first)):
        length = float(np.linalg.norm(following.get_start() - arc.get_end()))
        gaps.append(int(arc.get_num_curves() * length / arc.get_arc_length()) + 1)
    assert polygon.get_num_curves() == first.get_num_curves() + second.get_num_curves() + sum(gaps)
    assert len(polygon.get_subpaths()) == 1
    try:
        ArcPolygonFromArcs(first, Line(LEFT, RIGHT))
    except ValueError:
        pass
    else:
        raise AssertionError("a line is not an arc")


def test_variable_follows_its_tracker():
    _require_latex()
    variable = Variable(0.5, "x", num_decimal_places=3)
    assert isinstance(variable.tracker, ValueTracker)
    assert isinstance(variable.value, DecimalNumber) and variable.value.string == "0.500"
    assert variable.submobjects == [variable.label, variable.value]
    assert variable.value.get_left()[0] > variable.label.get_right()[0]
    variable.tracker.set_value(2.25)
    variable.update(0)
    assert variable.value.string == "2.250"
    counter = Variable(3, Text("n"), var_type=Integer)
    assert isinstance(counter.value, Integer) and counter.value.string == "3"
    counter.tracker.set_value(10.4)
    counter.update(0)
    assert counter.value.string == "10"
    try:
        Variable(1, "y", var_type=float)
    except TypeError:
        pass
    else:
        raise AssertionError("var_type must be DecimalNumber or Integer")


def test_animated_boundary_cycles_through_its_colors():
    circle = Circle()
    boundary = AnimatedBoundary(circle, cycle_rate=1.0)
    growing, fading = boundary.boundary_copies
    assert boundary.submobjects == [growing, fading]
    assert growing.get_fill_opacity() == 0.0
    dt = 1 / 10
    for _ in range(5):                             # t = 0.5: half drawn, first colour
        boundary.update(dt)
    assert growing.get_stroke_color() == BLUE_D and growing.get_stroke_width() == 3.0
    for _ in range(10):                            # t = 1.5: the second cycle runs backwards
        boundary.update(dt)
    assert growing.get_stroke_color() == BLUE_B
    assert fading.get_stroke_color() == BLUE_D
    assert 0.0 < fading.get_stroke_width() < 3.0
    reference = circle.copy()
    reference.pointwise_become_partial(circle, 1 - boundary.draw_rate_func(0.5), 1)
    # the update at t = 1.5 used total_time 1.4: compare the point count only
    assert len(growing.points) == len(reference.points)
    colors = [BLUE_D, BLUE_B, BLUE_E, GREY_BROWN]
    assert boundary.colors == colors


def test_sample_space_divisions():
    space = SampleSpace(width=3, height=3)
    space.divide_horizontally([0.3])
    heights = [float(part.get_height()) for part in space.horizontal_parts]
    assert np.allclose(heights, [0.9, 2.1], atol=1e-5)
    assert np.allclose(space.horizontal_parts[0].get_top(), space.get_top(), atol=1e-5)
    assert space[1] is space.horizontal_parts[1]
    other = SampleSpace(width=4, height=2)
    other.divide_vertically([0.25, 0.25])
    widths = [float(part.get_width()) for part in other.vertical_parts]
    assert np.allclose(widths, [1.0, 1.0, 2.0], atol=1e-5)
    assert np.allclose(other.vertical_parts[0].get_left(), other.get_left(), atol=1e-5)
    assert other.complete_p_list([0.5, 0.5]) == [0.5, 0.5]
    try:
        SampleSpace().get_side_braces_and_labels(["a"])
    except ValueError:
        pass
    else:
        raise AssertionError("braces need a division first")


def test_sample_space_labels():
    _require_latex()
    space = SampleSpace()
    space.divide_horizontally([0.3])
    braces, labels = space.get_side_braces_and_labels(["P(A)", "P(B)"])
    assert len(braces) == 2 and len(labels) == 2
    assert all(brace.get_right()[0] < space.get_left()[0] for brace in braces)
    space.add_braces_and_labels()
    assert space.horizontal_parts.braces in space.submobjects
    space.add_title("a long title for a small space")
    assert space.title.get_width() <= space.get_width() + 1e-5


def main():
    failures = 0
    for name, test in sorted(globals().items()):
        if name.startswith("test_") and callable(test):
            try:
                test()
                print(f"OK   {name}")
            except _Skipped as reason:
                print(f"SKIP {name}: {reason}")
            except AssertionError as error:
                failures += 1
                print(f"BAD  {name}: {error}")
    print("all tests passed" if not failures else f"{failures} test(s) failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
