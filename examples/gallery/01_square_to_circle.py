"""Gallery 01: draw a square, morph it into a circle, then fade it out."""

from janim import (
    BLUE,
    Circle,
    DOWN,
    FadeOut,
    Scene,
    ShowCreation,
    Square,
    TAU,
    Transform,
    WHITE,
    YELLOW,
)


KEY_FRAME = 1.7
KEY_FRAMES = [KEY_FRAME, 2.8, 3.8]
RESOLUTION = (640, 360)


class SquareToCircle(Scene):
    def construct(self):
        square = Square()
        square.set_fill(color=BLUE, opacity=0.7)
        square.set_stroke(color=WHITE, width=4.0)
        square.rotate(TAU / 8)
        self.play(ShowCreation(square), run_time=1.0)

        circle = Circle(radius=1.2)
        circle.set_fill(color=YELLOW, opacity=0.7)
        circle.set_stroke(color=WHITE, width=4.0)
        self.play(Transform(square, circle), run_time=1.4)
        self.wait(0.5)
        self.play(FadeOut(square, shift=0.5 * DOWN), run_time=1.0)
        self.wait(0.4)
