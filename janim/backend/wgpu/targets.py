"""Owned color/depth targets and padded readback."""

from contextlib import contextmanager
import operator

import numpy as np

from janim.png import dimensions
from .context import _binding, _shared_gpu, gpu_info


def padded_bytes_per_row(width):
    width = operator.index(width)
    if width <= 0:
        raise ValueError("a row needs a positive width")
    return ((4 * width + 255) // 256) * 256


class GPUTarget:
    """Own the textures and views; a borrower must keep this target alive."""

    def __init__(self, gpu, width, height, *, depth=False, samples=1, format="rgba8unorm"):
        gpu.check()
        binding = _binding()
        self.gpu = gpu
        self.width, self.height = dimensions(width, height)
        self.samples = operator.index(samples)
        if self.samples not in (1, 4):
            raise ValueError("target samples must be 1 or 4")
        if format not in ("rgba8unorm", "rgba16float"):
            raise ValueError("target format must be rgba8unorm or rgba16float")
        self.format = format
        self.closed = False
        self.texture = self.view = self.depth = self.depth_view = None
        usage = binding.TextureUsage.RENDER_ATTACHMENT
        if samples == 1:
            usage |= (
                binding.TextureUsage.COPY_SRC
                | binding.TextureUsage.COPY_DST
                | binding.TextureUsage.TEXTURE_BINDING
            )
        try:
            self.texture = gpu.device.create_texture(
                label="Janim target",
                size=(self.width, self.height, 1),
                format=format,
                sample_count=samples,
                usage=usage,
            )
            self.view = self.texture.create_view()
            if depth:
                self.depth = gpu.device.create_texture(
                    label="Janim depth",
                    size=(self.width, self.height, 1),
                    format="depth24plus-stencil8",
                    sample_count=samples,
                    usage=binding.TextureUsage.RENDER_ATTACHMENT,
                )
                self.depth_view = self.depth.create_view()
        except BaseException:
            self.close()
            raise

    def _check_open(self, what="operation"):
        if self.closed:
            raise _binding().GPUValidationError(f"the target is closed before {what}")
        self.gpu.check()

    def _check_copyable(self):
        self._check_open("readback or upload")
        if self.samples != 1 or self.format != "rgba8unorm":
            raise ValueError("byte readback/upload needs a single-sample rgba8unorm target")

    def clear(self, color=(0.0, 0.0, 0.0, 1.0), *, resolve=None):
        with render_pass(self, color, resolve=resolve):
            pass

    def write_rgba(self, pixels):
        self._check_copyable()
        data = memoryview(pixels).cast("B")
        if len(data) != self.width * self.height * 4:
            raise ValueError("RGBA upload size does not match the target")
        self.gpu.queue.write_texture(
            {"texture": self.texture},
            data,
            {"bytes_per_row": 4 * self.width, "rows_per_image": self.height},
            (self.width, self.height, 1),
        )
        self.gpu.check()

    def close(self):
        if self.closed:
            return
        self.closed = True
        # Drop references instead of destroying resources another wrapper owns.
        self.view = self.depth_view = None
        self.texture = self.depth = None

    def __enter__(self):
        self._check_open()
        return self

    def __exit__(self, *_):
        self.close()


@contextmanager
def render_pass(target, color, *, resolve=None):
    target._check_open("render pass")
    if resolve is not None:
        resolve._check_open("resolve")
        if resolve.gpu is not target.gpu:
            raise ValueError("resolve and target must belong to the same GPU")
    encoder = target.gpu.device.create_command_encoder(label="Janim frame")
    attachment = {
        "view": target.view,
        "resolve_target": None if resolve is None else resolve.view,
        "clear_value": tuple(float(c) for c in color),
        "load_op": "clear",
        "store_op": "store" if resolve is None else "discard",
    }
    options = {}
    if target.depth_view is not None:
        options["depth_stencil_attachment"] = {
            "view": target.depth_view,
            "depth_clear_value": 1.0,
            "depth_load_op": "clear",
            "depth_store_op": "store" if target.samples == 1 else "discard",
            "stencil_clear_value": 0,
            "stencil_load_op": "clear",
            "stencil_store_op": "discard",
        }
    render = encoder.begin_render_pass(color_attachments=[attachment], **options)
    try:
        yield render
    except BaseException:
        render.end()
        raise
    else:
        render.end()
        target.gpu.submit(encoder.finish())


def create_staging(gpu, nbytes):
    gpu.check()
    binding = _binding()
    return gpu.device.create_buffer(
        label="Janim readback",
        size=nbytes,
        usage=binding.BufferUsage.MAP_READ | binding.BufferUsage.COPY_DST,
    )


def copy_target_to_buffer(gpu, target, staging):
    target._check_copyable()
    if target.gpu is not gpu:
        raise ValueError("target belongs to another GPU")
    encoder = gpu.device.create_command_encoder(label="Janim readback copy")
    encoder.copy_texture_to_buffer(
        {"texture": target.texture},
        {
            "buffer": staging,
            "offset": 0,
            "bytes_per_row": padded_bytes_per_row(target.width),
            "rows_per_image": target.height,
        },
        (target.width, target.height, 1),
    )
    return gpu.submit(encoder.finish())


@contextmanager
def mapped_read(gpu, staging, index, nbytes):
    gpu.check()
    # Public map_sync adds an empty submit and polls all work. v24's indexed
    # wait preserves the overlap with the next frame; the binding still owns
    # the callback, map state, memoryviews and unmap bookkeeping.
    pending = staging._map("READ_NOSYNC", 0, nbytes)
    # The staging owner handles a failed map and destroys its buffer once.
    # On failure the traceback retains this frame and its pending callback
    # until _read, GPURenderVM.read or FramePipeline's cleanup cancels it.
    gpu.wait(index)
    if pending.result is None:
        gpu.wait()
    if pending.result is None:
        raise RuntimeError("the map callback never fired after a blocking device poll")
    pending.sync_wait()
    try:
        yield staging.read_mapped(size=nbytes, copy=False)
    finally:
        staging.unmap()


def crop_rows(source, destination, width, height, channels=3):
    padded = np.frombuffer(source, dtype=np.uint8).reshape(height, padded_bytes_per_row(width))
    rgba = padded[:, :width * 4].reshape(height, width, 4)
    tight = np.frombuffer(destination, dtype=np.uint8).reshape(height, width, channels)
    np.copyto(tight, rgba[:, :, :channels])


def _read(gpu, target, channels, *, staging=None, destination=None):
    target._check_copyable()
    own_staging = staging is None
    result = bytearray(target.width * target.height * channels) if destination is None else destination
    if memoryview(result).nbytes != target.width * target.height * channels:
        raise ValueError("readback destination size does not match the target")
    if own_staging:
        staging = create_staging(gpu, padded_bytes_per_row(target.width) * target.height)
    try:
        index = copy_target_to_buffer(gpu, target, staging)
        with mapped_read(gpu, staging, index, padded_bytes_per_row(target.width) * target.height) as data:
            crop_rows(data, result, target.width, target.height, channels)
    finally:
        if own_staging:
            staging.destroy()
    return memoryview(result).toreadonly() if destination is None else result


def read_rgb_topdown(gpu, target, *, staging=None, destination=None):
    """Return an independent read-only RGB view, or fill the supplied buffer."""
    return _read(gpu, target, 3, staging=staging, destination=destination)


def read_rgba_topdown(gpu, target, *, staging=None, destination=None):
    """Return an independent read-only RGBA view, or fill the supplied buffer."""
    return _read(gpu, target, 4, staging=staging, destination=destination)


def render_solid_frame(width, height, color=(0, 0, 0, 255)):
    gpu = _shared_gpu()
    with GPUTarget(gpu, width, height) as target:
        target.clear(tuple(float(c) / 255 for c in color))
        return read_rgb_topdown(gpu, target), gpu_info(gpu)


def render_two_band_frame(width, height):
    gpu = _shared_gpu()
    with GPUTarget(gpu, width, height) as target:
        pixels = np.zeros((height, width, 4), dtype=np.uint8)
        pixels[:, :, 3] = 255
        split = (height + 1) // 2
        pixels[:split, :, 0] = 255
        pixels[split:, :, 2] = 255
        target.write_rgba(pixels)
        return read_rgb_topdown(gpu, target), gpu_info(gpu)
