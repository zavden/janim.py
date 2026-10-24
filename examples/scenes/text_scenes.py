"""Sets and a quadratic, using the LaTeX route."""

from janim import *


class Sets(Scene):
    def construct(self):
        blue, orange, yellow = "#58C4DD", "#F0A045", "#FFD25E"
        center_a = 1.05 * Vec3(LEFT) + 0.45 * Vec3(DOWN)
        center_b = 1.05 * Vec3(RIGHT) + 0.45 * Vec3(DOWN)

        def outline(position, color):
            return Circle(radius=1.9, fill_opacity=0).set_stroke(color, width=5).shift(position)

        def fill(position, color, opacity):
            return Circle(radius=1.9, fill_opacity=opacity).set_fill(color, opacity).set_stroke(
                opacity=0,
            ).shift(
                position,
            )

        first, second = outline(center_a, blue), outline(center_b, orange)
        intersection = fill(center_a, yellow, 0.85)
        first_only = fill(center_a, blue, 0.6)
        second_only = fill(center_b, orange, 0.6)
        union_a, union_b = fill(center_a, blue, 0.45), fill(center_b, orange, 0.45)
        background = Rectangle(
            width=16,
            height=9,
            fill_color="#101418",
            fill_opacity=1,
            stroke_opacity=0,
            stroke_width=0,
        )
        label_a = Tex("A", color=WHITE, size=1.1).move_to(center_a + 2.1 * Vec3(UL))
        label_b = Tex("B", color=WHITE, size=1.1).move_to(center_b + 2.1 * Vec3(UR))

        def formula(text, color):
            return Tex(text, color=color, size=1.35).move_to(2.85 * Vec3(UP))

        title = formula(r"A \cap B", yellow)
        self.use_composition(
            Composition(
                Layer(background),
                crop(intersection, inside=fill(center_b, WHITE, 1), feather=0.02),
                crop(first_only, minus=fill(center_b, WHITE, 1), feather=0.02),
                crop(second_only, minus=fill(center_a, WHITE, 1), feather=0.02),
                Layer(union_a, union_b),
                Layer(first, second, label_a, label_b, title),
            ),
        )
        for mob in (intersection, first_only, second_only, union_a, union_b):
            mob.set_fill(opacity=0)

        def appear(mob, opacity):
            return Transform(mob, mob.copy().set_fill(opacity=opacity))

        self.play(LaggedStart(ShowCreation(first), ShowCreation(second), lag_ratio=0.35), run_time=1.8)
        self.play(
            AnimationGroup(FadeIn(label_a, shift=0.3 * DOWN), FadeIn(label_b, shift=0.3 * DOWN)),
            run_time=0.7,
        )
        self.wait(0.4)
        self.play(AnimationGroup(FadeIn(title), appear(intersection, 0.85)), run_time=0.9)
        self.wait(1.8)
        self.play(
            AnimationGroup(
                Transform(title, formula(r"A \setminus B", blue)),
                FadeOut(intersection),
                appear(first_only, 0.6),
            ),
            run_time=1.0,
        )
        self.wait(1.8)
        self.play(
            AnimationGroup(
                Transform(title, formula(r"B \setminus A", orange)),
                FadeOut(first_only),
                appear(second_only, 0.6),
            ),
            run_time=1.0,
        )
        self.wait(1.8)
        self.play(
            AnimationGroup(
                Transform(title, formula(r"A \cup B", "#7FDD58")),
                FadeOut(second_only),
                appear(union_a, 0.45),
                appear(union_b, 0.45),
            ),
            run_time=1.0,
        )
        self.wait(2.0)
        self.play(
            AnimationGroup(
                FadeOut(union_a),
                FadeOut(union_b),
                FadeOut(title),
                FadeOut(label_a),
                FadeOut(label_b),
                FadeOut(first),
                FadeOut(second),
            ),
            run_time=1.2,
        )
        self.wait(0.4)


class Quadratic(Scene):
    def construct(self):
        steps = (
            r"ax^2 + bx + c = 0",
            r"x^2 + \frac{b}{a}x = -\frac{c}{a}",
            r"\left(x + \frac{b}{2a}\right)^2 = \frac{b^2 - 4ac}{4a^2}",
            r"x + \frac{b}{2a} = \pm\frac{\sqrt{b^2 - 4ac}}{2a}",
            r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}",
        )
        notes = ("the general equation", "divide by a and rearrange", "complete the square", "take the square root of both sides", "solve for x")
        title = Text("The quadratic formula").set_height(0.42).move_to(3.05 * Vec3(UP))
        title.set_fill("#8899AA", 1.0)

        def formula(index):
            result = Tex(steps[index], color=WHITE, size=1.15)
            if result.get_width() > 10.5:
                result.set_width(10.5)
            return result.move_to(0.3 * Vec3(UP))

        def counter(index):
            return Tex(str(index + 1), color="#FFD25E", size=1.0).move_to(5.9 * Vec3(RIGHT) + 3.05 * Vec3(UP))

        def note(index):
            return Text(notes[index]).set_height(0.3).set_fill("#58C4DD", 1.0).move_to(2.35 * Vec3(DOWN))

        current, number, caption = formula(0), counter(0), note(0)
        self.play(
            AnimationGroup(
                FadeIn(title, shift=0.25 * DOWN),
                FadeIn(current, shift=0.4 * UP),
                FadeIn(number),
                FadeIn(caption),
            ),
            run_time=1.0,
        )
        self.wait(1.6)
        for index in range(1, 5):
            self.play(
                AnimationGroup(
                    Transform(current, formula(index)),
                    Transform(number, counter(index)),
                    Transform(caption, note(index)),
                ),
                run_time=1.3,
            )
            self.wait(2.4 if index == 4 else 1.7)
        box = Rectangle(width=float(current.get_width()) + 0.7, height=float(current.get_height()) + 0.55)
        box.set_stroke("#FFD25E", width=4.0).move_to(current.get_center())
        self.play(ShowCreation(box), run_time=0.9)
        self.wait(1.6)
        self.play(
            AnimationGroup(FadeOut(current), FadeOut(box), FadeOut(title), FadeOut(number), FadeOut(caption)),
            run_time=1.0,
        )
        self.wait(0.3)
