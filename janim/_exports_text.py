"""Lazy public names for text, formulas and their derived objects."""

TEXT_EXPORTS = {}
for _module, _names in {
    "text.text": "Text TextMobject",
    "text.tex": "Tex MathTex TexText LTex LMathTex TexTemplate tex_source TEX_BASE_PREAMBLE",
    "text.numbers": "DecimalNumber Integer IntegerMobject",
    "core.decor": "Paragraph BulletedList",
    "core.annotations": "BraceLabel BraceText",
    "core.compositor_types": "Composition crop",
    "animation.matching": "TransformMatchingTex TransformMatchingStrings TransformMatchingShapes",
}.items():
    TEXT_EXPORTS.update({name: "janim." + _module for name in _names.split()})
