"""Course 1 · 1.3 — Setters and getters

Setters mutate and return the mobject, so they chain. Getters answer in
SCENE UNITS: the default frame is 8 units tall and 8·16/9 ≈ 14.22 wide,
whatever the pixel resolution is.

    style     m.set_fill(color, opacity) · m.set_stroke(color, width,
              opacity) · m.set_color (both at once) · m.get_color
    place     shift · move_to · to_edge · next_to · center
    size      scale · set_width · set_height · stretch · rescale_to_fit
    turn      rotate(angle, axis=…, about_point=…) · flip
    ask       get_center · get_left/right/top/bottom · get_width/height
              get_bounding_box_point(direction) — the general one

The trap worth naming: `m.set_fill(opacity=0.5)` with NO colour keeps every
row's own colour and moves only the alpha. That is what lets a fade survive a
gradient (lesson 5.1) — and it is why "set the opacity" never silently
repaints your gradient grey.

    python examples/tutorial/c1_01_basics/03_setters_and_getters.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.5


class SettersAndGetters(Scene):
    def construct(self):
        title = Text("getters answer in scene units", size=0.5, color=GREY_A)
        title.to_edge(UP, buff=0.4)

        box = Rectangle(width=4.0, height=2.4)
        box.set_fill("#2C5F8A", 1.0)
        box.set_stroke(BLUE, width=3.0)
        box.shift(0.4 * DOWN)

        # The five bounding-box points every layout call is built on.
        marks = VGroup()
        for point, name in (
            (box.get_left(), "get_left"),
            (box.get_right(), "get_right"),
            (box.get_top(), "get_top"),
            (box.get_bottom(), "get_bottom"),
            (box.get_center(), "get_center"),
        ):
            dot = Dot(point, radius=0.07)
            dot.set_fill(YELLOW)
            marks.add(dot)

        # A brace measures what get_width() reports — the number and the
        # picture come from the same bounding box, so they cannot disagree.
        brace = Brace(box, DOWN, buff=0.15, color=GREY_A)
        width = DecimalNumber(
            float(box.get_width()),
            num_decimal_places=2,
            size=0.45,
            color=GREY_A,
        )
        width.next_to(brace, DOWN, buff=0.12)

        self.add(title, box, marks, brace, width)
        print(
            f"width = {round(float(box.get_width()), 3)}"
            f" · height = {round(float(box.get_height()), 3)}"
            f" · centre = {box.get_center()}",
        )

        self.play(FadeIn(box), run_time=0.6)
        self.wait(0.6)

        # Setters chain because each one returns the mobject.
        self.play(box.animate.set_width(6.0).rotate(TAU / 24), run_time=1.2)
        # …and the getters follow, because they are read off the live geometry.
        width.set_value(float(box.get_width()))
        brace.move_to(Vec3(box.get_bottom()) + 0.35 * Vec3(DOWN))
        for dot, point in zip(
            marks.submobjects,
            (
                box.get_left(),
                box.get_right(),
                box.get_top(),
                box.get_bottom(),
                box.get_center(),
            ),
        ):
            dot.move_to(point)
        width.next_to(brace, DOWN, buff=0.12)
        self.wait(0.8)
        print(
            f"after set_width(6) + rotate: width = {round(float(box.get_width()), 3)}"
            "  ← the bbox grew with the turn",
        )


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    SettersAndGetters(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
