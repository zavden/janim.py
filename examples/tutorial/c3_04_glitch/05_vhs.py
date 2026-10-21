"""Course 3 · 4.5 — VHS

    VHS(intensity=0.5, seed=1, rate=2, chroma_bleed=0.15, jitter=0.04,
        noise=0.12, head_switch=0.08)

Video tape: per-LINE horizontal jitter, chroma smearing, tape noise, and the
torn band at the bottom where the head switches.

    chroma_bleed  in SCENE UNITS. The smear keeps each pixel's OWN luma and
                  takes only the neighbours' COLOUR — which is what a tape
                  does, and it means that over a GREYSCALE image the smear
                  changes nothing at all, exactly.
    jitter        also scene units. The measured defaults matter here:
                  0.06 and 0.004 would be 2 px and 0.13 px at 480p — an
                  invisible wobble.
    head_switch   the height of the torn band as a fraction of the frame; the
                  tear starts exactly at that row.
    rate          how many frames the pattern is held for.
    intensity     master dial; 0 is an exact no-op.

    python examples/tutorial/c3_04_glitch/05_vhs.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.6


def panel(x, grey):
    """A colour panel and a grey one, side by side: the chroma smear only touches one."""
    group = VGroup()
    for k in range(5):
        rect = Rectangle(width=0.62, height=2.2)
        if grey:
            c = color_gradient([BLACK, WHITE], 5)[k]
        else:
            c = color_gradient(["#FF3D8B", "#FFD25E", "#39D0FF"], 5)[k]
        rect.set_fill(c, 1.0)
        rect.set_stroke(opacity=0)
        rect.move_to((x - 1.3 + 0.65 * k, 0.3, 0))
        group.add(rect)
    text = Text("greyscale" if grey else "colour", size=0.32, color=GREY_A)
    text.move_to((x, -1.2, 0))
    group.add(text)
    return group


class VHSLesson(Scene):
    def construct(self):
        title = Text(
            "the chroma smear takes colour, never luma",
            size=0.42,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.3)

        caption = Text(
            "left: as rendered · right: VHS(intensity = 0.9)",
            size=0.34,
            color=GREY_B,
        )
        caption.move_to(2.8 * DOWN)

        self.use_composition(
            Composition(
                Layer(panel(-4.6, False), panel(-1.7, True)),
                Layer(
                    panel(1.7, False),
                    panel(4.6, True),
                    effects=[VHS(intensity=0.9, seed=5)],
                ),
                Layer(title, caption),
                background=(0.02, 0.02, 0.03, 1.0),
            ),
        )

        self.wait(2.0)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    VHSLesson(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
