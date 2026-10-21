"""Course 1 · 2.4 — Importing SVG

    SVGMobject(path_or_string, height=2.0, width=None, color=None)

One FLAT child per graphic element (like manimlib), each carrying the file's
`id` as its KEY — so `svg["sun"]` addresses by name and `svg[3]` by
position, and `Transform` pairs child with child.

It takes a FILE PATH or an SVG STRING, which is handy: a diagram you build
in code needs no file at all.

Covered: the full path grammar (M L H V C S Q T A Z), rect/circle/ellipse/
line/polyline/polygon, nested groups with the spec's transform and style
cascade, defs/use/symbol, viewBox, linear and radial gradients (evaluated
per fragment), `<text>` through the font pipeline, and `clipPath` via
`clip_layers` (course 3, chapter 3). Anything unsupported produces ONE
warning — never an exception.

    python examples/tutorial/c1_02_config_and_assets/04_svg_import.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 2.2

# An SVG written as a string: no file, no asset pipeline.
INLINE = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <circle id="head" cx="50" cy="34" r="22" fill="#E8A33D"/>
  <path id="body" d="M 22 92 Q 50 52 78 92 Z" fill="#2C5F8A"/>
  <rect id="bar" x="30" y="86" width="40" height="6" rx="3" fill="#DDDDDD"/>
</svg>
"""


class SVGImport(Scene):
    def construct(self):
        title = Text("SVGMobject: ids become keys", size=0.5, color=GREY_A)
        title.to_edge(UP, buff=0.4)
        self.add(title)

        inline = SVGMobject(INLINE, height=3.0)
        inline.move_to(3.6 * LEFT)

        asset = Path(__file__).resolve().parents[2] / "assets" / "badge.svg"
        badge = SVGMobject(asset, height=3.0)
        badge.move_to(3.6 * RIGHT)

        # Keys starting with `_` are the importer's own bookkeeping (`_clip`,
        # `_clipref:id`, `_clipped:id` — what `clip_layers` reads); yours are
        # the ids from the file.
        def ids(mob):
            return [key for key in mob.get_all_keys() if not key.startswith("_")]

        print("inline children:", len(inline.submobjects), "· ids:", ids(inline))
        print("badge  children:", len(badge.submobjects), "· ids:", ids(badge))

        self.add(inline, badge)
        self.play(
            AnimationGroup(
                FadeIn(inline, shift=0.4 * UP),
                FadeIn(badge, shift=0.4 * UP),
                lag_ratio=0.3,
            ),
            run_time=1.2,
        )

        # Addressing by id: `svg["head"]` is a memoised VGroup of the children
        # carrying that key, so it can be animated like any other mobject.
        self.play(Indicate(inline["head"], scale_factor=1.25), run_time=1.0)
        self.play(
            Indicate(
                badge["sun"],
                scale_factor=1.4,
                color="#FFD25E",
            ),
            run_time=1.0,
        )
        self.wait(0.4)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    SVGImport(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
