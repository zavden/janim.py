"""The eleven acts of the effects gallery: one layer effect each, with its caption."""

from janim import *


EFFECTS = (
    ("Glitch", lambda: Glitch(intensity=0.8, seed=3, rate=2, slices=18)),
    ("CRT", lambda: CRT(scanlines=120, scan_depth=0.5, curvature=0.3, vignette=0.5)),
    ("VHS", lambda: VHS(intensity=0.8, seed=5, rate=2)),
    ("ColorAdjust", lambda: ColorAdjust(hue=2.1, saturation=1.4, contrast=1.2)),
    ("Pixelate", lambda: Pixelate(0.18)),
    ("Vignette", lambda: Vignette(amount=0.9, radius=0.3, feather=0.5)),
    ("Grain", lambda: Grain(amount=0.35, seed=9, rate=2)),
    ("ChromaticAberration", lambda: ChromaticAberration(0.2)),
    ("Sharpen", lambda: Sharpen(1.5, sigma=0.08)),
    ("Wave", lambda: Wave(amplitude=0.15, wavelength=1.2, angle=0.4)),
    ("EdgeDetect", lambda: EdgeDetect(color=WHITE, amount=1.6)),
)


def artwork():
    group = VGroup()
    sky = Rectangle(width=6.4, height=3.6)
    sky.set_fill_by_gradient("#1B4F8C", "#39D0FF").set_fill(opacity=1).set_stroke(opacity=0)
    sky.move_to(0.2 * Vec3(DOWN))
    group.add(sky)
    sun = Circle(radius=0.7).set_fill("#FFD25E", 1).set_stroke(WHITE, width=3)
    group.add(sun.move_to((2.0, 0.9, 0)))
    hill = Triangle(radius=1.6).set_fill("#3E8E52", 1).set_stroke(opacity=0)
    group.add(hill.move_to((-1.6, -0.6, 0)))
    bar = Rectangle(width=6.4, height=0.5).set_fill("#FF3D8B", 1).set_stroke(opacity=0)
    group.add(bar.move_to((0, -1.75, 0)))
    for x in (-2.4, -0.8, 0.8, 2.4):
        line = Line((x, -1.2, 0), (x + 0.6, 1.4, 0)).set_stroke(WHITE, width=2, opacity=0.8)
        group.add(line)
    group.add(Text("JANIM", size=0.9, color=WHITE).move_to((0.2, 0.1, 0)))
    return group


class EffectsGallery(Scene):
    def construct(self):
        layer = Layer(artwork())
        label = Text("effects", size=0.32, color=GREY_B).to_edge(DOWN, buff=0.12)
        self.use_composition(Composition(layer, Layer(label), background=(0.02, 0.03, 0.05, 1)))
        for name, factory in EFFECTS:
            layer.effects[:] = [factory()]
            label.become(Text(name, size=0.32, color=GREY_B).to_edge(DOWN, buff=0.12))
            self.wait(0.6)
