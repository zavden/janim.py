"""Demo 03 · PORTALS — one shape, three cameras: the scene camera in the center
and two identical MAGNIFIERS at the sides, one circular and one star-shaped

A 2D world (a rosette with tiny labels and two dots traveling along it in
opposite directions) drawn by the scene camera in the center. At the sides,
two layers see the SAME world with their own cameras, and their windows
are not rectangles. Both cameras are the same ×3 magnifier chasing a dot
(an updater on the `CameraFrame`, which in CE requires an entire
`ZoomedScene`): the circle follows the yellow dot and the star follows the
green one. This is a real render, not a scaled copy: strokes do not thicken
with zoom and 0.1-unit labels stay sharp. The portal's shape is only the
mask — the camera does not know whether it is a circle or a star. And the
star SPINS in place (mask and rim, with an updater): the image inside stays
upright; only the cutout rotates. Because a rotating star's bounding box
changes size and center, that layer's WINDOW is an invisible fixed square,
and the star is only the mask: magnification does not oscillate and the
image does not wobble.

The mechanics: `window=` places the view in the mobject's BOX (the lens is
square; the star nearly so), and `crop(..., inside=shape)` clips that box
with the actual shape. The mask is applied in the PARENT's space, after
the window, so the same shape can serve as both window and cutout. The
clipping shape is filled and NOT drawn; the visible rim is another
mobject, stroke-only, in the layer above.

Rosette samples come from `linear_range`. Each label's offset is computed
with care for types: `hypot` of two Float32 values is evaluated in Float64
and rounded to Float32, and `0.22 * point` promotes to Float64 (in numpy 2,
`0.22 * array_float32` would remain float32).

    bin/janim render examples/demo/03_portals.py -ql
"""

import math
from pathlib import Path

import numpy as np

from janim import *
from janim.math import cos, linear_range, sin


def rosette_point(t):
    """A hypotrochoid: five lobes, closed after two turns."""
    R, r, d = 2.0, 0.8, 1.15
    k = (R - r) / r
    return np.array(
        (
            (R - r) * cos(t) + d * cos(k * t),
            (R - r) * sin(t) - d * sin(k * t),
            0,
        ),
        dtype=np.float32,
    )


class Portals(Scene):
    def construct(self):
        # ── the 2D world ────────────────────────────────────────────────────
        plane = NumberPlane(
            (-7.0, 7.0, 1.0),
            (-4.0, 4.0, 1.0),
            width=14.0,
            height=8.0,
            background_line_color="#1C2E4A",
            faded_opacity=0.12,
        )

        rosette = VMobject()
        rosette.set_points_smoothly([rosette_point(t) for t in linear_range(0, 4 * PI, 721)])
        rosette.set_stroke(width=4.0)
        rosette.set_stroke_by_gradient("#FF3D8B", "#FFD25E", "#39D0FF", "#7FDD58", "#FF3D8B")

        # TINY labels along the curve: barely readable in the center,
        # sharp in the magnifier — proof that the magnifier is a render,
        # not a zoom of pixels
        labels = VGroup()
        for k in range(1, 11):
            p = rosette.point_from_proportion((k - 0.5) / 10)
            t = Text(str(k), size=0.11, color=GREY_A)
            # hypot of two Float32 values: in Float64, rounded to Float32
            h = np.float32(math.sqrt(float(p[0]) * float(p[0]) + float(p[1]) * float(p[1])))
            normal = np.array((-p[1], p[0], 0), dtype=np.float32).astype(np.float64)
            t.move_to(p.astype(np.float64) + 0.22 * normal / max(float(h), 1e-6))
            labels.add(t)
        fine_print = Text("a real render, not a copy", size=0.09, color=GREY_B)
        fine_print.move_to((0, -0.1, 0))

        # two dots, matching the rims that follow them, traveling along
        # the rosette in opposite directions (one lap every 7 s)
        def runner(color, alpha_of_t):
            d = Dot(ORIGIN, radius=0.11)
            d.set_fill(color)
            d.set_stroke(WHITE, width=1.5, opacity=1.0)

            def run(m, dt):
                m.move_to(rosette.point_from_proportion(alpha_of_t(self.t)))

            d.add_updater(run)
            return d

        dot_a = runner("#FFD25E", lambda t: (t / 7.0) % 1.0)
        dot_b = runner("#7FDD58", lambda t: (0.5 - t / 7.0) % 1.0)
        # tails go AFTER their dots in the list: they sample this frame's
        # position rather than the previous one's
        tail_a = TracingTail(
            lambda: dot_a.get_center(),
            time_traced=0.9,
            color=WHITE,
            stroke_width=7.0,
        )
        tail_b = TracingTail(
            lambda: dot_b.get_center(),
            time_traced=0.9,
            color=WHITE,
            stroke_width=7.0,
        )

        world = [plane, rosette, labels, fine_print, tail_a, tail_b, dot_a, dot_b]

        # ── the two cameras ────────────────────────────────────────────────
        # the same magnifier twice: ×3, attached to its dot. The star clips
        # with a box of aspect ~1.05, so it sees 1.3 units vertically just
        # like the circle — magnification is the same
        cam_lens = CameraFrame()
        cam_lens.set_frame_height(1.3)
        cam_lens.add_updater(lambda f: f.move_to(dot_a.get_center()))

        cam_star = CameraFrame()
        cam_star.set_frame_height(1.3)
        cam_star.add_updater(lambda f: f.move_to(dot_b.get_center()))

        # ── the portals: the FILLED shape clips and is not drawn; the rim is visible
        lens_mask = Circle(radius=1.9, fill_opacity=1.0)
        lens_mask.set_fill(WHITE, opacity=1.0)
        lens_mask.set_stroke(opacity=0)
        lens_mask.move_to((-4.9, 0.2, 0))
        lens_rim = Circle(radius=1.9)
        lens_rim.set_fill(opacity=0)
        lens_rim.set_stroke("#FFD25E", width=4.0)
        lens_rim.move_to((-4.9, 0.2, 0))

        # The BOX center of a five-pointed star is not its center:
        # it is 0.2 units above (the top tip reaches R, the bottom tips
        # R·cos 36°). Rotating around it would make the star orbit, so it
        # is placed and rotated by its centroid, which
        # `get_real_center_of_mass` computes exactly.
        star_center = np.array((4.9, 0.2, 0), dtype=np.float32)
        star_mask = Star(5, outer_radius=2.15, inner_radius=1.15)
        star_mask.set_fill(WHITE, opacity=1.0)
        star_mask.set_stroke(opacity=0)
        star_mask.shift(star_center - star_mask.get_real_center_of_mass())
        star_rim = Star(5, outer_radius=2.15, inner_radius=1.15)
        star_rim.set_fill(opacity=0)
        star_rim.set_stroke("#7FDD58", width=4.0)
        star_rim.shift(star_center - star_rim.get_real_center_of_mass())
        # the window: a fixed box the size of the star (not drawn)
        star_window = Square(side_length=4.3)
        star_window.move_to(star_center)

        # the star spins: the mask (which clips and acts as a window) and the
        # visible rim receive the same rotation each frame, around the same point
        def spin(m, dt):
            if not dt > 0:
                return
            m.rotate(0.3 * dt, about_point=star_center)
            star_rim.rotate(0.3 * dt, about_point=star_center)

        star_mask.add_updater(spin)

        # ── labels ────────────────────────────────────────────────────────
        tag_lens = Text("LENS ×3", size=0.34, color="#FFD25E")
        tag_lens.next_to(lens_rim, DOWN, buff=0.3)
        tag_star = Text("LENS ×3", size=0.34, color="#7FDD58")
        tag_star.move_to((4.9, -2.65, 0))       # below the lowest possible tip
        tag_mid = Text("the scene camera", size=0.3, color=GREY_B)
        tag_mid.move_to((0, -2.65, 0))
        caption = Text(
            "one 2D world, three cameras — two identical lenses, each chasing its own dot: "
            "the portal's shape is just a mask, and it can spin",
            size=0.3,
            color=GREY_C,
        )
        if caption.get_width() > FRAME_WIDTH - 1.0:
            caption.set_width(FRAME_WIDTH - 1.0)
        caption.to_edge(DOWN, buff=0.3)

        self.use_composition(
            Composition(
                Layer(*world),
                crop(
                    *world,
                    inside=lens_mask,
                    feather=0.02,
                    camera=cam_lens,
                    window=lens_mask,
                ),
                crop(
                    *world,
                    inside=star_mask,
                    feather=0.02,
                    camera=cam_star,
                    window=star_window,
                ),
                Layer(lens_rim, star_rim, tag_lens, tag_star, tag_mid, caption),
                background=(0.015, 0.02, 0.04, 1),
            ),
        )

        # two laps per dot; everything else is handled by updaters
        self.wait(14.0)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    Portals(output=str(here.with_suffix(".mp4")), fps=30, resolution=(1280, 720)).render()
