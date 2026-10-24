"""Demo 10 · MOTION BLUR — una rueda, cuatro órbitas y un barrido de cámara

Esta escena se escribió para un motion blur que no fuese un difuminado
direccional pintado sobre la imagen: avanzar el ESTADO de la escena entre
sub-exposiciones y promediar (en luz lineal). Así cada objeto se emborrona a
lo largo de SU trayectoria —
rectas, arcos, giros, movimiento de cámara— y con `shutter = 0.5` (el
obturador de 180° del cine) los radios de una rueda rápida se funden en un
disco, como en una cámara de verdad.

Janim no hace ese motion blur dentro del bucle de render: `Scene` no tiene
un kwarg `motion_blur` (y el CLI rechaza `--motion-blur` por su nombre), así
que el vídeo sale con exposiciones simples. Lo que hay es la foto fija
`render_frame_motion(MotionBlur, t, n=8, shutter=0.5)` (ver
`examples/tutorial/c3_05_motion_blur/04_render_frame_motion.py`), con su
límite: coge el frame que contiene cada sub-exposición, y como la ventana del
obturador (`shutter / fps`) es más corta que un frame, promedia como mucho DOS
frames distintos — dos copias, no una estela (ver el README de esta carpeta).

Tres cosas en un mismo plano: un título que entra a látigo, una rueda que
acelera, cuatro partículas en órbita, y al final un barrido de cámara. El
rótulo de abajo describe ese motion blur por sub-exposiciones, aunque el
vídeo no lo aplique. Manim no tiene motion blur.

    bin/janim render examples/demo/10_motion_blur.py -ql
"""

from pathlib import Path

import numpy as np

from janim import *
from janim.math import cos, sin


class MotionBlur(Scene):
    def construct(self):
        title = Text("motion blur", size=0.95, color=WHITE)
        title.move_to((-10.0, 2.4, 0))       # fuera de cuadro, a la izquierda

        # una rueda con radios: al girar deprisa, los radios se funden en un disco
        wheel = VGroup()
        for k in range(6):
            spoke = Rectangle(width=3.0, height=0.16)
            spoke.set_fill("#FFD25E", opacity=1.0)
            spoke.set_stroke(opacity=0)
            spoke.rotate(k * TAU / 12)
            wheel.add(spoke)
        rim = Circle(radius=1.55)
        rim.set_stroke("#FFD25E", width=8.0)
        wheel.add(rim)
        hub = Circle(radius=0.22, fill_opacity=1.0)
        hub.set_fill("#FF3D8B", opacity=1.0)
        hub.set_stroke(opacity=0)
        wheel_center = np.array((-3.4, -0.9, 0), dtype=np.float32)
        wheel.move_to(wheel_center)
        hub.move_to(wheel_center)

        # el giro es función CERRADA del tiempo: acelera 3 s y luego va a 3 rev/s
        omega_max, t_acc = 3.0 * TAU, 3.0

        def angle(t):
            return omega_max * (t * t) / (2 * t_acc) if t < t_acc else omega_max * (t - t_acc / 2)

        theta_prev = [0.0]

        def spin(m, dt):
            theta = angle(self.t)
            m.rotate(theta - theta_prev[0], about_point=wheel_center)
            theta_prev[0] = theta

        wheel.add_updater(spin)

        # cuatro partículas en órbita rápida: cada una sigue su propio arco
        orbit_center = np.array((3.4, -0.9, 0), dtype=np.float32)
        ring = Circle(radius=1.8)
        ring.move_to(orbit_center)
        ring.set_stroke("#25405C", width=2.0)
        orbiters = VGroup()
        for c in ("#FF3D8B", "#39D0FF", "#7FDD58", "#FFFFFF"):
            d = Dot(ORIGIN, radius=0.18)
            d.set_fill(c)
            orbiters.add(d)

        def orbit(m, dt):
            t = self.t
            for k, d in enumerate(m.submobjects):
                phi = 1.3 * TAU * t + k * TAU / 4
                d.move_to(orbit_center + np.array((1.8 * cos(phi), 1.8 * sin(phi), 0), dtype=np.float32))

        orbiters.add_updater(orbit)

        caption = Text(
            "motion_blur = 8, shutter = 0.5: the state advances between sub-exposures",
            size=0.32,
            color=GREY_C,
        )
        caption.to_edge(DOWN, buff=0.35)

        self.add(wheel, hub, ring, orbiters, title, caption)

        # 1 · el título entra a látigo
        self.play(
            title.animate(rate_func=ease_out_quint).move_to((0, 2.4, 0)),
            run_time=0.6,
        )
        # 2 · la rueda acelera y las partículas orbitan
        self.wait(5.0)
        # 3 · barrido de cámara: todo se mueve a la vez, incluido lo quieto
        self.play(
            self.frame.animate.move_to((3.2, -0.6, 0)).scale_frame(0.6),
            run_time=0.7,
        )
        self.wait(0.8)
        self.play(
            self.frame.animate.move_to(ORIGIN).scale_frame(1 / 0.6),
            run_time=0.7,
        )
        self.wait(1.2)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    # El vídeo sale sin motion blur (ver el docstring).
    MotionBlur(output=str(here.with_suffix(".mp4")), fps=30, resolution=(1280, 720)).render()
