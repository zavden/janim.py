"""Gallery 05: five circles arrive in a cascade and leave in reverse order."""

from janim import (
    BLUE,
    Circle,
    DOWN,
    FadeIn,
    FadeOut,
    GREEN,
    LaggedStart,
    RED,
    RIGHT,
    Scene,
    UP,
    WHITE,
    YELLOW,
)


KEY_FRAME = 1.0
KEY_FRAMES = [KEY_FRAME, 2.5, 4.1]
RESOLUTION = (640, 360)


class LaggedStartExample(Scene):
    def construct(self):
        colors = [BLUE, GREEN, YELLOW, RED, WHITE]
        circles = [Circle(radius=0.5) for _ in range(5)]
        for index, (circle, color) in enumerate(zip(circles, colors), 1):
            circle.set_fill(color=color, opacity=0.8)
            circle.set_stroke(color=WHITE, width=3.0)
            circle.move_to((1.3 * index - 3.9) * RIGHT)
        self.play(
            LaggedStart(*(FadeIn(circle, shift=0.5 * UP) for circle in circles), lag_ratio=0.25),
            run_time=2.0,
        )
        self.wait(0.6)
        self.play(
            LaggedStart(*(FadeOut(circle, shift=0.5 * DOWN) for circle in reversed(circles)), lag_ratio=0.25),
            run_time=1.6,
        )
        self.wait(0.3)
