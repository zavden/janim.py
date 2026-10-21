"""Small v24 bridge for features absent from wgpu-py 0.21's public API.

Use the binding's own cffi declarations and safe-call proxy. Only instance
configuration, per-device error callbacks and indexed submissions need this
bridge; resources and render descriptors use wgpu-py's regular classes.
"""

import os

from .context import _BINDING, BACKEND

if _BINDING is None:
    raise RuntimeError("load the native bridge through context._binding() first")

import wgpu
from wgpu.backends.wgpu_native import _api, _helpers
from wgpu.backends.wgpu_native._ffi import ffi, lib


_INSTANCE = None
# wgpu.h: WGPUInstanceBackend_Vulkan = 1 << 0, _Metal = 1 << 2; cffi ABI mode
# cannot expose this header's static const WGPUFlags as integer constants.
_INSTANCE_BACKENDS = {"Vulkan": 1 << 0, "Metal": 1 << 2}
_BACKEND_TYPES = {"Vulkan": lib.WGPUBackendType_Vulkan, "Metal": lib.WGPUBackendType_Metal}
NATIVE_CALLS = (
    "wgpuCreateInstance",
    "wgpuAdapterRequestDevice",
    "wgpuDeviceGetQueue",
    "wgpuQueueSubmitForIndex",
    "wgpuDevicePoll",
    "wgpuInstanceEnumerateAdapters",
    "wgpuAdapterGetInfo",
    "wgpuAdapterInfoFreeMembers",
    "wgpuAdapterRelease",
    "wgpuSetLogCallback",
    "wgpuSetLogLevel",
    "wgpuSurfaceGetCapabilities",
    "wgpuSurfaceCapabilitiesFreeMembers",
    "wgpuSurfaceConfigure",
    "wgpuSurfaceUnconfigure",
    "wgpuSurfaceGetCurrentTexture",
    "wgpuSurfacePresent",
    "wgpuSurfaceRelease",
    "wgpuTextureRelease",
)


def initialize_instance():
    global _INSTANCE
    if _INSTANCE is not None:
        return
    if _helpers._the_instance is not None:
        raise RuntimeError(f"a graphics instance was opened before Janim's {BACKEND} gate")
    levels = {
        "off": lib.WGPULogLevel_Off,
        "error": lib.WGPULogLevel_Error,
        "warn": lib.WGPULogLevel_Warn,
        "info": lib.WGPULogLevel_Info,
        "debug": lib.WGPULogLevel_Debug,
        "trace": lib.WGPULogLevel_Trace,
    }
    _api.libf.wgpuSetLogCallback(_on_log, ffi.NULL)
    _api.libf.wgpuSetLogLevel(levels.get(os.environ.get("JANIM_WGPU_LOG", "warn").lower(), levels["warn"]))
    extras = ffi.new("WGPUInstanceExtras *")
    extras.chain.sType = lib.WGPUSType_InstanceExtras
    extras.backends = _INSTANCE_BACKENDS[BACKEND]
    descriptor = ffi.new("WGPUInstanceDescriptor *")
    descriptor.nextInChain = ffi.cast("WGPUChainedStruct *", extras)
    instance = _api.libf.wgpuCreateInstance(descriptor)
    if instance == ffi.NULL:
        raise RuntimeError(f"could not create the {BACKEND} instance")
    _helpers._the_instance = instance
    _INSTANCE = instance


def _adapter_information(info):
    # Native 24.0.0.1 implements a void return despite the header's WGPUStatus.
    # Its return register is undefined; read only the filled struct.
    if info.backendType != _BACKEND_TYPES[BACKEND]:
        raise wgpu.GPUValidationError("adapter information is missing or invalid")
    result = {
        key: _api.from_c_string_view(getattr(info, key))
        for key in ("vendor", "architecture", "device", "description")
    }
    if not result["device"]:
        raise wgpu.GPUValidationError("adapter information has an empty device name")
    result.update(
        vendor_id=int(info.vendorID),
        device_id=int(info.deviceID),
        adapter_type=_api.enum_int2str["AdapterType"].get(info.adapterType, "Unknown"),
        backend_type=BACKEND,
    )
    return result


def enumerate_adapters():
    count = _api.libf.wgpuInstanceEnumerateAdapters(_INSTANCE, ffi.NULL, ffi.NULL)
    handles = ffi.new("WGPUAdapter[]", count)
    _api.libf.wgpuInstanceEnumerateAdapters(_INSTANCE, ffi.NULL, handles)
    adapters = []
    try:
        for handle in handles:
            info = ffi.new("WGPUAdapterInfo *")
            try:
                _api.libf.wgpuAdapterGetInfo(handle, info)
                values = _adapter_information(info[0])
            finally:
                _api.libf.wgpuAdapterInfoFreeMembers(info[0])
            adapter = _api.GPUAdapter(
                handle,
                _api._get_features(handle, adapter=True),
                _api._get_limits(handle, adapter=True),
                values,
            )
            adapters.append(adapter)
    except BaseException:
        for handle in handles[len(adapters):count]:
            _api.libf.wgpuAdapterRelease(handle)
        raise
    return adapters


def _copy_message(destination, message):
    """Copy at most one slot, respecting NULL and the WGPU_STRLEN sentinel."""
    if message.data == ffi.NULL:
        return 0
    if message.length == lib.WGPU_STRLEN:
        length = len(ffi.string(message.data, 4095))
    else:
        length = min(message.length, 4095)
    if length:
        ffi.memmove(destination, message.data, length)
    return length


class Mailbox:
    """Preallocated first-message slots; native callbacks never print or throw."""

    def __init__(self):
        self.errors = ffi.new("char[4096]")
        self.lost = ffi.new("char[4096]")
        self.state = ffi.new("size_t[5]")

    def post_error(self, message):
        if self.state[0] == 0:
            self.state[1] = _copy_message(self.errors, message)
        self.state[0] += 1

    def post_lost(self, reason, message):
        if reason != lib.WGPUDeviceLostReason_Destroyed and self.state[2] == 0:
            self.state[2] = reason
            self.state[3] = _copy_message(self.lost, message)

    def check(self, gpu):
        if self.state[2]:
            from .context import GPUDeviceLostError

            gpu.dead = True
            message = bytes(ffi.buffer(self.lost, self.state[3])).decode(errors="replace")
            raise GPUDeviceLostError(message or "the GPU device was lost")
        if self.state[0]:
            count = self.state[0]
            message = bytes(ffi.buffer(self.errors, self.state[1])).decode(errors="replace")
            self.state[0] = 0
            raise wgpu.GPUValidationError(f"{message} ({count} uncaptured errors)")


_LOG = Mailbox()


@ffi.callback("void(WGPULogLevel, WGPUStringView, void *)")
def _on_log(level, message, userdata):
    if _LOG.state[0] == 0:
        _LOG.state[4] = level
    _LOG.post_error(message)


def wgpu_log():
    """Take (count, first level, first message) without logging in callbacks."""
    count, length = _LOG.state[0], _LOG.state[1]
    result = (
        count,
        int(_LOG.state[4]) if count else 0,
        bytes(ffi.buffer(_LOG.errors, length)).decode(errors="replace") if count else "",
    )
    _LOG.state[0] = _LOG.state[1] = _LOG.state[4] = 0
    return result


def request_device(adapter):
    mailbox = Mailbox()

    @ffi.callback(
        "void(WGPUDevice const *, WGPUDeviceLostReason, WGPUStringView, void *, void *)",
    )
    def lost(device, reason, message, user1, user2):
        mailbox.post_lost(reason, message)

    @ffi.callback(
        "void(WGPUDevice const *, WGPUErrorType, WGPUStringView, void *, void *)",
    )
    def error(device, kind, message, user1, user2):
        # Match the binding's normal exception attribution for synchronous calls.
        if _api.error_handler._get_proxy_stack():
            _api.error_handler.handle_error(
                _api.enum_int2str["ErrorType"].get(kind, "Unknown"),
                _api.from_c_string_view(message),
            )
        else:
            mailbox.post_error(message)

    reply = ffi.new("WGPUDevice *")
    status = ffi.new("int *", -1)

    @ffi.callback(
        "void(WGPURequestDeviceStatus, WGPUDevice, WGPUStringView, void *, void *)",
    )
    def received(code, device, message, user1, user2):
        status[0] = code
        reply[0] = device
        if code != lib.WGPURequestDeviceStatus_Success:
            mailbox.post_error(message)

    limits = ffi.new("WGPULimits *")
    for name, field in ffi.typeof(limits[0]).fields:
        if field.type.kind == "primitive":
            setattr(limits, name, (1 << (8 * ffi.sizeof(field.type))) - 1)
    limits.minUniformBufferOffsetAlignment = adapter.limits["min-uniform-buffer-offset-alignment"]
    limits.minStorageBufferOffsetAlignment = adapter.limits["min-storage-buffer-offset-alignment"]
    features = ffi.new("WGPUFeatureName[]", [lib.WGPUFeatureName_Float32Filterable])
    descriptor = ffi.new("WGPUDeviceDescriptor *")
    label = ffi.new("char[]", b"Janim device")
    descriptor.label.data = label
    descriptor.label.length = len(b"Janim device")
    descriptor.requiredLimits = limits
    if "float32-filterable" in adapter.features:
        descriptor.requiredFeatureCount = 1
        descriptor.requiredFeatures = features
    descriptor.deviceLostCallbackInfo.mode = lib.WGPUCallbackMode_AllowSpontaneous
    descriptor.deviceLostCallbackInfo.callback = lost
    descriptor.uncapturedErrorCallbackInfo.callback = error
    callback = ffi.new("WGPURequestDeviceCallbackInfo *")
    callback.mode = lib.WGPUCallbackMode_AllowProcessEvents
    callback.callback = received
    _api.libf.wgpuAdapterRequestDevice(adapter._internal, descriptor, callback[0])
    if status[0] != lib.WGPURequestDeviceStatus_Success or reply[0] == ffi.NULL:
        message = bytes(ffi.buffer(mailbox.errors, mailbox.state[1])).decode(errors="replace")
        raise RuntimeError(f"device request failed ({status[0]}): {message}")
    handle = reply[0]
    queue = _api.GPUQueue("Janim queue", _api.libf.wgpuDeviceGetQueue(handle), None)
    device = _api.GPUDevice(
        "Janim device",
        handle,
        adapter,
        _api._get_features(handle, device=True),
        _api._get_limits(handle, device=True),
        queue,
    )
    # Native callbacks outlive the wrapper GPU when a target still owns a device.
    device._uncaptured_error_callback = error
    device._device_lost_callback = lost
    return device, mailbox, (lost, error, received)


def submit(gpu, command):
    commands = ffi.new("WGPUCommandBuffer[]", [command._internal])
    return _api.libf.wgpuQueueSubmitForIndex(gpu.queue._internal, 1, commands)


def wait(gpu, index=None):
    pointer = ffi.NULL if index is None else ffi.new("WGPUSubmissionIndex *", index)
    _api.libf.wgpuDevicePoll(gpu.device._internal, True, pointer)


# ── the preview's surface ────────────────────────────────────────────────
#
# wgpu-py 0.21 builds a surface only inside GPUCanvasContext, whose policy
# (present mode by `_vsync`, opaque alpha, statuses that raise) is not the
# contract Janim needs. The surface itself comes from the binding's own helper,
# for the three surface source types (Wayland, X11 and a CAMetalLayer); configure, acquire and
# present go through the library like every other v24 call here. An acquire on
# an UNCONFIGURED surface aborts the process in v24: window.py keeps the
# `configured` flag.

SURFACE_STATUS = {
    "success_optimal": 1,
    "success_suboptimal": 2,
    "timeout": 3,
    "outdated": 4,
    "lost": 5,
    "out_of_memory": 6,
    "device_lost": 7,
    "error": 8,
}
USAGE_COPY_SRC = 1
USAGE_RENDER_ATTACHMENT = 16


def create_surface(info):
    """The surface for `{"platform", "window", "display"}` on the process's instance."""
    surface = _helpers.get_surface_id_from_info(info)
    if surface == ffi.NULL:
        raise wgpu.GPUValidationError(f"wgpuInstanceCreateSurface returned NULL on {info['platform']}")
    return surface


def surface_capabilities(surface, adapter):
    """Formats, usages, present and alpha modes; v24 returns 0 as status, the struct decides."""
    holder = ffi.new("WGPUSurfaceCapabilities *")
    _api.libf.wgpuSurfaceGetCapabilities(surface, adapter._internal, holder)
    names = _api.enum_int2str
    result = {
        "usages": int(holder.usages),
        "formats": [names["TextureFormat"][holder.formats[i]] for i in range(holder.formatCount)],
        "present_modes": [names["PresentMode"][holder.presentModes[i]].lower() for i in range(holder.presentModeCount)],
        "alpha_modes": [names["CompositeAlphaMode"][holder.alphaModes[i]].lower() for i in range(holder.alphaModeCount)],
    }
    _api.libf.wgpuSurfaceCapabilitiesFreeMembers(holder[0])
    return result


def surface_configure(surface, gpu, format_name, usage, width, height):
    """Fifo, alpha Auto, no view formats: Janim's configuration."""
    config = ffi.new("WGPUSurfaceConfiguration *")
    config.device = gpu.device._internal
    config.format = _api.enummap["TextureFormat." + format_name]
    config.usage = usage
    config.width = int(width)
    config.height = int(height)
    config.viewFormatCount = 0
    config.alphaMode = lib.WGPUCompositeAlphaMode_Auto
    config.presentMode = lib.WGPUPresentMode_Fifo
    _api.libf.wgpuSurfaceConfigure(surface, config)


def surface_unconfigure(surface):
    _api.libf.wgpuSurfaceUnconfigure(surface)


def surface_release(surface):
    _api.libf.wgpuSurfaceRelease(surface)


def surface_acquire(surface):
    """One acquire: (status, texture handle or NULL). The caller checks `configured`."""
    holder = ffi.new("WGPUSurfaceTexture *")
    _api.libf.wgpuSurfaceGetCurrentTexture(surface, holder)
    return int(holder.status), holder.texture


def surface_present(surface):
    _api.libf.wgpuSurfacePresent(surface)


def release_texture(handle):
    if handle != ffi.NULL:
        _api.libf.wgpuTextureRelease(handle)


def wrap_surface_texture(handle, gpu, format_name, width, height, usage):
    """A binding texture over the swapchain's handle; released, never destroyed."""
    info = {
        "size": (int(width), int(height), 1),
        "mip_level_count": 1,
        "sample_count": 1,
        "dimension": "2d",
        "format": format_name,
        "usage": usage,
    }
    return _api.GPUTexture("Janim surface texture", handle, gpu.device, info)
