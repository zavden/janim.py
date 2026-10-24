# The CLI, live window and render farm

This page describes `bin/janim`, the live preview window, checkpoints and
parallel rendering (`-j N`).

## `bin/janim`: one process per call

```text
janim scene.py [flags]            no verb = PREVIEW; -w writes, -p writes and opens, -s one frame
janim render  scene.py [flags]    the whole video (or a still with -s)
janim frame   scene.py K out.png  ONE frame: K ↔ t = (K − ½)/fps (re-simulates from t = 0; K beyond the end is an error)
janim preview scene.py [-qm] [-r WxH] [--fps N] [-c] [--samples N]
janim states  scene.py            (no snapshots outside the process: it says so)
janim codecs                      what the CLI's ffmpeg can do
janim check | finish | ping | daemon | stop     one-line no-op, exit 0
```

There is no daemon: each call is an ordinary process that starts in tens of
milliseconds. The `check`, `finish`, `ping`, `daemon` and `stop` verbs exist
only so scripts that call them do not fail.

Flags: `-r WxH`/`--resolution`, `--fps N`, `-q{s,l,m,h,q,k}` (resolution **and**
fps: 640×360@10 · 854×480@15 · 1280×720@30 · 1920×1080@60 · 2560×1440@60 ·
3840×2160@60), `-pq…`/`-wq…` (never `-qmp`), `-o`, `-j N`, `-n X,Y` and `-nX,Y`
(animations start at 1, `wait` calls count; `-n 3` = through the end), `--from`
(label, frame or `1.5s`), `--to`, `-t` (ProRes 4444 in `.mov`, RGBA PNG),
`-s [--to X]` (only the last frame; `--to` selects it), `--samples` (0/1/4; 0
means 4), `--out_dir`, `-p`, `-c`, `--only-cli`/`--no-tui` (accepted, do
nothing: there is no panel or `janim.cfg`). **The last flag wins**:
`-qh -r 640x360` means 640×360 at 60 fps. CLI defaults: 1280×720@30,
`samples 0`; a manually constructed `Scene(...)` still uses 1920×1080@60.
Precedence is `flag > class attributes > defaults`: it is resolved by
constructing the scene with the CLI kwargs.

Output: without `-o`, next to the scene (`x.py:Intro` → `x_Intro.mp4`; with
`-t`, `.mov`); `--out_dir D` performs `mkdir -p`, joins a relative `-o`
and yields with a `WARN` to an absolute one. Name a scene as `file.py:Class`
or `file.py Class`; without a name, the file's only `Scene` subclass is used.
The result line is `OK <path> [(detail)]` — `(animations A:B of N)`,
`(frames A:B of T)`, `(checkpoint L, prefix simulated without drawing)`,
`(N frames, J processes)`, `(still: the scene has no animations)` — and
`-p` opens what was written. Exit 0 / 1 (`ERR …` on stderr, ONE line,
never a traceback) / 2 (only unsupported `--motion-blur`) / 130 (Ctrl-C).

**No flag is silently ignored.** These are rejected with an explanation:
`-s` with `-j`, `--from` or `-n`; `-t` with `-j`; `-j` with `--from`,
`-n` or `--to`; `--to` with a label; malformed `-n`; out-of-range `--from`
or `--to`; `-n` that draws nothing
(`ERR -n 9 drew nothing: the scene has 4 animations`); `--from L` whose
label is never reached; `preview` with `-t`, `-w` or `-p`; a scene with
no animations with `-j`. Two scenes in a file without a name:
`ERR x.py defines 2 scenes: Main, Intro — name one as x.py:Main`;
a nonexistent name:
`ERR scene «Nope» is not defined by x.py — expected class Nope(Scene) …`.

Other common rejections:

| Command | Response |
|---|---|
| a flag the verb does not use (`frame … -j 4`, `render … -c`, `preview … -o x.mp4`, `states … -qm`) | `ERR frame does not take -j: it splits a video across processes, and frame takes -qs…-qk, -r, --fps, -t, --samples, --out_dir, -p` |
| `frame x.py 999 out.png` in a 90-frame scene | `ERR frame 999 is past the end (90 frames)`, as with `render -s --to 999` |
| `--samples 3` | `ERR --samples wants 0 (the default, 4), 1 or 4 (got «3»)` |
| `-j 4096` | `ERR -j 4096 asks for more processes than this machine has threads (N): …` |
| `--from 0`, `--from -2` | `ERR --from wants a frame ≥ 1 (got «0»)` |
| `--to 0` | `ERR --to 0 lands before the first frame` |
| `--from 1.5` (without the `s`) | the error for a marker never reached, plus `— a time is written with its unit: --from 1.5s` |
| `check`, `finish` | `OK no daemon, so there is nothing to check or finish` |

The table of flags accepted by each verb is `VERB_FLAGS` in `janim/cli.py`.

Three environment variables do not change any pixels: `JANIM_FFMPEG` (the
CLI's ffmpeg executable; defaults to the one on PATH), `JANIM_CRF` (23 by
default) and `JANIM_ENCODER_THREADS` (x264 threads; its own default).
Use them to choose container quality (for example, `JANIM_CRF=0` for a
lossless file) or to fix a single thread and obtain a byte-reproducible mp4.

## Checkpoints and ranges

`self.checkpoint("act2")` marks a point. In the CLI, `--from act2`
**simulates the prefix without drawing** and starts drawing at the marker
(`render_from(..., simulate_prefix=True)`): the output contains frames
from the marker onward and matches the same frames in the whole video byte
for byte. A marker the scene never reaches is an error (`drew nothing`),
not a full or empty video.

The `render_from(cls, out, label, scene_path=…)` API retains a geometry
snapshot within a process: a valid one skips the prefix
(`scene.skipped_prefix`); without it, the WHOLE video is rendered and a
snapshot is taken for the next call. Snapshots store mobject state, not the
internal state of stateful updaters; for those, replaying from zero is the
reliable route. The validity key is the SHA-256 of the file text before
the marker line; a marker written twice in a file is never valid, and
snapshots are per scene (`Intro --from act2` using `Main`'s label reaches
nothing and is an error in the CLI).

`--from 20 --to 50` is `render_segment` (simulates everything, draws the
range); `-n 2,3` is `anim_range` (another gate on drawing); the two
compose and neither changes what is simulated: `-n 2,3` delivers exactly
the same frames to the encoder as `--from 31 --to 75`.

## The render farm: `-j N`

`render_parallel(path, out, n=, frames_total=, …)` splits frames into N ranges
`round(T·(k−1)/N)+1 … round(T·k/N)`, launches N child processes
(`sys.executable -c`, with the scene name validated as an identifier before
interpolation) that run `render_segment` with **one x264 thread per process**,
and concatenates the segments with the SAME ffmpeg (`-f concat -c copy`,
without re-encoding; the list escapes apostrophes as required by the
demuxer, so output in `it's here/` keeps its video). `1 ≤ N ≤ os.cpu_count()`:
each process has its own graphics device and its own full simulation of
the scene, so the benefit grows with video length.

The farm does NOT speed up simulation: each process simulates the scene
from t = 0 to the end of its segment (updaters run on every frame and only
the segment's frames are drawn), so the last process simulates it all and
together they repeat it (N + 1)/2 times. A scene whose cost lies in its
updaters takes as long or longer with `-j 4` than with one process; the
farm distributes drawing and encoding.

## The live window

`janim scene.py` (or `preview`) opens a GLFW window **without a graphics API**
(non-resizable, at render size) and presents through a WebGPU surface
created from its native handles (Wayland or X11 on Linux, Cocoa on macOS;
`JANIM_GLFW_PLATFORM=x11` forces X11; under `JANIM_HEADLESS=1` or without
a display there is no surface and only events are handled). At 1:1, the
window receives frame bytes exactly as `render_frame` produces them;
on a Retina display at 2:1, each frame pixel occupies a 2×2 block.

Keys: `Esc`/`q` quit · `space` pause · `.`/`,` one frame · `←`/`→` ∓1 s ·
`[`/`]` animation · `PgUp`/`PgDn` checkpoint · `Home` to frame 1 · `c` stop
at checkpoints · `r` reset the user camera · `d`+mouse rotates (turntable in
screen units over the composited frame, φ ∈ [0, π], γ untouched) ·
`f`+mouse or drag pans (through the world) · wheel zooms around the cursor.
User deltas are COMPOSED over the scene camera and never edit it; the
cursor is re-seeded on entering the window and sudden cursor jumps are
clamped to 150 px.

The playhead: `construct` runs ONCE in a thread parked by `Scene.frame_hook`
at the end of each simulated frame; the loop requests frames one at a
time and draws the parked state (frame k matches `render_frame(k)` byte
for byte, including with stateful updaters). Any backward jump rebuilds
from t = 0 (no resuming from snapshots). The landmark map grows with the
playhead and only a file edit resets it. There is a cache of
`max(8, 500 MB/(3·W·H))` frames; a hit rewrites the target.

A file edit is detected by the SHA-256 of its text and applied by
re-executing the module (the class is resolved again). A scene that raises
an exception or an edit that fails to compile FREEZES the window on the
last good frame, with the error in a banner, and watches the file: saving
a fix revives it automatically. The bottom timeline (track, played portion,
act ticks, golden checkpoint marks) is painted AFTER caching: only live
preview has it. Pacing is `sleep(1/fps − elapsed)`, without dropping frames.

Two design limits to know before opening the window: (1) the loop waits
for the next frame without a deadline or event pumping, so a `construct`
that does heavy computation between frames freezes the window for that
time and `Esc` does not respond until the frame arrives; (2) on close, the
playhead thread is abandoned after 5 s and the scene is closed from the
main thread even if `construct` is still alive (a hung scene): the window
goes away and the process exits.

When the window closes, focus is drained (it is hidden and events are
pumped until `leave`, capped at 0.25 s). If the window was alone in its
workspace, the desktop compositor does not send `leave` and the timeout
always expires; this is normal.

API: `live(address, fps=, resolution=, stop_at_checkpoints=, samples=)`;
`setup_live(...)` + `live_step(v)` + `live_status(v)` + `close_live(v)` to
drive the loop manually (hidden window by default); `Scene(preview=True)`
(a visible window showing every drawn frame; without output, the fixed
clock is paced at 1/fps); `count_frames(cls)` (simulates without drawing,
without a GPU).
