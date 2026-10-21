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

- **Linux** con un driver Vulkan (Mesa RADV, lavapipe u otro). macOS y Windows
  todavía no están soportados.
- **Python 3.14.**
- **`ffmpeg`** en el `PATH`, para escribir vídeo.
- **`latex` y `dvisvgm`** en el `PATH`, para `Tex` y `MathTex`.
- Las fuentes que pidan tus escenas. Los ejemplos usan DejaVu Sans.

## Instalar

```bash
git clone https://github.com/<usuario>/Janim.py.git
cd Janim.py
scripts/bootstrap.sh        # crea .venv/ con numpy, wgpu, glfw y freetype-py
```

`PYTHON=/ruta/a/python3.14 scripts/bootstrap.sh` elige otro intérprete.

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
renderiza por CPU (lavapipe).

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

- **Solo Linux** por ahora.
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
