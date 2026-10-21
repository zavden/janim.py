"""Course 2 · 2.1 — The anatomy of an animation

An animation is a class that subclasses `Animation` and answers three verbs:

    begin()                 snapshot whatever you will need; put α = 0
    interpolate(alpha)      the whole animation, as a function of α
    finish()                the default is `interpolate(1)` + cleanup

`Animation.__init__` gives you `mobject`, `run_time`, `rate_func`,
`lag_ratio`, `remover` and `starting_mobject` for free, and with them
`get_run_time` and `is_remover` already work on your class.

TWO RULES, both learned by breaking them:

  1. SNAPSHOT IN `begin`, never in the constructor. `play` may be handed
     your animation long after it was built — inside a `Succession`, for
     instance — and the state to capture is the one at that moment.
  2. APPLY THE RATE FUNCTION YOURSELF, or inherit it: `Transform` applies it
     through `get_sub_alpha` (which also spreads `lag_ratio` over the family).
     If your animation does neither, `rate_func` silently does nothing.

Nothing here knows about the scene. That is deliberate: it is why the same
animation behaves identically under `play`, `render_frame` and the render
farm.

    python examples/tutorial/c2_02_custom_animations/01_anatomy.py
"""

from pathlib import Path

import numpy as np

from janim import *


class Unroll(Animation):
    """Reveal `m` by sliding a straight cut across it: at α the mobject is squashed
    to `α` of its width against `from_edge` and grows out. Not a Transform — the
    target is recomputed each frame from the snapshot, so it composes with any
    rate function and never accumulates drift."""

    def __init__(self, mobject, from_edge=LEFT, **kwargs):
        super().__init__(mobject, **kwargs)
        self.from_edge = np.array(from_edge, dtype=np.float32)
        self.snapshot = None                  # filled in begin, RULE 1

    def begin(self):
        self.snapshot = self.mobject.copy()   # RULE 1: the state as of NOW
        self.interpolate(0.0)
        return self

    def interpolate(self, alpha):
        a = self.rate_func(min(max(alpha, 0), 1))   # RULE 2: apply it yourself
        m, s = self.mobject, self.snapshot
        m.become(s)                                   # back to the snapshot…
        edge = s.get_bounding_box_point(self.from_edge)
        m.scale((max(a, 1e-3), 1.0, 1.0), about_point=edge)   # …then squash
        return self

# `finish` has a perfectly good default (interpolate at α = 1); it is worth
# overriding only when there is cleanup to do — a remover restoring the
# mobject it consumed, say.


PREVIEW_T = 1.4


class Anatomy(Scene):
    def construct(self):
        title = Text(
            "an animation is three verbs",
            size=0.46,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.35)
        self.add(title)

        bars = VGroup()
        for k, colour in enumerate(("#58C4DD", "#7FDD58", "#E8A33D", "#FF5E5E"), start=1):
            b = Rectangle(width=3.0 + 0.9 * k, height=0.7)
            b.set_fill(color=colour, opacity=1.0)
            b.set_stroke(opacity=0)
            bars.add(b)
        bars.arrange(
            DOWN,
            buff=0.35,
            aligned_edge=LEFT,
        )
        bars.move_to(0.3 * DOWN)
        self.add(bars)

        # The custom animation, with every Animation dial working on it:
        # run_time, rate_func and lag_ratio all come for free.
        self.play(
            LaggedStart(
                *(Unroll(b, rate_func=ease_out_cubic) for b in bars.submobjects),
                lag_ratio=0.18,
            ),
            run_time=2.2,
        )
        self.wait(0.5)

        # …and it composes with the rest, because it speaks the same protocol.
        self.play(
            AnimationGroup(
                *(
                    Unroll(
                        b,
                        from_edge=RIGHT,
                        rate_func=lambda t: 1 - smooth(t),
                    )
                    for b in bars.submobjects
                ),
                lag_ratio=0.1,
            ),
            run_time=1.4,
        )
        print("Unroll answers get_run_time: ", Unroll(bars[0], run_time=3.0).get_run_time(), " s", sep="")


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    Anatomy(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
