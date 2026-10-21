"""Gallery 02: a square crosses the conformal map z -> exp(z)."""

import numpy as np

from janim import FadeIn, ORIGIN, Scene, Square, Transform, YELLOW


KEY_FRAME = 1.4
KEY_FRAMES = [KEY_FRAME, 0.5, 2.7]
RESOLUTION = (640, 360)


def warp(mobject):
    def point_function(point):
        value = np.exp(np.complex64(complex(float(point[0]), float(point[1]))))
        return np.array((float(value.real) - 1.2, value.imag, 0), dtype=np.float32)

    return mobject.apply_function(point_function, about_point=ORIGIN)


class WarpSquare(Scene):
    def construct(self):
        def make_square():
            return Square(side_length=2.0).set_stroke(color=YELLOW, width=4.0).set_fill(color=YELLOW, opacity=0.2)

        square = make_square()
        self.play(FadeIn(square), run_time=0.6)
        target = warp(make_square())
        self.play(Transform(square, target), run_time=1.6)
        self.wait(0.6)
