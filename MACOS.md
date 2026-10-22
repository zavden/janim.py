# Janim (Python) en macOS (Apple Silicon) · sugerencias para el agente

Escrito el 2026-10-21 en la máquina Linux de desarrollo (RADV, Fedora), **sin
probar nada en un Mac**. Son sugerencias, no instrucciones cerradas: cada punto
dice qué espero, dónde mirar y cómo confirmarlo. Si una resulta falsa,
corrígela aquí mismo y di que lo estaba.

El repo hermano, Janim.jl, tiene su propio `MACOS.md`, y en macOS va un paso
por delante: ya elige Metal. Las dos bibliotecas comparten los shaders WGSL y
la versión mayor de wgpu-native (v24), así que lo que aprendas en una sirve
para la otra. Si tienes los dos clones, lee también ese fichero.

## Resultado · 2026-10-21, macOS 26.6.2, Apple M1, Python 3.14.7 (Homebrew)

**El port está terminado.** Render a fichero, CLI y ventana en vivo con
teclas y ratón, verificados por Alex el 2026-10-21 en este M1, en las dos
bibliotecas; las siete primeras demos renderizadas a 1080p60 en las dos.

Probado en el Mac, sección por sección. Casi todo lo previsto era cierto; lo
que cambia está marcado.

- **§1 · Preparar.** Confirmado. `brew install --cask font-dejavu` deja las
  DejaVu en `~/Library/Fonts`. Las lecciones que piden «Liberation Serif» o
  «Liberation Mono» (`c1_03/03_text.py` entre ellas) dan el `FontNotFound`
  esperado si no se instala `font-liberation`. LaTeX y `dvisvgm` de MacTeX
  en `/Library/TeX/texbin` funcionan desde `bin/janim` sin más.
- **§2 · Instalar.** Confirmado: `import wgpu` moría sin `rubicon-objc`. Está
  en `[tool.janim.bootstrap]` con el marcador `sys_platform == 'darwin'`; el
  wheel de wgpu trae wgpu-native 24.0.0.2 y pasa `NATIVE_VERSION`.
- **§3 · Metal.** Confirmado. `context.BACKEND` (`"Metal"` en darwin,
  `"Vulkan"` en el resto) manda en `native.py`: el bit de la instancia, el
  `backendType` que acepta `_adapter_information` y los mensajes. El
  adaptador es «Apple M1 · IntegratedGPU · Metal», con `vendor`,
  `architecture` y `description` vacíos (slug `apple`, versión `unknown`),
  alineaciones 256/256 y `float32-filterable`. `JANIM_HEADLESS=1` da el error
  con la lista de adaptadores, como se esperaba. Renders correctos a la vista:
  `c1_01/01`, `c1_03/04_latex`, `c1_03/06_tex_transformations`,
  `demo/03_portals`, `demo/07_text_mask`, `c2_03/03_camera_3d`. Determinismo
  entre procesos: `03_portals` (140 frames) y `07_text_mask` (141) dan hashes
  idénticos en dos procesos.
- **§4 · Fuentes.** Confirmado contra el código de FreeTypeAbstraction
  (`__init__`: recursión solo en `Sys.isunix() && !Sys.isapple()`) y BaseDirs
  (`darwin.jl`): en macOS, las cinco carpetas planas y en ese orden. El
  catálogo del M1 tiene 463 caras; «DejaVu Sans» resuelve a
  `~/Library/Fonts/DejaVuSans.ttf`.
- **§5 · Lo demás.** Confirmado. `_headless_env` devuelve falso en darwin;
  `JANIM_GLFW_PLATFORM` admite `null` o `cocoa` en macOS (y sigue admitiendo
  `null`, `wayland` o `x11` en Linux, con el mismo mensaje). `readlink -f`
  funciona en `bin/janim`.
- **§6 · La ventana en vivo.** Funciona con menos de lo previsto: bastó
  devolver `{"platform": "cocoa", "window": NSWindow}` en `native_handles`
  y aceptar `cocoa` en `create_window`; la rama darwin de wgpu-py crea la
  `CAMetalLayer`. La superficie ofrece `bgra8unorm-srgb` primero (se usa
  `bgra8unorm`), Fifo e Immediate, y CopySrc. **Retina:** wgpu-py deja
  `contentsScale = 1.0`; wgpu-native sí pone `drawableSize` al tamaño del
  framebuffer (2560×1440 sobre 1280×720 puntos), así que no sale «un cuarto
  de la ventana». `glfw.sync_content_scale` pone `contentsScale =
  backingScaleFactor` (2.0) al crear la surface y al reconfigurar, como hace
  GLFW con sus surfaces de Vulkan. Medido con `present_readback`: cada píxel
  del frame ocupa exactamente un bloque 2×2 del swapchain. Dos previews
  seguidas abren y cierran limpias; el drenaje de foco de Wayland no estorba
  (termina sin agotar el tope). El hilo del playhead no toca GLFW, no hubo
  que cambiar nada. **Teclas y ratón:** probados a mano por Alex, incluido
  el movimiento de cámara: funcionan, y el problema del §6.7 no aparece
  (los callbacks usan coordenadas lógicas de forma consistente).
- **§7 · Python contra Julia.** Hecho en el mismo Mac, con los dos arneses
  del §6 de Janim.jl. Cuatro demos (`01`, `03`, `04`, `07`) salieron
  idénticas byte a byte a la primera; `11_chase_camera` difería en los 220
  frames, y **las tres hipótesis de esta sección eran falsas**: las fuentes
  resolvían al mismo fichero, la geometría de la CPU (`knot`, `atan2`,
  rotaciones) y cada byte subido a la GPU (puntos, normales, índices,
  uniformes) eran idénticos en las dos bibliotecas. La diferencia estaba en
  los píxeles de los tres `Torus` (±1 a ±4 de 255) y la causa es que Python
  fusiona en un solo `draw_indexed` las mallas consecutivas que comparten
  pipeline, bloque de uniformes y textura (`render.py`, `_record_commands`),
  mientras Julia emite una llamada por malla: en Metal el color iluminado
  que se interpola sobre un triángulo cambia en el último bit según la
  llamada que lo lleva (partir una sola malla en dos llamadas ya mueve
  píxeles; con `@interpolate(flat)` no), y en RADV no. El arreglo está en
  `render.py`: `_MERGE_MESH_DRAWS = BACKEND != "Metal"`, una llamada por
  malla en Metal, como en Janim.jl. En Linux `BACKEND` es Vulkan y el bucle
  de fusión es el mismo de hoy. Con el arreglo, las cinco demos dan frames
  idénticos entre Python y Julia (140, 140, 180, 141 y 220), y las cuatro
  que ya coincidían no cambiaron ni un byte.
- **Lo que no cambió:** `live.py`, `cli.py`, `tex.py`, `video.py`.

## Resultado · 2026-10-22, revisión tras el port a Windows (macOS 26.6.2, Apple M1, Python 3.14.7)

**Nada cambió en el Mac.** Revisado con un clon limpio de `main` (`7f54aa3`)
frente al último `main` anterior al port a Windows (`ce98cf2`), con el guion
del `LINUX.md`, en esta sesión:

- **Instalación desde cero** con las líneas de macOS del README.
  `scripts/bootstrap.sh` (que ahora llama a `scripts/bootstrap.py`) crea el
  venv con exactamente los mismos paquetes que antes (`pip list` idéntico,
  `janim.pth` en su sitio); `gpu_info()` dice «Apple M1 · metal ·
  integrated»; el `frame` y el `render -ql` del apartado «Check it» salen.
- **Frames antes y después, byte a byte** (`tapf.py`, 640×360 a 10 fps):
  `01_multicam` (140), `03_portals` (140), `04_lorenz_glow` (180),
  `06_broadcast` (198, la del CRT con el `select`), `07_text_mask` (141) y
  `11_chase_camera` (220) dan la misma lista de hashes con los dos checkouts.
  Las cinco de referencia siguen idénticas entre Python y Julia. La clase de
  `06_broadcast` es `BroadcastScene` (el `LINUX.md` decía `Broadcast`;
  corregido).
- **CLI** (sin `-p` ni la ventana desde la CLI, que abren algo que solo Alex
  cierra): `render -qs`, `-j 2` (140 frames, 2 procesos; el mismo contenido
  que el render de un proceso, a 45 dB de PSNR por la codificación por
  segmentos, exactamente igual que en Julia), `-t` (ProRes 4444,
  `yuva444p12le`), `-s --to 40`, `frame`, y `-o` relativa con `--out_dir`.
- **Ventana en vivo** en proceso (`live(…, max_seconds=3)`, dos sesiones
  seguidas): Cocoa, `CAMetalLayer`, `contentsScale` 2.0, 2560×1440 sobre
  1280×720 puntos, 84 presentaciones por sesión, sin reconfiguraciones,
  cierra limpia. `JANIM_HEADLESS=1` sigue dando el error con la lista de
  adaptadores.
- **Las 12 demos a 1080p60** (`bin/janim render … -qh`), una cada vez: 11
  salen; `12_motion_blur` falla por la fuente «Fredoka Expanded», como en
  Windows. Las de `01` a `07` son idénticas fotograma a fotograma a las
  renderizadas el 2026-10-21, antes del port a Windows.

**Python contra Julia en los mp4 a 1080p60** (decodificados y comparados
fotograma a fotograma): `01`, `03`, `04`, `07` y `10` idénticos.
`11_chase_camera` difiere en 28 fotogramas (972–1000, a 54–58 dB) con
fotogramas crudos idénticos: el arnés a 1920×1080/60 da 1320 hashes iguales,
y `frame 972` y `frame 990` por las dos CLIs dan los mismos píxeles. La causa
es el codificador: Janim.jl escribe con el ffmpeg de FFMPEG_jll (x264 core
164) y Janim.py con el del `PATH` (Homebrew ffmpeg 9.0.1, x264 core 165).
Para comparar las dos bibliotecas valen los arneses, no los mp4. `02`, `05`,
`06`, `08` y `09` difieren en todos los fotogramas, como en Linux: en `08` y
`09` el texto del demo nombra el lenguaje; en `02`, `05` y `06` lo visible a
ojo es el espaciado del `Tex` (Janim.jl separa los glifos; Python los compone
con el kerning de LaTeX).

**Tiempos a 1080p60**, reloj del proceso `bin/janim render` entero, un
render cada vez (Julia a través del daemon caliente); los de Windows son los
del `LINUX.md`, §5 (Ryzen 7 9700X, Radeon RX 9070 XT, DX12):

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
| 12_motion_blur | — | falla | falla | falla | falla |
| total 01–11 | 10 242 | 547 s | 492 s | 180 s | 138 s |

En las demos pesadas de GPU (`02`, `04`, `05`, `08`, `09`) Python y Julia
tardan lo mismo en el M1: el límite es la GPU integrada, de 5 a 10 veces más
lenta que la RX 9070 XT. `04` y `07` en Python siguen siendo trabajo de CPU
(numpy), como en Windows.

## 0 · Reglas de trabajo

- **El objetivo** es que en un M1 funcionen el render a fichero, la CLI
  `bin/janim` y la ventana en vivo.
- **Linux no puede cambiar.** Todo lo específico de macOS va dentro de
  `sys.platform == "darwin"`, y en Linux el código que corre y los frames que
  salen deben ser los mismos que hoy. Al volver a la máquina Linux, se repite
  allí la comparación de frames contra la versión anterior.
- **No hay frames de referencia en el repo.** En Metal muchos bordes cambiarán
  un píxel respecto a Linux, así que una diferencia de bytes no es un fallo.
  Lo que hay que buscar es que algo se vea MAL. Las escenas se miran; un exit 0
  no dice nada de lo que hay en pantalla.
- **Commits solo con permiso de Alex, y nunca push.** Un commit por arreglo,
  en español, que explique el porqué. Ninguna dependencia nueva sin preguntar:
  la única que hace falta seguro es `rubicon-objc` (§2), y también se
  pregunta. Solo texto y SVG en git.
- **El orden que sugiero:**
  1. Instalar.
  2. Que la instancia elija Metal.
  3. Renderizar a fichero una escena simple.
  4. Probar fórmulas, capas y 3D.
  5. Dejar la ventana en vivo para el final.

## 1 · Preparar el Mac

- **macOS 14 o posterior**: el wheel de `numpy==2.4.6` para cp314 arm64 es
  `macosx_14_0`.
- **Python 3.14**: `brew install python@3.14`, o el instalador de python.org.
- **ffmpeg** en el `PATH`: `brew install ffmpeg`. Janim lo llama por nombre,
  `ffmpeg`/`ffprobe`.
- **Fuentes:** `brew install --cask font-dejavu`, que las deja en
  `~/Library/Fonts`. Los ejemplos piden DejaVu Sans, y una familia que falta es
  un `FontNotFound` a propósito, no un sustituto silencioso.
- **LaTeX, opcional, para `Tex`/`MathTex`:** MacTeX o BasicTeX, más `dvisvgm`,
  en `/Library/TeX/texbin`. Comprueba que esa carpeta está en el `PATH` del
  proceso, no solo en el de la terminal.

## 2 · Instalar: un arreglo seguro antes de empezar

`scripts/bootstrap.sh` instala con `--only-binary=:all: --no-deps` las
versiones fijadas de `pyproject.toml`. Comprobado desde Linux con
`pip download --platform macosx_14_0_arm64 --python-version 3.14`: **existen
wheels de macOS arm64 para todas**. Las que llevan código nativo:

| paquete | qué trae para macOS |
|---|---|
| `wgpu==0.21.0` | `wgpu/resources/libwgpu_native-release.dylib`, wgpu-native **v24.0.0.2**, la misma versión que el wheel de Linux, así que `NATIVE_VERSION = (24, 0)` en `janim/backend/wgpu/context.py` pasa |
| `glfw==2.10.2` | `glfw/libglfw.3.dylib` |
| `freetype-py==2.5.1` | wheel `universal2` |
| `cffi==2.1.1` | `cp314 macosx_11_0_arm64` |

**Lo que va a fallar:** el `METADATA` de wgpu 0.21.0 declara
`rubicon-objc>=0.4.1; sys_platform == 'darwin'`, y
`wgpu/backends/wgpu_native/_helpers.py:33` lo importa al cargar el módulo en
macOS. Con `--no-deps` no se instala, así que `import wgpu` fallará.

- **El arreglo** que sugiero (dependencia nueva: pide permiso a Alex) es
  añadir `"rubicon-objc==0.5.7; sys_platform == 'darwin'"` a
  `[tool.janim.bootstrap] dependencies` en `pyproject.toml`. Es un wheel
  `py3-none-any`, y pip respeta el marcador, así que en Linux no cambia nada.
- **Después:**

  ```bash
  PYTHON=python3.14 scripts/bootstrap.sh
  .venv/bin/python -c "import janim, wgpu; print(wgpu.__version__)"
  ```

## 3 · Que la instancia elija Metal (lo primero que fallará al renderizar)

1. **La instancia se crea SOLO con Vulkan**:
   `janim/backend/wgpu/native.py:62-64` (`extras.backends = 1 << 0`).
   - En `wgpu.h`: Vulkan es `1 << 0`, GL `1 << 1`, Metal `1 << 2` y DX12
     `1 << 3`. Compruébalo en `wgpu/resources/wgpu.h`.
   - Julia ya lo hace en `src/backend/wgpu/context.jl:242`, con Metal en macOS.
     Copia esa regla, dentro de `sys.platform == "darwin"`.
2. **`_adapter_information` rechaza todo lo que no sea Vulkan**
   (`native.py:77`) y escribe `backend_type="Vulkan"` fijo (`:89`). Acepta
   `lib.WGPUBackendType_Metal` en macOS y pon el nombre real.
3. **Mensajes que dicen «Vulkan»:** `native.py:49`, `:69` y
   `janim/backend/wgpu/context.py:1` y `:110`. Que digan el backend de verdad.
4. **`JANIM_HEADLESS=1` no funciona en macOS.** Pide el adaptador de CPU de
   Mesa (lavapipe), que en macOS no existe. `choose_adapter`
   (`context.py:103-125`) ya da un error con la lista de adaptadores, y es el
   comportamiento correcto. Sin la variable, elige la GPU integrada del M1.
5. **Los límites del dispositivo:** `native.py:226-227` pide las alineaciones
   del adaptador, y `uniforms.py:154` las usa. En Metal pueden ser 256, no 32;
   el código ya lo admite. `float32-filterable` se pide solo si existe.
6. **Un pánico de wgpu-native mata el proceso de Python.** Si muere en seco,
   repite con `JANIM_WGPU_LOG=info` (o `debug`) y mira la última llamada.

Primera prueba:

```bash
bin/janim render examples/tutorial/c1_01_basics/01_how_janim_works.py -ql
```

Luego, en este orden:

- **Fórmulas:** `examples/tutorial/c1_03_groups_and_text/`.
- **Capas y efectos:** `examples/demo/03_portals.py`.
- **3D:** `examples/tutorial/c2_03_camera/` y `examples/demo/07_text_mask.py`.

Mira el centro de cada Transform, el primer frame y el último
(`bin/janim frame …`).

## 4 · Fuentes: el catálogo solo conoce las carpetas de Linux

`janim/text/glyphs.py:27-45` (`_font_catalog`) recorre las raíces XDG de Unix.
En macOS no encontrará nada fuera de `~/.local/share/fonts`.

Que imite exactamente a FreeTypeAbstraction, el buscador que usa Janim.jl.
En macOS, ese buscador usa las carpetas de `BaseDirs.fonts()`, en este orden y
**sin entrar en subcarpetas**:

1. `~/Library/Fonts`
2. `/Library/Fonts`
3. `/System/Library/Fonts`
4. `/System/Library/Fonts/Supplemental`
5. `/Network/Library/Fonts`

Si el orden o el recorrido difieren, las dos bibliotecas pueden elegir caras
distintas para el mismo nombre. Se notaría en la comparación del §7, aunque
cada una se vea bien por separado.

Las `.ttc` (colecciones) tienen varias caras. Hoy, como FreeTypeAbstraction,
se carga solo la primera (`freetype.Face(path)`): no lo cambies sin cambiarlo
en los dos lados.

## 5 · Lo demás que está escrito para Linux

- **GLFW:** `janim/backend/glfw.py:13`, `LIBRARY = "/usr/lib64/libglfw.so.3"`,
  solo se usa si existe. En macOS se cargará la `libglfw.3.dylib` del wheel.
  `:14` (`X_LOCALE_DIRECTORY`) solo aplica si existe.
- **¿Hay pantalla?** `glfw.py:50-53` (`_headless_env`) decide «no hay
  pantalla» si faltan `DISPLAY` y `WAYLAND_DISPLAY`, que en macOS nunca
  existen. Haz que en darwin cuente como pantalla. Julia lo restringe a Linux
  en `src/backend/glfw.jl:186`.
- **La plataforma:** `glfw.py:71-90` solo conoce Null, Wayland y X11. Añade
  `glfw.PLATFORM_COCOA` a la tabla de `JANIM_GLFW_PLATFORM` y a los nombres
  (`:89`), como `"cocoa"`.
- **`-p`** ya abre con `open` en macOS (`janim/cli.py:329`).
- **`bin/janim`** usa `readlink -f`, que necesita macOS 12.3 o posterior, y el
  `.venv/bin/python` del checkout.

## 6 · La ventana en vivo: lo que falta escribir

1. **La fuente de la superficie.** `glfw.py:115-127` (`native_handles`) solo
   devuelve Wayland o X11. Para Cocoa, devuelve
   `{"platform": "cocoa", "window": int(glfw.get_cocoa_window(window.handle))}`.
   `native.create_surface` (`native.py:297-301`) se lo pasa a
   `_helpers.get_surface_id_from_info` de wgpu-py. Su rama `darwin` ya crea la
   `CAMetalLayer` sobre el `contentView` del `NSWindow` con rubicon-objc, y la
   superficie `WGPUSurfaceSourceMetalLayer`. No hay que escribir Objective-C.
2. **`create_window`** (`janim/backend/wgpu/window.py:221-232`) solo acepta
   `"wayland"` y `"x11"`: añade `"cocoa"`.
3. **Retina.** El presentador ya se configura con `framebuffer_size` (píxeles
   físicos, `window.py:225`), que en Retina es el doble que la ventana. La capa
   que crea wgpu-py no ajusta `contentsScale`. Si la imagen sale borrosa o en
   un cuarto de la ventana, pon `contentsScale = backingScaleFactor` del
   `NSWindow` sobre la capa (con rubicon). En la era OpenGL, este error dio una
   ventana negra en este mismo M1.
4. **El formato:** `window.py:25-28` ya maneja `bgra8unorm`, que es lo que
   preferirá Metal.
5. **El hilo principal.** Cocoa exige ventanas y eventos en el hilo principal.
   - La preview simula la escena en un hilo aparte (`janim/interactive/live.py:220`,
     `janim-playhead`), y el bucle de eventos y el presente van en el principal
     (`live.py:240`).
   - Comprueba que ninguna llamada a GLFW (ni `create_window`, ni callbacks
     instalados desde el otro hilo) ocurre fuera del hilo principal.
   - Si la ventana se congela o el proceso muere al abrirla, sospecha esto
     primero.
6. **El parche de Wayland** (`glfw.py:160-200`) esconde la ventana y bombea
   eventos antes de destruirla. Si en macOS estorba, limítalo a Linux.
7. **El ratón en Retina.** El cursor llega en coordenadas lógicas y el
   framebuffer está en físicas. Si orbitar o arrastrar va al doble o a la
   mitad de velocidad, la mezcla está en los callbacks de `live.py` (hacia
   `:540-600`) y en `janim/interactive/`.

Prueba con `bin/janim examples/demo/03_portals.py`: teclas (espacio, `,`/`.`,
←/→, `[`/`]`, Esc), ratón, y abrir y cerrar dos previews seguidas.

## 7 · Un instrumento sin Linux: Python contra Julia en el mismo Mac

En Linux (RADV, 640×360 a 10 fps) estas cinco demos dan **frames idénticos
byte a byte** en Janim.py y en Janim.jl, medido el 2026-10-21:

| demo | clase | frames |
|---|---|---|
| `01_multicam` | `Multicam` | 140 |
| `03_portals` | `Portals` | 140 |
| `04_lorenz_glow` | `LorenzGlow` | 180 |
| `07_text_mask` | `TextMask` | 141 |
| `11_chase_camera` | `ChaseCamera` | 220 |

Las otras ya difieren en Linux: la 08 por su texto en pantalla, y las 02, 05,
06 y 09 por causas no investigadas. No las uses. En el Mac las dos
bibliotecas deberían seguir coincidiendo entre sí. Los dos arneses (hashes por
frame con `frame_tap` en Python y `Janim._FRAME_TAP` en Julia) están en el
`MACOS.md` de Janim.jl, §6. Guárdalos fuera del repo.

Si en el Mac no coinciden y en Linux sí, por orden:

1. **Las fuentes.** Mira el §4: el mismo nombre resuelto a caras distintas.
2. **La libm.** Python usa `math.sin`/`math.cos`/`math.tan` del sistema en
   algunos sitios, y Julia usa sus propias implementaciones:
   - `janim/animation/transform.py:129-132` (`path_arc`);
   - `janim/animation/indication.py:61` y `:99`;
   - `janim/animation/homotopy.py:63` (`ApplyWave`);
   - `janim/backend/wgpu/effects.py:95` y `:238-243` (ángulos de efectos);
   - `janim/core/decor.py:146-153`.

   La glibc de Linux da los mismos bits que Julia en estos casos; la libm de
   Apple puede no darlos en el último ulp. El arreglo es usar `sin`/`cos`/`tan`
   de `janim/core/_julia_math.py`, el port de Julia Base que ya usa
   `janim/core/surface.py` (`_julia_trig`). Cámbialo solo si en Linux los
   frames siguen idénticos: allí glibc y Julia coinciden en estos casos, no en
   todos los valores posibles.
3. **numpy.** `janim/core/bezier.py` usa `np.sin`/`np.cos`, y numpy tiene sus
   propias implementaciones vectoriales por arquitectura: NEON en arm64 y AVX
   en x86. Pueden diferir en el último bit entre las dos máquinas.

**Determinismo:** la misma escena en dos procesos del Mac debe dar los mismos
frames. No debería depender de la GPU; compruébalo con un par de escenas.

## 8 · Lo que no es un problema del Mac

- **El desenfoque de movimiento en vídeo no existe** en ninguna plataforma.
  `Scene` no acepta `motion_blur` y la CLI rechaza `--motion-blur`. Las demos
  10 y 12 y las lecciones de `c3_05_motion_blur` lo describen.
- **`c2_05_from_manim/01_from_manim_ce.py` dice que `-ql` no existe**, pero la
  CLI sí lo tiene.

## 9 · Al terminar

Deja aquí, en este fichero, lo que confirmaste y lo que resultó falso, y en la
sección «Known limitations» de los dos README cambia «Linux only» por lo que
de verdad funcione, con la versión de macOS y el chip en que se probó.
