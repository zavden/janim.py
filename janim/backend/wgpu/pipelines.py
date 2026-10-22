"""Literal shader assembly and the 17 render states.

The three fill shaders include inserts/thin_triangle.wgsl and declare
``THIN_PX``; the six fill modules substitute it (``_FILL_THIN_PX``, the height
in window pixels under which a fill triangle is culled; 0 turns the cull off,
leaving only ManimGL 1.7's two culls). The default text is identical to the
shader source.
"""

from pathlib import Path
import re

import numpy as np

from .triangle import compile_wgsl


SHADERS = Path(__file__).with_name("shaders")
_STROKE_SWAP_P1P2 = False
_STROKE_Z_CORE = 0.5
_FILL_THIN_PX = 2 ** -9
_FILL_MODULES = ("stencil_1", "stencil_4", "stencil_grad_1", "stencil_grad_4", "cover", "cover_grad")
_COVER_DEPTH_SLOPE = 1.0
_COVER_DEPTH_BIAS = 0


def assemble(name):
    lines = []
    for line in (SHADERS / name).read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"// #INSERT (\S+)\s*", line)
        if match:
            insert = match[1]
            if Path(insert).name != insert:
                raise ValueError("shader inserts must name a local source")
            lines.append(f"// ── {insert} ──\n" + (SHADERS / "inserts" / insert).read_text(encoding="utf-8"))
        else:
            lines.append(line)
    return "\n".join(lines) + "\n"


def replace_constant(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f"expected exactly one shader declaration: {old}")
    return source.replace(old, new)


def fill_source(source):
    return replace_constant(
        source,
        "const THIN_PX: f32 = 0.001953125;",
        f"const THIN_PX: f32 = {float(np.float32(_FILL_THIN_PX))};",
    )


def shader_source(name):
    if name in ("cover", "cover_grad"):
        return fill_source(assemble(name + ".wgsl"))
    if name == "stroke_zpass":
        source = replace_constant(
            assemble("stroke.wgsl"),
            "const Z_PASS: f32 = 0.0;",
            "const Z_PASS: f32 = 1.0;",
        )
        return replace_constant(
            source,
            "const Z_CORE: f32 = 0.5;",
            f"const Z_CORE: f32 = {float(np.float32(_STROKE_Z_CORE))};",
        )
    if name.startswith("stencil_"):
        samples = int(name.rsplit("_", 1)[1])
        if samples not in (1, 4):
            raise ValueError("stencil samples must be 1 or 4")
        source = replace_constant(
            assemble("stencil.wgsl"),
            "const SAMPLES: u32 = 4u;",
            f"const SAMPLES: u32 = {samples}u;",
        )
        source = replace_constant(
            source,
            "const CULL_ALPHA: f32 = 1.0;",
            f"const CULL_ALPHA: f32 = {0.0 if 'grad' in name else 1.0};",
        )
        return fill_source(source)
    return assemble(name + ".wgsl")


def vertex_layouts(kind):
    def slot(stride, attributes, *, mode="instance"):
        return {
            "array_stride": stride,
            "step_mode": mode,
            "attributes": [
                {"format": format, "offset": offset, "shader_location": location}
                for format, offset, location in attributes
            ],
        }

    def triple(format, size, location):
        return [(format, i * size, location + i) for i in range(3)]

    if kind == "stroke":
        points = triple("float32x3", 12, 0)
        if _STROKE_SWAP_P1P2:
            points[1], points[2] = ("float32x3", 24, 1), ("float32x3", 12, 2)
        return [
            slot(36, points),
            slot(48, [("float32", 0, 13)]),
            slot(48, triple("float32x4", 16, 3)),
            slot(12, triple("float32", 4, 6)),
            slot(12, triple("float32", 4, 9)),
            slot(36, [("float32x3", 12, 12)]),
            slot(24, [("float32", 0, 14)]),
            slot(24, [("float32", 0, 15)]),
        ]
    if kind in ("stencil", "stencil_grad", "cover", "cover_grad"):
        return [
            slot(36, triple("float32x3", 12, 0)),
            slot(48, triple("float32x4", 16, 3)),
            slot(48, [("float32", 0, 12)]),
            slot(12, [("float32", 0, 13)]),
            slot(12, [("float32", 0, 14)]),
            slot(36, [("float32x3", 0, 6), ("float32x3", 12, 7)]),
            slot(24, triple("float32x2", 8, 8) if kind == "cover_grad" else [("float32", 0, 15)]),
            slot(24, [("float32x2", 0, 11)] if kind == "cover_grad" else [("float32", 0, 9)]),
        ]
    attributes = {
        "dots": [(12, "float32x3"), (4, "float32"), (16, "float32x4")],
        "surface": [(12, "float32x3"), (12, "float32x3"), (16, "float32x4")],
        "image": [(12, "float32x3"), (8, "float32x2")],
        "textured_surface": [(12, "float32x3"), (12, "float32x3"), (8, "float32x2")],
    }
    if kind not in attributes:
        raise ValueError(f"unknown pipeline primitive: {kind}")
    return [
        slot(size, [(format, 0, i)], mode="instance" if kind == "dots" else "vertex")
        for i, (size, format) in enumerate(attributes[kind])
    ]


def stencil_face(compare="always", pass_op="keep", depth_fail_op="keep"):
    return {"compare": compare, "fail_op": "keep", "depth_fail_op": depth_fail_op, "pass_op": pass_op}


class PipelineCache:
    def __init__(self, gpu, stats, layout, texture_layout):
        self.gpu, self.stats = gpu, stats
        self.layout, self.texture_layout = layout, texture_layout
        self.modules = {}
        self.pipelines = {}

    def module(self, name):
        if name not in self.modules:
            self.modules[name] = compile_wgsl(self.gpu, shader_source(name), label="Janim " + name)
            self.stats.objects += 1
        return self.modules[name]

    def get(self, kind, depth=False, z_pass=False, samples=4, format="rgba8unorm"):
        key = kind, depth, z_pass, samples, format
        if key in self.pipelines:
            return self.pipelines[key]
        if samples not in (1, 4):
            raise ValueError("a render pipeline needs 1 or 4 samples")
        if z_pass and (kind != "stroke" or not depth):
            raise ValueError("the z prepass belongs to the depth-tested stroke alone")
        write_mask = 15
        compare = "less" if depth else "always"
        write_depth = bool(depth)
        front = back = stencil_face()
        bias = slope = 0
        if kind in ("stencil", "stencil_grad"):
            if depth or z_pass:
                raise ValueError("the stencil count neither depth-tests nor runs a z prepass")
            module = self.module(f"{kind}_{samples}")
            write_mask = 0
            front = stencil_face(pass_op="increment-wrap")
            back = stencil_face(pass_op="decrement-wrap")
        elif kind in ("cover", "cover_grad"):
            module = self.module(kind)
            front = back = stencil_face("not-equal", "zero", "zero")
            if depth:
                bias, slope = _COVER_DEPTH_BIAS, _COVER_DEPTH_SLOPE
        elif kind == "stroke":
            module = self.module("stroke_zpass" if z_pass else "stroke")
            if z_pass:
                write_mask = 0
            elif depth:
                compare, write_depth = "less-equal", False
        else:
            module = self.module("true_dot" if kind == "dots" else kind)
        textured = kind in ("cover_grad", "image", "textured_surface")
        result = self.gpu.device.create_render_pipeline(
            label=f"Janim {kind} depth={depth} z_pass={z_pass}",
            layout=self.texture_layout if textured else self.layout,
            vertex={"module": module, "entry_point": "vs_main", "buffers": vertex_layouts(kind)},
            primitive={
                "topology": "triangle-strip" if kind == "image" else "triangle-list",
                "front_face": "ccw",
                "cull_mode": "none",
            },
            depth_stencil={
                "format": "depth24plus-stencil8",
                "depth_write_enabled": write_depth,
                "depth_compare": compare,
                "stencil_front": front,
                "stencil_back": back,
                "stencil_read_mask": 0xffffffff,
                "stencil_write_mask": 0xffffffff,
                "depth_bias": bias,
                "depth_bias_slope_scale": slope,
                "depth_bias_clamp": 0.0,
            },
            multisample={"count": samples, "mask": 0xffffffff, "alpha_to_coverage_enabled": False},
            fragment={
                "module": module,
                "entry_point": "fs_main",
                "targets": [{
                    "format": format,
                    "write_mask": write_mask,
                    "blend": {
                        "color": {"operation": "add", "src_factor": "src-alpha", "dst_factor": "one-minus-src-alpha"},
                        "alpha": {"operation": "add", "src_factor": "one", "dst_factor": "one-minus-src-alpha"},
                    },
                }],
            },
        )
        self.stats.objects += 1
        self.pipelines[key] = result
        return result

    def close(self):
        self.pipelines.clear()
        self.modules.clear()
        self.layout = self.texture_layout = None
