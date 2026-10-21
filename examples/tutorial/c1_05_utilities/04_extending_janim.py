"""Course 1 · 5.4 — Extending Janim (Manim's "plugins")

Manim has a plugin system: packages advertise themselves through entry
points and `config` lists which are enabled. Janim has NO such registry, and
there is nothing to install — extension happens through the language's own
mechanism: a subclass of an existing mobject, or a function. A "plugin" is
just a module that does `from janim import *` and defines some.

The four seams, weakest to deepest:

  1. A FUNCTION that builds mobjects. Most of what people call a plugin is
     this: `my_flowchart(steps)` returning a VGroup. Nothing to declare.
  2. A SHAPE: `class Hexagon(VMobject)` plus a constructor. The class IS
     the tag of the shape — course 2, lesson 1.3.
  3. A MOBJECT of your own: implement the interpolation contract
     (`is_interpolable`, `copy`, `interpolate(a, b, α)`, `become`) and every
     animation works on it, Transform included.
  4. An EFFECT: a dataclass, a fragment shader registered with
     `effect_shader` and one `apply_effect.register` — course 2, chapter 6.

What is missing compared with Manim, honestly: discovery. There is no list
of available plugins and no `plugins = […]` to enable them. You import the
module and call it.

This lesson does (1) and (2).

    python examples/tutorial/c1_05_utilities/04_extending_janim.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.8


# ── seam 2: a new shape, with its own class ────────────────────────────────
#
# `VMobject(**kwargs)` builds the empty mobject with its factory style — it is
# what every shape in the engine starts from, and it is public API: the most
# common extension seam needs no reaching into the package.
class Chevron(VMobject):
    """A chevron pointing RIGHT, `width` across and `height` tall."""

    def __init__(
        self,
        width=1.0,
        height=1.2,
        thickness=0.35,
        **kwargs,
    ):
        super().__init__(**kwargs)
        w, h, t = float(width), float(height) / 2, float(thickness)
        self.set_points_as_corners(
            [
                (-w, h, 0),
                (0, 0, 0),
                (-w, -h, 0),
                (-w + t, -h, 0),
                (t, 0, 0),
                (-w + t, h, 0),
                (-w, h, 0),
            ],
        )


# ── seam 1: a function that builds a composite ─────────────────────────────
def step_box(text, width=2.4, colour="#2C5F8A"):
    """A labelled step: a rounded box with text inside, as one VGroup."""
    box = RoundedRectangle(
        width=width,
        height=1.0,
        corner_radius=0.18,
    )
    box.set_fill(color=colour, opacity=1.0)
    box.set_stroke(opacity=0)
    lab = Text(text, size=0.34)
    lab.move_to(box.get_center())
    return VGroup(box, lab)


def pipeline_diagram(steps):
    """A row of steps with chevrons between them."""
    g = VGroup()
    for k, s in enumerate(steps):
        g.add(step_box(s))
        if k < len(steps) - 1:
            ch = Chevron(
                width=0.5,
                height=0.7,
                thickness=0.18,
            )
            ch.set_fill(color="#FFD25E", opacity=1.0)
            ch.set_stroke(opacity=0)
            g.add(ch)
    g.arrange(RIGHT, buff=0.25)
    return g


class ExtendingJanim(Scene):
    def construct(self):
        title = Text(
            "a plugin is a package that adds methods",
            size=0.44,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.35)
        self.add(title)

        diagram = pipeline_diagram(["parse", "layout", "render"])
        diagram.scale(0.95)
        diagram.move_to(0.5 * UP)

        note = Text(
            "Chevron is a VMobject{:Chevron} — real dispatch, no inheritance",
            size=0.32,
            color=GREY_C,
        )
        note.move_to(1.9 * DOWN)

        self.add(diagram, note)
        self.play(
            LaggedStart(
                *(FadeIn(part, shift=0.3 * RIGHT) for part in diagram.submobjects),
                lag_ratio=0.2,
            ),
            run_time=2.0,
        )
        self.play(Write(note), run_time=1.0)

        # The new shape is a first-class mobject: it transforms like any other.
        lone = Chevron(
            width=1.6,
            height=2.0,
            thickness=0.5,
        )
        lone.set_fill(color="#7FDD58", opacity=1.0)
        lone.set_stroke(opacity=0)
        lone.move_to(4.6 * LEFT + 0.4 * UP)
        self.play(GrowFromCenter(lone), run_time=0.8)
        print(
            "tag: ",
            type(lone).__name__,
            " · points: ",
            lone.get_num_points(),
            " · subpaths: ",
            len(lone.get_subpaths()),
            sep="",
        )
        self.wait(0.4)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    ExtendingJanim(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
