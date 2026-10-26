"""The composed animations of course 4.2: what each one does, frame by frame.

Run it directly (`python tests/test_composed_animations.py`) or with pytest.
No scene is rendered: every test drives an animation through its own
lifecycle (`begin`, `interpolate`, `finish`) and reads the mobjects back.
"""
import math
import sys

import numpy as np

from janim import (
    DOWN,
    LEFT,
    RIGHT,
    TAU,
    UP,
    AddTextLetterByLetter,
    AddTextWordByWord,
    AnimationGroup,
    ApplyPointwiseFunctionToCenter,
    Circle,
    Clock,
    ClockPassesTime,
    FlashyFadeIn,
    Rectangle,
    RemoveTextLetterByLetter,
    ShowCreationThenDestruction,
    ShowCreationThenDestructionAround,
    ShowCreationThenFadeAround,
    ShowCreationThenFadeOut,
    ShowPassingFlash,
    ShowPassingFlashAround,
    ShowPassingFlashWithThinningStrokeWidth,
    SpiralIn,
    Square,
    Text,
    Triangle,
    UntypeWithCursor,
    VGroup,
)


def _visible(glyphs):
    return [bool(glyph.fill_rgba[:, 3].max() > 0) for glyph in glyphs]


def test_add_text_word_by_word_shows_whole_words():
    text = Text("hello brave new  world", size=0.5)
    animation = AddTextWordByWord(text)
    assert [len(word) for word in animation.children] == [5, 5, 3, 5]
    assert abs(animation.run_time - 0.2 * 4) < 1e-12
    animation.begin()
    animation.interpolate(0.3)                      # ceil(0.3 * 4) = 2 words
    assert _visible(text.submobjects) == [True] * 10 + [False] * 8
    animation.interpolate(0.76)                     # ceil(0.76 * 4) = 4 words
    assert all(_visible(text.submobjects))
    animation.interpolate(0.01)
    assert _visible(text.submobjects) == [True] * 5 + [False] * 13
    animation.finish()
    assert all(_visible(text.submobjects))
    # the letter-by-letter reveal is a different thing: one glyph per step
    letters = AddTextLetterByLetter(Text("hello brave", size=0.5))
    letters.begin()
    letters.interpolate(0.3)
    assert sum(_visible(letters.mobject.submobjects)) == math.ceil(0.3 * 10)


def test_add_text_word_by_word_on_a_group_uses_its_children():
    group = VGroup(Square(), Circle(), Triangle())
    animation = AddTextWordByWord(group, time_per_word=0.5)
    assert [len(word) for word in animation.children] == [1, 1, 1]
    assert abs(animation.run_time - 1.5) < 1e-12
    try:
        AddTextWordByWord(VGroup())
    except ValueError:
        pass
    else:
        raise AssertionError("an empty group must be refused")


def test_remove_text_letter_by_letter_erases_from_the_end_and_hands_back():
    text = Text("erase me", size=0.5)
    count = len(text)
    animation = RemoveTextLetterByLetter(text)
    assert animation.remover
    assert abs(animation.run_time - max(0.5, count * 0.06)) < 1e-12
    animation.begin()
    assert all(_visible(text.submobjects))
    animation.interpolate(0.25)
    shown = math.ceil(0.75 * count)
    assert _visible(text.submobjects) == [True] * shown + [False] * (count - shown)
    animation.interpolate(0.99)
    assert _visible(text.submobjects) == [True] + [False] * (count - 1)
    animation.finish()
    # like Uncreate, the mobject comes back intact
    assert all(_visible(text.submobjects))


def test_untype_with_cursor_follows_the_last_glyph_left():
    text = Text("abcdef", size=0.5)
    cursor = Rectangle(width=0.05, height=0.4)
    animation = UntypeWithCursor(text, cursor)
    assert isinstance(animation, AnimationGroup)
    animation.begin()
    animation.interpolate(0.5)
    left = text.submobjects[math.ceil(0.5 * 6) - 1]
    gap = float(cursor.get_left()[0] - left.get_right()[0])
    assert abs(gap - 0.1) < 1e-5 and abs(float(cursor.get_y() - left.get_y())) < 1e-5
    animation.interpolate(1.0)
    assert np.allclose(cursor.get_center(), text.submobjects[0].get_center(), atol=1e-6)
    animation.finish()
    assert all(_visible(text.submobjects))
    assert isinstance(UntypeWithCursor(Text("ab")), RemoveTextLetterByLetter)


def test_apply_pointwise_function_to_center_moves_without_deforming():
    square = Square(side_length=1.5).shift(RIGHT + 0.5 * UP)
    width, height = square.get_width(), square.get_height()
    center = square.get_center().copy()
    animation = ApplyPointwiseFunctionToCenter(lambda point: 2 * point + DOWN, square)
    assert animation.run_time == 1.0
    animation.begin()
    animation.finish()
    assert np.allclose(square.get_center(), 2 * center + DOWN, atol=1e-6)
    assert abs(square.get_width() - width) < 1e-6 and abs(square.get_height() - height) < 1e-6


def test_thinning_flash_is_ce_linspace_without_the_empty_copy():
    circle = Circle().set_stroke(width=6)
    animation = ShowPassingFlashWithThinningStrokeWidth(circle, n_segments=10, time_width=0.3, run_time=2)
    flashes = animation.animations
    assert len(flashes) == 9
    assert all(isinstance(flash, ShowPassingFlash) for flash in flashes)
    assert np.allclose([flash.mobject.get_stroke_width() for flash in flashes], np.linspace(0, 6, 10)[:9], atol=1e-6)
    assert np.allclose([flash.time_width for flash in flashes], np.linspace(0.3, 0, 10)[:9])
    assert all(flash.mobject is not circle and flash.run_time == 2 for flash in flashes)
    assert len(ShowPassingFlashWithThinningStrokeWidth(circle, n_segments=1).animations) == 1


def test_spiral_in_starts_far_and_ends_exactly_where_it_was():
    shapes = VGroup(
        Square(side_length=0.8).set_fill(opacity=0.5),
        Circle(radius=0.4).shift(2 * RIGHT).set_fill(opacity=1.0),
        Triangle().shift(2 * UP),
    )
    points = [shape.points.copy() for shape in shapes]
    fills = [shape.fill_rgba.copy() for shape in shapes]
    centers = [shape.get_center().copy() for shape in shapes]
    center = shapes.get_center().copy()
    animation = SpiralIn(shapes, scale_factor=4)
    # building it moves nothing (CE moves the shapes in __init__)
    assert all(np.array_equal(shape.points, before) for shape, before in zip(shapes, points))
    animation.begin()                               # alpha 0: four times further out, transparent
    for shape, final in zip(shapes, centers):
        expected = final + (final - center) * 4
        assert np.allclose(shape.get_center(), expected, atol=1e-4)
        assert float(shape.fill_rgba[:, 3].max()) == 0.0
    animation.interpolate(0.5)                      # orientation kept: a translated copy
    for shape, before in zip(shapes, points):
        offset = shape.points - before
        assert np.allclose(offset, offset[0], atol=1e-4)
    animation.interpolate(0.15)                     # fades in over the first 30%
    expected_fade = min(1.0, animation.rate_func(0.15) / 0.3)
    assert abs(float(shapes[1].fill_rgba[0, 3]) - expected_fade) < 1e-6
    animation.finish()
    for shape, before, fill in zip(shapes, points, fills):
        assert np.array_equal(shape.points, before) and np.array_equal(shape.fill_rgba, fill)


def test_spiral_in_without_children_flies_as_one_piece():
    square = Square().shift(RIGHT)
    animation = SpiralIn(square)
    animation.begin()
    animation.interpolate(0.4)
    animation.finish()
    assert np.allclose(square.get_center(), RIGHT, atol=1e-6)


def test_flashy_fade_in_is_a_fade_and_an_outline_flash():
    circle = Circle().set_fill(opacity=0.7).set_stroke(width=1)
    animation = FlashyFadeIn(circle, stroke_width=3.0)
    fade, flash = animation.animations
    assert fade.mobject is circle and flash.mobject is not circle
    assert flash.mobject.get_fill_opacity() == 0.0
    assert flash.mobject.get_stroke_width() == 3.0
    assert flash.time_width == 1.0


def test_around_family_runs_its_gesture_on_a_rectangle():
    for cls, kind in (
        (ShowPassingFlashAround, ShowPassingFlash),
        (ShowCreationThenDestructionAround, ShowCreationThenDestruction),
        (ShowCreationThenFadeAround, ShowCreationThenFadeOut),
    ):
        square = Square(side_length=1.0)
        animation = cls(square, buff=0.2, stroke_width=3.0)
        assert isinstance(animation.animations[0], kind)
        rectangle = animation.rectangle
        assert abs(rectangle.get_width() - 1.4) < 1e-6 and rectangle.get_stroke_width() == 3.0
        # placed again on the mobject when it begins, before its snapshot
        square.shift(2 * LEFT)
        animation.begin()
        inner = animation.animations[0]
        first = inner.animations[0] if isinstance(inner, AnimationGroup) else inner
        assert np.allclose(first.starting_mobject.get_center(), square.get_center(), atol=1e-6)
        animation.finish()


def test_clock_passes_time_turns_both_hands():
    clock = Clock(radius=1.0)
    assert clock.hour_hand is clock.submobjects[1] and clock.minute_hand is clock.submobjects[2]
    assert clock.face is clock.submobjects[0] and clock.ticks is clock.submobjects[3]
    animation = ClockPassesTime(clock, hours_passed=3)
    assert isinstance(animation, AnimationGroup) and animation.run_time == 5.0
    animation.begin()
    animation.interpolate(0.5)                      # an hour and a half: the minute hand at six
    tip = clock.minute_hand.points[-1]
    assert np.allclose(tip / np.linalg.norm(tip), DOWN, atol=1e-5)
    animation.finish()
    hour_tip = clock.hour_hand.points[-1]
    minute_tip = clock.minute_hand.points[-1]
    assert np.allclose(hour_tip / np.linalg.norm(hour_tip), RIGHT, atol=1e-5)
    assert np.allclose(minute_tip / np.linalg.norm(minute_tip), UP, atol=1e-5)
    try:
        ClockPassesTime(Circle())
    except TypeError:
        pass
    else:
        raise AssertionError("a mobject without hands must be refused")


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
