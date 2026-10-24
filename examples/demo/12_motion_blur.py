"""Demo 12 · MOTION BLUR — “Welcome to JANIM”, three words whipping in

A variation on demo 10: three words enter from the left one after another
with `ease_out_quint`, intended for motion blur that advances STATE
between sub-exposures and averages in linear light, so each word blurs
along its actual trajectory. Janim does not apply that motion blur inside
the render loop (`Scene` has no `motion_blur` kwarg), so video uses single
exposures. The available still-image function is `render_frame_motion`
(see `examples/tutorial/c3_05_motion_blur/04_render_frame_motion.py` and
this folder's README: it averages at most two distinct frames).

“JANIM” uses the Fredoka Expanded typeface, which must be installed
(fontconfig finds it by its family name); the bottom caption describes
sub-exposure motion blur, although the video does not apply it.

    bin/janim render examples/demo/12_motion_blur.py -ql
"""

from pathlib import Path

from janim import *


class MotionBlurWelcome(Scene):
    def construct(self):
        title = VGroup(
            Text("Welcome", size=0.95, color=WHITE),
            Text("to", size=0.95, color=WHITE),
            Text("JANIM", size=0.95, color=WHITE, font="Fredoka Expanded"),
        )
        title.arrange(DOWN)
        title.scale(1.8)
        title.shift(LEFT * 11)

        caption = Text(
            "motion_blur = 8, shutter = 0.5: the state advances between sub-exposures",
            size=0.32,
            color=GREY_C,
        )
        caption.to_edge(DOWN, buff=0.35)

        self.add(caption)
        self.wait(1)
        self.add(title)
        self.play(
            title[0].animate(rate_func=ease_out_quint).set_x(0),
            run_time=0.8,
        )
        self.wait(0.1)
        self.play(
            title[1].animate(rate_func=ease_out_quint).set_x(0),
            run_time=0.8,
        )
        self.wait(0.1)
        self.play(
            title[2].animate(rate_func=ease_out_quint).set_x(0),
            run_time=0.8,
        )
        self.wait(3)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    # The video has no motion blur (see the docstring).
    MotionBlurWelcome(output=str(here.with_suffix(".mp4")), fps=30, resolution=(1280, 720)).render()
