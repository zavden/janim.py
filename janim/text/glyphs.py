"""The FreeType outline reader for SVG text elements.

This module deliberately exposes no Text or formula constructor. Font
loading happens only when an SVG actually contains a text element.
"""

import ctypes
from functools import lru_cache
import os
from pathlib import Path
import re
import threading

import numpy as np

from janim.core.bezier import cubic_to_two_quadratics
from janim.core.mobject import VGroup, VMobject


_FONT_LOCK = threading.RLock()


class FontNotFound(ValueError):
    pass


@lru_cache(maxsize=1)
def _font_catalog():
    """Use BaseDirs' Unix roots and FreeTypeAbstraction's breadth-first order."""
    import freetype

    roots = [
        Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "fonts",
        Path.home() / ".fonts",
        *(Path(path) / "fonts" for path in (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")),
    ]
    folders = list(dict.fromkeys(path for path in roots if path.is_dir()))
    index = 0
    while index < len(folders):
        folders.extend(path for path in sorted(folders[index].iterdir()) if path.is_dir())
        index += 1
    extra = os.environ.get("FREETYPE_ABSTRACTION_FONT_PATH")
    if extra:
        folders.append(Path(extra))
    catalog = []
    for folder in folders:
        for path in sorted(folder.iterdir()):
            if not path.is_file():
                continue
            try:
                face = freetype.Face(str(path))
            except freetype.FT_Exception:
                continue
            family = (face.family_name or b"").decode("utf-8", errors="surrogateescape")
            style = (face.style_name or b"").decode("utf-8", errors="surrogateescape")
            catalog.append((str(path), family, style))
    return catalog


def _font_score(family, style, parts):
    family, style = family.lower(), style.lower()
    regular = any(value in style for value in ("regular", "normal", "medium", "standard", "roman", "book"))
    family_score = sum(len(part) for part in parts if part in family)
    style_score = sum(len(part) for part in parts if part not in family and part in style) if family_score else 0
    return family_score, style_score, regular, -(len(family) + len(style))


@lru_cache(maxsize=32)
def find_face(name):
    """Resolve and validate a family/style with a deterministic scorer."""
    import freetype

    parts = tuple(dict.fromkeys(part for part in re.split(r"\W+", name.lower()) if part))
    best = None
    best_score = (0, 0, False, -2**63)
    for path, family, style in _font_catalog():
        score = _font_score(family, style, parts)
        if score[0] > 0 and score > best_score:
            best, best_score = (path, family, style), score
    if best is None:
        raise FontNotFound(f"cannot find font {name!r}")
    path, family, style = best
    if name.strip().lower() not in (family.strip().lower(), (family + " " + style).strip().lower()):
        raise FontNotFound(f"font {name!r} is unavailable; closest face is {family} {style}")
    return freetype.Face(path), path


def _add_glyph(mobject, face, glyph_id, transform):
    import freetype

    face.load_glyph(glyph_id, freetype.FT_LOAD_NO_SCALE)
    outline = face.glyph.outline
    if not outline.n_contours:
        return mobject
    points = outline.points
    tags = outline.tags
    upem = float(face.units_per_EM)
    first = 0
    for last in outline.contours:
        count = last - first + 1

        def point(index):
            x, y = points[first + index % count]
            return transform(x / upem, y / upem)

        def tag(index):
            return tags[first + index % count] & 3

        start_index = next((index for index in range(count) if tag(index) & 1), None)
        start = (point(0) + point(1)) / np.float32(2) if start_index is None else point(start_index)
        mobject.start_new_path(start)
        index = 0 if start_index is None else start_index + 1
        done = 0
        while done < count:
            kind = tag(index)
            if kind & 1:
                mobject.add_line_to(point(index))
                index += 1
                done += 1
            elif kind == 0:
                control = point(index)
                if tag(index + 1) & 1:
                    mobject.add_quadratic_bezier_curve_to(control, point(index + 1))
                    index += 2
                    done += 2
                else:
                    mobject.add_quadratic_bezier_curve_to(
                        control,
                        (control + point(index + 1)) / np.float32(2),
                    )
                    index += 1
                    done += 1
            else:
                first_control, middle, second_control = cubic_to_two_quadratics(
                    mobject.points[-1],
                    point(index),
                    point(index + 1),
                    point(index + 2),
                )
                mobject.add_quadratic_bezier_curve_to(first_control, middle)
                mobject.add_quadratic_bezier_curve_to(second_control, point(index + 2))
                index += 3
                done += 3
        if not np.array_equal(mobject.points[-1], start):
            mobject.add_line_to(start)
        first = last + 1
    return mobject


def svg_text(text, font="DejaVu Sans", size=16.0):
    """Build uncentered glyph outlines in em units, with unscaled kerning."""
    import freetype

    with _FONT_LOCK:
        face, _ = find_face(font)
        advance = 0.0
        previous = 0
        upem = float(face.units_per_EM)
        children = []
        for character in text:
            glyph_id = face.get_char_index(ord(character))
            if previous and glyph_id:
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
                child = VMobject(
                    fill_color="#FFFFFF",
                    fill_opacity=1.0,
                    stroke_color="#FFFFFF",
                    stroke_width=0.0,
                )
                child.set_key(character)
                x0 = advance
                _add_glyph(
                    child,
                    face,
                    glyph_id,
                    lambda x, y: np.array(((x0 + x) * size, y * size, 0), dtype=np.float32),
                )
                if child.has_points():
                    children.append(child)
                face.load_glyph(glyph_id, freetype.FT_LOAD_NO_SCALE)
                advance += face.glyph.advance.x / upem
            else:
                advance += 0.33
            previous = glyph_id
        if not children:
            raise ValueError(f"text {text!r} produced no geometry")
        return VGroup(*children)
