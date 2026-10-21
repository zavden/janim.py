"""Lazy public compositor effects and rendering doors."""

EFFECT_EXPORTS = {
    name: "janim.core.effects_types"
    for name in (
        "Blur", "BoxBlur", "DirectionalBlur", "RadialBlur", "Dof", "Bloom",
        "Glitch", "CRT", "VHS", "ColorAdjust", "Pixelate", "Vignette", "Grain",
        "ChromaticAberration", "Sharpen", "Wave", "EdgeDetect",
    )
}
EFFECT_EXPORTS.update(
    {
        name: "janim.backend"
        for name in ("render_composition", "read_layer_rgba", "effect_shader", "apply_effect")
    },
)
