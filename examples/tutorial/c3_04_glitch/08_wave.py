"""Course 3 · 4.8 — Wave

    Wave(amplitude=0.1, wavelength=1.5, angle=0.0, phase=0.0)

The uv are displaced by a sine: ripples, heat haze, water, a flag.
`amplitude` and `wavelength` are in SCENE UNITS; `angle` is the direction
the wave TRAVELS in, and the displacement is perpendicular to it.

`phase` is a plain field with no clock behind it, so animating it from an
updater is what makes the wave move. That is the whole design: no wall time,
no internal counter, and the wave stays as deterministic as everything else.

One numerical detail worth stealing: the phase is reduced mod 2π on its way
to the shader. The sine is periodic but float32 is not — an updater doing
`phase += dt` for a minute would hand the shader a number big enough to lose
resolution, and the ripples would go blocky. Normalising makes the period
exact and minute ten as sharp as second one.

    python examples/tutorial/c3_04_glitch/08_wave.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 2.4


def grid(x):
    """A grid: the shape that shows a displacement field best."""
    group = VGroup()
    for k in range(-6, 7):
        vertical = Line((x + 0.28 * k, -1.8, 0), (x + 0.28 * k, 1.8, 0))
        vertical.set_stroke("#39D0FF", width=2.0)
        group.add(vertical)
    for k in range(-6, 7):
        horizontal = Line((x - 1.7, 0.28 * k, 0), (x + 1.7, 0.28 * k, 0))
        horizontal.set_stroke("#39D0FF", width=2.0)
        group.add(horizontal)
    return group


class WaveLesson(Scene):
    def construct(self):
        title = Text(
            "animate the phase and the wave travels",
            size=0.42,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.3)

        across = Wave(
            amplitude=0.09,
            wavelength=0.9,
            angle=0.0,
        )
        upwards = Wave(
            amplitude=0.09,
            wavelength=0.9,
            angle=PI / 2,
        )
        diagonal = Wave(
            amplitude=0.14,
            wavelength=1.6,
            angle=PI / 4,
        )

        labels = []
        for x, text in ((-4.6, "angle = 0"), (0.0, "angle = pi/2"), (4.6, "angle = pi/4")):
            label = Text(text, size=0.3, color=GREY_B)
            label.move_to((x, -2.6, 0))
            labels.append(label)

        self.use_composition(
            Composition(
                Layer(grid(-4.6), effects=[across]),
                Layer(grid(0.0), effects=[upwards]),
                Layer(grid(4.6), effects=[diagonal]),
                Layer(title, *labels),
                background=(0.02, 0.03, 0.05, 1.0),
            ),
        )

        def travel(m, dt):
            if not dt > 0:
                return
            for wave, speed in ((across, 2.4), (upwards, -1.8), (diagonal, 1.2)):
                wave.phase = (wave.phase + speed * dt) % TAU   # keep it small, exactly

        clock = VGroup()
        clock.add_updater(travel)
        self.add(clock)

        self.wait(4.0)
        print(
            "phases:",
            tuple(round(w.phase, 3) for w in (across, upwards, diagonal)),
            "— all inside [0, 2pi)",
        )


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    WaveLesson(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
