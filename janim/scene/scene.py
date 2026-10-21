"""Manim-facing Scene with a fixed clock and a four-act lifecycle."""

import math
import operator
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import warnings

import numpy as np

from janim.animation.animation import check_duration, prepare_animation
from janim.animation.camera import CameraFrame
from janim.animation.composition import AnimationGroup, leaf_animations
from janim.core.camera import Camera
from janim.core.mobject import Mobject, VMobject
from janim.png import dimensions, save_png
from .progress import RenderProgress


def family_lookup(mobjects):
    result = {}
    for mob in mobjects:
        if not isinstance(mob, Mobject):
            raise TypeError(f"scene roots must be Mobjects, got {type(mob).__name__}")
        result[mob] = None
        result.update(dict.fromkeys(mob.get_family()))
    return result


def without_family(roots, gone):
    # Mark affected ancestors once, then flatten only those containers. Two
    # iterative passes avoid recursion depth and repeated family scans.
    affected = {}
    pending = [(root, False) for root in reversed(roots)]
    while pending:
        mob, ready = pending.pop()
        if mob in affected:
            continue
        if mob in gone:
            affected[mob] = True
        elif ready:
            affected[mob] = any(affected[child] for child in mob.submobjects)
        else:
            pending.append((mob, True))
            pending.extend((child, False) for child in reversed(mob.submobjects))
    result = []
    pending = list(reversed(roots))
    while pending:
        mob = pending.pop()
        if mob in gone:
            continue
        if affected[mob]:
            pending.extend(reversed(mob.submobjects))
        else:
            result.append(mob)
    return list(dict.fromkeys(result))


def selection(value, name):
    if value is None:
        return value
    if isinstance(value, range):
        if value.step != 1 or value.start < 1 or value.stop <= value.start:
            raise ValueError(f"{name} needs a nonempty range starting at 1 or later with step 1")
        return value
    if isinstance(value, int):
        first, last = value, sys.maxsize
    else:
        if len(value) != 2:
            raise ValueError(f"{name} needs an inclusive (first, last) pair")
        first, last = value
        last = sys.maxsize if last is None else last
    first, last = operator.index(first), operator.index(last)
    if first < 1 or last < first:
        raise ValueError(f"{name} needs 1 <= first <= last")
    return range(first, last + 1)


class Scene:
    samples = 0
    default_frame_orientation = None
    always_depth_test = False

    def __init__(
        self,
        *,
        output=None,
        fps=60,
        resolution=(1920, 1080),
        samples=None,
        transparent=False,
        crf=23,
        preset="medium",
        encoder_threads=None,
        anim_range=None,
        frame_range=None,
        progress="auto",
        context=None,
        ffmpeg="ffmpeg",
        environment=None,
        frame_tap=None,
        io_timeout=30.0,
        finish_timeout=None,
        composition=None,
        preview=False,
    ):
        if isinstance(fps, bool):
            raise ValueError("fps must be a positive integer")
        self.fps = operator.index(fps)
        if not 0 < self.fps <= sys.maxsize:
            raise ValueError("fps must be a positive integer")
        width, height = dimensions(*resolution)
        self.samples = operator.index(type(self).samples if samples is None else samples)
        if self.samples not in (0, 1, 4):
            raise ValueError("samples must be 0 (default 4), 1 or 4")
        self.transparent = bool(transparent)
        self.camera = Camera(width=width, height=height, background=(0, 0, 0, 0 if transparent else 1))
        self.frame = CameraFrame(self.camera)
        # ManimGL's `self.camera.fps`, `.frame_rate`, `.frame` and `.background_color`
        # (read at construction in GL, a plain attribute afterwards)
        self.camera.fps = fps
        self.camera.frame_rate = fps
        self.camera.frame = self.frame
        self.camera.background_color = "#000000"
        if self.default_frame_orientation is not None:
            self.frame.reorient(*self.default_frame_orientation)
        self.mobjects = [self.frame]
        self.t = 0.0
        self.frames = 0
        self.frames_drawn = 0
        self.last_alphas = []
        self.anim_index = 0
        self.anim_starts = []
        self.anim_range = selection(anim_range, "anim_range")
        self.frame_range = selection(frame_range, "frame_range")
        self.capture_t = self.capture_img = self.capture_txt = None
        self.frame_hook = None
        self.skipping = False
        self.skip_until = None
        # `--from label` without a snapshot simulates the prefix and draws
        # from the marker on: a gate on the DRAWING.
        self.draw_from = None
        self.checkpoint_frames = []
        self.scene_path = ""
        self.scene_name = type(self).__name__
        self.sounds = []
        self.rv = None
        self.pipeline = None
        self.composition = None
        self.cg = None
        self.preview = bool(preview)
        self.window = None
        self._clock = None
        self.borrowed = context is not None
        if context is not None:
            self.rv = context[1] if isinstance(context, tuple) else context
            if (self.rv.width, self.rv.height) != (width, height):
                raise ValueError("context resolution must match the scene")
        self.output = None if output is None else Path(output)
        self.rendered_path = self.output
        self.closed = False
        self._owner = threading.get_ident()
        self._active_play = False
        self._in_update = False
        self._ran = False
        if composition is not None:
            self.use_composition(composition)
        self._pipeline_options = {
            "fps": self.fps,
            "crf": crf,
            "preset": preset,
            "encoder_threads": encoder_threads,
            "ffmpeg": ffmpeg,
            "environment": environment,
            "tap": frame_tap,
            "io_timeout": io_timeout,
            "finish_timeout": finish_timeout,
        }
        if progress == "auto":
            self.progress = RenderProgress(sys.stderr) if output is not None and sys.stderr.isatty() else None
        elif isinstance(progress, bool):
            self.progress = RenderProgress(sys.stderr) if progress else None
        else:
            self.progress = progress
        if self.preview and context is None:
            # Two sinks: a visible window mirrors what is written,
            # or shows the fixed clock paced to real time when nothing is.
            from janim.backend import create_window

            self.window = create_window(width, height, title="Janim", visible=True)
            try:
                self._ensure_renderer()
            except BaseException:
                self._close_window()
                raise
        if self.output is not None:
            try:
                self._open_output()
            except BaseException:
                if self.rv is not None and not self.borrowed:
                    self.rv.close()
                self._close_window()
                self.closed = True
                raise

    @property
    def time(self):
        return self.t

    @property
    def num_plays(self):
        return self.anim_index

    def get_time(self):
        return self.t

    def get_mobjects(self):
        return list(self.mobjects)

    def get_mobject_family_members(self):
        return list(family_lookup(self.mobjects))

    def _check_open(self):
        if self.closed:
            raise RuntimeError("the scene is closed")
        if threading.get_ident() != self._owner:
            raise RuntimeError("scene operations belong to their creating thread")

    def _adopt_thread(self):
        """Make the calling thread the owner: the live playhead runs construct apart."""
        self._owner = threading.get_ident()
        return self

    def _close_window(self):
        if self.window is not None and not self.borrowed:
            from janim.backend import close_context

            close_context(self.window)
        self.window = None

    def _check_schedule(self):
        self._check_open()
        if self._active_play or self._in_update:
            raise RuntimeError("cannot schedule a scene recursively during an animation or updater")

    def add(self, *mobjects, recurse=True):
        self._check_open()
        gone = family_lookup(mobjects)
        if self.always_depth_test:
            for mob in mobjects:
                mob.apply_depth_test()
        roots = without_family(self.mobjects, gone) if recurse else list(self.mobjects)
        roots.extend(mobjects)
        self.mobjects[:] = dict.fromkeys(roots)
        return self

    def remove(self, *mobjects, recurse=True):
        self._check_open()
        gone = family_lookup(mobjects) if recurse else dict.fromkeys(mobjects)
        roots = without_family(self.mobjects, gone) if recurse else [mob for mob in self.mobjects if mob not in gone]
        self.mobjects[:] = roots
        if recurse and self.composition is not None:
            for members in self.composition.content_lists():
                members[:] = without_family(members, gone)
        return self

    def clear(self):
        self._check_open()
        self.mobjects.clear()
        return self

    def replace(self, mobject, *replacements):
        found = False
        if self.composition is not None:
            for members in self.composition.content_lists():
                if mobject in members:
                    index = members.index(mobject)
                    members[index:index + 1] = replacements
                    found = True
        if found:
            return self.remove(mobject)
        return self.remove(mobject).add(*replacements)

    def use_composition(self, composition):
        from janim.core.compositor_types import Composition

        self._check_open()
        if not isinstance(composition, Composition):
            raise TypeError("composition must be a Composition")
        self.composition = composition
        return self

    def bring_to_front(self, *mobjects):
        return self.add(*mobjects)

    def bring_to_back(self, *mobjects):
        self._check_open()
        roots = without_family(self.mobjects, family_lookup(mobjects))
        ordered = list(dict.fromkeys(mobjects))
        self.mobjects[:] = [*ordered, *roots]
        return self

    def remove_all_except(self, *mobjects):
        self.clear()
        return self.add(*mobjects)

    def _add_animated(self, animation):
        known = family_lookup(self.mobjects)
        pending = []
        pending_family = {}
        for leaf in leaf_animations(animation):
            mob = leaf.mobject
            if mob not in known:
                members = family_lookup([mob])
                # Disjoint additions commute with removal of their families.
                # Flush before an overlap to retain sequential promotion and
                # flattening, including groups with a shared descendant.
                if any(member in pending_family for member in members):
                    self.add(*pending)
                    pending.clear()
                    pending_family.clear()
                pending.append(mob)
                pending_family.update(members)
                known.update(members)
        if pending:
            self.add(*pending)

    def update_mobjects(self, dt):
        self._check_open()
        if self._in_update:
            raise RuntimeError("cannot recursively update scene roots")
        self._in_update = True
        try:
            # Snapshot membership, check eligibility at each turn.
            # A newly activated later root runs now; a newly added root waits.
            roots = list(self.mobjects)
            if self.composition is not None:
                roots = list(dict.fromkeys((*roots, *self.composition.mobjects())))
            for mob in roots:
                if mob.has_updaters():
                    mob.update(dt)
        finally:
            self._in_update = False
        return self

    def _ensure_renderer(self):
        if self.rv is None:
            from janim.backend import setup_render_vm

            self.rv = setup_render_vm(self.camera.width, self.camera.height, samples=self.samples)
        return self.rv

    def _open_output(self):
        try:
            self.output.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise ValueError(f"cannot create the output directory for {self.output}: {error}") from error
        from janim.backend import FramePipeline

        rv = self._ensure_renderer()
        self.pipeline = FramePipeline(rv.gpu, rv.target, self.output, transparent=self.transparent, **self._pipeline_options)

    def _draw_frame(self):
        rv = self._ensure_renderer()
        if self.composition is None:
            rv.draw_scene(self.mobjects, self.camera, flip_y=True)
        else:
            if self.cg is None:
                from janim.backend import setup_compositor

                self.cg = setup_compositor(rv)
            self.cg.draw(self.composition, self.camera, flip_y=True, frame=self.frames)
        self.frames_drawn += 1

    def _advance(self, dt, *, draw=True):
        before = self.t
        self.t += dt
        self.frames += 1
        selected = (
            draw
            and self.draw_from is None
            and (self.capture_t is None or before < self.capture_t <= self.t + 1e-12)
            and (self.frame_range is None or self.frames in self.frame_range)
            and (self.anim_range is None or self.anim_index in self.anim_range)
        )
        self.update_mobjects(dt)
        if selected:
            self._draw_frame()
            if self.pipeline is not None:
                self.pipeline.enqueue()
            if self.capture_t is not None:
                self.capture_img = self.rv.read(rgba=self.transparent)
                self.capture_txt = describe(self)
            if self.preview and self.window is not None:
                self._present_frame()
        if self.frame_hook is not None:
            self.frame_hook(self)

    def _present_frame(self):
        """Show the target on the preview window; without an output, pace the fixed clock."""
        from janim.backend import present

        present(self.rv, self.window)
        if self.pipeline is None:
            now = time.monotonic()
            if self._clock is not None:
                spare = 1 / self.fps - (now - self._clock)
                if spare > 0:
                    time.sleep(spare)
            self._clock = time.monotonic()

    def _progress(self, label, frame, count):
        if self.progress is not None:
            self.progress.update(self.anim_index, label, frame, count)

    def play(self, *protos, run_time=None, rate_func=None, lag_ratio=None):
        self._check_schedule()
        if not protos:
            raise ValueError("play needs an animation; use wait for a pause")
        if run_time is not None:
            run_time = check_duration(run_time, self.fps)
        animations = [prepare_animation(proto) for proto in protos]
        for anim in animations:
            anim.update_rate_info(run_time, rate_func, lag_ratio)
        animation = animations[0] if len(animations) == 1 else AnimationGroup(*animations)
        duration = check_duration(animation.get_run_time(), self.fps)
        count = max(1, round(duration * self.fps))
        self.anim_index += 1
        self.anim_starts.append(self.frames + 1)
        self._active_play = True
        try:
            self._add_animated(animation)
            animation.begin()
            if self.skipping:
                animation.finish()
                self.t += count / self.fps
                self.frames += count
            else:
                self.last_alphas = [(index + 0.5) / count for index in range(count)]
                for index, alpha in enumerate(self.last_alphas, 1):
                    animation.interpolate(alpha)
                    self._advance(1 / self.fps)
                    self._progress(type(animation).__name__, index, count)
                animation.finish()
            animation.clean_up_from_scene(self)
        finally:
            self._active_play = False
        return self

    def wait(self, duration=1.0, *, stop_condition=None):
        self._check_schedule()
        duration = check_duration(duration, self.fps, "wait duration")
        if stop_condition is not None and not callable(stop_condition):
            raise TypeError("stop_condition must be callable")
        count = max(1, round(duration * self.fps))
        self.anim_index += 1
        self.anim_starts.append(self.frames + 1)
        if self.skipping and stop_condition is None:
            self.t += count / self.fps
            self.frames += count
            return self
        self._active_play = True
        try:
            for index in range(1, count + 1):
                self._advance(1 / self.fps, draw=not self.skipping)
                if not self.skipping:
                    self._progress("Wait", index, count)
                if stop_condition is not None and stop_condition():
                    break
        finally:
            self._active_play = False
        return self

    def wait_until(self, condition, *, max_time=60.0):
        return self.wait(max_time, stop_condition=condition)

    def checkpoint(self, label):
        self._check_open()
        from .checkpoints import checkpoint

        return checkpoint(self, label)

    def add_sound(self, path, *, time_offset=0.0, time=None, gain=0.0):
        self._check_open()
        from .audio import resolve_sound

        file = resolve_sound(path)
        at = self.t + float(time_offset) if time is None else float(time)
        if not at >= 0:
            raise ValueError(f"a sound cannot start before the scene: {at}")
        self.sounds.append((str(file), at, float(gain)))
        return self

    def setup(self):
        pass

    def construct(self):
        pass

    def tear_down(self):
        pass

    def _finish_run(self):
        try:
            self.tear_down()
        finally:
            self.close()

    def _run(self, after_construct=None):
        if self._ran:
            raise RuntimeError("a scene can only run its construct method once")
        self._check_schedule()
        self._ran = True
        try:
            self.setup()
            self.construct()
            result = self if after_construct is None else after_construct(self)
        except BaseException as primary:
            try:
                self._finish_run()
            except BaseException as cleanup:
                raise primary from cleanup
            raise
        else:
            self._finish_run()
        return result

    def run(self):
        return self._run()

    def render(self, output=None):
        self._check_schedule()
        if output is not None:
            if self.pipeline is not None or self.frames:
                raise RuntimeError("set output before the scene starts rendering")
            self.output = self.rendered_path = Path(output)
            try:
                self._open_output()
            except BaseException as primary:
                try:
                    self.close()
                except BaseException as cleanup:
                    raise primary from cleanup
                raise
        return self.run()

    def close(self):
        """Drain on the owning thread, outside an active play/update call.

        A rejected recursive close propagates through run(), whose cleanup
        closes the pipeline after the active call unwinds. Other threads must
        leave GPU cleanup to the owner; concurrent target release is unsafe.
        """
        if self.closed:
            return self
        self._check_schedule()
        self.closed = True
        still = False
        try:
            if self.pipeline is not None:
                if self.anim_range is not None and self.anim_range.start > self.anim_index:
                    # The `-n` diagnostic comes before any still.
                    self.pipeline.abort()
                    self.output.unlink(missing_ok=True)
                    raise ValueError(f"the -n selection drew nothing: the scene has {self.anim_index} animations")
                if self.draw_from is not None:
                    self.pipeline.abort()
                    self.output.unlink(missing_ok=True)
                    raise ValueError(f"--from {self.draw_from} drew nothing: the scene never reaches checkpoint «{self.draw_from}»")
                if self.frames == 0:
                    still = True
                    try:
                        self._draw_frame()
                        self.rendered_path = self.output.with_suffix(".png")
                        save_png(self.rendered_path, self.rv.read(rgba=self.transparent))
                        warnings.warn(
                            f"the scene has no animations; written as a still: {self.rendered_path}",
                            RuntimeWarning,
                            stacklevel=2,
                        )
                    finally:
                        self.pipeline.close()
                        self.output.unlink(missing_ok=True)
                elif self.pipeline.k == 0:
                    self.pipeline.abort()
                    self.output.unlink(missing_ok=True)
                    raise ValueError("the selection produced no video frames")
                else:
                    self.pipeline.close()
        finally:
            # The converter may still borrow the target until the pipeline
            # has drained. The render VM is released only after that barrier.
            if self.cg is not None:
                self.cg.close()
            if self.rv is not None and not self.borrowed:
                self.rv.close()
            self._close_window()
        if self.sounds:
            if still:
                warnings.warn("a still image cannot carry audio; sounds were ignored", RuntimeWarning, stacklevel=2)
            else:
                from .audio import mux_sounds

                mux_sounds(
                    self.output,
                    self.sounds,
                    self.frames / self.fps,
                    ffmpeg=self._pipeline_options["ffmpeg"],
                    environment=self._pipeline_options["environment"],
                )
        return self

    def __enter__(self):
        self._check_open()
        return self

    def __exit__(self, kind, error, traceback):
        try:
            self.close()
        except BaseException as cleanup:
            if error is not None:
                raise error.with_traceback(traceback) from cleanup
            raise


MovingCameraScene = Scene


class ThreeDScene(Scene):
    samples = 4
    default_frame_orientation = (-30, 70)
    always_depth_test = True


def render(scene_class, *, output=None, **kwargs):
    scene = scene_class(output=output, **kwargs)
    return scene.run()


def render_frame(subject, t=None, *, fps=30, resolution=(854, 480), png=None, transparent=False, samples=0, **kwargs):
    if not isinstance(subject, type) or not issubclass(subject, Scene):
        if t is not None or transparent:
            raise TypeError("a timed or transparent capture requires a Scene subclass")
        from janim.backend import render_frame as render_static

        return render_static(subject, resolution=resolution, png=png, samples=samples, **kwargs)
    if t is None:
        t = math.inf
    scene = subject(fps=fps, resolution=resolution, transparent=transparent, samples=samples, progress=False, **kwargs)
    scene.capture_t = max(float(t), 0.5 / fps)
    def capture(scene):
        if scene.capture_img is None:
            scene._draw_frame()
            scene.capture_img = scene.rv.read(rgba=transparent)
        if png is not None:
            save_png(png, scene.capture_img)
        return scene.capture_img

    return scene._run(capture)


def render_frame_motion(scene_class, t, *, n=8, shutter=0.5, fps=30, resolution=(854, 480), png=None, **kwargs):
    """Render one frame with motion blur: `n` sub-exposures across `shutter / fps` around `t`, averaged in linear light."""
    from janim.core.colorspace import linear_to_srgb, srgb_to_linear

    if n < 1:
        raise ValueError("render_frame_motion needs at least one exposure")
    dtf = shutter / fps
    width, height = dimensions(*resolution)
    accumulator = np.zeros((height, width, 3), dtype=np.float64)
    to_linear = np.vectorize(srgb_to_linear, otypes=[np.float64])
    to_srgb = np.vectorize(linear_to_srgb, otypes=[np.float64])
    for k in range(n):
        tk = t - dtf / 2 + dtf * (k + 0.5) / n
        frame = render_frame(scene_class, max(tk, 1e-3), fps=fps, resolution=resolution, **kwargs)
        accumulator += to_linear(frame.astype(np.float64) / 255)
    image = np.clip(np.rint(255 * to_srgb(accumulator / n)), 0, 255).astype(np.uint8)
    if png is not None:
        save_png(png, image)
    return image


def animation_map(scene_class, *, fps=30, resolution=(854, 480), **kwargs):
    scene = scene_class(fps=fps, resolution=resolution, progress=False, **kwargs)
    scene.capture_t = 1.0e9
    scene.run()
    return list(scene.anim_starts), scene.frames


def render_segment(scene_class, output, *, frames, fps=30, resolution=(1280, 720), **kwargs):
    """Return the completed Scene; its output path is scene.rendered_path."""
    scene = scene_class(output=output, fps=fps, resolution=resolution, frame_range=frames, **kwargs)
    return scene.run()


def render_from(scene_class, output, label, *, scene_path="", scene_name=None, fps=30, resolution=(1280, 720), simulate_prefix=False, **kwargs):
    """Render the part of the scene after checkpoint `label`; return the Scene.

    With a valid snapshot in this process the prefix is skipped outright (no
    updaters, no frames). Without one, by default the scene runs
    in FULL and re-takes the snapshot, so the next call is fast. With
    `simulate_prefix=True` (the CLI: no snapshot outlives a
    call) the prefix is simulated and not drawn, the output starts at the
    marker, and a marker the scene never reaches is an error rather than an
    empty or a full video. `scene.skipped_prefix` tells whether a snapshot
    was used.
    """
    from .checkpoints import checkpoint_valid, normalized_path

    scene = scene_class(output=output, fps=fps, resolution=resolution, **kwargs)
    scene.scene_path = normalized_path(scene_path)
    scene.scene_name = scene_class.__name__ if scene_name is None else str(scene_name)
    scene.skipped_prefix = bool(scene.scene_path) and checkpoint_valid(scene.scene_path, scene.scene_name, str(label))
    if scene.skipped_prefix:
        scene.skip_until = str(label)
        scene.skipping = True
    elif simulate_prefix:
        scene.draw_from = str(label)
    return scene.run()


def count_frames(scene_class, *, fps=30, resolution=(1280, 720), **kwargs):
    """(frames, animations) of a scene, simulated without drawing: no GPU is touched."""
    starts, total = animation_map(scene_class, fps=fps, resolution=resolution, **kwargs)
    return total, len(starts)


def segment_ranges(frames_total, n):
    """The farm's partition: `round(total·(k−1)/n)+1 … round(total·k/n)`."""
    return [
        range(round(frames_total * (k - 1) / n) + 1, round(frames_total * k / n) + 1)
        for k in range(1, n + 1)
    ]


def concat_listing(segments):
    """The segment list of ffmpeg's concat demuxer, in its own quoting.

    A quote inside the quoted path closes the quotes, is escaped, and opens
    them again: `it's` is written `'it'\\''s'`.
    """
    return "".join("file '" + str(segment).replace("'", "'\\''") + "'\n" for segment in segments)


def render_parallel(
    scene_path,
    output,
    *,
    n=4,
    frames_total,
    fps=30,
    resolution=(1280, 720),
    crf=23,
    preset="medium",
    encoder_threads=1,
    samples=0,
    scene_name="",
    ffmpeg="ffmpeg",
    environment=None,
):
    """Split `frames_total` across `n` processes and concatenate with the same ffmpeg.

    Each worker simulates the whole scene and draws its own range
    (`render_segment`); the segments are joined by `ffmpeg -f concat -c copy`
    without re-encoding. `encoder_threads=1` by default: one single-threaded
    x264 per process, the usual farm configuration.
    """
    if scene_name and not str(scene_name).isidentifier():
        raise ValueError(
            f"scene_name = «{scene_name}» is not a Python identifier — after `file.py:` write the scene class's name as the file defines it",
        )
    limit = os.cpu_count() or 1
    n = operator.index(n)
    if not 1 <= n <= limit:
        raise ValueError(
            f"n = {n} render workers: this machine has {limit} threads, and each worker costs a Python process with its own device — use 1 ≤ n ≤ {limit}",
        )
    frames_total = operator.index(frames_total)
    if frames_total < 1:
        raise ValueError("render_parallel needs at least one frame to split")
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    path = str(Path(scene_path).resolve())
    segments = [output.with_name(output.name + f".seg{k}.mp4") for k in range(1, n + 1)]
    environment = dict(os.environ if environment is None else environment)
    workers = []
    for segment, frames in zip(segments, segment_ranges(frames_total, n)):
        code = (
            "from janim.scene.address import load_scene_class\n"
            "from janim.scene.scene import render_segment\n"
            f"cls = load_scene_class({path!r}, {str(scene_name)!r})\n"
            f"render_segment(cls, {str(segment)!r}, frames=range({frames.start}, {frames.stop}), fps={int(fps)}, "
            f"resolution=({int(resolution[0])}, {int(resolution[1])}), crf={int(crf)}, preset={str(preset)!r}, "
            f"encoder_threads={encoder_threads!r}, samples={int(samples)}, progress=False, ffmpeg={str(ffmpeg)!r})\n"
        )
        workers.append(subprocess.Popen([sys.executable, "-c", code], env=environment))
    failed = [worker.pid for worker in workers if worker.wait() != 0]
    if failed:
        for segment in segments:
            segment.unlink(missing_ok=True)
        raise RuntimeError(f"a render_parallel process failed (pids {failed})")
    listing = output.with_name(output.name + ".list.txt")
    listing.write_text(concat_listing(segments))
    try:
        subprocess.run(
            [str(ffmpeg), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(output)],
            env=environment,
            check=True,
        )
    finally:
        for segment in segments:
            segment.unlink(missing_ok=True)
        listing.unlink(missing_ok=True)
    return output


def _describe_mobjects(lines, mobjects, level):
    pending = [(mob, level) for mob in reversed(mobjects)]
    while pending:
        mob, depth = pending.pop()
        if not isinstance(mob, VMobject):
            continue
        box = mob.get_bounding_box()
        line = f"{'  ' * depth}- {type(mob).__name__} · {len(mob.points)} points"
        if mob.has_points():
            def color_text(color):
                channels = "".join(f"{round(float(np.float32(255) * value)):02x}" for value in color[:3])
                return f"#{channels} α{float(color[3]):.2f}"

            line += f" · bbox [{box[0, 0]:.3f}, {box[2, 0]:.3f}]×[{box[0, 1]:.3f}, {box[2, 1]:.3f}]"
            width = str(np.round(mob.stroke_width[0] * np.float32(100)) / np.float32(100))
            line += f" · stroke {color_text(mob.stroke_rgba[0])} w{width} · fill {color_text(mob.fill_rgba[0])}"
        if mob.has_updaters():
            line += f" · {len(mob.updaters)} updater(s)"
        lines.append(line)
        pending.extend((child, depth + 1) for child in reversed(mob.submobjects))


def describe(subject, t=None, *, fps=30, resolution=(854, 480), **kwargs):
    if not isinstance(subject, Scene):
        scene = subject(fps=fps, resolution=resolution, progress=False, **kwargs)
        scene.capture_t = math.inf if t is None else max(float(t), 0.5 / fps)
        scene.run()
        return scene.capture_txt if scene.capture_txt is not None else describe(scene)
    scene = subject
    lines = [f"Scene {scene.camera.width}×{scene.camera.height} · t={scene.t:.3f} s · {scene.frames} frames · {len(scene.mobjects)} mobjects"]
    _describe_mobjects(lines, scene.mobjects, 1)
    if scene.composition is not None:
        _describe_composition(lines, scene.composition)
    return "\n".join(lines) + "\n"


def _describe_composition(lines, composition, depth=0, prefix=""):
    from janim.core.compositor_types import Composition

    for index, layer in enumerate(composition.layers, 1):
        name = f"{prefix}{index}"
        pad = "  " * depth
        content = layer.content
        if content is None:
            lines.append(f"{pad}layer {name} · adjustment · {len(layer.effects)} effects")
        elif isinstance(content, Composition):
            lines.append(f"{pad}layer {name} · blend=:{layer.blend} · opacity={layer.opacity} · precomp · {len(content.layers)} layers")
            _describe_composition(lines, content, depth + 1, name + ".")
        else:
            lines.append(f"{pad}layer {name} · blend=:{layer.blend} · opacity={layer.opacity} · {len(content)} mobjects")
            _describe_mobjects(lines, content, depth + 2)
        if layer.mask is not None:
            lines.append(f"{pad}  mask · {len(layer.mask.content)} mobjects")
            _describe_mobjects(lines, layer.mask.content, depth + 2)
