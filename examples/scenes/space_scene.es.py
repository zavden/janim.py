"""A wave mesh, orbited by a piloted camera, as a Manim scene."""

import numpy as np

from janim import *
from janim.math import cos, linear_range, sin

X, Y, NU, NV = 6.5, 4.6, 61, 41


class SpaceScene(Scene):
    def construct(self):
        self.camera.reorient(15, 68)
        olas = PlaneXY(
            x_range=(-X, X),
            y_range=(-Y, Y),
            resolution=(NU, NV),
            color="#16324F",
            opacity=1.0,
            shading=(0.45, 0.55, 0.35),
        )
        us = np.asarray(linear_range(-X, X, NU))
        vs = np.asarray(linear_range(-Y, Y, NV))
        U, V = (grid.ravel() for grid in np.meshgrid(us, vs, indexing="ij"))
        clock = [0.0]

        def wave(m, dt):
            clock[0] += dt
            t = clock[0]
            # every vertex at once: janim.math's sin and cos take arrays
            a, b, c = 1.3 * U + 1.8 * t, 1.1 * V + 1.3 * t, 2.1 * U - 1.1 * t
            sa, ca, sb, cb, sc, cc = sin(a), cos(a), sin(b), cos(b), sin(c), cos(c)
            z = -1.35 + 0.22 * sa * cb + 0.10 * sc
            dzx = 0.286 * ca * cb + 0.21 * cc
            dzy = -0.242 * sa * sb
            inv = 1e-3 / np.sqrt(dzx * dzx + dzy * dzy + 1)
            points, nudged = m.points, m.d_normal_points
            points[:, 0], points[:, 1], points[:, 2] = U, V, z
            nudged[:, 0], nudged[:, 1], nudged[:, 2] = U - dzx * inv, V - dzy * inv, z + inv
            m.note_changed_data()

        olas.add_updater(wave)
        esf = Sphere(radius=1.15, color="#58C4DD").shift((-1.9, 0, 0.35))
        tor = Torus(r1=1.5, r2=0.42, color="#F0A045").shift((1.9, 0, -0.1))
        anillos = VGroup()
        for r, col, tilt in ((3.0, "#FFD25E", 0.35), (3.55, "#DD58C4", -0.25)):
            a = Circle(radius=r)
            a.set_stroke(col, width=4.0)
            a.rotate(tilt, axis=RIGHT)
            a.shift((0, 0, 0.25))
            a.apply_depth_test()
            anillos.add(a)

        def spin(m, dt):
            if not dt > 0:
                return
            for a in m.submobjects:
                a.rotate(0.25 * dt, axis=OUT, about_point=(0, 0, 0.25))

        anillos.add_updater(spin)
        camera_clock = [0.0]
        piloto = VGroup()

        def pilot(m, dt):
            if not dt > 0:
                return
            camera_clock[0] += dt
            t = camera_clock[0]
            self.camera.increment_euler_angles(dtheta=0.30 * dt)
            if 14 <= t < 22:
                self.camera.increment_euler_angles(dphi=-0.075 * dt)
            if 40 <= t < 50:
                self.camera.increment_euler_angles(dphi=0.055 * dt)
            if 26 <= t < 34:
                self.camera.scale_frame(1 - 0.095 * dt)
            if 46 <= t < 56:
                self.camera.scale_frame(1 + 0.082 * dt)

        piloto.add_updater(pilot)
        hud = Tex(r"S^2 \times T^2 \subset \mathbb{R}^3", color="#FFFFFF", size=0.85)
        hud.fix_in_frame()
        hud.move_to((-3.9, 3.05, 0))

        def make_hud(source, color):
            return Tex(source, color=color, size=0.85).move_to((-3.9, 3.05, 0))

        marca = Text("Janim")
        marca.set_height(0.32)
        marca.set_fill("#44536A", opacity=0.85)
        marca.fix_in_frame()
        marca.move_to((5.5, -3.25, 0))
        self.add(olas, esf, tor, anillos, marca, piloto)
        self.play(FadeIn(hud, shift=0.25 * Vec3(DOWN)), run_time=1.2)
        self.wait(12.8)
        self.play(Transform(hud, make_hud(r"A_{S^2} = 4\pi r^2", "#58C4DD")), run_time=1.2)
        self.wait(12.8)
        self.play(Transform(hud, make_hud(r"A_{T^2} = 4\pi^2 R\, r", "#F0A045")), run_time=1.2)
        self.wait(12.8)
        self.play(Transform(hud, make_hud(r"\chi(T^2) = 0", "#FFD25E")), run_time=1.2)
        self.wait(10.6)
        self.play(AnimationGroup(FadeOut(hud), FadeOut(marca)), run_time=1.6)
        self.wait(4.6)
