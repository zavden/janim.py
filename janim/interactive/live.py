"""The live window: a playhead forward, exact replay backward.

`construct` runs ONCE, in a thread parked by `Scene.frame_hook` at the end of
every simulated frame; the loop orders frames one at a time and draws the
parked state itself — the same picture `_advance` would have captured, equal
to `render_frame` byte for byte. Any jump BEHIND the playhead rebuilds it
from t = 0 (updaters with state cannot resume from a snapshot). The map of
landmarks GROWS with the playhead and only an edit resets it. Edits are seen
by the SHA-256 of the file's text and applied with `importlib.reload`; a
broken edit or a throwing scene FREEZES the window on the last good frame and
watches the file. The timeline strip is painted AFTER caching: live pixels.
"""

import hashlib
import math
from pathlib import Path
import queue
import sys
import threading
import time
import traceback
import warnings

import numpy as np

from janim.backend import (
    blit_image,
    close_context,
    create_window,
    paint_strip,
    poll_events,
    present,
    read_frame_into,
    setup_render_vm,
)
from janim.constants import DOWN, FRAME_HEIGHT, UP
from janim.core.camera import Camera
from janim.scene.address import load_scene_module, reload_scene_module, resolve_scene, scene_address
from janim.scene.progress import RenderProgress
from .controls import (
    Controls,
    CursorTracker,
    anim_at,
    apply_user_delta,
    compose_camera,
    cursor_delta,
    hop_to,
    key_press,
    mark_at,
    mouse_drag,
    mouse_move,
    refresh_scene_base,
    release,
    scroll,
    user_cam_snapshot,
)

CACHE_BYTES = 500_000_000
PLAYED = (0.345, 0.769, 0.867)
TRACK = (0.10, 0.10, 0.12)
ACT_TICK = (0.62, 0.62, 0.66)
MARK = (1.0, 0.823, 0.369)


class _LiveAbort(Exception):
    """The playhead's way out of a running construct. Never reaches the user."""


class Playhead:
    """`construct` running once, parked between frames by a two-queue handshake."""

    def __init__(self, scene, ucam):
        self.scene = scene
        self.thread = None
        self.step = queue.Queue(maxsize=1)
        self.ready = queue.Queue(maxsize=2)
        self.idx = 0
        self.parked = False
        self.finished = False
        self.total = 0
        self.error = None
        self.ucam = ucam


class Live:
    def __init__(self, path, name, fps, resolution, window, rv, module, scene_class, source_hash):
        self.path = path
        self.name = name
        self.fps = fps
        self.resolution = resolution
        self.window = window
        self.rv = rv
        self.ctrl = Controls()
        self.idx = 0
        self.source_hash = source_hash
        self.pool = []
        self.cache = {}
        self.hits = 0
        self.module = module
        self.scene_class = scene_class
        self.anim_starts = []
        self.marks = []
        self.total = 0
        self.abort = lambda: False
        self.ph = None
        self.progress = None
        self.reloads = 0


def source_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cache_cap(resolution):
    """~500 MB of frames with a floor of 8 (what the step back needs)."""
    width, height = resolution
    return max(8, CACHE_BYTES // (3 * width * height))


def live_status(v):
    """The title bar: frame, animation, checkpoint and whether it plays."""
    count = len(v.anim_starts)
    text = f"Janim · frame {v.idx}" + (f"/{v.total}" if v.total > 0 else "")
    if count > 0:
        text += f" · animation {anim_at(v.anim_starts, v.idx)}/{count}"
    label = mark_at(v.marks, v.idx)
    if label is not None:
        text += f" · {label}"
    return text + (" ⏸" if v.ctrl.paused else " ▶")


def setup_live(address, *, fps=30, resolution=(1280, 720), visible=False, samples=0):
    """The live session without its loop: module, window, VM and state."""
    path, name = scene_address(str(address))
    path = str(Path(path).resolve())
    module = load_scene_module(path)
    scene_class = resolve_scene(module, name, path)
    width, height = int(resolution[0]), int(resolution[1])
    window = create_window(width, height, title="Janim (live)", visible=visible)
    try:
        rv = setup_render_vm(width, height, samples=samples)
    except BaseException:
        close_context(window)
        raise
    return Live(path, name, int(fps), (width, height), window, rv, module, scene_class, source_digest(path))


def _pool_take(v):
    if v.pool:
        return v.pool.pop()
    return np.empty((v.resolution[1], v.resolution[0], 3), dtype=np.uint8)


def _recycle_cache(v):
    v.pool.extend(v.cache.values())
    v.cache.clear()


def _new_scene(v, *, capture_t=None, progress=None):
    scene = v.scene_class(
        fps=v.fps,
        resolution=v.resolution,
        context=v.rv,
        progress=progress,
        samples=v.rv.samples,
    )
    scene.scene_path = v.path
    scene.scene_name = v.name or v.scene_class.__name__
    if capture_t is not None:
        scene.capture_t = capture_t
    compose_camera(scene.camera, v.ctrl.camera)
    return scene


def simulate(v, idx):
    """Frame `idx` from t = 0 on the calling thread: the reference the playhead must equal."""
    scene = _new_scene(v, capture_t=(idx - 0.5) / v.fps, progress=False)
    try:
        scene.setup()
        scene.construct()
        scene.tear_down()
        v.anim_starts = list(scene.anim_starts)
        v.marks = list(scene.checkpoint_frames)
        v.total = scene.frames
        if scene.capture_img is None:
            scene._draw_frame()
            scene.capture_img = scene.rv.read()
        return np.array(scene.capture_img, dtype=np.uint8)
    finally:
        scene.close()


def _playhead_start(v):
    scene = _new_scene(v, capture_t=-1.0, progress=v.progress)
    ph = Playhead(scene, user_cam_snapshot(v.ctrl.camera))

    def hook(sc):
        ph.ready.put((False, sc.frames))
        if ph.step.get() == -1:
            raise _LiveAbort()

    scene.frame_hook = hook

    def run():
        scene._adopt_thread()
        try:
            scene.setup()
            scene.construct()
            scene.tear_down()
        except _LiveAbort:
            pass
        except BaseException as error:  # the scene's own bug, surfaced by the loop
            ph.error = error
        finally:
            try:
                ph.ready.put((True, scene.frames), timeout=1.0)
            except queue.Full:
                pass

    ph.thread = threading.Thread(target=run, name="janim-playhead", daemon=True)
    ph.thread.start()
    return ph


def _playhead_advance(v, ph, target):
    """Advance to `target`; control returns to the loop after EVERY simulated frame."""
    while not ph.finished and ph.idx < target:
        if ph.parked:
            ph.step.put(1)
            ph.parked = False
        ended, frames = ph.ready.get()
        ph.idx = frames
        if ended:
            ph.finished = True
            ph.total = frames
        else:
            ph.parked = True
            refresh_scene_base(v.ctrl, ph.scene.camera, ph.ucam)
            if v.window is not None:
                poll_events()
            if v.abort() or v.ctrl.quit:
                break
    return ph


def _playhead_close(ph):
    try:
        while not ph.finished:
            if ph.parked:
                ph.step.put(-1)
                ph.parked = False
            ended, _ = ph.ready.get(timeout=5.0)
            if ended:
                ph.finished = True
            else:
                ph.parked = True
    except queue.Empty:
        pass
    if ph.thread is not None:
        ph.thread.join(timeout=5.0)
    ph.scene.frame_hook = None
    ph.scene._adopt_thread()
    try:
        ph.scene.close()
    except Exception:
        traceback.print_exc()


def _invalidate_playhead(v):
    if v.ph is None:
        return
    _playhead_close(v.ph)
    v.ph = None


def _frame_via_playhead(v, target):
    ph = v.ph
    if ph is None or target < ph.idx or ph.error is not None:
        _invalidate_playhead(v)
        ph = v.ph = _playhead_start(v)
    _playhead_advance(v, ph, target)
    if ph.error is not None:
        raise ph.error
    ph.scene._draw_frame()
    return read_frame_into(v.rv, _pool_take(v))


def _seek_landmark(v, kind, beyond):
    ph = v.ph
    if ph is None or ph.error is not None:
        _invalidate_playhead(v)
        ph = v.ph = _playhead_start(v)

    def landmark():
        marks = ph.scene.anim_starts if kind == "anim" else [frame for _, frame in ph.scene.checkpoint_frames]
        return next((mark for mark in marks if mark > beyond), None)

    while True:
        found = landmark()
        if found is not None:
            return found
        if ph.finished:
            return beyond
        _playhead_advance(v, ph, ph.idx + 1)
        if v.abort() or v.ctrl.quit:
            return beyond


def _hop_forward(v, kind, count):
    current = v.idx
    for _ in range(count):
        known = v.anim_starts if kind == "anim" else [frame for _, frame in v.marks]
        following = next((mark for mark in known if mark > current), None)
        following = _seek_landmark(v, kind, current) if following is None else following
        if following == current:
            break
        current = following
        _refresh_map(v)
    return current


def _refresh_map(v):
    """Monotone: a rebuilt playhead never shrinks what was already learned."""
    ph = v.ph
    if ph is None:
        return
    scene = ph.scene
    if len(scene.anim_starts) > len(v.anim_starts):
        v.anim_starts = list(scene.anim_starts)
    if len(scene.checkpoint_frames) > len(v.marks):
        v.marks = list(scene.checkpoint_frames)
    if ph.finished and ph.total > 0:
        v.total = ph.total


def _trim_cache(v):
    cap = cache_cap(v.resolution)
    while len(v.cache) > cap:
        far = max(v.cache, key=lambda key: abs(key - v.idx))
        v.pool.append(v.cache.pop(far))


def _reload_if_edited(v):
    digest = source_digest(v.path)
    if digest == v.source_hash:
        return False
    reload_scene_module(v.module)
    v.scene_class = resolve_scene(v.module, v.name, v.path)
    v.source_hash = digest
    v.reloads += 1
    return True


def live_step(v):
    """One tick: the edit, the camera, the navigation, and the frame."""
    if _reload_if_edited(v):
        _recycle_cache(v)
        _invalidate_playhead(v)
        v.anim_starts = []
        v.marks = []
        v.total = 0
        if v.progress is not None:
            v.progress.seen = v.progress.current = 0
    if v.ctrl.touched:
        v.ctrl.touched = False
        _recycle_cache(v)
        if v.ph is None or v.ph.error is not None:
            _invalidate_playhead(v)
        else:
            apply_user_delta(v.ph.scene.camera, v.ph.ucam, v.ctrl.camera)
            v.ph.ucam = user_cam_snapshot(v.ctrl.camera)
    if "left" in v.ctrl.keys_down:
        v.ctrl.scrub -= v.fps
        release(v.ctrl, "left")
    if "right" in v.ctrl.keys_down:
        v.ctrl.scrub += v.fps
        release(v.ctrl, "right")
    advanced = False
    if v.ctrl.home:
        v.idx = 1
        v.ctrl.home = False
    elif v.ctrl.hop_anims != 0:
        if v.ctrl.hop_anims > 0:
            v.idx = _hop_forward(v, "anim", v.ctrl.hop_anims)
        else:
            v.idx = hop_to(v.anim_starts, v.idx, v.ctrl.hop_anims)
        v.ctrl.hop_anims = 0
    elif v.ctrl.hop_marks != 0:
        if v.ctrl.hop_marks > 0:
            v.idx = _hop_forward(v, "mark", v.ctrl.hop_marks)
        else:
            v.idx = hop_to([frame for _, frame in v.marks], v.idx, v.ctrl.hop_marks)
        v.ctrl.hop_marks = 0
    elif v.ctrl.scrub != 0:
        v.idx = max(1, v.idx + v.ctrl.scrub)
        v.ctrl.scrub = 0
    elif v.ctrl.paused:
        v.idx = max(1, v.idx + v.ctrl.steps)
        v.ctrl.steps = 0
    else:
        if v.total > 0 and v.idx >= v.total:
            v.idx = v.total
        else:
            v.idx += 1
        advanced = True
    if advanced and v.ctrl.stop_at_marks and any(frame == v.idx for _, frame in v.marks):
        v.ctrl.paused = True
    image = v.cache.get(v.idx)
    if image is None:
        image = _frame_via_playhead(v, v.idx)
        v.cache[v.idx] = image
        _trim_cache(v)
    else:
        v.hits += 1
        blit_image(v.rv, image)
    _refresh_map(v)
    if v.ph is not None:
        refresh_scene_base(v.ctrl, v.ph.scene.camera, v.ph.ucam)
    return image


def live_tick(v):
    """A guarded tick: (image, None) or (None, error). KeyboardInterrupt propagates."""
    try:
        return live_step(v), None
    except KeyboardInterrupt:
        raise
    except BaseException as error:  # the scene's bug or a broken edit: the loop freezes
        return None, error


def error_overlay(v, error, base, *, label=None):
    """The last good frame under a veil, the error on a banner, what is watched."""
    from janim.core.image import ImageMobject
    from janim.core.shapes import Rectangle
    from janim.text.text import Text

    width, height = v.resolution
    camera = Camera(width=width, height=height)
    frame_width, frame_height = camera.frame_width, camera.frame_height
    mobjects = []
    if base is not None:
        rgba = np.empty((base.shape[0], base.shape[1], 4), dtype=np.uint8)
        rgba[:, :, :3] = base
        rgba[:, :, 3] = 255
        mobjects.append(ImageMobject(rgba, height=frame_height))
        veil = Rectangle(width=frame_width, height=frame_height)
        veil.set_stroke(opacity=0)
        veil.set_fill(color="#000000", opacity=0.45)
        mobjects.append(veil)
    banner = Rectangle(width=frame_width, height=2.1)
    banner.set_stroke(opacity=0)
    banner.set_fill(color="#121216", opacity=0.85)
    banner.to_edge(UP, buff=0.0)
    mobjects.append(banner)
    head = Text("The scene threw — frozen at the last good frame", size=0.4, color="#FF6B6B")
    head.to_edge(UP, buff=0.22)
    mobjects.append(head)
    message = "unknown error" if error is None else str(error)
    previous = head
    for line in message.split("\n")[:2]:
        text = line.strip()
        if not text:
            continue
        if len(text) > 110:
            text = text[:107] + "…"
        row = Text(text, size=0.27, color="#DDDDDD")
        row.next_to(previous, DOWN, buff=0.14)
        mobjects.append(row)
        previous = row
    watched = Path(v.path).name if label is None else label
    foot = Text(f"watching {watched} — save a fix to resume · Esc/q quits", size=0.3, color="#9AA5B1")
    foot.next_to(previous, DOWN, buff=0.18)
    mobjects.append(foot)
    v.rv.draw_scene(mobjects, camera, flip_y=True)


def freeze_frame(v, error, base, *, label=None):
    """Freeze on `error`; if even the overlay fails, fall back to the plain frame."""
    try:
        error_overlay(v, error, base, label=label)
    except Exception:
        if base is not None:
            blit_image(v.rv, base)


def timeline_segments(width, height, idx, total, anim_starts, marks):
    """The strip's segments (x0, x1, r, g, b) in painting order; None when nothing plays yet."""
    if total <= 0:
        return None
    segments = []

    def segment(x0, x1, color):
        x0 = min(max(int(x0), 0), width)
        x1 = min(max(int(x1), 0), width)
        if x1 > x0:
            segments.append((x0, x1, *color))

    segment(0, width, TRACK)
    segment(0, round(width * min(max(idx / total, 0.0), 1.0)), PLAYED)
    for frame in anim_starts:
        x = round(width * (frame - 1) / total)
        segment(x, x + 2, ACT_TICK)
    for _, frame in marks:
        x = round(width * (frame - 1) / total)
        segment(x, x + 3, MARK)
    return segments


def draw_timeline(v):
    width, height = v.resolution
    total = v.total if v.total > 0 else (v.idx if v.ph is None else max(v.ph.idx, v.idx))
    segments = timeline_segments(width, height, v.idx, total, v.anim_starts, v.marks)
    if segments is None:
        return
    paint_strip(v.rv, width, height, max(4, height // 90), segments)


def close_live(v):
    _invalidate_playhead(v)
    _recycle_cache(v)
    v.rv.close()
    close_context(v.window)
    v.window = None


def _install_callbacks(v):
    import glfw

    width, height = v.resolution
    ppu_fixed = FRAME_HEIGHT / height
    tracker = CursorTracker()

    def ppu():
        return v.ctrl.camera.frame_width / width

    def on_enter(_window, entered):
        if entered:
            tracker.reseed = True

    def on_cursor(_window, x, y):
        delta = cursor_delta(tracker, x, y)
        if delta is None:
            return
        d_point = (delta[0] * ppu_fixed, -delta[1] * ppu_fixed, 0.0)
        if v.ctrl.dragging:
            mouse_drag(v.ctrl, d_point)
        else:
            mouse_move(v.ctrl, d_point)

    def on_button(_window, _button, action, _mods):
        v.ctrl.dragging = action == glfw.PRESS

    def on_scroll(_window, _dx, dy):
        x, y = tracker.last
        point = ((x - width / 2) * ppu(), (height / 2 - y) * ppu(), 0.0)
        scroll(v.ctrl, point, -dy * 2, height)

    key_map = {
        glfw.KEY_D: "d",
        glfw.KEY_F: "f",
        glfw.KEY_R: "r",
        glfw.KEY_SPACE: "space",
        glfw.KEY_PERIOD: "period",
        glfw.KEY_COMMA: "comma",
        glfw.KEY_LEFT: "left",
        glfw.KEY_RIGHT: "right",
        glfw.KEY_LEFT_BRACKET: "bracket_left",
        glfw.KEY_RIGHT_BRACKET: "bracket_right",
        glfw.KEY_PAGE_UP: "page_up",
        glfw.KEY_PAGE_DOWN: "page_down",
        glfw.KEY_HOME: "home",
        glfw.KEY_C: "c",
        glfw.KEY_ESCAPE: "escape",
        glfw.KEY_Q: "q",
    }

    def on_key(_window, key, _scancode, action, _mods):
        symbol = key_map.get(key)
        if symbol is None:
            return
        if action == glfw.PRESS:
            key_press(v.ctrl, symbol)
        elif action == glfw.RELEASE:
            release(v.ctrl, symbol)

    handle = v.window.handle
    glfw.set_cursor_enter_callback(handle, on_enter)
    glfw.set_cursor_pos_callback(handle, on_cursor)
    glfw.set_mouse_button_callback(handle, on_button)
    glfw.set_scroll_callback(handle, on_scroll)
    glfw.set_key_callback(handle, on_key)
    v.window.callbacks.extend([on_enter, on_cursor, on_button, on_scroll, on_key])


def live(address, *, fps=30, resolution=(1280, 720), stop_at_checkpoints=False, max_seconds=math.inf, abort=lambda: False, progress="auto", samples=0):
    """The complete interactive loop over `address` (`file.py` or `file.py:Class`)."""
    from janim.backend import glfw as window_system

    v = setup_live(address, fps=fps, resolution=resolution, visible=True, samples=samples)
    v.ctrl.stop_at_marks = bool(stop_at_checkpoints)
    v.abort = abort
    if progress == "auto":
        v.progress = RenderProgress(sys.stderr) if sys.stderr.isatty() else None
    elif isinstance(progress, bool):
        v.progress = RenderProgress(sys.stderr) if progress else None
    else:
        v.progress = progress
    _install_callbacks(v)
    started = time.monotonic()
    last_good = None
    frozen = None
    frozen_hash = ""
    try:
        while not window_system.should_close(v.window) and not v.ctrl.quit and not abort() and time.monotonic() - started < max_seconds:
            mark = time.monotonic()
            if frozen is None:
                image, error = live_tick(v)
                if error is None:
                    last_good = image
                    draw_timeline(v)
                else:
                    frozen = error
                    frozen_hash = source_digest(v.path)
                    _invalidate_playhead(v)
                    freeze_frame(v, error, last_good)
                    warnings.warn(f"the scene threw — frozen; watching {Path(v.path).name}: {error}", RuntimeWarning, stacklevel=2)
            else:
                poll_events()
                if source_digest(v.path) != frozen_hash:
                    frozen = None
            present(v.rv, v.window)
            title = live_status(v) if frozen is None else f"Janim · ERROR — watching {Path(v.path).name} (save to resume)"
            window_system.set_title(v.window, title)
            spare = 1 / v.fps - (time.monotonic() - mark)
            if spare > 0:
                time.sleep(spare)
    except KeyboardInterrupt:
        pass
    finally:
        close_live(v)
    return v
