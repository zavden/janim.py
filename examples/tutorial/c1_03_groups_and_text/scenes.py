"""The scenes of the c1_03 lessons."""

from janim import *


class TextLesson(Scene):
    def construct(self):
        plain = Text("plain text through FreeType", size=0.6)
        colored = Text(
            "colour by substring and by range",
            size=0.6,
            t2c={"substring": YELLOW, range(24, 32): "#7FDD58"},
        )
        weighted = Text("weight comes from a real face", size=0.6, t2w={"real face": "bold"})
        serif = Text("another family entirely", size=0.6, font="Liberation Serif", color="#E8A33D")
        lines = VGroup(plain, colored, weighted, serif).arrange(DOWN, buff=0.45).shift(0.4 * UP)
        self.add(lines)
        self.play(LaggedStart(*(Write(line) for line in lines), lag_ratio=0.25), run_time=2.4)
        self.play(Indicate(plain["e"], color="#FF5E5E", scale_factor=1.0), run_time=1.2)
        self.wait(0.4)


class LatexConfig(Scene):
    def construct(self):
        title = Text("LaTeX: documentos, medidas y claves", size=0.44, color=GREY_A).to_edge(UP, buff=0.4)
        self.add(title)
        formula = Tex(r"\frac{a^2}{b} + \sqrt{c}", size=0.9).set_color("#E8A33D")
        label = Text("LaTeX", size=0.35, color=GREY_C)
        row = VGroup(label, formula).arrange(RIGHT, buff=0.8)
        rows = VGroup(row).arrange(DOWN, buff=0.6, aligned_edge=LEFT)
        self.add(rows)
        self.play(
            LaggedStart(*(FadeIn(item, shift=0.3 * RIGHT) for item in rows), lag_ratio=0.3),
            run_time=1.8,
        )
        self.wait(0.6)
        isolated = Tex("x^2 + y^2", isolate=["x^2"])
        assert len(isolated["x^2"]) == 2
        try:
            isolated["y"]
        except KeyError:
            pass
        else:
            raise AssertionError("an unisolated substring must fail")


class TexTransformations(Scene):
    def construct(self):
        title = Text("matched by key, not by position", size=0.46, color=GREY_A).to_edge(UP, buff=0.4)
        self.add(title)
        first = Tex(r"a^2 + b^2 = c^2", size=1.3)
        second = Tex(r"c^2 - b^2 = a^2", size=1.3)
        third = Tex(r"c = \sqrt{a^2 + b^2}", size=1.3)
        for mob in (first, second, third):
            mob.move_to(0.3 * UP)
        self.add(first)
        self.play(Write(first), run_time=1.2)
        self.wait(0.5)
        self.play(TransformMatchingTex(first, second), run_time=1.6)
        self.wait(0.6)
        self.play(TransformMatchingTex(second, third), run_time=1.6)
        self.wait(0.6)
        assert third in self.mobjects


class SymbolBySymbol(Scene):
    def construct(self):
        title = Text("address the parts, then animate them", size=0.46, color=GREY_A).to_edge(UP, buff=0.4)
        self.add(title)
        formula = Tex("x^2 + 2xy + y^2", size=1.5, isolate=["x^2", "y^2", "2xy"]).move_to(0.6 * UP)
        self.add(formula)
        self.play(Write(formula), run_time=1.4)
        assert formula["x^2"] is formula["x^2"]
        self.play(Indicate(formula["x^2"], color="#58C4DD", scale_factor=1.3), run_time=1.0)
        self.play(Indicate(formula["2xy"], color="#E8A33D", scale_factor=1.3), run_time=1.0)
        self.play(Circumscribe(VGroup(formula[5], formula[7]), color="#7FDD58", buff=0.12), run_time=1.2)
        self.play(Indicate(formula[2], color="#FF5E5E"), run_time=0.8)
        target = Tex("(x + y)^2", size=1.5, isolate=["x", "y"]).move_to(0.6 * UP)
        self.play(TransformMatchingTex(formula, target), run_time=1.8)
        self.wait(0.6)
