"""GPU regression for a blurred object crossing the camera edge."""

from math import pi

import numpy as np

from janim import Bloom, Blur, Camera, DirectionalBlur, Layer, Rectangle, apply_effect, effect_shader
from janim.backend import setup_compositor, setup_render_vm


def test_blur_at_camera_edges():
    cam = Camera(width=256, height=144)
    with setup_render_vm(cam.width, cam.height) as rv, setup_compositor(rv) as cg:
        for axis, extent in enumerate((cam.frame_width, cam.frame_height)):
            for side in (-1, 1):
                position = [0.0, 0.0, 0.0]
                position[axis] = side * extent / 2
                tile = Rectangle(width=2, height=2).set_fill("#FFFFFF", 1).set_stroke(width=0)
                tile.move_to(position)
                source = cg.read_layer_rgba(Layer(tile), cam)[:, :, 3]
                for effect in (DirectionalBlur(.25, axis * pi / 2), Blur(.25), Bloom(sigma=.12)):
                    alpha = cg.read_layer_rgba(Layer(tile, effects=[effect]), cam)[:, :, 3]
                    strip = alpha if axis == 0 else alpha.T
                    opposite_half = np.hsplit(strip, 2)[1 if side < 0 else 0]
                    assert not opposite_half.any(), (effect, axis, side)
                    assert strip[len(strip) // 2, 0 if side < 0 else -1] >= 254
                    assert np.any((source == 0) & (alpha > 0)), "expected a local blur halo"


def test_registered_shader_repeats():
    class ShiftByOneTile:
        def __init__(self, linear):
            self.linear = linear

    effect_shader("test_repeat_uv", """
        @fragment fn fs_test_repeat_uv(in: QuadOut) -> @location(0) vec4<f32> {
            return sample_a(in.uv + vec2<f32>(1.0, -1.0));
        }
    """)

    @apply_effect.register(ShiftByOneTile)
    def shift(effect, cg, src):
        return cg._quad("test_repeat_uv", cg._scratch(src), src, linear=effect.linear)

    cam = Camera(width=256, height=144)
    tile = Rectangle(width=2, height=2).set_fill("#FFFFFF", 1).set_stroke(width=0)
    with setup_render_vm(cam.width, cam.height) as rv, setup_compositor(rv) as cg:
        source = cg.read_layer_rgba(Layer(tile), cam)[:, :, 3]
        assert source.max() == 255 and source.min() == 0
        for linear in (False, True):
            layer = Layer(tile, effects=[ShiftByOneTile(linear)])
            np.testing.assert_allclose(cg.read_layer_rgba(layer, cam)[:, :, 3], source, atol=1)


if __name__ == "__main__":
    test_blur_at_camera_edges()
    test_registered_shader_repeats()
