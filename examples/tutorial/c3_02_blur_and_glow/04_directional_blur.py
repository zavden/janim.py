"""Course 3 · 2.4 — DirectionalBlur

    DirectionalBlur(sigma, angle)      sigma in scene units, angle in radians

A ONE-dimensional Gaussian along `angle`. Half the cost of a full blur, and
it reads as SPEED: a shape smeared along its direction of travel is what the
eye expects from something moving fast.

It is not motion blur. Motion blur (chapter 5) averages several exposures of
the scene as the state advances, so it smears every object along its own
path, curves included. This one smears the whole layer along one straight
direction. Use it when the direction is obvious and the cost matters — a
speed line, a wipe, a horizontal scan — and motion blur when the truth
matters.

`angle` is a plain field, so animating it sweeps the smear around.

    python examples/tutorial/c3_02_blur_and_glow/04_directional_blur.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 2.0


class DirectionalBlurLesson(Scene):
    def construct(self):
        title = Text("a one-dimensional Gaussian reads as speed", size=0.42, color=GREY_A)
        title.to_edge(UP, buff=0.3)

        def rocket(x, y):
            """A little rocket: a triangle and two dots."""
            g = VGroup()
            t = Triangle(radius=0.5)
            t.rotate(-PI / 2)
            t.set_fill("#FFD25E", 1.0)
            t.set_stroke(opacity=0)
            t.move_to((x, y, 0))
            g.add(t)
            for dx in (-0.55, -0.95):
                d = Circle(radius=0.16)
                d.set_fill("#FF5E5E", 1.0)
                d.set_stroke(opacity=0)
                d.move_to((x + dx, y, 0))
                g.add(d)
            return g

        still = rocket(-3.6, 1.2)
        smear = rocket(-3.6, -1.2)
        swept = rocket(3.4, 0.0)

        l1 = Text("as rendered", size=0.3, color=GREY_B)
        l1.move_to((-3.6, 2.1, 0))
        l2 = Text("DirectionalBlur(0.12, angle = 0)", size=0.3, color=GREY_B)
        l2.move_to((-3.6, -2.3, 0))
        l3 = Text("…with the angle animated", size=0.3, color=GREY_B)
        l3.move_to((3.4, -2.3, 0))

        spin = DirectionalBlur(0.12, 0.0)
        clock = VGroup()

        def sweep(m, dt):
            if dt <= 0:
                return
            spin.angle = 0.9 * self.t

        clock.add_updater(sweep)
        self.add(clock)

        self.use_composition(
            Composition(
                Layer(still),
                Layer(smear, effects=[DirectionalBlur(0.12, 0.0)]),
                Layer(swept, effects=[spin]),
                Layer(title, l1, l2, l3),
                background=(0.02, 0.03, 0.05, 1),
            ),
        )

        self.wait(3.0)
        print("swept angle at the end:", round(spin.angle / DEG, 1), "°")


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    DirectionalBlurLesson(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
