"""The live window's input state and camera maths, window-free.

Follows ManimGL's scene.py mouse and keyboard handlers on top of Janim's camera: the
USER's camera holds deltas composed over the scene's own camera, the rotate
is GL's turntable in screen units on the COMPOSED frame, the pan maps through
the composed rotation and scale, and every seam of the event↔tick cycle
renormalises its quaternion (one ulp of drift compounds to zero in ~80
rounds).
"""

import math

import numpy as np

from janim.constants import FRAME_HEIGHT
from janim.core.algebra import (
    euler_zxz_from_quat,
    quat_conj,
    quat_from_euler_zxz,
    quat_identity,
    quat_mul,
    quat_normalize,
    quat_to_matrix,
)
from janim.core.camera import Camera

CURSOR_CAP = 150.0


# ── navigation by landmark ────────────────────────────────────────

def hop_to(marks, idx, delta):
    """The landmark `delta` steps from `idx`; out of landmarks, stay put."""
    if not marks:
        return idx
    current = idx
    for _ in range(abs(delta)):
        if delta < 0:
            candidates = [mark for mark in marks if mark < current]
            if not candidates:
                return current
            current = candidates[-1]
        else:
            candidates = [mark for mark in marks if mark > current]
            if not candidates:
                return current
            current = candidates[0]
    return current


def anim_at(starts, idx):
    """Which numbered animation frame `idx` falls inside (0 before the first)."""
    return sum(1 for start in starts if start <= idx)


def mark_at(marks, idx):
    """The last checkpoint label at or before `idx`, or None."""
    best = None
    for label, frame in marks:
        if frame <= idx and (best is None or frame >= best[1]):
            best = (label, frame)
    return None if best is None else best[0]


# ── the cursor's delta hygiene ───────────────────────────────────

class CursorTracker:
    """Starts unseeded and reseeds on every re-entry: the first event moves nothing."""

    def __init__(self):
        self.last = (0.0, 0.0)
        self.reseed = True


def cursor_delta(tracker, x, y, *, cap=CURSOR_CAP):
    """(dx, dy) clamped to `cap` per axis, or None when this event seeds the tracker."""
    x, y = float(x), float(y)
    if tracker.reseed:
        tracker.reseed = False
        tracker.last = (x, y)
        return None
    dx, dy = x - tracker.last[0], y - tracker.last[1]
    tracker.last = (x, y)
    return (min(max(dx, -cap), cap), min(max(dy, -cap), cap))


# ── the controls ─────────────────────────────────────────────────────────

class Controls:
    """Keys down, pause, requested jumps and the user's camera deltas."""

    def __init__(self, *, camera=None, sens_pan3d=0.5, sens_scroll=20.0):
        self.camera = Camera() if camera is None else camera
        self.scene_orientation = quat_identity()
        self.scene_scale = 1.0
        self.keys_down = {}
        self.dragging = False
        self.paused = False
        self.steps = 0
        self.scrub = 0
        self.sens_pan3d = float(sens_pan3d)
        self.sens_scroll = float(sens_scroll)
        self.touched = False
        self.hop_anims = 0
        self.hop_marks = 0
        self.home = False
        self.stop_at_marks = False
        self.quit = False


def composed_orientation(ctrl):
    """The composed (user ∘ scene) orientation: GL's actual frame."""
    return quat_mul(ctrl.camera.orientation, ctrl.scene_orientation)


def composed_scale(ctrl):
    return ctrl.camera.get_scale() * ctrl.scene_scale


def set_composed_orientation(ctrl, quaternion):
    """Store a composed orientation as the user delta that produces it, renormalised."""
    ctrl.camera.orientation = quat_normalize(quat_mul(quaternion, quat_conj(ctrl.scene_orientation)))
    return ctrl


def refresh_scene_base(ctrl, composed, ucam):
    """The pure scene part of a parked camera: `ucam⁻¹ ∘ composed`, renormalised."""
    ctrl.scene_orientation = quat_normalize(quat_mul(quat_conj(ucam.orientation), composed.orientation))
    ctrl.scene_scale = composed.get_scale() / (ucam.frame_height / FRAME_HEIGHT)
    return ctrl


def _vector(point):
    values = [float(point[0]), float(point[1]), float(point[2]) if len(point) > 2 else 0.0]
    return np.array(values, dtype=np.float64)


def world_delta(ctrl, delta):
    """GL's from_fixed_frame_point(d, relative=true): screen → world = R·(s·d)."""
    return quat_to_matrix(composed_orientation(ctrl)) @ (delta * composed_scale(ctrl))


def mouse_move(ctrl, d_point):
    """`d` rotates (turntable on the composed frame), `f` pans (through the world)."""
    delta = _vector(d_point)
    if "d" in ctrl.keys_down:
        ff = delta * ctrl.sens_pan3d
        theta, phi, gamma = euler_zxz_from_quat(composed_orientation(ctrl))
        set_composed_orientation(
            ctrl,
            quat_from_euler_zxz(
                theta - ff[0],
                min(max(phi + ff[1], 0.0), math.pi),
                gamma,
            ),
        )
        ctrl.touched = True
    elif "f" in ctrl.keys_down:
        center = ctrl.camera.center_point.astype(np.float64) - world_delta(ctrl, delta)
        ctrl.camera.center_point = center.astype(np.float32)
        ctrl.touched = True
    return ctrl


def mouse_drag(ctrl, d_point):
    """Dragging pans (GL's drag_to_pan), through the same world mapping."""
    center = ctrl.camera.center_point.astype(np.float64) - world_delta(ctrl, _vector(d_point))
    ctrl.camera.center_point = center.astype(np.float32)
    ctrl.touched = True
    return ctrl


def scroll(ctrl, point, dy_pixels, height_pixels):
    """The wheel zooms about the cursor's point: factor 1 − sens·dy/H."""
    factor = 1 - ctrl.sens_scroll * float(dy_pixels) / float(height_pixels)
    ctrl.camera.scale_frame(factor, about=point)
    ctrl.touched = True
    return ctrl


def key_press(ctrl, key):
    """on_key_press plus the playback controls; Esc/q are orders, not modifiers."""
    if key == "r":
        ctrl.camera.reset_camera()
        ctrl.touched = True
    elif key == "space":
        ctrl.paused = not ctrl.paused
    elif key == "period":
        ctrl.paused = True
        ctrl.steps += 1
    elif key == "comma":
        ctrl.paused = True
        ctrl.steps -= 1
    elif key in ("left", "right"):
        ctrl.keys_down[key] = None
    elif key == "bracket_left":
        ctrl.hop_anims -= 1
        ctrl.paused = True
    elif key == "bracket_right":
        ctrl.hop_anims += 1
        ctrl.paused = True
    elif key == "page_up":
        ctrl.hop_marks -= 1
        ctrl.paused = True
    elif key == "page_down":
        ctrl.hop_marks += 1
        ctrl.paused = True
    elif key == "home":
        ctrl.home = True
        ctrl.paused = True
    elif key == "c":
        ctrl.stop_at_marks = not ctrl.stop_at_marks
    elif key in ("escape", "q"):
        ctrl.quit = True
    else:
        ctrl.keys_down[key] = None
    return ctrl


def release(ctrl, key):
    ctrl.keys_down.pop(key, None)
    return ctrl


class UserCameraSnapshot:
    """The user camera's state at composition time."""

    def __init__(self, orientation, center, frame_height):
        self.orientation = orientation
        self.center = center
        self.frame_height = frame_height


def user_cam_snapshot(user):
    return UserCameraSnapshot(user.orientation, user.center_point.copy(), user.frame_height)


def compose_camera(scene_camera, user):
    """Compose the user's deltas ON TOP of the scene's camera."""
    scene_camera.orientation = quat_normalize(quat_mul(user.orientation, scene_camera.orientation))
    center = scene_camera.center_point.astype(np.float64) + user.center_point.astype(np.float64)
    scene_camera.center_point = center.astype(np.float32)
    zoom = user.frame_height / FRAME_HEIGHT
    scene_camera.frame_height *= zoom
    scene_camera.frame_width *= zoom
    return scene_camera


def apply_user_delta(scene_camera, snapshot, user):
    """Re-express the deltas on an already composed camera: `to ∘ from⁻¹` on top."""
    scene_camera.orientation = quat_normalize(
        quat_mul(user.orientation, quat_mul(quat_conj(snapshot.orientation), scene_camera.orientation)),
    )
    center = (
        scene_camera.center_point.astype(np.float64)
        + user.center_point.astype(np.float64)
        - snapshot.center.astype(np.float64)
    )
    scene_camera.center_point = center.astype(np.float32)
    zoom = user.frame_height / snapshot.frame_height
    scene_camera.frame_height *= zoom
    scene_camera.frame_width *= zoom
    return scene_camera
