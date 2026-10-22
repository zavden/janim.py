"""Course 1 · 6.4 — Vector fields and stream lines

    VectorField(func, axes, density=…, magnitude_range=…, stroke_width=…)
    TimeVaryingVectorField(lambda coords, t: …, axes, …)
    vf.update_vectors()                 re-lay the arrows after a change
    StreamLines(func, axes, density=…, solution_time=…, dt=…, magnitude_range=…,
                color_by_magnitude=…, taper_stroke_width=…)
    AnimatedStreamLines(sl, time_width=…, lag_range=…)
    ode_solution_points(func, state0, time, dt=…)

`func` is pointwise over COORDINATES: `lambda c: (fx, fy)`. A whole field is
ONE VMobject — every arrow is 8 points and its head is a per-point
stroke-width pattern, so a dense field costs one draw call. Long vectors
clamp smoothly with tanh instead of overlapping their neighbours, and
colour follows the coordinate-space magnitude through the 3b1b colormap.

Two things ManimGL cannot promise here, and this engine does:
  · the stream-line seeds and the flow phases come from a COUNTER HASH,
    not from np.random — the same scene gives the same frames in any
    process, so scrubbing and the render farm both work;
  · the integrator is a fixed-step RK4 with no external dependency, checked
    against the CLOSED FORM (the rotation field's lines are circles to
    0.03%).

    python examples/tutorial/c1_06_plots_and_updaters/04_vector_fields.py
"""

from pathlib import Path

from janim import *
from janim.math import cos

PREVIEW_T = 5.8


class VectorFields(Scene):
    def construct(self):
        axes = Axes(
            (-4.0, 4.0, 1.0),
            (-3.0, 3.0, 1.0),
            width=11.0,
            height=8.0,
            color="#37506B",
            stroke_width=2.0,
        )

        # A time-varying field: the classic rotation, breathing with cos(t/2).
        # The updater it installs advances `vf.time` and re-lays every arrow.
        # `cos` comes from janim.math (Julia Base's math functions).
        vf = TimeVaryingVectorField(
            lambda c, t: (cos(0.5 * t) * -c[1], cos(0.5 * t) * c[0]),
            axes,
            density=2.0,
            magnitude_range=(0.0, 3.0),
        )
        self.add(axes, vf)

        # Stream lines are the same field INTEGRATED: seeds on the grid
        # (hash-jittered), each line a smoothed RK4 solution, coloured by the
        # local magnitude. AnimatedStreamLines turns them into travelling
        # packets — a gaussian window over the per-point stroke widths; the
        # points themselves never move.
        sl = StreamLines(
            lambda c: (-c[1], c[0]),
            axes,
            density=1.0,
            solution_time=3.0,
            magnitude_range=(0.0, 3.0),
            stroke_width=2.0,
        )
        self.add(AnimatedStreamLines(sl))

        hud = Text("d/dt (x, y) = ω(t) · (-y, x)", size=0.4, color=GREY_A)
        hud.to_corner(UL, buff=0.35)
        hud.fix_in_frame()
        self.add(hud)

        self.wait(6.5)
        print(
            "arrows: ",
            len(vf.sample_coords),
            " · lines: ",
            len(sl),
            " · points per line: ",
            len(sl[0].points),
            sep="",
        )


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    VectorFields(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
