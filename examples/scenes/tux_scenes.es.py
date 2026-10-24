"""Three SVG scenes: a big bang, style rows and compositing."""

import math
from pathlib import Path

import numpy as np

from janim import *
from janim.core.algebra import _muladd_rows, norm

TUX = Path(__file__).resolve().parents[1] / "assets/linux.svg"


def hsv_rgb(hue, saturation):
    """HSV to RGB (hue divided by 60, then sector conversion), vectorized over style rows."""
    hue = np.asarray(hue, dtype=np.float64)
    divided = _muladd_rows(hue, np.float64(1 / 960), hue * np.float64(1 / 64))
    integer = np.trunc(divided).astype(np.int32)
    integer = np.where(divided < 0, integer - 1, integer)
    fraction = divided - integer
    fraction = np.where((integer & 1) == 0, 1 - fraction, fraction)
    selector = np.left_shift(1, integer % 6)
    minimum = 1.0 - saturation
    middle = _muladd_rows(-np.float64(saturation), fraction, np.float64(1))
    maximum = np.ones_like(hue)
    red = np.where((selector & 0b100001) != 0, maximum, np.where((selector & 0b010010) != 0, middle, minimum))
    green = np.where((selector & 0b000110) != 0, maximum, np.where((selector & 0b001001) != 0, middle, minimum))
    blue = np.where((selector & 0b011000) != 0, maximum, np.where((selector & 0b100100) != 0, middle, minimum))
    return np.stack((red, green, blue), axis=-1).astype(np.float32)


def acid_color(index):
    return np.append(hsv_rgb((47.0 * index) % 360.0, 0.9), np.float32(1))


class TuxBigBang(Scene):
    def construct(self):
        title = Text("Tux · big bang por hijos", size=0.45, color=GREY_A).to_edge(UP, buff=0.3)
        tux = SVGMobject(TUX, height=4.6).shift(0.2 * Vec3(DOWN))
        original = tux.copy()
        self.add(title, tux)
        self.wait(0.4)
        center = tux.get_center()
        animations = []
        for index, child in enumerate(tux, 1):
            delta = child.get_center() - center
            length = norm(delta)
            direction = delta / length if length > 1e-6 else np.array((math.cos(0.7 * index), math.sin(0.7 * index), 0), dtype=np.float32)
            distance = 2.0 + 1.6 * ((0.23 * index) % 1.0)
            spin = (1 if index % 2 else -1) * TAU * (0.25 + 0.5 * ((0.37 * index) % 1.0))
            squash = 0.55 + 0.9 * ((0.61 * index) % 1.0)
            animations.append(child.animate.shift(distance * direction.astype(np.float64)).rotate(spin).scale(squash))
        self.play(AnimationGroup(*animations, lag_ratio=0.03), run_time=1.7)
        self.wait(0.3)
        acid = SVGMobject(TUX, height=4.6).shift(0.2 * Vec3(DOWN)).rotate(TAU / 28)
        for index, child in enumerate(acid, 1):
            child.fill_rgba[:, :3] = acid_color(index + 3)[:3]
        self.play(Transform(tux, acid), run_time=1.4)
        self.wait(0.4)
        self.play(Transform(tux, original), run_time=1.2)
        self.wait(0.6)


class TuxStyleRows(Scene):
    def construct(self):
        title = Text("Tux · cirugía de filas de estilo en vivo", size=0.45, color=GREY_A).to_edge(UP, buff=0.3)
        tux = SVGMobject(TUX, height=5).shift(0.2 * Vec3(DOWN))
        pristine = tux.copy()
        self.add(title, tux)
        elapsed = 0.0

        def recolor(mob, dt):
            nonlocal elapsed
            elapsed += dt
            for child in mob:
                points = child.points.astype(np.float64)
                hue = 360.0 * ((0.21 * (points[:, 0] + 0.6 * points[:, 1]) + 0.35 * elapsed) % 1.0)
                child.fill_rgba[:, :3] = hsv_rgb(hue, 0.85)

        tux.add_updater(recolor)
        self.wait(3)
        tux.clear_updaters()
        neon = pristine.copy()
        for index, child in enumerate(neon, 1):
            child.set_fill(opacity=0).set_stroke(acid_color(2 * index), opacity=1, width=3)
        self.play(Transform(tux, neon), run_time=1.3)
        self.wait(0.5)
        self.play(Transform(tux, pristine), run_time=1.3)
        self.wait(0.6)


class TuxLayers(Scene):
    def construct(self):
        title = Text("Tux · capas: glow aditivo + blur animado + zoom", size=0.42, color=GREY_A).to_edge(UP, buff=0.3)
        front = SVGMobject(TUX, height=4.2).shift(0.3 * Vec3(DOWN))
        back = SVGMobject(TUX, height=7.8).shift(0.3 * Vec3(DOWN))
        halo = Blur(0.22)
        self.use_composition(
            Composition(
                Layer(back, blend="add", opacity=0.55, effects=[halo]),
                Layer(front, effects=[Bloom(threshold=0.55, intensity=0.9, sigma=0.10)]),
                Layer(title),
                background=(0.05, 0.04, 0.09, 1),
            ),
        )
        elapsed = 0.0

        def breathe(mob, dt):
            nonlocal elapsed
            elapsed += dt
            mob.rotate(0.25 * dt)
            halo.sigma = 0.22 + 0.12 * math.sin(1.6 * elapsed)

        back.add_updater(breathe)
        self.wait(1.2)
        self.play(self.frame.animate.scale(0.72), run_time=1.8)
        self.wait(1)
        self.play(self.frame.animate.scale(1 / 0.72), run_time=1.8)
        self.wait(0.8)
