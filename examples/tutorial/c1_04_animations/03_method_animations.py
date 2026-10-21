"""Course 1 · 4.3 — `.animate`: the method-call form

In CE/GL this is `self.play(m.animate.shift(RIGHT).rotate(PI))` — about half
of all `play` calls — and Janim has that exact chainable proxy, which
records method calls. So:

    m.animate(run_time=2).shift(2 * RIGHT).rotate(TAU / 4)
    m.animate.center()                        # a method with no arguments
    tracker.animate.set_value(10.0)           # works on a ValueTracker too
    self.frame.animate.scale(0.5)             # …and on the camera

Under the hood it is exactly what Manim does: a `Transform` towards a COPY
that has had those mutations applied. Three consequences worth internalising:

  1. The copy is built EAGERLY, when you touch `.animate` — ManimGL's proxy.
     Two `.animate` of one mobject share its last target, so chaining over
     the same mobject inside a `Succession` needs `ApplyMethod(m.shift, v)`,
     which builds its copy inside `begin` (lesson 4.4 does exactly that).
  2. Calls keep their keyword arguments: `m.animate.set_color(c)` needs no
     adapter, as in lesson 1.4.
  3. It is a Transform, so it interpolates the END STATE, not the gesture.
     `m.animate.rotate(PI)` moves every point along its chord — for a real
     turn use `Rotate`/`Rotating`.

    python examples/tutorial/c1_04_animations/03_method_animations.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 2.2


class MethodAnimations(Scene):
    def construct(self):
        title = Text(
            "m.animate.f(args...) — the .animate idiom",
            size=0.44,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.35)
        self.add(title)

        box = RoundedRectangle(
            width=1.8,
            height=1.2,
            corner_radius=0.25,
        )
        box.set_fill("#2C5F8A", 1.0)
        box.set_stroke(opacity=0)
        box.move_to(4.0 * LEFT + 1.2 * UP)
        self.add(box)

        # Several mutations in ONE animation: they are applied in order to the
        # copy, and the result is what the mobject travels towards.
        self.play(
            box.animate.shift(4.0 * RIGHT).rotate(TAU / 8).scale(1.3).set_color("#E8A33D"),
            run_time=2.0,
        )

        # A method with no arguments is fine.
        self.play(box.animate.center(), run_time=1.0)

        # It is not limited to geometry: anything that fulfils the
        # interpolation contract works, including a number and the camera
        # frame.
        vt = ValueTracker(0.0)
        counter = DecimalNumber(
            0.0,
            num_decimal_places=2,
            size=0.8,
            color="#7FDD58",
        )
        counter.move_to(2.0 * DOWN)
        counter.add_updater(lambda d: d.set_value(vt.get_value()))
        self.add(vt, counter)
        self.play(
            vt.animate(rate_func=ease_out_cubic).set_value(12.5),
            run_time=1.8,
        )

        self.wait(0.4)
        print("tracker:", vt.get_value(), "· counter shows:", counter.get_value())


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    MethodAnimations(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
