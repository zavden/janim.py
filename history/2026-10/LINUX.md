# Janim (Python) on Linux · confirming the Windows port left it unchanged · suggestions for the agent

Written on 2026-10-22 on the Windows 11 machine where the Windows port has
just been completed (`WINDOWS.md`, “Results” section), **without testing
anything on Linux** since then. The port's rule was that Linux and macOS
must remain unchanged: all Windows code goes behind `sys.platform == "win32"`,
and the code executed and frames produced on Linux must match those from
before. This file says where to look to confirm that, what remains untested
on Linux (the README installation commands), and what to record. What I
could check from here (the diff, library sources) is marked “verified”.
If anything proves false, correct it here and say that it was false.

The sibling repo, Janim.jl, has its own `LINUX.md`. Both libraries share
WGSL shaders, and the only shared shader that changed is the same in both
(§2). Comparison harnesses are in Janim.jl's `MACOS.md`, §6.

## Results · 2026-10-22, Fedora 44, Ryzen 7 9700X, Radeon RX 9070 XT (RADV, Mesa 26.2.5), Python 3.14.8, sway 1.11 (Wayland) + Xwayland

**Nothing changed on Linux.** Completed §1 (what could be checked without
reinstalling Python), §2, §3, §4 and §5 between `ce98cf2` and `main`
(`7f54aa3`), with two clean clones and one `scripts/bootstrap.sh` run each,
on 2026-10-22.

- **§1 · Install.** All eleven packages in the README's `dnf` command exist
  in Fedora 44 repositories (`dnf repoquery`). Those in the `apt` command
  exist in Debian (`packages.debian.org`), but `python3.14` is only in
  `forky`/`sid`, not Debian 13 (`trixie`); Ubuntu 26.04 (`resolute`) has
  it: the README's `uv` note covers that gap. Lessons `03_text`,
  `05_physics_warning` and `06_cli_and_farm` require Liberation Serif and
  Mono, which the README names but the `dnf`/`apt` commands omit
  (`liberation-fonts`, `fonts-liberation`); they were installed here.
  `bootstrap.sh` → `bootstrap.py`: both venvs have identical `pip list`
  output (cffi 2.1.1, freetype-py 2.5.1, glfw 2.10.2, numpy 2.4.6,
  pycparser 3.0, sniffio 1.3.1, wgpu 0.21.0; `rubicon-objc` skipped by its marker).
- **§2 · Frames, byte for byte.** All 134 `Scene` classes in `examples/`:
  **134 renders, 8,544 frames, identical** before and after at 640×360 and
  10 fps on RADV (one SHA-256 per frame through `frame_tap`, one process
  per render). `06_broadcast` (`BroadcastScene`), the CRT demo, gives the
  same 198 frames. Python versus Julia (Janim.jl on `main`): `01`, `03`,
  `04`, `07`, `11` match as on Windows, as do `10` (90 frames) and
  `12` (66; Fredoka is installed here); `02`, `05`, `06`, `08` and
  `09` differ, as they already did before the port (Janim.jl's `MACOS.md`, §6).
- **§3 · Shared code.** `gpu_info()` reports `radv`, `vulkan`, `Mesa
  26.2.5`, `discrete`; with `JANIM_HEADLESS=1`, llvmpipe and `cpu`.
  `import janim` loads; `_BACKEND_TYPES["DX12"]` exists on Linux (4).
  GLFW: without `DISPLAY` or `WAYLAND_DISPLAY` → `null`; with
  `JANIM_HEADLESS=1` → `null`; `JANIM_GLFW_PLATFORM=win32` or `cocoa`
  → “expected null, wayland or x11”. `video.py`: `03_portals` at `-ql`
  (210 frames) and with `-j 2` (140) give the same frame counts and decoded
  frames (`framemd5`) before and after. The nine reads with
  `encoding="utf-8"`: shaders (any render), `Tex` (the LaTeX lesson) and
  the farm (`-j 2`) pass. Fonts: `03_text` finds DejaVu and Liberation.
- **§4 · CLI and window.** `-p` calls `xdg-open` (stub) with the correct
  path; `-j 2`; `-t`; `-s --to 40 --out_dir`; `frame 60`; the LaTeX
  lesson; multi-scene `:Intro`; `ping` and `check` without a daemon.
  The window: `live()` on Wayland and X11 (two consecutive sessions each,
  81 and 89 frames in 3 s), and the CLI window closed with Esc (frame 66).
- **§5 · Timings.** Below, alongside Windows.

### §5 · Timings at 1920×1080 and 60 fps, Linux alongside Windows

Linux: Fedora 44, Ryzen 7 9700X, Radeon RX 9070 XT (RADV, Mesa 26.2.5),
`main` at `7f54aa3`, one render at a time, wall-clock time for the whole
process (`bin/janim render … -r 1920x1080 --fps 60`; Python starts in
~1 s), on 2026-10-22. Windows: the table in §5. Demo 12 renders here:
Fredoka is installed.

| demo | frames | Python Linux | Python Windows | Julia Linux | Julia Windows |
|---|---:|---:|---:|---:|---:|
| 01_multicam | 840 | 5.5 s | 7 s | 8.0 s | 10 s |
| 02_pendulum_glow | 1356 | 9.5 s | 12 s | 15.1 s | 18 s |
| 03_portals | 840 | 6.9 s | 8 s | 10.9 s | 13 s |
| 04_lorenz_glow | 1080 | 25.2 s | 61 s | 14.5 s | 16 s |
| 05_rack_focus | 756 | 5.3 s | 6 s | 9.0 s | 11 s |
| 06_broadcast | 1188 | 8.1 s | 8 s | 10.7 s | 13 s |
| 07_text_mask | 846 | 44.0 s | 51 s | 9.8 s | 12 s |
| 08_light_vs_pigment | 708 | 5.0 s | 5 s | 8.5 s | 10 s |
| 09_reflection | 768 | 5.7 s | 6 s | 9.6 s | 11 s |
| 10_motion_blur | 540 | 3.9 s | 4 s | 7.4 s | 9 s |
| 11_chase_camera | 1320 | 9.8 s | 12 s | 12.3 s | 15 s |
| 12_motion_blur | 396 | 3.0 s | fails (font) | 5.8 s | fails (font) |

Frame counts match Windows. At this resolution, through x264, Python and
Julia mp4s decode to the same frames (`ffmpeg -f framemd5`) in the seven
demos that match at 640×360 (`01`, `03`, `04`, `07`, `10`, `11`,
`12`); the other five pairs differ, as below.

## 0 · Working rules

- **The goal** is to confirm that nothing changed on Linux: neither the
  executed code nor the frames. This is not a port: if everything matches,
  the work is short.
- **Before** is commit `ce98cf2` (“WINDOWS.md: suggestions for porting Janim
  to Windows 11”), the last `main` before the port; **after** is `main`.
  The 14 commits between them: `git log --oneline ce98cf2..main`.
- **Windows and macOS must not change** from here: there is no machine to
  test them. Any Linux fix goes behind a Linux guard, or outside all guards
  only if it is identical on all three.
- **Commits only with Alex's permission, and never push.** One commit per
  fix, in Spanish, explaining why. No new dependency without asking.
  Only text and SVG in git.
- **There are no reference frames in the repo, but here there is a before:**
  the same Linux, the same GPU, commit `ce98cf2`. Compare byte for byte (§2),
  not by eye.
- **Suggested order:** install from scratch with the README (§1), compare
  frames before and after (§2), review the rest of the shared code (§3),
  the CLI and window (§4), then record timings (§5).

## 1 · Install from scratch: the README's Linux commands have not been tested

The README (`### Linux`) gives `dnf` commands for Fedora 43 and `apt` for
Debian/Ubuntu, written without a Linux machine available: package names,
especially TeX Live's (`texlive-standalone`, `texlive-preview`,
`texlive-dvisvgm`) and `python3.14` on Debian, may not exist under those
names on your distribution. Follow the README exactly in a clean clone,
correct failing commands (in both languages), and run the “Check it”
section after the platform instructions: `gpu_info()` should report
`backend='vulkan'`.

`scripts/bootstrap.sh` no longer embeds Python: it calls
`scripts/bootstrap.py`, the old heredoc moved into a file so
`bootstrap.cmd` can share it (verified in the diff: same `pip install`,
same options, same `janim.pth`). Compare `.venv/bin/pip list` against a
venv made from `ce98cf2`: they should match.

## 2 · Frames: before and after, byte for byte

The only shared change that can move a pixel is in
`janim/backend/wgpu/shaders/effects.wgsl`, in `fs_crt`: `grille[col] = 1.0`
(a write through a dynamic index, rejected by the DX12 compiler) became
a `select` with the same value:

```wgsl
let grille = select(vec3<f32>(1.0 - mask_depth * intensity), vec3<f32>(1.0),
                    vec3<bool>(col == 0, col == 1, col == 2));
```

The other shared changes are reads with `encoding="utf-8"` (§3), which
do not touch any frames. Still, compare more than one demo: the harness is cheap.

Use `tapf.py` from Janim.jl's `MACOS.md`, §6 (SHA-256 hashes per frame,
640×360 at 10 fps, one render per process), saved outside the repo, with
two clones or a `git worktree add ../janim_py-before ce98cf2` (with its
own `scripts/bootstrap.sh`). For each demo, produce a list of hashes
with each checkout and compare them frame by frame:

- **`06_broadcast`** (class `BroadcastScene`): the CRT demo, the only one
  with a reason to change. It must produce the same list. Otherwise,
  inspect the shader: `select` must give exactly `1.0` in stripe `col`
  and `1.0 - mask_depth * intensity` in the other two.
- **`01_multicam`, `03_portals`, `04_lorenz_glow`, `07_text_mask`,
  `11_chase_camera`** (`Multicam`, `Portals`, `LorenzGlow`, `TextMask`,
  `ChaseCamera`): the five that match between Python and Julia on Linux;
  they serve as controls (they do not touch CRT) and also confirm that both
  libraries still match after the port (on Windows with DX12, all five
  continued to match byte for byte).

A difference here is a porting bug, not a driver issue: same machine,
same driver, one process per render.

## 3 · The rest of the shared code, file by file

All of this is verified in the diff (`git diff ce98cf2..main -- janim
scripts`); what remains on Linux is to run it.

| file | change | what to check on Linux |
|---|---|---|
| `backend/wgpu/context.py` | `BACKEND = {"darwin": "Metal", "win32": "DX12"}.get(sys.platform, "Vulkan")` | `gpu_info()` says `backend='vulkan'` |
| `backend/wgpu/native.py` | `_INSTANCE_BACKENDS` and `_BACKEND_TYPES` gain `DX12` (`lib.WGPUBackendType_D3D12`, a constant the header defines on all platforms: verified in `webgpu.h`) | `import janim` loads |
| `backend/glfw.py` | `_headless_env` returns `False` for `("darwin", "win32")` instead of only `darwin`; `names` gains `glfw.PLATFORM_WIN32` (an unconditional constant in pyGLFW 2.10.2, line 648: verified); `native_handles` gains a `win32` branch after `cocoa`, unreachable here | the live window opens on Wayland and X11; without `DISPLAY` or `WAYLAND_DISPLAY`, and with `JANIM_HEADLESS=1`, the result is still `null` |
| `backend/wgpu/window.py` | `create_window` accepts `"win32"` in its tuple; `PRESENT_WGSL` is read as UTF-8 | same as above |
| `video.py` | `select.select` is inside `if sys.platform != "win32"`, and `except BlockingIOError` only sleeps on Windows; on Linux, the same lines as before | a long render and one with `-j 2`; same frame count as before (`ffprobe`) |
| `cli.py` | `open_output` starts with a `win32` branch (`os.startfile`) and `main` with another (UTF-8 stdout); the rest is identical | `-p` opens with `xdg-open` |
| `text/glyphs.py` | `_font_catalog` gains an `elif sys.platform == "win32"` branch | DejaVu and Liberation are found as before |
| nine `read_text`/`write_text` calls with `encoding="utf-8"`: `pipelines.py:29,35`, `compositor.py:49`, `triangle.py:12`, `window.py:22`, `core/model.py:41,83`, `scene/scene.py:807`, `text/tex.py:111` and following | without `encoding`, Windows read cp1252 and died at the first non-Latin character; on Linux the locale was already UTF-8, so the bytes are the same | shaders (any render), a model (`core/model.py`), `Tex`, the farm (`scene.py:807` writes the ffmpeg list) |
| `scripts/bootstrap.sh` → `scripts/bootstrap.py` | §1 | §1 |
| `.gitattributes`, `bin/janim.cmd`, `scripts/bootstrap.cmd` | Windows files; on Linux, `*.cmd` deliberately use CRLF | nothing |
| `README*.md`, `llms.txt`, `WINDOWS.md` | documentation | Linux commands (§1) |

`bin/janim` (bash) did not change. On Linux without a UTF-8 locale
(`LANG=C`), the reads with explicit `encoding` are precisely what makes
it work there too; previously it depended on the locale.

## 4 · The CLI and window

None of this changed on Linux, so this is a pass through the checks,
not an investigation:

```bash
bin/janim render examples/demo/03_portals.py -ql -p          # xdg-open when finished
bin/janim render examples/demo/03_portals.py -qs -j 2 -o /tmp/farm.mp4
bin/janim render examples/demo/03_portals.py -qs -t -o /tmp/alpha.mov
bin/janim render examples/demo/03_portals.py -s --to 40 -ql --out_dir /tmp/stills
bin/janim frame  examples/demo/03_portals.py 60 /tmp/f.png -ql
bin/janim examples/demo/03_portals.py                        # window: keys, mouse, Esc
```

Test the window on Wayland and X11 if the machine has both
(`JANIM_GLFW_PLATFORM`, if that variable exists, or the appropriate session).

## 5 · Timings, for comparison with Windows

On Windows (Ryzen 7 9700X, Radeon RX 9070 XT, DX12, driver 32.0.32015.7029),
one render at a time, wall-clock time for the whole process (Python starts
in ~1 s; Julia, 4–5 s), measured on 2026-10-21 with `main` at `2a2f079`:

| demo | frames | 1080p60 Python | 1080p60 Julia | 720p60 Python | 720p60 Julia |
|---|---:|---:|---:|---:|---:|
| 01_multicam | 840 | 7 s | 10 s | 4 s | 7 s |
| 02_pendulum_glow | 1356 | 12 s | 18 s | 9 s | 13 s |
| 03_portals | 840 | 8 s | 13 s | 7 s | 10 s |
| 04_lorenz_glow | 1080 | 61 s | 16 s | 57 s | 11 s |
| 05_rack_focus | 756 | 6 s | 11 s | 3 s | 7 s |
| 06_broadcast | 1188 | 8 s | 13 s | 5 s | 9 s |
| 07_text_mask | 846 | 51 s | 12 s | 54 s | 8 s |
| 08_light_vs_pigment | 708 | 5 s | 10 s | 4 s | 8 s |
| 09_reflection | 768 | 6 s | 11 s | 4 s | 9 s |
| 10_motion_blur | 540 | 4 s | 9 s | 2 s | 7 s |
| 11_chase_camera | 1320 | 12 s | 15 s | 8 s | 11 s |
| 12_motion_blur | — | fails | fails | fails | fails |

Python's demos 04 and 07 are CPU-bound (numpy), not GPU-bound: their
timings barely change with resolution. Demo 12 needs “Fredoka Expanded”,
which was not installed. To repeat here, in the same order and never
two at once:

```bash
time bin/janim render examples/demo/01_multicam.py -r 1920x1080 --fps 60 -o /tmp/01.mp4
```

Record the GPU, Mesa driver and timings at the start of this file,
alongside the result of §2.

## 6 · What is not a Linux problem

- `12_motion_blur` fails because of the “Fredoka Expanded” font; Alex said
  to ignore it, as with motion blur (`04`, `10`, `12`).
- Everything behind `sys.platform == "win32"`, `bin\janim.cmd` and
  `scripts\bootstrap.cmd`: it cannot be tested here and should not be touched.

## 7 · When finished

Add a “Results” section at the start of this file with the distribution,
GPU, driver, what matched and what did not (as in `MACOS.md` and
`WINDOWS.md`). If the README's Linux commands changed, say which ones.
If everything matches, the port is complete on all three platforms and
Alex decides whether to push.
