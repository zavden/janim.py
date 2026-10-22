# Janim

[English](README.md) · **Español**

Janim es una biblioteca de animación matemática en Python con el vocabulario
de ManimGL: `class X(Scene)`, `self.play`, `.animate`, `next_to`, `Text`,
`Tex`. Dibuja con WebGPU (`wgpu-py`), compone las fórmulas con LaTeX y el
texto con FreeType. Añade lo que Manim no tiene: capas, máscaras, efectos de
compositor y una cámara por capa.

El mismo código da los mismos frames en cada ejecución: el reloj es fijo y la
aritmética no depende de la libm del sistema.

## Requisitos

- **Linux** con un driver Vulkan (Mesa RADV, lavapipe u otro), **macOS 14 o
  posterior en Apple Silicon**, donde Janim dibuja con Metal (probado en
  macOS 26.6, Apple M1), o **Windows 11**, donde dibuja con DX12 (probado en
  Windows 11 25H2, AMD Radeon RX 9070 XT). En Windows el port es parcial: los
  frames sueltos se renderizan; el vídeo y la ventana viva están por escribir
  (ver [`WINDOWS.md`](WINDOWS.md)).
- **Python 3.14.**
- **`ffmpeg`** en el `PATH`, para escribir vídeo.
- **`latex` y `dvisvgm`** en el `PATH`, para `Tex` y `MathTex`.
- Las fuentes que pidan tus escenas. Los ejemplos usan DejaVu Sans; alguna
  lección pide también Liberation Serif y Liberation Mono.

## Instalar

```bash
git clone https://github.com/<usuario>/Janim.py.git
cd Janim.py
scripts/bootstrap.sh        # crea .venv/ con numpy, wgpu, glfw y freetype-py
```

`PYTHON=/ruta/a/python3.14 scripts/bootstrap.sh` elige otro intérprete. Antes,
cada plataforma necesita sus paquetes.

### Linux

Python 3.14, los drivers Vulkan de Mesa, ffmpeg, las fuentes DejaVu y, para
`Tex`, LaTeX con la clase `standalone` y `dvisvgm`:

```bash
# Fedora 43 o posterior (ffmpeg, de RPM Fusion)
sudo dnf install python3 mesa-vulkan-drivers ffmpeg dejavu-sans-fonts \
  texlive-latex texlive-standalone texlive-preview texlive-amsmath texlive-amsfonts texlive-xcolor texlive-dvisvgm
# Debian, Ubuntu
sudo apt install python3.14 mesa-vulkan-drivers ffmpeg fonts-dejavu texlive-latex-extra dvisvgm
```

Si la distribución no tiene Python 3.14, [uv](https://docs.astral.sh/uv/) lo
da: `uv python install 3.14` y luego
`PYTHON="$(uv python find 3.14)" scripts/bootstrap.sh`.

### macOS

Homebrew da todo menos LaTeX:

```bash
brew install python@3.14 ffmpeg
brew install --cask font-dejavu          # la fuente de los ejemplos, en ~/Library/Fonts
PYTHON=python3.14 scripts/bootstrap.sh   # instala también rubicon-objc, que wgpu necesita en macOS
```

`Tex` necesita MacTeX o BasicTeX más `dvisvgm` (`sudo tlmgr install dvisvgm`
si falta); los dos quedan en `/Library/TeX/texbin`, que debe estar en el
`PATH`.

### Windows

En PowerShell. [uv](https://docs.astral.sh/uv/) descarga Python 3.14 y
construye el entorno (`scripts/bootstrap.sh` espera `.venv/bin/python` y
todavía no sirve aquí); ffmpeg y MiKTeX, que trae `dvisvgm`, vienen de
winget. Git for Windows solo hace falta para clonar: hazlo con
`git clone -c core.autocrlf=input …`, o los scripts bash salen con CRLF.

```powershell
winget install -e --id astral-sh.uv
winget install -e --id Gyan.FFmpeg
winget install -e --id MiKTeX.MiKTeX      # opcional: Tex y MathTex
```

Abre un terminal nuevo para que cargue el `PATH` y, dentro del clon:

```powershell
uv venv --python 3.14 .venv
uv pip install --python .venv\Scripts\python.exe --only-binary :all: --no-deps numpy==2.4.6 wgpu==0.21.0 glfw==2.10.2 freetype-py==2.5.1 cffi==2.1.1 pycparser==3.0 sniffio==1.3.1
.venv\Scripts\python.exe -c "import pathlib, sysconfig; (pathlib.Path(sysconfig.get_path('purelib')) / 'janim.pth').write_text(str(pathlib.Path.cwd()) + '\n')"
```

Son las versiones que fija `pyproject.toml` (`[project]` y
`[tool.janim.bootstrap]`, sin `rubicon-objc`, que es solo de macOS), y el
`.pth` hace importable el clon, como hace el bootstrap.

Fuentes: descarga [DejaVu](https://github.com/dejavu-fonts/dejavu-fonts/releases)
(y [Liberation](https://github.com/liberationfonts/liberation-fonts/releases)),
selecciona los `.ttf`, clic derecho, *Instalar*. Van a
`%LOCALAPPDATA%\Microsoft\Windows\Fonts`, una carpeta que Janim todavía no
conoce, así que nómbrala en cada sesión que renderice texto:

```powershell
$env:FREETYPE_ABSTRACTION_FONT_PATH = "$env:LOCALAPPDATA\Microsoft\Windows\Fonts"
```

Si instalaste MiKTeX, abre MiKTeX Console y pon la instalación de paquetes
que falten en *Always* (o ejecuta
`initexmf --set-config-value=[MPM]AutoInstall=1`); si no, el primer `Tex` se
queda esperando un diálogo que nadie ve.

`bin/janim` es bash; en Windows llama al módulo:

```powershell
.venv\Scripts\python.exe -m janim.cli frame hola.py 20 f.png -ql
```

## Una escena mínima

```python
from janim import *


class Hola(Scene):
    def construct(self):
        c = Circle(radius=1.0)
        c.set_fill(YELLOW, opacity=1.0)
        self.play(FadeIn(c, shift=0.5 * UP), run_time=0.8)
        self.play(Transform(c, Square()), run_time=1.2)
        self.wait(0.5)
```

Guárdala como `hola.py` y renderízala:

```bash
bin/janim render hola.py -ql            # el vídeo, junto a la escena
bin/janim hola.py                       # la ventana viva; Esc o q para salir
bin/janim frame hola.py 20 f.png -ql    # un solo frame
```

Si un fichero tiene varias escenas, nombra la clase después de `:`
(`bin/janim render escenas.py:Hola -ql`). `bin/janim --help` muestra el resto
de la línea de comandos.

La calidad fija la resolución y los fps a la vez:

| flag | resolución | fps |
|---|---|---|
| `-qs` | 640×360 | 10 |
| `-ql` | 854×480 | 15 |
| `-qm` | 1280×720 | 30 (por defecto) |
| `-qh` | 1920×1080 | 60 |

Por defecto se renderiza en la GPU. `JANIM_HEADLESS=1` delante de la orden
renderiza por CPU (lavapipe en Linux, WARP en Windows; macOS no tiene
adaptador de CPU).

## Ejemplos

| carpeta | qué hay |
|---|---|
| [`examples/tutorial/`](examples/tutorial/README.md) | el curso: fundamentos, temas avanzados, lo que solo Janim hace, y la referencia |
| [`examples/gallery/`](examples/gallery/) | clásicos mínimos |
| [`examples/scenes/`](examples/scenes/) | escenas completas: máscaras, fórmulas, 2D y 3D, compositor |
| [`examples/demo/`](examples/demo/README.md) | demos de capas, cámaras y efectos |

```bash
bin/janim render examples/demo/03_portals.py -ql
```

## Documentación

- [`llms.txt`](llms.txt): la API entera en un fichero.
- [`docs/cli.md`](docs/cli.md): la línea de comandos y la ventana viva.
- [`docs/compositor.md`](docs/compositor.md): capas, máscaras y efectos.
- [`docs/3d.md`](docs/3d.md): superficies, cámara y profundidad.

## Limitaciones conocidas

- **Windows es un port parcial.** Los frames sueltos se renderizan (DX12); el
  vídeo y la ventana viva todavía no. Los frames son reproducibles dentro de
  cada ruta (RADV, lavapipe, Metal, DX12 o WARP), y las rutas pueden diferir
  entre sí en un píxel en algunos bordes.
- **No hay desenfoque de movimiento en el vídeo.** `Scene` no acepta
  `motion_blur` ni `shutter`, y la CLI rechaza `--motion-blur`. Lo que sí
  existe es `render_frame_motion`, que promedia varias exposiciones en un solo
  frame. Las lecciones de `examples/tutorial/c3_05_motion_blur/` todavía
  describen la versión en el vídeo; se revisarán.

## Licencia

MIT, ver [`LICENSE`](LICENSE). Janim porta código de ManimGL, Manim Community,
Julia, varios paquetes de Julia y el paquete `isosurfaces`, todos con licencia
MIT: los avisos están en
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
