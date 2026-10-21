"""Course 1 · 2.1 — Configuration: there is no config file, and that is the design

Manim has `manim.cfg`, a global `config` object and `with tempconfig({…})`.
Janim has none of them, on purpose. The precedence rule is one line:

    CLI flag  >  the Scene kwargs in your script  >  engine defaults

and it is resolved by BUILDING the scene with those kwargs. There is no
ENGINE file to find, no environment to leak between runs, nothing to un-set
— and no scene whose output depends on a config file you cannot see.

(The CLI has no client-side file that shortens its flags either, on purpose.
`--out_dir DIR` exists in the same spirit: the CLI joins the path and creates
it, and the engine still receives one plain `-o`. The rule above is
untouched: nothing global ever reaches the Scene.)

What you use instead is Python: a dict of settings, splatted into the scene
(`MyScene(**settings)`). That is lesson 2.3. This one is about the defaults
themselves and about the one knob that IS global — and why.

    python examples/tutorial/c1_02_config_and_assets/01_configuration.py
"""

import math
from pathlib import Path

from janim import *

PREVIEW_T = 1.0

# The engine's defaults, spelled out (from janim/scene/scene.py):
#
#   fps = 60 · resolution = (1920, 1080) · crf = 23 · preset = "medium"
#   preview = False · output = None (headless) · no motion blur
#
# The nominal FRAME, which is what `to_edge` and FRAME_X_RADIUS talk about,
# is 8 scene units tall and 8·16/9 wide REGARDLESS of the resolution. Pixels
# are a rendering decision; scene units are the geometry.


class Configuration(Scene):
    def construct(self):
        title = Text(
            "no config file: kwargs all the way down",
            size=0.5,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.4)

        # `self.camera` knows the pixels; the constants know the scene units.
        lines = [
            f"resolution  {self.camera.width}×{self.camera.height} px",
            f"fps         {self.fps}",
            f"frame       {round(FRAME_WIDTH, 2)} × {FRAME_HEIGHT} scene units",
            f"aspect      {round(self.camera.width / self.camera.height, 3)}",
        ]
        rows = VGroup()
        for line in lines:
            rows.add(Text(line, size=0.4, color=GREY_B))
        rows.arrange(DOWN, buff=0.28, aligned_edge=LEFT)

        # The nominal frame drawn as a rectangle: at any resolution it is the
        # same 14.22 × 8 box, which is why `to_edge` lands in the same place.
        border = Rectangle(width=FRAME_WIDTH - 0.2, height=FRAME_HEIGHT - 0.2)
        border.set_stroke("#37506B", width=2.0)
        border.set_fill(opacity=0)

        corner = Dot((FRAME_X_RADIUS - 0.1, FRAME_Y_RADIUS - 0.1, 0), radius=0.09)
        corner.set_fill(YELLOW)

        self.add(border, corner, title, rows)
        self.play(FadeIn(rows, shift=0.3 * UP), run_time=0.8)
        self.wait(0.8)

        # The ONE global switch, and it is not styling: which adapter renders.
        # `JANIM_HEADLESS=1` picks lavapipe (the CPU route) and `JANIM_ADAPTER`
        # picks by name. It is global because the DEVICE is, and it has to be
        # set before the device opens. (`strict_gl()` reports the OpenGL-era
        # knob that pinned the driver's shader variant; its list is empty and
        # determinism is measured instead. Opt out with JANIM_STRICT_GL=0.)
        print(
            "frame diagonal =",
            round(math.hypot(FRAME_WIDTH, FRAME_HEIGHT), 3),
            "scene units",
        )


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    # These kwargs ARE the configuration. A different film, a different call.
    Configuration(
        output=str(out),
        fps=30,
        resolution=(854, 480),
        crf=23,
        preset="medium",
    ).render()
    print("→", out)
