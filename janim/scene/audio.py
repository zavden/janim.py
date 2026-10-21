"""Mix scene sound cues without re-encoding or shortening the video."""

import os
from pathlib import Path
import subprocess
import warnings


def resolve_sound(path):
    path = Path(path)
    for candidate in (path, Path(str(path) + ".wav"), Path(str(path) + ".mp3")):
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(f"sound file not found: {path} (also tried .wav and .mp3)")


def mux_sounds(path, sounds, duration, *, ffmpeg="ffmpeg", environment=None):
    if path is None:
        warnings.warn("add_sound: this scene has no video output; sounds were ignored", RuntimeWarning, stacklevel=2)
        return None
    path = Path(path)
    if not path.is_file():
        return path
    prefix = [os.fspath(ffmpeg)] if isinstance(ffmpeg, (str, bytes, os.PathLike)) else list(map(os.fspath, ffmpeg))
    inputs, filters, labels = [], [], []
    for index, (file, at, gain) in enumerate(sounds, 1):
        inputs.extend(["-i", str(file)])
        delay = max(0, round(1000 * at))
        label = f"a{index}"
        filters.append(f"[{index}:a]adelay={delay}|{delay},volume={gain}dB[{label}]")
        labels.append(f"[{label}]")
    mix = labels[0] + "anull[aout]" if len(labels) == 1 else "".join(labels) + f"amix=inputs={len(labels)}:normalize=0[aout]"
    temporary = Path(str(path) + ".withsound.mp4")
    command = [
        *prefix,
        "-y", "-v", "error", "-i", str(path),
        *inputs,
        "-filter_complex", ";".join([*filters, mix]),
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac",
        "-t", str(round(float(duration), 6)),
        str(temporary),
    ]
    try:
        result = subprocess.run(command, env=environment, capture_output=True, check=False)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors="replace"))
        os.replace(temporary, path)
    except (OSError, RuntimeError) as error:
        temporary.unlink(missing_ok=True)
        warnings.warn(f"add_sound: audio mux failed; the video is intact: {error}", RuntimeWarning, stacklevel=2)
    return path
