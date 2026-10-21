"""The scenes of the six c1_01 lessons."""

from janim import *


class FixedClock(Scene):
    def construct(self):
        line = NumberLine((0.0, 1.0, 0.25), width=9.0).shift(1.2 * DOWN)
        self.add(line)
        samples = VGroup()
        for k in range(5):
            dot = Dot(line.number_to_point((k + 0.5) / 5), radius=0.09)
            dot.set_fill(YELLOW)
            samples.add(dot)
        self.add(samples)
        box = Square(side_length=0.7).set_fill(BLUE, 1.0).set_stroke(opacity=0)
        box.move_to(Vec3(line.number_to_point(0.0)) + 1.4 * Vec3(UP))
        self.add(box)
        self.play(
            LaggedStart(
                *(FadeIn(dot, shift=0.3 * UP) for dot in samples),
                lag_ratio=0.25,
            ),
            run_time=1.2,
        )
        self.play(
            box.animate(rate_func=linear).move_to(Vec3(line.number_to_point(1.0)) + 1.4 * Vec3(UP)),
            run_time=2.0,
        )
        self.wait(0.6)


class MobjectsAndAnimations(Scene):
    def construct(self):
        circle = Circle(radius=1.1).set_fill(BLUE, 1.0)
        circle.set_stroke(WHITE, width=4.0).shift(3.2 * LEFT)
        square = Square().set_fill("#E8A33D", 1.0).set_stroke(opacity=0)
        triangle = Triangle(radius=1.3).set_fill(GREEN, 1.0)
        triangle.set_stroke(opacity=0).shift(3.2 * RIGHT)
        self.play(ShowCreation(circle), run_time=1.0)
        self.play(FadeIn(square, shift=0.6 * UP), run_time=0.8)
        self.play(Transform(square, triangle), run_time=1.2)
        self.wait(0.6)
        self.play(FadeOut(square), run_time=0.8)
        self.wait(0.4)


class SettersAndGetters(Scene):
    def construct(self):
        box = Rectangle(width=4.0, height=2.4).set_fill("#2C5F8A", 1.0)
        box.set_stroke(BLUE, width=3.0).shift(0.4 * DOWN)
        points = lambda: (
            box.get_left(),
            box.get_right(),
            box.get_top(),
            box.get_bottom(),
            box.get_center(),
        )
        marks = VGroup(*(Dot(point, radius=0.07).set_fill(YELLOW) for point in points()))
        brace = Brace(box, DOWN, buff=0.15, color=GREY_A)
        self.add(box, marks, brace)
        self.play(FadeIn(box), run_time=0.6)
        self.wait(0.6)
        self.play(box.animate.set_width(6.0).rotate(TAU / 24), run_time=1.2)
        brace.move_to(Vec3(box.get_bottom()) + 0.35 * Vec3(DOWN))
        for dot, point in zip(marks, points()):
            dot.move_to(point)
        self.wait(0.8)


class AnimationProperties(Scene):
    def construct(self):
        rows = []
        lags = (0.0, 0.15, 1.0)
        for y in (1.5, 0.0, -1.5):
            row = VGroup()
            for k in range(6):
                row.add(Dot((-3.6 + k, y, 0), radius=0.2).set_fill("#37506B"))
            rows.append(row)
            self.add(row)
        self.play(
            AnimationGroup(
                *(row.animate(lag_ratio=lag).set_color(YELLOW).scale(1.5) for row, lag in zip(rows, lags)),
            ),
            run_time=3.0,
        )
        self.wait(0.4)
        self.play(
            AnimationGroup(*(FadeOut(row) for row in rows), lag_ratio=0.2),
            run_time=1.2,
        )


class Copies(Scene):
    def construct(self):
        source = Square(side_length=1.6).set_fill(BLUE, 1.0)
        source.set_stroke(opacity=0).move_to(4.2 * LEFT)
        target = Circle(radius=0.95).set_fill("#E8A33D", 1.0)
        target.set_stroke(opacity=0).move_to(4.2 * RIGHT)
        self.add(source, target)
        twin = source.copy().set_fill(GREEN).move_to(1.6 * LEFT)
        self.play(FadeIn(twin), run_time=0.6)
        self.play(TransformFromCopy(source, target), run_time=1.6)
        self.wait(0.4)
        circle = Circle(radius=0.6).set_fill(GREEN, 1.0)
        circle.set_stroke(opacity=0).move_to(1.6 * RIGHT)
        self.play(Transform(twin, circle), run_time=1.2)
        self.wait(0.5)


class Layers(Scene):
    @staticmethod
    def stack(x):
        circles = [
            Circle(radius=0.9).set_fill("#2C5F8A", 1.0),
            Circle(radius=0.9).set_fill("#E8A33D", 1.0),
            Circle(radius=0.9).set_fill(GREEN, 1.0),
        ]
        for circle, dx in zip(circles, (-0.5, 0.0, 0.5)):
            circle.set_stroke(BLACK, width=3.0).move_to((x + dx, 0.3, 0))
        return circles

    def construct(self):
        self.add(*self.stack(-3.6))
        other = self.stack(3.6)
        self.add(*other)
        other[0].set_z_index(1)
        path = Circle(radius=0.55).move_to((0, -2.4, 0))
        dot = Dot((0.55, -2.4, 0), radius=0.11).set_fill(YELLOW)
        trail = TracedPath(dot.get_center, stroke_color=YELLOW, stroke_width=3.0)
        self.add(dot, trail)
        trail.set_z_index(-1)
        self.play(MoveAlongPath(dot, path, rate_func=linear), run_time=2.5)
        self.wait(0.4)


SCENES = {
    "01": FixedClock,
    "02": MobjectsAndAnimations,
    "03": SettersAndGetters,
    "04": AnimationProperties,
    "05": Copies,
    "06": Layers,
}
