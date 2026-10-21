"""Per-act progress reporting; wall time never enters scene simulation."""

import math
import time


def bar_cells(fraction, cells=16):
    value = min(max(float(fraction), 0.0), 1.0) * cells
    full = math.floor(value)
    eighth = round(8 * (value - full))
    if eighth == 8:
        full += 1
        eighth = 0
    partial = "" if eighth == 0 else "▏▎▍▌▋▊▉"[eighth - 1]
    return "▕" + "█" * full + partial + " " * max(0, cells - full - bool(partial)) + "▏"


def bar_text(index, label, frame, total, elapsed):
    fraction = frame / total if total else 1.0
    fps = frame / elapsed if elapsed > 0 else 0.0
    eta = (total - frame) / fps if fps > 0 else 0.0
    head = f"Animation {index} · {label}".ljust(26)
    tail = f"100% · {total} f · {elapsed:.1f} s" if frame >= total else f"{round(100 * fraction):3d}% · {frame}/{total} · {fps:.0f} f/s · eta {eta:.1f} s"
    color = "\x1b[32m" if frame >= total else "\x1b[2m"
    return f"\x1b[2m{head}\x1b[0m \x1b[36m{bar_cells(fraction)}\x1b[0m {color}{tail}\x1b[0m"


class RenderProgress:
    def __init__(self, stream):
        self.stream = stream
        self.enabled = True
        self.seen = self.current = 0
        self.started = self.emitted = 0.0

    def update(self, index, label, frame, total):
        if not self.enabled or index <= self.seen:
            return
        now = time.monotonic()
        if self.current != index:
            self.current = index
            self.started = now
            self.emitted = 0.0
        done = frame >= total
        if not (done or frame == 1 or now - self.emitted > 0.15):
            return
        self.emitted = now
        try:
            self.stream.write("\r\x1b[K" + bar_text(index, label, frame, total, now - self.started) + ("\n" if done else ""))
            self.stream.flush()
        except (OSError, ValueError):
            self.enabled = False
        if done:
            self.seen = index
            self.current = 0
