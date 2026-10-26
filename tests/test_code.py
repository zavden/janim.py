"""Code: ManimCE 0.22's tests for its Code, ported, plus Janim's own.

Run it directly (`python tests/test_code.py`) or with pytest. pygments is
one of Janim's pinned dependencies, so a missing pygments is a failure here,
not a skip.

The first block mirrors `tests/module/mobject/text/test_code_mobject.py` of
CE 0.22 test by test (its parametrizations become loops). The second block
pins what Janim does on its own: CE's geometry measured on CE itself, the
font fallback, the configuration errors and the lazy import.
"""
import sys
from pathlib import Path

import numpy as np

from janim import Code
from janim.core.mobject import VGroup

REPO = Path(__file__).resolve().parents[1]


class _Skipped(Exception):
    pass


def _require_font(family):
    from janim.text.glyphs import FontNotFound, find_face

    try:
        find_face(family)
    except FontNotFound:
        if "pytest" in sys.modules:
            import pytest

            pytest.skip(f"{family} is not installed")
        raise _Skipped(f"{family} is not installed")


# ---------------------------------------------------------------- CE's tests


def test_code_initialization_from_string():
    code_string = """from manim import Scene, Square

class FadeInSquare(Scene):
    def construct(self):
        s = Square()
        self.play(FadeIn(s))
        self.play(s.animate.scale(2))
        self.wait()"""
    rendered_code = Code(
        code_string=code_string,
        language="python",
    )
    num_lines = len(code_string.split("\n"))
    assert len(rendered_code.code_lines) == num_lines
    assert len(rendered_code.line_numbers) == num_lines


def test_code_initialization_without_line_numbers():
    for code_string, num_lines in (("pass", 1), ("   ", 1), (" \n ", 2)):
        rendered_code = Code(
            code_string=code_string,
            language="python",
            add_line_numbers=False,
        )
        assert len(rendered_code.code_lines) == num_lines, code_string
        assert not hasattr(rendered_code, "line_numbers")


def test_code_initialization_from_file():
    rendered_code = Code(
        code_file=REPO / "examples" / "gallery" / "01_square_to_circle.py",
        language="python",
        background="window",
        background_config={"fill_color": "#101010"},
        paragraph_config={"font_size": 14},
    )
    assert len(rendered_code.code_lines) == len(rendered_code.line_numbers)
    assert rendered_code.background.get_fill_color() == "#101010"


def test_code_uses_formatter_style_colors():
    for formatter_style, background_color, text_color in (
        ("xcode", "#FFFFFF", "#000000"),
        ("vim", "#000000", "#CCCCCC"),
    ):
        rendered_code = Code(
            code_string="plain text",
            language="text",
            formatter_style=formatter_style,
            add_line_numbers=False,
        )
        assert rendered_code.background.get_fill_color() == background_color
        assert rendered_code.code_lines[0][0].get_color() == text_color


def test_code_ignores_paragraph_color():
    rendered_code = Code(
        code_string="plain text",
        language="text",
        formatter_style="vim",
        paragraph_config={"color": "#ff0000"},
    )
    assert rendered_code.code_lines[0][0].get_color() == "#CCCCCC"
    assert rendered_code.line_numbers[0][0].get_color() == "#CCCCCC"


def test_code_ignores_default_paragraph_color():
    Code.default_paragraph_config["color"] = "#ff0000"
    try:
        rendered_code = Code(
            code_string="plain text",
            language="text",
            formatter_style="vim",
        )
    finally:
        del Code.default_paragraph_config["color"]
    assert rendered_code.code_lines[0][0].get_color() == "#CCCCCC"
    assert rendered_code.line_numbers[0][0].get_color() == "#CCCCCC"


def test_code_accepts_custom_pygments_style():

    class CustomStyle(Code.get_pygments_style("xcode")):
        background_color = "#123456"
        line_number_color = "#abcdef"

    rendered_code = Code(
        code_string="plain text",
        language="text",
        formatter_style=CustomStyle,
    )
    assert rendered_code.background.get_fill_color() == "#123456"
    assert rendered_code.code_lines[0][0].get_color() == "#000000"
    assert rendered_code.line_numbers[0][0].get_color() == "#ABCDEF"


def test_code_line_numbers_use_formatter_style_color():
    for formatter_style, line_number_color in (
        ("solarized-light", "#93A1A1"),
        ("vim", "#CCCCCC"),
        ("xcode", "#000000"),
    ):
        rendered_code = Code(
            code_string="plain text",
            language="text",
            formatter_style=formatter_style,
        )
        assert rendered_code.line_numbers[0][0].get_color() == line_number_color, formatter_style


def test_line_heights_initial_whitespace():
    rendered_code = Code(
        code_string="""print('Hello, World!')
for _ in range(42):
    print('Hello, World!')
""",
        language="python",
    )
    np.testing.assert_almost_equal(
        rendered_code.code_lines[0].get_height(),
        rendered_code.code_lines[2].get_height(),
    )


def test_code_baseline_alignment():
    for line_numbers_from in (1, 10, -2):
        baseline_offsets = []
        for code_string in ("pass", "pass b"):
            rendered_code = Code(
                code_string=code_string,
                language="python",
                line_numbers_from=line_numbers_from,
            )
            baseline_offsets.append(
                rendered_code.code_lines[0].get_bottom()[1]
                - rendered_code.line_numbers[0].get_bottom()[1]
            )
        np.testing.assert_allclose(baseline_offsets[0], baseline_offsets[1], atol=1e-6)


def test_code_height_is_independent_of_boundary_glyphs():
    code_strings = (
        "AAA\nppp",
        "ppp\nAAA",
        "AAA\nAAA",
        "ppp\nppp",
        "---\n---",
    )
    for background in ("rectangle", "window"):
        for add_line_numbers in (True, False):
            background_heights = [
                Code(
                    code_string=code_string,
                    language="python",
                    background=background,
                    add_line_numbers=add_line_numbers,
                ).background.get_height()
                for code_string in code_strings
            ]
            np.testing.assert_allclose(background_heights, background_heights[0], atol=1e-6)


def test_code_line_mobject_is_independent_of_ordinality():
    for disable_ligatures in (True, False):
        for add_line_numbers in (True, False):
            code_mobject = Code(
                code_string="\n".join(("Hello World!",) * 5),
                add_line_numbers=add_line_numbers,
                paragraph_config={"disable_ligatures": disable_ligatures},
            )
            lines = code_mobject.code_lines
            reference_line = lines[len(lines) // 2]
            for boundary_line in (lines[0], lines[-1]):
                assert len(boundary_line) == len(reference_line)
                np.testing.assert_allclose(
                    boundary_line.get_width(),
                    reference_line.get_width(),
                    atol=1e-6,
                )


def test_code_syntax_highlighting_colors():
    code_string = "pass\n# comment"
    rendered_code = Code(
        code_string=code_string,
        language="python",
        formatter_style="vim",
    )
    assert {char.get_color() for char in rendered_code.code_lines[0]} == {"#CDCD00"}
    assert {char.get_color() for char in rendered_code.code_lines[1]} == {"#000080"}
    assert [len(line) for line in rendered_code.code_lines] == [
        sum(not char.isspace() for char in line) for line in code_string.splitlines()
    ]
    assert len(rendered_code.code_lines) == len(rendered_code.code_lines.chars)


def test_code_initialization_style_correct_color():
    for style in Code.get_styles_list():
        Code(
            code_string="""# This is a comment.
var = 3
print(var)
""",
            formatter_style=style,
        )


# ------------------------------------------------------------- Janim's own


def test_geometry_matches_ce_measured():
    """CE 0.22 measured on itself with Liberation Mono (2026-10-26): Janim's Bézier boxes agree to 2e-3."""
    _require_font("Liberation Mono")
    code = "def f(x):\n    return x + 1\n\nprint(f(2))"
    rectangle = Code(
        code_string=code,
        language="python",
        paragraph_config={"font": "Liberation Mono"},
    )
    window = Code(
        code_string=code,
        language="python",
        background="window",
        paragraph_config={"font": "Liberation Mono"},
    )
    np.testing.assert_allclose(
        (rectangle.get_width(), rectangle.get_height()),
        (4.179638650000001, 2.0359375),
        atol=2e-3,
    )
    np.testing.assert_allclose(
        (window.get_width(), window.get_height()),
        (4.279638650000001, 2.3359375),
        atol=2e-3,
    )
    np.testing.assert_allclose(rectangle.code_lines.get_center(), (0, 0, 0), atol=2e-3)
    np.testing.assert_allclose(
        [float(number.get_bottom()[1]) for number in rectangle.line_numbers][:3],
        (0.4765625, 0.1015625, -0.2765625),
        atol=2e-3,
    )
    np.testing.assert_allclose(
        float(rectangle.line_numbers.get_right()[0]),
        -1.831225575,
        atol=2e-3,
    )


def test_pitch_follows_ce_scale():
    """CE's Paragraph pitch is (1 + line_spacing) * 0.75 em and its em is font_size / 72 units."""
    for font_size, line_spacing, pitch in ((24, 0.5, 0.375), (24, 1.0, 0.5), (24, 0.0, 0.25), (14, 0.5, 0.21875)):
        code = Code(
            code_string="H\nH\nH",
            language="text",
            paragraph_config={"font_size": font_size, "line_spacing": line_spacing},
        )
        lines = code.code_lines
        assert abs((lines[0].get_bottom()[1] - lines[1].get_bottom()[1]) - pitch) < 1e-6
        assert abs(code.line_pitch - pitch) < 1e-12
    explicit = Code(code_string="H\nH", language="text", paragraph_config={"size": 0.5})
    assert abs(explicit.line_pitch - 1.5 * 0.75 * 0.5) < 1e-12


def test_box_is_tight_on_the_visible_code():
    """CE glues " pA1" to the line and centres with it; Janim centres the code that is drawn."""
    code = Code(code_string="pass", language="python", add_line_numbers=False)
    buff = Code.default_background_config["buff"]
    assert abs(code.background.get_width() - (code.code_lines.get_width() + 2 * buff)) < 1e-5
    assert abs(float(code.code_lines.get_center()[0])) < 1e-6


def test_structure_and_order():
    code = Code(code_string="a = 1\n\nb = 2", language="python")
    assert code.submobjects == [code.background, code.line_numbers, code.code_lines]
    assert len(code.code_lines[1]) == 0 and isinstance(code.code_lines[1], VGroup)
    assert len(code.background.submobjects) == 0
    window = Code(code_string="a = 1", language="python", background="window", add_line_numbers=False)
    assert window.submobjects == [window.background, window.code_lines]
    buttons = window.background.submobjects[0]
    assert [button.get_fill_color() for button in buttons] == ["#FF5F56", "#FFBD2E", "#27C93F"]
    assert buttons.get_top()[1] < window.background.get_top()[1]


def test_all_whitespace_code():
    code = Code(code_string="  \n\t\n", language="python")
    assert len(code.code_lines) == 2
    assert all(len(line) == 0 for line in code.code_lines)
    assert code.background.get_height() > 0 and code.background.get_width() > 0


def test_language_is_guessed():
    assert Code(code_file=REPO / "examples" / "gallery" / "01_square_to_circle.py").language == "Python"
    assert Code(code_string="#include <stdio.h>\nint main(void) { return 0; }", language="c").language == "C"


def test_configuration_errors():
    for call, error in (
        (lambda: Code(), ValueError),
        (lambda: Code(code_string="x", background="frame"), ValueError),
        (lambda: Code(code_string="x", paragraph_config={"fonts": "X"}), TypeError),
        (lambda: Code(code_string="x", background_config={"radius": 1}), TypeError),
        (lambda: Code(code_string="x", formatter_style=42), TypeError),
        (lambda: Code(code_string="x", paragraph_config={"font": "No Such Mono Font"}), ValueError),
    ):
        try:
            call()
        except error:
            continue
        raise AssertionError(f"expected {error.__name__}")


def test_missing_pygments_is_a_clear_error():
    saved = {name: module for name, module in sys.modules.items() if name == "pygments" or name.startswith("pygments.")}
    for name in saved:
        del sys.modules[name]
    sys.modules["pygments"] = None
    try:
        Code(code_string="x = 1", language="python")
    except ImportError as error:
        assert "scripts/bootstrap.sh" in str(error) and "pygments==2.21.0" in str(error)
    else:
        raise AssertionError("Code built without pygments")
    finally:
        del sys.modules["pygments"]
        sys.modules.update(saved)


def main():
    failures = 0
    for name, test in sorted(globals().items()):
        if name.startswith("test_") and callable(test):
            try:
                test()
                print(f"OK   {name}")
            except _Skipped as reason:
                print(f"SKIP {name}: {reason}")
            except AssertionError as error:
                failures += 1
                print(f"BAD  {name}: {error}")
    print("all tests passed" if not failures else f"{failures} test(s) failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
