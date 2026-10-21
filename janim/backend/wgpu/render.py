"""One-pass static rendering."""

from dataclasses import dataclass
import operator

import numpy as np

from janim.backend.expanded import ELEMENT_BYTES, RenderMesh, batch_key, step_budget
from janim.core.camera import Camera, camera_uniforms
from janim.core.gradients import active_fill_gradient, fill_gradient_opacity
from janim.core.mobject import Mobject, VMobject
from janim.png import save_rgb_png
from .context import _binding, _shared_gpu
from .pipelines import PipelineCache
from .records import DrawCache, RunRecord, TextureCache, VertexArena
from .targets import GPUTarget, create_staging, padded_bytes_per_row, read_rgb_topdown, read_rgba_topdown
from .uniforms import (
    FRAME_DTYPE,
    ParamArena,
    RenderStats,
    UniformArena,
    frame_uniforms,
    mobject_uniforms,
    texture_layout,
    uniform_layout,
)


_DISABLE_DRAW_BATCH = False
_DISABLE_DRAW_CACHE = False
JOINT_CODES = {"no_joint": 0, "auto": 1, "bevel": 2, "miter": 3}


@dataclass
class FrameTarget:
    view: object
    depth_view: object
    resolve: object
    samples: int
    format: str
    frame_slot: int = 0
    owner: object = None


@dataclass
class RecordedList:
    """The commands a pass recorded, by identity: the caches hand back the same objects while
    nothing they depend on changed, and the list keeps them alive so no id is reused."""

    ids: list
    key: tuple
    commands: list


@dataclass
class FrameBundle(RecordedList):
    bundle: object
    counts: tuple           # the draws, block binds and arena binds one execution carries


RECORD_NAMES = ("SetPipeline", "SetBindGroup", "SetVertexBuffer", "SetIndexBuffer", "Draw", "DrawIndexed")


@dataclass(frozen=True)
class DrawCommand:
    """One draw of a frame. Frozen: the caches hand the same object back frame after frame
    and the recorder trusts identity, so a change is always a new command."""

    kind: str
    depth: bool
    z_pass: bool
    block: int
    record: object
    vertices: int
    instances: int
    first: int = 0
    texture: object = None


def draw_order(mobjects):
    roots = list(dict.fromkeys(mobjects))
    return sorted(roots, key=lambda mob: mob.z_index) if any(mob.z_index != 0 for mob in roots) else roots


class GPURenderVM:
    def __init__(self, gpu, width, height, *, samples=0):
        samples = operator.index(samples)
        if samples not in (0, 1, 4):
            raise ValueError(f"samples={samples}: expected 0 (default 4), 1 or 4")
        gpu.check()
        if "float32-filterable" not in gpu.features:
            raise RuntimeError("the device lacks float32-filterable for gradient ramps")
        self.gpu = gpu
        self.closed = False
        self.samples = samples or 4
        self.stats = RenderStats()
        self.target = GPUTarget(gpu, width, height, depth=True)
        self.width, self.height = self.target.width, self.target.height
        self.ms = GPUTarget(gpu, width, height, depth=True, samples=4) if self.samples == 4 else None
        self.stats.objects += 4 if self.ms is None else 8
        self.layout_frame = uniform_layout(gpu, self.stats, 112, "Janim frame layout")
        self.layout_mob = uniform_layout(gpu, self.stats, 64, "Janim mobject layout")
        self.layout_tex = texture_layout(gpu, self.stats)
        layout = gpu.device.create_pipeline_layout(bind_group_layouts=[self.layout_frame, self.layout_mob])
        layout_tex = gpu.device.create_pipeline_layout(bind_group_layouts=[self.layout_frame, self.layout_mob, self.layout_tex])
        self.stats.objects += 2
        self.pipelines = PipelineCache(gpu, self.stats, layout, layout_tex)
        self.frame_ring = ParamArena(
            gpu,
            self.stats,
            FRAME_DTYPE,
            capacity=64,
            label="Janim frame uniforms",
            layout=self.layout_frame,
        )
        self.arena = UniformArena(gpu, self.stats, self.layout_mob)
        self.varena = VertexArena(gpu, self.stats)
        self.cache = DrawCache(gpu, self.stats, self.varena)
        self.sampler = gpu.device.create_sampler(
            label="Janim sampler",
            address_mode_u="clamp-to-edge",
            address_mode_v="clamp-to-edge",
            address_mode_w="clamp-to-edge",
            mag_filter="linear",
            min_filter="linear",
            mipmap_filter="nearest",
            lod_min_clamp=0.0,
            lod_max_clamp=32.0,
            max_anisotropy=1,
        )
        self.stats.objects += 1
        self.textures = TextureCache(gpu, self.stats, self.layout_tex, self.sampler)
        self.ramps = TextureCache(gpu, self.stats, self.layout_tex, self.sampler)
        self.commands = []
        self.staging = None
        self.scratch = None
        self._last_uniform_key = None
        self._last_uniform_slot = None
        # The recording loop calls the library directly: the binding's
        # method plus its error-capturing proxy cost more than the call for
        # commands that wgpu-core only validates when the pass ends. One
        # preallocated dynamic offset serves every bind.
        from wgpu.backends.wgpu_native import _api
        from wgpu.backends.wgpu_native._ffi import ffi, lib

        self._lib = lib
        self._offset_ref = ffi.new("uint32_t[1]")
        self._null = ffi.NULL
        self._index_uint32 = _api.enummap["IndexFormat.uint32"]
        self._function_sets = {}
        # The second frame in a row with the same commands records them once into a
        # render bundle, and the frames after it execute the bundle instead of recording.
        self._previous = None
        self._bundle = None

    def _check_open(self, what="operation"):
        if self.closed:
            raise _binding().GPUValidationError(f"the render VM is closed before {what}")
        self.gpu.check()

    def _draw_run(self, run, camera, *, gradient=None):
        record = self.cache.run(run, gradient)
        self.stats.runs += 1
        if not record.n:
            return
        first = run[0]
        if gradient is not None:
            self._draw_gradient_run(record, first, camera, gradient)
            return
        uniform_key = (
            first.uniforms["shading"].tobytes(),
            first.uniforms["is_fixed_in_frame"],
            first.joint_type,
        )
        if uniform_key == self._last_uniform_key:
            block = self._last_uniform_slot
        else:
            block = self.arena.push(mobject_uniforms(
                shading=first.uniforms["shading"],
                is_fixed_in_frame=first.uniforms["is_fixed_in_frame"],
                joint_type=JOINT_CODES[first.joint_type],
            ))
            self._last_uniform_key = uniform_key
            self._last_uniform_slot = block
        # The commands of a record depend on its block, its depth test and the frame unit
        # of its step budget alone: a record nobody restaged hands back last frame's tuple.
        strokes = any(record.strokes)
        frame_unit = (np.float32(1) if first.uniforms["is_fixed_in_frame"] else camera["frame_scale"]) if strokes else None
        key = (block, first.depth_test, frame_unit)
        if record.commands_key == key:
            self.commands.extend(record.commands)
            return
        commands = []
        if any(record.fills):
            for offset, count, fill in zip(record.offsets, record.counts, record.fills):
                if not fill or not count:
                    continue
                start = (record.base + offset) // 3
                commands.append(DrawCommand("stencil", False, False, block, record, 6, count // 3, start))
                commands.append(DrawCommand("cover", first.depth_test, False, block, record, 6, count // 3, start))
        if strokes:
            if record.step_frame_unit != frame_unit:
                record.step_vertices = 6 * (step_budget(record.sqrt_area, frame_unit) - 1)
                record.step_frame_unit = frame_unit
            vertices = record.step_vertices
            if first.depth_test:
                commands.append(DrawCommand("stroke", True, True, block, record, vertices, record.n // 3, record.base // 3))
            commands.append(DrawCommand("stroke", first.depth_test, False, block, record, vertices, record.n // 3, record.base // 3))
        record.commands = tuple(commands)
        record.commands_key = key
        self.commands.extend(commands)

    def _draw_gradient_run(self, record, first, camera, gradient):
        """A run under a fill gradient: its block carries the gradient, so it is pushed every
        frame; the commands are cached like any other run's, keyed by the ramp too."""
        opacity = fill_gradient_opacity(first)
        block = self.arena.push(mobject_uniforms(
            shading=first.uniforms["shading"],
            is_fixed_in_frame=first.uniforms["is_fixed_in_frame"],
            joint_type=JOINT_CODES[first.joint_type],
            grad_focus=(*gradient.focus, 0),
            grad_kind=float(gradient.kind == "radial"),
            spread_mode=gradient.spread,
            grad_opacity=opacity,
        ))
        self._last_uniform_key = None
        self._last_uniform_slot = block
        fills = bool(any(record.fills) and opacity != 0)
        strokes = any(record.strokes)
        texture = self.ramps.get(gradient.ramp, ramp=True) if fills else None
        frame_unit = (np.float32(1) if first.uniforms["is_fixed_in_frame"] else camera["frame_scale"]) if strokes else None
        key = (block, first.depth_test, frame_unit, fills, texture)
        if record.commands_key == key:
            self.commands.extend(record.commands)
            return
        commands = []
        if fills:
            for offset, count, fill in zip(record.offsets, record.counts, record.fills):
                if not fill or not count:
                    continue
                start = (record.base + offset) // 3
                commands.append(DrawCommand("stencil_grad", False, False, block, record, 6, count // 3, start))
                commands.append(DrawCommand("cover_grad", first.depth_test, False, block, record, 6, count // 3, start, texture))
        if strokes:
            if record.step_frame_unit != frame_unit:
                record.step_vertices = 6 * (step_budget(record.sqrt_area, frame_unit) - 1)
                record.step_frame_unit = frame_unit
            vertices = record.step_vertices
            if first.depth_test:
                commands.append(DrawCommand("stroke", True, True, block, record, vertices, record.n // 3, record.base // 3))
            commands.append(DrawCommand("stroke", first.depth_test, False, block, record, vertices, record.n // 3, record.base // 3))
        record.commands = tuple(commands)
        record.commands_key = key
        self.commands.extend(commands)

    def _draw_mesh(self, mob):
        kind = mob.render_kind
        if kind in ("surface", "textured_surface") and not len(mob.indices):
            return
        record = self.cache.mesh(mob)
        if not record.count:
            return
        # The uniform block of a mesh is serialised once per key and pushed as bytes; the
        # command is last frame's while its block, its counts and its texture agree.
        texture = None
        if kind == "surface":
            key = (kind, mob.uniforms["is_fixed_in_frame"], mob.uniforms["shading"].tobytes())
        elif kind == "dots":
            key = (kind, mob.uniforms["is_fixed_in_frame"], mob.uniforms["shading"].tobytes(), mob.anti_alias_width, mob.glow_factor)
        else:
            texture = self.textures.get(mob.pixels)
            key = (kind, mob.uniforms["is_fixed_in_frame"], None if kind == "image" else mob.uniforms["shading"].tobytes(), mob.opacity)
        if record.block_key != key:
            values = {"is_fixed_in_frame": mob.uniforms["is_fixed_in_frame"]}
            if kind != "image":
                values["shading"] = mob.uniforms["shading"]
            if kind == "dots":
                values.update(anti_alias_width=mob.anti_alias_width, glow_factor=mob.glow_factor)
            if kind in ("image", "textured_surface"):
                values["opacity"] = mob.opacity
            record.block_bytes = mobject_uniforms(**values).tobytes()
            record.block_key = key
            record.command = None
        block = self.arena.push_bytes(record.block_bytes)
        # `first` is the mesh's place in its store: the first instance of a dot cloud, the
        # first vertex of an image, the first (rebased) index of a surface.
        if kind == "dots":
            vertices, instances, first = 6, record.count, record.offset
        elif kind == "image":
            vertices, instances, first = 4, 1, record.offset
        else:
            vertices, instances, first = record.index_count, 1, record.index_offset
        command = record.command
        if (
            command is None
            or command.block != block
            or command.depth != mob.depth_test
            or command.vertices != vertices
            or command.instances != instances
            or command.first != first
            or command.texture is not texture
        ):
            command = DrawCommand(kind, mob.depth_test, False, block, record, vertices, instances, first, texture)
            record.command = command
        self.commands.append(command)

    def _draw_list(self, mobjects, camera):
        self.cache.pass_index += 1
        self.cache.disabled = _DISABLE_DRAW_CACHE
        run = []
        key = None

        def flush():
            if run:
                self._draw_run(run, camera)
                run.clear()

        for root in draw_order(mobjects):
            for mob in root._draw_family():
                if getattr(mob, "render_kind", None) in ("dots", "surface", "image", "textured_surface"):
                    # Only a primitive that draws can split a run.
                    if not len(mob.points) or mob.render_kind in ("surface", "textured_surface") and not len(mob.indices):
                        continue
                    flush()
                    key = None
                    self._draw_mesh(mob)
                    continue
                if not isinstance(mob, VMobject) or not len(mob.points):
                    continue
                gradient = active_fill_gradient(mob)
                if gradient is not None or mob.depth_test or _DISABLE_DRAW_BATCH:
                    flush()
                    key = None
                    self._draw_run([mob], camera, gradient=gradient)
                    continue
                new_key = batch_key(mob)
                if new_key != key:
                    flush()
                    key = new_key
                run.append(mob)
            flush()
            key = None
        if self.cache.pass_index % 64 == 0:
            self.cache.sweep()

    def prepare(self, mobjects, camera, *, flip_y=False):
        self._check_open("prepare")
        if (camera.width, camera.height) != (self.width, self.height):
            raise ValueError("camera resolution must match the render VM")
        if not self.frame_ring.has_room():
            raise RuntimeError("the frame uniform ring is full: flush before preparing a frame")
        self.commands.clear()
        self._last_uniform_key = None
        self._last_uniform_slot = None
        values = camera_uniforms(camera, flip_y=flip_y)
        self._draw_list(mobjects, values)
        # the deferred joints reach the arena's shadow before the flush uploads it
        self.cache.finish_joints()
        self.varena.flush()
        self.cache.flush_meshes()
        return self.frame_ring.push(frame_uniforms(values))

    def scene_target(self, slot=0):
        self._check_open("frame target")
        self.target._check_open("frame target")
        target = self.target if self.ms is None else self.ms
        target._check_open("multisample frame target")
        return FrameTarget(
            target.view,
            target.depth_view,
            None if self.ms is None else self.target.view,
            self.samples,
            "rgba8unorm",
            slot,
            self,
        )

    def _functions(self, encoder):
        """The six recording functions of one encoder type of the library, looked up once."""
        functions = self._function_sets.get(encoder)
        if functions is None:
            functions = tuple(getattr(self._lib, f"wgpu{encoder}{name}") for name in RECORD_NAMES)
            self._function_sets[encoder] = functions
        return functions

    def _record_commands(self, encoder_id, functions, frame_slot, commands, pipelines):
        """The frame's commands onto a pass or a bundle encoder: the same calls through that
        encoder's functions. Returns the draws, block binds and arena binds it made.

        A mesh store's buffers are bound once per stretch of its meshes, and consecutive
        meshes of one store, pipeline, block and texture whose spans follow each other draw
        as one call: the same triangles in the same order, one `draw_indexed` or, for
        dot clouds, one instanced `draw`. An image is a strip of its own and never merges."""
        set_pipeline, set_bind_group, set_vertex_buffer, set_index_buffer, draw, draw_indexed = functions
        offset_ref, null, index_uint32 = self._offset_ref, self._null, self._index_uint32
        offset_ref[0] = frame_slot * self.frame_ring.stride
        set_bind_group(encoder_id, 0, self.frame_ring.bind_group._internal, 1, offset_ref)
        mobject_group, stride = self.arena.bind_group._internal, self.arena.stride
        arena_slots = [(slot, buffer._internal, self.varena.capacity * size) for slot, (buffer, size) in enumerate(zip(self.varena.buffers, ELEMENT_BYTES))]
        draws = block_binds = arena_binds = merged = 0
        last_pipeline = last_texture = None
        last_block = -1
        bound = None            # the vertex arena (True), a mesh store, or nothing
        total = len(commands)
        i = 0
        while i < total:
            command, pipeline = commands[i], pipelines[i]
            i += 1
            if pipeline is not last_pipeline:
                set_pipeline(encoder_id, pipeline._internal)
                last_pipeline = pipeline
            if command.block != last_block:
                offset_ref[0] = command.block * stride
                set_bind_group(encoder_id, 1, mobject_group, 1, offset_ref)
                last_block = command.block
                block_binds += 1
            if command.texture is not None and command.texture is not last_texture:
                set_bind_group(encoder_id, 2, command.texture._internal, 0, null)
                last_texture = command.texture
            record = command.record
            draws += 1
            if isinstance(record, RunRecord):
                if bound is not True:
                    for slot, buffer, size in arena_slots:
                        set_vertex_buffer(encoder_id, slot, buffer, 0, size)
                    bound = True
                    arena_binds += 1
                draw(encoder_id, command.vertices, command.instances, 0, command.first)
                continue
            store = record.store
            if bound is not store:
                vertices = store.vertices
                for slot, (buffer, size) in enumerate(zip(vertices.buffers, vertices.sizes)):
                    set_vertex_buffer(encoder_id, slot, buffer._internal, 0, vertices.capacity * size)
                if store.indices is not None:
                    set_index_buffer(encoder_id, store.indices.buffers[0]._internal, index_uint32, 0, store.indices.capacity * 4)
                bound = store
            kind = command.kind
            if kind == "image":
                draw(encoder_id, 4, 1, command.first, 0)
                continue
            first, count = command.first, command.vertices if store.indices is not None else command.instances
            while i < total:
                following = commands[i]
                if (
                    following.kind != kind
                    or pipelines[i] is not pipeline
                    or following.block != command.block
                    or following.texture is not command.texture
                    or following.first != first + count
                ):
                    break
                count += following.vertices if store.indices is not None else following.instances
                draws += 1
                merged += 1
                i += 1
            if store.indices is not None:
                draw_indexed(encoder_id, count, 1, first, 0, 0)
            else:
                draw(encoder_id, 6, count, 0, first)
        self.stats.merged_draws += merged
        return draws, block_binds, arena_binds

    def _count(self, counts):
        draws, block_binds, arena_binds = counts
        self.stats.draws += draws
        self.stats.block_binds += block_binds
        self.stats.arena_binds += arena_binds

    def _build_bundle(self, commands, ids, key, target):
        """The second frame in a row with the same commands records them once into a bundle
        that the frames after it execute. A buffer recreated behind the commands (a growth of
        either arena, or a mesh that outgrew its buffer: that one is a new command object) or
        a target of another shape retires it; a device without bundles records every frame."""
        create = getattr(self.gpu.device, "create_render_bundle_encoder", None)
        if create is None:
            return None
        pipelines = [
            self.pipelines.get(cmd.kind, cmd.depth, cmd.z_pass, target.samples, target.format)
            for cmd in commands
        ]
        encoder = create(
            label="Janim frame bundle",
            color_formats=[target.format],
            depth_stencil_format="depth24plus-stencil8",
            sample_count=target.samples,
        )
        counts = self._record_commands(encoder._internal, self._functions("RenderBundleEncoder"), target.frame_slot, commands, pipelines)
        self._bundle = FrameBundle(ids, key, list(commands), encoder.finish(label="Janim frame bundle"), counts)
        self.stats.bundles += 1
        return self._bundle

    def _record_frame(self, encoder, clear, target):
        self._check_open("record frame")
        if target.owner is not None and hasattr(target.owner, "_check_open"):
            target.owner._check_open("record frame target")
        commands = self.commands
        ids = list(map(id, commands))
        key = (target.samples, target.format, target.frame_slot, self.varena.generation, self.arena.generation, self.cache.store_generation())
        bundle = None
        if self._bundle is not None and self._bundle.key == key and self._bundle.ids == ids:
            bundle = self._bundle
        elif ids and self._previous is not None and self._previous.key == key and self._previous.ids == ids:
            bundle = self._build_bundle(commands, ids, key, target)
        self._previous = RecordedList(ids, key, list(commands))
        if bundle is None:
            # Create pipelines before opening a pass, so validation failures
            # leave no half-open render pass behind.
            pipelines = [
                self.pipelines.get(cmd.kind, cmd.depth, cmd.z_pass, target.samples, target.format)
                for cmd in commands
            ]
        render = encoder.begin_render_pass(
            color_attachments=[{
                "view": target.view,
                "resolve_target": target.resolve,
                "clear_value": tuple(map(float, clear)),
                "load_op": "clear",
                "store_op": "discard" if target.resolve is not None else "store",
            }],
            depth_stencil_attachment={
                "view": target.depth_view,
                "depth_clear_value": 1.0,
                "depth_load_op": "clear",
                "depth_store_op": "discard" if target.samples > 1 else "store",
                "stencil_clear_value": 0,
                "stencil_load_op": "clear",
                "stencil_store_op": "discard",
            },
        )
        self.stats.passes += 1
        self.arena.recorded = self.frame_ring.recorded = self.varena.recorded = True
        try:
            if bundle is not None:
                render.execute_bundles([bundle.bundle])
                self._count(bundle.counts)
                self.stats.bundle_replays += 1
            else:
                self._count(self._record_commands(render._internal, self._functions("RenderPassEncoder"), target.frame_slot, commands, pipelines))
        finally:
            # If end() also fails, it replaces the first exception's type;
            # Python preserves the original exception in __context__.
            render.end()

    def after_submit(self):
        self.cache.after_submit()
        self.textures.pending.clear()
        self.ramps.pending.clear()
        self.arena.recorded = self.frame_ring.recorded = False

    def draw_scene(self, mobjects, camera, *, flip_y=False):
        self._check_open("draw scene")
        self.frame_ring.reset()
        self.arena.reset()
        try:
            slot = self.prepare(mobjects, camera)
            self.arena.upload()
            self.frame_ring.upload()
            encoder = self.gpu.device.create_command_encoder(label="Janim frame")
            self._record_frame(encoder, camera.background, self.scene_target(slot))
            index = self.gpu.submit(encoder.finish())
        finally:
            self.after_submit()
        self.gpu.check()
        return index

    def read(self, *, rgba=False):
        self._check_open("readback")
        if self.staging is None:
            self.staging = create_staging(self.gpu, padded_bytes_per_row(self.width) * self.height)
            self.stats.objects += 1
        read = read_rgba_topdown if rgba else read_rgb_topdown
        try:
            pixels = read(self.gpu, self.target, staging=self.staging)
        except BaseException:
            # Cancel a pending map while its exception still retains the
            # callback; a later read allocates a fresh staging buffer.
            self.staging.destroy()
            self.staging = None
            raise
        return np.frombuffer(pixels, dtype=np.uint8).reshape(self.height, self.width, 4 if rgba else 3)

    def close(self, *, targets=True):
        if self.closed:
            return
        self.closed = True
        self.commands.clear()
        self._bundle = self._previous = None
        self.cache.close()
        self.textures.close()
        self.ramps.close()
        self.pipelines.close()
        self.arena.close()
        self.frame_ring.close()
        self.varena.close()
        self.staging = self.sampler = None
        self.layout_frame = self.layout_mob = self.layout_tex = None
        if targets:
            self.target.close()
            if self.ms is not None:
                self.ms.close()

    def __enter__(self):
        self._check_open()
        return self

    def __exit__(self, *_):
        self.close()


def setup_render_vm(width, height, *, gpu=None, samples=0):
    return GPURenderVM(_shared_gpu() if gpu is None else gpu, width, height, samples=samples)


_SHARED_VMS = {}


def _clear_shared_vms():
    for rv in _SHARED_VMS.values():
        rv.close()
    _SHARED_VMS.clear()


def render_mobjects(mobjects, camera=None, *, rv=None, samples=0):
    camera = Camera() if camera is None else camera
    if isinstance(mobjects, Mobject):
        mobjects = [mobjects]
    if rv is None:
        gpu = _shared_gpu()
        key = camera.width, camera.height, operator.index(samples)
        rv = _SHARED_VMS.get(key)
        if rv is None or rv.closed or rv.gpu is not gpu:
            if rv is not None:
                rv.close()
            rv = setup_render_vm(camera.width, camera.height, gpu=gpu, samples=samples)
            _SHARED_VMS[key] = rv
    rv.draw_scene(mobjects, camera)
    return rv.read()


def render_frame(mobjects, *, resolution=(854, 480), camera=None, png=None, samples=0):
    camera = Camera(width=resolution[0], height=resolution[1]) if camera is None else camera
    pixels = render_mobjects(mobjects, camera, samples=samples)
    if png is not None:
        save_rgb_png(png, camera.width, camera.height, pixels)
    return pixels


def _record_frame(encoder, rv, clear, target):
    return rv._record_frame(encoder, clear, target)


def draw_scene(rv, mobjects, camera, *, flip_y=False):
    return rv.draw_scene(mobjects, camera, flip_y=flip_y)
