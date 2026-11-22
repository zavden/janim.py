"""Brace, against ManimCE 0.22.

Run it directly (`python tests/test_brace.py`) or with pytest.

Janim's Brace is CE's brace: the same SVG path (two curls, a tip, straight
runs whose length follows `sharpness`), placed and stretched the way CE does
it. The numbers below were printed by ManimCE 0.22.0 itself on 2026-11-22
(`Brace(Square())`, `Brace(Square(), sharpness=1)`, a 0.3-wide `Line`,
`Rectangle(width=10, height=1)` braced UP, `Square()` braced RIGHT and UL).

Janim draws quadratics, so every cubic of the path becomes two quadratics:
CE's anchors all survive as anchors (plus one new anchor per cubic), and the
brace is aligned on the extent of the path's own control points, which is
CE's bounding box. CE's anchors were printed to 6 decimals and Janim's points
are float32 (spacing 1.2e-7 near 1.5): 1e-6 covers both.
"""
import sys

import numpy as np

from janim import DOWN, LEFT, RIGHT, UL, UP, Brace, BraceBetweenPoints, BraceLabel, Line, Rectangle, Square

ATOL = 1e-6

# CE 0.22.0: Brace(Square()).points[0::4] + the last anchor (25 cubics → 26 anchors)
CE_SQUARE_DOWN = [
    (-0.993920, -1.200000), (-1.000000, -1.213110), (-1.000000, -1.220872), (-0.884650, -1.366372),
    (-0.111030, -1.366372), (-0.048730, -1.392732), (-0.005490, -1.470422), (0.000000, -1.472985),
    (0.005490, -1.470422), (0.048730, -1.392732), (0.111030, -1.366372), (0.884650, -1.366372),
    (1.000000, -1.220872), (1.000000, -1.213110), (0.993920, -1.200000), (0.988465, -1.202563),
    (0.945225, -1.280253), (0.882925, -1.306613), (0.109305, -1.306613), (0.000055, -1.432213),
    (-0.109195, -1.306613), (-0.882815, -1.306613), (-0.945115, -1.280253), (-0.988355, -1.202563),
    (-0.993810, -1.200000), (-0.993920, -1.200000),
]
# CE 0.22.0: get_tip() of each case
CE_TIPS = {
    "square_down": (0.0, -1.472985),
    "square_right": (1.472985, 0.0),
    "line_down": (0.0, -0.472985),
    "rect_up": (0.0, 0.972985),
    "square_ul": (-1.334451, 1.334451),
}
CE_DEPTH = 0.272985          # CE: Brace(...).height for a DOWN brace, whatever the width


def _cases():
    return {
        "square_down": Brace(Square(), DOWN),
        "square_right": Brace(Square(), RIGHT),
        "line_down": Brace(Line(0.15 * LEFT, 0.15 * RIGHT), DOWN),
        "rect_up": Brace(Rectangle(width=10, height=1), UP),
        "square_ul": Brace(Square(), UL),
    }


def _nearest(points, targets):
    points = np.asarray(points, dtype=np.float64)[:, :2]
    targets = np.asarray(targets, dtype=np.float64)
    return np.min(np.linalg.norm(targets[:, None, :] - points[None, :, :], axis=2), axis=1)


def test_every_ce_anchor_is_an_anchor():
    brace = Brace(Square())
    anchors = brace.points[0::2]
    distance = _nearest(anchors, CE_SQUARE_DOWN)
    assert distance.max() < ATOL, f"an anchor is {distance.max():.2e} away from CE's"


def test_tips_are_ce_tips():
    for name, brace in _cases().items():
        tip = brace.get_tip()[:2]
        assert np.allclose(tip, CE_TIPS[name], atol=ATOL), f"{name}: tip {tip} != CE {CE_TIPS[name]}"


def test_directions_point_away_from_the_mobject():
    for name, direction in (("square_down", DOWN), ("square_right", RIGHT), ("rect_up", UP)):
        got = _cases()[name].get_direction()
        assert np.allclose(got, direction, atol=1e-5), f"{name}: {got}"


def test_span_is_the_mobject_and_depth_is_ce():
    brace = Brace(Rectangle(width=10, height=1), UP, buff=0.3)
    anchors = brace.points[0::2].astype(np.float64)
    assert np.isclose(anchors[:, 0].min(), -5.0, atol=ATOL) and np.isclose(anchors[:, 0].max(), 5.0, atol=ATOL)
    assert np.isclose(anchors[:, 1].min(), 0.5 + 0.3, atol=ATOL), "the open side sits buff away from the edge"
    assert np.isclose(brace.get_tip()[1], 0.5 + 0.3 + CE_DEPTH, atol=ATOL)


def test_sharpness_moves_the_curls_not_the_span():
    sharp, round_ = Brace(Square(), sharpness=2), Brace(Square(), sharpness=1)
    # CE 0.22.0, Brace(Square(), sharpness=1).points[12]: the end of the first curl
    assert _nearest(round_.points[0::2], [(-0.7693, -1.366372)]).max() < ATOL
    assert _nearest(sharp.points[0::2], [(-0.884650, -1.366372)]).max() < ATOL
    for brace in (sharp, round_):
        assert np.allclose(brace.get_tip()[:2], CE_TIPS["square_down"], atol=ATOL)


def test_a_narrow_span_squeezes_the_whole_path():
    brace = Brace(Line(0.15 * LEFT, 0.15 * RIGHT), DOWN)
    anchors = brace.points[0::2].astype(np.float64)
    assert np.isclose(anchors[:, 0].min(), -0.15, atol=ATOL) and np.isclose(anchors[:, 0].max(), 0.15, atol=ATOL)
    # CE 0.22.0: the end of the first curl, squeezed with the rest
    assert _nearest(anchors, [(-0.0735688, -0.366372)]).max() < ATOL


def test_a_filled_brace_with_no_outline():
    brace = Brace(Square(), color="#F4D57F")
    assert np.isclose(brace.get_fill_opacity(), 1.0)
    assert np.isclose(brace.get_stroke_width(), 0.0)
    assert brace.get_fill_color().lower() == "#f4d57f"


def test_brace_label_sits_past_the_tip():
    group = BraceLabel(Square(), "side", RIGHT)
    brace, label = group
    assert label.get_left()[0] > brace.get_tip()[0], "the label must start past the tip"


def test_the_mobject_is_not_moved():
    square = Square().rotate(0.3)
    before = square.points.copy()
    Brace(square, UL)
    assert np.array_equal(square.points, before)


def test_refusals():
    for build, error in (
        (lambda: Brace(Square(), thickness=0.1), TypeError),           # the old knobs are gone, loudly
        (lambda: Brace(Square(), tip_length=0.2), TypeError),
        (lambda: Brace(Line(UP, DOWN), DOWN), ValueError),              # nothing to span across
        (lambda: Brace(Square(), sharpness=0), ValueError),
        (lambda: BraceBetweenPoints(UP, UP), ValueError),
    ):
        try:
            build()
        except error:
            continue
        raise AssertionError(f"{build} must raise {error.__name__}")


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
