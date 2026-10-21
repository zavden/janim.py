"""LaTeX and dvisvgm formulas, with Janim's metric and span contracts."""

import copy
from functools import lru_cache
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import warnings

import numpy as np

from janim.constants import DEFAULT_FONT_SIZE, WHITE
from janim.core.mobject import VGroup
from janim.core.mobject import VMobject
from .text import glyph_style, style_pairs, text_size, text_style_keywords
from .tex_labelling import label_tex, selectors


XH_MATH = 0.4546249806880951
GL_SIZE_LATEX = 2.0700
GL_SIZE_TEXT_MODE = 2.1839
TEX_DOCUMENTCLASS = r"\documentclass[preview]{standalone}"
TEX_BASE_PREAMBLE = r"\usepackage{amsmath,amssymb}"
TEX_COLOR_PREAMBLE = r"\usepackage{xcolor}"
_SVG_MEMO = {}
_CALIBRATIONS = {}
_TEX_LOCK = threading.RLock()
_COMPILE_TIMEOUT = 120.0


class TexTemplate:
    """Preamble and document additions to the fixed standalone template."""

    def __init__(self, preamble=None):
        self.preamble = [] if preamble is None else [str(preamble)]
        self.document = []

    def add_to_preamble(self, *lines):
        self.preamble.extend(map(str, lines))
        return self

    def add_to_document(self, *lines):
        self.document.extend(map(str, lines))
        return self

    def copy(self):
        return copy.deepcopy(self)

    def __repr__(self):
        return f"TexTemplate(preamble={self.preamble!r}, document={self.document!r})"


def tex_source(template, body="…", *, math=True, color=False, alignment=""):
    if not isinstance(template, TexTemplate):
        raise TypeError("template must be a TexTemplate")
    if not isinstance(body, str):
        raise TypeError("the TeX body must be a string")
    inner = body if not math or body.lstrip().startswith(r"\begin{") else "$\\displaystyle " + body + "$"
    preamble = [TEX_BASE_PREAMBLE]
    if color:
        preamble.append(TEX_COLOR_PREAMBLE)
    preamble.extend(template.preamble)
    post = "\n".join(template.document) + "\n" if template.document else ""
    align = alignment + "\n" if alignment else ""
    paragraph = "\n" if alignment else ""
    return TEX_DOCUMENTCLASS + "\n" + "\n".join(preamble) + "\n\\begin{document}\n" + post + align + inner + paragraph + "\n\\end{document}\n"


def _latex_source(body, *, color=False):
    return tex_source(TexTemplate(), body, color=color)


@lru_cache(maxsize=1)
def _latex_version():
    values = []
    for executable in ("latex", "dvisvgm"):
        try:
            result = subprocess.run(
                [executable, "--version"],
                check=True,
                capture_output=True,
                text=True,
            )
            values.append(result.stdout.split("\n", 1)[0])
        except (OSError, subprocess.CalledProcessError):
            values.append("?")
    return " + ".join(values)


def _cache_directory():
    default = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "janim/tex"
    return Path(os.environ.get("JANIM_TEX_CACHE") or default)


def _cache_key(document):
    return hashlib.sha256(("latex\0" + _latex_version() + "\0" + document).encode()).hexdigest()


def _run_compiler(command, **kwargs):
    try:
        return subprocess.run(command, timeout=_COMPILE_TIMEOUT, **kwargs)
    except subprocess.TimeoutExpired:
        raise ValueError(f"{Path(command[0]).name} exceeded the {_COMPILE_TIMEOUT:g} second compilation timeout") from None


def _latex_error(path):
    lines = path.read_text(errors="replace").splitlines() if path.is_file() else []
    first = next((index for index, line in enumerate(lines) if line.startswith("!")), None)
    if first is None:
        return "  (no '!' line in the LaTeX log)"
    message = "\n".join("  " + line for line in lines[first:first + 3])
    if "Missing $ inserted" in lines[first] or "forgotten $" in lines[first]:
        message += "\n  A mode mismatch: use Tex for ^ and _, and TexText for prose with inline $...$."
    elif "Undefined control sequence" in lines[first]:
        message += "\n  A macro or package is missing; add it with TexTemplate.add_to_preamble()."
    return message


def _compile_svg(document):
    latex, dvisvgm = shutil.which("latex"), shutil.which("dvisvgm")
    if latex is None or dvisvgm is None:
        raise ValueError("Tex requires latex and dvisvgm on PATH")
    with tempfile.TemporaryDirectory(prefix="janim-tex-") as directory:
        directory = Path(directory)
        (directory / "f.tex").write_text(document, encoding="utf-8")
        result = _run_compiler(
            [latex, "-interaction=batchmode", "-halt-on-error", "f.tex"],
            cwd=directory,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode:
            quoted = "\n".join("  │ " + line for line in document.rstrip().split("\n"))
            raise ValueError("LaTeX could not compile this:\n" + _latex_error(
                directory / "f.log",
            ) + "\nthe document it was given:\n" + quoted)
        result = _run_compiler(
            [dvisvgm, "--no-fonts", "-o", "f.svg", "f.dvi"],
            cwd=directory,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode:
            raise ValueError(f"dvisvgm could not convert the LaTeX output: {result.stderr.strip()}")
        return (directory / "f.svg").read_text(encoding="utf-8")


def _svg_latex_source(document):
    key = _cache_key(document)
    with _TEX_LOCK:
        if key in _SVG_MEMO:
            return _SVG_MEMO[key]
        path = _cache_directory() / (key[:40] + ".svg")
        if path.is_file():
            svg = path.read_text(encoding="utf-8")
            if not svg.rstrip().endswith("</svg>"):
                raise ValueError(f"incomplete LaTeX SVG cache entry: {path}")
        else:
            svg = _compile_svg(document)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
            try:
                temporary.write_text(svg, encoding="utf-8")
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        _SVG_MEMO[key] = svg
        return svg


def _tex_svg(svg, scale, style):
    from janim.core.svg import XMLNode, SVGBuild, SVGContext, _affine, _local_name, _walk, _xml_parse

    root = _xml_parse(svg)
    node = next(
        (child for child in root.children if isinstance(child, XMLNode) and _local_name(child.name) == "svg"),
        root,
    )
    build = SVGBuild((0.0, 0.0, 100.0, 100.0), "tex-svg")
    build.index(node)
    build.css.sort(key=lambda rule: rule[:2])
    context = SVGContext(_affine(scale, 0, 0, -scale, 0, 0), {})
    for child in node.children:
        if isinstance(child, XMLNode):
            _walk(build, child, context)
    children, labels = [], []
    for child in build.sink:
        filled = np.any(child.fill_rgba[:, 3] > 0)
        rows = child.fill_rgba if filled else child.stroke_rgba
        label = 0
        if len(rows):
            red, green, blue = [round(float(value * np.float32(255))) for value in rows[0, :3]]
            label = (red << 16) | (green << 8) | blue
        glyph = VMobject(**style).set_points(child.points)
        if np.any(child.stroke_width > 0) and np.any(child.stroke_rgba[:, 3] > 0) and not filled:
            glyph.set_fill(opacity=0)
            glyph.set_stroke(opacity=1, width=float(child.stroke_width[0] * np.float32(100)) * scale)
        if glyph.has_points():
            children.append(glyph)
            labels.append(label)
    return children, labels


def _calibration(template, math_mode):
    color = any(
        "\\color" in line or "\\textcolor" in line
        for line in (*template.preamble, *template.document)
    )
    document = tex_source(template, "x", math=math_mode, color=color)
    with _TEX_LOCK:
        if document not in _CALIBRATIONS:
            children, _ = _tex_svg(_svg_latex_source(document), 1.0, {"fill_opacity": 1.0})
            probe = VMobject().add(*children)
            _CALIBRATIONS[document] = XH_MATH / float(probe.get_height())
        return _CALIBRATIONS[document]


class Tex(VMobject):
    """Display mathematics through LaTeX, with explicit isolated substrings."""

    _labelled_text = True
    _math_mode = True

    def __init__(
        self,
        *strings,
        size=None,
        font_size=None,
        color=WHITE,
        center=True,
        isolate=(),
        t2c=None,
        tex_to_color_map=None,
        template=None,
        alignment="",
        **kwargs,
    ):
        if not strings or any(not isinstance(value, str) for value in strings):
            raise TypeError("Tex requires at least one string")
        kwargs = text_style_keywords(kwargs, type(self).__name__)
        color = WHITE if color is None else color
        self.string = strings[0] if len(strings) == 1 else " ".join(strings).strip()
        if not self.string.strip():
            raise ValueError(f"{type(self).__name__}: an empty formula has no glyphs")
        patterns = selectors(isolate)
        if len(strings) > 1:
            patterns.extend(strings)
        pairs = style_pairs(t2c) + style_pairs(tex_to_color_map)
        if any(not isinstance(key, str) for key, _ in pairs):
            raise TypeError("Tex t2c keys must be strings")
        self.template = TexTemplate() if template is None else template
        scale_constant = GL_SIZE_LATEX if self._math_mode else GL_SIZE_TEXT_MODE
        self.size = text_size(size, font_size, scale_constant, type(self).__name__)
        self.font_size = self.size * (DEFAULT_FONT_SIZE * scale_constant)
        lab = label_tex(self.string, isolate=patterns, t2c=[key for key, _ in pairs])
        self.labelled_spans = lab.spans
        labelled = len(lab.spans) > 1
        document = tex_source(
            self.template,
            lab.body if labelled else self.string,
            math=self._math_mode,
            color=labelled,
            alignment=alignment,
        )
        super().__init__(**kwargs)
        children, self.labels = _tex_svg(
            _svg_latex_source(document),
            self.size * _calibration(self.template, self._math_mode),
            glyph_style(color, kwargs),
        )
        if not children:
            raise ValueError(f"formula {self.string!r} produced no geometry")
        self.add(*children)
        self.key_runs = {}
        self._apply_labels()
        for key, value in pairs:
            self[key].set_color(value)
        if center:
            self.center()

    def build_groups(self):
        """ManimGL's: consecutive glyphs sharing a label form one group, in reading order."""
        import itertools

        groups = VGroup()
        start = 0
        for _, run in itertools.groupby(self.labels):
            count = len(list(run))
            groups.add(VGroup(*self.submobjects[start:start + count]))
            start += count
        return groups

    def _apply_labels(self):
        spans = self.labelled_spans
        if len(spans) <= 1:
            return
        top = len(spans) - 1
        stray = list(dict.fromkeys(label for label in self.labels if label > top))
        if stray:
            warnings.warn(
                f"Tex: unrecognizable color labels {stray}; those glyphs have no isolate/t2c key",
                RuntimeWarning,
                stacklevel=3,
            )
        self.labels = [0 if label > top else label for label in self.labels]
        for index, label in enumerate(self.labels):
            if not 1 <= label <= top:
                continue
            own = spans[label]
            for first, last in spans[1:]:
                if first <= own[0] and last >= own[1]:
                    self.submobjects[index].add_key(self.string[first:last])
        for first, last in spans[1:]:
            indices = [
                index
                for index, label in enumerate(self.labels)
                if 1 <= label <= top and spans[label][0] >= first and spans[label][1] <= last
            ]
            if indices:
                runs = self.key_runs.setdefault(self.string[first:last], [])
                if indices not in runs:
                    runs.append(indices)

    def get_tex(self):
        return self.string

    get_string = get_tex

    def get_specified_substrings(self):
        return list(dict.fromkeys(self.string[first:last] for first, last in self.labelled_spans[1:]))

    def set_color_by_tex(self, selector, color):
        self[selector].set_color(color)
        return self

    def set_color_by_tex_to_color_map(self, colors):
        for key, color in style_pairs(colors):
            self.set_color_by_tex(key, color)
        return self


class TexText(Tex):
    """LaTeX text mode; inline mathematics is written inside dollar signs."""

    _math_mode = False


MathTex = Tex
LMathTex = Tex
LTex = TexText
