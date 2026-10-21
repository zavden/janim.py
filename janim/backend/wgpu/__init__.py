"""The production boundary for the pinned graphics API and its shaders."""


def resolve_export(name):
    from importlib import import_module

    modules = {
        "gpu_info": "context",
        "driver_header": "context",
        "renderer_info": "context",
        "render_solid_frame": "targets",
        "render_two_band_frame": "targets",
        "render_frame": "render",
        "render_mobjects": "render",
        "setup_render_vm": "render",
        "FramePipeline": "pipeline",
        "setup_compositor": "compositor",
        "render_composition": "compositor",
        "read_layer_rgba": "compositor",
        "effect_shader": "compositor",
        "apply_effect": "effects",
        "create_window": "window",
        "present": "window",
        "presenter": "window",
        "blit_image": "window",
        "paint_strip": "window",
        "read_frame_into": "window",
        "write_target": "window",
        "GPUPresenter": "window",
        "present_readback": "window",
    }
    if name not in modules:
        raise AttributeError(name)
    return getattr(import_module(f"{__name__}.{modules[name]}"), name)
