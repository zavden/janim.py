"""Course 3 · 3.6 — The animated spotlight

A mask's mobjects are updated like everything else, so a mask can FOLLOW
something. That is the whole trick behind a spotlight: a hidden grid, a
feathered circle chasing the subject, and the grid is revealed only where
the circle is.

Two practical notes:

  · PARK THE SHAPE OFF SCREEN to start with (`spot.move_to((99, 99, 0))`).
    A mask always cuts, so before the spotlight "turns on" you want its
    coverage to be nowhere — and moving it away is cheaper and clearer than
    animating its radius from zero.
  · The masking shape is never drawn, so its colour does not matter; only
    its alpha does. Give it `fill_opacity=1.0` and forget about it.

    python examples/tutorial/c3_03_masks/06_animated_spotlight.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 2.6


class AnimatedSpotlight(Scene):
    def construct(self):
        title = Text(
            "the mask follows: a spotlight",
            size=0.44,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.3)

        # The hidden layer: a grid of numbers nobody can see until the light hits.
        hidden = VGroup()
        for i in range(9):
            for j in range(5):
                t = Text(str((i * 5 + j) % 10), size=0.42, color="#7FDD58")
                t.move_to((-5.6 + 1.4 * i, 1.9 - 0.95 * j, 0))
                hidden.add(t)

        # The subject the light follows.
        ball = Circle(radius=0.28)
        ball.set_fill(color="#FFD25E", opacity=1.0)
        ball.set_stroke(opacity=0)
        ball.move_to((-4.5, 0, 0))

        spot = Circle(radius=1.5, fill_opacity=1.0)
        spot.move_to((99, 99, 0))          # parked: nothing is revealed
        spot.add_updater(lambda m: m.move_to(ball.get_center()))

        self.use_composition(
            Composition(
                crop(
                    hidden,
                    inside=spot,
                    feather=0.28,
                ),
                Layer(ball),
                Layer(title),
                background=(0.02, 0.03, 0.05, 1),
            ),
        )

        # The updater is registered but the spotlight is parked, so the first
        # frames show nothing. Moving the ball is what turns it on.
        self.wait(0.4)
        self.play(
            ball.animate(rate_func=ease_in_out_sine).move_to((4.6, 1.4, 0)),
            run_time=2.2,
        )
        self.play(
            ball.animate(rate_func=ease_in_out_sine).move_to((-1.2, -1.7, 0)),
            run_time=1.8,
        )
        self.wait(0.5)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    AnimatedSpotlight(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
