"""The SVG-import scene, including its text and key selections."""

from pathlib import Path

from janim import *


INLINE = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <circle id="head" cx="50" cy="34" r="22" fill="#E8A33D"/>
  <path id="body" d="M 22 92 Q 50 52 78 92 Z" fill="#2C5F8A"/>
  <rect id="bar" x="30" y="86" width="40" height="6" rx="3" fill="#DDDDDD"/>
</svg>
"""


class SVGImport(Scene):
    def construct(self):
        title = Text("SVGMobject: ids become keys", size=0.5, color=GREY_A).to_edge(UP, buff=0.4)
        self.add(title)
        inline = SVGMobject(INLINE, height=3.0).move_to(3.6 * LEFT)
        asset = Path(__file__).resolve().parents[2] / "assets/badge.svg"
        badge = SVGMobject(asset, height=3.0).move_to(3.6 * RIGHT)
        self.add(inline, badge)
        self.play(
            AnimationGroup(FadeIn(inline, shift=0.4 * UP), FadeIn(badge, shift=0.4 * UP), lag_ratio=0.3),
            run_time=1.2,
        )
        self.play(Indicate(inline["head"], scale_factor=1.25), run_time=1.0)
        self.play(Indicate(badge["sun"], scale_factor=1.4, color="#FFD25E"), run_time=1.0)
        self.wait(0.4)
