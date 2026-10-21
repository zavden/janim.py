"""Course 1 · 2.5 — Importing images

    ImageMobject(path, height=4.0, opacity=1.0)
    ImageMobject(array_of_pixels, height=4.0)        ← no file needed
    TexturedSurface(surface, image, opacity=1.0)     ← the 3D form

PNG is decoded natively; everything else (jpg, bmp, tiff, webp) goes through
ffmpeg's image demuxer. An array is `(height, width, 3 or 4)` uint8, row 0
on top.

This lesson COMPUTES its image instead of loading one: it is the more
interesting half of the API — an image made in Python never touches the disk
— and the lesson needs no extra file to run.

The four corner points go through the ordinary transform machinery, so
`shift`, `rotate`, `scale`, `move_to` and the interpolation contract all
work — and so does the relative layout: `next_to`, `to_edge`, `align_to` and
friends read `get_bounding_box_point`, which ImageMobject and
TexturedSurface answer like Surface does. One thing still does NOT, and it
is better to know it now:

  · `set_fill`/`set_stroke` — an ImageMobject has pixels, not style rows.
    Its one dial is `set_opacity`.

    python examples/tutorial/c1_02_config_and_assets/05_image_import.py
"""

import cmath
import math
from pathlib import Path

import numpy as np

from janim import *

PREVIEW_T = 1.8


def domain_colouring(n=128):
    """A 128×128 complex-plane picture: |z| in the hue, arg(z) in the brightness.

    The colours are computed as floats in [0, 1] and quantised to 8 bits:
    round(255·c), ties to even."""
    img = np.empty((n, n, 4), dtype=np.float64)
    for j in range(1, n + 1):
        for i in range(1, n + 1):
            z = complex((i - n / 2) / (n / 4), (n / 2 - j) / (n / 4))
            w = z * z * z - 1                        # the function being coloured
            h = (cmath.phase(w) + math.pi) / (2 * math.pi)   # hue from the argument
            v = 0.35 + 0.65 * (1 - math.exp(-abs(w) / 3))
            # a cheap HSV→RGB, so the lesson needs no extra dependency
            k = h * 6
            c, x = v, v * (1 - abs(k % 2 - 1))
            if k < 1:
                rgb = (c, x, 0.0)
            elif k < 2:
                rgb = (x, c, 0.0)
            elif k < 3:
                rgb = (0.0, c, x)
            elif k < 4:
                rgb = (0.0, x, c)
            elif k < 5:
                rgb = (x, 0.0, c)
            else:
                rgb = (c, 0.0, x)
            img[j - 1, i - 1] = (*rgb, 1.0)
    return np.rint(255.0 * img).astype(np.uint8)


class ImageImport(Scene):
    def construct(self):
        title = Text(
            "an image computed in Python needs no file",
            size=0.48,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.4)
        self.add(title)

        picture = ImageMobject(domain_colouring(), height=4.0)
        picture.move_to(3.2 * LEFT + 0.3 * DOWN)
        print(
            f"pixels: {pixel_size(picture)}"
            f" · height in scene units: {round(float(picture.get_height()), 2)}",
        )

        # `next_to` against an image — the same call you would write against
        # any VMobject.
        caption = Text("z^3 - 1", size=0.42, color=GREY_B)
        caption.next_to(picture, DOWN, buff=0.35)

        # The 3D form: the same raster sampled over a uv mesh.
        globe = TexturedSurface(
            Sphere(radius=1.5, resolution=(81, 41)),
            domain_colouring(64),
        )
        globe.move_to((3.4, 0.2, 0))
        globe.apply_depth_test()

        self.add(picture, caption, globe)
        self.play(FadeIn(caption), run_time=0.5)

        # ImageMobject is interpolable, so `.animate` drives it like anything else.
        self.play(picture.animate.rotate(TAU / 16).scale(0.85), run_time=1.2)
        # …but the raster has one dial of its own:
        self.play(
            UpdateFromAlphaFunc(picture, lambda m, a: m.set_opacity(1 - 0.6 * a)),
            run_time=0.8,
        )
        self.wait(0.4)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    ImageImport(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
