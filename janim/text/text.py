"""FreeType text with one child per visible glyph."""

import ctypes
import math
import warnings
from collections.abc import Mapping

import numpy as np

from janim.constants import DEFAULT_FONT_SIZE, WHITE
from janim.core.mobject import VMobject
from .glyphs import _FONT_LOCK, _add_glyph, find_face


GL_SIZE_TEXT = 2.2017
_MISSING_GLYPHS = {}


def text_size(size, font_size, calibration, name):
    if size is not None and font_size is not None:
        raise ValueError(f"{name} takes size or font_size, not both")
    if size is not None:
        value = float(size)
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name}: size must be finite and positive, got {value}")
        return value
    value = DEFAULT_FONT_SIZE if font_size is None else float(font_size)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name}: font_size must be finite and positive, got {value}")
    return value / (DEFAULT_FONT_SIZE * calibration)


def style_pairs(value):
    if value is None:
        return []
    if isinstance(value, Mapping):
        return list(value.items())
    if not isinstance(value, (list, tuple)) or any(
        (
            not isinstance(pair, (list, tuple)) or len(pair) != 2 for pair in value
        ),
    ):
        raise TypeError("t2c/t2w requires a mapping or an ordered list of pairs")
    return list(value)


def character_ranges(pattern, text):
    if isinstance(pattern, str):
        if not pattern:
            return []
        ranges = []
        index = text.find(pattern)
        while index >= 0:
            ranges.append(range(index, index + len(pattern)))
            index = text.find(pattern, index + len(pattern))
        return ranges
    if isinstance(pattern, range):
        if pattern.step != 1:
            raise ValueError("a character range must have step one")
        return [range(max(0, pattern.start), min(len(text), pattern.stop))]
    if isinstance(pattern, slice):
        start, stop, step = pattern.indices(len(text))
        if step != 1:
            raise ValueError("a character slice must have step one")
        return [range(start, stop)]
    raise TypeError("a t2c/t2w key must be a substring or a character range")


def weighted_face(family, weight):
    if not isinstance(weight, str):
        raise TypeError("a font weight must be a style or full face name")
    styles = (
        "bold", "normal", "regular", "medium", "book", "italic", "oblique",
        "thin", "light", "semibold", "demibold", "heavy", "black", "ultralight", "ultrabold",
    )
    is_style = weight.lower() in styles
    name = family + " " + weight.capitalize() if is_style else weight
    face = find_face(name)[0]
    face_name = b" ".join((face.family_name or b"", face.style_name or b""))
    if is_style and weight.lower() not in face_name.decode("utf-8", errors="surrogateescape").lower():
        raise ValueError(f"font {family!r} has no requested weight {weight!r}")
    return face


def same_face(first, second):
    return first is second or (
        first is not None
        and first.family_name == second.family_name
        and first.style_name == second.style_name
        and first.num_glyphs == second.num_glyphs
    )


def text_style_keywords(kwargs, name):
    allowed = (
        "stroke_color", "stroke_opacity", "stroke_width", "fill_color",
        "fill_opacity", "key", "joint_type", "z_index",
    )
    unknown = next((key for key in kwargs if key not in allowed), None)
    if unknown is not None:
        raise TypeError(f"{name} does not take {unknown!r}")
    cleaned = {key: value for key, value in kwargs.items() if value is not None}
    for key in ("stroke_opacity", "stroke_width", "fill_opacity", "z_index"):
        if key in cleaned and not math.isfinite(float(cleaned[key])):
            raise ValueError(f"{name}: {key} must be finite, got {cleaned[key]!r}")
    return cleaned


def glyph_style(color, kwargs):
    return {
        "fill_color": kwargs.get("fill_color", color),
        "fill_opacity": kwargs.get("fill_opacity", 1.0),
        "stroke_color": kwargs.get("stroke_color", color),
        "stroke_opacity": kwargs.get("stroke_opacity", 1.0),
        "stroke_width": kwargs.get("stroke_width", 0.0),
        **{key: kwargs[key] for key in ("z_index", "joint_type") if key in kwargs},
    }


class Text(VMobject):
    """Plain Latin/Greek/Cyrillic outlines; no shaping or newline layout.

    Character ranges are zero-based and half-open. Spaces advance the pen
    without creating children; Paragraph lays out separate lines.
    """

    _plain_text = True

    def __init__(
        self,
        text,
        *,
        font="DejaVu Sans",
        size=None,
        font_size=None,
        color=WHITE,
        center=True,
        t2c=None,
        t2w=None,
        **kwargs,
    ):
        if not isinstance(text, str):
            raise TypeError("Text requires a string")
        if not isinstance(font, str):
            raise TypeError("font must be a family or face name")
        kwargs = text_style_keywords(kwargs, type(self).__name__)
        color = WHITE if color is None else color
        self.string = text
        self.font = font
        self.size = text_size(size, font_size, GL_SIZE_TEXT, "Text")
        self.font_size = self.size * (DEFAULT_FONT_SIZE * GL_SIZE_TEXT)
        super().__init__(**kwargs)
        self._build_glyphs(text, font, color, t2c, t2w, kwargs)
        if not self.submobjects:
            raise ValueError(f"text {text!r} produced no geometry")
        self.key_runs = {}
        for index, child in enumerate(self.submobjects):
            for key in child.get_keys():
                if len(key) == 1:
                    self.key_runs.setdefault(key, []).append([index])
        if center:
            self.center()

    def _build_glyphs(self, text, font, color, t2c, t2w, kwargs):
        import freetype

        with _FONT_LOCK:
            base, _ = find_face(font)
            colors = [kwargs.get("fill_color", color)] * len(text)
            faces = [base] * len(text)
            for pattern, value in style_pairs(t2c):
                for selected in character_ranges(pattern, text):
                    for index in selected:
                        colors[index] = value
            for pattern, weight in style_pairs(t2w):
                face = weighted_face(font, weight)
                for selected in character_ranges(pattern, text):
                    for index in selected:
                        faces[index] = face
            advance = 0.0
            previous = 0
            previous_face = None
            children = []
            for character, color, face in zip(text, colors, faces):
                glyph_id = face.get_char_index(ord(character))
                upem = float(face.units_per_EM)
                if previous and glyph_id and same_face(previous_face, face):
                    kern = freetype.FT_Vector(0, 0)
                    error = freetype.FT_Get_Kerning(
                        face._FT_Face,
                        previous,
                        glyph_id,
                        freetype.FT_KERNING_UNSCALED,
                        ctypes.byref(kern),
                    )
                    if error:
                        raise ValueError(f"FreeType kerning failed with code {error}")
                    advance += kern.x / upem
                if glyph_id:
                    child = VMobject(**glyph_style(color, {**kwargs, "fill_color": color})).set_key(character)
                    x0 = advance
                    _add_glyph(
                        child,
                        face,
                        glyph_id,
                        lambda x, y: np.array(((x0 + x) * self.size, y * self.size, 0), dtype=np.float32),
                    )
                    if child.has_points():
                        children.append(child)
                    face.load_glyph(glyph_id, freetype.FT_LOAD_NO_SCALE)
                    advance += face.glyph.advance.x / upem
                else:
                    key = (face.family_name, character)
                    if key not in _MISSING_GLYPHS:
                        family = (face.family_name or b"").decode("utf-8", errors="surrogateescape")
                        warnings.warn(
                            f"Text: {character!r} has no glyph in {family} — a 0.33 em gap is left",
                            UserWarning,
                            stacklevel=3,
                        )
                        _MISSING_GLYPHS[key] = None
                    advance += 0.33
                previous, previous_face = glyph_id, face
            self.add(*children)

    def get_string(self):
        return self.string


TextMobject = Text
