"""Prefix-keyed geometry snapshots.

Snapshots preserve mobject state, not the internal state of updater closures.
Replay from zero is the reliable path for stateful integrators.
"""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

from janim.animation.animation import animation_copy


@dataclass
class Checkpoint:
    mobjects: list
    time: float
    frames: int
    prefix_hash: str
    stamped: float


_CHECKPOINTS = {}


def normalized_path(path):
    return str(Path(path).resolve()) if path else ""


def prefix_hash(path, label):
    path = Path(normalized_path(path))
    if not path.is_file():
        return ""
    lines = path.read_text(encoding="utf-8").split("\n")
    pattern = re.compile(r"checkpoint\s*\(.*[\"']" + re.escape(str(label)) + r"[\"']")
    indices = [index for index, line in enumerate(lines) if pattern.search(line)]
    if len(indices) != 1:
        return ""
    return hashlib.sha256("\n".join(lines[:indices[0]]).encode()).hexdigest()


def checkpoint_valid(path, scene_name, label):
    path = normalized_path(path)
    snapshot = _CHECKPOINTS.get((path, str(scene_name), str(label)))
    if snapshot is None:
        return False
    current = prefix_hash(path, label)
    return bool(current) and current == snapshot.prefix_hash


def checkpoint_states(path):
    path = normalized_path(path)
    states = []
    for stored_path, name, label in _CHECKPOINTS:
        if stored_path == path:
            shown = label if name == "construct" else name + ":" + label
            states.append((shown, checkpoint_valid(path, name, label)))
    return sorted(states, key=lambda state: state[0])


def clear_checkpoints():
    _CHECKPOINTS.clear()


def adopt_snapshot(scene, snapshot):
    count = min(len(scene.mobjects), len(snapshot.mobjects))
    for index in range(count):
        live, saved = scene.mobjects[index], snapshot.mobjects[index]
        if type(live) is type(saved):
            live.become(saved)
        else:
            scene.mobjects[index] = animation_copy(saved)
    scene.mobjects.extend(animation_copy(mob) for mob in snapshot.mobjects[count:])
    return scene


def checkpoint(scene, label):
    label = str(label)
    path = normalized_path(scene.scene_path)
    key = (path, scene.scene_name, label)
    if scene.draw_from == label:
        # The simulated prefix hands over to the drawn suffix here.
        scene.draw_from = None
    if scene.skip_until == label:
        snapshot = _CHECKPOINTS.get(key)
        if snapshot is not None and checkpoint_valid(path, scene.scene_name, label):
            adopt_snapshot(scene, snapshot)
            scene.t, scene.frames = snapshot.time, snapshot.frames
        scene.skipping = False
        scene.skip_until = None
    elif path:
        digest = prefix_hash(path, label)
        if digest:
            try:
                stamped = Path(path).stat().st_mtime
            except OSError:
                stamped = 0.0
            _CHECKPOINTS[key] = Checkpoint(
                [animation_copy(mob) for mob in scene.mobjects],
                scene.t,
                scene.frames,
                digest,
                stamped,
            )
    scene.checkpoint_frames.append((label, scene.frames + 1))
    return scene
