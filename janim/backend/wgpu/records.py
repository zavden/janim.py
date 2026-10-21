"""Persistent source mirrors and vertex spans."""

from dataclasses import dataclass, field

import numpy as np

from janim.backend.expanded import ARRAY_NAMES, DEFER, ELEMENT_BYTES, batched_joint_angles, expanded_data, max_sqrt_area, stroke_collapses
from .context import _binding
from .uniforms import gpu_buffer, write_buffer


SOURCE_FIELDS = ("points", "stroke_rgba", "fill_rgba", "stroke_width")
JOINT_SLOT = ARRAY_NAMES.index("joint_angle")
IMAGE_UV = np.array(((0, 0), (0, 1), (1, 0), (1, 1)), dtype=np.float32)


def source_signature(array):
    return array.dtype, array.shape, array.tobytes()


def source_rows(mobject):
    return (
        source_signature(mobject.points),
        source_signature(mobject.stroke_rgba),
        source_signature(mobject.fill_rgba),
        source_signature(mobject.stroke_width),
    )


# Two dirty spans of one arena buffer closer than this (in vertices) are
# uploaded as one write: the bytes between them are the shadow's, which are
# the buffer's, so the merged write changes nothing but the number of calls.
MERGE_GAP = 4096


class VertexArena:
    """The vertex buffers of every run, with a CPU shadow of each one.

    A write lands in the shadow and marks its span dirty, and `flush` (the end
    of the draw list, before recording) uploads each buffer's dirty spans in a
    handful of calls, instead of one `write_buffer` call per member and per
    array (six per changed member, eight with a gradient: some six thousand
    per frame of a thousand turning dots). The GPU buffers hold the same bytes
    at the same offsets before the same submit; only `upload_calls` moves."""

    def __init__(self, gpu, stats, *, capacity=12288, sizes=ELEMENT_BYTES, granule=3, label="Janim vertex arena", index=False):
        self.gpu, self.stats = gpu, stats
        self.sizes, self.granule, self.label, self.index = tuple(sizes), granule, label, index
        self.capacity = capacity + (-capacity % granule)
        self.generation = 1         # new buffers at every growth: a recorded bundle no longer binds them
        self.buffers = self._buffers(self.capacity)
        self.shadow = [np.zeros(self.capacity * size, dtype=np.uint8) for size in self.sizes]
        self.dirty = [[] for _ in self.sizes]
        self.free = [(0, self.capacity)]
        self.pending = []
        self.retired = []
        self.recorded = False

    def _buffers(self, capacity):
        usage = _binding().BufferUsage
        return [
            gpu_buffer(
                self.gpu,
                self.stats,
                capacity * size,
                (usage.INDEX if self.index else usage.VERTEX) | usage.COPY_DST | usage.COPY_SRC,
                self.label,
            )
            for size in self.sizes
        ]

    def allocate(self, count):
        if count % self.granule:
            raise ValueError("vertex spans must contain whole quadratic triples")
        if count == 0:
            return 0
        while True:
            for i, (offset, length) in enumerate(self.free):
                if length >= count:
                    if length == count:
                        self.free.pop(i)
                    else:
                        self.free[i] = offset + count, length - count
                    return offset
            # Recorded passes retain the old buffers. Copy into new storage
            # on the queue and retire the old references until submission.
            # The pending spans reach the old buffers first, so the copy
            # carries them, exactly as the per-member writes did.
            self.flush()
            old_capacity = self.capacity
            new_capacity = max(2 * old_capacity, old_capacity + count)
            new = self._buffers(new_capacity)
            encoder = self.gpu.device.create_command_encoder(label="Janim arena growth")
            for old, buffer, size in zip(self.buffers, new, self.sizes):
                encoder.copy_buffer_to_buffer(old, 0, buffer, 0, old_capacity * size)
            self.gpu.submit(encoder.finish())
            self.retired.extend(self.buffers)
            self.buffers = new
            self.capacity = new_capacity
            self.generation += 1
            self.shadow = [
                np.concatenate((shadow, np.zeros((new_capacity - old_capacity) * size, dtype=np.uint8)))
                for shadow, size in zip(self.shadow, self.sizes)
            ]
            self.free.append((old_capacity, new_capacity - old_capacity))
            self._coalesce()

    def release(self, offset, count):
        if count:
            self.pending.append((offset, count))

    def _coalesce(self):
        merged = []
        for offset, length in sorted(self.free):
            if merged and merged[-1][0] + merged[-1][1] == offset:
                begin, previous = merged[-1]
                merged[-1] = begin, previous + length
            else:
                merged.append((offset, length))
        self.free = merged

    def drain(self):
        self.recorded = False
        if self.pending:
            self.free.extend(self.pending)
            self.pending.clear()
            self._coalesce()
        self.retired.clear()

    @property
    def used(self):
        return self.capacity - sum(n for _, n in self.free) - sum(n for _, n in self.pending)

    def write(self, offset, data):
        """Stage one member's arrays at vertex `offset`: into the shadow, span marked dirty.

        `upload_bytes` and `geometry_bytes` count what the member wrote; the
        calls are counted by `flush`."""
        count = data["n"]
        if not count:
            return
        stats = self.stats
        for index, (name, size) in enumerate(zip(ARRAY_NAMES, ELEMENT_BYTES)):
            array = data[name]
            if array is None:
                continue
            start = offset * size
            nbytes = array.nbytes
            self.shadow[index][start:start + nbytes] = np.ascontiguousarray(array).view(np.uint8).reshape(-1)
            self.dirty[index].append((offset, offset + count))
            stats.upload_bytes += nbytes
            stats.geometry_bytes += nbytes

    def write_slot(self, offset, index, array):
        """Stage one array (by slot) of a member whose other arrays are already
        staged: the deferred joints land in the shadow like the rest."""
        size = self.sizes[index]
        start = offset * size
        nbytes = array.nbytes
        self.shadow[index][start:start + nbytes] = np.ascontiguousarray(array).view(np.uint8).reshape(-1)
        self.dirty[index].append((offset, offset + nbytes // size))
        self.stats.upload_bytes += nbytes
        self.stats.geometry_bytes += nbytes

    def flush(self):
        """Upload every dirty span, merging the ones closer than MERGE_GAP; one queue write per span."""
        for index, spans in enumerate(self.dirty):
            if not spans:
                continue
            spans.sort()
            size = self.sizes[index]
            buffer, shadow = self.buffers[index], self.shadow[index]
            begin, end = spans[0]
            for start, stop in spans[1:]:
                if start - end <= MERGE_GAP:
                    end = max(end, stop)
                    continue
                self._upload(buffer, shadow, size, begin, end)
                begin, end = start, stop
            self._upload(buffer, shadow, size, begin, end)
            spans.clear()

    def _upload(self, buffer, shadow, size, begin, end):
        self.gpu.queue.write_buffer(buffer, begin * size, shadow[begin * size:end * size])
        self.stats.upload_calls += 1
        self.stats.flush_bytes += (end - begin) * size

    def close(self):
        self.buffers.clear()
        self.shadow.clear()
        for spans in self.dirty:
            spans.clear()
        self.retired.clear()
        self.pending.clear()
        self.free.clear()


@dataclass
class Mirror:
    rows: tuple
    generation: int
    last_pass: int
    fill: bool
    stroke: bool
    runs: list = field(default_factory=list)


@dataclass
class RunRecord:
    members: tuple
    gradient: object
    base: int
    n: int
    offsets: list
    counts: list
    generations: list
    fills: list
    strokes: list
    sqrt_area: list
    last_pass: int
    step_frame_unit: object = None
    step_vertices: int = 0
    commands: tuple = ()          # last frame's draw commands, valid under `commands_key`
    commands_key: object = None   # (uniform block, depth test, frame unit) they were built for


@dataclass
class MeshRecord:
    store: object               # the MeshStore of its kind
    offset: int                 # its first vertex (instance, for dots) in the store
    count: int                  # vertices (instances) it holds
    index_offset: int           # its first index in the store's index arena (indexed kinds)
    index_count: int            # indices it draws; 0 for a kind without an index buffer
    mirrors: list
    index_signature: object
    last_pass: int
    block_key: object = None      # what the uniform block was built from
    block_bytes: bytes = b""      # the block, serialised once per key
    command: object = None        # last frame's draw command, reused while block, counts and texture agree


class MeshStore:
    """The arrays of every mesh of one kind in shared buffers: one arena per array with a
    shadow and merged uploads, like the runs', and for the indexed kinds one index
    arena whose entries are stored REBASED by the mesh's vertex offset, so the recorder
    draws consecutive meshes of one state with one `draw_indexed`."""

    SIZES = {"dots": (12, 4, 16), "surface": (12, 12, 16), "image": (12, 8), "textured_surface": (12, 12, 8)}
    INDEXED = ("surface", "textured_surface")

    def __init__(self, gpu, stats, kind, *, capacity=4096):
        if kind not in self.SIZES:
            raise ValueError(f"unknown mesh kind: {kind}")
        self.kind = kind
        self.vertices = VertexArena(gpu, stats, capacity=capacity, sizes=self.SIZES[kind], granule=1, label=f"Janim {kind} arena")
        self.indices = None
        if kind in self.INDEXED:
            self.indices = VertexArena(gpu, stats, capacity=2 * capacity, sizes=(4,), granule=1, label=f"Janim {kind} indices", index=True)

    @property
    def generation(self):
        return self.vertices.generation + (0 if self.indices is None else self.indices.generation)

    def release(self, record):
        self.vertices.release(record.offset, record.count)
        if self.indices is not None:
            self.indices.release(record.index_offset, record.index_count)

    def flush(self):
        self.vertices.flush()
        if self.indices is not None:
            self.indices.flush()

    def drain(self):
        self.vertices.drain()
        if self.indices is not None:
            self.indices.drain()

    def close(self):
        self.vertices.close()
        if self.indices is not None:
            self.indices.close()


class DrawCache:
    def __init__(self, gpu, stats, arena):
        self.gpu, self.stats, self.arena = gpu, stats, arena
        self.mirrors = {}
        self.meshes = {}
        self.stores = {}         # one MeshStore per mesh kind, made on first use
        self.pass_index = 0
        self.pending = []
        self.ephemeral = []
        self.disabled = False
        self.deferred = []       # (vertex offset, expanded part) whose joints one atan2 resolves

    def expand(self, mob, gradient):
        """A member's arrays; the joints of a stroke the shader reads are deferred to `finish_joints`."""
        if stroke_collapses(mob):
            return expanded_data(mob, grad=gradient, joints=False)
        return expanded_data(mob, grad=gradient, joints=DEFER)

    def stage(self, offset, part):
        self.arena.write(offset, part)
        if part["joint_vectors"] is not None:
            self.deferred.append((offset, part))

    def finish_joints(self):
        """One `atan2` for every deferred member of the frame, then its slot of the arena."""
        if not self.deferred:
            return
        angles = batched_joint_angles([(y, x, len(y) // 2) for _, (y, x) in ((offset, part["joint_vectors"]) for offset, part in self.deferred)])
        for (offset, part), member in zip(self.deferred, angles):
            self.arena.write_slot(offset, JOINT_SLOT, member[part["indices"]])
        self.deferred.clear()

    def sync(self, mob):
        mirror = self.mirrors.get(mob)
        if mirror is not None and mirror.last_pass == self.pass_index:
            return mirror
        self.stats.mirror_checks += 1
        rows = source_rows(mob)
        if mirror is None or mirror.rows != rows:
            has_fill = bool(np.any(mob.fill_rgba[:, 3] > 0))
            has_stroke = bool(np.any(mob.stroke_width > 0) and np.any(mob.stroke_rgba[:, 3] > 0))
            if mirror is None:
                mirror = Mirror(rows, 1, self.pass_index, has_fill, has_stroke)
                self.mirrors[mob] = mirror
            else:
                mirror.rows = rows
                mirror.generation += 1
                mirror.fill, mirror.stroke = has_fill, has_stroke
        mirror.last_pass = self.pass_index
        return mirror

    def poison_mirror(self, mob):
        self.mirrors[mob].rows = source_rows(mob)

    def build(self, members, gradient, mirrors):
        data = [self.expand(mob, gradient) for mob in members]
        counts = [part["n"] for part in data]
        offsets = []
        n = 0
        for count in counts:
            offsets.append(n)
            n += count
        base = self.arena.allocate(n)
        for offset, part in zip(offsets, data):
            self.stage(base + offset, part)
        return RunRecord(
            tuple(members),
            gradient,
            base,
            n,
            offsets,
            counts,
            [mirror.generation for mirror in mirrors],
            [gradient is not None or mirror.fill for mirror in mirrors],
            [mirror.stroke for mirror in mirrors],
            [max_sqrt_area(part["point"]) for part in data],
            self.pass_index,
        )

    def run(self, members, gradient):
        head = self.sync(members[0])
        if not self.disabled and len(members) == 1:
            for record in head.runs:
                if len(record.members) == 1 and record.gradient is gradient and record.generations[0] == head.generation:
                    record.last_pass = self.pass_index
                    return record
        mirrors = [head, *(self.sync(mob) for mob in members[1:])]
        existing = None
        if not self.disabled:
            for record in head.runs:
                if len(record.members) == len(members) and all(a is b for a, b in zip(
                    record.members,
                    members,
                )):
                    existing = record
                    break
        counts = [3 * mob.get_num_curves() for mob in members]
        if existing is None or existing.gradient is not gradient or existing.counts != counts:
            record = self.build(members, gradient, mirrors)
            if self.disabled:
                self.ephemeral.append(record)
            elif existing is None:
                head.runs.append(record)
            else:
                self.arena.release(existing.base, existing.n)
                head.runs[head.runs.index(existing)] = record
        else:
            record = existing
            for i, (mob, mirror) in enumerate(zip(members, mirrors)):
                if record.generations[i] != mirror.generation:
                    data = self.expand(mob, gradient)
                    self.stage(record.base + record.offsets[i], data)
                    record.generations[i] = mirror.generation
                    record.fills[i] = gradient is not None or mirror.fill
                    record.strokes[i] = mirror.stroke
                    record.sqrt_area[i] = max_sqrt_area(data["point"])
                    record.step_frame_unit = None
                    record.commands_key = None
        record.last_pass = self.pass_index
        return record

    def store(self, kind):
        store = self.stores.get(kind)
        if store is None:
            store = self.stores[kind] = MeshStore(self.gpu, self.stats, kind)
        return store

    def store_generation(self):
        """Moves whenever a mesh store grew: its buffers are new ones."""
        return sum(store.generation for store in self.stores.values())

    def flush_meshes(self):
        for store in self.stores.values():
            store.flush()

    def mesh(self, mob):
        kind = mob.render_kind
        arrays = [mob.points]
        if kind == "dots":
            arrays.extend((mob.radii, mob.rgba))
        elif kind == "image":
            arrays.append(IMAGE_UV)
        else:
            arrays.extend((mob.d_normal_points, mob.rgba if kind == "surface" else mob.uv))
        store = self.stores.get(kind)
        if store is None:
            store = self.store(kind)
        index = mob.indices if store.indices is not None else None
        count = len(arrays[0])
        index_count = 0 if index is None else index.size
        record = None if self.disabled else self.meshes.get(mob)
        if record is None or record.count != count or record.index_count != index_count:
            if record is not None:
                store.release(record)
            for array, size in zip(arrays, store.vertices.sizes):
                if array.nbytes != count * size:
                    raise TypeError(f"a {kind} mesh needs float32 arrays of one row per vertex")
            record = MeshRecord(
                store,
                store.vertices.allocate(count),
                count,
                store.indices.allocate(index_count) if store.indices is not None else 0,
                index_count,
                [None] * len(arrays),
                None,
                self.pass_index,
            )
            if self.disabled:
                self.ephemeral.append(record)
            else:
                self.meshes[mob] = record
        for i, array in enumerate(arrays):
            signature = source_signature(array)
            if signature != record.mirrors[i]:
                store.vertices.write_slot(record.offset, i, array)
                record.mirrors[i] = signature
        if index is not None:
            signature = source_signature(index)
            if signature != record.index_signature:
                if index.dtype.kind not in "iu" or index.dtype.itemsize != 4 or index.nbytes != 4 * index_count:
                    raise TypeError("mesh indices must be 32-bit integers")
                store.indices.write_slot(record.index_offset, 0, index.astype(np.uint32, copy=False) + np.uint32(record.offset))
                record.index_signature = signature
        record.last_pass = self.pass_index
        return record

    def sweep(self):
        cutoff = self.pass_index - 8
        for mob, mirror in list(self.mirrors.items()):
            keep = []
            for record in mirror.runs:
                if record.last_pass < cutoff:
                    self.arena.release(record.base, record.n)
                else:
                    keep.append(record)
            mirror.runs = keep
            if mirror.last_pass < cutoff and not keep:
                del self.mirrors[mob]
        for mob, record in list(self.meshes.items()):
            if record.last_pass < cutoff:
                record.store.release(self.meshes.pop(mob))

    def after_submit(self):
        for record in self.ephemeral:
            if isinstance(record, RunRecord):
                self.arena.release(record.base, record.n)
            else:
                record.store.release(record)
        self.ephemeral.clear()
        self.pending.clear()
        self.arena.drain()
        for store in self.stores.values():
            store.drain()

    def close(self):
        self.mirrors.clear()
        self.meshes.clear()
        for store in self.stores.values():
            store.close()
        self.stores.clear()
        self.pending.clear()
        self.ephemeral.clear()
        self.deferred.clear()


class TextureCache:
    def __init__(self, gpu, stats, layout, sampler):
        self.gpu, self.stats, self.layout, self.sampler = gpu, stats, layout, sampler
        self.entries = {}
        self.pending = []

    def get(self, pixels, *, ramp=False):
        key = id(pixels)
        if key in self.entries:
            return self.entries[key][3]
        if len(self.entries) >= 64:
            self.pending.extend(self.entries.values())
            self.entries.clear()
        if ramp:
            if pixels.dtype != np.float32 or pixels.size != 4096:
                raise ValueError("a gradient ramp needs 1024 float32 RGBA texels")
            width, height, size, format = 1024, 1, 16, "rgba32float"
        else:
            if pixels.dtype != np.uint8 or pixels.ndim != 3 or pixels.shape[2] != 4:
                raise ValueError("texture pixels must be a (height, width, 4) uint8 array")
            height, width = pixels.shape[:2]
            size, format = 4, "rgba8unorm"
        texture = self.gpu.device.create_texture(
            label="Janim ramp" if ramp else "Janim texture",
            size=(width, height, 1),
            format=format,
            usage=_binding().TextureUsage.TEXTURE_BINDING | _binding().TextureUsage.COPY_DST,
        )
        view = texture.create_view()
        self.gpu.queue.write_texture(
            {"texture": texture},
            pixels,
            {"bytes_per_row": size * width, "rows_per_image": height},
            (width, height, 1),
        )
        group = self.gpu.device.create_bind_group(
            label="Janim texture bind group",
            layout=self.layout,
            entries=[{"binding": 0, "resource": view}, {"binding": 1, "resource": self.sampler}],
        )
        self.stats.objects += 3
        self.stats.upload_calls += 1
        self.stats.upload_bytes += pixels.nbytes
        self.stats.texture_bytes += pixels.nbytes
        self.entries[key] = pixels, texture, view, group
        return group

    def close(self):
        self.entries.clear()
        self.pending.clear()
        self.layout = self.sampler = None
