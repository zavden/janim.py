"""Demo 07 · SEA LETTERS — the title as a MASK over an animated 3D world

A `Text` is a mobject like any other, so it can clip a layer:
`crop(sea, inside=word)`. And the clipped layer has its OWN camera
(`camera=`), tilted over a sea of waves moved by an updater with analytic
normals (real lighting, not a gradient). Inside each letter is a lit 3D
render; the rest of the screen does not know it exists.

The ending is the classic opening-title shot: the mask grows until the
eye enters through the “I” and the whole sea appears. The mask is a
mobject, so that flight is an ordinary `animate` with an `about_point`.

Manim has no masks: a `Text` can only be drawn, not used to clip.

Mesh samples come from `linear_range`; waves are calculated for all
vertices at once using `janim.math`'s `sin` and `cos` on arrays (the same
bits as calling them one by one, and the same as Janim.jl), written into
the surface's live `points`/`d_normal_points` arrays, then reported with
`note_changed_data()`; an `animate` with two operations is a chain on the
`.animate` builder.

    bin/janim render examples/demo/07_text_mask.py -ql
"""

from pathlib import Path

import numpy as np

from janim import *
from janim.math import cos, linear_range, sin


class TextMask(Scene):
    def construct(self):
        # ── the sea: an animated surface with analytic normals ─────────
        X, Y, NU, NV = 12.0, 5.5, 101, 51
        sea = PlaneXY(
            x_range=(-X, X),
            y_range=(-Y, Y),
            resolution=(NU, NV),
            color="#0F3D6E",
            opacity=1.0,
            shading=(0.25, 0.35, 0.5),
        )
        # each vertex's u, v samples, in mesh order (u outermost, v innermost)
        us = np.asarray(linear_range(-X, X, NU))
        vs = np.asarray(linear_range(-Y, Y, NV))
        U, V = (grid.ravel() for grid in np.meshgrid(us, vs, indexing="ij"))

        def waves(m, dt):
            # waves for ALL vertices at once: janim.math's `sin` and `cos`
            # accept arrays and give the same bits as a loop, 5× faster
            t = self.t
            a, b, c = 1.7 * U + 1.8 * t, 1.4 * V + 1.3 * t, 2.6 * U - 1.1 * t
            sa, ca, sb, cb, sc, cc = sin(a), cos(a), sin(b), cos(b), sin(c), cos(c)
            z = 0.34 * sa * cb + 0.12 * sc
            dzx = 0.578 * ca * cb + 0.312 * cc
            dzy = -0.476 * sa * sb
            inv = 1e-3 / np.sqrt(dzx * dzx + dzy * dzy + 1)
            points, nudged = m.points, m.d_normal_points
            points[:, 0], points[:, 1], points[:, 2] = U, V, z
            nudged[:, 0], nudged[:, 1], nudged[:, 2] = U - dzx * inv, V - dzy * inv, z + inv
            m.note_changed_data()

        sea.add_updater(waves)
        sun = Sphere(radius=0.9)
        sun.set_color("#FFB84D")
        sun.move_to((1.5, 5.5, 1.6))

        # the sea camera: tilted and swaying slightly
        cam_sea = CameraFrame()
        cam_sea.reorient(0.0, 62.0)
        cam_sea.set_frame_height(6.0)
        cam_sea.move_to((0, 0.6, 0))

        def rock(f, dt):
            f.reorient(6.0 * sin(0.22 * self.t), 62.0)

        cam_sea.add_updater(rock)

        # ── the letters: the FILLED one clips and is not drawn; the rim is ───────
        word_mask = Text("JANIM", font="DejaVu Sans", size=2.3)
        if word_mask.get_width() > FRAME_WIDTH - 1.6:
            word_mask.set_width(FRAME_WIDTH - 1.6)
        word_mask.set_fill(WHITE, opacity=1.0)
        word_mask.set_stroke(opacity=0)
        word_mask.move_to(0.25 * UP)
        word_rim = word_mask.copy()
        word_rim.set_fill(opacity=0)
        word_rim.set_stroke("#9ADCFF", width=2.5, opacity=1.0)

        caption = Text(
            "the world seen THROUGH the letters: a lit 3D render, cut out by a TextMobject",
            size=0.3,
            color=GREY_C,
        )
        caption.to_edge(DOWN, buff=0.35)

        self.use_composition(
            Composition(
                crop(sea, sun, inside=word_mask, feather=0.015, camera=cam_sea),
                Layer(
                    word_rim,
                    blend="add",
                    effects=[Bloom(threshold=0.25, intensity=1.1, sigma=0.055)],
                ),
                Layer(caption),
                background=(0.01, 0.012, 0.03, 1),
            ),
        )
        caption.set_opacity(0.0)
        self.wait(1.0)
        caption.set_opacity(1.0)
        self.play(FadeIn(caption, shift=0.2 * UP), run_time=1.0)
        self.wait(2.5)
        self.play(FadeOut(caption), run_time=0.6)

        # the flight: the mask grows 90× around the “I” — the eye enters
        # through the letter and the sea fills everything
        anchor = word_mask["I"].get_center()
        # the rim grows AND fades in the SAME animate: two animations
        # on one mobject overwrite each other (each writes the entire state);
        # a single one does not
        self.play(
            AnimationGroup(
                word_mask.animate(rate_func=ease_in_cubic).scale(90.0, about_point=anchor),
                word_rim.animate(rate_func=ease_in_cubic).scale(90.0, about_point=anchor).set_stroke(opacity=0.0),
            ),
            run_time=5,
        )
        self.wait(4)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    TextMask(output=str(here.with_suffix(".mp4")), fps=30, resolution=(1280, 720)).render()
