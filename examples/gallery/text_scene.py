"""A formula morph through the LaTeX-only text API."""

from janim import *


class TexTransformExample(Scene):
    def construct(self):
        first = Tex(r"a^2 + b^2 = c^2", size=1.4)
        self.play(FadeIn(first, shift=0.3 * UP), run_time=0.8)
        self.wait(0.6)
        second = Tex(r"c = \sqrt{a^2 + b^2}", size=1.4)
        self.play(Transform(first, second), run_time=1.4)
        self.wait(0.8)
