"""Course 1 · 6.2 — 3D plots

    ThreeDAxes(x_range, y_range, z_range, width=…, height=…, depth=…)
    ax.c2p(x, y, z)
    Surface(uv_func, u_range=…, v_range=…, resolution=…, color=…, opacity=…, shading=…)

A `Surface` is a uv mesh: `resolution` samples of `uv_func`, triangulated.
Normals come from the ε-steps in u and v, and each one travels as a SECOND
point (`d_normal_point = p + nudge·n̂`), so `shift` and `rotate` transform
the normal for free and the shader recovers it by subtraction.

The three 3D switches:

    self.frame.reorient(theta_deg, phi_deg, gamma_deg, center=…, height=…)
    m.apply_depth_test()   join the z-buffer (real occlusion). 2D mobjects do
                           NOT by default — in 2D, ordering IS the answer.
    m.fix_in_frame()       ignore the camera: HUD, titles, labels that must
                           stay put while the world turns.
    m.set_shading(reflectiveness=…, gloss=…, shadow=…)

    python examples/tutorial/c1_06_plots_and_updaters/02_plots_3d.py
"""

from pathlib import Path

from janim import *
from janim.math import cos, hypot, sin, step_range

PREVIEW_T = 2.4


def ripple_point(u, v):
    """z = sin(r)/r — the classic ripple, sampled as a uv patch."""
    r = hypot(u, v) + 1e-6
    return (u, v, 1.6 * sin(2 * r) / (1 + r))


class Plots3D(Scene):
    def construct(self):
        # The camera first: an isometric-ish view of the world.
        self.frame.reorient(-50.0, 68.0, height=9.0)

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

        # z = sin(r)/r — the classic ripple, sampled as a uv patch. `hypot` and
        # `sin` come from janim.math (Julia Base's math functions),
        # so every vertex is the same on any machine.
        ripple = Surface(
            ripple_point,
            u_range=(-3.0, 3.0),
            v_range=(-3.0, 3.0),
            resolution=(81, 81),
            color="#2C5F8A",
            opacity=0.92,
            shading=(0.35, 0.35, 0.4),
        )
        ripple.apply_depth_test()

        # A parametric curve through the same space, placed with c2p.
        # `step_range` samples the range in twice the precision.
        helix = VMobject()
        helix.set_points_as_corners(
            [
                axes.coords_to_point(2.2 * cos(t), 2.2 * sin(t), 0.35 * t - 1.6)
                for t in step_range(0, 2 * TAU, 0.05)
            ],
        )
        helix.set_stroke(color="#FFD25E", width=4.0)
        helix.apply_depth_test()

        # A HUD that ignores the camera entirely.
        hud = Text("z = 1.6 sin(2r) / (1 + r)", size=0.42, color=GREY_A)
        hud.to_corner(UL, buff=0.4)
        hud.fix_in_frame()

        self.add(axes, ripple, helix, hud)
        self.play(
            AnimationGroup(
                FadeIn(hud),
                ShowCreation(helix),
                lag_ratio=0.3,
            ),
            run_time=1.6,
        )

        # Moving the camera is animating a mobject: `self.frame` is one.
        self.play(self.frame.animate.reorient(25.0, 55.0), run_time=2.4)
        self.wait(0.5)
        print(
            "camera: theta = ",
            round(self.camera.get_theta() / DEG, 1),
            "° · phi = ",
            round(self.camera.get_phi() / DEG, 1),
            "°",
            sep="",
        )


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    Plots3D(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
