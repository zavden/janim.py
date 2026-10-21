"""Gallery 03: a point orbits by an updater and a square follows it."""

import math

import numpy as np

from janim import BLUE, Circle, Scene, Square, YELLOW


KEY_FRAME = 2.5
KEY_FRAMES = [KEY_FRAME, 1.2, 3.9]
RESOLUTION = (640, 360)


class UpdatersExample(Scene):
    def construct(self):
        point_mob = Circle(radius=0.12)
        point_mob.set_fill(color=YELLOW, opacity=1.0)
        point_mob.set_stroke(opacity=0.0, width=0.0)
        box = Square(side_length=0.6).set_stroke(color=BLUE, width=4.0)
        clock = 0.0

        def orbit(mobject, dt):
            nonlocal clock
            clock += dt
            direction = np.array((math.cos(1.5 * clock), math.sin(1.5 * clock), 0), dtype=np.float32)
            mobject.move_to(np.float64(2.2) * direction)

        point_mob.add_updater(orbit)
        box.add_updater(lambda mobject, dt: mobject.move_to(point_mob.get_center()))
        self.add(point_mob, box)
        self.wait(4.5)
