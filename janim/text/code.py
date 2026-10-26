"""Highlighted source code listings with ManimCE's `Code` API.

The colours come from pygments, walked token by token: `style_for_token`
gives each token the same colour that CE reads back from pygments' HTML, so
there is no HTML and no BeautifulSoup in between. pygments is one of Janim's
pinned dependencies, imported only when a `Code` is built, so importing
Janim does not load it.

The layout is the part that differs from CE on purpose. CE stacks Pango
lines and, since Pango exposes no baseline, appends the glyphs " pA<n>" to
the first and last lines to normalise the height of the block. Janim places
every line on its own baseline at a fixed pitch and takes the same vertical
extents from those reference glyphs directly, so the "height independent of
the boundary glyphs" and "line numbers on the code's baseline" properties
hold by construction and the visible code is never shifted by the suffix.
"""

import re
from pathlib import Path

from janim.constants import BLACK, LEFT, RIGHT, UP, WHITE
from janim.core.mobject import VGroup, VMobject

# CE's Pango scale: a font_size of 24 draws an em of 24/72 of a scene unit.
_CE_POINTS_PER_UNIT = 72.0
# CE's Paragraph pitch is (1 + line_spacing) * 0.75 em, whatever the font.
_CE_PITCH_FACTOR = 0.75
# CE's DEFAULT_LINE_SPACING_SCALE, used when line_spacing is -1.
_CE_DEFAULT_LINE_SPACING = 0.3
# CE's next_to(..., LEFT) gap between the line numbers and the code.
_LINE_NUMBER_BUFF = 0.25
_WINDOW_BUTTON_COLORS = ("#ff5f56", "#ffbd2e", "#27c93f")

# Janim resolves real families only (no fontconfig "Monospace" alias), so the
# default is the first family of this list that the system has.
MONOSPACE_FONTS = (
    "DejaVu Sans Mono",
    "Menlo",
    "Consolas",
    "Liberation Mono",
    "Noto Sans Mono",
    "Courier New",
)

_PARAGRAPH_KEYS = (
    "font",
    "font_size",
    "size",
    "line_spacing",
    "disable_ligatures",
    "color",
    "weight",
    "slant",
)
_BACKGROUND_KEYS = (
    "buff",
    "corner_radius",
    "fill_color",
    "fill_opacity",
    "stroke_color",
    "stroke_width",
    "stroke_opacity",
    "color",
)
_HEX_COLOR = re.compile(r"[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6}")


def _pygments():
    try:
        import pygments.lexers
        import pygments.style
        import pygments.styles
        import pygments.token
    except ImportError as error:
        raise ImportError(
            "Code needs pygments, one of Janim's pinned dependencies: run "
            "scripts/bootstrap.sh again, or pip install pygments==2.21.0"
        ) from error
    return pygments


def default_monospace_font():
    """The first family of `MONOSPACE_FONTS` that this system has."""
    from .glyphs import FontNotFound, find_face

    for family in MONOSPACE_FONTS:
        try:
            find_face(family)
        except FontNotFound:
            continue
        return family
    raise FontNotFound(
        "Code found none of the monospace families "
        + ", ".join(MONOSPACE_FONTS)
        + "; pass paragraph_config={'font': <an installed family>}"
    )


def _face_name(family, weight, slant):
    words = [
        str(value).capitalize()
        for value in (weight, slant)
        if value is not None and str(value).lower() not in ("normal", "regular")
    ]
    return " ".join((family, *words))


def _token_color(style, token_type):
    color = style.style_for_token(token_type).get("color")
    return "#" + color if color and _HEX_COLOR.fullmatch(color) else None


def _highlighted_lines(lexer, style, code_string):
    """Split the token stream into lines of (text, [(start, stop, colour)])."""
    lines = [["", []]]
    for token_type, value in lexer.get_tokens(code_string):
        color = _token_color(style, token_type)
        for index, piece in enumerate(value.split("\n")):
            if index:
                lines.append(["", []])
            line = lines[-1]
            if piece and color is not None:
                line[1].append((len(line[0]), len(line[0]) + len(piece), color))
            line[0] += piece
    # The lexer ends the text with a newline, which opens one empty last line.
    if len(lines) > 1 and not lines[-1][0]:
        lines.pop()
    return lines


def _ink_box(mobjects):
    boxes = [mob.get_bounding_box() for mob in mobjects if mob.get_family() and _has_ink(mob)]
    if not boxes:
        return None
    lows = [box[0] for box in boxes]
    highs = [box[2] for box in boxes]
    return (
        min(float(low[0]) for low in lows),
        min(float(low[1]) for low in lows),
        max(float(high[0]) for high in highs),
        max(float(high[1]) for high in highs),
    )


def _has_ink(mobject):
    return any(member.has_points() for member in mobject.get_family())


class Code(VMobject):
    """A highlighted source code listing (ManimCE's `Code`).

    Parameters are CE's: `code_file` or `code_string`, `language` (guessed
    from the file name or the code when omitted), `formatter_style` (a
    pygments style name or class, `"vim"` by default), `tab_width`,
    `add_line_numbers`, `line_numbers_from`, `background` (`"rectangle"` or
    `"window"`), `background_config` and `paragraph_config`. The result
    carries `code_lines` (one group of glyphs per line, spaces make no
    glyph), `line_numbers` (when added) and `background`.

    `paragraph_config["font_size"]` follows CE's scale (24 draws an em of a
    third of a unit, CE's size); `size` gives the em in scene units instead.
    The colour setting is ignored: the pygments style decides every colour.
    """

    _styles_list_cache = None
    default_background_config = {
        "buff": 0.3,
        "fill_color": None,
        "stroke_color": WHITE,
        "corner_radius": 0.2,
        "stroke_width": 1,
        "fill_opacity": 1,
    }
    default_paragraph_config = {
        "font": None,
        "font_size": 24,
        "line_spacing": 0.5,
        "disable_ligatures": True,
    }

    def __init__(
        self,
        code_file=None,
        code_string=None,
        language=None,
        formatter_style="vim",
        tab_width=4,
        add_line_numbers=True,
        line_numbers_from=1,
        background="rectangle",
        background_config=None,
        paragraph_config=None,
    ):
        pygments = _pygments()
        lexers = pygments.lexers
        if background not in ("rectangle", "window"):
            raise ValueError(f"Unknown background type: {background}")
        if code_file is not None:
            code_file = Path(code_file)
            code_string = code_file.read_text(encoding="utf-8")
            if language is not None:
                lexer = lexers.get_lexer_by_name(language)
            else:
                lexer = lexers.guess_lexer_for_filename(code_file.name, code_string)
        elif code_string is not None:
            if language is not None:
                lexer = lexers.get_lexer_by_name(language)
            else:
                lexer = lexers.guess_lexer(code_string)
        else:
            raise ValueError("Either a code file or a code string must be specified.")
        code_string = code_string.expandtabs(tabsize=tab_width)
        style = self.get_pygments_style(formatter_style) if isinstance(formatter_style, str) else formatter_style
        if not (isinstance(style, type) and issubclass(style, pygments.style.Style)):
            raise TypeError("formatter_style must be a pygments style name or a pygments Style class")

        paragraph = self._paragraph_config(paragraph_config)
        background_style = self._background_config(background_config, style)
        foreground = _token_color(style, pygments.token.Text) or BLACK
        line_number_color = style.line_number_color
        if line_number_color == "inherit" or not line_number_color:
            line_number_color = foreground

        super().__init__()
        self.language = lexer.name
        self.formatter_style = style
        self.font = paragraph["font"]
        self.size = paragraph["size"]
        lines = _highlighted_lines(lexer, style, code_string)
        self.code_string = "\n".join(text for text, _ in lines)

        size = paragraph["size"]
        pitch = (1 + paragraph["line_spacing"]) * _CE_PITCH_FACTOR * size
        self.line_pitch = pitch
        self.code_lines = VGroup(*(
            self._line(text, paragraph, foreground, colors).shift(-index * pitch * UP)
            for index, (text, colors) in enumerate(lines)
        ))
        self.code_lines.chars = list(self.code_lines.submobjects)

        # The vertical extents of " pA<n>" that CE appends to the first and last
        # lines, measured on their own baselines instead of glued to the text.
        reference = self._line("pA" + str(line_numbers_from), paragraph, foreground, ())
        reference_top = float(reference.get_top()[1])
        reference_bottom = float(reference.get_bottom()[1])
        last_baseline = -(len(lines) - 1) * pitch
        ink = _ink_box(self.code_lines.submobjects)
        top = reference_top if ink is None else max(reference_top, ink[3])
        bottom = last_baseline + reference_bottom if ink is None else min(last_baseline + reference_bottom, ink[1])
        center_x = 0.0 if ink is None else (ink[0] + ink[2]) / 2
        shift = (-center_x, -(top + bottom) / 2, 0)
        self.code_lines.shift(shift)
        self.baselines = [-index * pitch + shift[1] for index in range(len(lines))]
        top, bottom = top + shift[1], bottom + shift[1]
        code_left = 0.0 if ink is None else ink[0] + shift[0]
        code_right = 0.0 if ink is None else ink[2] + shift[0]

        content = [self.code_lines]
        if add_line_numbers:
            numbers = []
            for offset, baseline in enumerate(self.baselines):
                number = self._line(str(line_numbers_from + offset), paragraph, line_number_color, ())
                number.shift((code_left - _LINE_NUMBER_BUFF - float(number.get_right()[0]), baseline, 0))
                numbers.append(number)
            self.line_numbers = VGroup(*numbers)
            content.insert(0, self.line_numbers)
            self.add(self.line_numbers)
        self.add(self.code_lines)

        box = _ink_box(content)
        left = code_left if box is None else min(box[0], code_left)
        right = code_right if box is None else max(box[2], code_right)
        top = top if box is None else max(top, box[3])
        bottom = bottom if box is None else min(bottom, box[1])
        self.background = self._background(background, background_style, left, right, bottom, top)
        self.add_to_back(self.background)

    @staticmethod
    def _paragraph_config(paragraph_config):
        config = dict(Code.default_paragraph_config)
        config.update(paragraph_config or {})
        unknown = sorted(key for key in config if key not in _PARAGRAPH_KEYS)
        if unknown:
            raise TypeError(
                f"Code's paragraph_config does not take {', '.join(map(repr, unknown))}; "
                f"it takes {', '.join(_PARAGRAPH_KEYS)}"
            )
        config.pop("color", None)
        family = config.get("font") or default_monospace_font()
        config["font"] = _face_name(family, config.pop("weight", None), config.pop("slant", None))
        from .glyphs import find_face

        find_face(config["font"])
        if config.get("size") is not None:
            size = float(config["size"])
        else:
            size = float(config.get("font_size", 24)) / _CE_POINTS_PER_UNIT
        if not size > 0 or size == float("inf"):
            raise ValueError(f"Code needs a positive, finite text size, got {size}")
        config["size"] = size
        line_spacing = float(config.get("line_spacing", 0.5))
        config["line_spacing"] = _CE_DEFAULT_LINE_SPACING if line_spacing == -1 else line_spacing
        return config

    @staticmethod
    def _background_config(background_config, style):
        config = dict(Code.default_background_config)
        config.update(background_config or {})
        unknown = sorted(key for key in config if key not in _BACKGROUND_KEYS)
        if unknown:
            raise TypeError(
                f"Code's background_config does not take {', '.join(map(repr, unknown))}; "
                f"it takes {', '.join(_BACKGROUND_KEYS)}"
            )
        if "color" in config:
            config["stroke_color"] = config.pop("color")
        if config["fill_color"] is None:
            config["fill_color"] = style.background_color or BLACK
        return config

    @staticmethod
    def _line(text, paragraph, color, colors):
        from .text import Text

        if not text.strip():
            return VGroup()
        try:
            return Text(
                text,
                font=paragraph["font"],
                size=paragraph["size"],
                color=color,
                center=False,
                t2c=[(range(start, stop), value) for start, stop, value in colors],
            )
        except ValueError as error:
            if str(error).endswith("produced no geometry"):
                return VGroup()
            raise

    @staticmethod
    def _background(kind, config, left, right, bottom, top):
        from janim.core.shapes import Dot, RoundedRectangle

        buff = float(config["buff"])
        buttons = None
        if kind == "window":
            buttons = VGroup(*(
                Dot(radius=0.1, fill_color=color, stroke_width=0.0)
                for color in _WINDOW_BUTTON_COLORS
            )).arrange(RIGHT, buff=0.1)
            # CE: next_to(content, UP, buff=0.1), align_to(content, LEFT), shift
            # 0.1 left, surround everything, then shift the buttons 0.1 up-left.
            buttons.shift((
                left - 0.1 - float(buttons.get_left()[0]),
                top + 0.1 - float(buttons.get_bottom()[1]),
                0,
            ))
            left = min(left, float(buttons.get_left()[0]))
            right = max(right, float(buttons.get_right()[0]))
            top = max(top, float(buttons.get_top()[1]))
            buttons.shift(0.1 * UP + 0.1 * LEFT)
        rectangle = RoundedRectangle(
            width=right - left + 2 * buff,
            height=top - bottom + 2 * buff,
            corner_radius=config["corner_radius"],
        )
        rectangle.move_to(((left + right) / 2, (bottom + top) / 2, 0))
        rectangle.set_fill(config["fill_color"], opacity=config["fill_opacity"])
        rectangle.set_stroke(
            config["stroke_color"],
            width=config["stroke_width"],
            opacity=config.get("stroke_opacity", 1.0),
        )
        if buttons is not None:
            rectangle.add(buttons)
        return rectangle

    @classmethod
    def get_pygments_style(cls, name):
        """Return the pygments style class registered under `name`."""
        return _pygments().styles.get_style_by_name(name)

    @classmethod
    def get_styles_list(cls):
        """The names of every pygments style available."""
        if cls._styles_list_cache is None:
            cls._styles_list_cache = list(_pygments().styles.get_all_styles())
        return cls._styles_list_cache
