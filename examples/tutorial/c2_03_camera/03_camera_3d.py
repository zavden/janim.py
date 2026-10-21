"""Course 2 · 3.3 — The 3D camera

There is no `ThreeDScene` you have to inherit from either: the same camera
does 3D, and it is a QUATERNION camera (the controls traced from ManimGL).

    self.frame.reorient(theta_deg, phi_deg, gamma_deg, center=…, height=…)
    set_euler_angles · increment_euler_angles
    get_theta / get_phi / get_gamma · get_view_matrix
    get_focal_distance / set_focal_distance   (what Dof focuses on)
    get_implied_camera_location               (where the eye actually is)

The angles, in ManimGL's convention: `theta` spins around the z axis (which
way you are looking from), `phi` tilts down from the pole (0° = straight
down onto the xy plane, 90° = edge on), `gamma` rolls the camera about its
own axis.

THE THREE SWITCHES that decide how a mobject behaves in 3D:

    m.apply_depth_test()   join the z-buffer. Off by default: in 2D, ORDER is
                           the answer, and paying for depth would be a tax on
                           every flat scene.
    m.fix_in_frame()       ignore the camera entirely — HUD, titles, legends.
    m.set_shading(reflectiveness=…, gloss=…, shadow=…)

Animating the camera is animating a mobject, so it composes with everything:
`AnimationGroup(self.frame.animate.reorient(…), FadeIn(x))` is ordinary code.

    python examples/tutorial/c2_03_camera/03_camera_3d.py
"""

from pathlib import Path

import numpy as np

from janim import *

PREVIEW_T = 3.0


class Camera3D(Scene):
    def construct(self):
        self.frame.reorient(-35.0, 72.0, height=9.0)

        axes = ThreeDAxes(
            (-3.0, 3.0, 1.0),
            (-3.0, 3.0, 1.0),
            (-2.0, 2.0, 1.0),
            width=6.0,
            height=6.0,
            depth=4.0,
            color="#37506B",
            stroke_width=2.0,
        )
        axes.apply_depth_test()

        ball = Sphere(
            radius=0.9,
            resolution=(81, 41),
            color="#2C5F8A",
        )
        # A Float32 difference, like the mesh itself.
        ball.shift(np.array((-1.6, -1.2, 0.9), dtype=np.float32) - ball.get_center())
        ball.set_shading(
            reflectiveness=0.5,
            gloss=0.4,
            shadow=0.35,
        )
        ball.apply_depth_test()

        ring = Torus(
            r1=1.8,
            r2=0.28,
            resolution=(81, 41),
            color="#E8A33D",
        )
        ring.shift(np.array((1.4, 1.0, 0.4), dtype=np.float32) - ring.get_center())
        ring.apply_depth_test()

        # A flat mobject in a 3D world: without depth testing it draws in list
        # order and will happily sit "through" the sphere. With it, it is
        # occluded properly.
        blade = Rectangle(width=4.0, height=2.2)
        blade.set_fill(color="#7FDD58", opacity=0.55)
        blade.set_stroke(opacity=0)
        blade.rotate(PI / 2, axis=RIGHT)
        blade.apply_depth_test()

        hud = VGroup()
        for s in (
            "apply_depth_test! → real occlusion",
            "fix_in_frame! → this text ignores the camera",
        ):
            hud.add(Text(s, size=0.34, color=GREY_A))
        hud.arrange(
            DOWN,
            buff=0.2,
            aligned_edge=LEFT,
        )
        hud.to_corner(UL, buff=0.35)
        hud.fix_in_frame()

        self.add(axes, blade, ball, ring, hud)
        self.wait(0.6)

        # An orbit: theta sweeps, phi dips. One animation over `self.frame`.
        self.play(
            self.frame.animate(rate_func=ease_in_out_sine).reorient(55.0, 58.0),
            run_time=2.6,
        )
        print(
            "eye at ",
            tuple(round(float(v), 2) for v in self.camera.get_implied_camera_location()),
            " · focal distance ",
            round(float(self.camera.get_focal_distance()), 3),
            sep="",
        )

        # Zoom in 3D is the same verb as in 2D.
        self.play(self.frame.animate.scale_frame(0.65), run_time=1.4)
        self.wait(0.5)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    Camera3D(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
