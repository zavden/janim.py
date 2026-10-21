"""Directions, frame constants and the frozen Manim color catalogue."""

import math
from types import SimpleNamespace

import numpy as np

from .core._palette import PALETTE


ORIGIN = np.array([0, 0, 0], dtype=np.float32)
RIGHT = np.array([1, 0, 0], dtype=np.float32)
LEFT = np.array([-1, 0, 0], dtype=np.float32)
UP = np.array([0, 1, 0], dtype=np.float32)
DOWN = np.array([0, -1, 0], dtype=np.float32)
OUT = np.array([0, 0, 1], dtype=np.float32)
IN = np.array([0, 0, -1], dtype=np.float32)
UR, UL, DR, DL = UP + RIGHT, UP + LEFT, DOWN + RIGHT, DOWN + LEFT
PI, TAU = math.pi, math.tau
DEG = DEGREES = TAU / 360
FRAME_HEIGHT = 8.0
FRAME_WIDTH = 8.0 * 16 / 9
FRAME_Y_RADIUS = FRAME_HEIGHT / 2
FRAME_X_RADIUS = FRAME_WIDTH / 2
SMALL_BUFF = 0.1
MED_SMALL_BUFF = 0.25
MED_LARGE_BUFF = 0.5
LARGE_BUFF = 1.0
DEFAULT_MOBJECT_TO_EDGE_BUFF = DEFAULT_MOBJECT_TO_EDGE_BUFFER = MED_LARGE_BUFF
DEFAULT_MOBJECT_TO_MOBJECT_BUFF = DEFAULT_MOBJECT_TO_MOBJECT_BUFFER = MED_SMALL_BUFF
DEFAULT_DOT_RADIUS = 0.05
DEFAULT_FONT_SIZE = 48.0
DEFAULT_SMALL_DOT_RADIUS = 0.04
DEFAULT_STROKE_WIDTH = np.float32(4)

for _name, _value in PALETTE.items():
    if "." in _name:
        _catalogue, _key = _name.split(".", 1)
        if _catalogue not in globals():
            globals()[_catalogue] = SimpleNamespace()
        setattr(globals()[_catalogue], _key, _value)
    else:
        globals()[_name] = _value

del _name, _value, _catalogue, _key
