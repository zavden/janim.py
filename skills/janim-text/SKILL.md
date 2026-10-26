---
name: janim-text
description: Text and formulas in Janim.py — `Text` through FreeType (`size=`/`font_size=`, `t2c`, `t2w`, one child per glyph), `Tex`/`MathTex`/`TexText` through real LaTeX + dvisvgm (`isolate`, keys, `TransformMatchingTex`), numbers that change (`DecimalNumber`, `Integer`, `Variable`), `Code` listings with pygments, `Paragraph`, `BulletedList`, braces and labels. Use when a Janim.py scene animates a formula or a derivation step by step, shows source code, counts a number or puts any text on screen, and when a `KeyError` or `FontNotFound` comes out of one of them.
---

# Text and formulas (Janim.py)

Two engines, both measured: `Text` is FreeType straight to Béziers (no LaTeX,
no Pango); `Tex` is real LaTeX + `dvisvgm` → SVG. There is no other
typesetting route — no Typst, no MathTeXEngine, no `MarkupText`.

## 1 · Text

```python
t = Text(
    "stable orbit",
    font="DejaVu Sans",
    size=0.6,
    color=WHITE,
    t2c={"orbit": YELLOW, range(0, 6): BLUE},   # a substring, or a 0-based half-open character range
    t2w={"stable": "bold"},
)
```

- `size=` is the em in scene units; `font_size=` is Manim's (48 by default).
  Give one. `Text("hi")` and `Text("hi", font_size=48)` are the same height
  (0.345 units, ManimGL's), not CE's Pango height (0.506).
- Every glyph is a CHILD keyed by its character: `t["a"]` is a VGroup of the
  a's, `t[3]` the fourth glyph. **Spaces make no child**, so glyph index ≠
  character index: colour by `t2c` at construction, which knows which glyph
  came from which character, never by index afterwards.
- A weight the font lacks is an ERROR, not a fallback:
  `Text("x", t2w={"x": "ultrablack"})` raises `FontNotFound`. The fonts are
  the system's (`fc-list : family`); the examples use DejaVu Sans.
- No complex shaping: Latin, Greek and Cyrillic are the honest frontier.
- Layouts: `Paragraph(*lines, alignment=LEFT, line_spacing=0.3)`,
  `BulletedList(*items)`, `Title`, `Label(text)` (a boxed label),
  `Brace(m, DOWN)` (a native path, no LaTeX), `BraceLabel(m, "text", DOWN)`.

## 2 · Tex: one route, real LaTeX

```python
f = Tex(r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}", size=1.0, color=WHITE)
TexText(r"Let $x^2$ be the area")                    # text mode
MathTex(r"e^{i\pi}")                                  # the same class as Tex
LTex(r"\ce{H2O}", template=TexTemplate().add_to_preamble(r"\usepackage{mhchem}"))
```

- `latex` and `dvisvgm` must be on the PATH, or:
  `ValueError: Tex requires latex and dvisvgm on PATH`. A LaTeX error comes
  back as `ValueError: LaTeX could not compile this:` with the log's line.
- Always `r"…"`: a plain string eats the backslashes.
- The SVGs are cached in `$JANIM_TEX_CACHE` (default `~/.cache/janim/tex`,
  keyed by the latex version and the document): a formula costs about a
  second once and nothing after.
- A `Tex` is a parent plus ONE CHILD PER GLYPH, on purpose: with every glyph
  in one path, a morph's intermediate blob flies over its neighbours and
  cancels their fill. Morph the parent and the children pair glyph to glyph.

## 3 · Parts: a glyph answers only to the keys you gave

Through LaTeX a glyph does not know which source characters made it, so the
keys come from construction:

```python
f = Tex(r"x^2 + y^2 = r^2", isolate=["x^2", "y^2"])
f["x^2"]                       # the union of what that key names
f.get_parts_by_tex("x^2")      # one group per occurrence
f.get_part_by_tex("x^2", 0)    # the first
f["r^2"]                       # KeyError: no child carries 'r^2'; available keys: x^2, y^2; use isolate or t2c …
Tex("f(", "x", ")")            # each argument is a key: 'f(', 'x', ')'
f[2], f[1:4]                   # by glyph position, 0-based
```

`t2c={"x": YELLOW}` both colours and registers the key. `Tex` and `Text`
share this addressing (`text["a"]`), and `find_by_key`/`set_key` label
mobjects of your own the same way.

## 4 · The morphs

```python
a = Tex(r"a^2 + b^2 = c^2", size=1.2, isolate=["a^2", "b^2", "c^2"])
b = Tex(r"c = \sqrt{a^2 + b^2}", size=1.2, isolate=["a^2", "b^2", "c"])
self.play(Write(a))
self.play(TransformMatchingTex(a, b, key_map={"c^2": "c"}), run_time=1.4)   # the scene now holds b
```

- `Transform(a, b)` pairs glyph with glyph in reading order; for a derivation,
  morph ONE `Tex` through the steps rather than building a new mobject per
  line.
- `TransformMatchingTex(a, b, key_map=…)` morphs glyphs that share a key
  (longest first) and fades the rest; **when it ends the scene holds `b`** —
  carry on with `b`, not `a`. `TransformMatchingStrings` is its GL name;
  `TransformMatchingShapes` pairs by shape, without keys.
- `Write`/`Unwrite`, `AddTextLetterByLetter`, `AddTextWordByWord` (the words
  of a `Text` are its glyphs between spaces), `RemoveTextLetterByLetter`,
  `TypeWithCursor(text, cursor)` / `UntypeWithCursor(text, cursor)` (the
  cursor follows each glyph's height — `TODO.md`). Removers hand the text
  back intact.
- **Verify the MIDDLE of every morph** (`janim-verify`): bad morphs are
  invisible at both ends.

## 5 · Numbers

```python
d = DecimalNumber(3.14159, num_decimal_places=3, size=0.6)       # d.string == "3.142"
d.set_value(2.0)                                                # the LEFT edge stays (edge_to_fix=LEFT; ORIGIN re-centres)
n = Integer(7)
v = Variable(0.5, "x", num_decimal_places=3)                    # "x = 0.500", following v.tracker
self.play(ChangeDecimalToValue(d, 9.0), run_time=2)
self.play(CountInFrom(n, 0))
readout = DecimalNumber(0).add_updater(lambda m: m.set_value(t.get_value()))
```

## 6 · Code listings

```python
code = Code(
    code_string="def f(x):\n    return x * 2\n",
    language="python",
    formatter_style="vim",
    add_line_numbers=True,
    background="window",
)
code.code_lines[0][3]      # the 4th VISIBLE glyph of line 1 (spaces make no glyph)
code.line_numbers
code.background
```

ManimCE's `Code`, with CE's names and geometry: `code_file=` reads a file;
`tab_width`, `line_numbers_from`, `background="rectangle" | "window"`,
`background_config`, `paragraph_config={"font": …, "font_size": 24,
"line_spacing": 0.5}`. pygments is a pinned dependency and colours token by
token; every colour comes from the style (a `color` in `paragraph_config` is
ignored); `Code.get_styles_list()` lists the styles. The font is the first
installed of DejaVu Sans Mono, Menlo, Consolas, Liberation Mono, Noto Sans
Mono and Courier New. The submobjects are `[background, line_numbers,
code_lines]`. Lesson: `examples/tutorial/c1_03_groups_and_text/08_code.py`.

## 7 · Blackboard composition that works

- Title: `Text(…, size=0.5, color=GREY_A).to_edge(UP, buff=0.4)`.
- Emphasis: `SurroundingRectangle(m, buff=0.1)` + `ShowCreation`, or
  `Indicate(m)`, `Circumscribe(m)`.
- Footnote: a small `Text`, `next_to(formula, DOWN, buff=0.6)`, one
  `FadeIn`/`FadeOut` per step.
- Too wide: `if f.get_width() > FRAME_WIDTH - 1: f.set_width(FRAME_WIDTH - 1)`.
- Grids: `Matrix([[1, 2], [3, 4]])` (`cell=lambda s: Tex(s, size=0.7)` to
  typeset the entries), `Table`, `get_entries`, `get_rows`, `get_cell(i, j)`
  (one-based).

Lessons: `examples/tutorial/c1_03_groups_and_text/` — 03 text, 04 latex, 06
matching, 07 symbol by symbol, 08 code.
