"""Linear layer composition."""

from contextlib import contextmanager
import operator
from pathlib import Path

import numpy as np

from janim.core.colorspace import decode_premult_srgb
from janim.core.compositor_types import (
    BLEND_MODES,
    Blur,
    Composition,
    focus_composition,
    resolved_camera,
    validate_composition,
    window_destination,
    window_source,
)
from janim.core.effects_types import tick_effects
from .context import _binding
from .pipelines import assemble
from .render import FrameTarget
from .targets import GPUTarget
from .triangle import compile_wgsl
from .uniforms import ParamArena, QUAD_DTYPE, quad_params
from .effects import apply_effect


_QUAD_ENTRIES = ("comb", "blur", "copy", "saturate", "mask", "bright", "add2", "decode", "final", "zoom", "window")
_EFFECT_ENTRIES = ("glitch", "crt", "vhs", "color", "pixelate", "vignette", "grain", "chroma", "sharpen", "wave", "edge")
_USER_SHADERS = {}
_USER_GENERATION = 0


def effect_shader(entry, fragment):
    """Register a fragment named fs_<entry>; a later registration replaces it."""
    global _USER_GENERATION

    if not isinstance(entry, str) or not isinstance(fragment, str):
        raise TypeError("effect_shader requires an entry name and fragment source strings")
    if entry in (*_QUAD_ENTRIES, *_EFFECT_ENTRIES):
        raise ValueError(f"{entry!r} is a built-in effect entry; choose another name")
    if "fs_" + entry not in fragment:
        raise ValueError(f"the fragment must define fn fs_{entry}(in: QuadOut)")
    directory = Path(__file__).with_name("shaders") / "inserts"
    source = "".join(
        (
        f"// ── {name} ──\n" + (directory / name).read_text() + "\n"
        for name in ("quad_common.wgsl", "noise.wgsl", "straight.wgsl")
        ),
    ) + fragment
    _USER_GENERATION += 1
    _USER_SHADERS[entry] = source, _USER_GENERATION
    return entry


class GPUCompositor:
    def __init__(self, rv, *, samples=None):
        rv._check_open("setup compositor")
        self.rv, self.gpu = rv, rv.gpu
        self.width, self.height = rv.width, rv.height
        self.samples = rv.samples if samples is None else (operator.index(samples) or 4)
        if self.samples != rv.samples:
            raise ValueError("compositor and render VM must use the same sample count")
        self.closed = False
        self.slots = [
            GPUTarget(
                self.gpu,
                self.width,
                self.height,
                format="rgba16float",
                depth=index == 2,
            )
            for index in range(9)
        ]
        self.ms = GPUTarget(
            self.gpu,
            self.width,
            self.height,
            depth=True,
            samples=4,
            format="rgba16float",
        ) if self.samples == 4 else None
        binding = _binding()
        self.sampler = self.gpu.device.create_sampler(
            label="Janim compositor nearest",
            address_mode_u="repeat",
            address_mode_v="repeat",
            address_mode_w="clamp-to-edge",
            mag_filter="nearest",
            min_filter="nearest",
            mipmap_filter="nearest",
            lod_min_clamp=0.0,
            lod_max_clamp=32.0,
            max_anisotropy=1,
        )
        self.sampler_linear = self.gpu.device.create_sampler(
            label="Janim compositor linear",
            address_mode_u="repeat",
            address_mode_v="repeat",
            address_mode_w="clamp-to-edge",
            mag_filter="linear",
            min_filter="linear",
            mipmap_filter="nearest",
            lod_min_clamp=0.0,
            lod_max_clamp=32.0,
            max_anisotropy=1,
        )
        self.layout = self.gpu.device.create_bind_group_layout(
            label="Janim quad layout",
            entries=[
                {"binding": 0, "visibility": binding.ShaderStage.FRAGMENT, "texture": {"sample_type": "float", "view_dimension": "2d"}},
                {"binding": 1, "visibility": binding.ShaderStage.FRAGMENT, "texture": {"sample_type": "float", "view_dimension": "2d"}},
                {"binding": 2, "visibility": binding.ShaderStage.FRAGMENT, "sampler": {"type": "filtering"}},
                {"binding": 3, "visibility": binding.ShaderStage.VERTEX | binding.ShaderStage.FRAGMENT, "buffer": {"type": "uniform", "has_dynamic_offset": True, "min_binding_size": QUAD_DTYPE.itemsize}},
            ],
        )
        self.pipeline_layout = self.gpu.device.create_pipeline_layout(bind_group_layouts=[self.layout])
        self.params = ParamArena(self.gpu, rv.stats, QUAD_DTYPE, capacity=256, label="Janim quad params")
        self.module = compile_wgsl(self.gpu, assemble("quad.wgsl"), label="Janim compositor")
        self.modules = {"quad": self.module}
        self.user_generations = {}
        self.referee = None
        self.ppu = self.width / (8.0 * 16 / 9)
        self.pipelines = {}
        self.bind_groups = {}
        self.encoder = None
        self.live = []
        self.frames = self.quads = self.submits = 0
        rv.stats.objects += 24 if self.ms is None else 28

    def _check_open(self, what="operation"):
        if self.closed:
            raise _binding().GPUValidationError(f"the compositor is closed before {what}")
        self.rv._check_open(what)
        self.rv.target._check_open(what)

    def _begin(self):
        if self.encoder is not None:
            raise RuntimeError("the compositor's previous frame was never ended")
        self.rv.arena.reset()
        self.rv.frame_ring.reset()
        self.params.reset()
        self.encoder = self.gpu.device.create_command_encoder(label="Janim composition")

    def _submit(self):
        self.rv.arena.upload()
        self.rv.frame_ring.upload()
        self.params.upload()
        command = self.encoder.finish()
        self.encoder = None
        self.gpu.submit(command)
        self.rv.after_submit()
        self.params.recorded = False
        self.submits += 1

    def _abort(self):
        self.encoder = None
        self.live.clear()
        self.rv.after_submit()
        self.rv.arena.reset()
        self.rv.frame_ring.reset()
        self.params.recorded = False
        self.params.reset()

    def _flush(self):
        self._submit()
        self._begin()

    def _scratch(self, *busy):
        for index in (3, 0, 2, 4, 5):
            if index not in busy and index not in self.live:
                return index
        raise RuntimeError("no compositor scratch surface is available")

    @contextmanager
    def _keep(self, *indices):
        previous = len(self.live)
        self.live.extend(indices)
        try:
            yield
        finally:
            del self.live[previous:]

    def _shader(self, name):
        user = _USER_SHADERS.get(name)
        if user is not None and name in self.modules and self.user_generations.get(name) != user[1]:
            for key in tuple(self.pipelines):
                if key[0] == name:
                    del self.pipelines[key]
            del self.modules[name]
        if name not in self.modules:
            source = assemble(name + ".wgsl") if user is None else user[0]
            self.modules[name] = compile_wgsl(self.gpu, source, label="Janim " + name)
            self.rv.stats.objects += 1
            if user is not None:
                self.user_generations[name] = user[1]
        return self.modules[name]

    def _pipeline(self, entry, format):
        if entry in _QUAD_ENTRIES:
            module_name = "quad"
        elif entry in _EFFECT_ENTRIES:
            module_name = "effects"
        elif entry in _USER_SHADERS:
            module_name = entry
        else:
            raise ValueError(f"no quad entry named {entry!r}; register it with effect_shader first")
        module = self._shader(module_name)
        key = entry, format
        if key not in self.pipelines:
            self.pipelines[key] = self.gpu.device.create_render_pipeline(
                label="Janim quad " + entry,
                layout=self.pipeline_layout,
                vertex={"module": module, "entry_point": "vs_window" if entry == "window" else "vs_quad", "buffers": []},
                primitive={"topology": "triangle-strip", "front_face": "ccw", "cull_mode": "none"},
                multisample={"count": 1, "mask": 0xffffffff, "alpha_to_coverage_enabled": False},
                fragment={"module": module, "entry_point": "fs_" + entry, "targets": [{"format": format, "write_mask": 15}]},
            )
            self.rv.stats.objects += 1
        return self.pipelines[key]

    def _bind_group(self, first, second, linear=False):
        key = first, second, linear
        if key not in self.bind_groups:
            self.bind_groups[key] = self.gpu.device.create_bind_group(
                label="Janim quad textures",
                layout=self.layout,
                entries=[
                    {"binding": 0, "resource": self.slots[first].view},
                    {"binding": 1, "resource": self.slots[second].view},
                    {"binding": 2, "resource": self.sampler_linear if linear else self.sampler},
                    {"binding": 3, "resource": {"buffer": self.params.buffer, "offset": 0, "size": QUAD_DTYPE.itemsize}},
                ],
            )
            self.rv.stats.objects += 1
        return self.bind_groups[key]

    def _quad(self, entry, destination, first, second=None, params=None, *, linear=False):
        second = first if second is None else second
        target = self.slots[destination] if isinstance(destination, int) else destination
        target._check_open("quad pass")
        if isinstance(destination, int) and destination in (first, second):
            raise ValueError("a quad cannot read and write the same surface")
        if not self.params.has_room():
            self._flush()
        slot = self.params.push(quad_params() if params is None else params)
        pipeline = self._pipeline(entry, target.format)
        bind_group = self._bind_group(first, second, linear)
        render = self.encoder.begin_render_pass(
            color_attachments=[{
                "view": target.view,
                "resolve_target": None,
                "clear_value": (0, 0, 0, 0),
                "load_op": "clear",
                "store_op": "store",
            }],
        )
        try:
            render.set_pipeline(pipeline)
            render.set_bind_group(0, bind_group, [slot * self.params.stride])
            render.draw(4, 1, 0, 0)
        finally:
            render.end()
        self.params.recorded = True
        self.quads += 1
        self.rv.stats.passes += 1
        self.rv.stats.draws += 1
        return destination

    def _clear(self, slot, color):
        render = self.encoder.begin_render_pass(
            color_attachments=[{
                "view": self.slots[slot].view,
                "resolve_target": None,
                "clear_value": tuple(map(float, color)),
                "load_op": "clear",
                "store_op": "store",
            }],
        )
        render.end()
        self.rv.stats.passes += 1

    def _content(self, mobjects, camera, destination, flip_y):
        while True:
            if not self.rv.frame_ring.has_room():
                self._flush()
            before = self.rv.arena.n
            frame_before = self.rv.frame_ring.n
            frame_slot = self.rv.prepare(mobjects or (), camera, flip_y=not flip_y)
            needed = self.rv.arena.n
            if needed <= self.rv.arena.capacity:
                break
            self.rv.arena.n = before
            self.rv.frame_ring.n = frame_before
            self._flush()
            self.rv.arena.n = 2 * (needed - before)
            self.rv.arena.ensure_capacity()
            self.rv.arena.reset()
        target = self.ms if self.ms is not None else self.slots[destination]
        depth = self.ms.depth_view if self.ms is not None else self.slots[2].depth_view
        descriptor = FrameTarget(
            target.view,
            depth,
            self.slots[destination].view if self.ms is not None else None,
            self.samples,
            "rgba16float",
            frame_slot,
            target,
        )
        self.rv._record_frame(self.encoder, (0, 0, 0, 0), descriptor)

    def _content_layer(self, content, camera, flip_y):
        self._content(content, camera, 2, flip_y)
        return self._quad("decode", self._scratch(2), 2)

    def _blur_hv(self, current, radius, weights):
        temporary = self._scratch(current)
        self._quad(
            "blur",
            temporary,
            current,
            params=quad_params(f0=(1 / self.width, 0), i0=(radius,), w=weights),
        )
        self._quad(
            "blur",
            current,
            temporary,
            params=quad_params(f0=(0, 1 / self.height), i0=(radius,), w=weights),
        )
        return current

    def _blur_to(self, source, radius, weights):
        with self._keep(source):
            horizontal = self._scratch(source)
            self._quad(
                "blur",
                horizontal,
                source,
                params=quad_params(f0=(1 / self.width, 0), i0=(radius,), w=weights),
            )
            vertical = self._scratch(source, horizontal)
            return self._quad(
                "blur",
                vertical,
                horizontal,
                params=quad_params(f0=(0, 1 / self.height), i0=(radius,), w=weights),
            )

    def _mask(self, mask, current, camera, flip_y):
        with self._keep(current):
            self._content(mask.content, camera, 1, flip_y)
            masked = self._quad("decode", self._scratch(1), 1)
            self.ppu = camera.width / camera.frame_width
            if mask.feather > 0:
                masked = apply_effect(Blur(mask.feather), self, masked)
            with self._keep(masked):
                return self._quad(
                    "mask",
                    self._scratch(current),
                    current,
                    masked,
                    quad_params(i0=(mask.luma, mask.invert, mask.hard)),
                )

    def _window(self, layer, current, camera, layer_camera, flip_y):
        destination = window_destination(camera, layer.window, flip_y=flip_y)
        if destination is None:
            self._clear(6, (0, 0, 0, 0))
            return 6
        source = window_source(self.width, self.height, layer_camera, destination)
        return self._quad(
            "window",
            6,
            current,
            params=quad_params(f0=destination, f1=source),
            linear=True,
        )

    def _accumulators(self, depth):
        first = 7 + 2 * depth
        while len(self.slots) < first + 2:
            self.slots.append(GPUTarget(self.gpu, self.width, self.height, format="rgba16float"))
            self.rv.stats.objects += 2
        return first, first + 1

    def _layer(self, layer, camera, flip_y, depth):
        layer_camera = resolved_camera(layer, camera)
        if isinstance(layer.content, Composition):
            current = self._compose(layer.content, layer_camera, flip_y, depth + 1)
        else:
            current = self._content_layer(layer.content, layer_camera, flip_y)
        # A nested composition may have changed ppu to an inner camera.
        self.ppu = layer_camera.width / layer_camera.frame_width
        for effect in layer.effects:
            current = apply_effect(effect, self, current)
        if layer.window is not None:
            current = self._window(layer, current, camera, layer_camera, flip_y)
        if layer.mask is not None:
            current = self._mask(layer.mask, current, camera, flip_y)
        return current

    def _compose(self, composition, camera, flip_y, depth=0):
        pair = self._accumulators(depth)
        accumulator = pair[0]
        self._clear(accumulator, decode_premult_srgb(composition.background))
        index = 0
        while index < len(composition.layers):
            layer = composition.layers[index]
            if layer.content is None:
                self.ppu = camera.width / camera.frame_width
                current = accumulator
                with self._keep(*pair):
                    for effect in layer.effects:
                        current = apply_effect(effect, self, current)
                if current != accumulator:
                    self._quad("copy", accumulator, current)
                index += 1
                continue
            current = self._layer(layer, camera, flip_y, depth)
            if layer.matte is not None:
                matte = composition.layers[index + 1]
                if current == 2:
                    current = self._quad("copy", self._scratch(2), 2)
                with self._keep(current):
                    masked = self._content_layer(matte.content, resolved_camera(matte, camera), flip_y)
                    with self._keep(masked):
                        current = self._quad(
                            "mask",
                            self._scratch(current),
                            current,
                            masked,
                            quad_params(i0=(layer.matte in ("luma", "luma_inv"), layer.matte in ("alpha_inv", "luma_inv"), 0)),
                        )
                index += 1
            other = pair[1] if accumulator == pair[0] else pair[0]
            self._quad(
                "comb",
                other,
                accumulator,
                current,
                quad_params(f0=(layer.opacity,), i0=(BLEND_MODES[layer.blend],)),
            )
            accumulator = other
            index += 1
        return accumulator

    def draw(self, composition, camera, *, flip_y=True, frame=0):
        self._check_open("draw")
        if (camera.width, camera.height) != (self.width, self.height):
            raise ValueError("composition camera resolution must match the render VM")
        validate_composition(composition)
        focus_composition(composition, camera)
        tick_effects(composition, frame)
        self.live.clear()
        self._begin()
        try:
            accumulator = self._compose(composition, camera, flip_y)
            self._quad(
                "final",
                self.rv.target,
                accumulator,
                params=quad_params(f0=decode_premult_srgb(camera.background), i0=(1,)),
            )
            self._submit()
            self.gpu.check()
            self.frames += 1
        except BaseException:
            self._abort()
            raise
        return self.rv

    def read_layer_rgba(self, layer, camera=None, *, frame=0):
        """Read straight RGBA in bottom-first row order."""
        from janim.core.camera import Camera
        from .targets import read_rgba_topdown

        self._check_open("read_layer_rgba")
        camera = Camera(width=self.width, height=self.height) if camera is None else camera
        if (camera.width, camera.height) != (self.width, self.height):
            raise ValueError("layer camera resolution must match the compositor")
        tick_effects(layer, frame)
        self.ppu = camera.width / camera.frame_width
        if self.referee is None:
            self.referee = GPUTarget(self.gpu, self.width, self.height)
            self.rv.stats.objects += 2
        self.live.clear()
        self._begin()
        try:
            current = self._layer(layer, camera, False, 0)
            self._quad("final", self.referee, current, params=quad_params(i0=(0,)))
            self._submit()
            self.gpu.check()
            self.frames += 1
        except BaseException:
            self._abort()
            raise
        raw = read_rgba_topdown(self.gpu, self.referee)
        return np.frombuffer(raw, dtype=np.uint8).reshape(self.height, self.width, 4).copy()

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.encoder = None
        self.bind_groups.clear()
        self.pipelines.clear()
        self.params.close()
        self.modules.clear()
        self.user_generations.clear()
        self.module = self.pipeline_layout = self.layout = self.sampler = self.sampler_linear = None
        if self.referee is not None:
            self.referee.close()
        for slot in self.slots:
            slot.close()
        if self.ms is not None:
            self.ms.close()
        self.slots.clear()

    def __enter__(self):
        self._check_open()
        return self

    def __exit__(self, *_):
        self.close()


def setup_compositor(rv, *, samples=None):
    return GPUCompositor(rv, samples=samples)


def render_composition(composition, camera, *, rv, cg=None, flip_y=False, frame=0):
    """Render one composition to a top-down RGB array through the chosen route."""
    if cg is None:
        with setup_compositor(rv) as compositor:
            return render_composition(composition, camera, rv=rv, cg=compositor, flip_y=flip_y, frame=frame)
    if cg.rv is not rv:
        raise ValueError("the compositor belongs to another render VM")
    cg.draw(composition, camera, flip_y=flip_y, frame=frame)
    pixels = rv.read()
    return pixels if flip_y else pixels[::-1].copy()


def read_layer_rgba(layer, camera=None, *, rv, cg=None, frame=0):
    """Read a layer's straight RGBA with row zero at the bottom."""
    if cg is None:
        with setup_compositor(rv) as compositor:
            return compositor.read_layer_rgba(layer, camera, frame=frame)
    if cg.rv is not rv:
        raise ValueError("the compositor belongs to another render VM")
    return cg.read_layer_rgba(layer, camera, frame=frame)
