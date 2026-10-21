"""Course 2 · 5.2 — Translating a ManimGL scene

Janim's engine is modelled on ManimGL, so this direction is the closer one:
the rate functions ARE GL's (`smooth` is its quintic, not CE's sigmoid), the
arc geometry has GL's 16 components, `Arrow` is one closed contour like GL's
and not CE's tip-as-a-child, and the camera controls were traced from
`scene.py`. In Janim even the syntax is GL's:

    class Demo(Scene):                          class Demo(Scene):
        def construct(self):                        def construct(self):
            self.frame.set_height(6)                    self.frame.set_frame_height(6)
            tex = Tex(R"\\int_0^1 x^2 dx")               tex = Tex(r"\\int_0^1 x^2 dx")
            self.play(Write(tex))                       self.play(Write(tex))
            self.play(self.frame.animate                self.play(self.frame.animate
                      .scale(0.5))                                .scale_frame(0.5))
            self.embed()                            # bin/janim this_file.py

WHAT IS DIFFERENT, and it is short:

  1. `self.embed()` (the IPython terminal in the middle of a render) becomes
     `bin/janim scene.py` — the live window, which re-runs the file when it
     changes. Space pauses, `,`/`.` step, `←`/`→` jump a second, `[`/`]`
     jump an animation, PgUp/PgDn jump a checkpoint.
  2. `checkpoint_paste()` becomes `self.checkpoint("label")` plus
     `bin/janim render scene.py --from label`. It is anchored to the CLI
     instead of to an editor, and a checkpoint is only trusted while the code
     before the mark is unchanged (manimgl trusts you and will serve stale
     state).
  3. GL's shaders are per-mobject; Janim's effects are per LAYER, which is a
     compositor and not a renderer feature (course 3).
  4. `always_redraw(lambda: …)` is the same call and behaves the same:
     rebuild every frame, adopt with `become`.

    python examples/tutorial/c2_05_from_manim/02_from_manimgl.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 3.0


class FromManimGL(Scene):
    def construct(self):
        # self.frame.set_height(7)
        self.frame.set_frame_height(7.0)

        # tex = Tex(R"\int_0^1 x^2\,dx = \frac{1}{3}")
        # NOTE the height: the frame was set to 7 units, so the visible range is
        # ±3.5 — and an integral with limits is over 2 units tall on its own.
        tex = Tex(r"\int_0^1 x^2\,dx = \frac{1}{3}", size=0.75)
        tex.move_to(2.0 * UP)

        plane = NumberPlane(
            (-4.0, 4.0, 1.0),
            (-2.0, 2.0, 1.0),
            width=8.0,
            height=3.6,
            background_line_color="#25405C",
            faded_opacity=0.12,
        )
        plane.move_to(1.1 * DOWN)

        # tracker = ValueTracker(0.2); dot = always_redraw(lambda: Dot(...))
        t = ValueTracker(0.2)

        def moving_dot():
            x = t.get_value()
            d = Dot(plane.coords_to_point(x, x * x - 1.0), radius=0.11)
            d.set_fill(color="#FFD25E")
            return d

        dot = always_redraw(moving_dot)
        curve = plane.axes.plot(
            lambda x: x * x - 1.0,
            x_range=(-1.6, 1.6),
            color="#58C4DD",
            stroke_width=4.0,
        )

        self.add(plane, curve, tex, t, dot)

        # A checkpoint: everything before it can be skipped with `--from`, and it
        # is the anchor `janim states` reports on.
        self.checkpoint("after_setup")

        self.play(Write(tex), run_time=1.4)
        self.play(ShowCreation(curve), run_time=1.0)
        self.play(t.animate.set_value(1.55), run_time=1.6)

        # self.play(self.frame.animate.scale(0.55).move_to(dot))
        self.play(
            self.frame.animate.scale_frame(0.55).move_to(dot.get_center()),
            run_time=1.6,
        )
        self.wait(0.5)
        self.play(self.frame.animate.reset_frame(), run_time=1.0)
        print("checkpoints recorded in this run: ", [label for label, _ in self.checkpoint_frames], sep="")


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    FromManimGL(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
    print("live preview:  bin/janim preview", here)
