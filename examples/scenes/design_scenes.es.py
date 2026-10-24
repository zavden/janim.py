"""The design lessons as Manim scenes: layers, a map, a user-defined mobject and a contract."""

import numpy as np

from janim import *


def design_shapes():
    back = Circle(radius=1.6, fill_opacity=1).set_fill("#2C5F8A").set_stroke(opacity=0)
    middle = Square(side_length=2.2, fill_opacity=1).rotate(TAU / 16)
    middle.set_fill("#F0A045").set_stroke(opacity=0)
    front = Triangle(radius=1.1, fill_opacity=1).set_fill("#7FDD58").set_stroke(opacity=0)
    return back, middle, front


class DesignLayers(Scene):
    def construct(self):
        title = Text("Efectos POR CAPA: lo que el diseño de Manim impide", size=0.5, color=GREY_A)
        title.to_edge(UP, buff=0.3)
        left_label = Text("un solo framebuffer, orden z", size=0.3, color=GREY_B)
        right_label = Text("una capa por grupo, con efectos", size=0.3, color=GREY_B)
        flat = VGroup(*design_shapes()).shift(3.4 * Vec3(LEFT) + 0.3 * Vec3(DOWN))
        back, middle, front = design_shapes()
        for mob in (back, middle, front):
            mob.shift(3.4 * Vec3(RIGHT) + 0.3 * Vec3(DOWN))
        blur = Blur(0.09)
        left_label.move_to((-3.4, -2.7, 0))
        right_label.move_to((3.4, -2.7, 0))
        self.use_composition(
            Composition(
                Layer(back, effects=[blur]),
                Layer(middle, blend="multiply"),
                Layer(front),
                Layer(flat, title, left_label, right_label),
                background=(0.04, 0.04, 0.05, 1),
            ),
        )

        def soften(mob, dt):
            blur.sigma = min(blur.sigma + 0.06 * dt, 0.16)

        back.add_updater(soften)
        self.wait(2)


class DesignMap(Scene):
    def construct(self):
        title = Text("El mapa de coordenadas: derivado vs cacheado", size=0.5, color=GREY_A)
        self.add(title.to_edge(UP, buff=0.3))
        def plane():
            return NumberPlane(
                (-3, 3, 1),
                (-2, 2, 1),
                width=4.4,
                height=3,
                background_stroke_width=2.5,
                faded_line_ratio=2,
            )

        left = plane().shift(3.3 * Vec3(LEFT) + 0.4 * Vec3(DOWN))
        right = plane().shift(3.3 * Vec3(RIGHT) + 0.4 * Vec3(DOWN))
        live = Dot(ORIGIN, radius=0.11).set_color(YELLOW)
        cached = Dot(ORIGIN, radius=0.11).set_color(RED)
        self.add(left, right, live, cached)
        live.add_updater(lambda mob: mob.move_to(left.c2p(1, 1)))
        cached.move_to(right.c2p(1, 1))
        left_label = Text("c2p(1,1) preguntado cada frame", size=0.28, color=YELLOW).move_to((-3.3, -3, 0))
        right_label = Text("c2p(1,1) calculado una vez", size=0.28, color=RED).move_to((3.3, -3, 0))
        self.add(left_label, right_label)
        self.wait(0.5)
        self.play(AnimationGroup(left.animate.scale(0.62), right.animate.scale(0.62)), run_time=1.2)
        self.play(
            AnimationGroup(
                left.animate.shift(0.9 * Vec3(UP) + 0.5 * Vec3(RIGHT)),
                right.animate.shift(0.9 * Vec3(UP) + 0.5 * Vec3(RIGHT)),
            ),
            run_time=1.2,
        )
        self.play(AnimationGroup(left.animate.rotate(TAU / 14), right.animate.rotate(TAU / 14)), run_time=1.2)
        self.play(Circumscribe(cached, shape="circle", buff=0.25, color=RED), run_time=1)
        self.wait(0.8)


class Thermometer(Mobject):
    """A user-defined interpolable value, with vector children for drawing."""

    is_interpolable = True

    def __init__(self, level=0.2, height=3.0, width=0.45):
        super().__init__()
        self.level, self.column_height = float(level), float(height)
        self.tube = Rectangle(width=width, height=height).set_stroke(GREY_A, width=3).set_fill(opacity=0)
        self.mercury = Rectangle(width=width * 0.6, height=0.01).set_fill(RED, 1).set_stroke(opacity=0)
        self.group = VGroup(self.tube, self.mercury)
        self.add(self.group)
        self._redraw()

    def _redraw(self):
        height = max(1e-3, self.level * self.column_height)
        base = self.tube.get_bounding_box_point(DOWN)
        fresh = Rectangle(width=float(self.tube.get_width()) * 0.6, height=height)
        fresh.set_fill(RED, 1).set_stroke(opacity=0)
        fresh.move_to(base + np.array((0, height / 2, 0), dtype=np.float32))
        self.mercury.become(fresh)
        return self

    def set_level(self, value):
        self.level = min(max(float(value), 0), 1)
        return self._redraw()

    def get_level(self):
        return self.level

    def copy(self, deep=False):
        result = Thermometer(self.level, self.column_height, float(self.tube.get_width()))
        return result.shift(self.group.get_center() - result.group.get_center())

    def interpolate(self, first, second, alpha, **kwargs):
        return self.set_level(first.level + float(alpha) * (second.level - first.level))

    def become(self, other, **kwargs):
        return self.set_level(other.level)


class DesignContract(Scene):
    def construct(self):
        title = Text("El contrato de interpolación: 4 líneas y ya se anima", size=0.48, color=GREY_A)
        title.to_edge(UP, buff=0.3)
        thermometer = Thermometer(level=0.15).shift(3.6 * Vec3(LEFT) + 0.3 * Vec3(DOWN))
        reading = DecimalNumber(15, num_decimal_places=0, size=0.9, color=RED)
        reading.add_updater(lambda mob: mob.set_value(100 * thermometer.get_level()))
        reading.move_to((-2.2, -0.9, 0))
        ball = Circle(radius=0.55, fill_opacity=1).set_fill(BLUE).set_stroke(opacity=0)
        ball.move_to((1.6, -0.4, 0))
        code = Text("is_interpolable · copy · interpolate · become", size=0.34, color=GREY_B)
        code.move_to((0, -2.9, 0))
        note = Text("Transform no menciona este tipo en ninguna parte", size=0.3, color=GREY_C)
        note.next_to(code, DOWN, buff=0.25)
        self.add(title, thermometer, reading, ball, code, note)
        self.wait(0.4)
        self.play(
            AnimationGroup(
                thermometer.animate.set_level(0.85),
                ball.animate.shift(3 * Vec3(RIGHT)).scale(1.5),
            ),
            run_time=1.8,
        )
        self.wait(0.5)
        self.play(thermometer.animate(rate_func=there_and_back).set_level(0.35), run_time=1.2)
        self.wait(0.5)
