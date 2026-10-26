"""Course 4 · 2.1 — Composed animations

Ten animations that Manim ships as compositions of others, and Janim too:
each is a few lines over an animation this course has already met.

    AddTextWordByWord(text, time_per_word=0.2)       GL's; words are the
                                                     glyphs between spaces
    RemoveTextLetterByLetter(text, time_per_char=0.06)
                                                     CE's; last glyph first,
                                                     and the text comes back
                                                     INTACT, like Uncreate
    UntypeWithCursor(text, cursor)                   CE's; TypeWithCursor
                                                     backwards
    SpiralIn(group, scale_factor=8, fade_in_fraction=0.3)
                                                     CE's; every child flies
                                                     in on a spiral
    ApplyPointwiseFunctionToCenter(f, m)             GL's; moves m, unchanged,
                                                     to f(its centre)
    ShowPassingFlashWithThinningStrokeWidth(m, n_segments=10, time_width=0.1)
                                                     CE's; flashes of copies,
                                                     thick and short to thin
                                                     and long
    FlashyFadeIn(m, stroke_width=2, time_width=1)    GL's; FadeIn plus a flash
                                                     along the outline
    ShowPassingFlashAround(m), ShowCreationThenDestructionAround(m),
    ShowCreationThenFadeAround(m)                    GL's; the same three
                                                     gestures on a
                                                     SurroundingRectangle
    ClockPassesTime(clock, hours_passed=12)          GL's; turns a Clock's
                                                     hands

Two of them do on purpose what their source does not. ManimGL 1.7.2 groups
a whole `Text` into one part, so its `AddTextWordByWord` shows everything at
once (CE calls its own version broken); Janim's shows words. And GL's
`…Around` family re-centres the rectangle's partial path on the mobject
every frame, which drags the flash through the middle; Janim places the
rectangle when the animation begins and leaves the path alone.

    python examples/tutorial/c4_02_animation_zoo/01_composed_animations.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 9.0


class ComposedAnimations(Scene):
    def construct(self):
        title = Text("composed animations", size=0.4, color=GREY_A)
        title.to_edge(UP, buff=0.25)
        self.add(title)

        # ── text: by words, by letters, with a cursor ────────────────────────
        words = Text("one word at a time", size=0.55)
        words.shift(1.6 * UP)
        self.play(AddTextWordByWord(words))
        self.play(RemoveTextLetterByLetter(words))

        typed = Text("typed, then untyped", size=0.55, color=TEAL)
        typed.shift(0.6 * UP)
        cursor = Rectangle(width=0.06, height=0.5)
        cursor.set_fill(GREY_A, opacity=1.0).set_stroke(width=0)
        cursor.next_to(typed[0], LEFT, buff=0.1)
        self.play(TypeWithCursor(typed, cursor))
        self.play(UntypeWithCursor(typed, cursor))
        self.remove(cursor)

        # ── shapes: a spiral, a function of the centre ───────────────────────
        shapes = VGroup(
            Square(side_length=0.9).set_fill(BLUE_D, opacity=0.8),
            Circle(radius=0.5).set_fill(RED_D, opacity=0.8),
            Triangle().scale(0.6).set_fill(GREEN_D, opacity=0.8),
        )
        shapes.arrange(RIGHT, buff=0.6).shift(0.4 * DOWN)
        # CE flies them in from 8 times as far; 3 keeps them on screen.
        self.play(SpiralIn(shapes, scale_factor=3), run_time=1.6)
        self.play(
            ApplyPointwiseFunctionToCenter(
                lambda point: point + 2.2 * LEFT + 1.0 * DOWN,
                shapes[0],
            ),
            ApplyPointwiseFunctionToCenter(
                lambda point: 1.6 * point + 0.4 * DOWN,
                shapes[2],
            ),
        )

        # ── flashes along a path and around a mobject ────────────────────────
        star = Star(outer_radius=0.9).set_stroke(YELLOW, width=8).set_fill(opacity=0)
        star.move_to((-4.2, 1.5, 0))
        self.play(ShowPassingFlashWithThinningStrokeWidth(star, time_width=0.4), run_time=1.4)

        label = Text("FlashyFadeIn", size=0.45, color=ORANGE)
        label.move_to((3.6, 1.5, 0))
        self.play(FlashyFadeIn(label, stroke_width=1.5), run_time=1.4)

        self.play(ShowPassingFlashAround(shapes[1], stroke_width=4), run_time=1.0)
        self.play(ShowCreationThenDestructionAround(label), run_time=1.0)
        self.play(ShowCreationThenFadeAround(shapes[2]), run_time=1.2)

        # ── a clock that passes three hours ──────────────────────────────────
        clock = Clock(radius=0.8).to_corner(DR, buff=0.5)
        self.play(ClockPassesTime(clock, hours_passed=3), run_time=2.0)
        self.wait(0.4)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    ComposedAnimations(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
