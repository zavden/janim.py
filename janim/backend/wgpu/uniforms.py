"""Exact block layouts and persistent arenas."""

from dataclasses import dataclass

import numpy as np

from janim.core.camera import camera_uniforms
from .context import _binding


FRAME_DTYPE = np.dtype(
    [
        ("view", "<f4", (16,)),
        ("frame_rescale_factors", "<f4", (3,)),
        ("frame_scale", "<f4"),
        ("camera_position", "<f4", (3,)),
        ("pixel_size", "<f4"),
        ("light_position", "<f4", (3,)),
        ("_pad", "<f4"),
    ],
)
MOBJECT_DTYPE = np.dtype(
    [
        ("shading", "<f4", (3,)),
        ("is_fixed_in_frame", "<f4"),
        ("anti_alias_width", "<f4"),
        ("joint_type", "<f4"),
        ("flat_stroke", "<f4"),
        ("stroke_width_in_scene_units", "<f4"),
        ("grad_focus", "<f4", (3,)),
        ("grad_kind", "<f4"),
        ("spread_mode", "<f4"),
        ("grad_opacity", "<f4"),
        ("glow_factor", "<f4"),
        ("opacity", "<f4"),
    ],
)
QUAD_DTYPE = np.dtype(
    [
        ("f0", "<f4", (4,)),
        ("f1", "<f4", (4,)),
        ("i0", "<i4", (4,)),
        ("w", "<f4", (64,)),
    ],
)


def frame_uniforms(camera):
    values = camera_uniforms(camera) if not isinstance(camera, dict) else camera
    result = np.zeros((), dtype=FRAME_DTYPE)
    for name in FRAME_DTYPE.names:
        if name == "view":
            result[name] = values[name].T.reshape(-1)
        elif name != "_pad":
            result[name] = values[name]
    return result


def mobject_uniforms(**values):
    result = np.zeros((), dtype=MOBJECT_DTYPE)
    result["anti_alias_width"] = 1.5
    result["joint_type"] = 1
    result["grad_opacity"] = 1
    result["opacity"] = 1
    for name, value in values.items():
        result[name] = value
    return result


def quad_params(*, f0=(), f1=(), i0=(), w=()):
    result = np.zeros((), dtype=QUAD_DTYPE)
    for name, values, maximum in (("f0", f0, 4), ("f1", f1, 4), ("i0", i0, 4), ("w", w, 64)):
        if len(values) > maximum:
            raise ValueError(f"{name} accepts at most {maximum} values")
        result[name][:len(values)] = values
    return result


@dataclass
class RenderStats:
    objects: int = 0
    upload_bytes: int = 0
    upload_calls: int = 0
    flush_bytes: int = 0        # bytes the arena's merged writes carried, gaps included
    geometry_bytes: int = 0
    uniform_bytes: int = 0
    texture_bytes: int = 0
    runs: int = 0
    draws: int = 0
    passes: int = 0
    merged_draws: int = 0       # mesh commands a neighbour's draw carried
    bundles: int = 0            # frames recorded once into a render bundle
    bundle_replays: int = 0     # passes that executed one instead of recording
    arena_binds: int = 0
    block_binds: int = 0
    mirror_checks: int = 0


def gpu_buffer(gpu, stats, size, usage, label):
    result = gpu.device.create_buffer(label=label, size=max(4, size), usage=usage)
    stats.objects += 1
    return result


def write_buffer(gpu, stats, buffer, offset, data, *, category="geometry"):
    size = memoryview(data).nbytes
    if not size:
        return
    gpu.queue.write_buffer(buffer, offset, data)
    stats.upload_bytes += size
    stats.upload_calls += 1
    if category == "geometry":
        stats.geometry_bytes += size
    else:
        stats.uniform_bytes += size


def uniform_layout(gpu, stats, size, label):
    result = gpu.device.create_bind_group_layout(
        label=label,
        entries=[{
            "binding": 0,
            "visibility": _binding().ShaderStage.VERTEX | _binding().ShaderStage.FRAGMENT,
            "buffer": {"type": "uniform", "has_dynamic_offset": True, "min_binding_size": size},
        }],
    )
    stats.objects += 1
    return result


def texture_layout(gpu, stats):
    result = gpu.device.create_bind_group_layout(
        label="Janim texture layout",
        entries=[
            {
                "binding": 0,
                "visibility": _binding().ShaderStage.FRAGMENT,
                "texture": {"sample_type": "float", "view_dimension": "2d", "multisampled": False},
            },
            {
                "binding": 1,
                "visibility": _binding().ShaderStage.FRAGMENT,
                "sampler": {"type": "filtering"},
            },
        ],
    )
    stats.objects += 1
    return result


class ParamArena:
    def __init__(self, gpu, stats, dtype, *, capacity, label, layout=None):
        self.gpu, self.stats, self.dtype = gpu, stats, dtype
        alignment = gpu.device.limits["min-uniform-buffer-offset-alignment"] or 256
        self.stride = dtype.itemsize + (-dtype.itemsize % alignment)
        self.capacity = capacity
        self.label = label
        self.layout = layout
        self.buffer = self.bind_group = None
        self.staging = bytearray(self.stride * capacity)
        self.n = 0
        self.recorded = False
        self._last = None
        self.generation = 0         # a new buffer and bind group each time `_create` runs
        self._create()

    def _create(self):
        self.generation += 1
        self.buffer = gpu_buffer(
            self.gpu,
            self.stats,
            self.capacity * self.stride,
            _binding().BufferUsage.UNIFORM | _binding().BufferUsage.COPY_DST,
            self.label,
        )
        if self.layout is not None:
            self.bind_group = self.gpu.device.create_bind_group(
                label=self.label + " bind group",
                layout=self.layout,
                entries=[{
                    "binding": 0,
                    "resource": {"buffer": self.buffer, "offset": 0, "size": self.dtype.itemsize},
                }],
            )
            self.stats.objects += 1
        self._last = None

    def reset(self):
        if self.recorded:
            raise RuntimeError("submit the recorded passes before resetting their parameter arena")
        self.n = 0

    def push(self, block):
        if not self.has_room():
            raise RuntimeError(f"the {self.label} ring is full: flush before adding a slot")
        return self._stage(block)

    def has_room(self, count=1):
        return 0 <= count <= self.capacity - self.n

    def _stage(self, block):
        if block.dtype != self.dtype:
            raise TypeError(f"wrong uniform block type for {self.label}")
        return self._stage_bytes(block.tobytes())

    def _stage_bytes(self, data):
        if len(data) != self.dtype.itemsize:
            raise TypeError(f"wrong uniform block size for {self.label}")
        slot = self.n
        needed = (slot + 1) * self.stride
        if needed > len(self.staging):
            self.staging.extend(bytes(max(needed, 2 * len(self.staging)) - len(self.staging)))
        offset = slot * self.stride
        self.staging[offset:offset + len(data)] = data
        self.n += 1
        return slot

    def upload(self):
        payload = self.staging[:self.n * self.stride]
        # Uniform values also remain valid between identical frames. The
        # bit comparison skips redundant queue traffic without dirty hooks.
        if payload and payload != self._last:
            write_buffer(self.gpu, self.stats, self.buffer, 0, payload, category="uniform")
            self._last = payload

    def close(self):
        self.bind_group = None
        self.buffer = None
        self.staging.clear()


class UniformArena(ParamArena):
    def __init__(self, gpu, stats, layout, *, capacity=256):
        super().__init__(
            gpu,
            stats,
            MOBJECT_DTYPE,
            capacity=capacity,
            label="Janim mobject uniforms",
            layout=layout,
        )

    def push(self, block):
        return self.push_bytes(block.tobytes())

    def push_bytes(self, data):
        """A block serialised once by its owner: the previous slot when the bytes repeat."""
        if self.n:
            offset = (self.n - 1) * self.stride
            if self.staging[offset:offset + self.dtype.itemsize] == data:
                return self.n - 1
        return self._stage_bytes(data)

    def ensure_capacity(self):
        if self.n <= self.capacity:
            return
        if self.recorded:
            raise RuntimeError("flush before growing a uniform arena used by a recorded pass")
        self.capacity = max(2 * self.capacity, self.n)
        self._create()

    def upload(self):
        self.ensure_capacity()
        super().upload()
