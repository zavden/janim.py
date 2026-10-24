# Janim (Python) on Windows 11 · suggestions for the agent

Written on 2026-10-21 on the Mac M1 where the macOS port has just been
completed (`MACOS.md`), **without testing anything on Windows**. These are
suggestions, not fixed instructions: each point says what I expect, where
to look and how to confirm it. What I could check from here (wheels,
headers, code) is marked “verified”. If anything proves false, correct it
in this file and say that it was false.

The sibling repo, Janim.jl, has its own `WINDOWS.md`, and is one step ahead
on Windows: it already selects DX12 and includes wgpu-native for
`x86_64-windows`. Both libraries share WGSL shaders and the major version
of wgpu-native (v24), so what you learn in one applies to the other.
Also read this repo's `MACOS.md`: the macOS port is the precedent, and almost
everything it touched (backend, GLFW platform, fonts) is touched again
here, in the same places.

## Results · 2026-10-21, Windows 11 Home 25H2, Ryzen 7 9700X, Radeon RX 9070 XT, Python 3.14.9

**The port is almost complete.** Installation, DX12, video, fonts, the live
window with keyboard and mouse, and Python versus Julia were checked on
this machine on 2026-10-21 and 22 (the window manually by Alex), and `-p`
opens the player. The Linux and macOS frame comparison required by §0
remains, because a shared shader changed.

- **§1 · Prepare.** Python came through uv (`uv python install 3.14`),
  not the python.org installer: there is no `py`, and `python` is still
  the Store shortcut. ffmpeg 9.0.2 and MiKTeX 26.5 (`latex`, `dvisvgm` 3.6,
  `AutoInstall=1`) came through winget. Git 2.56 was already installed
  with `core.autocrlf=true`: the first two clones had CRLF, as expected.
  DejaVu 2.37 and Liberation 2.1.5 installed for the user
  (`%LOCALAPPDATA%\Microsoft\Windows\Fonts`, registered in HKCU).
- **§2 · Install.** Confirmed: the wheels exist (wgpu-native 24.0.0.2 in
  wgpu's wheel) and `import wgpu` passes `NATIVE_VERSION`. Implemented
  as suggested: the Python part of bootstrap lives in `scripts/bootstrap.py`;
  `bootstrap.sh` calls it as before, and `scripts/bootstrap.cmd` calls it
  after creating the venv with `py -3.14`, `uv venv --seed` or `python3.14`.
  **Two surprises:** uv's `python3.14.exe` is a launcher and `venv` cannot
  copy it (`ensurepip` fails), hence the uv branch; and pip fails with
  `[Errno 2]` inside long paths (the wheel's `numpy` exceeds MAX_PATH):
  a clone two or three directories from the root avoids this.
  `bin/janim.cmd` serves as `bin/janim`, and PowerShell finds it as
  `bin\janim`. The `.gitattributes` (`bin/janim` and `*.sh` LF, `*.cmd`
  CRLF) resolves CRLF for clones using `autocrlf=true`. **False:** that the
  backend would fail first. The first failure was
  `UnicodeDecodeError: 'charmap' codec can't decode byte 0x81` when reading
  `stencil.wgsl`: `read_text()` without `encoding` uses cp1252 on Windows
  (Python 3.14 does not default to UTF-8 yet; that arrives in 3.15), and
  shaders contain `──`. Fixed with `encoding="utf-8"` in the nine
  `read_text` and `write_text` calls lacking it (`pipelines.py`,
  `compositor.py`, `triangle.py`, `window.py`, `core/model.py`,
  `scene/scene.py`, `text/tex.py`).
- **§3 · DX12.** Done: `BACKEND = {"darwin": "Metal", "win32":
  "DX12"}.get(sys.platform, "Vulkan")` in `context.py`, and both
  `native.py` tables gain `DX12` (`1 << 3`, `WGPUBackendType_D3D12`).
  Before the change, using Vulkan on AMD's driver (26.10.1, LLPC), the
  first `create_render_pipeline` died with an *access violation* inside
  wgpu-native, with nothing in `JANIM_WGPU_LOG=info`: Vulkan on Windows
  is not an option with this driver. **§3.3, confirmed:**
  `JANIM_HEADLESS=1` works: WARP appears as “Microsoft Basic Render
  Driver”, type `cpu`, and produces different bytes from the GPU.
  **§3.4, false:** DX12 does not provide the vendor name. wgpu-native puts
  the driver version (“32.0.32015.7029”) in `vendor` and leaves
  `description` empty, so the slug is `320320157029` (WARP:
  `100261009711`, the Windows build), and the version is `unknown`.
  Nothing breaks, but the slug changes with every driver; if it matters,
  derive it from `vendor_id` (0x1002 AMD, 0x10DE NVIDIA, 0x8086 Intel,
  0x1414 Microsoft). **What FXC cannot compile:** `effects.wgsl` wrote
  `grille[col] = 1.0`, a dynamically indexed `vec3` component, and demo 06
  (CRT effect) died with `X3500: array reference cannot be used as an l-value`.
  It was the only such write in the shaders; it is now a `select` with
  the same value in both libraries. The twelve demos render at 1280×720
  and 60 fps (12 requires “Fredoka Expanded”, not installed), and in Python
  04 and 07 take 50 s versus 11 and 9 in Julia: CPU, not GPU.
- **§4 · Video.** Confirmed the failure (`WinError 10038` in
  `video.py:290`) and made the minimal fix: on `win32`, skip `select`,
  write to the nonblocking pipe and sleep 1 ms when `BlockingIOError`
  says it is full. `finish` worked as is. **The `-j 2` farm** works
  without touching `concat_listing`: paths are single-quoted, and the
  demuxer does not interpret `\` inside them.
- **§5 · Fonts.** Done: `_font_catalog` gains the `win32` branch with
  BaseDirs' two directories in their order (system, then user), without
  recursion. “DejaVu Sans” resolves to the user's `DejaVuSans.ttf` among
  374 faces, and the frame matches the one with
  `FREETYPE_ABSTRACTION_FONT_PATH` byte for byte.
- **§6 · Everything else.** Done: `open_output` uses `os.startfile`
  on `win32` (`render … -p` opens the player). Confirmed that drive-letter
  addresses survive (`C:\…\03_portals.py:Portals` renders). GLFW was
  handled in §7; `LIBRARY`, LaTeX and the cache work as described.
- **§7 · The window.** Implemented as expected: `native_handles` returns
  the HWND and wgpu-py builds `WGPUSurfaceSourceWindowsHWND`;
  `create_window` accepts `win32`; `JANIM_GLFW_PLATFORM` accepts `win32`
  or `null`. **Unexpected:** `_headless_env` treated Windows as headless
  (no `DISPLAY`), and GLFW started in Null; Win32 now counts like macOS.
  The surface offers `bgra8unorm-srgb` first (`bgra8unorm` is used),
  mailbox, Fifo and Immediate, and CopySrc; `framebuffer_size` is
  `(854, 480)` for an 854×480 window. The live loop with `03_portals`
  at 15 fps presented 69 frames in 5 s without reconfiguring.
  **Keyboard and mouse:** tested manually by Alex on 2026-10-22: they work.
- **§8 · Python versus Julia.** Done with both harnesses from Janim.jl's
  `MACOS.md`, at 640×360 and 10 fps, one process per render: the five demos
  produce **byte-identical frames** on DX12 (140, 140, 180, 141 and 220).
- **Unchanged:** `live.py`, `cli.py`, `bin/janim`.

## 0 · Working rules

- **The goal** is to make file rendering, the `bin/janim` CLI and the live
  window work on Windows 11 with the machine's GPU.
- **Linux and macOS must not change.** Everything specific to Windows goes
  inside `sys.platform == "win32"`, and the code executed and frames
  produced on Linux and macOS must stay the same as today. Back on those
  machines, repeat the frame comparison against the previous version.
- **There are no reference frames in the repo.** On DX12, many edges will
  shift by one pixel compared with Linux and Metal, so a byte difference
  is not a bug. Look for things that look WRONG. Inspect the scenes;
  exit 0 says nothing about what is on screen.
- **Commits only with Alex's permission, and never push.** One commit per
  fix, in Spanish, explaining why. No new dependency without asking;
  I expect none from the wheels (§2). Only text and SVG in git.
- **Suggested order:**
  1. Install (§1, §2): bootstrap and launcher do not know about `Scripts\`.
  2. Make the instance select DX12 (§3).
  3. Fix the video writer, which uses `select` on a pipe (§4).
  4. Render a simple scene to a file; then formulas, layers and 3D.
  5. Fonts (§5) and other code written for Unix (§6).
  6. Leave the live window until last (§7).
  7. Python versus Julia on the same machine (§8).

## 1 · Prepare Windows

- **Windows 11** (or Windows 10 with DX12). The GPU needs a WDDM driver
  with Direct3D 12; any GPU from the last decade has one. Without a GPU,
  DX12 offers WARP, Microsoft's software rasterizer (§3).
- **Python 3.14**: the python.org installer or `winget install
  Python.Python.3.14`, with the `py` launcher. Check `py -3.14 --version`.
- **Git for Windows**, for Git Bash: `scripts/bootstrap.sh` and
  `bin/janim` are bash scripts. Watch `core.autocrlf`: if `true`
  (the installer's default), scripts get CRLF and bash dies with
  `$'\r': command not found`. See §2.
- **ffmpeg** on `PATH`: `winget install Gyan.FFmpeg` (or chocolatey,
  scoop). Janim calls it by name, `ffmpeg`/`ffprobe`; `shutil.which`
  finds the `.exe` files.
- **Fonts:** Windows does not include DejaVu. Download it from
  dejavu-fonts.github.io and install “for all users” (goes in
  `C:\Windows\Fonts`) or just yourself (goes in
  `%LOCALAPPDATA%\Microsoft\Windows\Fonts`). Both directories are searched
  (§5). Some lessons require “Liberation Serif” and “Liberation Mono”.
- **LaTeX, optional, for `Tex`/`MathTex`:** MiKTeX (includes `dvisvgm`)
  or TeX Live. Put `latex.exe` and `dvisvgm.exe` on `PATH`. In MiKTeX,
  set missing-package installation to “always”, or the first `Tex`
  waits for a dialog nobody sees.
- **Windows Terminal**: the progress bar uses ANSI sequences
  (`\r\033[K`), which old conhost does not understand.

## 2 · Install: what will fail before starting

Verified from the Mac with `pip download --platform win_amd64
--python-version 3.14 --only-binary=:all: --no-deps`: **Windows x86-64
wheels exist for all** versions pinned in `pyproject.toml`, and none
declares a Windows-only dependency (wgpu's only platform marker is
`rubicon-objc; sys_platform == 'darwin'`). Their native components:

| package | what it includes for Windows |
|---|---|
| `wgpu==0.21.0` | `wgpu/resources/wgpu_native-release.dll` (7.8 MB), wgpu-native v24; `NATIVE_VERSION = (24, 0)` in `context.py` should pass |
| `glfw==2.10.2` | `glfw/glfw3.dll` and `glfw/msvcr120.dll` |
| `freetype-py==2.5.1` | `freetype/libfreetype.dll` |
| `numpy==2.4.6` | `cp314-win_amd64` |
| `cffi==2.1.1` | `cp314-win_amd64` |

`wgpu_native-release.dll` is built with MSVC; it needs the Visual C++
runtime (`vcruntime140.dll`), already included in Windows 11.
If `import wgpu` reports a missing DLL, install “Microsoft Visual C++
Redistributable”.

**What will fail:**

1. **`scripts/bootstrap.sh`** calls `python3.14`, which does not exist
   on Windows (it is `py -3.14` or `python`), and creates the venv
   expecting `.venv/bin/python`, which is `.venv\Scripts\python.exe`
   on Windows. **`bin/janim`** uses the same path. My suggestion,
   without changing what Linux does today:
   - move bootstrap's Python part (the heredoc: pip with
     `--only-binary=:all: --no-deps` for `pyproject.toml`'s versions and
     `janim.pth`) into `scripts/bootstrap.py`, so `bootstrap.sh` calls
     it and a new `scripts/bootstrap.cmd` does the same with
     `py -3.14 -m venv .venv` and `.venv\Scripts\python.exe scripts\bootstrap.py`;
   - a four-line `bin/janim.cmd` using `.venv\Scripts\python.exe` if it
     exists, otherwise `py -3.14`, and running `-m janim.cli %*`.
   A smaller alternative: have both bash scripts detect
   `.venv/Scripts/python.exe` for Git Bash users. The `.pth` goes in
   `Lib\site-packages`: `sysconfig.get_path("purelib")` already resolves it.
2. **CRLF.** With `core.autocrlf=true`, bash scripts break. Add
   `.gitattributes` with `* text=auto`, `bin/janim text eol=lf` and
   `scripts/*.sh text eol=lf` (`.wgsl` and `.py` handle CRLF, but
   `eol=lf` for the whole repo is simplest). Ask permission:
   it is a new file in git.
3. **`PYTHON=... scripts/bootstrap.sh` from Git Bash:** `python3.14`
   does not exist, but `PYTHON=py` also fails (the launcher needs `-3.14`).
   This is what the `.cmd` solves.

Afterward:

```bat
scripts\bootstrap.cmd
.venv\Scripts\python.exe -c "import janim, wgpu; print(wgpu.__version__)"
```

## 3 · Make the instance select DX12 (the first rendering failure)

1. **Backend.** `context.BACKEND` says “Metal” on darwin and “Vulkan”
   elsewhere; on `win32` it must say “DX12”, because Janim.jl selects
   DX12 on Windows (`src/backend/wgpu/context.jl:242`,
   `_instance_backends`), and §8's comparison requires the same backend
   in both. Vulkan exists on Windows, but DX12 is wgpu's most-tested
   path and offers WARP. In `native.py`:
   `_INSTANCE_BACKENDS["DX12"] = 1 << 3` (verified in
   `wgpu/resources/wgpu.h`: `WGPUInstanceBackend_DX12 = 1 << 3`), and
   `_BACKEND_TYPES["DX12"] = lib.WGPUBackendType_D3D12` (= 4 in
   `webgpu.h`). Messages already use `BACKEND`.
2. **Shader compiler.** `WGPUInstanceExtras` has `dx12ShaderCompiler`,
   `dxilPath` and `dxcPath` (verified in `wgpu.h`); `native.py` does
   not touch them, and Julia passes `WGPUDx12Compiler_Undefined`,
   so both use FXC (`d3dcompiler_47.dll`, included with Windows).
   DXC would give different precision and needs two more DLLs:
   do not change it; if you do, change it in both libraries.
3. **`JANIM_HEADLESS=1` may WORK on Windows.** DX12 enumerates WARP
   (“Microsoft Basic Render Driver”), and wgpu reports it as a `CPU`
   adapter, exactly what `choose_adapter` seeks. Check:
   `JANIM_HEADLESS=1 bin/janim render … -qs` and `gpu_info()`; the slug
   comes from `vendor` (“Microsoft” → `microsoft`). If it works, the
   READMEs and `llms.txt` can no longer call headless mode Linux-only.
4. **Driver identity.** DX12 provides vendor names (“NVIDIA”, “Advanced
   Micro Devices, Inc.”, “Intel”), so the slug will be `nvidia`,
   `advancedmicrodevicesinc` or `intel`, and `description` the driver
   version. Ensure a new name does not break anything in the `# driver:` header.
5. **Limits:** on DX12, `min-uniform-buffer-offset-alignment` is 256,
   as on Metal; the code already supports it. `float32-filterable` exists.
6. **A wgpu-native panic kills the process.** If it dies abruptly,
   repeat with `JANIM_WGPU_LOG=info` (or `debug`) and inspect the last call.

First test (as soon as §4 is done):

```bat
bin\janim render examples\tutorial\c1_01_basics\01_how_janim_works.py -ql
```

Then, in order: **formulas**
(`examples/tutorial/c1_03_groups_and_text/04_latex.py`), **layers and
effects** (`examples/demo/03_portals.py`), **3D**
(`examples/tutorial/c2_03_camera/03_camera_3d.py` and
`examples/demo/07_text_mask.py`), **particles and bloom**
(`examples/demo/04_lorenz_glow.py`). Inspect each Transform's midpoint,
the first frame and the last (`bin/janim frame …`).

## 4 · Video: Windows has no pipe support in `select`

`janim/video.py:290` waits for ffmpeg's pipe to become writable using
`select.select([], [descriptor], [], 0.01)`. On Windows, `select` only
accepts sockets: the first frame ends with `OSError: [WinError 10038]`.
The rest of the writer works: `os.set_blocking(fd, False)` (line 202)
works on Windows pipes since Python 3.12, `os.write` on a nonblocking
pipe raises `BlockingIOError` when full, and the loop already handles
that case with `continue`.

- **Suggested minimal fix:** on `win32`, do not call `select`; instead,
  sleep for one millisecond when writing makes no progress, so the loop
  does not spin. Leave the Linux branch byte for byte identical and add
  `if sys.platform == "win32": time.sleep(0.001)` where `select` is.
  The cleaner alternative (a writer thread with blocking writes) changes
  the writer's design; do not do it without asking.
- **`finish`** (lines 316-345) does not use `select`: it closes `stdin`
  and waits with `poll`; it works unchanged. `janim/scene/audio.py` uses
  `subprocess.run`; that works.
- **The farm (`-j`)** launches
  `subprocess.Popen([sys.executable, "-c", code])` (`scene.py:800`) and
  inserts paths into `code` with `repr`, so Windows backslashes survive.
  Inspect ffmpeg's `concat` list file (`scene.py:741`, “in its own quoting”):
  for `C:\…` paths, writing `/` is advisable; the demuxer accepts it
  without treating it as an escape.
- **`core/image.py`** calls `ffprobe`/`ffmpeg` by name with
  `subprocess.run`: that works.

## 5 · Fonts: the catalog knows Linux and macOS, not Windows

`janim/text/glyphs.py` (`_font_catalog`) has a darwin branch and an XDG
branch. It will find nothing on Windows.

Match FreeTypeAbstraction, as on the other two platforms. Verified in
BaseDirs' code (`nt.jl`): on Windows, `FONTS_DIRS` is

1. the system `Fonts` directory, through its “known folder”
   (`C:\Windows\Fonts`);
2. `%LOCALAPPDATA%\Microsoft\Windows\Fonts` (fonts installed “just for me”).

In that order, system BEFORE user (the reverse of macOS), and **without
entering subdirectories**: FreeTypeAbstraction recurses only for
`Sys.isunix() && !Sys.isapple()`. In Python:
`Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"` and
`Path(os.environ["LOCALAPPDATA"]) / "Microsoft/Windows/Fonts"`, flat.
If order or traversal differs, the libraries may choose different faces
for the same name, which §8 will catch.

`C:\Windows\Fonts` contains many `.ttc` files (load the first face, as
in FreeTypeAbstraction) and bitmap `.fon` files that FreeType can open
with unusual family names; they do not interfere with scoring, but check
that `find_face("DejaVu Sans")` resolves to `DejaVuSans.ttf` and nothing else.

## 6 · Other code written for Unix

- **GLFW:** `janim/backend/glfw.py`. `LIBRARY`
  (`/usr/lib64/libglfw.so.3`) does not exist, so the wheel's `glfw3.dll`
  is used. `_headless_env` decides “no display” without `DISPLAY`:
  treat `win32` as having a display, like darwin. The
  `JANIM_GLFW_PLATFORM` table should accept `null` or `win32`
  (`glfw.PLATFORM_WIN32`, verified in pyglfw 2.10.2: `0x00060001`),
  and `names` gains `"win32"`. `_point_xkb_at_x_locale` does not apply.
- **`-p`:** `cli.py:329` (`open_output`) only knows `open` and
  `xdg-open`; on Windows use `os.startfile(path)`.
- **`bin/janim`:** `readlink -f` exists in Git Bash; what does not exist
  is `.venv/bin/python` (§2).
- **LaTeX:** `tex.py` finds `latex` and `dvisvgm` with `shutil.which`,
  which finds `.exe` files; the cache goes to `%XDG_CACHE_HOME%` or
  `~/.cache/janim/tex`, which on Windows is
  `C:\Users\<you>\.cache\janim\tex`. That works.
- **`C:\x.py:Class` addresses:** `janim/scene/address.py` splits at
  the LAST `:` whose left side ends in `.py`, so the drive letter
  survives (`C:\…\x.py` does not end in `.py` before its `:`).
  Check with `bin/janim render C:\…\scenes.py:Hello -qs`.
- **`MESA_VK_IGNORE_CONFORMANCE_WARNING`** (`context.py:53`) is harmless.
- **Code that is not Unix-specific:** `threading`, `time.monotonic`,
  `Path.home()`, `tempfile`, `subprocess`. There is no `fcntl`,
  `signal`, `fork` or `setsid` in the package (verified with grep).
  The only `select` is the one in §4.

## 7 · The live window: what remains to implement

1. **The surface source.** `glfw.py` (`native_handles`) returns Wayland,
   X11 or Cocoa. For Win32, return
   `{"platform": "win32", "window": int(glfw.get_win32_window(window.handle))}`
   (verified: pyglfw 2.10.2 has `get_win32_window`).
   `native.create_surface` passes it to wgpu-py's
   `_helpers.get_surface_id_from_info`, whose `win` branch already builds
   `WGPUSurfaceSourceWindowsHWND` with `hwnd` and an `hinstance` from
   `GetModuleHandleW` (verified in
   `wgpu/backends/wgpu_native/_helpers.py:107-112`).
   No Win32 code needs to be written.
2. **`create_window`** (`janim/backend/wgpu/window.py`) accepts
   `wayland`, `x11` and `cocoa`: add `win32`.
3. **No Retina step.** On Windows, GLFW declares the process per-monitor
   DPI-aware; with `GLFW_SCALE_TO_MONITOR` off (the default), the window
   is created at the requested pixel size and `framebuffer_size` matches
   the window size. On a 4K screen the window will look small; that is
   not a bug. Check `framebuffer_size == (1280, 720)` and that
   `sync_content_scale` (specific to Cocoa) is not called.
4. **Format and modes:** DX12 prefers `bgra8unorm` or its sRGB variant;
   `plain_format` handles both. Fifo exists. CopySrc is usually offered
   on DX12's swapchain; if `present_readback` returns `None`, it is
   unavailable, which is not an error.
5. **The main thread.** Win32 delivers a window's messages to the thread
   that created it: the main thread, as today. The playhead
   (`janim-playhead`) does not touch GLFW.
6. **Modal loops.** Dragging the title bar puts Windows in a modal loop
   that blocks `poll_events` until release: preview freezes during the
   drag and resumes afterward. This is normal; do not “fix” it.
7. **Wayland's focus drain** (`drain_focus`) hides the window before
   destroying it; it did not interfere on Cocoa. If it causes flicker
   or delay on Windows, restrict it to Linux.

Test with `bin\janim examples\demo\03_portals.py`: keys (space, `,`/`.`,
←/→, `[`/`]`, Esc), mouse, and opening and closing two consecutive previews.

## 8 · A tool without Linux: Python versus Julia on the same Windows machine

This is §7 of `MACOS.md`, and both harnesses (per-frame hashes with
`frame_tap` in Python and `Janim._FRAME_TAP` in Julia) are in Janim.jl's
`MACOS.md`, §6. On Linux (RADV) and macOS (Metal), the five demos
`01_multicam`, `03_portals`, `04_lorenz_glow`, `07_text_mask` and
`11_chase_camera` produce byte-identical frames in both libraries;
on Windows, with both using DX12, they should still match.

**What we learned on macOS that may recur on DX12.** Python merges
consecutive meshes sharing a pipeline, uniform block and texture into
one `draw_indexed` (`render.py`, `_record_commands`); Julia issues
one call per mesh. On Metal, lit color interpolated over a triangle
changes in the last bit depending on the call containing it, and
`11_chase_camera` (three consecutive `Torus` objects) differed in all
220 frames while the other four matched. The fix was
`_MERGE_MESH_DRAWS = BACKEND != "Metal"`. If Windows shows the same
pattern (11 differs, the other four do not, and the differences are in
torus pixels), set `_MERGE_MESH_DRAWS = BACKEND not in ("Metal", "DX12")`,
measure again and check that the other four do not change a byte.
If more demos differ, inspect fonts first (§5), then the shader compiler (§3.2).

**Determinism:** the same scene in two processes on the same machine
must produce the same frames. Check a couple of scenes, and WARP if
§3.3 works (WARP is deterministic and does not depend on the GPU).

## 9 · What is not a Windows problem

- **Video motion blur does not exist** on any platform: `Scene` does
  not accept `motion_blur` and the CLI rejects `--motion-blur`.
  Demos 10 and 12 and the `c3_05_motion_blur` lessons explain this
  and fail the same way on Linux and macOS.
- **`c2_05_from_manim/01_from_manim_ce.py` says `-ql` does not exist**,
  but the CLI does support it.
- **Lessons requiring Liberation** raise `FontNotFound` if the family
  is not installed: this is deliberate.

## 10 · WSL2 is a shortcut, not the port

The Linux version runs unchanged in WSL2 (Ubuntu) with lavapipe
(`JANIM_HEADLESS=1`), and with WSLg it opens a Wayland window.
GPU access through Vulkan inside WSL2 depends on Mesa's experimental
`dzn` driver (Vulkan over D3D12). It helps with comparisons and getting
unstuck, but is not this file's goal: the goal is native Windows with DX12.

## 11 · When finished

Record here what you confirmed and what proved false (as in `MACOS.md`,
with a results section at the start), and in both READMEs' “Known
limitations” sections replace “Linux and macOS” with what actually works,
including the Windows version and GPU tested.
