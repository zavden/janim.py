"""Demo 12 · MOTION BLUR — «Welcome to JANIM», tres palabras que entran a látigo

Una variante de la demo 10: tres palabras que entran desde la izquierda una
tras otra con `ease_out_quint`, pensadas para un motion blur que avanza el
ESTADO entre sub-exposiciones y promedia en luz lineal, de modo que cada
palabra se emborrona a lo largo de su trayectoria real. Janim no hace ese
motion blur dentro del bucle de render (`Scene` no tiene un kwarg
`motion_blur`), así que el vídeo sale con exposiciones simples. La foto fija
que hay es `render_frame_motion` (ver
`examples/tutorial/c3_05_motion_blur/04_render_frame_motion.py` y el README de
esta carpeta: promedia como mucho dos frames distintos).

«JANIM» va en la tipografía Fredoka Expanded, que tiene que estar instalada
(fontconfig la encuentra por su nombre de familia); el rótulo de abajo
describe el motion blur por sub-exposiciones, aunque el vídeo no lo aplique.

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
    # El vídeo sale sin motion blur (ver el docstring).
    MotionBlurWelcome(output=str(here.with_suffix(".mp4")), fps=30, resolution=(1280, 720)).render()
