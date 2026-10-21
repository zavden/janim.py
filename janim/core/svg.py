"""SVG document import."""

from dataclasses import dataclass, field
import math
from pathlib import Path
import re
import warnings

import numpy as np

from ._atan import scalar_atan2

from ._ranges import linear_range
from ._named_colors import NAMED_COLORS
from .algebra import apply_matrix_rows
from .bezier import cubic_to_two_quadratics
from .colorspace import color_to_rgba
from .gradients import FillGradient, RAMP_RESOLUTION
from .mobject import VGroup, VMobject


@dataclass
class XMLNode:
    name: str
    attrs: list = field(default_factory=list)
    children: list = field(default_factory=list)


_ENTITY_RE = re.compile(r"&(#[xX]([0-9A-Fa-f]+)|#([0-9]+)|lt|gt|quot|apos|amp);")
_ENTITIES = {"lt": "<", "gt": ">", "quot": '"', "apos": "'", "amp": "&"}


def _decode_entities(text):
    def character(match):
        body = match[1]
        if not body.startswith("#"):
            return _ENTITIES[body]
        try:
            value = int(match[2], 16) if match[2] is not None else int(match[3], 10)
        except ValueError:
            return "\ufffd"
        return chr(value) if value <= 0x10FFFF and not 0xD800 <= value <= 0xDFFF else "\ufffd"

    return _ENTITY_RE.sub(character, text)


def _find_tag_end(text, start):
    quote = None
    for index in range(start, len(text)):
        character = text[index]
        if quote is not None:
            if character == quote:
                quote = None
        elif character in "\"'":
            quote = character
        elif character == ">":
            return index
    return None


def _xml_parse(text):
    root = XMLNode("#root")
    stack = [root]
    index = 0
    while index < len(text):
        start = text.find("<", index)
        if start < 0:
            break
        content = _decode_entities(text[index:start])
        if content.strip():
            stack[-1].children.append(content)
        special = next(
            (entry for entry in (("<!--", "-->"), ("<![CDATA[", "]]>") , ("<?", "?>")) if text.startswith(
                entry[0],
                start,
            )),
            None,
        )
        if special:
            finish = text.find(special[1], start + len(special[0]))
            finish = len(text) if finish < 0 else finish
            if special[0] == "<![CDATA[":
                stack[-1].children.append(text[start + 9:finish])
            index = finish + len(special[1])
            continue
        if text.startswith("<!", start):
            depth = 0
            index = start
            while index < len(text):
                character = text[index]
                depth += int(character == "[") - int(character == "]")
                index += 1
                if character == ">" and depth <= 0:
                    break
            continue
        finish = _find_tag_end(text, start)
        if finish is None:
            break
        body = text[start + 1:finish]
        if body.startswith("/"):
            name = body[1:].strip()
            for position in range(len(stack) - 1, 0, -1):
                if stack[position].name == name:
                    del stack[position:]
                    break
        else:
            self_closing = body.endswith("/")
            body = body[:-1] if self_closing else body
            match = re.match(r"^[\w:.-]+", body)
            if match:
                attrs = []
                for attr in re.finditer(r'''([\w:.-]+)\s*=\s*("([^"]*)"|'([^']*)')''', body[match.end():]):
                    attrs.append((attr[1], _decode_entities(attr[3] if attr[3] is not None else attr[4])))
                node = XMLNode(match[0], attrs)
                stack[-1].children.append(node)
                if not self_closing:
                    stack.append(node)
        index = finish + 1
    return root


def _local_name(name):
    return name.rsplit(":", 1)[-1]


def _prefix(name):
    return name.rsplit(":", 1)[0] if ":" in name else ""


def _attr(node, name, default=None):
    return next((value for key, value in node.attrs if key == name or _local_name(key) == name), default)


_NUMBER = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
_NUMBER_RE = re.compile(_NUMBER)
_UNITS = {"px": 1.0, "pt": 96 / 72, "pc": 16.0, "mm": 96 / 25.4, "cm": 96 / 2.54, "in": 96.0}


def _flt(value, default=None):
    if value is None:
        return default
    value = value.strip()
    match = re.match(_NUMBER, value)
    return default if match is None else float(
        match[0],
    ) * _UNITS.get(
        value[match.end():].strip().lower(),
        1.0,
    )


def _floats(value):
    return [float(match[0]) for match in re.finditer(_NUMBER, value)]


def _affine(a, b, c, d, e, f):
    return np.array(((a, c, e), (b, d, f), (0, 0, 1)), dtype=np.float64)


def _translation(x, y):
    return _affine(1, 0, 0, 1, x, y)


def _matmul(first, second):
    return apply_matrix_rows(second.T, first).T


def _inverse(matrix):
    # StaticArrays' 3x3 inverse, with its exact division and cross order.
    first, second, third = matrix.T.copy()
    y0 = np.cross(second, third)
    products = first * y0
    determinant = (products[0] + products[1]) + products[2]
    if determinant == 0:
        raise ValueError("singular SVG transform")
    first = first / determinant
    return np.array((y0 / determinant, np.cross(third, first), np.cross(first, second)))


def _parse_transform(build, value):
    matrix = np.eye(3)
    if value is None:
        return matrix
    for match in re.finditer(r"(\w+)\s*\(([^)]*)\)", value):
        name, args = match[1], _floats(match[2])
        if name == "matrix" and len(args) == 6:
            transform = _affine(*args)
        elif name == "translate" and args:
            transform = _translation(args[0], args[1] if len(args) > 1 else 0)
        elif name == "scale" and args:
            transform = _affine(args[0], 0, 0, args[1] if len(args) > 1 else args[0], 0, 0)
        elif name == "rotate" and args:
            angle = args[0] * (math.pi / 180)
            transform = _affine(math.cos(angle), math.sin(angle), -math.sin(angle), math.cos(angle), 0, 0)
            if len(args) >= 3:
                transform = _matmul(
                    _matmul(_translation(args[1], args[2]), transform),
                    _translation(-args[1], -args[2]),
                )
        elif name == "skewX" and args:
            transform = _affine(1, 0, math.tan(args[0] * (math.pi / 180)), 1, 0, 0)
        elif name == "skewY" and args:
            transform = _affine(1, math.tan(args[0] * (math.pi / 180)), 0, 1, 0, 0)
        else:
            build.note("transform:" + name)
            transform = np.eye(3)
        matrix = _matmul(matrix, transform)
    return matrix


def _svg_paint(build, value, computed):
    value = value.strip()
    lower = value.lower()
    if lower in ("none", "transparent"):
        return None
    if lower.startswith("url("):
        match = re.match(r'''url\(\s*['"]?#([^'")\s]+)''', value)
        if match:
            return "url", match[1]
    elif lower == "currentcolor":
        return _svg_paint(build, computed.get("color", "black"), {})
    elif match := re.fullmatch(r"rgba?\(([^)]*)\)", lower):
        values = []
        for part in filter(None, re.split(r"[,\s/]+", match[1].strip())):
            try:
                number = float(part[:-1] if part.endswith("%") else part)
            except ValueError:
                number = 0.0
            values.append(np.float32(number * 2.55 if part.endswith("%") else number))
        if len(values) >= 3:
            alpha = np.clip(
                values[3] / np.float32(255) if values[3] > 1 else values[3],
                0,
                1,
            ) if len(
                values,
            ) >= 4 else np.float32(
                1,
            )
            rgb = np.clip(np.array(values[:3]) / np.float32(255), 0, 1)
            return "rgb", rgb, np.float32(alpha)
    elif re.fullmatch(r"#(?:[0-9a-f]{4}|[0-9a-f]{8})", lower):
        code = lower[1:]
        code = "".join(character * 2 for character in code) if len(code) == 4 else code
        rgba = np.array([int(code[index:index + 2], 16) / 255 for index in range(0, 8, 2)], dtype=np.float32)
        return "rgb", rgba[:3], rgba[3]
    elif lower.startswith("#") or lower in NAMED_COLORS:
        try:
            return "rgb", color_to_rgba(lower)[:3], np.float32(1)
        except ValueError:
            pass
    build.note("paint:" + value)
    return "rgb", np.zeros(3, dtype=np.float32), np.float32(1)


_INHERITED = tuple(
    "fill stroke stroke-width fill-opacity stroke-opacity fill-rule color visibility font-family font-size text-anchor stroke-linejoin".split(),
)
_PRESENTATION = (*_INHERITED, "opacity", "stop-color", "stop-opacity", "clip-path", "display")
_UNSUPPORTED = tuple(
    "stroke-dasharray stroke-dashoffset stroke-linecap stroke-miterlimit filter mask marker-start marker-mid marker-end paint-order vector-effect clip-rule baseline-shift letter-spacing word-spacing".split(),
)


def _declarations(body):
    result = []
    for part in body.split(";"):
        if ":" in part:
            key, value = part.split(":", 1)
            if key.strip() and value.strip():
                result.append((key.strip().lower(), value.strip()))
    return result


@dataclass
class SVGContext:
    matrix: np.ndarray
    style: dict
    opacity: float = 1.0
    clip: object = None


class SVGBuild:
    def __init__(self, viewbox, source_name):
        self.byid = {}
        self.css = []
        self.viewbox = viewbox
        self.sink = []
        self.unknowns = {}
        self.use_stack = []
        self.source_name = source_name

    def note(self, feature):
        self.unknowns[feature] = None

    def index(self, node):
        identity = _attr(node, "id")
        if identity is not None:
            self.byid.setdefault(identity, node)
        if _local_name(node.name) == "style":
            for child in node.children:
                if isinstance(child, str):
                    self.parse_css(child)
        for child in node.children:
            if isinstance(child, XMLNode):
                self.index(child)

    def parse_css(self, text):
        clean = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        for match in re.finditer(r"([^{}]+)\{([^}]*)\}", clean):
            declarations = _declarations(match[2])
            if not declarations:
                continue
            for selector in match[1].split(","):
                selector = selector.strip()
                if not selector:
                    continue
                parsed = re.fullmatch(r"(\*|[A-Za-z][\w-]*)?((?:[.#][\w-]+)*)", selector)
                if not parsed:
                    self.note("css-selector:" + selector)
                    continue
                tag = "" if parsed[1] in (None, "*") else parsed[1]
                classes = re.findall(r"\.([\w-]+)", parsed[2])
                identities = re.findall(r"#([\w-]+)", parsed[2])
                identity = identities[-1] if identities else ""
                specificity = int(bool(identity)), len(classes), int(bool(tag))
                self.css.append((specificity, len(self.css), tag, classes, identity, declarations))

    def own_style(self, node):
        result = {}
        for key, value in node.attrs:
            key = _local_name(key)
            if key in _PRESENTATION:
                result[key] = value.strip()
            elif key in _UNSUPPORTED and not (key == "clip-rule" and value.strip() == "nonzero"):
                self.note("attr:" + key)
        for _, _, tag, classes, identity, declarations in self.css:
            if tag and tag != _local_name(node.name):
                continue
            if identity and identity != _attr(node, "id", ""):
                continue
            if any(name not in _attr(node, "class", "").split() for name in classes):
                continue
            self._apply_declarations(result, declarations)
        self._apply_declarations(result, _declarations(_attr(node, "style", "")))
        return result

    def _apply_declarations(self, result, declarations):
        for key, value in declarations:
            if key in _PRESENTATION:
                result[key] = value
            elif key in _UNSUPPORTED:
                self.note("attr:" + key)


def _computed_style(inherited, own):
    return {**inherited, **{key: value for key, value in own.items() if value != "inherit"}}


def _inheritable(style):
    return {key: value for key, value in style.items() if key in _INHERITED}


class PathScan:
    def __init__(self, source):
        self.source = source
        self.index = 0

    def skip(self):
        while self.index < len(self.source) and self.source[self.index] in " \t\n\r,":
            self.index += 1

    def done(self):
        self.skip()
        return self.index >= len(self.source)

    def number(self):
        self.skip()
        match = _NUMBER_RE.match(self.source, self.index)
        if not match:
            raise ValueError(f"malformed SVG path number at offset {self.index}")
        self.index = match.end()
        return float(match[0])

    def flag(self):
        self.skip()
        if self.index >= len(self.source) or self.source[self.index] not in "01":
            raise ValueError(f"SVG arc flag must be 0 or 1 at offset {self.index}")
        value = self.source[self.index] == "1"
        self.index += 1
        return value


class _PointBuffer:
    """Build one SVG element in linear space, then allocate its SoA once."""

    def __init__(self):
        self.points = []

    def start_new_path(self, point):
        if self.points:
            self.points.append(self.points[-1].copy())
        self.points.append(np.array(point, dtype=np.float32))
        return self

    def add_line_to(self, point):
        if not self.points:
            raise ValueError("a line command needs a starting point")
        point = np.array(point, dtype=np.float32)
        self.points.extend(((self.points[-1] + point) / np.float32(2), point))
        return self

    def add_quadratic_bezier_curve_to(self, handle, anchor):
        if not self.points:
            raise ValueError("a quadratic command needs a starting point")
        self.points.extend((np.array(handle, dtype=np.float32), np.array(anchor, dtype=np.float32)))
        return self

    def append_points(self, points):
        self.points.extend(np.array(point, dtype=np.float32) for point in points)
        return self

    def note_changed_data(self):
        return self


def _ellipse_arc_append(mobject, transform, cx, cy, rx, ry, rotation, start, sweep):
    count = math.floor(15 * (abs(sweep) / math.tau)) + 1
    nudge = 1 / math.cos(sweep / count / 2)
    cosine, sine = math.cos(rotation), math.sin(rotation)
    mapped = []
    for index, angle in enumerate(linear_range(start, start + sweep, 2 * count + 1)):
        ux, uy = math.cos(angle), math.sin(angle)
        if index % 2:
            ux *= nudge
            uy *= nudge
        qx, qy = rx * ux, ry * uy
        mapped.append(transform(cosine * qx - sine * qy + cx, sine * qx + cosine * qy + cy))
    delta = mobject.points[-1] - mapped[0]
    mobject.append_points(np.array(mapped[1:], dtype=np.float32) + delta)


def _arc_to(mobject, transform, cx, cy, rx, ry, rotation_degrees, large, sweep, x, y):
    if x == cx and y == cy:
        return
    if rx == 0 or ry == 0:
        mobject.add_line_to(transform(x, y))
        return
    rx, ry = abs(rx), abs(ry)
    rotation = rotation_degrees * (math.pi / 180)
    cosine, sine = math.cos(rotation), math.sin(rotation)
    dx, dy = (cx - x) / 2, (cy - y) / 2
    xp, yp = cosine * dx + sine * dy, -sine * dx + cosine * dy
    scale = xp * xp / (rx * rx) + yp * yp / (ry * ry)
    if scale > 1:
        rx *= math.sqrt(scale)
        ry *= math.sqrt(scale)
    rx2, ry2, xp2, yp2 = rx * rx, ry * ry, xp * xp, yp * yp
    numerator = rx2 * ry2 - rx2 * yp2 - ry2 * xp2
    denominator = rx2 * yp2 + ry2 * xp2
    coefficient = (1 if large != sweep else -1) * math.sqrt(max(numerator, 0.0) / denominator)
    cxp, cyp = coefficient * rx * yp / ry, -coefficient * ry * xp / rx
    center_x = cosine * cxp - sine * cyp + (cx + x) / 2
    center_y = sine * cxp + cosine * cyp + (cy + y) / 2
    first = scalar_atan2((yp - cyp) / ry, (xp - cxp) / rx)
    last = scalar_atan2((-yp - cyp) / ry, (-xp - cxp) / rx)
    delta = last - first
    if sweep and delta < 0:
        delta += math.tau
    if not sweep and delta > 0:
        delta -= math.tau
    _ellipse_arc_append(mobject, transform, center_x, center_y, rx, ry, rotation, first, delta)


def _path_data(mobject, data, transform):
    scan = PathScan(data)
    cx = cy = sx = sy = control_x = control_y = 0.0
    command = last_command = ""
    while not scan.done():
        character = scan.source[scan.index]
        explicit = character.isalpha()
        if explicit:
            command = character
            scan.index += 1
        relative = command.islower()
        kind = command.upper()
        if kind in ("M", "L"):
            x, y = scan.number(), scan.number()
            if relative:
                x += cx
                y += cy
            cx, cy = x, y
            if kind == "M":
                sx, sy = x, y
                mobject.start_new_path(transform(x, y))
                command = "l" if relative else "L"
            else:
                mobject.add_line_to(transform(x, y))
        elif kind == "H":
            x = scan.number()
            cx = cx + x if relative else x
            mobject.add_line_to(transform(cx, cy))
        elif kind == "V":
            y = scan.number()
            cy = cy + y if relative else y
            mobject.add_line_to(transform(cx, cy))
        elif kind in ("C", "S"):
            if kind == "C":
                x1, y1 = scan.number(), scan.number()
                if relative:
                    x1 += cx
                    y1 += cy
            else:
                x1 = 2 * cx - control_x if last_command in ("C", "S") else cx
                y1 = 2 * cy - control_y if last_command in ("C", "S") else cy
            x2, y2, x, y = (scan.number() for _ in range(4))
            if relative:
                x2 += cx
                y2 += cy
                x += cx
                y += cy
            first, middle, second = cubic_to_two_quadratics(
                transform(cx, cy),
                transform(x1, y1),
                transform(x2, y2),
                transform(x, y),
            )
            mobject.add_quadratic_bezier_curve_to(first, middle)
            mobject.add_quadratic_bezier_curve_to(second, transform(x, y))
            control_x, control_y = x2, y2
            cx, cy = x, y
        elif kind in ("Q", "T"):
            if kind == "Q":
                x1, y1 = scan.number(), scan.number()
                if relative:
                    x1 += cx
                    y1 += cy
            else:
                x1 = 2 * cx - control_x if last_command in ("Q", "T") else cx
                y1 = 2 * cy - control_y if last_command in ("Q", "T") else cy
            x, y = scan.number(), scan.number()
            if relative:
                x += cx
                y += cy
            mobject.add_quadratic_bezier_curve_to(transform(x1, y1), transform(x, y))
            control_x, control_y = x1, y1
            cx, cy = x, y
        elif kind == "A":
            rx, ry, rotation = scan.number(), scan.number(), scan.number()
            large, sweep = scan.flag(), scan.flag()
            x, y = scan.number(), scan.number()
            if relative:
                x += cx
                y += cy
            _arc_to(mobject, transform, cx, cy, rx, ry, rotation, large, sweep, x, y)
            cx, cy = x, y
        elif kind == "Z" and explicit:
            if cx != sx or cy != sy:
                mobject.add_line_to(transform(sx, sy))
            cx, cy = sx, sy
        else:
            raise ValueError(f"unknown or misplaced SVG path command {command!r}")
        last_command = kind
    return mobject


def _make_trans(matrix):
    def transform(x, y):
        px = matrix[0, 0] * x + matrix[0, 1] * y + matrix[0, 2]
        py = matrix[1, 0] * x + matrix[1, 1] * y + matrix[1, 2]
        return np.array((px, py, 0), dtype=np.float32)

    return transform


def _drop_point_subpaths(mobject):
    pieces = []
    for subpath in mobject.get_subpaths():
        if np.all(subpath == subpath[0]):
            continue
        if pieces:
            pieces.append(pieces[-1][-1:])
        pieces.append(subpath)
    count = sum(len(piece) for piece in pieces)
    if count != len(mobject.points):
        mobject.set_points(np.concatenate(pieces) if pieces else np.empty((0, 3), dtype=np.float32))


def _rect_geometry(mobject, transform, x, y, width, height, rx, ry):
    if rx <= 0 and ry <= 0:
        mobject.start_new_path(transform(x, y))
        for px, py in ((x + width, y), (x + width, y + height), (x, y + height), (x, y)):
            mobject.add_line_to(transform(px, py))
        return
    rx = ry if rx <= 0 else rx
    ry = rx if ry <= 0 else ry
    rx, ry = min(rx, width / 2), min(ry, height / 2)
    quarter = math.tau / 4
    mobject.start_new_path(transform(x + rx, y))
    segments = (
        (x + width - rx, y, x + width - rx, y + ry, -quarter),
        (x + width, y + height - ry, x + width - rx, y + height - ry, 0.0),
        (x + rx, y + height, x + rx, y + height - ry, quarter),
        (x, y + ry, x + rx, y + ry, 2 * quarter),
    )
    for px, py, cx, cy, start in segments:
        mobject.add_line_to(transform(px, py))
        _ellipse_arc_append(mobject, transform, cx, cy, rx, ry, 0.0, start, quarter)


def _geometry(build, kind, node, mobject, transform):
    def value(name, default=0.0):
        text = _attr(node, name)
        number = _flt(text, default)
        if text is not None and text.strip().endswith("%"):
            number /= 100
            if name in ("x", "x1", "x2", "cx", "width", "rx"):
                number *= build.viewbox[2]
            elif name == "r":
                number *= math.hypot(build.viewbox[2], build.viewbox[3]) / math.sqrt(2)
            else:
                number *= build.viewbox[3]
        return number

    if kind == "path":
        data = _attr(node, "d")
        if data is not None:
            _path_data(mobject, data, transform)
    elif kind == "rect":
        width, height = value("width"), value("height")
        if width > 0 and height > 0:
            _rect_geometry(
                mobject,
                transform,
                value("x"),
                value("y"),
                width,
                height,
                value("rx"),
                value("ry"),
            )
    elif kind in ("circle", "ellipse"):
        rx = value("r") if kind == "circle" else value("rx")
        ry = rx if kind == "circle" else value("ry")
        if rx > 0 and ry > 0:
            start = transform(value("cx") + rx, value("cy"))
            mobject.start_new_path(start)
            _ellipse_arc_append(mobject, transform, value("cx"), value("cy"), rx, ry, 0.0, 0.0, math.tau)
            mobject.points[-1] = start
            mobject.note_changed_data()
    elif kind == "line":
        mobject.start_new_path(transform(value("x1"), value("y1")))
        mobject.add_line_to(transform(value("x2"), value("y2")))
    elif kind in ("polyline", "polygon"):
        values = _floats(_attr(node, "points", ""))
        if len(values) >= 4:
            mobject.start_new_path(transform(values[0], values[1]))
            for x, y in zip(values[2::2], values[3::2]):
                mobject.add_line_to(transform(x, y))
            if kind == "polygon":
                mobject.add_line_to(transform(values[0], values[1]))


def _gradient_stops(build, node, depth=0):
    stops = []
    for child in node.children:
        if not isinstance(child, XMLNode) or _local_name(child.name) != "stop":
            continue
        own = build.own_style(child)
        offset = _attr(child, "offset", "0").strip()
        try:
            time = float(offset[:-1]) / 100 if offset.endswith("%") else float(offset)
        except ValueError:
            time = 0.0
        paint = _svg_paint(build, own.get("stop-color", "black"), {})
        rgb, alpha = (paint[1], paint[2]) if paint is not None and paint[0] == "rgb" else ((0, 0, 0), 1)
        opacity = np.float32(np.clip(_flt(own.get("stop-opacity", "1"), 1.0), 0, 1))
        time = float(np.clip(time, 0, 1))
        if stops:
            time = max(time, stops[-1][0])
        stops.append((time, np.array((*rgb, opacity * alpha), dtype=np.float32)))
    if not stops and depth < 8:
        href = _attr(node, "href", "")
        if href.startswith("#") and href[1:] in build.byid:
            return _gradient_stops(build, build.byid[href[1:]], depth + 1)
    return stops


def _stop_color(stops, time):
    if time <= stops[0][0]:
        return stops[0][1]
    for (first_time, first), (last_time, last) in zip(stops, stops[1:]):
        if time <= last_time:
            near = abs(
                last_time - first_time,
            ) <= math.sqrt(
                np.finfo(np.float64).eps,
            ) * max(
                abs(first_time),
                abs(last_time),
            )
            alpha = 1.0 if near else (time - first_time) / (last_time - first_time)
            return first + np.float32(alpha) * (last - first)
    return stops[-1][1]


def _spread_t(time, spread):
    if spread == 1:
        return 1.0 - abs(time % 2.0 - 1.0)
    if spread == 2:
        return time % 1.0
    return min(1.0, max(0.0, time))


def _radial_t(point, focus):
    ff = focus[0] * focus[0] + focus[1] * focus[1]
    if ff < 1e-12:
        return math.hypot(point[0], point[1])
    delta = point - focus
    a = ff - 1.0
    b = delta[0] * focus[0] + delta[1] * focus[1]
    c = delta[0] * delta[0] + delta[1] * delta[1]
    return (-b - math.sqrt(max(b * b - a * c, 0.0))) / a


def _grad_attr(build, node, name, default, depth=0):
    value = _attr(node, name)
    if value is not None:
        return value
    href = _attr(node, "href", "")
    if depth < 8 and href.startswith("#") and href[1:] in build.byid:
        return _grad_attr(build, build.byid[href[1:]], name, default, depth + 1)
    return default


def _apply_gradient(build, child, node, matrix, which, opacity):
    kind = _local_name(node.name)
    if kind not in ("linearGradient", "radialGradient"):
        build.note("paint-ref:" + kind)
        return
    stops = _gradient_stops(build, node)
    if not stops:
        build.note("gradient-without-stops")
        return
    try:
        inverse = _inverse(matrix)
        gradient_inverse = _inverse(_parse_transform(build, _attr(node, "gradientTransform")))
    except ValueError:
        build.note("gradient-singular-transform")
        return
    bounding = _grad_attr(build, node, "gradientUnits", "objectBoundingBox") == "objectBoundingBox"
    points = child.points.astype(np.float64)
    local = points[:, :1] * inverse[:2, 0] + points[:, 1:2] * inverse[:2, 1] + inverse[:2, 2]
    low = local.min(axis=0)
    size = np.maximum(local.max(axis=0) - low, 1e-12)

    def value(name, default):
        text = _grad_attr(build, node, name, default).strip()
        number = _flt(text, 0.0)
        return number / 100 if text.endswith("%") else number

    spread = {"reflect": 1, "repeat": 2}.get(_grad_attr(build, node, "spreadMethod", "pad"), 0)
    coordinates = (local - low) / size if bounding else local
    mapped = coordinates[:, :1] * gradient_inverse[:2, 0] + coordinates[:, 1:2] * gradient_inverse[:2, 1] + gradient_inverse[:2, 2]
    uv = np.empty((len(points), 2), dtype=np.float32)
    focus = np.zeros(2, dtype=np.float64)
    if kind == "linearGradient":
        first = np.array((value("x1", "0"), value("y1", "0")))
        last = np.array((value("x2", "1" if bounding else "0"), value("y2", "0")))
        delta = last - first
        divisor = max(delta[0] * delta[0] + delta[1] * delta[1], 1e-24)
        products = (mapped - first) * delta
        raw = (products[:, 0] + products[:, 1]) / divisor
        uv[:, 0], uv[:, 1] = raw, 0
    else:
        center = np.array((value("cx", "0.5" if bounding else "0"), value("cy", "0.5" if bounding else "0")))
        radius = max(value("r", "0.5" if bounding else "1"), 1e-12)
        fx = value("fx", str(center[0])) if _grad_attr(build, node, "fx", "").strip() else center[0]
        fy = value("fy", str(center[1])) if _grad_attr(build, node, "fy", "").strip() else center[1]
        focus = (np.array((fx, fy)) - center) / radius
        magnitude = math.hypot(*focus)
        if magnitude > 0.999:
            focus *= 0.999 / magnitude
        radial = (mapped - center) / radius
        uv[:] = radial
        raw = [_radial_t(point, focus) for point in radial]
    rows = child.fill_rgba if which == "fill" else child.stroke_rgba
    for index, time in enumerate(raw):
        color = _stop_color(stops, _spread_t(float(time), spread))
        rows[index] = (*color[:3], color[3] * np.float32(opacity))
    if which == "fill":
        ramp = np.empty((RAMP_RESOLUTION, 4), dtype=np.float32)
        for index in range(RAMP_RESOLUTION):
            color = _stop_color(stops, (index + 0.5) / RAMP_RESOLUTION)
            ramp[index] = (*color[:3], color[3] * np.float32(opacity))
        child.fill_gradient = FillGradient(
            "linear" if kind == "linearGradient" else "radial",
            uv,
            tuple(focus.astype(np.float32)),
            spread,
            ramp,
            rows.copy(),
        )
    setattr(child, "default_" + which + "_rgba", _stop_color(stops, 0.5).copy())


def _poly_signed_area(polygon):
    area = 0.0
    for first, last in zip(polygon, np.roll(polygon, -1, axis=0)):
        area += first[0] * last[1] - last[0] * first[1]
    return area / 2


def _point_in_poly(polygon, point):
    inside = False
    for first, last in zip(polygon, np.roll(polygon, -1, axis=0)):
        if (first[1] > point[1]) != (last[1] > point[1]):
            x = first[0] + (point[1] - first[1]) / (last[1] - first[1]) * (last[0] - first[0])
            if x > point[0]:
                inside = not inside
    return inside


def _normalize_evenodd(mobject):
    ends = mobject.get_subpath_end_indices().copy()
    if len(ends) < 2:
        return True
    starts = [0, *(ends[:-1] + 2)]
    polygons = []
    for start, end in zip(starts, ends):
        polygon = []
        for index in range(start, end - 1, 2):
            first, handle, last = mobject.points[index:index + 3, :2].astype(np.float64)
            for time in (0.0, 0.25, 0.5, 0.75):
                polygon.append(
                    (1 - time) ** 2 * first + (2 * time * (1 - time)) * handle + time * time * last,
                )
        polygons.append(np.array(polygon, dtype=np.float64).reshape(-1, 2))
    areas = [_poly_signed_area(polygon) for polygon in polygons]
    depths = [0] * len(polygons)
    for index, polygon in enumerate(polygons):
        count = len(polygon)
        if not count:
            continue
        probes = tuple(dict.fromkeys((0, max(1, count // 3) - 1, max(1, 2 * count // 3) - 1)))
        for other_index, other in enumerate(polygons):
            if other_index != index and len(other) >= 3:
                votes = sum(_point_in_poly(other, polygon[probe]) for probe in probes)
                depths[index] += int(2 * votes > len(probes))
    outer = [index for index, depth in enumerate(depths) if depth == 0] or list(range(len(depths)))
    sign = np.sign(areas[max(outer, key=lambda index: abs(areas[index]))])
    if sign == 0:
        return True
    names = ("points", "fill_rgba", "stroke_rgba", "stroke_width")
    saved = None
    for index, (start, end) in enumerate(zip(starts, ends)):
        wanted = sign if depths[index] % 2 == 0 else -sign
        if areas[index] == 0 or np.sign(areas[index]) == wanted:
            continue
        if saved is None:
            saved = [getattr(mobject, name).copy() for name in names]
        for name in names:
            rows = getattr(mobject, name)
            rows[start:end + 1] = rows[start:end + 1][::-1]
        if end + 1 < len(mobject.points):
            mobject.points[end + 1] = mobject.points[end]
    if saved is None:
        return True
    mobject.subpath_end_indices = None
    if np.array_equal(mobject.get_subpath_end_indices(), ends):
        return True
    for name, original in zip(names, saved):
        getattr(mobject, name)[:] = original
    mobject.subpath_end_indices = None
    return False


def _apply_style(build, child, computed, matrix, opacity):
    fill_opacity = float(np.clip(_flt(computed.get("fill-opacity", "1"), 1.0), 0, 1))
    stroke_opacity = float(np.clip(_flt(computed.get("stroke-opacity", "1"), 1.0), 0, 1))
    width = _flt(computed.get("stroke-width", "1"), 1.0)
    fill = _svg_paint(build, computed.get("fill", "black"), computed)
    if fill is not None and computed.get("fill-rule", "nonzero") == "evenodd":
        if not _normalize_evenodd(child):
            build.note("fill-rule:evenodd")
    if fill is None:
        child.set_fill(opacity=0)
    elif fill[0] == "rgb":
        child.set_fill((*fill[1], 1), fill_opacity * opacity * float(fill[2]))
    elif fill[1] in build.byid:
        _apply_gradient(build, child, build.byid[fill[1]], matrix, "fill", fill_opacity * opacity)
    else:
        build.note("paint-ref:#" + fill[1])
        child.set_fill((0, 0, 0, 1), fill_opacity * opacity)
    joint = computed.get("stroke-linejoin", "")
    if joint in ("miter", "bevel"):
        child.set_joint_type(joint, recurse=False)
    elif joint:
        build.note("stroke-linejoin:" + joint)
    stroke = _svg_paint(build, computed.get("stroke", "none"), computed)
    if stroke is None or width <= 0:
        child.set_stroke(width=0, opacity=0)
    elif stroke[0] == "rgb":
        child.set_stroke((*stroke[1], 1), width=width, opacity=stroke_opacity * opacity * float(stroke[2]))
    elif stroke[1] in build.byid:
        child.set_stroke(width=width)
        _apply_gradient(build, child, build.byid[stroke[1]], matrix, "stroke", stroke_opacity * opacity)
    else:
        build.note("paint-ref:#" + stroke[1])
        child.set_stroke(width=0, opacity=0)


def _clip_id(build, own):
    value = own.get("clip-path", "")
    if not value:
        return None
    match = re.match(r'''url\(\s*['"]?#([^'")\s]+)''', value)
    if match is None:
        build.note("clip-path:" + value)
        return None
    return match[1]


def _attach_clip(build, child, identity, matrix):
    if identity not in build.byid:
        build.note("clip-path:#" + identity)
        return
    node = build.byid[identity]
    if _attr(node, "clipPathUnits", "userSpaceOnUse") != "userSpaceOnUse":
        build.note("clipPathUnits:objectBoundingBox")
    previous_sink = build.sink
    build.sink = shapes = []
    try:
        context = SVGContext(matrix, {"fill": "white"})
        for element in node.children:
            if isinstance(element, XMLNode):
                _walk(build, element, context)
    finally:
        build.sink = previous_sink
    for shape in shapes:
        shape.set_fill(opacity=0).set_stroke(opacity=0, width=0)
        shape.set_key("_clip").add_key("_clipref:" + identity)
    child.add(*shapes)
    if shapes:
        child.add_key("_clipped:" + identity)


def clip_layers(svg):
    """Return ordered layers with frozen copies of each SVG clipping mask."""
    from .compositor_types import Layer, Mask

    layers = []
    run = []
    for child in svg.submobjects:
        clips = [sub for sub in child.submobjects if isinstance(sub, VMobject) and "_clip" in sub.get_keys()]
        if not clips:
            run.append(child)
            continue
        if run:
            layers.append(Layer(*run))
            run = []
        shapes = [
            sub.copy().refresh_bounding_box(recurse_down=True).set_fill((1, 1, 1, 1), 1.0).set_stroke(
                opacity=0,
                width=0,
            )
            for sub in clips
        ]
        layers.append(Layer(child, mask=Mask(*shapes)))
    if run:
        layers.append(Layer(*run))
    return layers


def _collect_text(build, node):
    result = []
    for child in node.children:
        if isinstance(child, str):
            result.append(child)
        elif _local_name(child.name) == "tspan":
            if any(_attr(child, key) is not None for key in ("x", "y", "dx", "dy")):
                build.note("tspan-positioning")
            result.append(_collect_text(build, child))
    return "".join(result)


def _text_element(build, node, computed, matrix, opacity):
    from janim.text.glyphs import FontNotFound, svg_text

    text = re.sub(r"\s+", " ", _collect_text(build, node)).strip()
    if not text:
        return
    size = _flt(computed.get("font-size", "16"), 16.0)
    family = computed.get("font-family", "DejaVu Sans").split(",", 1)[0].strip(" '\"")
    try:
        mob = svg_text(text, font=family, size=size)
    except FontNotFound:
        if family == "DejaVu Sans":
            raise
        build.note("font:" + family)
        mob = svg_text(text, font="DejaVu Sans", size=size)
    anchor = computed.get("text-anchor", "start")
    left, right = float(mob.get_left()[0]), float(mob.get_right()[0])
    dx = -(left + right) / 2 if anchor == "middle" else -right if anchor == "end" else 0.0
    x, y = _flt(_attr(node, "x"), 0.0), _flt(_attr(node, "y"), 0.0)
    transform = _matmul(_matmul(matrix, _affine(1, 0, 0, -1, x, y)), _translation(dx, 0.0))
    for glyph in mob.get_family():
        if glyph.has_points():
            points = glyph.points.astype(np.float64)
            xy = points[:, :1] * transform[:2, 0] + points[:, 1:2] * transform[:2, 1] + transform[:2, 2]
            glyph.points[:, :2] = xy
            glyph.points[:, 2] = 0
            glyph.note_changed_data()
    fill = _svg_paint(build, computed.get("fill", "black"), computed)
    fill_opacity = float(np.clip(_flt(computed.get("fill-opacity", "1"), 1.0), 0, 1))
    if fill is None:
        mob.set_fill(opacity=0)
    elif fill[0] == "rgb":
        mob.set_fill((*fill[1], 1), fill_opacity * opacity * float(fill[2]))
    identity = _attr(node, "id")
    if identity is not None:
        mob.set_key(identity)
    build.sink.append(mob)


_SKIP_ELEMENTS = tuple(
    "title desc metadata defs style namedview linearGradient radialGradient clipPath symbol marker foreignObject".split(),
)
_WARN_SKIP_ELEMENTS = ("pattern", "filter", "mask", "script", "image")
_GRAPHICS = ("path", "rect", "circle", "ellipse", "line", "polyline", "polygon")


def _walk(build, node, context):
    if _prefix(node.name) not in ("", "svg"):
        return
    kind = _local_name(node.name)
    if kind in _SKIP_ELEMENTS:
        return
    if kind in _WARN_SKIP_ELEMENTS:
        build.note("element:" + kind)
        return
    own = build.own_style(node)
    if own.get("display") == "none":
        return
    computed = _computed_style(context.style, own)
    if computed.get("visibility", "visible") in ("hidden", "collapse") and kind in (*_GRAPHICS, "text"):
        return
    matrix = _matmul(context.matrix, _parse_transform(build, _attr(node, "transform")))
    opacity = context.opacity * float(np.clip(_flt(own.get("opacity", "1"), 1.0), 0, 1))
    identity = _clip_id(build, own)
    clip = context.clip
    if identity is not None:
        if clip is not None:
            build.note("nested-clip")
        clip = identity, matrix
    if kind in ("g", "a", "svg", "switch"):
        if kind == "svg":
            matrix = _matmul(matrix, _translation(_flt(_attr(node, "x"), 0.0), _flt(_attr(node, "y"), 0.0)))
        next_context = SVGContext(matrix, _inheritable(computed), opacity, clip)
        if kind == "switch":
            build.note("element:switch")
        for child in node.children:
            if isinstance(child, XMLNode):
                _walk(build, child, next_context)
                if kind == "switch":
                    break
    elif kind == "use":
        href = _attr(node, "href", "")
        if not href.startswith("#"):
            build.note("use:" + href)
            return
        identity = href[1:]
        if identity not in build.byid:
            build.note("use:#" + identity)
            return
        if identity in build.use_stack:
            build.note("use-cycle:#" + identity)
            return
        if len(build.use_stack) >= 20:
            build.note("use-depth")
            return
        shifted = _matmul(matrix, _translation(_flt(_attr(node, "x"), 0.0), _flt(_attr(node, "y"), 0.0)))
        next_context = SVGContext(shifted, _inheritable(computed), opacity, clip)
        build.use_stack.append(identity)
        try:
            target = build.byid[identity]
            if _local_name(target.name) == "symbol":
                for child in target.children:
                    if isinstance(child, XMLNode):
                        _walk(build, child, next_context)
            else:
                _walk(build, target, next_context)
        finally:
            build.use_stack.pop()
    elif kind in _GRAPHICS:
        child = VMobject()
        child.svg_tag = kind
        points = _PointBuffer()
        _geometry(build, kind, node, points, _make_trans(matrix))
        child.set_points(np.array(points.points, dtype=np.float32).reshape(-1, 3))
        _drop_point_subpaths(child)
        if not child.has_points():
            return
        _apply_style(build, child, computed, matrix, opacity)
        if kind == "line":
            child.set_fill(opacity=0)
        identity = _attr(node, "id")
        if identity is not None:
            child.set_key(identity)
        if clip is not None:
            _attach_clip(build, child, *clip)
        build.sink.append(child)
    elif kind == "text":
        _text_element(build, node, computed, matrix, opacity)
    else:
        build.note("element:" + kind)


class SVGMobject(VGroup):
    def __init__(self, source=None, height=2.0, width=None, color=None, *, file_name=None, **kwargs):
        if source is None:
            source = file_name          # ManimGL's keyword for the file
        if source is None:
            raise TypeError("SVGMobject needs a source (a path or SVG text)")
        source = str(source)
        if "<" in source:
            text, name = source, "inline SVG"
        else:
            path = Path(source)
            if not path.is_file():
                raise ValueError(f"SVGMobject: {source!r} is neither an SVG file nor an SVG string")
            text, name = path.read_text(encoding="utf-8"), path.name
        root = _xml_parse(text)
        node = next(
            (child for child in root.children if isinstance(
                child,
                XMLNode,
            ) and _local_name(
                child.name,
            ) == "svg"),
            root,
        )
        if node is root and root.children:
            warnings.warn(
                f"SVGMobject: no SVG root in {name}; parsing the fragment",
                RuntimeWarning,
                stacklevel=2,
            )
        values = _floats(_attr(node, "viewBox", ""))
        if len(values) == 4:
            viewbox = values[0], values[1], max(values[2], 1e-12), max(values[3], 1e-12)
        else:
            viewbox = 0.0, 0.0, _flt(_attr(node, "width"), 100.0), _flt(_attr(node, "height"), 100.0)
        build = SVGBuild(viewbox, name)
        build.index(node)
        build.css.sort(key=lambda rule: rule[:2])
        style = _inheritable(_computed_style({}, build.own_style(node)))
        context = SVGContext(
            _matmul(_affine(1, 0, 0, -1, 0, 0), _parse_transform(build, _attr(node, "transform"))),
            style,
        )
        for child in node.children:
            if isinstance(child, XMLNode):
                _walk(build, child, context)
        if not build.sink:
            raise ValueError(f"SVGMobject: {name} produced no geometry")
        super().__init__(*build.sink, **kwargs)
        old_width, old_height = float(self.get_width()), float(self.get_height())
        if width is not None and old_width > 1e-9:
            scale = float(width) / old_width
        elif old_height > 1e-9:
            scale = float(height) / old_height
        elif old_width > 1e-9:
            scale = float(height if width is None else width) / old_width
        else:
            scale = 1.0
        self.scale(scale).move_to((0, 0, 0))
        for child in self.get_family():
            child.stroke_width *= np.float64(100 * scale)
            child.default_stroke_width = np.float32(np.float64(child.default_stroke_width) * (100 * scale))
        if color is not None:
            self.set_color(color)
        if build.unknowns:
            warnings.warn(
                f"SVGMobject: {name} uses unsupported features; ignored: " + ", ".join(
                    sorted(build.unknowns),
                ),
                RuntimeWarning,
                stacklevel=2,
            )
