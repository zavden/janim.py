// inserts/srgb.wgsl — the exact IEC 61966-2-1 transfer pair: the SAME six
// constants as the CPU colour code, the same partition at the toe, `pow`
// guarded with `max` in both directions (f16 blur ringing can dip a hair
// under zero). GLSL's `mix(high, low, lessThanEqual(c, k))` is
// `select(high, low, c <= k)` here — the same order: `low` where the
// component sits at or below the toe.
//
// What this pair does NOT promise is the bits of `pow`: neither GLSL nor
// WGSL requires it correctly rounded, and each driver lowers it as it
// likes, so the encoded byte of a given input can differ between drivers.

fn srgb_to_linear(c: vec3<f32>) -> vec3<f32> {
    let low = c / 12.92;
    let high = pow(max((c + 0.055) / 1.055, vec3<f32>(0.0)), vec3<f32>(2.4));
    return select(high, low, c <= vec3<f32>(0.04045));
}

fn linear_to_srgb(c: vec3<f32>) -> vec3<f32> {
    let low = 12.92 * c;
    let high = 1.055 * pow(max(c, vec3<f32>(0.0)), vec3<f32>(1.0 / 2.4)) - 0.055;
    return select(high, low, c <= vec3<f32>(0.0031308));
}
