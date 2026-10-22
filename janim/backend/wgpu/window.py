"""The preview's presenter: a WebGPU surface on a GLFW window.

A surface exists only for a VISIBLE window on a native platform (Wayland, X11
or Cocoa); hidden windows and the Null platform draw into the render target and
`present` only pumps events. The pass is ManimGL's present.wgsl: one triangle
from `vertex_index`, nearest sampling, so at 1:1 the surface receives the
bytes of the frame (observable by reading the surface texture back through
CopySrc).
"""

from pathlib import Path

import numpy as np

from janim.backend import glfw as window_system
from janim.core.colorspace import _as_rgba  # noqa: F401  (colour helper shared with the strip)
from .context import GPUDeviceLostError, _binding, _shared_gpu
from .targets import padded_bytes_per_row, read_rgb_topdown
from .triangle import compile_wgsl
from .uniforms import RenderStats, texture_layout

PRESENT_WGSL = (Path(__file__).with_name("shaders") / "present.wgsl").read_text(encoding="utf-8")
PRESENTS = 0
SURFACE_RECONFIGS = 0
_PLAIN = {"bgra8unorm-srgb": "bgra8unorm", "rgba8unorm-srgb": "rgba8unorm"}


def plain_format(name):
    """The plain form of the surface's preferred format, never sRGB."""
    return _PLAIN.get(name, name)


class GPUPresenter:
    """Everything that presents one window: surface, configuration, pass objects."""

    def __init__(self, gpu, window, platform):
        from . import native

        gpu.check()
        self.gpu = gpu
        self.window = window
        self.platform = platform
        self.surface = native.create_surface(window_system.native_handles(window))
        if platform == "cocoa":
            window_system.sync_content_scale(window)
        self.format = None
        self.width = self.height = 0
        self.configured = False
        self.copy_src = False
        self.stats = RenderStats()
        self.layout = texture_layout(gpu, self.stats)
        self.pipeline_layout = gpu.device.create_pipeline_layout(bind_group_layouts=[self.layout])
        self.sampler = gpu.device.create_sampler(
            label="Janim present",
            address_mode_u="clamp-to-edge",
            address_mode_v="clamp-to-edge",
            address_mode_w="clamp-to-edge",
            mag_filter="nearest",
            min_filter="nearest",
            mipmap_filter="nearest",
            lod_min_clamp=0.0,
            lod_max_clamp=32.0,
            max_anisotropy=1,
        )
        self.shader = compile_wgsl(gpu, PRESENT_WGSL, label="present")
        self.pipeline = None
        self.pipeline_format = None
        self.bind_group = None
        self.bound_target = None
        self.warned = False
        self.presents = 0
        self.reconfigures = 0
        self.closed = False

    def configure(self, width, height):
        from . import native

        if not (width > 0 and height > 0):
            raise ValueError(f"a surface needs a positive size, got {width}×{height}")
        if self.format is None:
            capabilities = native.surface_capabilities(self.surface, self.gpu.adapter)
            if not capabilities["formats"]:
                raise _binding().GPUValidationError(
                    f"the adapter {self.gpu.info.renderer} cannot present on this window's surface (no formats)",
                )
            if "fifo" not in capabilities["present_modes"]:
                raise _binding().GPUValidationError("the surface offers no Fifo present mode (the one the spec guarantees)")
            self.copy_src = bool(capabilities["usages"] & native.USAGE_COPY_SRC)
            self.format = plain_format(capabilities["formats"][0])
            self.capabilities = capabilities
        usage = native.USAGE_RENDER_ATTACHMENT | (native.USAGE_COPY_SRC if self.copy_src else 0)
        native.surface_configure(self.surface, self.gpu, self.format, usage, width, height)
        self.gpu.check()
        self.width, self.height = int(width), int(height)
        self.configured = True
        return self

    def reconfigure(self):
        global SURFACE_RECONFIGS
        width, height = window_system.framebuffer_size(self.window)
        if not (width > 0 and height > 0):
            return False
        if self.platform == "cocoa":
            window_system.sync_content_scale(self.window)
        self.configure(width, height)
        self.reconfigures += 1
        SURFACE_RECONFIGS += 1
        return True

    def _ensure_pipeline(self):
        if self.pipeline is not None and self.pipeline_format == self.format:
            return self.pipeline
        self.pipeline = self.gpu.device.create_render_pipeline(
            label="Janim present",
            layout=self.pipeline_layout,
            vertex={"module": self.shader, "entry_point": "vs_main"},
            primitive={"topology": "triangle-list", "front_face": "ccw", "cull_mode": "none"},
            multisample={"count": 1, "mask": 0xffffffff, "alpha_to_coverage_enabled": False},
            fragment={"module": self.shader, "entry_point": "fs_main", "targets": [{"format": self.format, "write_mask": 15}]},
        )
        self.pipeline_format = self.format
        return self.pipeline

    def _ensure_bind_group(self, target):
        if self.bind_group is not None and self.bound_target is target:
            return self.bind_group
        self.bind_group = self.gpu.device.create_bind_group(
            label="Janim present",
            layout=self.layout,
            entries=[{"binding": 0, "resource": target.view}, {"binding": 1, "resource": self.sampler}],
        )
        self.bound_target = target
        return self.bind_group

    def acquire(self):
        from . import native

        if not self.configured:
            raise RuntimeError("acquire on an unconfigured surface: wgpu-native v24 would abort the process")
        return native.surface_acquire(self.surface)

    def present_to_view(self, target, view):
        """The pass: `target` onto any colour view in the surface's format."""
        target._check_open("present")
        pipeline = self._ensure_pipeline()
        bind_group = self._ensure_bind_group(target)
        encoder = self.gpu.device.create_command_encoder(label="Janim present")
        render = encoder.begin_render_pass(
            color_attachments=[{
                "view": view,
                "resolve_target": None,
                "clear_value": (0.0, 0.0, 0.0, 1.0),
                "load_op": "clear",
                "store_op": "store",
            }],
        )
        try:
            render.set_pipeline(pipeline)
            render.set_bind_group(0, bind_group)
            render.draw(3)
        finally:
            render.end()
        return self.gpu.submit(encoder.finish())

    def wrap(self, handle):
        from . import native

        usage = native.USAGE_RENDER_ATTACHMENT | (native.USAGE_COPY_SRC if self.copy_src else 0)
        return native.wrap_surface_texture(handle, self.gpu, self.format, self.width, self.height, usage)

    def draw_present(self, target, handle):
        global PRESENTS
        from . import native

        texture = self.wrap(handle)
        view = texture.create_view()
        self.present_to_view(target, view)
        native.surface_present(self.surface)
        view._release()
        texture._release()
        self.presents += 1
        PRESENTS += 1

    def present_status(self, target, status, handle):
        """Success presents; DeviceLost throws; anything else reconfigures and skips."""
        from . import native

        if status in (native.SURFACE_STATUS["success_optimal"], native.SURFACE_STATUS["success_suboptimal"]):
            self.draw_present(target, handle)
            return True
        native.release_texture(handle)
        if status == native.SURFACE_STATUS["device_lost"]:
            raise GPUDeviceLostError("the preview surface's device is lost: nothing on it can be presented again")
        if status in (native.SURFACE_STATUS["error"], native.SURFACE_STATUS["out_of_memory"]) and not self.warned:
            self.warned = True
            import warnings

            warnings.warn(
                f"the preview surface returned status {status} on acquire; reconfiguring and skipping the frame (once per session)",
                RuntimeWarning,
                stacklevel=3,
            )
        self.reconfigure()
        return False

    def release(self):
        from . import native

        if self.closed:
            return
        self.closed = True
        self.bind_group = self.pipeline = self.shader = self.sampler = None
        self.pipeline_layout = self.layout = None
        if self.configured:
            native.surface_unconfigure(self.surface)
        native.surface_release(self.surface)
        self.surface = None
        self.configured = False


def create_window(width, height, *, title="Janim", visible=True):
    """A window without a graphics API, with a presenter when visible and native."""
    window = window_system.create_window_noapi(width, height, title=title, visible=visible)
    platform = window_system.window_platform()
    if visible and not window_system.null_platform():
        if platform in ("wayland", "x11", "cocoa", "win32"):
            try:
                presenter = GPUPresenter(_shared_gpu(), window, platform)
                presenter.configure(*window_system.framebuffer_size(window))
                window.presenter = presenter
            except BaseException:
                window_system.close_context(window)
                raise
        else:
            window_system.close_context(window)
            raise RuntimeError(f"the preview surface on the {platform} platform is not written (Wayland, X11, Cocoa and Win32 are): render to a file")
    return window


def presenter(window):
    return None if window is None else window.presenter


def present(rv, window):
    """`rv.target` onto the window's surface when it has one, then the events."""
    target_presenter = presenter(window)
    if target_presenter is not None:
        width, height = window_system.framebuffer_size(window)
        if width > 0 and height > 0:
            if (width, height) != (target_presenter.width, target_presenter.height):
                target_presenter.reconfigure()
            status, handle = target_presenter.acquire()
            target_presenter.present_status(rv.target, status, handle)
            rv.gpu.check()
    window_system.poll_events()


def present_readback(rv, window):
    """Present one frame and return the swapchain's texture as read back BEFORE the present.

    The 1:1 guarantee: with CopySrc offered, the texture the surface
    is about to show holds the bytes of the frame (RGBA, unswizzled here).
    """
    from . import native
    from .targets import copy_target_to_buffer, create_staging, crop_rows, mapped_read

    target_presenter = presenter(window)
    if target_presenter is None or not target_presenter.copy_src:
        return None
    width, height = target_presenter.width, target_presenter.height
    status, handle = target_presenter.acquire()
    if status not in (native.SURFACE_STATUS["success_optimal"], native.SURFACE_STATUS["success_suboptimal"]):
        native.release_texture(handle)
        return None
    texture = target_presenter.wrap(handle)
    view = texture.create_view()
    target_presenter.present_to_view(rv.target, view)
    staging = create_staging(rv.gpu, padded_bytes_per_row(width) * height)
    encoder = rv.gpu.device.create_command_encoder(label="Janim swapchain readback")
    encoder.copy_texture_to_buffer(
        {"texture": texture},
        {"buffer": staging, "offset": 0, "bytes_per_row": padded_bytes_per_row(width), "rows_per_image": height},
        (width, height, 1),
    )
    index = rv.gpu.submit(encoder.finish())
    shown = bytearray(width * height * 4)
    with mapped_read(rv.gpu, staging, index, padded_bytes_per_row(width) * height) as data:
        crop_rows(data, shown, width, height, 4)
    staging.destroy()
    native.surface_present(target_presenter.surface)
    view._release()
    texture._release()
    target_presenter.presents += 1
    global PRESENTS
    PRESENTS += 1
    window_system.poll_events()
    pixels = np.frombuffer(shown, dtype=np.uint8).reshape(height, width, 4)
    if target_presenter.format.startswith("bgra"):
        pixels = pixels[:, :, [2, 1, 0, 3]]
    return pixels.copy()


def write_target(rv, data, x, y, width, height):
    """`4·w·h` RGBA bytes at (x, y), row 0 the top, through the queue."""
    target = rv.target
    target._check_copyable()
    view = memoryview(data).cast("B")
    if view.nbytes < 4 * width * height:
        raise ValueError(f"a {width}×{height} write needs {4 * width * height} bytes, got {view.nbytes}")
    if x + width > target.width or y + height > target.height:
        raise ValueError(f"a {width}×{height} write at ({x}, {y}) falls outside the {target.width}×{target.height} target")
    rv.gpu.queue.write_texture(
        {"texture": target.texture, "origin": (int(x), int(y), 0)},
        view[:4 * width * height],
        {"bytes_per_row": 4 * width, "rows_per_image": height},
        (int(width), int(height), 1),
    )
    rv.gpu.check()


def blit_image(rv, image):
    """A cached `H×W×3` frame back INTO the target: a cache hit leaves ITS frame."""
    height, width = rv.height, rv.width
    if image.shape != (height, width, 3):
        raise ValueError(f"a {width}×{height} VM cannot blit a {image.shape} image")
    if getattr(rv, "scratch", None) is None or rv.scratch.shape != (height, width, 4):
        rv.scratch = np.empty((height, width, 4), dtype=np.uint8)
    rv.scratch[:, :, :3] = image
    rv.scratch[:, :, 3] = 255
    write_target(rv, rv.scratch, 0, 0, width, height)


def paint_strip(rv, width, height, bar, segments):
    """The timeline strip: `bar` rows at the bottom, segment by segment in order."""
    if (width, height) != (rv.width, rv.height):
        raise ValueError(f"the strip's {width}×{height} is not the VM's {rv.width}×{rv.height}")
    buffer = np.zeros((bar, width, 4), dtype=np.uint8)
    for x0, x1, r, g, b in segments:
        color = (int(round(255 * r)), int(round(255 * g)), int(round(255 * b)), 255)
        buffer[:, x0:x1] = color
    write_target(rv, buffer, 0, height - bar, width, bar)


def read_frame_into(rv, destination):
    """The target as top-down RGB into `destination` (H×W×3), reusing the VM's staging."""
    rv._check_open("readback")
    from .targets import create_staging

    if rv.staging is None:
        rv.staging = create_staging(rv.gpu, padded_bytes_per_row(rv.width) * rv.height)
        rv.stats.objects += 1
    read_rgb_topdown(rv.gpu, rv.target, staging=rv.staging, destination=destination)
    return destination
