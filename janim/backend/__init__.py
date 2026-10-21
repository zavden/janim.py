"""Rendering backends, loaded only when requested."""


_WINDOW_EXPORTS = (
    "close_context",
    "window_platform",
    "ensure_window_system",
    "framebuffer_size",
    "poll_events",
)


def __getattr__(name):
    # This imports our own implementation, never the graphics binding.
    if name in _WINDOW_EXPORTS:
        from . import glfw as window_system

        return getattr(window_system, name)
    from .wgpu import resolve_export

    return resolve_export(name)
