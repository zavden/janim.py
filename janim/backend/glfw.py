"""The window system: GLFW through the pinned system library, only for a preview.

Nothing here is imported by a render to a file; importing `glfw` initialises
nothing, and the platform (Null, Wayland, X11 or Cocoa) is chosen ONCE, before the
first window.
"""

import os
from pathlib import Path
import sys
import threading
import time

LIBRARY = "/usr/lib64/libglfw.so.3"
X_LOCALE_DIRECTORY = "/usr/share/X11/locale"
FOCUS_DRAIN_CEILING = 0.25
EVENT_POLLS = 0
FOCUS_DRAINS = 0
FOCUS_DRAIN_TIMEOUTS = 0
_LOCK = threading.RLock()
_STATE = {"ready": False, "platform": "none", "null": False}
_WINDOWS = {}


class Window:
    """A GLFW window without a graphics API; `presenter` is its surface."""

    def __init__(self, handle, width, height, title, visible):
        self.handle = handle
        self.width = width
        self.height = height
        self.title = title
        self.visible = visible
        self.presenter = None
        self.callbacks = []
        self.closed = False

    @property
    def address(self):
        import ctypes

        return int(ctypes.cast(self.handle, ctypes.c_void_p).value or 0)


def _glfw():
    import glfw

    return glfw


def _headless_env():
    if os.environ.get("JANIM_HEADLESS") == "1":
        return True
    if sys.platform == "darwin":
        # Cocoa sets no DISPLAY variable; the window server is always there.
        return False
    return not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _point_xkb_at_x_locale():
    if Path(X_LOCALE_DIRECTORY, "compose.dir").is_file():
        os.environ.setdefault("XLOCALEDIR", X_LOCALE_DIRECTORY)


def ensure_window_system():
    """Initialise GLFW once on the platform the session offers; return the module."""
    with _LOCK:
        if _STATE["ready"]:
            return _glfw()
        if Path(LIBRARY).is_file():
            os.environ.setdefault("PYGLFW_LIBRARY", LIBRARY)
        import glfw

        glfw.ERROR_REPORTING = "exception"
        requested = os.environ.get("JANIM_GLFW_PLATFORM", "").lower()
        platforms = {"null": glfw.PLATFORM_NULL, "wayland": glfw.PLATFORM_WAYLAND, "x11": glfw.PLATFORM_X11}
        if sys.platform == "darwin":
            platforms = {"null": glfw.PLATFORM_NULL, "cocoa": glfw.PLATFORM_COCOA}
        if requested:
            if requested not in platforms:
                expected = ", ".join(list(platforms)[:-1]) + " or " + list(platforms)[-1]
                raise ValueError(f"JANIM_GLFW_PLATFORM={requested!r}: expected {expected}")
            platform = platforms[requested]
        elif _headless_env():
            platform = glfw.PLATFORM_NULL
        elif os.environ.get("WAYLAND_DISPLAY") and glfw.platform_supported(glfw.PLATFORM_WAYLAND):
            platform = glfw.PLATFORM_WAYLAND
        else:
            platform = None
        if platform is not None:
            glfw.init_hint(glfw.PLATFORM, platform)
        if platform != glfw.PLATFORM_NULL:
            _point_xkb_at_x_locale()
        if not glfw.init():
            raise RuntimeError(f"glfwInit failed on {glfw.get_version_string().decode()}")
        names = {glfw.PLATFORM_WAYLAND: "wayland", glfw.PLATFORM_X11: "x11", glfw.PLATFORM_COCOA: "cocoa", glfw.PLATFORM_NULL: "null"}
        _STATE["platform"] = names.get(glfw.get_platform(), "other")
        _STATE["null"] = _STATE["platform"] == "null"
        _STATE["ready"] = True
        return glfw


def window_platform():
    """`wayland`, `x11`, `cocoa`, `null`, `other` or `none` before the first window."""
    return _STATE["platform"]


def null_platform():
    return _STATE["null"]


def create_window_noapi(width, height, *, title="Janim", visible=True):
    """A window with CLIENT_API = NO_API; the three hints go on EVERY window."""
    glfw = ensure_window_system()
    glfw.window_hint(glfw.CLIENT_API, glfw.NO_API)
    glfw.window_hint(glfw.VISIBLE, bool(visible) and not _STATE["null"])
    glfw.window_hint(glfw.RESIZABLE, False)
    handle = glfw.create_window(int(width), int(height), title, None, None)
    if not handle:
        raise RuntimeError(f"glfwCreateWindow returned NULL for {width}×{height} on {_STATE['platform']}")
    window = Window(handle, int(width), int(height), title, bool(visible) and not _STATE["null"])
    _WINDOWS[window.address] = window
    return window


def native_handles(window):
    """The surface source for the platform: what the GPU seam turns into a surface."""
    glfw = _glfw()
    platform = _STATE["platform"]
    if platform == "wayland":
        return {"platform": "wayland", "window": int(glfw.get_wayland_window(window.handle)), "display": int(glfw.get_wayland_display())}
    if platform == "x11":
        return {"platform": "x11", "window": int(glfw.get_x11_window(window.handle)), "display": int(glfw.get_x11_display())}
    if platform == "cocoa":
        # The NSWindow; wgpu-py puts a CAMetalLayer on its contentView.
        return {"platform": "cocoa", "window": int(glfw.get_cocoa_window(window.handle))}
    raise ValueError(f"no surface source for the {platform} platform")


def sync_content_scale(window):
    """Cocoa: give the CAMetalLayer the window's backing scale, as GLFW does for its own Vulkan surfaces.

    wgpu-py creates the layer with contentsScale 1.0; on Retina the framebuffer
    (and the drawable) is twice the window, and the layer must say so.
    """
    if _STATE["platform"] != "cocoa":
        return False
    import ctypes

    from rubicon.objc.api import ObjCInstance

    ns_window = ObjCInstance(ctypes.c_void_p(int(_glfw().get_cocoa_window(window.handle))))
    layer = ns_window.contentView.layer
    if layer is None:
        return False
    layer.setContentsScale(ns_window.backingScaleFactor)
    return True


def framebuffer_size(window):
    """Physical pixels: on HiDPI they differ from the window's coordinates."""
    return tuple(_glfw().get_framebuffer_size(window.handle))


def poll_events():
    global EVENT_POLLS
    EVENT_POLLS += 1
    _glfw().poll_events()


def window_focused(window):
    glfw = _glfw()
    return bool(glfw.get_window_attrib(window.handle, glfw.FOCUSED))


def client_api(window):
    glfw = _glfw()
    return int(glfw.get_window_attrib(window.handle, glfw.CLIENT_API))


def should_close(window):
    return bool(_glfw().window_should_close(window.handle))


def set_title(window, title):
    if title != window.title:
        _glfw().set_window_title(window.handle, title)
        window.title = title


def drain_focus(window):
    """Hide a FOCUSED window and pump until GLFW has seen its focus leave.

    GLFW 3.4 implements key repeat on Wayland with its own timer, armed by a
    PRESS and disarmed by the RELEASE or the keyboard's leave only while the
    library has a focused window. A window destroyed while Esc is still held
    leaves the timer armed and the next poll crashes or feeds a phantom key
    to the next window. Hiding makes the leave
    happen while GLFW still knows the window. Bounded by the ceiling.
    """
    global FOCUS_DRAINS, FOCUS_DRAIN_TIMEOUTS
    if not window_focused(window):
        return False
    glfw = _glfw()
    FOCUS_DRAINS += 1
    glfw.hide_window(window.handle)
    started = time.perf_counter()
    while window_focused(window):
        if time.perf_counter() - started >= FOCUS_DRAIN_CEILING:
            FOCUS_DRAIN_TIMEOUTS += 1
            break
        glfw.wait_events_timeout(0.01)
    return True


def close_context(window):
    """Release the presenter, drain the focus, destroy, then poll once more.

    In this order: a surface that outlives its wl_surface is a use-after-free
    inside the driver's WSI; a held key must not outlive the window; and on
    Wayland glfwDestroyWindow only QUEUES the requests to the compositor, so
    one more poll flushes them.
    """
    if window is None or window.closed:
        return None
    window.closed = True
    if window.presenter is not None:
        window.presenter.release()
        window.presenter = None
    drain_focus(window)
    _glfw().destroy_window(window.handle)
    poll_events()
    _WINDOWS.pop(window.address, None)
    window.callbacks.clear()
    return None


def open_windows():
    return len(_WINDOWS)
