"""Course 1 · 2.6 — Importing audio

    self.add_sound("clap.wav", time=None, gain=0.0)

`time` defaults to NOW — wherever the scene's clock has got to — and `gain`
is in dB. The tracks are queued and mixed into the mp4 when the scene
CLOSES: one ffmpeg call with `adelay` per track, `amix` to add them and
`-c:v copy`, so not a single video frame is re-encoded. The render loop does
not change at all, which is how the video stays deterministic while
carrying sound.

It needs an `output=` mp4. On a headless render with no output (a frame-only
render, for instance) it warns and carries on, because
there is nowhere to put the audio.

This lesson SYNTHESISES its wav — a tone written by 20 lines of Python is
a better lesson than a file you cannot inspect.

    python examples/tutorial/c1_02_config_and_assets/06_audio_import.py
"""

import math
from pathlib import Path
import struct

from janim import *

PREVIEW_T = 1.4


def write_wav(path, samples, rate=44100):
    """A 16-bit mono PCM wav, by hand: 44 bytes of RIFF header and the samples.

    `struct`'s `<` spells the byte order out rather than trusting the
    machine's."""
    n = len(samples)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as io:
        io.write(b"RIFF")
        io.write(struct.pack("<I", 36 + 2 * n))
        io.write(b"WAVE")
        io.write(b"fmt ")
        io.write(struct.pack("<I", 16))
        io.write(struct.pack("<H", 1))              # 1 = PCM
        io.write(struct.pack("<H", 1))              # mono
        io.write(struct.pack("<I", rate))
        io.write(struct.pack("<I", 2 * rate))       # bytes per second
        io.write(struct.pack("<H", 2))              # block align
        io.write(struct.pack("<H", 16))             # bits per sample
        io.write(b"data")
        io.write(struct.pack("<I", 2 * n))
        for s in samples:
            io.write(struct.pack("<h", max(-32768, min(32767, round(32767 * s)))))
    return path


def pluck(freq, seconds=0.45, rate=44100):
    """A plucked note: a sine at `freq` Hz under an exponential decay."""
    n = round(seconds * rate)
    return [
        0.6 * math.sin(2 * math.pi * freq * k / rate) * math.exp(-3.5 * k / n)
        for k in range(n)
    ]


class AudioImport(Scene):
    def construct(self):
        title = Text(
            "sound is muxed at the end, not rendered",
            size=0.48,
            color=GREY_A,
        )
        title.to_edge(UP, buff=0.4)
        self.add(title)

        lesson = Path(__file__).resolve()
        here = lesson.parents[1] / "output" / lesson.parent.name
        notes = [
            ("A4", 440.0, "#58C4DD"),
            ("C#5", 554.37, "#E8A33D"),
            ("E5", 659.25, "#7FDD58"),
        ]

        bars = VGroup()
        for k, (name, freq, colour) in enumerate(notes, start=1):
            bar = Rectangle(width=1.4, height=0.6 + 0.5 * k)
            bar.set_fill(colour, 1.0)
            bar.set_stroke(opacity=0)
            bar.move_to((-2.6 + 2.6 * (k - 1), -0.6 + 0.25 * k, 0))
            label = Text(name, size=0.4, color=GREY_A)
            label.next_to(bar, DOWN, buff=0.2)
            bars.add(VGroup(bar, label))
        self.add(bars)

        for k, (name, freq, _) in enumerate(notes):
            wav = write_wav(here / f"note_{name}.wav", pluck(freq))
            # `time` left out = NOW: the note is queued at the scene's clock,
            # so it lands exactly when this animation starts.
            self.add_sound(wav, gain=-3.0)
            self.play(GrowFromEdge(bars[k], DOWN), run_time=0.5)
            self.wait(0.25)
        self.wait(0.6)
        print(f"queued sounds: {len(self.sounds)} — they are mixed in when the scene closes")


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    AudioImport(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out, "   (play it: the mp4 has a track)")
