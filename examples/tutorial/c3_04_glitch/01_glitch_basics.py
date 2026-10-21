"""Course 3 · 4.1 — Glitch

    Glitch(intensity=0.5, seed=1, rate=3, rgb_shift=0.05, slices=12, block=0.3)

Three ingredients in one pass: horizontal BANDS displaced sideways, a few
BLOCKS jumping harder, and the RGB channels pulled apart.

    intensity   the master dial. **0 is an exact no-op** — the pass is
                skipped, so the layer comes out bit for bit as it went in.
    rate        how many FRAMES the pattern is held for. Re-rolling every
                frame reads as television snow; 2–4 reads as a glitch.
    slices      how many horizontal bands the frame is cut into.
    rgb_shift,  in SCENE UNITS, so the look survives the resolution. The
    block       defaults were MEASURED, not guessed: 0.01 and 0.04 would be
                0.34 px and 1.35 px at 480p — an invisible separation and
                one-pixel "blocks" that read as salt-and-pepper.
    seed        the pattern. It is mixed with the effect's TYPE NAME before
                reaching the shader, so a Glitch(seed=1) and a Grain(seed=1)
                on the same layer do not draw the same numbers.

And it is DETERMINISTIC: the randomness is a hash of (pixel, frame, seed),
never `random()`, so two renders agree byte for byte.

    python examples/tutorial/c3_04_glitch/01_glitch_basics.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.2


def card(x):
    """A broadcast-looking card: flat colour, hard edges, readable text."""
    group = VGroup()
    plate = Rectangle(width=2.9, height=2.0)
    plate.set_fill("#1F3B5C", 1.0)
    plate.set_stroke(opacity=0)
    plate.move_to((x, 0.2, 0))
    group.add(plate)
    bar = Rectangle(width=2.9, height=0.45)
    bar.set_fill("#FF3D8B", 1.0)
    bar.set_stroke(opacity=0)
    bar.move_to((x, 0.95, 0))
    group.add(bar)
    text = Text("SIGNAL", size=0.5, color=WHITE)
    text.move_to((x, 0.05, 0))
    group.add(text)
    return group


class GlitchBasics(Scene):
    def construct(self):
        title = Text(
            "bands, blocks and an RGB split — one pass",
            size=0.42,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.3)

        cases = (
            ("intensity = 0", Glitch(intensity=0.0)),
            ("0.35", Glitch(intensity=0.35, seed=3)),
            ("0.8", Glitch(intensity=0.8, seed=3)),
            (
                "0.8, slices = 40",
                Glitch(
                    intensity=0.8,
                    seed=3,
                    slices=40,
                ),
            ),
        )

        layers = []
        labels = []
        for k, (name, fx) in enumerate(cases, start=1):
            x = -5.1 + 3.4 * (k - 1)
            layers.append(Layer(card(x), effects=[fx]))
            label = Text(name, size=0.3, color=GREY_B)
            label.move_to((x, -1.6, 0))
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
    GlitchBasics(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
