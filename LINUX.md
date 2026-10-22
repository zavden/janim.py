# Janim (Python) en Linux · confirmar que el port a Windows no lo cambió · sugerencias para el agente

Escrito el 2026-10-22 en el Windows 11 donde se acaba de terminar el port a
Windows (`WINDOWS.md`, apartado «Resultado»), **sin probar nada en Linux**
desde entonces. La regla del port era que Linux y macOS no cambiaran: todo lo
de Windows va tras `sys.platform == "win32"`, y el código que corre y los
frames que salen en Linux deben ser los mismos que antes. Este fichero dice
dónde mirar para confirmarlo, qué quedó sin probar en Linux (las líneas de
instalación del README) y qué anotar. Lo que pude comprobar desde aquí (el
diff, las fuentes de las bibliotecas) lleva la marca «comprobado». Si algo
resulta falso, corrígelo en este fichero y di que lo estaba.

El repo hermano, Janim.jl, tiene su propio `LINUX.md`. Las dos bibliotecas
comparten los shaders WGSL, y el único shader común que cambió es el mismo en
las dos (§2). Los arneses de comparación están en el `MACOS.md` de Janim.jl,
§6.

## 0 · Reglas de trabajo

- **El objetivo** es confirmar que en Linux nada cambió: ni el código que
  corre ni los frames. No es un port: si todo coincide, el trabajo es corto.
- **El antes** es el commit `ce98cf2` («WINDOWS.md: sugerencias para portar
  Janim a Windows 11»), el último `main` anterior al port; **el después** es
  `main`. Los 14 commits entre los dos: `git log --oneline ce98cf2..main`.
- **Windows y macOS no pueden cambiar** desde aquí: no hay máquina donde
  probarlos. Si algo de Linux hay que arreglar, va tras una compuerta de
  Linux, o fuera de toda compuerta solo si es idéntico en los tres.
- **Commits solo con permiso de Alex, y nunca push.** Un commit por arreglo,
  en español, que explique el porqué. Ninguna dependencia nueva sin preguntar.
  Solo texto y SVG en git.
- **No hay frames de referencia en el repo, pero aquí sí hay un antes:** el
  mismo Linux, la misma GPU, el commit `ce98cf2`. La comparación es byte a
  byte (§2), no a ojo.
- **El orden que sugiero:** instalar desde cero con el README (§1), comparar
  frames antes y después (§2), repasar el resto del código común (§3), la CLI
  y la ventana (§4), y anotar tiempos (§5).

## 1 · Instalar desde cero: las líneas de Linux del README no se han probado

El README (`### Linux`) da `dnf` para Fedora 43 y `apt` para Debian/Ubuntu,
escritos sin una máquina Linux delante: los nombres de paquete, sobre todo los
de TeX Live (`texlive-standalone`, `texlive-preview`, `texlive-dvisvgm`) y
`python3.14` en Debian, pueden no existir con ese nombre en la distribución
que tengas. Sigue el README tal cual en un clon limpio, corrige las líneas
que fallen (en los dos idiomas) y pasa el apartado «Check it / Comprobar» que
viene tras las plataformas: `gpu_info()` debe decir `backend='vulkan'`.

`scripts/bootstrap.sh` ya no lleva el Python dentro: llama a
`scripts/bootstrap.py`, que es el heredoc de antes movido a un fichero para
que `bootstrap.cmd` lo comparta (comprobado en el diff: mismo `pip install`,
mismas opciones, mismo `janim.pth`). Compara `.venv/bin/pip list` con el de
un venv hecho desde `ce98cf2`: deben coincidir.

## 2 · Frames: antes y después, byte a byte

Lo único común que puede mover un píxel es
`janim/backend/wgpu/shaders/effects.wgsl`, en `fs_crt`: `grille[col] = 1.0`
(una escritura por índice dinámico, que el compilador de DX12 rechaza) pasó a
un `select` con el mismo valor:

```wgsl
let grille = select(vec3<f32>(1.0 - mask_depth * intensity), vec3<f32>(1.0),
                    vec3<bool>(col == 0, col == 1, col == 2));
```

Lo demás común son lecturas con `encoding="utf-8"` (§3), que no tocan ningún
frame. Aun así compara más de una demo: el arnés es barato.

Usa `tapf.py` del `MACOS.md` de Janim.jl, §6 (hashes SHA-256 por frame,
640×360 a 10 fps, un render por proceso), guardado fuera del repo, con dos
clones o un `git worktree add ../janim_py-antes ce98cf2` (con su propio
`scripts/bootstrap.sh`). Para cada demo, una lista de hashes con cada
checkout, y compáralas frame a frame:

- **`06_broadcast`** (clase `BroadcastScene`): es la del CRT, la única con un
  motivo para cambiar. Debe dar la misma lista. Si no, mira el shader: el
  `select` tiene que dar exactamente `1.0` en la franja `col` y
  `1.0 - mask_depth * intensity` en las otras dos.
- **`01_multicam`, `03_portals`, `04_lorenz_glow`, `07_text_mask`,
  `11_chase_camera`** (`Multicam`, `Portals`, `LorenzGlow`, `TextMask`,
  `ChaseCamera`): las cinco que en Linux dan lo mismo en Python y en Julia;
  sirven de control (no tocan el CRT) y, de paso, confirman que las dos
  bibliotecas siguen coincidiendo entre sí tras el port (en Windows, con
  DX12, las cinco siguieron coincidiendo byte a byte).

Una diferencia aquí es un fallo del port, no del driver: misma máquina, mismo
driver, un proceso por render.

## 3 · El resto del código común, fichero por fichero

Todo esto está comprobado en el diff (`git diff ce98cf2..main -- janim
scripts`); lo que hace falta en Linux es que corra.

| fichero | cambio | qué comprobar en Linux |
|---|---|---|
| `backend/wgpu/context.py` | `BACKEND = {"darwin": "Metal", "win32": "DX12"}.get(sys.platform, "Vulkan")` | `gpu_info()` dice `backend='vulkan'` |
| `backend/wgpu/native.py` | `_INSTANCE_BACKENDS` y `_BACKEND_TYPES` ganan `DX12` (`lib.WGPUBackendType_D3D12`, una constante que la cabecera define en todas las plataformas: comprobado en `webgpu.h`) | que `import janim` cargue |
| `backend/glfw.py` | `_headless_env` devuelve `False` para `("darwin", "win32")` en vez de solo `darwin`; `names` gana `glfw.PLATFORM_WIN32` (constante incondicional en pyGLFW 2.10.2, línea 648: comprobado); `native_handles` gana una rama `win32` tras la de `cocoa`, inalcanzable aquí | la ventana en vivo abre en Wayland y en X11; sin `DISPLAY` ni `WAYLAND_DISPLAY`, y con `JANIM_HEADLESS=1`, sigue saliendo `null` |
| `backend/wgpu/window.py` | `create_window` acepta `"win32"` en su tupla; `PRESENT_WGSL` se lee como UTF-8 | lo mismo |
| `video.py` | el `select.select` queda dentro de `if sys.platform != "win32"`, y el `except BlockingIOError` solo duerme en Windows; en Linux, las mismas líneas de antes | un render largo y uno con `-j 2`; el mismo número de frames que antes (`ffprobe`) |
| `cli.py` | `open_output` empieza con una rama `win32` (`os.startfile`) y `main` con otra (stdout en UTF-8); el resto, idéntico | `-p` abre con `xdg-open` |
| `text/glyphs.py` | `_font_catalog` gana una rama `elif sys.platform == "win32"` | DejaVu y Liberation se encuentran igual |
| nueve `read_text`/`write_text` con `encoding="utf-8"`: `pipelines.py:29,35`, `compositor.py:49`, `triangle.py:12`, `window.py:22`, `core/model.py:41,83`, `scene/scene.py:807`, `text/tex.py:111` y siguientes | sin `encoding`, Windows leía cp1252 y moría en el primer carácter no latino; en Linux el locale ya era UTF-8, así que son los mismos bytes | los shaders (cualquier render), un modelo (`core/model.py`), `Tex`, la granja (`scene.py:807` escribe la lista de ffmpeg) |
| `scripts/bootstrap.sh` → `scripts/bootstrap.py` | §1 | §1 |
| `.gitattributes`, `bin/janim.cmd`, `scripts/bootstrap.cmd` | ficheros para Windows; en Linux los `*.cmd` salen con CRLF a propósito | nada |
| `README*.md`, `llms.txt`, `WINDOWS.md` | documentación | las líneas de Linux (§1) |

`bin/janim` (bash) no cambió. Si tienes un Linux sin locale UTF-8 (`LANG=C`),
las lecturas con `encoding` explícito son justo lo que lo hace funcionar ahí
también; antes dependía del locale.

## 4 · La CLI y la ventana

Nada de esto cambió en Linux, así que es una pasada, no una búsqueda:

```bash
bin/janim render examples/demo/03_portals.py -ql -p          # xdg-open al terminar
bin/janim render examples/demo/03_portals.py -qs -j 2 -o /tmp/farm.mp4
bin/janim render examples/demo/03_portals.py -qs -t -o /tmp/alpha.mov
bin/janim render examples/demo/03_portals.py -s --to 40 -ql --out_dir /tmp/stills
bin/janim frame  examples/demo/03_portals.py 60 /tmp/f.png -ql
bin/janim examples/demo/03_portals.py                        # la ventana: teclas, ratón, Esc
```

La ventana, en Wayland y en X11 si la máquina tiene los dos
(`JANIM_GLFW_PLATFORM`, si existe esa variable, o la sesión que toque).

## 5 · Tiempos, para comparar con Windows

En Windows (Ryzen 7 9700X, Radeon RX 9070 XT, DX12, driver 32.0.32015.7029),
un render cada vez, tiempo de reloj del proceso entero (Python arranca en
~1 s; Julia, 4–5 s), medido el 2026-10-21 con `main` en `2a2f079`:

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
| 12_motion_blur | — | falla | falla | falla | falla |

La 04 y la 07 de Python van por la CPU (numpy), no por la GPU: su tiempo
apenas cambia con la resolución. La 12 pide la fuente «Fredoka Expanded»,
que no estaba instalada. Para repetirlo aquí, en el mismo orden y nunca dos a
la vez:

```bash
time bin/janim render examples/demo/01_multicam.py -r 1920x1080 --fps 60 -o /tmp/01.mp4
```

Anota la GPU, el driver de Mesa y los tiempos al principio de este fichero,
junto con el resultado del §2.

## 6 · Lo que no es un problema de Linux

- `12_motion_blur` falla por la fuente «Fredoka Expanded»; Alex dijo que se
  ignore, como el desenfoque de movimiento (`04`, `10`, `12`).
- Todo lo que está tras `sys.platform == "win32"`, `bin\janim.cmd` y
  `scripts\bootstrap.cmd`: no se puede probar aquí y no hay que tocarlo.

## 7 · Al terminar

Deja aquí, al principio de este fichero, una sección «Resultado» con la
distribución, la GPU, el driver, lo que coincidió y lo que no (como hacen
`MACOS.md` y `WINDOWS.md`). Si las líneas de Linux del README cambiaron, di
cuáles. Si todo coincide, el port está cerrado en las tres plataformas y Alex
decide el push.
