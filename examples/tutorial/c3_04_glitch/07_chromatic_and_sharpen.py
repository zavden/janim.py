"""Course 3 · 4.7 — ChromaticAberration and Sharpen

    ChromaticAberration(amount=0.1)       scene units, AT THE CORNER
    Sharpen(amount=0.6, sigma=0.05)

`ChromaticAberration` is the clean cousin of `Glitch`'s RGB split: the
separation is RADIAL — zero at the centre, growing with the distance to it —
like a real lens. `amount` is the separation at the CORNER, measured rather
than guessed: 0.05 puts 1.1 px there at 320p and nothing at all near the
middle. Use it at tiny values as a "photographic" finish, or wide as an
effect.

`Sharpen` is an unsharp mask: `src + amount·(src − blur)`, reusing the same
Gaussian rather than writing a second one. Over a UNIFORM region the blur
equals the source, so the effect is the exact identity there — which is what
makes it safe to leave on: it touches edges and nothing else.

`sigma` sets which SCALE of detail is enhanced: small σ sharpens fine
texture, large σ gives the halo-ish "local contrast" look.

    python examples/tutorial/c3_04_glitch/07_chromatic_and_sharpen.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.2


def chart(x):
    """A pattern with detail at two scales and a flat area, to see both effects."""
    group = VGroup()
    flat = Rectangle(width=2.6, height=0.9)
    flat.set_fill("#3D7BC0", 1.0)
    flat.set_stroke(opacity=0)
    flat.move_to((x, 1.35, 0))
    group.add(flat)
    for k in range(12):
        line = Line((x - 1.25 + 0.23 * k, -0.1, 0), (x - 1.25 + 0.23 * k, 0.75, 0))
        line.set_stroke(WHITE, width=2.5)
        group.add(line)
    ring = Circle(radius=0.75)
    ring.set_stroke("#FFD25E", width=4.0)
    ring.set_fill(opacity=0)
    ring.move_to((x, -1.15, 0))
    group.add(ring)
    return group


class ChromaticAndSharpen(Scene):
    def construct(self):
        title = Text("radial split · unsharp mask", size=0.44, color=GREY_A)
        title.to_edge(UP, buff=0.3)

        cases = (
            ("as rendered", []),
            ("ChromaticAberration(0.05)", [ChromaticAberration(0.05)]),
            ("…(0.25)", [ChromaticAberration(0.25)]),
            ("Sharpen(1.4, sigma = 0.03)", [Sharpen(1.4, sigma=0.03)]),
        )

        layers = []
        labels = []
        for k, (name, fx) in enumerate(cases, start=1):
            x = -5.1 + 3.4 * (k - 1)
            layers.append(Layer(chart(x), effects=fx))
            label = Text(name, size=0.26, color=GREY_B)
            label.move_to((x, -2.4, 0))
            labels.append(label)
        layers.append(Layer(title, *labels))

        self.use_composition(
            Composition(
                *layers,
                background=(0.02, 0.03, 0.05, 1.0),
            ),
        )
        self.wait(1.5)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    ChromaticAndSharpen(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
