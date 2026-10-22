"""The smoke-test triangle: literal source and data."""

import hashlib
from pathlib import Path

import numpy as np

from .context import _binding
from .targets import render_pass


TRIANGLE_WGSL = (Path(__file__).with_name("shaders") / "triangle.wgsl").read_text(encoding="utf-8")
TRIANGLE_F0 = np.array(
    [(-0.6, -0.5, 1.0, 0.0, 0.0), (0.6, -0.5, 0.0, 1.0, 0.0), (0.0, 0.6, 0.0, 0.0, 1.0)],
    dtype=np.float32,
)


def compile_wgsl(gpu, source, *, label="wgsl"):
    gpu.check()
    digest = hashlib.sha256(source.encode()).hexdigest()
    module = gpu.device.create_shader_module(label=f"{label} sha256={digest}", code=source)
    module.source_sha256 = digest
    return module


class TriangleScene:
    def __init__(self, gpu):
        gpu.check()
        self.gpu = gpu
        self.closed = False
        self.vertices = TRIANGLE_F0.copy()
        self.shader = compile_wgsl(gpu, TRIANGLE_WGSL, label="triangle")
        binding = _binding()
        self.vbo = gpu.device.create_buffer(
            label="triangle vertices",
            size=self.vertices.nbytes,
            usage=binding.BufferUsage.VERTEX | binding.BufferUsage.COPY_DST,
        )
        gpu.queue.write_buffer(self.vbo, 0, self.vertices)
        self.pipeline = gpu.device.create_render_pipeline(
            label="triangle",
            layout="auto",
            vertex={
                "module": self.shader,
                "entry_point": "vs_main",
                "buffers": [{
                    "array_stride": 20,
                    "step_mode": "vertex",
                    "attributes": [
                        {"format": "float32x2", "offset": 0, "shader_location": 0},
                        {"format": "float32x3", "offset": 8, "shader_location": 1},
                    ],
                }],
            },
            primitive={"topology": "triangle-list", "front_face": "ccw", "cull_mode": "none"},
            multisample={"count": 1, "mask": 0xffffffff, "alpha_to_coverage_enabled": False},
            fragment={
                "module": self.shader,
                "entry_point": "fs_main",
                "targets": [{"format": "rgba8unorm", "write_mask": 15}],
            },
        )

    def draw(self, target, *, shift=0.0):
        if self.closed:
            raise _binding().GPUValidationError("the triangle scene is closed")
        target._check_open("triangle draw")
        if target.gpu is not self.gpu:
            raise ValueError("triangle and target must belong to the same GPU")
        if shift != 0:
            self.vertices[:, 0] = TRIANGLE_F0[:, 0] + np.float32(shift)
            self.gpu.queue.write_buffer(self.vbo, 0, self.vertices)
        with render_pass(target, (0.10, 0.10, 0.12, 1.0)) as render:
            render.set_pipeline(self.pipeline)
            render.set_vertex_buffer(0, self.vbo)
            render.draw(3)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.vbo.destroy()
        self.vbo = self.pipeline = self.shader = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
