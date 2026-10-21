"""janim — the command line: one ordinary process per call.

The vocabulary and every flag rule: no verb is a preview, `-w`/`-p`/`-s`
route it to a render, the LAST flag wins, a quality preset sets resolution
AND frame rate, `-n` numbers animations with the waits, `--from`/`--to`
speak frames or `1.5s`, and no flag is ever ignored in silence — a refusal
says why, and a flag a verb has no use for is refused by name (VERB_FLAGS).
There is no daemon: `ping`/`daemon`/`stop` are a noisy no-op, `check`/`finish`
say there is no daemon to look at, `states` explains that no snapshot outlives
a call, and `--from label` re-simulates the prefix.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

USAGE = """\
usage:
  janim scene.py [flags]             no verb = PREVIEW, manimgl-style:
                         -w          …write the video instead (= render)
                         -p          …write the video AND open it when done
                         -s          …one frame (= render -s)
  janim render  scene.py [-qm] [-r WxH] [--fps N] [-o out.mp4] [-j 4] [-p] [-t]
                         [--from X] [--to Y] [-n X,Y] [--samples N]
                         -n X,Y             animations X..Y — play/wait numbered from 1 — NOT frames
                         [-s [--to Y]]      one frame instead of a video
                         [--out_dir DIR]    put the output in DIR (mkdir -p'd);
                                            an absolute -o already says where and wins
                         [--only-cli]       accepted for scripts; there is no panel and no janim.cfg here
  janim frame   scene.py K out.png [-qm] [-r WxH] [--fps N] [-t] [--samples N] [-p] [--out_dir DIR]
                (re-simulates from t = 0: a late frame costs its whole prefix;
                 K past the last frame is an error, as `render -s --to K`)
  janim preview scene.py [-qm] [-r WxH] [--fps N] [-c] [--samples N]
                Esc/q=quit  space=pause  ,/.=frame  ←/→=±1 s  [ ]=animation
                PgUp/PgDn=checkpoint  Home=start  c=stop at checkpoints
  janim states  scene.py
  janim codecs
  janim check | finish | ping | daemon | stop   (there is no daemon: one line, exit 0)

Every <scene.py> also accepts `scene.py:Class` or `scene.py Class`; without a
name the file's only Scene subclass is used. The default output falls beside
the scene: `x.py:Intro` writes `x_Intro.mp4` (`.mov` under -t).

Quality presets — each sets BOTH the resolution and the frame rate:
    -qs   640x360   10 fps      -qh  1920x1080  60 fps
    -ql   854x480   15 fps      -qq  2560x1440  60 fps
    -qm  1280x720   30 fps      -qk  3840x2160  60 fps
-r and --fps win over whichever component they name, and the LAST flag wins:
`-qh -r 640x360` is 640x360 at 60 fps. Default: 1280x720 at 30. They glue to
-p and -w as Manim writes them: `-pqm` = -p -qm, `-wqh` = -w -qh.
"""

PRESETS = {
    "s": ((640, 360), 10),
    "l": ((854, 480), 15),
    "m": ((1280, 720), 30),
    "h": ((1920, 1080), 60),
    "q": ((2560, 1440), 60),
    "k": ((3840, 2160), 60),
}
MOTION_BLUR_RETIRED = (
    "error: --motion-blur is not supported (the renderer does not blur motion inside the render loop)."
)
NO_DAEMON = "OK no daemon: each janim call is one process and starts in tens of milliseconds"
NO_ORPHANS = "OK no daemon, so there is nothing to check or finish"
# What each verb has a use for; any other flag is refused by name, never dropped.
VERB_FLAGS = {
    "render": ("quality", "-r", "--fps", "-o", "-j", "-n", "--from", "--to", "-t", "-s", "--samples", "-w", "--out_dir", "-p"),
    "frame": ("quality", "-r", "--fps", "-t", "--samples", "--out_dir", "-p"),
    "preview": ("quality", "-r", "--fps", "-c", "--samples"),     # -t, -w and -p are refused before, with a reason of their own
    "states": (),
}
FLAG_PURPOSE = {
    "quality": "a quality preset sets a resolution and a frame rate",
    "-r": "it sets the resolution of a picture",
    "--fps": "it sets the frame rate of a simulation",
    "-o": "it names the video a render writes",
    "-j": "it splits a video across processes",
    "-n": "it selects animations of a video",
    "--from": "it selects where a video starts",
    "--to": "it selects where a video ends",
    "-t": "it asks for an alpha channel",
    "-s": "it turns a render into one frame",
    "--samples": "it sets the antialiasing of a picture",
    "-w": "it turns a preview into a render",
    "--out_dir": "it says where an output is written",
    "-p": "it opens what was written",
    "-c": "it stops a live preview at its checkpoints",
}


class CLIExit(Exception):
    """A message for the user and the exit code that goes with it."""

    def __init__(self, code, message="", *, usage=False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.usage = usage


class Reply(str):
    """The line a verb answers with; `path` is what it wrote, as data, and `open` whether -p asked for it."""

    def __new__(cls, text, path=None, open=False):
        reply = super().__new__(cls, text)
        reply.path = path
        reply.open = open
        return reply


class Flags:
    def __init__(self):
        self.given = []
        self.resolution = (1280, 720)
        self.fps = 30
        self.output = None
        self.jobs = 1
        self.from_ = None
        self.to = None
        self.nrange = None
        self.open = False
        self.stop_at_checkpoints = False
        self.transparent = False
        self.still = False
        self.samples = 0
        self.write = False
        self.out_dir = None
        self.positional = []


def _integer(text, flag, minimum=None):
    try:
        value = int(text)
    except (TypeError, ValueError):
        raise CLIExit(1, f"ERR {flag} wants an integer (got «{text}»)") from None
    if minimum is not None and value < minimum:
        raise CLIExit(1, f"ERR {flag} wants an integer ≥ {minimum} (got «{text}»)")
    return value


def parse_resolution(text):
    parts = str(text).lower().split("x")
    if len(parts) != 2 or not all(part.isdigit() and int(part) > 0 for part in parts):
        raise CLIExit(1, f"ERR -r wants WxH (got «{text}»)")
    return int(parts[0]), int(parts[1])


def parse_flags(args):
    """The flag loop: plain assignments, so the LAST flag wins."""
    flags = Flags()
    args = list(args)
    index = 0

    def value(flag):
        nonlocal index
        if index + 1 >= len(args):
            raise CLIExit(1, f"ERR {flag} needs a value")
        index += 1
        return args[index]

    def given(*names):
        # the canonical name of what was asked, beside the spelling the user typed
        flags.given.extend((name, arg) for name in names)

    while index < len(args):
        arg = args[index]
        if arg in ("-r", "--resolution"):
            given("-r")
            flags.resolution = parse_resolution(value(arg))
        elif arg == "--fps":
            given("--fps")
            flags.fps = _integer(value(arg), "--fps", 1)
        elif len(arg) == 3 and arg.startswith("-q") and arg[2] in PRESETS:
            given("quality")
            flags.resolution, flags.fps = PRESETS[arg[2]]
        elif len(arg) == 4 and arg.startswith("-pq") and arg[3] in PRESETS:
            given("-p", "quality")
            flags.open = True
            flags.resolution, flags.fps = PRESETS[arg[3]]
        elif len(arg) == 4 and arg.startswith("-wq") and arg[3] in PRESETS:
            given("-w", "quality")
            flags.write = True
            flags.resolution, flags.fps = PRESETS[arg[3]]
        elif arg in ("-o", "--output"):
            given("-o")
            flags.output = value(arg)
        elif arg in ("-j", "--jobs", "--nprocs"):
            given("-j")
            flags.jobs = _integer(value(arg), arg, 1)
        elif arg == "-n":
            given("-n")
            flags.nrange = value(arg)
        elif arg.startswith("-n") and len(arg) > 2 and arg[2].isdigit():
            given("-n")
            flags.nrange = arg[2:]
        elif arg == "--from":
            given("--from")
            flags.from_ = value(arg)
        elif arg == "--to":
            given("--to")
            flags.to = value(arg)
        elif arg == "--motion-blur":
            raise CLIExit(2, MOTION_BLUR_RETIRED)
        elif arg in ("-t", "--transparent"):
            given("-t")
            flags.transparent = True
        elif arg in ("-s", "--save-frame"):
            given("-s")
            flags.still = True
        elif arg == "--samples":
            given("--samples")
            text = value(arg)
            flags.samples = _integer(text, "--samples", 0)
            if flags.samples not in (0, 1, 4):
                raise CLIExit(1, f"ERR --samples wants 0 (the default, 4), 1 or 4 (got «{text}»)")
        elif arg in ("-w", "--write"):
            given("-w")
            flags.write = True
        elif arg in ("--out_dir", "--out-dir"):
            given("--out_dir")
            flags.out_dir = value(arg)
        elif arg in ("-p", "--play"):
            given("-p")
            flags.open = True
        elif arg in ("-c", "--stop-at-checkpoints"):
            given("-c")
            flags.stop_at_checkpoints = True
        elif arg in ("--no-tui", "--only-cli"):
            pass  # no panel and no janim.cfg to skip; accepted for scripts
        elif arg in ("-h", "--help"):
            raise CLIExit(0, USAGE.rstrip("\n"))
        elif arg.startswith("-") and arg != "-":
            raise CLIExit(1, f"ERR unknown flag: {arg}", usage=True)
        else:
            flags.positional.append(arg)
        index += 1
    return flags


def check_flags(verb, flags):
    """Refuse, by name, the first flag the verb has no use for."""
    allowed = VERB_FLAGS[verb]
    for name, spelled in flags.given:
        if name not in allowed:
            takes = ", ".join("-qs…-qk" if item == "quality" else item for item in allowed) or "no flag"
            raise CLIExit(1, f"ERR {verb} does not take {spelled}: {FLAG_PURPOSE[name]}, and {verb} takes {takes}")


def parse_anim_range(text):
    """`-n X,Y` → range; `-n X` → X to the end; None when absent; 'bad' otherwise."""
    if text is None or text == "" or text == "-":
        return None
    parts = text.split(",")
    if len(parts) > 2:
        return "bad"
    try:
        first = int(parts[0].strip())
    except ValueError:
        return "bad"
    if first < 1:
        return "bad"
    if len(parts) == 1:
        return range(first, sys.maxsize)
    try:
        last = int(parts[1].strip())
    except ValueError:
        return "bad"
    if last < first:
        return "bad"
    return range(first, last + 1)


def parse_frame(text, fps):
    """A frame number, or seconds when it ends in `s`; None if neither."""
    text = str(text)
    if text.endswith("s"):
        try:
            seconds = float(text[:-1])
        except ValueError:
            return None
        return max(1, round(seconds * fps))
    try:
        return int(text)
    except ValueError:
        return None


def scene_from_positionals(positional):
    """(path, name) from `x.py:Name` or `x.py Name`; the rest is returned too."""
    from janim.scene.address import scene_address

    path, name = scene_address(positional[0])
    rest = positional[1:]
    if not name and rest and rest[0].isidentifier() and not rest[0].endswith(".py"):
        name, rest = rest[0], rest[1:]
    return path, name, rest


def still_path(video):
    return str(Path(video).with_suffix(".png"))


def resolve_output(flags, path, name):
    """Beside the scene, `x_Name`, `.mov` under -t, --out_dir joins or loses."""
    extension = ".mov" if flags.transparent else ".mp4"
    if flags.output is None:
        base = str(Path(path).with_suffix("")) + (f"_{name}" if name else "")
        output = os.path.join(flags.out_dir, os.path.basename(base) + extension) if flags.out_dir else base + extension
    elif flags.out_dir:
        if os.path.isabs(flags.output):
            print(f"WARN --out_dir ignored: -o {flags.output} is absolute and already says where", file=sys.stderr, flush=True)
            output = flags.output
        else:
            output = os.path.join(flags.out_dir, flags.output)
    else:
        output = flags.output
    output = os.path.abspath(output)
    if flags.out_dir:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
    return output


def open_output(path):
    """Open a finished render with the desktop's default player; warn without one."""
    order = ("open", "xdg-open") if sys.platform == "darwin" else ("xdg-open", "open")
    opener = next((name for name in order if shutil.which(name)), None)
    if opener is None:
        print(f"WARN -p: no desktop opener found for {path}", file=sys.stderr, flush=True)
        return
    try:
        subprocess.Popen([opener, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        print(f"WARN -p: could not open {path}", file=sys.stderr, flush=True)


def ffmpeg_command():
    return os.environ.get("JANIM_FFMPEG", "ffmpeg")


def encoder_settings():
    """The encoder's crf and x264 threads (defaults: 23, and x264's own).

    JANIM_CRF and JANIM_ENCODER_THREADS pick the quality and the thread count
    of the encoder (for example crf 0 for a lossless file, one thread for a
    reproducible container); they change no pixel, only the container the CLI
    writes.
    """
    crf = os.environ.get("JANIM_CRF")
    threads = os.environ.get("JANIM_ENCODER_THREADS")
    try:
        crf = 23 if crf in (None, "") else int(crf)
        threads = None if threads in (None, "") else int(threads)
    except ValueError as error:
        raise CLIExit(1, f"ERR JANIM_CRF/JANIM_ENCODER_THREADS want integers ({error})") from None
    return crf, threads


def load_scene(path, name):
    from janim.scene.address import load_scene_class

    try:
        return load_scene_class(path, name)
    except LookupError as error:
        raise CLIExit(1, f"ERR {error}") from None
    except Exception as error:
        traceback.print_exc()
        raise CLIExit(1, f"ERR {type(error).__name__}: {error}") from None


def scene_kwargs(flags):
    crf, threads = encoder_settings()
    return {
        "fps": flags.fps,
        "resolution": flags.resolution,
        "transparent": flags.transparent,
        "samples": flags.samples,
        "ffmpeg": ffmpeg_command(),
        "crf": crf,
        "encoder_threads": threads,
    }


def render_one_frame(cls, frame, output, flags):
    from janim.scene.scene import render_frame

    render_frame(
        cls,
        (frame - 0.5) / flags.fps,
        fps=flags.fps,
        resolution=flags.resolution,
        transparent=flags.transparent,
        samples=flags.samples,
        png=output,
    )
    return Reply(f"OK {output}", output, flags.open)


def render_go(flags):
    from janim.scene.scene import count_frames, render_from, render_parallel, render_segment

    if not flags.positional:
        raise CLIExit(1, "ERR render needs a scene")
    check_flags("render", flags)
    path, name, _ = scene_from_positionals(flags.positional)
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise CLIExit(1, f"ERR no such file: {path}")
    output = resolve_output(flags, path, name)
    anim_range = parse_anim_range(flags.nrange)
    if anim_range == "bad":
        raise CLIExit(1, f"ERR -n wants X or X,Y with 1 ≤ X ≤ Y (got «{flags.nrange}»)")
    from_ = flags.from_ or ""
    to = flags.to or ""
    cls = load_scene(path, name)
    common = scene_kwargs(flags)
    if flags.still:
        if flags.jobs > 1:
            raise CLIExit(1, "ERR -s cannot be combined with -j: one frame is not a video, so there is nothing to split")
        if from_:
            raise CLIExit(1, "ERR -s cannot be combined with --from: a still is addressed absolutely, so say which frame you want with --to instead")
        if anim_range is not None:
            raise CLIExit(1, "ERR -s cannot be combined with -n: `-n` selects ANIMATIONS and a still is one frame — pick it with --to (a frame, or 1.5s)")
        total, _ = count_frames(cls, fps=flags.fps, resolution=flags.resolution)
        frame = total
        if to:
            requested = parse_frame(to, flags.fps)
            if requested is None:
                raise CLIExit(1, f"ERR --to wants a frame or seconds (got «{to}»)")
            if requested > total and total > 0:
                raise CLIExit(1, f"ERR --to {to} is past the end ({total} frames)")
            frame = requested
        return render_one_frame(cls, max(frame, 1), still_path(output), flags)
    if flags.transparent and flags.jobs > 1:
        raise CLIExit(1, "ERR -t cannot be combined with -j: the farm is for long renders and ProRes 4444 is ~137× h264, so the two do not mix by design")
    if flags.jobs > 1:
        if from_:
            raise CLIExit(1, "ERR -j and --from cannot be combined: the farm splits by frame ranges and needs the total")
        if anim_range is not None or to:
            raise CLIExit(1, "ERR -j cannot be combined with -n/--to: the farm partitions the frames, and a worker whose share falls outside the range would produce an empty segment")
        total, _ = count_frames(cls, fps=flags.fps, resolution=flags.resolution)
        if total == 0:
            raise CLIExit(1, f"ERR the scene has no animations, so there is nothing to split across {flags.jobs} processes — render it without -j and you get a still")
        limit = os.cpu_count() or 1
        if flags.jobs > limit:
            raise CLIExit(1, f"ERR -j {flags.jobs} asks for more processes than this machine has threads ({limit}): each worker is a Python process with its own device")
        crf, _ = encoder_settings()
        try:
            render_parallel(
                path,
                output,
                n=flags.jobs,
                frames_total=total,
                fps=flags.fps,
                resolution=flags.resolution,
                crf=crf,
                samples=flags.samples,
                scene_name=name,
                ffmpeg=ffmpeg_command(),
            )
        except ValueError as error:
            raise CLIExit(1, f"ERR {error}") from None
        return Reply(f"OK {output} ({total} frames, {flags.jobs} processes)", output, flags.open)
    first = parse_frame(from_, flags.fps) if from_ else None
    if to or first is not None:
        if from_ and first is None:
            raise CLIExit(1, f"ERR --to takes a frame or seconds --from, not the label «{from_}» (a label has no frame number until the scene runs)")
        if first is not None and first < 1:
            raise CLIExit(1, f"ERR --from wants a frame ≥ 1 (got «{from_}»)")
        total, _ = count_frames(cls, fps=flags.fps, resolution=flags.resolution)
        first_frame = 1 if first is None else first
        if first_frame > total:
            raise CLIExit(1, f"ERR --from {from_} is past the end ({total} frames)")
        last_frame = total
        if to:
            last = parse_frame(to, flags.fps)
            if last is None:
                raise CLIExit(1, f"ERR --to wants a frame or seconds (got «{to}»)")
            if last < first_frame:
                before = f"--from {from_}" if from_ else "the first frame"
                raise CLIExit(1, f"ERR --to {to} lands before {before}")
            last_frame = min(last, total)
        try:
            render_segment(cls, output, frames=range(first_frame, last_frame + 1), anim_range=anim_range, **common)
        except ValueError as error:
            raise CLIExit(1, f"ERR {error}") from None
        return Reply(f"OK {output} (frames {first_frame}:{last_frame} of {total})", output, flags.open)
    if from_:
        try:
            scene = render_from(cls, output, from_, scene_path=path, scene_name=name or cls.__name__, anim_range=anim_range, simulate_prefix=True, **common)
        except ValueError as error:
            hint = ""
            try:
                float(from_)
            except ValueError:
                pass
            else:
                hint = f" — a time is written with its unit: --from {from_}s"
            raise CLIExit(1, f"ERR {error}{hint}") from None
        detail = "skipped the prefix" if scene.skipped_prefix else "prefix simulated without drawing"
        return Reply(f"OK {output} (checkpoint {from_}, {detail})", output, flags.open)
    try:
        scene = cls(output=output, anim_range=anim_range, progress="auto", **common)
    except ValueError as error:
        raise CLIExit(1, f"ERR {error}") from None
    scene.scene_path = path
    scene.scene_name = name or cls.__name__
    try:
        scene.run()
    except ValueError as error:
        if "selection drew nothing" in str(error):
            raise CLIExit(1, f"ERR -n {flags.nrange} drew nothing: the scene has {scene.anim_index} animations") from None
        raise CLIExit(1, f"ERR {error}") from None
    if scene.frames == 0:
        return Reply(f"OK {scene.rendered_path} (still: the scene has no animations)", str(scene.rendered_path), flags.open)
    if anim_range is None:
        return Reply(f"OK {output}", output, flags.open)
    last = min(anim_range.stop - 1, scene.anim_index)
    return Reply(f"OK {output} (animations {anim_range.start}:{last} of {scene.anim_index})", output, flags.open)


def frame_go(flags):
    from janim.scene.scene import count_frames

    if len(flags.positional) < 3:
        raise CLIExit(1, "ERR frame <scene.py> <K> <out.png>")
    check_flags("frame", flags)
    path, name, rest = scene_from_positionals(flags.positional)
    if len(rest) < 2:
        raise CLIExit(1, "ERR frame <scene.py> <K> <out.png>")
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise CLIExit(1, f"ERR no such file: {path}")
    frame = _integer(rest[0], "frame", 1)
    output = rest[1]
    if flags.out_dir and not os.path.isabs(output):
        output = os.path.join(flags.out_dir, output)
    output = os.path.abspath(output)
    if flags.out_dir:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
    cls = load_scene(path, name)
    # the rule of `render -s --to K`: a frame the scene never reaches is an error, not the final state
    total, _ = count_frames(cls, fps=flags.fps, resolution=flags.resolution)
    if frame > total and total > 0:
        raise CLIExit(1, f"ERR frame {frame} is past the end ({total} frames)")
    return render_one_frame(cls, frame, output, flags)


def preview_go(flags):
    if not flags.positional:
        raise CLIExit(1, "ERR preview needs a scene")
    if flags.transparent:
        raise CLIExit(1, "ERR -t makes no sense for preview: a live window has no alpha to show. Use it on 'janim render' or 'janim frame'.")
    if flags.write or flags.open:
        raise CLIExit(1, "ERR -w/-p write a video, but 'preview' opens a window. Drop the\n    verb («janim scene.py -w») or use 'janim render'.")
    check_flags("preview", flags)
    path, name, _ = scene_from_positionals(flags.positional)
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise CLIExit(1, f"ERR no such file: {path}")
    from janim.interactive.live import live

    address = f"{path}:{name}" if name else path
    session = live(
        address,
        fps=flags.fps,
        resolution=flags.resolution,
        stop_at_checkpoints=flags.stop_at_checkpoints,
        samples=flags.samples,
    )
    where = f"{session.idx}/{session.total}" if session.total > 0 else str(session.idx)
    return f"OK preview closed (frame {where}, {session.hits} cache hits)"


def states_go(args):
    flags = parse_flags(args)
    if not flags.positional:
        raise CLIExit(1, "ERR states needs a scene")
    check_flags("states", flags)
    path, _, _ = scene_from_positionals(flags.positional)
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise CLIExit(1, f"ERR no such file: {path}")
    return (
        f"OK (no checkpoints recorded for {path}: the Python CLI is one process per call and no snapshot "
        "outlives it — `--from <label>` re-simulates the prefix without drawing instead)"
    )


def codecs_go():
    try:
        output = subprocess.run([ffmpeg_command(), "-hide_banner", "-encoders"], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise CLIExit(1, f"ERR codecs: {error}") from None
    encoders = [line.strip() for line in output.splitlines() if line.strip().startswith("V")]

    def has(pattern):
        return any(pattern in line for line in encoders)

    fields = {
        "video_encoders": len(encoders),
        "libx264": has("libx264"),
        "libx265": has("libx265"),
        "av1": has("libaom") or has("libsvtav1") or has("librav1e"),
        "nvenc": has("nvenc"),
        "vaapi": has("vaapi"),
    }
    return "OK " + " ".join(f"{key}={str(value).lower() if isinstance(value, bool) else value}" for key, value in fields.items())


def dispatch(argv):
    if not argv:
        raise CLIExit(0, USAGE.rstrip("\n"))
    command, args = argv[0], argv[1:]
    if command in ("-h", "--help", "help"):
        raise CLIExit(0, USAGE.rstrip("\n"))
    if command in ("ping", "stop"):
        return NO_DAEMON
    if command == "daemon":
        if args and args[0] not in ("start", "stop", "status"):
            raise CLIExit(1, "ERR daemon: start|stop|status")
        return NO_DAEMON
    if command in ("check", "finish"):
        return NO_ORPHANS
    if command == "codecs":
        return codecs_go()
    if command == "states":
        return states_go(args)
    if command == "frame":
        return frame_go(parse_flags(args))
    if command == "render":
        return render_go(parse_flags(args))
    if command == "preview":
        return preview_go(parse_flags(args))
    if command.endswith(".py") or ".py:" in command or command.startswith("-"):
        flags = parse_flags(argv)
        if flags.write or flags.open or flags.still:
            return render_go(flags)
        return preview_go(flags)
    raise CLIExit(1, f"ERR unknown command: {command}", usage=True)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    try:
        reply = dispatch(argv)
    except CLIExit as exit_request:
        stream = sys.stdout if exit_request.code == 0 else sys.stderr
        if exit_request.message:
            print(exit_request.message, file=stream, flush=True)
        if exit_request.usage:
            print(USAGE.rstrip("\n"), file=sys.stderr, flush=True)
        return exit_request.code
    except KeyboardInterrupt:
        return 130
    print(reply, flush=True)
    # what was written travels as data: a path with a space in it is one path
    if getattr(reply, "open", False) and reply.path:
        open_output(reply.path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
