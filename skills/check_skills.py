#!/usr/bin/env python
"""check_skills.py — the lock on this directory.

A skill names real identifiers, real paths, real CLI verbs and real environment
variables, so a rename turns it into a confident lie without touching a line of
it. This asks the library instead of trusting the prose. Four checks:

  1. every `name(` call, `x.method(` call and CamelCase type the skills claim
     is a public name of `janim`, an attribute of one of its core classes, a
     name of one of its documented modules, or a declared internal or foreign
     name (Manim's, WGSL's, Python's own);
  2. every repository path they point at exists;
  3. every `bin/janim <verb>` is a verb the CLI has;
  4. every `JANIM_*` variable they mention is read somewhere under janim/.

    .venv/bin/python skills/check_skills.py            # the skills/ folder beside this file
    .venv/bin/python skills/check_skills.py DIR        # another folder of *.md (a negative control)

It prints every problem and exits 1 if any check fails.
"""

import builtins
import keyword
import pathlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import janim  # noqa: E402  (after the path insert, so the checkout is what gets checked)

# ── what counts as a legitimate name ────────────────────────────────────────

EXPORTED = set(janim.__all__)

# The classes whose attributes a skill may call with a dot: `m.next_to(`,
# `self.play(`, `tex.get_parts_by_tex(`, `self.frame.reorient(`…
_CORE_CLASSES = (
    "Mobject", "VMobject", "VGroup", "Group", "Scene", "CameraFrame", "Camera", "Animation",
    "Axes", "NumberLine", "NumberPlane", "ThreeDAxes", "Text", "Tex", "Code", "DecimalNumber",
    "Variable", "ValueTracker", "TracedPath", "Layer", "Mask", "Composition", "DotCloud",
    "Surface", "Matrix", "Table", "SVGMobject", "ImageMobject", "Clock", "SampleSpace",
    "LabeledPolygram", "ConvexHull3D", "TexTemplate", "Polygon", "Line", "Arrow", "Dot",
    "Square", "Circle", "Rectangle", "Star", "Brace", "SurroundingRectangle", "Cutout",
    "ODEProblem", "Tsit5",
)
METHODS = set()
for _name in _CORE_CLASSES:
    METHODS.update(dir(getattr(janim, _name)))
# Standard-library receivers the examples call methods on.
for _obj in (pathlib.Path, str, list, dict, bytes, set, tuple):
    METHODS.update(dir(_obj))
METHODS.update({"tobytes", "hexdigest", "sha256", "append", "register", "default_rng", "shape", "dtype"})

# Modules the skills name by qualified path, whose public and documented
# private names may appear bare.
_MODULES = (
    "janim.math",
    "janim.ode",
    "janim.ode.dual",
    "janim.cli",
    "janim.text.glyphs",
    "janim.backend.wgpu.uniforms",
    "janim.backend.wgpu.compositor",
    "janim.backend.wgpu.context",
    "janim.core.effects_types",
)
MODULE_NAMES = set()
from importlib import import_module  # noqa: E402

for _module in _MODULES:
    MODULE_NAMES.update(dir(import_module(_module)))
# Internals the skills quote on purpose (the effect contract names the
# compositor's slot verbs; the noise lesson names the CPU twin).
DECLARED_INTERNAL = {"_quad", "_scratch", "_noise_seed", "_noise_hash", "_julia_math", "ppu", "_FILL_THIN_PX"}

BUILTIN_NAMES = set(dir(builtins)) | set(keyword.kwlist) | {"self", "cls", "np", "math", "functools", "partial"}

# Names the skills mention ON PURPOSE that are not Janim's. Every entry is an
# excuse, so the list is explicit and auditable rather than a fuzzy filter.
FOREIGN = {
    # the user's own scene classes and helpers, quoted in templates and prose
    "Demo", "Hello", "Glow", "Lesson", "Intro", "Main", "Class", "Foo", "Unroll", "Gear",
    "Thermometer", "Chevron", "MyEffect", "Posterize", "Sparkle", "Shadow",
    # Manim's API, quoted to contrast with Janim's (CE and GL)
    "MarkupText", "ZoomedScene", "Union", "Intersection", "Difference", "Exclusion", "Graph",
    "DiGraph", "BarChart", "ArrowTriangleTip", "StealthTip", "Add", "ChangeSpeed",
    "ClockwiseTransform", "PointCloudDot", "Point", "ParametricFunction", "ArrowVectorField",
    "ManimGL", "Manim", "Pango", "MathTeXEngine", "Typst", "FreeType", "HarfBuzz", "Julia",
    "set_camera_orientation", "move_camera", "begin_ambient_camera_rotation",
    "add_fixed_in_frame_mobjects", "embed", "checkpoint_paste", "to_hex", "tempconfig", "manim",
    # WGSL: the fragment entry points and the spliced helpers of the effect contract
    "QuadOut", "QuadParams", "sample_a", "sample_b", "unpremult", "luma", "janim_noise_px",
    "janim_noise_steps", "janim_frame_step", "seed_plus", "bitcast", "u32", "floor", "vec4",
    "fs_posterize", "fs_sparkle", "fn", "let", "var", "location",
    # third parties and tools named in shell lines or prose
    "Wellons", "Loop", "Blinn", "Mesa", "Metal", "Fedora", "Windows", "Linux", "Read", "Claude",
    "Code", "Tool", "Tsit5", "OrdinaryDiffEq", "SciML", "ForwardDiff",
    # placeholders in signatures and tables, and words inside quoted error messages
    "Effects", "Dials", "What", "Where", "Skill", "For", "SUBSTR", "OUT_DIR", "BEFORE_DIR", "AFTER_DIR",
    "WxH", "Around", "VMobjects", "LaTeX",
    # `random()` is named to say it is FORBIDDEN in a shader; a lesson's class is quoted as a measured case
    "random", "Plots3D",
}
FOREIGN_PATHS = {
    # generic names in templates and shell examples, not files of this repo
    "scene.py", "file.py", "x.py", "scenes.py", "msg.txt", "sweep.log", "out.mp4", "janim.cfg",
    "manim.cfg", "effects.py", "compositor.py", "math.py", "02_from_manimgl.py",
    "02_noise_and_determinism.py", "test_math.py", "test_surface.py", "test_code.py",
    "history/YYYY-MM/",
    # files the harness WRITES, named by the skill that runs it
    "driver.txt", "summary.tsv",
}

# ── pulling the claims out of the prose ─────────────────────────────────────

FENCE = re.compile(r"```([A-Za-z]*)\n(.*?)```", re.S)
INLINE = re.compile(r"`([^`\n]+)`")


def spans(text):
    """(kind, span) for every fenced block and inline code span.

    Fenced python blocks and inline spans are scanned for identifiers; bash
    blocks only for paths, verbs and variables; text and wgsl blocks for
    nothing (they are quoted output and shader code, not Python claims).
    """
    out = []
    for match in FENCE.finditer(text):
        language, body = match.group(1).lower(), match.group(2)
        kind = "python" if language in ("python", "") else language
        out.append((kind, body))
    stripped = FENCE.sub("", text)
    for match in INLINE.finditer(stripped):
        out.append(("inline", match.group(1)))
    return out


def python_claims(span):
    """Identifiers a span claims exist: bare calls, dot-calls and CamelCase types."""
    span = re.sub(r'"""(?:.|\n)*?"""', '""', span)              # triple-quoted strings (WGSL inside Python)
    span = re.sub(r"#[^\n]*", "", span)                        # comments
    span = re.sub(r"(?:r|f|rf|fr)?\"(?:[^\"\\]|\\.)*\"", '""', span)   # string literals
    span = re.sub(r"(?:r|f|rf|fr)?'(?:[^'\\]|\\.)*'", "''", span)
    span = re.sub(r"\b(def|class)\s+[A-Za-z_]\w*\s*\(", r"\1 (", span)   # a definition is not a claim
    bare = re.findall(r"(?<![.\w])([A-Za-z_]\w*)\s*\(", span)
    dotted = re.findall(r"\.([A-Za-z_]\w*)\s*\(", span)
    camel = re.findall(r"\b([A-Z][A-Za-z0-9_]*[a-z][A-Za-z0-9_]*)\b", span)
    # single letters are placeholders (`class X(Scene)`, `frame K`, `n/N`), never names
    return [n for n in bare if len(n) > 1], dotted, [n for n in camel if len(n) > 1]


PATH = re.compile(
    r"`(?:\.\./|\./)?((?:janim|examples|tests|docs|bin|scripts|skills|history)/(?:[A-Za-z0-9_./*-]|<[^>`]*>)*"
    r"|\.?[A-Za-z0-9_*-][A-Za-z0-9_.*-]*\.(?:py|md|txt|toml|wgsl|sh|cmd))\b`?"
)
VERB = re.compile(r"bin[/\\]janim\s+(\S+)")
ENV = re.compile(r"\b(JANIM_[A-Z0-9_]+)")


def glob_regex(pattern):
    return re.compile("^" + re.escape(pattern).replace(r"\*", ".*") + "$")


SKIPPED_FOLDERS = {".venv", ".git", "__pycache__", "output"}


def path_exists(claim):
    """Resolve a claimed path.

    `<placeholder>` and `*` are globs (`examples/tutorial/<course>/<nn>_<name>.py`,
    `tests/test_*.py`); a bare basename is searched for anywhere in the tree, and a
    leading dot (`.es.md`) is a suffix pattern.
    """
    claim = re.sub(r"<[^>]*>", "*", claim.rstrip("`"))
    if "/" in claim:
        if (ROOT / claim).exists():
            return True
        return "*" in claim and any(ROOT.glob(claim))
    if claim.startswith("."):
        claim = "*" + claim
    for path in ROOT.rglob(claim):
        if not SKIPPED_FOLDERS.intersection(path.relative_to(ROOT).parts):
            return True
    return False


def cli_verbs():
    from janim import cli

    source = (ROOT / "janim" / "cli.py").read_text(encoding="utf-8")
    verbs = set(cli.VERB_FLAGS)
    for verb in ("codecs", "check", "finish", "ping", "daemon", "stop"):
        if f'"{verb}"' in source:
            verbs.add(verb)
    return verbs


def env_names():
    names = set()
    for path in (ROOT / "janim").rglob("*.py"):
        names.update(ENV.findall(path.read_text(encoding="utf-8")))
    for path in (ROOT / "scripts").glob("*"):
        if path.is_file():
            names.update(ENV.findall(path.read_text(encoding="utf-8", errors="ignore")))
    return names


# ── the run ─────────────────────────────────────────────────────────────────


def main(argv):
    folder = Path(argv[1]).resolve() if len(argv) > 1 else HERE
    files = sorted(p for p in folder.rglob("*.md"))
    if not files:
        print(f"no markdown found under {folder}")
        return 1

    verbs, variables = cli_verbs(), env_names()
    bad_id, bad_path, bad_verb, bad_env = [], [], [], []

    for path in files:
        rel = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        text = path.read_text(encoding="utf-8")

        for kind, span in spans(text):
            if kind in ("python", "inline"):
                bare, dotted, camel = python_claims(span)
                for name in bare:
                    if name in EXPORTED or name in METHODS or name in MODULE_NAMES or name in BUILTIN_NAMES:
                        continue
                    if name in DECLARED_INTERNAL or name in FOREIGN:
                        continue
                    bad_id.append(f"{rel}: `{name}(` is not a janim name and not declared foreign")
                for name in dotted:
                    if name in METHODS or name in EXPORTED or name in MODULE_NAMES or name in DECLARED_INTERNAL or name in FOREIGN:
                        continue
                    bad_id.append(f"{rel}: `.{name}(` is not a method of a core class and not declared foreign")
                for name in camel:
                    if name in EXPORTED or name in MODULE_NAMES or name in BUILTIN_NAMES or name in FOREIGN:
                        continue
                    bad_id.append(f"{rel}: `{name}` is not a janim type and not declared foreign")
            if kind in ("python", "inline", "bash"):
                for verb in VERB.findall(re.sub(r"#[^\n]*", "", span)):
                    if "." in verb or verb.startswith("-") or verb.startswith("<"):
                        continue                      # a file or a flag, not a verb claim
                    if verb not in verbs:
                        bad_verb.append(f"{rel}: `bin/janim {verb}` is not a verb the CLI has")
                for variable in ENV.findall(span):
                    if variable not in variables:
                        bad_env.append(f"{rel}: `{variable}` is not read anywhere under janim/")

        for claim in PATH.findall(text):
            # render output is written by the lessons and ignored by git: never a claim about the tree
            if claim in FOREIGN_PATHS or "/output/" in claim or path_exists(claim):
                continue
            bad_path.append(f"{rel}: points at «{claim}», which does not exist")

    ok = True
    for title, bad in (("identifiers", bad_id), ("paths", bad_path), ("CLI verbs", bad_verb), ("environment variables", bad_env)):
        if not bad:
            print(f"  ✓ {title}")
            continue
        ok = False
        print(f"  ✗ {title} — {len(set(bad))} problem(s)")
        for line in sorted(set(bad)):
            print("      " + line)
    print(f"\nskills ✓  {len(files)} files, every claim resolves" if ok else "\nskills ✗  fix the above")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
