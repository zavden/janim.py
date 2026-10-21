"""Course 1 · 3.6 — Transforming one formula into another

    TransformMatchingTex(source, target, key_map=None, match_shapes=False, …)

Glyphs that share a KEY morph in pairs; source-only glyphs fade out;
target-only glyphs fade in. Longest keys claim first, so an isolated "x^2"
outranks its own "x", and ties break lexicographically (determinism).
`key_map={"a": "b"}` renames on the way across.

When it ends, THE SCENE HOLDS `target` — the source is consumed (hidden in
`begin`, removed at the end), exactly like manimgl. So keep using `target`
afterwards, not `source`.

Three decisions inside it, each paid for by a bug:

  1. It animates COPIES. The draw loop renders every scene root's family
     with no cross-root dedup, so a live glyph shared between source and
     animation group would be drawn twice and the winding alpha would
     deepen (2a − a²).
  2. It restructures NEITHER formula. Regrouping children orphans every
     external reference — including the memoised key groups you are holding.
  3. The scene swap rides the same protocol as ReplacementTransform, so the
     animation stays ignorant of the scene and behaves identically under
     `play`, a timeline and `render_frame`.

Through LaTeX (Janim's one route) a glyph carries only the keys you gave
with `isolate`/`t2c`; it does not carry its character.

    python examples/tutorial/c1_03_groups_and_text/06_tex_transformations.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.6


class TexTransformations(Scene):
    def construct(self):
        title = Text("matched by key, not by position", size=0.46, color=GREY_A)
        title.to_edge(UP, buff=0.4)
        self.add(title)

        a = Tex(r"a^2 + b^2 = c^2", size=1.3)
        b = Tex(r"c^2 - b^2 = a^2", size=1.3)
        c = Tex(r"c = \sqrt{a^2 + b^2}", size=1.3)
        for mob in (a, b, c):
            mob.move_to(0.3 * UP)

        self.add(a)
        self.play(Write(a), run_time=1.2)
        self.wait(0.5)

        # Every :math glyph already carries its character as a key, so this
        # needs no preparation at all: the a's find the a's, the ² finds the ².
        self.play(TransformMatchingTex(a, b), run_time=1.6)
        self.wait(0.6)
        # From here on the scene holds `b` — carry on with THAT one.
        self.play(TransformMatchingTex(b, c), run_time=1.6)
        self.wait(0.6)

        print(
            "the scene now holds the last formula:",
            any(m is c for m in self.mobjects),
        )


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    TexTransformations(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
