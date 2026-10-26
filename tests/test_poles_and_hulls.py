"""polylabel, LabeledPolygram and ConvexHull3D, against ManimCE 0.22.

Run it directly (`python tests/test_poles_and_hulls.py`) or with pytest.
The first block is CE's `tests/utils/test_polylabels.py`, ported (its
parametrizations become loops). The rest pins CE's results measured on CE
itself: the same poles to the last bit and the same hull triangles.
"""
import math
import sys

import numpy as np

from janim import ConvexHull3D, LabeledPolygram, Square
from janim.core.hull3d import convex_hull_triangles
from janim.core.polylabel import Cell, Polygon, polylabel

SQUARE = [[[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]]
DONUT = [
    [[1, 1], [5, 1], [5, 5], [1, 5], [1, 1]],
    [[2, 2], [2, 4], [4, 4], [4, 2], [2, 2]],
]
FLAG = [[[0, 0], [2, 2], [4, 0], [4, 4], [0, 4], [0, 0]]]
GRAPHICAL = [
    [[-2.5, -2.5, 0], [2.5, -2.5, 0], [2.5, 2.5, 0], [-2.5, 2.5, 0], [-2.5, -2.5, 0]],
    [[-1, -1, 0], [0.5, -1, 0], [0.5, 0.5, 0], [-1, 0.5, 0], [-1, -1, 0]],
    [[1, 1, 0], [2, 1, 0], [2, 2, 0], [1, 2, 0], [1, 1, 0]],
]
EXAMPLE = [
    [[-3.8, -2.4, 0], [-2.4, -2.5, 0], [-1.3, -1.6, 0], [-0.2, -1.7, 0], [1.7, -2.5, 0],
     [2.9, -2.6, 0], [3.5, -1.5, 0], [4.9, -1.4, 0], [4.5, 0.2, 0], [4.7, 1.6, 0],
     [3.5, 2.4, 0], [1.1, 2.5, 0], [-0.1, 0.9, 0], [-1.2, 0.5, 0], [-1.6, 0.7, 0],
     [-1.4, 1.9, 0], [-2.6, 2.6, 0], [-4.4, 1.2, 0], [-4.9, -0.8, 0], [-3.8, -2.4, 0]],
    [[0.2, -1.2, 0], [0.9, -1.2, 0], [1.4, -2.0, 0], [2.1, -1.6, 0], [2.2, -0.5, 0],
     [1.4, 0.0, 0], [0.4, -0.2, 0], [0.2, -1.2, 0]],
    [[-2.7, 1.4, 0], [-2.3, 1.7, 0], [-2.8, 1.9, 0], [-2.7, 1.4, 0]],
]
FIVE = [[-2.7, -0.6, 3.5], [0.2, -1.7, -2.8], [1.9, 1.2, 0.7], [-2.7, 0.9, 1.9], [1.6, 2.2, -4.2]]
FIFTEEN = [
    [1.93192757, 0.44134585, -1.52407061], [-0.93302521, 1.23206983, 0.64117067],
    [-0.44350918, -0.61043677, 0.21723705], [-0.42640268, -1.05260843, 1.61266094],
    [-1.84449637, 0.91238739, -1.85172623], [1.72068132, -0.11880457, 0.51881751],
    [0.41904805, 0.44938012, -1.86440686], [0.83864666, 1.66653337, 1.88960123],
    [0.22240514, -0.80986286, 1.34249326], [-1.29585759, 1.01516189, 0.46187522],
    [1.7776499, -1.59550796, -1.70240747], [0.80065226, -0.12530398, 1.70063977],
    [1.28960948, -1.44158255, 1.39938582], [-0.93538943, 1.33617705, -0.24852643],
    [-1.54868271, 1.7444399, -0.46170734],
]


def _three_d(rings):
    return [np.column_stack([np.asarray(ring, dtype=float)[:, :2], np.zeros(len(ring))]) for ring in rings]


# ---------------------------------------------------------------- CE's tests


def test_polygon_inside_outside():
    for rings, inside_points, outside_points in (
        (
            SQUARE,
            [[2, 2], [1, 1], [3.9, 3.9], [0, 0], [2, 0], [0, 2], [0, 4], [4, 0], [4, 2], [2, 4], [4, 4]],
            [[-1, -1], [5, 5], [4.1, 2]],
        ),
        (
            DONUT,
            [[1.5, 1.5], [3, 1.5], [1.5, 3]],
            [[3, 3], [6, 6], [0, 0]],
        ),
        (
            FLAG,
            [[1, 3], [3.9, 3.9], [2, 3.5]],
            [[0.1, 0], [1, 0], [2, 0], [2, 1], [2, 1.9], [3, 0], [3.9, 0]],
        ),
    ):
        polygon = Polygon(rings)
        for point in inside_points:
            assert polygon.inside(point), point
        for point in outside_points:
            assert not polygon.inside(point), point


def test_polygon_compute_distance():
    for rings, points, expected_distance in (
        (SQUARE, [[2, 2]], 2.0),
        (SQUARE, [[0, 0], [2, 0], [4, 2], [2, 4], [0, 2]], 0.0),
        (SQUARE, [[5, 5]], -math.sqrt(2)),
    ):
        polygon = Polygon(rings)
        for point in points:
            result = polygon.compute_distance(np.array(point))
            assert abs(result - expected_distance) <= 1e-3 * abs(expected_distance) + 1e-12, (point, result)


def test_cell():
    for center, h, rings in (([2, 2], 1.0, SQUARE), ([3, 1.5], 0.5, DONUT)):
        polygon = Polygon(rings)
        cell = Cell(center, h, polygon)
        assert isinstance(cell.d, float)
        assert isinstance(cell.p, float)
        assert np.allclose(cell.c, center)
        assert cell.h == h
        other = Cell(np.add(center, [0.1, 0.1]), h, polygon)
        assert (cell < other) == (cell.d < other.d)
        assert (cell > other) == (cell.d > other.d)
        assert (cell <= other) == (cell.d <= other.d)
        assert (cell >= other) == (cell.d >= other.d)


def test_polylabel():
    for rings, expected_centers in (
        (SQUARE, [[2.0, 2.0]]),
        (DONUT, [[1.5, 1.5], [1.5, 4.5], [4.5, 1.5], [4.5, 4.5]]),
    ):
        result = polylabel(_three_d(rings), precision=0.01)
        assert isinstance(result, Cell)
        assert result.h <= 0.01
        assert result.d >= 0.0
        assert any(np.allclose(result.c, center, atol=0.1) for center in expected_centers), result.c


# ------------------------------------------------------------- Janim's own


def test_polylabel_is_ce_to_the_last_bit():
    """CE 0.22 measured on itself (2026-10-26)."""
    for rings, center, distance, h in (
        (SQUARE, [2.0, 2.0], 2.0, 0.0),
        (DONUT, [4.4140625, 1.5859375], 0.5855728031701096, 0.0078125),
        (FLAG, [1.171875, 2.828125], 1.1711456063402192, 0.015625),
        (GRAPHICAL, [-1.4501953125, 1.4501953125], 1.0498046875, 0.0048828125),
        (EXAMPLE, [-2.883984375, -0.563671875], 1.795168089312348, 0.005078125),
    ):
        cell = polylabel(_three_d(rings), precision=0.01)
        assert cell.c.tolist() == center and float(cell.d) == distance and float(cell.h) == h, cell.c


def test_polylabel_degenerate_inputs():
    flat = polylabel([[[0, 0], [2, 0], [4, 0], [0, 0]]])
    assert np.allclose(flat.c, [2, 0]) and flat.d == 0.0
    repeated = Polygon([[[0, 0], [4, 0], [4, 0], [4, 4], [0, 4], [0, 0]]])
    assert repeated.compute_distance(np.array([2.0, 2.0])) == 2.0


def test_labeled_polygram_puts_its_label_at_the_pole():
    polygram = LabeledPolygram(*GRAPHICAL, label="C")
    assert np.array_equal(polygram.pole, [-1.4501953125, 1.4501953125, 0.0])
    assert polygram.radius == 1.0498046875
    assert np.allclose(polygram.label.get_center(), polygram.pole, atol=1e-6)
    assert polygram.submobjects == [polygram.label]
    assert len(polygram.get_subpaths()) == 3
    # an open ring is closed for the search and drawn the same
    opened = LabeledPolygram(*(ring[:-1] for ring in GRAPHICAL), label="C")
    assert np.array_equal(opened.pole, polygram.pole)
    assert np.array_equal(opened.points, polygram.points)
    # a mobject label is used as it is
    square = Square(side_length=0.3)
    framed = LabeledPolygram(*GRAPHICAL, label=square)
    assert np.allclose(square.get_center(), framed.pole, atol=1e-6)


def test_labeled_polygram_translates_ce_configs():
    polygram = LabeledPolygram(
        *GRAPHICAL,
        label="C",
        label_config={"size": 0.8},
        box_config={"color": "#123456", "fill_opacity": 0.5},
        frame_config={"color": "#ABCDEF", "stroke_width": 3.0},
    )
    background, text, border = polygram.label.submobjects
    assert background.get_fill_color() == "#123456" and abs(background.get_fill_opacity() - 0.5) < 1e-6
    assert border.get_stroke_color() == "#ABCDEF" and border.get_stroke_width() == 3.0
    for config in ({"box_config": {"corner_radius": 1}}, {"frame_config": {"dash": 1}}):
        try:
            LabeledPolygram(*GRAPHICAL, label="C", **config)
        except TypeError:
            continue
        raise AssertionError(f"{config} must be refused")


def test_hull_triangles_are_ce_triangles():
    """CE 0.22's QuickHull on its own examples, as sorted vertex indices."""
    expected = {
        "five": [[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 4], [1, 3, 4], [2, 3, 4]],
        "fifteen": [
            [0, 4, 6], [0, 4, 14], [0, 5, 7], [0, 5, 10], [0, 6, 10], [0, 7, 14], [1, 7, 9],
            [1, 7, 14], [1, 9, 14], [3, 4, 9], [3, 4, 10], [3, 7, 9], [3, 7, 11], [3, 10, 12],
            [3, 11, 12], [4, 6, 10], [4, 9, 14], [5, 7, 12], [5, 10, 12], [7, 11, 12],
        ],
    }
    for name, points in (("five", FIVE), ("fifteen", FIFTEEN)):
        faces = convex_hull_triangles(points)
        assert sorted(sorted(face) for face in faces) == expected[name], name
        array = np.asarray(points)
        centroid = array.mean(axis=0)
        for a, b, c in faces:
            normal = np.cross(array[b] - array[a], array[c] - array[a])
            assert np.dot(normal, array[a] - centroid) > 0, "a face looks inward"
        assert convex_hull_triangles(points) == faces


def test_hull_leaves_inner_and_flat_points_out():
    cube = [[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)]
    faces = convex_hull_triangles(cube + [[0.5, 0.5, 0.5], [0.5, 0.5, 1.0]])
    assert len(faces) == 12 and max(max(face) for face in faces) < 8
    for bad in ([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]], [[0, 0, 0], [1, 1, 1], [2, 2, 2], [3, 3, 3]], [[0, 0, 0]] * 4, FIVE[:3]):
        try:
            convex_hull_triangles(bad)
        except ValueError:
            continue
        raise AssertionError(f"{bad} must be refused")


def test_convex_hull_3d_is_a_polyhedron_of_its_triangles():
    hull = ConvexHull3D(*(FIFTEEN + [[0.0, 0.0, 0.0]]), fill_opacity=0.5)
    assert len(hull.submobjects) == 20
    # three of CE's fifteen points, and the added origin, are inside
    assert len(hull.hull_points) == 12
    assert all(len(face) == 3 for face in hull.hull_faces)
    corners = {tuple(np.round(point, 5)) for polygon in hull.submobjects for point in polygon.get_vertices()}
    assert corners <= {tuple(np.round(np.asarray(point, dtype=np.float32), 5)) for point in FIFTEEN}


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
