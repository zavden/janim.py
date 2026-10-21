"""GPU device ownership and routing: Vulkan on Linux, Metal on macOS.

The native library is the one bundled with the `wgpu` package, unless the
environment variable WGPU_LIB_PATH names another file.
"""

from collections import namedtuple
import logging
import os
from pathlib import Path
import re
import sys
import threading


NATIVE_VERSION = (24, 0)
# The one backend the instance opens: Metal on macOS, Vulkan elsewhere.
BACKEND = "Metal" if sys.platform == "darwin" else "Vulkan"
GPUInfo = namedtuple("GPUInfo", "renderer slug backend version kind")
_LOCK = threading.RLock()
_BINDING = None
_ROUTE = None
_SHARED = None


class GPUDeviceLostError(RuntimeError):
    """The device is lost; its resources must never reach the native API again."""


class _ExpectedVersionWarning(logging.Filter):
    def filter(self, record):
        return record.getMessage().strip() != (
            "Expected wgpu-native version (24, 0, 0, 2) but got (24, 0, 0, 1)."
        )


def _route():
    value = os.environ.get("JANIM_HEADLESS")
    if value is not None and value != "1":
        raise ValueError("JANIM_HEADLESS must be unset or exactly '1'")
    return value == "1", os.environ.get("JANIM_ADAPTER", "")


def _binding():
    global _BINDING, _ROUTE
    requested = _route()
    with _LOCK:
        if _BINDING is not None:
            if requested != _ROUTE:
                raise RuntimeError("the graphics route is fixed for this process")
            return _BINDING
        # The bundled native library is used unless WGPU_LIB_PATH names a file.
        library = os.environ.get("WGPU_LIB_PATH")
        if library and not Path(library).is_file():
            raise FileNotFoundError(f"WGPU_LIB_PATH does not name a file: {library}")
        os.environ.setdefault("MESA_VK_IGNORE_CONFORMANCE_WARNING", "1")
        # The wgpu package imports its canvas base internally. Preserve the
        # user's window settings: its GUI utility otherwise forces XWayland.
        window_keys = ("PYGLFW_LIBRARY_VARIANT", "QT_QPA_PLATFORM", "GDK_BACKEND")
        window_settings = {key: os.environ.get(key) for key in window_keys}
        try:
            import wgpu
        finally:
            for key, value in window_settings.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        logger = logging.getLogger("wgpu")
        warning_filter = _ExpectedVersionWarning()
        logger.addFilter(warning_filter)
        try:
            from wgpu.backends.wgpu_native import _ffi
        finally:
            logger.removeFilter(warning_filter)
        if wgpu.__version__ != "0.21.0" or tuple(_ffi.lib_version_info[:2]) != NATIVE_VERSION:
            raise RuntimeError(
                f"expected wgpu 0.21.0 / native {NATIVE_VERSION}, got "
                f"{wgpu.__version__} / {_ffi.lib_version_info}",
            )
        from wgpu.backends.wgpu_native import _api

        _validate_readback_api(_api)
        # Publish only inside this lock so native's import guard can prove it
        # passed the version check. Roll back if initialization fails.
        _BINDING = wgpu
        try:
            from . import native

            native.initialize_instance()
        except BaseException:
            _BINDING = None
            raise
        _ROUTE = requested
        return wgpu


def _validate_readback_api(api):
    method = getattr(api.GPUBuffer, "_map", None)
    code = getattr(method, "__code__", None)
    if not callable(method) or code is None or "READ_NOSYNC" not in code.co_consts:
        raise RuntimeError("the pinned readback API GPUBuffer._map(READ_NOSYNC) is missing")


def choose_adapter(adapters, *, headless=False, name=""):
    """Pick an adapter from those with the standard info fields: by name, else a CPU one when headless, else discrete, then integrated."""
    seen = "; ".join(
        f"{a.info['device']} [{a.info['adapter_type']}, {a.info['backend_type']}]"
        for a in adapters
    )
    if not adapters:
        raise RuntimeError(f"no {BACKEND} adapter is available")
    if name:
        for adapter in adapters:
            if name.lower() in adapter.info["device"].lower():
                return adapter
        raise ValueError(f"JANIM_ADAPTER={name!r} matches none of: {seen}")
    if headless:
        for adapter in adapters:
            if adapter.info["adapter_type"] == "CPU":
                return adapter
        raise RuntimeError(f"JANIM_HEADLESS=1 requires a CPU adapter; adapters: {seen}")
    for kind in ("DiscreteGPU", "IntegratedGPU"):
        for adapter in adapters:
            if adapter.info["adapter_type"] == kind:
                return adapter
    return next((a for a in adapters if a.info["adapter_type"] != "CPU"), adapters[0])


def _adapter():
    _binding()
    from .native import enumerate_adapters

    adapters = enumerate_adapters()
    return choose_adapter(adapters, headless=_ROUTE[0], name=_ROUTE[1])


def _info(adapter):
    info = adapter.info
    vendor = re.sub("[^A-Za-z0-9]", "", info["vendor"]).lower()
    words = info["device"].strip().split()
    fallback = re.sub("[^A-Za-z0-9]", "", words[0]).lower() if words else "unknown"
    kinds = {"DiscreteGPU": "discrete", "IntegratedGPU": "integrated", "CPU": "cpu"}
    return GPUInfo(
        info["device"],
        vendor or fallback or "unknown",
        info["backend_type"].lower(),
        info["description"] or info["architecture"] or "unknown",
        kinds.get(info["adapter_type"], "unknown"),
    )


def gpu_info(gpu=None):
    """Report renderer, slug, backend, driver version and adapter kind."""
    return gpu.info if gpu is not None else _info(_adapter())


def driver_header(info=None):
    info = gpu_info() if info is None else info
    return f"# driver: {info.slug} · {info.backend} · {info.version}"


renderer_info = gpu_info


class GPU:
    def __init__(self):
        self.closed = False
        self.dead = False
        self._owner = threading.get_ident()
        self.adapter = _adapter()
        self.info = _info(self.adapter)
        from .native import request_device

        self.device, self._mailbox, self._callbacks = request_device(self.adapter)
        self.queue = self.device.queue
        self.features = tuple(sorted(self.device.features))

    def check(self):
        if self.closed:
            raise _binding().GPUValidationError("the GPU is closed")
        if self.dead:
            raise GPUDeviceLostError("the GPU device is lost")
        if threading.get_ident() != self._owner:
            raise RuntimeError("graphics operations must run on the device's owner thread")
        self._mailbox.check(self)

    def submit(self, command):
        self.check()
        from .native import submit

        index = submit(self, command)
        self.check()
        return index

    def wait(self, index=None):
        self.check()
        from .native import wait

        wait(self, index)
        self.check()

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.device.destroy()

    def __enter__(self):
        self.check()
        return self

    def __exit__(self, *_):
        self.close()


def _shared_gpu():
    global _SHARED
    with _LOCK:
        _binding()
        if _SHARED is None or _SHARED.closed or _SHARED.dead:
            from .render import _clear_shared_vms

            _clear_shared_vms()
            if _SHARED is not None:
                _SHARED.close()
            _SHARED = GPU()
        return _SHARED
