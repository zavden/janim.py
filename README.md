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

- **Linux** with a Vulkan driver (Mesa RADV, lavapipe or another). macOS and
  Windows are not supported yet.
- **Python 3.14.**
- **`ffmpeg`** on the `PATH`, to write video.
- **`latex` and `dvisvgm`** on the `PATH`, for `Tex` and `MathTex`.
- The fonts your scenes ask for. The examples use DejaVu Sans.

## Install

```bash
git clone https://github.com/<user>/Janim.py.git
cd Janim.py
scripts/bootstrap.sh        # creates .venv/ with numpy, wgpu, glfw and freetype-py
```

`PYTHON=/path/to/python3.14 scripts/bootstrap.sh` picks another interpreter.

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
to render on the CPU (lavapipe).

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

- **Linux only** for now.
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
