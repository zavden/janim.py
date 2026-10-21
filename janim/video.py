"""Incremental RGB24/x264 or straight-RGBA/ProRes pipe.

One borrowed frame is written and acknowledged before another is accepted.
Acknowledgements count complete pipe writes, not independently encoded frames.
IO has a deadline; post-EOF flush has an optional, separate deadline and is
always cancellable.
"""

import math
import operator
import os
from pathlib import Path
import select
import shutil
import subprocess
import threading
import time

from janim.png import dimensions, rgb_view


class VideoWriterError(RuntimeError):
    """An encoder exited, a pipe failed, or a write was cancelled."""


class _DiagnosticTail:
    def __init__(self):
        self.data = bytearray()
        self.lock = threading.Lock()

    def read(self, pipe):
        try:
            while chunk := pipe.read(8192):
                with self.lock:
                    self.data.extend(chunk)
                    if len(self.data) > 65536:
                        del self.data[:-65536]
        finally:
            pipe.close()

    def snapshot(self):
        with self.lock:
            return bytes(self.data)


def _budget(value, name):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return value


class VideoWriter:
    """Open one ffmpeg child; use write_frame(), finish(), and cancel().

Use as a context manager to finish on success and reap on an exception.
Only cancel() may be called from another thread. The supported encoder is
one direct process, not a daemon that leaves descendants holding its pipes.
The ffmpeg argument accepts an executable path or an argv prefix. A frame
is borrowed until write_frame returns; its owner must not mutate it meanwhile.
"""

    def __init__(
        self,
        path,
        width,
        height,
        *,
        fps=30,
        crf=23,
        preset="medium",
        encoder_threads=None,
        ffmpeg="ffmpeg",
        io_timeout=30.0,
        finish_timeout=None,
        cancel_event=None,
        environment=None,
        transparent=False,
    ):
        self._process = None
        self._thread = None
        self._state = "new"
        self._error = None
        self._owner = threading.get_ident()
        self.width, self.height = dimensions(width, height)
        self.transparent = bool(transparent)
        if not self.transparent and (self.width % 2 or self.height % 2):
            raise ValueError("yuv420p requires even width and height")
        try:
            self.fps = operator.index(fps)
        except TypeError as error:
            raise ValueError("fps must be a positive integer") from error
        if isinstance(fps, bool) or self.fps <= 0:
            raise ValueError("fps must be a positive integer")
        if not self.transparent and (isinstance(crf, bool) or not 0 <= operator.index(crf) <= 51):
            raise ValueError("crf must be an integer from 0 to 51")
        if not self.transparent and (not isinstance(preset, str) or not preset):
            raise ValueError("preset must be a nonempty string")
        if encoder_threads is not None and not self.transparent:
            if isinstance(encoder_threads, bool) or operator.index(encoder_threads) < 1:
                raise ValueError("encoder_threads must be a positive integer or None")
        self.io_timeout = _budget(io_timeout, "io_timeout")
        self.finish_timeout = None if finish_timeout is None else _budget(
            finish_timeout,
            "finish_timeout",
        )
        self._cancelled = cancel_event if cancel_event is not None else threading.Event()
        prefix = [os.fspath(ffmpeg)] if isinstance(ffmpeg, (str, bytes, os.PathLike)) else [os.fspath(value) for value in ffmpeg]
        if not prefix:
            raise ValueError("ffmpeg command must not be empty")
        executable = shutil.which(prefix[0])
        if executable is None:
            raise FileNotFoundError(f"ffmpeg executable not found: {ffmpeg}")
        self.path = Path(path)
        self.command = [
            executable,
            *prefix[1:],
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            # Input-side placement makes the container metadata deterministic.
            "-fflags",
            "+bitexact",
            "-f",
            "rawvideo",
            "-pixel_format",
            "rgb24",
            "-video_size",
            f"{self.width}x{self.height}",
            "-framerate",
            str(self.fps),
            "-i",
            "pipe:0",
            "-map_metadata",
            "-1",
            "-an",
            "-metadata:s:v:0",
            "encoder=",
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            str(crf),
            "-pix_fmt",
            "yuv420p",
            "-flags:v",
            "+bitexact",
            "-fps_mode",
            "cfr",
            str(self.path),
        ]
        if self.transparent:
            self.command = [
                executable,
                *prefix[1:],
                "-y",
                "-v",
                "error",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgba",
                "-s",
                f"{self.width}x{self.height}",
                "-r",
                str(self.fps),
                "-i",
                "-",
                "-c:v",
                "prores_ks",
                "-profile:v",
                "4444",
                "-pix_fmt",
                "yuva444p10le",
                str(self.path),
            ]
        if encoder_threads is not None and not self.transparent:
            position = self.command.index("-flags:v")
            options = ["-threads", str(encoder_threads)]
            if encoder_threads == 1:
                options.extend(
                    [
                        "-x264-params",
                        "threads=1:lookahead_threads=1:sliced_threads=0",
                    ],
                )
            self.command[position:position] = options
        self.frames_written = 0
        self._tail = _DiagnosticTail()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                bufsize=0,
                env=environment,
            )
            os.set_blocking(self._process.stdin.fileno(), False)
            self._thread = threading.Thread(
                target=self._tail.read,
                args=(self._process.stderr,),
                name="janim-encoder-stderr",
                daemon=True,
            )
            self._thread.start()
            self._state = "open"
        except BaseException:
            self.abort()
            raise

    @property
    def pid(self):
        return self._process.pid

    @property
    def stderr_tail(self):
        return self._tail.snapshot()

    def cancel(self):
        """Request cancellation; safe to call while another thread finishes."""
        self._cancelled.set()

    def _check_owner(self):
        if threading.get_ident() != self._owner:
            raise VideoWriterError("write and finish belong to the creating thread")

    def _check_wait(self, operation, deadline):
        if self._cancelled.is_set():
            raise VideoWriterError(f"video {operation} cancelled")
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError(f"video {operation} timed out")

    def _encoder_error(self, status):
        if self._thread is not None:
            self._thread.join(timeout=1)
        diagnostic = self.stderr_tail.decode(errors="replace")
        return VideoWriterError(f"ffmpeg exited with status {status}: {diagnostic}")

    def _cleanup(self):
        process = self._process
        if process is None:
            return
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()
        if self._thread is not None:
            self._thread.join(timeout=2)
            if self._thread.is_alive():
                raise VideoWriterError("encoder descendants kept stderr open after exit")
        elif process.stderr is not None:
            process.stderr.close()

    def _fail(self, error):
        self._error = error
        self._state = "failed"
        try:
            self._cleanup()
        except Exception as cleanup_error:
            error.add_note(f"encoder cleanup also failed: {cleanup_error}")

    def write_frame(self, pixels):
        """Write one borrowed RGB24 frame completely, then poll the child."""
        self._check_owner()
        if self._state != "open":
            raise VideoWriterError("video writer is not open")
        if self.transparent:
            try:
                view = memoryview(pixels).cast("B")
            except (TypeError, ValueError) as error:
                raise ValueError("RGBA pixels must be a contiguous byte buffer") from error
            if view.nbytes != self.width * self.height * 4:
                raise ValueError("RGBA frame size does not match the video dimensions")
        else:
            view = rgb_view(self.width, self.height, pixels)
        deadline = time.monotonic() + self.io_timeout
        offset = 0
        try:
            while offset < len(view):
                self._check_wait("write", deadline)
                status = self._process.poll()
                if status is not None:
                    raise self._encoder_error(status)
                descriptor = self._process.stdin.fileno()
                _, writable, _ = select.select([], [descriptor], [], 0.01)
                if not writable:
                    continue
                try:
                    count = os.write(descriptor, view[offset:])
                except BlockingIOError:
                    continue
                except BrokenPipeError as error:
                    status = self._process.poll()
                    if status is not None:
                        raise self._encoder_error(status) from error
                    raise VideoWriterError(f"ffmpeg input pipe failed for {self.path}: {error}") from error
                if count == 0:
                    raise VideoWriterError("ffmpeg input pipe made no progress")
                offset += count
            status = self._process.poll()
            if status is not None:
                raise self._encoder_error(status)
            self.frames_written += 1
        except BaseException as error:
            self._fail(error)
            raise
        return self.frames_written

    write = write_frame

    def finish(self):
        """Send EOF and reap; unlimited flush remains cancellable by default."""
        self._check_owner()
        if self._state == "finished":
            return self.frames_written
        if self._error is not None:
            raise self._error
        if self._state != "open":
            raise VideoWriterError("video writer is not open")
        try:
            status = self._process.poll()
            if status is not None:
                raise self._encoder_error(status)
            # Unbuffered nonblocking writes already acknowledged all input;
            # closing stdin cannot wait for a user-space buffer to flush.
            self._process.stdin.close()
            deadline = None if self.finish_timeout is None else time.monotonic() + self.finish_timeout
            while True:
                self._check_wait("finish", deadline)
                status = self._process.poll()
                if status is not None:
                    break
                self._cancelled.wait(0.01)
            if status != 0:
                raise self._encoder_error(status)
            self._cleanup()
            self._state = "finished"
        except BaseException as error:
            self._fail(error)
            raise
        return self.frames_written

    def abort(self):
        """Reap an unfinished encoder without claiming a complete video."""
        if self._state in ("finished", "failed"):
            return
        self._fail(VideoWriterError("video writer aborted"))

    def __enter__(self):
        return self

    def __exit__(self, kind, error, traceback):
        if error is None:
            self.finish()
        else:
            self.abort()
            for note in getattr(self._error, "__notes__", ()):
                error.add_note(note)

    def __del__(self):
        try:
            self.abort()
        except Exception:
            # Interpreter teardown may already have removed process helpers.
            pass
