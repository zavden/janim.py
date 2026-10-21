"""One-frame-behind readback with bounded converter and encoder workers.

Two staging buffers, three padded CPU buffers and three tight CPU buffers. Only the render thread touches the GPU.
The encoder converts premultiplied RGBA once on the transparent route.
"""

import queue
import threading

from janim.video import VideoWriter, VideoWriterError
from janim.core.colorspace import unpremultiply_rgba
from .targets import copy_target_to_buffer, create_staging, crop_rows, mapped_read, padded_bytes_per_row


class FramePipeline:
    """Stream opaque frames with an optional short-lived observation callback.

    ``tap(index, data)`` runs on the converter thread before encoding. Its
    read-only memoryview borrows one of three reusable tight buffers; it is
    not a snapshot. Hash or copy inside the callback, keep it short, and do
    not mutate the underlying buffer or retain the view for later inspection.
    """

    def __init__(
        self,
        gpu,
        target,
        path,
        *,
        fps=60,
        crf=23,
        preset="medium",
        encoder_threads=None,
        ffmpeg="ffmpeg",
        tap=None,
        io_timeout=30.0,
        finish_timeout=None,
        environment=None,
        writer_factory=VideoWriter,
        transparent=False,
    ):
        target._check_copyable()
        if target.gpu is not gpu:
            raise ValueError("pipeline target belongs to another GPU")
        self.gpu = gpu
        self.target = target
        self.width, self.height = target.width, target.height
        self.transparent = bool(transparent)
        self.channels = 4 if self.transparent else 3
        self.bpr = padded_bytes_per_row(self.width)
        self._owner = threading.get_ident()
        self._error = None
        self._error_lock = threading.Lock()
        self._cancelled = threading.Event()
        self._ready = threading.Event()
        self._writer = None
        self.closed = False
        self.k = 0
        self.frames_harvested = 0
        self.frames_written = 0
        self.tap = tap
        self.staging = []
        self.indices = [None, None]
        self.padded = [bytearray(self.bpr * self.height) for _ in range(3)]
        self.tight = [bytearray(self.channels * self.width * self.height) for _ in range(3)]
        self._free = queue.Queue(maxsize=3)
        self._filled = queue.Queue(maxsize=3)
        self._free_tight = queue.Queue(maxsize=3)
        self._filled_tight = queue.Queue(maxsize=3)
        for index in range(3):
            self._free.put(index)
            self._free_tight.put(index)
        self._writer_options = {
            "fps": fps,
            "crf": crf,
            "preset": preset,
            "encoder_threads": encoder_threads,
            "ffmpeg": ffmpeg,
            "io_timeout": io_timeout,
            "finish_timeout": finish_timeout,
            "cancel_event": self._cancelled,
            "environment": environment,
        }
        if self.transparent:
            self._writer_options["transparent"] = True
        self._encoder = threading.Thread(
            target=self._encode,
            args=(writer_factory, path),
            name="janim-frame-encoder",
        )
        self._converter = threading.Thread(target=self._convert, name="janim-frame-converter")
        try:
            for _ in range(2):
                self.staging.append(create_staging(gpu, self.bpr * self.height))
            self._encoder.start()
            self._ready.wait()
            self._check_error()
            self._converter.start()
        except BaseException as error:
            self._fail(error)
            self._cleanup()
            self.closed = True
            raise

    def _check_error(self):
        if self._error is not None:
            raise self._error
        if self._cancelled.is_set():
            raise VideoWriterError("frame pipeline cancelled")

    def _fail(self, error):
        with self._error_lock:
            if self._error is None:
                self._error = error
        self._cancelled.set()

    def _take(self, channel):
        while True:
            self._check_error()
            try:
                return channel.get(timeout=0.05)
            except queue.Empty:
                pass

    def _put(self, channel, value):
        while True:
            self._check_error()
            try:
                channel.put(value, timeout=0.05)
                return
            except queue.Full:
                pass

    def _convert(self):
        try:
            while (item := self._take(self._filled)) is not None:
                frame, source = item
                destination = self._take(self._free_tight)
                crop_rows(
                    self.padded[source],
                    self.tight[destination],
                    self.width,
                    self.height,
                    self.channels,
                )
                if self.tap is not None:
                    self.tap(frame, memoryview(self.tight[destination]).toreadonly())
                self._put(self._free, source)
                self._put(self._filled_tight, destination)
            self._put(self._filled_tight, None)
        except BaseException as error:
            self._fail(error)

    def _encode(self, factory, path):
        writer = None
        try:
            writer = factory(path, self.width, self.height, **self._writer_options)
            self._writer = writer
            self._ready.set()
            while (index := self._take(self._filled_tight)) is not None:
                if self.transparent:
                    unpremultiply_rgba(self.tight[index])
                writer.write_frame(self.tight[index])
                self.frames_written += 1
                self._put(self._free_tight, index)
            writer.finish()
        except BaseException as error:
            self._fail(error)
        finally:
            if writer is not None:
                writer.abort()
            self._ready.set()

    def _assert_owner(self):
        if threading.get_ident() != self._owner:
            raise RuntimeError("pipeline operations belong to the render thread; use cancel()")

    def _harvest(self, frame):
        destination = self._take(self._free)
        slot = frame % 2
        with mapped_read(self.gpu, self.staging[slot], self.indices[slot], self.bpr * self.height) as pixels:
            memoryview(self.padded[destination])[:] = pixels
        self._put(self._filled, (frame, destination))
        self.frames_harvested += 1

    def enqueue(self):
        self._assert_owner()
        self._check_error()
        if self.closed:
            raise VideoWriterError("frame pipeline is closed")
        try:
            slot = self.k % 2
            self.indices[slot] = copy_target_to_buffer(self.gpu, self.target, self.staging[slot])
            if self.k:
                self._harvest(self.k - 1)
            self.k += 1
            return self
        except BaseException as error:
            self._fail(error)
            self._cleanup()
            self.closed = True
            raise

    def cancel(self):
        """Request cancellation from any thread; close/abort joins on the owner."""
        self._cancelled.set()

    def _cleanup(self):
        for worker in (self._converter, self._encoder):
            if worker.ident is not None:
                worker.join()
        for staging in self.staging:
            staging.destroy()
        self.staging.clear()

    def close_pipeline(self, *, drain=True):
        self._assert_owner()
        if self.closed:
            self._check_error()
            return self.frames_written
        try:
            self._check_error()
            if self.k and drain:
                self._harvest(self.k - 1)
            self._put(self._filled, None)
            self._converter.join()
            self._encoder.join()
            self._check_error()
            if self.frames_written != self.frames_harvested:
                raise VideoWriterError("the encoder did not receive every harvested frame")
        except BaseException as error:
            self._fail(error)
            raise
        finally:
            self._cleanup()
            self.closed = True
        return self.frames_written

    close = close_pipeline

    def abort(self):
        self._assert_owner()
        self.cancel()
        self._cleanup()
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, kind, error, traceback):
        if error is None:
            self.close_pipeline()
        else:
            self.abort()
