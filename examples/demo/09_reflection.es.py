"""Demo 09 · EL REFLEJO — un título sobre el agua, con ondas de verdad

El reflejo es una copia volteada del título y de la luna en una capa propia,
y esa capa lleva cuatro cosas que Manim no puede darle:

  · `Wave` con la fase animada desde un updater: las uv se desplazan con un
    seno que viaja — el agua se mueve, y el reflejo con ella;
  · `Blur`, porque un reflejo nunca es tan nítido como el original;
  · `opacity` de capa, para atenuarlo entero de una vez;
  · una `Mask` con `feather` grande: la cobertura cae suavemente hacia el
    fondo, que es como se apaga un reflejo con la distancia.

La luna y las estrellas van en una capa `"add"` con `Bloom` (el glow del
cielo), y un `Vignette` en una capa de ajuste cierra el plano. La luna sube
por updater y su reflejo baja: dos mobjects, un solo movimiento.

En `mirror` y en las estrellas reflejadas la cuenta `2 * WATERLINE - y` se
hace con `float(y)`: en numpy 2, `float - np.float32` se quedaría en float32
y aquí hace falta Float64.

    bin/janim render examples/demo/09_reflection.py -ql
"""

import math
from pathlib import Path

import numpy as np

from janim import *

WATERLINE = -0.2


def mirror(m):
    """La copia especular de `m` respecto a la línea del agua."""
    r = m.copy()
    r.flip(axis=RIGHT)
    c = m.get_center()
    r.move_to(np.array((c[0], 2 * WATERLINE - float(c[1]), c[2]), dtype=np.float32))
    return r


def frac(x):
    """Parte fraccionaria: la secuencia R2 (Roberts) reparte las estrellas sin filas."""
    return x - math.floor(x)


class Reflection(Scene):
    def construct(self):
        # ── el cielo ─────────────────────────────────────────────────────
        title = Text("Janim", font="DejaVu Sans", size=1.7)
        title.set_fill_by_gradient("#FFF1C1", "#FFB36B")
        title.move_to((0, WATERLINE + 0.95, 0))

        moon = Circle(radius=0.5, fill_opacity=1.0)
        moon.set_fill("#FFF4D6", opacity=1.0)
        moon.set_stroke(opacity=0)
        moon.move_to((4.6, WATERLINE + 2.5, 0))

        star_points = [
            np.array(
                (
                    -6.6 + 13.2 * frac(0.7548777 * k),
                    WATERLINE + 0.7 + 3.2 * frac(0.5698403 * k),
                    0,
                ),
                dtype=np.float32,
            )
            for k in range(1, 91)
        ]
        stars = GlowDots(
            star_points,
            color=WHITE,
            radius=0.035,
            glow_factor=1.5,
        )

        # ── el agua y los reflejos ───────────────────────────────────────
        water = Rectangle(width=16.0, height=4.0)
        water.set_fill("#04081A", opacity=1.0)
        water.set_stroke(opacity=0)
        water.move_to((0, WATERLINE - 2.0, 0))

        title_r = mirror(title)
        moon_r = mirror(moon)
        stars_r = GlowDots(
            [np.array((p[0], 2 * WATERLINE - float(p[1]), 0), dtype=np.float32) for p in star_points],
            color=WHITE,
            radius=0.035,
            glow_factor=1.5,
        )

        # la cobertura del reflejo: 1 junto a la orilla, y cae con la distancia
        fade = Rectangle(width=16.0, height=3.2)
        fade.set_fill(WHITE, opacity=1.0)
        fade.set_stroke(opacity=0)
        fade.move_to((0, WATERLINE - 1.0, 0))

        ripple = Wave(
            amplitude=0.035,
            wavelength=0.55,
            angle=TAU / 4,
            phase=0.0,
        )

        subtitle = Text(
            "an animation engine with a compositor, in Python",
            size=0.34,
            color=GREY_B,
        )
        subtitle.to_edge(DOWN, buff=0.3)

        self.use_composition(
            Composition(
                Layer(
                    stars,
                    moon,
                    blend="add",
                    effects=[Bloom(threshold=0.6, intensity=1.0, sigma=0.12)],
                ),
                Layer(title),
                Layer(water),
                Layer(
                    stars_r,
                    moon_r,
                    title_r,
                    opacity=0.55,
                    effects=[ripple, Blur(0.025)],
                    mask=Mask(fade, feather=0.7),
                ),
                Layer(subtitle),
                Layer(effects=[Vignette(amount=0.45, radius=0.5, feather=0.5)]),
                background=(0.03, 0.04, 0.11, 1),
            ),
        )

        # el agua se mueve y la luna sube (su reflejo, baja)
        def tide(m, dt):
            if not dt > 0:
                return
            ripple.phase += 2.4 * dt
            moon.shift(np.array((0, 0.03 * dt, 0), dtype=np.float32))
            moon_r.shift(np.array((0, -0.03 * dt, 0), dtype=np.float32))

        clock = VGroup()
        clock.add_updater(tide)
        self.add(clock)

        self.play(
            AnimationGroup(
                FadeIn(title, shift=0.25 * UP),
                FadeIn(title_r, shift=0.25 * DOWN),
            ),
            run_time=1.8,
        )
        self.play(FadeIn(subtitle), run_time=0.8)
        self.wait(8.0)
        self.play(
            AnimationGroup(
                FadeOut(title),
                FadeOut(title_r),
                FadeOut(subtitle),
            ),
            run_time=1.4,
        )
        self.wait(0.8)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    Reflection(output=str(here.with_suffix(".mp4")), fps=30, resolution=(1280, 720)).render()
