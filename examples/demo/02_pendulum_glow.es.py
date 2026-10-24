"""Demo 02 · EL PÉNDULO CON GLOW — física dentro de un updater, una estela con
Bloom en una capa aditiva y un foco que es una MÁSCARA ANIMADA

Un doble péndulo integrado con Tsit5 DENTRO del updater de la varilla: el
integrador vive fuera, el updater le pide `step(integ, dt, True)` y lee el
estado. El integrador es `janim.ode` (un Tsit5). Tres cosas que Manim no
tiene:

  · la estela va en una capa `blend="add"` con `Bloom`: la luz SUMA en vez de
    tapar, y el halo sale del propio color del trazo. Las muestras se unen
    con `set_points_smoothly` (el `make_smooth` de GL): una curva por los
    mismos puntos, sin esquinas;
  · la masa lleva detrás un `GlowDot`: un halo REDONDO por fragmento
    (`pow(1-r, 2)`), que es lo que un Bloom no puede dar a un punto — el
    nivel más ancho de su pirámide chocaba con el tope del kernel (±63 px) y
    el halo salía CUADRADO;
  · el foco que sigue a la punta es una máscara con `feather`: recorta la
    rejilla encendida, y como es un mobject normal se mueve con un updater;
  · debajo queda la rejilla tenue, siempre visible — la misma geometría dos
    veces, con dos estilos, en dos capas.

Es el acto 2 de `examples/scenes/field_scene.py:FieldAndChaos`, sin las
líneas de campo de fondo y con la rejilla completa.

El estado mutable de los updaters son listas de un elemento; el seno y el
coseno vienen de `janim.math` y el rango de la rejilla
(`-7.2` a `7.2` de `0.8` en `0.8`) de `janim.math.step_range`, para
que las muestras sean siempre las mismas.

    bin/janim render examples/demo/02_pendulum_glow.py -ql
"""

from pathlib import Path

import numpy as np

from janim import *
from janim.math import cos, sin, step_range
from janim.ode import ODEProblem, Tsit5, init, step

G02 = 9.8


def double_pendulum(du, u, p, t):
    theta1, theta2, omega1, omega2 = u
    delta = theta1 - theta2
    den = 3 - cos(2 * delta)
    du[0] = omega1
    du[1] = omega2
    du[2] = (
        -3 * G02 * sin(theta1)
        - G02 * sin(theta1 - 2 * theta2)
        - 2 * sin(delta) * (omega2 * omega2 + omega1 * omega1 * cos(delta))
    ) / den
    du[3] = 2 * sin(delta) * (2 * omega1 * omega1 + 2 * G02 * cos(theta1) + omega2 * omega2 * cos(delta)) / den


def grid(color, width):
    """La rejilla de fondo, con el color y el grosor que se le pidan."""
    g = VGroup()
    for x in step_range(-7.2, 7.2, 0.8):
        line = Line((x, -4.2, 0), (x, 4.2, 0))
        line.set_stroke(color, width=width)
        g.add(line)
    for y in step_range(-4.0, 4.0, 0.8):
        line = Line((-7.2, y, 0), (7.2, y, 0))
        line.set_stroke(color, width=width)
        g.add(line)
    return g


class PendulumGlow(Scene):
    def construct(self):
        background = Rectangle(
            width=16.0,
            height=9.0,
            fill_color="#0B0E14",
            fill_opacity=1.0,
            stroke_opacity=0,
            stroke_width=0,
        )
        grid_dim = grid("#182338", 1.2)      # la rejilla tenue, siempre visible
        grid_lit = grid("#4A6FA8", 1.8)      # la rejilla encendida bajo el foco

        # el foco: un círculo relleno que NO se dibuja — recorta la rejilla encendida
        spotlight = Circle(radius=1.45, fill_opacity=1.0)

        # ── el péndulo ───────────────────────────────────────────────────
        pivot = np.array((0, 0.4, 0), dtype=np.float32)
        L = 1.25
        rod = VMobject()
        rod.set_stroke("#C8D2DC", width=3.5)
        bob1 = Circle(radius=0.11, fill_opacity=1.0)
        bob1.set_fill("#C8D2DC", opacity=0.0)
        bob1.set_stroke(opacity=0)
        bob2 = Circle(radius=0.13, fill_opacity=1.0)
        bob2.set_fill("#FFD25E", opacity=0.0)
        bob2.set_stroke(opacity=0)
        trail = VMobject()
        trail.set_stroke("#58C4DD", width=2.6, opacity=0.85)
        # el halo de la masa: un GlowDot nace con su estilo final (lo mueve un
        # updater, y un updater no re-estampa la opacidad de un DotCloud)
        halo = GlowDot(
            ORIGIN,
            color="#FFD25E",
            radius=0.55,
            glow_factor=2.0,
            opacity=0.0,
        )

        u0 = [2.1, 2.6, 0.0, 0.0]
        integ = init(
            ODEProblem(double_pendulum, u0, (0.0, 1e4)),
            Tsit5(),
            reltol=1e-9,
            abstol=1e-9,
        )

        def positions(u):
            p1 = pivot + np.array((L * sin(u[0]), -L * cos(u[0]), 0), dtype=np.float32)
            p2 = p1 + np.array((L * sin(u[1]), -L * cos(u[1]), 0), dtype=np.float32)
            return p1, p2

        # el estado inicial ya dibujado: nada aparece en el origen y salta después
        p1, p2 = positions(u0)
        rod.set_points_as_corners([pivot, p1, p2])
        bob1.move_to(p1)
        bob2.move_to(p2)
        halo.move_to(p2)
        spotlight.move_to(p2)

        samples = []
        tip = [p2]
        running = [False]

        def swing(m, dt):
            if not (running[0] and dt > 0):
                return
            step(integ, dt, True)
            p1, p2 = positions(integ.u)
            m.set_points_as_corners([pivot, p1, p2])
            bob1.move_to(p1)
            bob2.move_to(p2)
            halo.move_to(p2)
            tip[0] = p2
            samples.append(p2)
            if len(samples) > 300:
                del samples[0]
            # esquinas + make_smooth en una llamada: la misma curva
            if len(samples) > 1:
                trail.set_points_smoothly(list(samples))

        rod.add_updater(swing)

        def follow(m, dt):
            if running[0]:
                m.move_to(tip[0])

        spotlight.add_updater(follow)

        # ── el título ────────────────────────────────────────────────────
        def make_title(s, color):
            t = Tex(s, color=color, size=0.95)
            t.move_to(3.3 * UP)
            return t

        title = make_title(r"E = T + V", "#C8D2DC")

        self.use_composition(
            Composition(
                Layer(background, grid_dim),
                crop(grid_lit, inside=spotlight, feather=0.2),
                Layer(rod, bob1),
                # σ = 0.055 u son 5 px a 720p: los tres niveles de la pirámide
                # (σ, 2σ, 4σ) caben enteros en el kernel, así que el halo es
                # gaussiano de verdad
                Layer(
                    trail,
                    halo,
                    bob2,
                    blend="add",
                    effects=[Bloom(threshold=0.25, intensity=1.8, sigma=0.055)],
                ),
                Layer(title),
            ),
        )

        # «aparecer» = Transform hacia una copia con la opacidad final (FadeIn
        # funde hacia el estado ACTUAL, que aquí es 0)
        def appear(m, op):
            c = m.copy()
            c.set_fill(opacity=op)
            return Transform(m, c)

        self.play(
            AnimationGroup(
                FadeIn(title, shift=0.3 * DOWN),
                appear(bob1, 1.0),
                appear(bob2, 1.0),
                UpdateFromAlphaFunc(halo, lambda m, a: m.set_opacity(0.7 * a)),
            ),
            run_time=1.2,
        )
        running[0] = True
        self.wait(8.0)
        self.play(
            Transform(title, make_title(r"\dot\theta_1, \; \dot\theta_2", "#FFD25E")),
            run_time=1.0,
        )
        self.wait(10.0)

        # congelar ANTES del fundido: si el updater sigue, re-estampa el estilo
        # cada frame y el fundido no se ve
        running[0] = False
        self.play(
            AnimationGroup(
                FadeOut(rod),
                FadeOut(bob1),
                FadeOut(bob2),
                FadeOut(trail),
                FadeOut(title),
                UpdateFromAlphaFunc(halo, lambda m, a: m.set_opacity(0.7 * (1 - a))),
            ),
            run_time=1.8,
        )
        self.wait(0.6)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    PendulumGlow(output=str(here.with_suffix(".mp4")), fps=30, resolution=(1280, 720)).render()
