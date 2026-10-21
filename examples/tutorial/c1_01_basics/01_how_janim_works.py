"""Course 1 · 1.1 — How Janim works

Three ideas, and everything else in the course is a consequence of them.

1. `construct(self)` is a CONTRACT, not a convention. The CLI, the render
   farm and the live window all look up the Scene subclass in your file and
   call its `construct`. Define it and every tool
   works on your scene.
2. A frame is one step of a FIXED clock. `self.play(…, run_time=2)` at 30 fps
   is exactly 60 steps of dt = 1/30 s. Nothing is measured against the wall
   clock, which is what makes two renders of this file give identical
   frames (the mp4 container is x264's: identical too with encoder_threads=1).
3. Each of those steps hands the animation an α — and the αs are the
   MIDPOINTS (k + ½)/n, never 0 and never 1. So the first drawn frame is
   already half a step in, and the exact end pose (α = 1) belongs to
   `finish`, i.e. to the frame AFTER the animation.

    python examples/tutorial/c1_01_basics/01_how_janim_works.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.6


class HowJanimWorks(Scene):
    def construct(self):
        title = Text("A frame is one step of a fixed clock", size=0.55)
        title.to_edge(UP, buff=0.6)
        self.add(title)

        # The sampling line: five ticks at α = 0.1, 0.3, 0.5, 0.7, 0.9 — where a
        # five-frame animation is actually evaluated.
        line = NumberLine(
            (0.0, 1.0, 0.25),
            width=9.0,
            include_numbers=True,
            num_decimal_places=2,
        )
        line.shift(1.2 * DOWN)
        self.add(line)

        n = 5
        samples = VGroup()
        for k in range(n):
            dot = Dot(line.number_to_point((k + 0.5) / n), radius=0.09)
            dot.set_fill(YELLOW)
            samples.add(dot)
        self.add(samples)

        alpha_label = Text("alpha = (k + 1/2) / n", size=0.42, color=YELLOW)
        alpha_label.next_to(line, DOWN, buff=0.55)
        self.add(alpha_label)

        # The thing being animated: a square crossing the same interval.
        box = Square(side_length=0.7)
        box.set_fill(BLUE, 1.0)
        box.set_stroke(opacity=0)
        box.move_to(Vec3(line.number_to_point(0.0)) + 1.4 * Vec3(UP))
        self.add(box)

        self.play(
            LaggedStart(
                *(FadeIn(dot, shift=0.3 * UP) for dot in samples.submobjects),
                lag_ratio=0.25,
            ),
            run_time=1.2,
        )
        # NOTE where `rate_func` goes: on the ANIMATION, not on `self.play`.
        # `play` only knows about time (`run_time`); how α moves inside that
        # time is the animation's business, and that split is why the same
        # animation behaves identically under `play`, a timeline and
        # `render_frame`.
        self.play(
            box.animate(rate_func=linear).move_to(Vec3(line.number_to_point(1.0)) + 1.4 * Vec3(UP)),
            run_time=2.0,
        )
        self.wait(0.6)

        # A3, the agent hook: the scene's state as text, with no GPU involved.
        # `self.last_alphas` is literally the list the last `play` handed the
        # animation — the arithmetic above, measured rather than promised.
        print(f"fps = {self.fps} · frames so far = {self.frames} · t = {round(self.t, 3)} s")
        print(f"alphas of the last play: {[round(a, 3) for a in self.last_alphas[:6]]} …")
        print("\n".join(describe(self).split("\n")[:4]) + "\n  …")


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    HowJanimWorks(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
