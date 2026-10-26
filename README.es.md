# Janim

[English](README.md) · **Español**

Janim es una biblioteca de animación matemática en Python con el vocabulario
de ManimGL: `class X(Scene)`, `self.play`, `.animate`, `next_to`, `Text`,
`Tex`. Dibuja con WebGPU (`wgpu-py`), compone las fórmulas con LaTeX y el
texto con FreeType. Añade lo que Manim no tiene: capas, máscaras, efectos de
compositor y una cámara por capa.

El mismo código da los mismos frames en cada ejecución: el reloj es fijo y la
aritmética no depende de la libm del sistema; `janim.math` da a tus propios
updaters esa misma libm determinista, para floats y para arrays enteros.

## Requisitos

- **Linux** con un driver Vulkan (Mesa RADV, lavapipe u otro), **macOS 14 o
  posterior en Apple Silicon**, donde Janim dibuja con Metal (probado en
  macOS 26.6, Apple M1), o **Windows 11**, donde dibuja con DX12 (probado en
  Windows 11 25H2, AMD Radeon RX 9070 XT; el port es nuevo, ver
  [`history/2026-10/WINDOWS.md`](history/2026-10/WINDOWS.md)).
- **Python 3.14.**
- **`ffmpeg`** en el `PATH`, para escribir vídeo.
- **`latex` y `dvisvgm`** en el `PATH`, para `Tex` y `MathTex`.
- Una fuente monoespaciada para `Code`: DejaVu Sans Mono, Menlo, Consolas,
  Liberation Mono, Noto Sans Mono o Courier New.
- Las fuentes que pidan tus escenas. Los ejemplos usan DejaVu Sans; alguna
  lección pide también Liberation Serif y Liberation Mono.

## Instalar

```bash
git clone https://github.com/<usuario>/Janim.py.git
cd Janim.py
scripts/bootstrap.sh        # crea .venv/ con numpy, wgpu, glfw, freetype-py y pygments
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

En PowerShell. Python 3.14 viene de winget (`Python.Python.3.14`, con el
lanzador `py`) o de [uv](https://docs.astral.sh/uv/) (`astral-sh.uv`; el
bootstrap le pide la 3.14); ffmpeg y MiKTeX, que trae `dvisvgm`, vienen
también de winget. Git for Windows solo hace falta para clonar.

```powershell
winget install -e --id Python.Python.3.14
winget install -e --id Gyan.FFmpeg
winget install -e --id MiKTeX.MiKTeX      # opcional: Tex y MathTex
```

Abre un terminal nuevo para que cargue el `PATH` y, dentro del clon:

```powershell
scripts\bootstrap.cmd       # el bootstrap para cmd y PowerShell: py -3.14, si no uv, si no python3.14
```

Fuentes: descarga [DejaVu](https://github.com/dejavu-fonts/dejavu-fonts/releases)
(y [Liberation](https://github.com/liberationfonts/liberation-fonts/releases)),
selecciona los `.ttf`, clic derecho, *Instalar*. Van a
`%LOCALAPPDATA%\Microsoft\Windows\Fonts`, donde Janim las encuentra.

Si instalaste MiKTeX, abre MiKTeX Console y pon la instalación de paquetes
que falten en *Always* (o ejecuta
`initexmf --set-config-value=[MPM]AutoInstall=1`); si no, el primer `Tex` se
queda esperando un diálogo que nadie ve.

La línea de comandos también es `bin\janim` aquí (`bin\janim.cmd`, el gemelo
del `bin/janim` de bash):

```powershell
bin\janim render hola.py -ql
bin\janim hola.py
```

Tres cosas que Windows hace distinto. Clona como siempre: `.gitattributes`
deja los scripts bash con LF diga lo que diga `core.autocrlf`. Deja el clon
en una ruta corta (`C:\Users\tú\proyectos\…`): pip puede fallar en una
carpeta muy profunda, en el límite de 260 caracteres de Windows. Y `python` a
secas puede ser el atajo de la Store; el bootstrap y `bin\janim` usan el
intérprete del venv, así que no hay nada que cambiar (Configuración →
Aplicaciones → Configuración avanzada de aplicaciones → Alias de ejecución de
aplicaciones apaga el atajo). Usa Windows Terminal y no la consola antigua:
la barra de progreso es ANSI.

### Comprobar

Desde el clon, en cualquier plataforma (`.venv\Scripts\python.exe` y
`bin\janim` en Windows):

```bash
.venv/bin/python -c "from janim.backend.wgpu.context import gpu_info; print(gpu_info())"
bin/janim frame  examples/tutorial/c1_01_basics/01_how_janim_works.py 20 frame.png -qs
bin/janim render examples/tutorial/c1_01_basics/01_how_janim_works.py -ql -o hola.mp4
```

La primera línea dice la GPU y el backend (`vulkan`, `metal` o `dx12`; con
`JANIM_HEADLESS=1`, lavapipe o WARP, `kind='cpu'`). La segunda escribe un
frame sin ffmpeg; la tercera es la cadena entera, ffmpeg incluido, y con `-p`
abre el vídeo. Una escena con `Tex` o `MathTex` comprueba LaTeX y `dvisvgm`;
en Windows la primera instala paquetes de MiKTeX y tarda.

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

- **Windows es nuevo.** El render, la granja y la ventana viva corren sobre
  DX12, comprobado en una sola máquina (Windows 11, AMD Radeon RX 9070 XT).
  Los frames son reproducibles dentro de cada ruta (RADV, lavapipe, Metal,
  DX12 o WARP), y las rutas pueden diferir entre sí en un píxel en algunos
  bordes.
- **No hay desenfoque de movimiento en el vídeo.** `Scene` no acepta
  `motion_blur` ni `shutter`, y la CLI rechaza `--motion-blur`. Lo que sí
  existe es `render_frame_motion`, que promedia varias exposiciones en un solo
  frame. Las lecciones de `examples/tutorial/c3_05_motion_blur/` todavía
  describen la versión en el vídeo; se revisarán.
- **Lo demás que queda abierto** está en [`TODO.md`](TODO.md).

## Licencia

MIT, ver [`LICENSE`](LICENSE). Janim porta código de ManimGL, Manim Community,
Julia, varios paquetes de Julia y el paquete `isosurfaces`, todos con licencia
MIT: los avisos están en
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
