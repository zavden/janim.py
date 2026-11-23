"""Wiggle starts every frame from the starting pose and leaves nothing behind.

Run it directly (`python tests/test_wiggle.py`) or with pytest.

Wiggle used to put back the points of path members only, then call scale().
Two things compounded frame after frame and outlived the animation:
scale()'s side effects (a DecimalNumber's size and font size; a subclass that
thickens its strokes with its size, as a lesson's props do, which left a dark
halo around them) and the turn and swell of members that are not paths (a
surface, an image), which ended displaced. The swell now moves points only and
every member with points is put back, as Rotate does.

These tests drive the animation without a scene, at 30 alphas as a 1 s
wiggle at 30 fps would, then finish() it. No GPU.
"""
import sys

import numpy as np

from janim import DecimalNumber, Group, Sphere, Square, VGroup, Wiggle


class Thickening(Square):
    """A square whose outline grows with its size (a scale side effect)."""

    def _handle_scale_side_effects(self, factor):
        if np.isscalar(factor):
            self.set_stroke(width=float(self.get_stroke_width()) * float(factor))


def _run(animation, frames=30):
    animation.begin()
    for k in range(frames):
        animation.interpolate((k + 0.5) / frames)
    animation.finish()


def test_scale_side_effects_do_not_compound():
    square = Thickening().set_stroke(width=4.0)
    _run(Wiggle(square, scale_value=1.3, n_wiggles=4))
    assert np.isclose(square.get_stroke_width(), 4.0), f"stroke width drifted to {square.get_stroke_width():.3f}"


def test_a_decimal_keeps_its_font_size():
    number = DecimalNumber(3.14, num_decimal_places=2, size=0.6)
    size, font_size = number.size, number.font_size
    _run(Wiggle(number, scale_value=1.2))
    assert np.isclose(number.size, size) and np.isclose(number.font_size, font_size), (number.size, number.font_size)
    number.set_value(2.72)                       # a rebuild after the wiggle uses the size it had before
    assert np.isclose(number.get_height(), DecimalNumber(2.72, num_decimal_places=2, size=0.6).get_height(), atol=1e-4)


def test_every_member_comes_back():
    ball = Sphere(radius=0.6, resolution=(12, 12)).shift((1.5, 0.0, 0.0))
    group = Group(Square(), ball)
    before = [array.copy() for array in ball._point_arrays()]
    _run(Wiggle(group, scale_value=1.2, rotation_angle=0.2, n_wiggles=5))
    for after, start in zip(ball._point_arrays(), before):
        assert np.allclose(after, start, atol=1e-5), f"the sphere moved by {np.abs(after - start).max():.2e}"


def test_it_still_wiggles():
    square = Square()
    start = square.points.copy()
    animation = Wiggle(square, scale_value=1.5, rotation_angle=0.3, n_wiggles=2)
    animation.begin()
    animation.interpolate(0.5)                   # there_and_back(0.5) = 1, sin(2 * pi * 0.5) = 0: the full swell, no turn
    assert np.allclose(square.points, 1.5 * start, atol=1e-5), "the mid pose must be the full swell"
    animation.interpolate(0.25)                  # sin(2 * pi * 0.25) = 1: turned by rotation_angle
    first = square.points[0] - square.get_center()
    turned = np.arctan2(first[1], first[0]) - np.arctan2(start[0][1], start[0][0])
    assert np.isclose((turned + np.pi) % (2 * np.pi) - np.pi, 0.3, atol=1e-3), f"turned by {turned:.4f}"
    animation.finish()
    assert np.allclose(square.points, start, atol=1e-6), "it must end where it began"


def test_plain_paths_end_where_they_began():
    shapes = VGroup(Square(), Square().shift((2.0, 0.0, 0.0)).set_stroke(width=6.0))
    start = [shape.points.copy() for shape in shapes]
    _run(Wiggle(shapes))
    for shape, points in zip(shapes, start):
        assert np.allclose(shape.points, points, atol=1e-6)
    assert np.isclose(shapes[1].get_stroke_width(), 6.0)


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
