# Janim (Python) on macOS (Apple Silicon) · suggestions for the agent

Written on 2026-10-21 on the Linux development machine (RADV, Fedora),
**without testing anything on a Mac**. These are suggestions, not fixed
instructions: each point says what I expect, where to look and how to
confirm it. If anything proves false, correct it here and say that it was false.

The sibling repo, Janim.jl, has its own `MACOS.md`, and is one step ahead
on macOS: it already selects Metal. Both libraries share WGSL shaders and
the major version of wgpu-native (v24), so what you learn in one applies
to the other. If you have both clones, read that file too.

## Results · 2026-10-21, macOS 26.6.2, Apple M1, Python 3.14.7 (Homebrew)

**The port is complete.** Rendering to files, the CLI and the live window
with keyboard and mouse were verified by Alex on 2026-10-21 on this M1 in
both libraries; the first seven demos were rendered at 1080p60 in both.

Tested on the Mac, section by section. Almost all expectations were correct;
changes are marked.

- **§1 · Prepare.** Confirmed. `brew install --cask font-dejavu` places
  DejaVu fonts in `~/Library/Fonts`. Lessons requiring “Liberation Serif”
  or “Liberation Mono” (including `c1_03/03_text.py`) give the expected
  `FontNotFound` unless `font-liberation` is installed. MacTeX's LaTeX
  and `dvisvgm` in `/Library/TeX/texbin` work directly from `bin/janim`.
- **§2 · Install.** Confirmed: `import wgpu` died without `rubicon-objc`.
  It is in `[tool.janim.bootstrap]` with the `sys_platform == 'darwin'`
  marker; the wgpu wheel includes wgpu-native 24.0.0.2 and passes `NATIVE_VERSION`.
- **§3 · Metal.** Confirmed. `context.BACKEND` (`"Metal"` on darwin,
  `"Vulkan"` elsewhere) controls `native.py`: the instance bit, the
  `backendType` accepted by `_adapter_information`, and messages. The
  adapter is “Apple M1 · IntegratedGPU · Metal”, with empty `vendor`,
  `architecture` and `description` (slug `apple`, version `unknown`),
  256/256 alignments and `float32-filterable`. `JANIM_HEADLESS=1` gives
  the error listing adapters, as expected. Visually correct renders:
  `c1_01/01`, `c1_03/04_latex`, `c1_03/06_tex_transformations`,
  `demo/03_portals`, `demo/07_text_mask`, `c2_03/03_camera_3d`.
  Cross-process determinism: `03_portals` (140 frames) and `07_text_mask`
  (141) give identical hashes in two processes.
- **§4 · Fonts.** Confirmed against FreeTypeAbstraction's code
  (`__init__`: recursion only for `Sys.isunix() && !Sys.isapple()`) and
  BaseDirs (`darwin.jl`): on macOS, the five flat directories in that
  order. The M1 catalog has 463 faces; “DejaVu Sans” resolves to
  `~/Library/Fonts/DejaVuSans.ttf`.
- **§5 · Everything else.** Confirmed. `_headless_env` returns false on
  darwin; `JANIM_GLFW_PLATFORM` accepts `null` or `cocoa` on macOS
  (and still accepts `null`, `wayland` or `x11` on Linux, with the same
  message). `readlink -f` works in `bin/janim`.
- **§6 · The live window.** Works with fewer changes than expected:
  returning `{"platform": "cocoa", "window": NSWindow}` in
  `native_handles` and accepting `cocoa` in `create_window` was enough;
  wgpu-py's darwin branch creates the `CAMetalLayer`. The surface offers
  `bgra8unorm-srgb` first (`bgra8unorm` is used), Fifo and Immediate,
  and CopySrc. **Retina:** wgpu-py leaves `contentsScale = 1.0`;
  wgpu-native does set `drawableSize` to the framebuffer size (2560×1440
  over 1280×720 points), so it does not occupy “one quarter of the window”.
  `glfw.sync_content_scale` sets `contentsScale = backingScaleFactor`
  (2.0) when creating the surface and reconfiguring, as GLFW does with
  Vulkan surfaces. Measured with `present_readback`: each frame pixel
  occupies exactly one 2×2 swapchain block. Two consecutive previews open
  and close cleanly; Wayland's focus drain does not interfere (it finishes
  before the timeout). The playhead thread does not touch GLFW; no changes
  were needed. **Keyboard and mouse:** tested manually by Alex, including
  camera movement: they work, and the §6.7 issue does not occur (callbacks
  consistently use logical coordinates).
- **§7 · Python versus Julia.** Done on the same Mac with both harnesses
  from Janim.jl's §6. Four demos (`01`, `03`, `04`, `07`) matched
  byte for byte immediately; `11_chase_camera` differed in all 220
  frames, and **all three hypotheses in this section were false**:
  fonts resolved to the same file, CPU geometry (`knot`, `atan2`,
  rotations) and every byte uploaded to the GPU (points, normals, indices,
  uniforms) were identical in both libraries. The difference was in
  pixels of the three `Torus` objects (±1 to ±4 out of 255), caused by
  Python merging consecutive meshes sharing a pipeline, uniform block
  and texture into one `draw_indexed` (`render.py`, `_record_commands`),
  while Julia issues one call per mesh: on Metal, the lit color interpolated
  over a triangle changes in the last bit depending on its draw call
  (splitting a single mesh into two calls already changes pixels;
  `@interpolate(flat)` does not), whereas RADV does not. The fix is in
  `render.py`: `_MERGE_MESH_DRAWS = BACKEND != "Metal"`, one call per
  mesh on Metal, as in Janim.jl. On Linux, `BACKEND` is Vulkan and the
  merging loop remains unchanged. With the fix, all five demos give
  identical Python and Julia frames (140, 140, 180, 141 and 220), and
  the four that already matched did not change a single byte.
- **Unchanged:** `live.py`, `cli.py`, `tex.py`, `video.py`.

## Results · 2026-10-22, review after the Windows port (macOS 26.6.2, Apple M1, Python 3.14.7)

**Nothing changed on the Mac.** Checked with a clean `main` clone
(`7f54aa3`) against the last `main` before the Windows port (`ce98cf2`),
following `LINUX.md` in this session:

- **Installation from scratch** using the README's macOS commands.
  `scripts/bootstrap.sh` (which now calls `scripts/bootstrap.py`) creates
  the venv with exactly the same packages as before (identical `pip list`,
  `janim.pth` in place); `gpu_info()` says “Apple M1 · metal · integrated”;
  `frame` and `render -ql` from “Check it” succeed.
- **Frames before and after, byte for byte** (`tapf.py`, 640×360 at 10 fps):
  `01_multicam` (140), `03_portals` (140), `04_lorenz_glow` (180),
  `06_broadcast` (198, CRT with `select`), `07_text_mask` (141) and
  `11_chase_camera` (220) give the same hash lists in both checkouts.
  The five reference demos still match between Python and Julia.
  `06_broadcast`'s class is `BroadcastScene` (`LINUX.md` said
  `Broadcast`; corrected).
- **CLI** (without `-p` or the CLI window, which open something only Alex
  closes): `render -qs`, `-j 2` (140 frames, 2 processes; same content
  as the single-process render, at 45 dB PSNR due to segment encoding,
  exactly as in Julia), `-t` (ProRes 4444, `yuva444p12le`),
  `-s --to 40`, `frame`, and relative `-o` with `--out_dir`.
- **Live window** in-process (`live(…, max_seconds=3)`, two consecutive
  sessions): Cocoa, `CAMetalLayer`, `contentsScale` 2.0, 2560×1440 over
  1280×720 points, 84 presentations per session, no reconfigurations,
  closes cleanly. `JANIM_HEADLESS=1` still gives the error listing adapters.
- **All 12 demos at 1080p60** (`bin/janim render … -qh`), one at a time:
  11 succeed; `12_motion_blur` fails because of “Fredoka Expanded”, as
  on Windows. Demos `01` through `07` match frame for frame with those
  rendered on 2026-10-21, before the Windows port.

**Python versus Julia in 1080p60 mp4s** (decoded and compared frame by
frame): `01`, `03`, `04`, `07` and `10` are identical.
`11_chase_camera` differs in 28 frames (972–1000, at 54–58 dB) despite
identical raw frames: the harness at 1920×1080/60 gives 1320 equal hashes,
and `frame 972` and `frame 990` through both CLIs give the same pixels.
The cause is the encoder: Janim.jl writes with FFMPEG_jll's ffmpeg
(x264 core 164), and Janim.py with the one on `PATH` (Homebrew ffmpeg
9.0.1, x264 core 165). Use the harnesses to compare the libraries, not
mp4s. `02`, `05`, `06`, `08` and `09` differ in every frame, as
on Linux: in `08` and `09`, the demo text names the language; in `02`,
`05` and `06`, the visible difference is `Tex` spacing (Janim.jl
separates glyphs; Python composes them with LaTeX kerning).

**1080p60 timings**, wall-clock time for the whole `bin/janim render`
process, one render at a time (Julia through the warm daemon); Windows
figures are from `LINUX.md`, §5 (Ryzen 7 9700X, Radeon RX 9070 XT, DX12):

| demo | frames | Mac Python | Mac Julia | Windows Python | Windows Julia |
|---|---:|---:|---:|---:|---:|
| 01_multicam | 840 | 10 s | 9 s | 7 s | 10 s |
| 02_pendulum_glow | 1356 | 73 s | 82 s | 12 s | 18 s |
| 03_portals | 840 | 16 s | 16 s | 8 s | 13 s |
| 04_lorenz_glow | 1080 | 168 s | 163 s | 61 s | 16 s |
| 05_rack_focus | 756 | 54 s | 54 s | 6 s | 11 s |
| 06_broadcast | 1188 | 17 s | 11 s | 8 s | 13 s |
| 07_text_mask | 846 | 78 s | 38 s | 51 s | 12 s |
| 08_light_vs_pigment | 708 | 38 s | 40 s | 5 s | 10 s |
| 09_reflection | 768 | 59 s | 58 s | 6 s | 11 s |
| 10_motion_blur | 540 | 10 s | 6 s | 4 s | 9 s |
| 11_chase_camera | 1320 | 24 s | 15 s | 12 s | 15 s |
| 12_motion_blur | — | fails | fails | fails | fails |
| total 01–11 | 10,242 | 547 s | 492 s | 180 s | 138 s |

In GPU-heavy demos (`02`, `04`, `05`, `08`, `09`), Python and Julia
take the same time on the M1: the bottleneck is the integrated GPU,
5 to 10 times slower than the RX 9070 XT. Python's `04` and `07` remain
CPU work (numpy), as on Windows.

## 0 · Working rules

- **The goal** is to make file rendering, the `bin/janim` CLI and the
  live window work on an M1.
- **Linux must not change.** Everything specific to macOS goes inside
  `sys.platform == "darwin"`, and on Linux the executed code and resulting
  frames must remain the same as today. Back on the Linux machine, repeat
  the frame comparison against the previous version.
- **There are no reference frames in the repo.** On Metal, many edges
  will shift by one pixel compared with Linux, so a byte difference is
  not a bug. Look for things that look WRONG. Inspect the scenes; exit 0
  says nothing about what is on screen.
- **Commits only with Alex's permission, and never push.** One commit
  per fix, in Spanish, explaining why. No new dependency without asking:
  the only definitely needed one is `rubicon-objc` (§2), and that also
  requires asking. Only text and SVG in git.
- **Suggested order:**
  1. Install.
  2. Make the instance select Metal.
  3. Render a simple scene to a file.
  4. Test formulas, layers and 3D.
  5. Leave the live window until last.

## 1 · Prepare the Mac

- **macOS 14 or later**: the `numpy==2.4.6` wheel for cp314 arm64 is
  `macosx_14_0`.
- **Python 3.14**: `brew install python@3.14`, or the python.org installer.
- **ffmpeg** on `PATH`: `brew install ffmpeg`. Janim calls it by name,
  `ffmpeg`/`ffprobe`.
- **Fonts:** `brew install --cask font-dejavu` puts them in
  `~/Library/Fonts`. Examples require DejaVu Sans, and a missing family
  deliberately raises `FontNotFound`, with no silent substitution.
- **LaTeX, optional, for `Tex`/`MathTex`:** MacTeX or BasicTeX, plus
  `dvisvgm`, in `/Library/TeX/texbin`. Check that directory is on the
  process's `PATH`, not just the terminal's.

## 2 · Install: one definite fix before starting

`scripts/bootstrap.sh` installs the pinned versions from `pyproject.toml`
with `--only-binary=:all: --no-deps`. Verified from Linux with
`pip download --platform macosx_14_0_arm64 --python-version 3.14`:
**macOS arm64 wheels exist for all of them**. Those with native code:

| package | what it includes for macOS |
|---|---|
| `wgpu==0.21.0` | `wgpu/resources/libwgpu_native-release.dylib`, wgpu-native **v24.0.0.2**, the same version as the Linux wheel, so `NATIVE_VERSION = (24, 0)` in `janim/backend/wgpu/context.py` passes |
| `glfw==2.10.2` | `glfw/libglfw.3.dylib` |
| `freetype-py==2.5.1` | `universal2` wheel |
| `cffi==2.1.1` | `cp314 macosx_11_0_arm64` |

**What will fail:** wgpu 0.21.0's `METADATA` declares
`rubicon-objc>=0.4.1; sys_platform == 'darwin'`, and
`wgpu/backends/wgpu_native/_helpers.py:33` imports it when loading the
module on macOS. With `--no-deps` it is not installed, so `import wgpu`
will fail.

- **Suggested fix** (new dependency: ask Alex's permission): add
  `"rubicon-objc==0.5.7; sys_platform == 'darwin'"` to
  `[tool.janim.bootstrap] dependencies` in `pyproject.toml`.
  It is a `py3-none-any` wheel, and pip respects the marker, so nothing
  changes on Linux.
- **Afterward:**

  ```bash
  PYTHON=python3.14 scripts/bootstrap.sh
  .venv/bin/python -c "import janim, wgpu; print(wgpu.__version__)"
  ```

## 3 · Make the instance select Metal (the first rendering failure)

1. **The instance is created with Vulkan ONLY**:
   `janim/backend/wgpu/native.py:62-64` (`extras.backends = 1 << 0`).
   - In `wgpu.h`: Vulkan is `1 << 0`, GL `1 << 1`, Metal `1 << 2`
     and DX12 `1 << 3`. Check `wgpu/resources/wgpu.h`.
   - Julia already does this in `src/backend/wgpu/context.jl:242`,
     using Metal on macOS. Copy that rule inside `sys.platform == "darwin"`.
2. **`_adapter_information` rejects everything except Vulkan**
   (`native.py:77`) and hardcodes `backend_type="Vulkan"` (`:89`).
   Accept `lib.WGPUBackendType_Metal` on macOS and set the real name.
3. **Messages that say “Vulkan”:** `native.py:49`, `:69`,
   `janim/backend/wgpu/context.py:1` and `:110`. Make them name the actual backend.
4. **`JANIM_HEADLESS=1` does not work on macOS.** It requests Mesa's CPU
   adapter (lavapipe), which does not exist on macOS. `choose_adapter`
   (`context.py:103-125`) already gives an error listing adapters, which
   is correct. Without the variable, it selects the M1's integrated GPU.
5. **Device limits:** `native.py:226-227` requests adapter alignments,
   and `uniforms.py:154` uses them. On Metal they may be 256, not 32;
   the code already supports this. `float32-filterable` is requested
   only if available.
6. **A wgpu-native panic kills the Python process.** If it dies abruptly,
   repeat with `JANIM_WGPU_LOG=info` (or `debug`) and inspect the last call.

First test:

```bash
bin/janim render examples/tutorial/c1_01_basics/01_how_janim_works.py -ql
```

Then, in this order:

- **Formulas:** `examples/tutorial/c1_03_groups_and_text/`.
- **Layers and effects:** `examples/demo/03_portals.py`.
- **3D:** `examples/tutorial/c2_03_camera/` and `examples/demo/07_text_mask.py`.

Inspect the midpoint of each Transform, the first frame and the last
(`bin/janim frame …`).

## 4 · Fonts: the catalog only knows Linux directories

`janim/text/glyphs.py:27-45` (`_font_catalog`) traverses Unix XDG roots.
On macOS it will find nothing outside `~/.local/share/fonts`.

Make it exactly match FreeTypeAbstraction, the font finder used by
Janim.jl. On macOS it uses `BaseDirs.fonts()` directories, in this order
and **without entering subdirectories**:

1. `~/Library/Fonts`
2. `/Library/Fonts`
3. `/System/Library/Fonts`
4. `/System/Library/Fonts/Supplemental`
5. `/Network/Library/Fonts`

If the order or traversal differs, the libraries may choose different
faces for the same name. That would show up in §7's comparison even if
each looks correct individually.

`.ttc` collections have multiple faces. Currently, as in
FreeTypeAbstraction, only the first is loaded (`freetype.Face(path)`):
do not change this without changing both sides.

## 5 · Other code written for Linux

- **GLFW:** `janim/backend/glfw.py:13`,
  `LIBRARY = "/usr/lib64/libglfw.so.3"`, is used only if it exists.
  On macOS the wheel's `libglfw.3.dylib` will load.
  `:14` (`X_LOCALE_DIRECTORY`) also applies only if it exists.
- **Is there a display?** `glfw.py:50-53` (`_headless_env`) decides
  “no display” if `DISPLAY` and `WAYLAND_DISPLAY` are missing, as they
  always are on macOS. Treat darwin as having a display. Julia restricts
  the check to Linux in `src/backend/glfw.jl:186`.
- **Platform:** `glfw.py:71-90` only knows Null, Wayland and X11.
  Add `glfw.PLATFORM_COCOA` to the `JANIM_GLFW_PLATFORM` table and
  names (`:89`) as `"cocoa"`.
- **`-p`** already uses `open` on macOS (`janim/cli.py:329`).
- **`bin/janim`** uses `readlink -f`, requiring macOS 12.3 or later,
  and the checkout's `.venv/bin/python`.

## 6 · The live window: what remains to implement

1. **The surface source.** `glfw.py:115-127` (`native_handles`) returns
   only Wayland or X11. For Cocoa, return
   `{"platform": "cocoa", "window": int(glfw.get_cocoa_window(window.handle))}`.
   `native.create_surface` (`native.py:297-301`) passes this to
   wgpu-py's `_helpers.get_surface_id_from_info`. Its `darwin` branch
   already creates the `CAMetalLayer` on the `NSWindow`'s `contentView`
   using rubicon-objc, and the `WGPUSurfaceSourceMetalLayer` surface.
   No Objective-C needs to be written.
2. **`create_window`** (`janim/backend/wgpu/window.py:221-232`) only
   accepts `"wayland"` and `"x11"`: add `"cocoa"`.
3. **Retina.** The presenter already uses `framebuffer_size` (physical
   pixels, `window.py:225`), twice the window size on Retina. The layer
   wgpu-py creates does not adjust `contentsScale`. If the image is
   blurry or occupies a quarter of the window, set the layer's
   `contentsScale = backingScaleFactor` from the `NSWindow` (using
   rubicon). In the OpenGL era, this error produced a black window on this M1.
4. **Format:** `window.py:25-28` already handles `bgra8unorm`, which
   Metal will prefer.
5. **The main thread.** Cocoa requires windows and events on the main thread.
   - Preview simulates the scene on another thread
     (`janim/interactive/live.py:220`, `janim-playhead`), while the event
     loop and presentation run on the main thread (`live.py:240`).
   - Check that no GLFW call (including `create_window` or callbacks
     installed from the other thread) occurs outside the main thread.
   - Suspect this first if the window freezes or the process dies when opening it.
6. **The Wayland patch** (`glfw.py:160-200`) hides the window and pumps
   events before destroying it. If it interferes on macOS, restrict it to Linux.
7. **The mouse on Retina.** Cursor coordinates are logical; the framebuffer
   uses physical pixels. If orbiting or dragging runs at double or half
   speed, the mix is in `live.py` callbacks (around `:540-600`) and
   `janim/interactive/`.

Test with `bin/janim examples/demo/03_portals.py`: keys (space, `,`/`.`,
←/→, `[`/`]`, Esc), mouse, and opening and closing two consecutive previews.

## 7 · A tool without Linux: Python versus Julia on the same Mac

On Linux (RADV, 640×360 at 10 fps), these five demos produce **byte-identical
frames** in Janim.py and Janim.jl, measured on 2026-10-21:

| demo | class | frames |
|---|---|---|
| `01_multicam` | `Multicam` | 140 |
| `03_portals` | `Portals` | 140 |
| `04_lorenz_glow` | `LorenzGlow` | 180 |
| `07_text_mask` | `TextMask` | 141 |
| `11_chase_camera` | `ChaseCamera` | 220 |

The others already differ on Linux: 08 because of its on-screen text,
and 02, 05, 06 and 09 for uninvestigated reasons. Do not use them.
On the Mac, the two libraries should still match each other.
Both harnesses (per-frame hashes with `frame_tap` in Python and
`Janim._FRAME_TAP` in Julia) are in Janim.jl's `MACOS.md`, §6.
Save them outside the repo.

If they differ on the Mac but match on Linux, check in this order:

1. **Fonts.** See §4: the same name resolving to different faces.
2. **libm.** Python uses the system's `math.sin`/`math.cos`/`math.tan`
   in some places, whereas Julia uses its own implementations:
   - `janim/animation/transform.py:129-132` (`path_arc`);
   - `janim/animation/indication.py:61` and `:99`;
   - `janim/animation/homotopy.py:63` (`ApplyWave`);
   - `janim/backend/wgpu/effects.py:95` and `:238-243` (effect angles);
   - `janim/core/decor.py:146-153`.

   Linux's glibc gives the same bits as Julia in these cases; Apple's
   libm may differ in the last ulp. The fix is to use `sin`/`cos`/`tan`
   from `janim/core/_julia_math.py`, the Julia Base port already used by
   `janim/core/surface.py` (`_julia_trig`). Change this only if frames
   remain identical on Linux: glibc and Julia agree there in these cases,
   not for every possible value.
3. **numpy.** `janim/core/bezier.py` uses `np.sin`/`np.cos`, and numpy
   has its own vector implementations per architecture: NEON on arm64,
   AVX on x86. They may differ in the last bit between the machines.

**Determinism:** the same scene in two Mac processes must give the same
frames. It should not depend on the GPU; check with a couple of scenes.

## 8 · What is not a Mac problem

- **Video motion blur does not exist** on any platform. `Scene` does
  not accept `motion_blur` and the CLI rejects `--motion-blur`.
  Demos 10 and 12 and the `c3_05_motion_blur` lessons explain this.
- **`c2_05_from_manim/01_from_manim_ce.py` says `-ql` does not exist**,
  but the CLI does support it.

## 9 · When finished

Record here what you confirmed and what proved false, and in both READMEs'
“Known limitations” sections replace “Linux only” with what actually
works, including the macOS version and chip tested.
