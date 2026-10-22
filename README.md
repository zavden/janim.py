# Janim

**English** · [Español](README.es.md)

Janim is a Python library for mathematical animation that speaks ManimGL's
vocabulary: `class X(Scene)`, `self.play`, `.animate`, `next_to`, `Text`,
`Tex`. It draws with WebGPU (`wgpu-py`), typesets formulas with LaTeX and text
with FreeType. On top of that it adds what Manim lacks: layers, masks,
compositor effects and a camera per layer.

The same code gives the same frames on every run: the clock is fixed and the
arithmetic does not depend on the system's libm.

## Requirements

- **Linux** with a Vulkan driver (Mesa RADV, lavapipe or another), **macOS 14
  or later on Apple Silicon**, where Janim draws with Metal (tested on macOS
  26.6, Apple M1), or **Windows 11**, where it draws with DX12 (tested on
  Windows 11 25H2, AMD Radeon RX 9070 XT). On Windows the port is partial:
  single frames render; video and the live window are still being written
  (see [`WINDOWS.md`](WINDOWS.md)).
- **Python 3.14.**
- **`ffmpeg`** on the `PATH`, to write video.
- **`latex` and `dvisvgm`** on the `PATH`, for `Tex` and `MathTex`.
- The fonts your scenes ask for. The examples use DejaVu Sans; a few lessons
  also ask for Liberation Serif and Liberation Mono.

## Install

```bash
git clone https://github.com/<user>/Janim.py.git
cd Janim.py
scripts/bootstrap.sh        # creates .venv/ with numpy, wgpu, glfw and freetype-py
```

`PYTHON=/path/to/python3.14 scripts/bootstrap.sh` picks another interpreter.
Before that, each platform needs its own packages.

### Linux

Python 3.14, Mesa's Vulkan drivers, ffmpeg, the DejaVu fonts and, for `Tex`,
LaTeX with the `standalone` class and `dvisvgm`:

```bash
# Fedora 43 or later (ffmpeg from RPM Fusion)
sudo dnf install python3 mesa-vulkan-drivers ffmpeg dejavu-sans-fonts \
  texlive-latex texlive-standalone texlive-preview texlive-amsmath texlive-amsfonts texlive-xcolor texlive-dvisvgm
# Debian, Ubuntu
sudo apt install python3.14 mesa-vulkan-drivers ffmpeg fonts-dejavu texlive-latex-extra dvisvgm
```

Where the distribution has no Python 3.14, [uv](https://docs.astral.sh/uv/)
provides one: `uv python install 3.14`, then
`PYTHON="$(uv python find 3.14)" scripts/bootstrap.sh`.

### macOS

Homebrew provides everything but LaTeX:

```bash
brew install python@3.14 ffmpeg
brew install --cask font-dejavu          # the examples' font, into ~/Library/Fonts
PYTHON=python3.14 scripts/bootstrap.sh   # also installs rubicon-objc, which wgpu needs on macOS
```

`Tex` needs MacTeX or BasicTeX plus `dvisvgm` (`sudo tlmgr install dvisvgm`
if it is missing); both live in `/Library/TeX/texbin`, which must be on the
`PATH`.

### Windows

In PowerShell. [uv](https://docs.astral.sh/uv/) fetches Python 3.14 and
builds the environment (`scripts/bootstrap.sh` expects `.venv/bin/python`
and does not run here yet); ffmpeg and MiKTeX, which brings `dvisvgm`, come
from winget. Git for Windows is needed only to clone: do it with
`git clone -c core.autocrlf=input …`, or the bash scripts come out with CRLF.

```powershell
winget install -e --id astral-sh.uv
winget install -e --id Gyan.FFmpeg
winget install -e --id MiKTeX.MiKTeX      # optional: Tex and MathTex
```

Open a new terminal so the `PATH` is fresh, then, in the checkout:

```powershell
uv venv --python 3.14 .venv
uv pip install --python .venv\Scripts\python.exe --only-binary :all: --no-deps numpy==2.4.6 wgpu==0.21.0 glfw==2.10.2 freetype-py==2.5.1 cffi==2.1.1 pycparser==3.0 sniffio==1.3.1
.venv\Scripts\python.exe -c "import pathlib, sysconfig; (pathlib.Path(sysconfig.get_path('purelib')) / 'janim.pth').write_text(str(pathlib.Path.cwd()) + '\n')"
```

Those are the versions `pyproject.toml` pins (`[project]` and
`[tool.janim.bootstrap]`, minus `rubicon-objc`, which is macOS only), and the
`.pth` makes the checkout importable, as the bootstrap does.

Fonts: download [DejaVu](https://github.com/dejavu-fonts/dejavu-fonts/releases)
(and [Liberation](https://github.com/liberationfonts/liberation-fonts/releases)),
select the `.ttf` files, right-click, *Install*. They land in
`%LOCALAPPDATA%\Microsoft\Windows\Fonts`, a folder Janim does not know yet,
so name it in every session that renders text:

```powershell
$env:FREETYPE_ABSTRACTION_FONT_PATH = "$env:LOCALAPPDATA\Microsoft\Windows\Fonts"
```

If you installed MiKTeX, open MiKTeX Console and set the on-the-fly package
installation to *Always* (or run
`initexmf --set-config-value=[MPM]AutoInstall=1`); otherwise the first `Tex`
waits for a dialog nobody sees.

`bin/janim` is bash; on Windows call the module instead:

```powershell
.venv\Scripts\python.exe -m janim.cli frame hello.py 20 f.png -ql
```

## A minimal scene

```python
from janim import *


class Hello(Scene):
    def construct(self):
        c = Circle(radius=1.0)
        c.set_fill(YELLOW, opacity=1.0)
        self.play(FadeIn(c, shift=0.5 * UP), run_time=0.8)
        self.play(Transform(c, Square()), run_time=1.2)
        self.wait(0.5)
```

Save it as `hello.py` and render it:

```bash
bin/janim render hello.py -ql            # the video, next to the scene
bin/janim hello.py                       # the live window; Esc or q to quit
bin/janim frame hello.py 20 f.png -ql    # a single frame
```

If a file holds several scenes, name the class after `:`
(`bin/janim render scenes.py:Hello -ql`). `bin/janim --help` shows the rest of
the command line.

The quality flag sets resolution and frame rate together:

| flag | resolution | fps |
|---|---|---|
| `-qs` | 640×360 | 10 |
| `-ql` | 854×480 | 15 |
| `-qm` | 1280×720 | 30 (default) |
| `-qh` | 1920×1080 | 60 |

Rendering runs on the GPU by default. Prefix a command with `JANIM_HEADLESS=1`
to render on the CPU (lavapipe on Linux, WARP on Windows; macOS has no CPU
adapter).

## Examples

| folder | contents |
|---|---|
| [`examples/tutorial/`](examples/tutorial/README.md) | the course: foundations, going deeper, what only Janim does, and the reference |
| [`examples/gallery/`](examples/gallery/) | minimal classics |
| [`examples/scenes/`](examples/scenes/) | complete scenes: masks, formulas, 2D and 3D, the compositor |
| [`examples/demo/`](examples/demo/README.md) | demos of layers, cameras and effects |

```bash
bin/janim render examples/demo/03_portals.py -ql
```

Each lesson explains itself in its docstring. Some examples, the demos among
them, are written in Spanish.

## Documentation

- [`llms.txt`](llms.txt): the whole API in one file.
- [`docs/cli.md`](docs/cli.md): the command line and the live window (Spanish).
- [`docs/compositor.md`](docs/compositor.md): layers, masks and effects (Spanish).
- [`docs/3d.md`](docs/3d.md): surfaces, camera and depth (Spanish).

## Known limitations

- **Windows is a partial port.** Single frames render (DX12); video and the
  live window do not yet. Frames are reproducible within a route (RADV,
  lavapipe, Metal, DX12 or WARP), and routes can differ from each other by a
  pixel at some edges.
- **No motion blur in video.** `Scene` takes no `motion_blur` or `shutter`,
  and the CLI rejects `--motion-blur`. What exists is `render_frame_motion`,
  which averages several exposures into a single frame. The lessons in
  `examples/tutorial/c3_05_motion_blur/` still describe the in-video version;
  they will be revised.

## License

MIT, see [`LICENSE`](LICENSE). Janim ports code from ManimGL, Manim Community,
Julia, several Julia packages and the `isosurfaces` package, all
MIT-licensed: their notices are in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
