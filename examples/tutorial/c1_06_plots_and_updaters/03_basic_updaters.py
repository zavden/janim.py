"""Course 1 · 6.3 — Updaters

An updater is a function the scene calls once per frame:

    m.add_updater(lambda m, dt: …)     the dt form (time-based)
    m.add_updater(lambda m: …)         the no-dt form (state-based)

Which one you get is decided by ARITY: the engine asks whether the function
takes a second argument. Registration calls it once with dt = 0, which is why
an integrator inside an updater must guard with `if dt > 0` (course 2).

The three companions:

    ValueTracker(x)     a mobject with no points whose state is one number.
                        Animatable, so `vt.animate.set_value(10)` works.
    DecimalNumber(x)    that number as glyphs; `set_value` rebuilds them
                        and RE-CENTRES, so 9.9 → 10.0 does not jump sideways.
    always_redraw(f)    `f()` builds a mobject from scratch every frame and
                        the result is adopted with `become` — so the scene,
                        the compositor and any group keep the SAME identity.

THE RULE that costs an afternoon if you do not know it: a mobject whose
POINTS are created inside an updater must be born with its final style. New
points re-stamp the factory style, so styling it after the fact is undone on
the next frame. `always_redraw` and `TracedPath` handle it for you.

    python examples/tutorial/c1_06_plots_and_updaters/03_basic_updaters.py
"""

from pathlib import Path

from janim import *
from janim.math import cos, sin

PREVIEW_T = 2.4


class BasicUpdaters(Scene):
    def construct(self):
        title = Text(
            "one function, called every frame",
            size=0.44,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.3)
        self.add(title)

        ax = Axes(
            (0.0, 6.5, 1.0),
            (-1.2, 1.2, 0.5),
            width=6.4,
            height=2.6,
            color="#37506B",
            stroke_width=2.0,
        )
        ax.move_to(2.6 * LEFT + 0.6 * DOWN)
        self.add(ax)

        # The tracker drives everything else in this scene.
        t = ValueTracker(0.3)
        self.add(t)

        # `sin` and `cos` come from janim.math (Julia Base's math
        # functions).
        curve = ax.plot(sin, color="#37506B", stroke_width=2.5)
        self.add(curve)

        # always_redraw: the chord is rebuilt from the tracker every frame. Note
        # that the mobject is built COMPLETE (points and style) inside `f`, which
        # is exactly the rule above, made automatic.
        def chord():
            x = t.get_value()
            p = ax.c2p(x, sin(x))
            d = 0.9
            l = Line(
                ax.c2p(x - d, sin(x) - d * cos(x)),
                ax.c2p(x + d, sin(x) + d * cos(x)),
            )
            l.set_stroke(color="#FFD25E", width=3.5)
            return l

        tangent = always_redraw(chord)
        self.add(tangent)

        # A dot with an updater of its own: it reads the tracker, so it needs
        # no dt at all — the no-dt form is the honest signature here.
        dot = Dot(ORIGIN, radius=0.11)
        dot.set_fill(color="#FF5E5E")
        dot.add_updater(lambda m: m.move_to(ax.c2p(t.get_value(), sin(t.get_value()))))
        self.add(dot)

        # A live readout. `add_updater` on a DecimalNumber hands YOU the number.
        readout = DecimalNumber(
            0.0,
            num_decimal_places=2,
            size=0.7,
            color="#58C4DD",
        )
        readout.move_to((4.6, 1.4, 0))
        readout.add_updater(lambda d: d.set_value(cos(t.get_value())))
        caption = Text("slope = cos x", size=0.34, color=GREY_B)
        caption.move_to((4.6, 0.85, 0))
        self.add(readout, caption)

        # A trail, added AFTER what it follows and layered with set_z_index.
        trail = TracedPath(
            dot.get_center,
            stroke_color="#FF5E5E",
            stroke_width=2.5,
            time_traced=3.0,
        )
        self.add(trail)
        trail.set_z_index(-1)

        self.play(t.animate(rate_func=smooth).set_value(6.2), run_time=4.0)
        self.wait(0.5)
        print(
            "tracker ended at ",
            round(t.get_value(), 3),
            " · readout shows ",
            round(readout.get_value(), 3),
            sep="",
        )


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    BasicUpdaters(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
